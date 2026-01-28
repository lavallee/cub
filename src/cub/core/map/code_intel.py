"""
Code intelligence module using tree-sitter and PageRank.

Provides symbol extraction from source files using tree-sitter AST parsing,
and ranks symbols by importance using a PageRank algorithm on the
definition/reference graph. Adapted from Aider's repo map approach.

This module degrades gracefully: if tree-sitter or grep-ast are unavailable,
all public functions return empty results with a logged warning.

Main entry points:
    - extract_tags(): Parse source files and extract symbol definitions/references
    - rank_symbols(): Rank extracted symbols by importance using PageRank

Example:
    >>> from cub.core.map.code_intel import extract_tags, rank_symbols
    >>> tags = extract_tags(Path("/path/to/project"), [Path("src/main.py")])
    >>> ranked = rank_symbols(tags, token_budget=2048)
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


@runtime_checkable
class _CacheLike(Protocol):
    """Protocol for diskcache.Cache-like objects."""

    def get(self, key: str) -> object: ...
    def set(self, key: str, value: object) -> None: ...


@runtime_checkable
class _PathSpecLike(Protocol):
    """Protocol for pathspec.PathSpec-like objects."""

    def match_file(self, path: str) -> bool: ...

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful import of optional dependencies
# ---------------------------------------------------------------------------

_HAS_TREE_SITTER = False
_HAS_NETWORKX = False
_HAS_DISKCACHE = False
_HAS_PATHSPEC = False

try:
    from grep_ast.parsers import filename_to_lang
    from tree_sitter import Query, QueryCursor
    from tree_sitter_language_pack import (
        get_language,
        get_parser,
    )

    _HAS_TREE_SITTER = True
except ImportError:
    logger.warning(
        "tree-sitter dependencies not available. "
        "Install grep-ast, tree-sitter, and tree-sitter-language-pack "
        "for code intelligence features."
    )

try:
    import networkx as nx

    _HAS_NETWORKX = True
except ImportError:
    logger.warning(
        "networkx not available. Install networkx for symbol ranking features."
    )

try:
    import diskcache

    _HAS_DISKCACHE = True
except ImportError:
    logger.debug("diskcache not available; using in-memory tag cache.")

try:
    import pathspec

    _HAS_PATHSPEC = True
except ImportError:
    logger.debug("pathspec not available; .gitignore filtering disabled.")

# Pygments fallback for reference extraction
try:
    from pygments.lexers import guess_lexer_for_filename
    from pygments.token import Token as PygmentsToken

    _HAS_PYGMENTS = True
except ImportError:
    _HAS_PYGMENTS = False


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class SymbolTag(BaseModel):
    """A symbol tag extracted from source code via tree-sitter.

    Represents either a definition (class, function, variable) or a reference
    (usage of a symbol defined elsewhere).
    """

    model_config = ConfigDict(frozen=True)

    rel_path: str = Field(..., description="Relative file path from project root")
    abs_path: str = Field(..., description="Absolute file path")
    name: str = Field(..., description="Symbol name (identifier text)")
    kind: str = Field(
        ...,
        description="Tag kind: 'def' for definitions, 'ref' for references",
    )
    line: int = Field(
        ...,
        description="Line number (0-indexed); -1 for synthetic references",
    )


class RankedSymbol(BaseModel):
    """A symbol ranked by importance using PageRank.

    Higher scores indicate symbols that are more central to the codebase
    structure — i.e., they are defined in files that many other files reference.
    """

    model_config = ConfigDict(frozen=True)

    rel_path: str = Field(..., description="Relative file path containing this symbol")
    name: str = Field(..., description="Symbol name")
    kind: str = Field(..., description="Tag kind: 'def' or 'ref'")
    line: int = Field(..., description="Line number (0-indexed)")
    score: float = Field(..., description="PageRank-derived importance score")


# ---------------------------------------------------------------------------
# Tag queries per language
# ---------------------------------------------------------------------------

# These are tree-sitter query patterns for extracting definition and reference
# tags from source code. Each language maps to a query string that uses
# @name.definition.* and @name.reference.* capture groups.
#
# When no language-specific query is available, we fall back to Pygments
# lexer-based token extraction for references.

_TAG_QUERIES: dict[str, str] = {
    "python": """
(function_definition name: (identifier) @name.definition.function)
(class_definition name: (identifier) @name.definition.class)
(call function: (identifier) @name.reference.call)
(call function: (attribute attribute: (identifier) @name.reference.call))
""",
    "javascript": """
(function_declaration name: (identifier) @name.definition.function)
(class_declaration name: (identifier) @name.definition.class)
(method_definition name: (property_identifier) @name.definition.method)
(call_expression function: (identifier) @name.reference.call)
(call_expression function: (member_expression property: (property_identifier) @name.reference.call))
""",
    "typescript": """
(function_declaration name: (identifier) @name.definition.function)
(class_declaration name: (identifier) @name.definition.class)
(method_definition name: (property_identifier) @name.definition.method)
(interface_declaration name: (type_identifier) @name.definition.interface)
(call_expression function: (identifier) @name.reference.call)
(call_expression function: (member_expression property: (property_identifier) @name.reference.call))
""",
    "rust": """
(function_item name: (identifier) @name.definition.function)
(struct_item name: (type_identifier) @name.definition.struct)
(enum_item name: (type_identifier) @name.definition.enum)
(trait_item name: (type_identifier) @name.definition.trait)
(impl_item type: (type_identifier) @name.definition.impl)
(call_expression function: (identifier) @name.reference.call)
(call_expression function: (field_expression field: (field_identifier) @name.reference.call))
""",
    "go": """
(function_declaration name: (identifier) @name.definition.function)
(method_declaration name: (field_identifier) @name.definition.method)
(type_declaration (type_spec name: (type_identifier) @name.definition.type))
(call_expression function: (identifier) @name.reference.call)
(call_expression function: (selector_expression field: (field_identifier) @name.reference.call))
""",
    "java": """
(class_declaration name: (identifier) @name.definition.class)
(method_declaration name: (identifier) @name.definition.method)
(interface_declaration name: (identifier) @name.definition.interface)
(method_invocation name: (identifier) @name.reference.call)
""",
    "ruby": """
(class name: (constant) @name.definition.class)
(method name: (identifier) @name.definition.method)
(call method: (identifier) @name.reference.call)
""",
    "c": (
        "(function_definition"
        " declarator: (function_declarator"
        " declarator: (identifier) @name.definition.function))\n"
        "(struct_specifier name: (type_identifier) @name.definition.struct)\n"
        "(call_expression function: (identifier) @name.reference.call)\n"
    ),
    "cpp": (
        "(function_definition"
        " declarator: (function_declarator"
        " declarator: (identifier) @name.definition.function))\n"
        "(class_specifier name: (type_identifier) @name.definition.class)\n"
        "(struct_specifier name: (type_identifier) @name.definition.struct)\n"
        "(call_expression function: (identifier) @name.reference.call)\n"
        "(call_expression function: (field_expression"
        " field: (field_identifier) @name.reference.call))\n"
    ),
}

# Aliases for language variants
_TAG_QUERIES["tsx"] = _TAG_QUERIES["typescript"]

# ---------------------------------------------------------------------------
# Default ignore patterns (used when .gitignore unavailable)
# ---------------------------------------------------------------------------

_DEFAULT_IGNORE_PATTERNS: list[str] = [
    ".git/",
    ".hg/",
    ".svn/",
    "node_modules/",
    "__pycache__/",
    ".venv/",
    "venv/",
    ".env/",
    "env/",
    ".tox/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    "dist/",
    "build/",
    "*.egg-info/",
    ".eggs/",
    "target/",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.o",
    "*.a",
    "*.dylib",
    "*.dll",
    "*.class",
    "*.exe",
    "*.wasm",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.lock",
    "*.sum",
    "package-lock.json",
    "yarn.lock",
    "uv.lock",
    "Cargo.lock",
]


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


def _cache_key(file_path: Path) -> str:
    """Build a cache key from a file path, mtime, and size.

    The key changes whenever the file is modified, ensuring stale
    cache entries are never returned.
    """
    try:
        stat = file_path.stat()
        raw = f"{file_path}:{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        # File may have been deleted between listing and stat
        raw = f"{file_path}:missing"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_disk_cache(project_dir: Path) -> _CacheLike | None:
    """Return a diskcache.Cache instance for the project, or None."""
    if not _HAS_DISKCACHE:
        return None
    try:
        cache_dir = project_dir / ".cub" / "cache" / "code_intel"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache: _CacheLike = diskcache.Cache(str(cache_dir))
        return cache
    except Exception:
        logger.debug("Failed to create disk cache; falling back to in-memory", exc_info=True)
        return None


# Module-level in-memory cache as fallback
_memory_cache: dict[str, list[SymbolTag]] = {}


def _cache_get(
    cache: _CacheLike | None,
    key: str,
) -> list[SymbolTag] | None:
    """Retrieve tags from cache (disk or memory)."""
    if cache is not None and _HAS_DISKCACHE:
        try:
            val = cache.get(key)
            if val is not None and isinstance(val, list):
                return [SymbolTag.model_validate(t) for t in val]
        except Exception:
            logger.debug("Disk cache read failed", exc_info=True)
    # Fallback to memory cache
    return _memory_cache.get(key)


def _cache_set(
    cache: _CacheLike | None,
    key: str,
    tags: list[SymbolTag],
) -> None:
    """Store tags in cache (disk and memory)."""
    _memory_cache[key] = tags
    if cache is not None and _HAS_DISKCACHE:
        try:
            # Store as dicts for serialization
            cache.set(key, [t.model_dump() for t in tags])
        except Exception:
            logger.debug("Disk cache write failed", exc_info=True)


# ---------------------------------------------------------------------------
# .gitignore-aware file filtering
# ---------------------------------------------------------------------------


def _load_gitignore_spec(project_dir: Path) -> _PathSpecLike | None:
    """Load .gitignore as a pathspec matcher, or return None."""
    if not _HAS_PATHSPEC:
        return None
    gitignore = project_dir / ".gitignore"
    patterns = list(_DEFAULT_IGNORE_PATTERNS)
    if gitignore.is_file():
        try:
            patterns.extend(gitignore.read_text().splitlines())
        except OSError:
            pass
    try:
        spec: _PathSpecLike = pathspec.PathSpec.from_lines("gitignore", patterns)
        return spec
    except Exception:
        logger.debug("Failed to parse .gitignore patterns", exc_info=True)
        return None


def _is_ignored(
    rel_path: str,
    spec: _PathSpecLike | None,
) -> bool:
    """Check if a relative path should be ignored."""
    if spec is not None:
        try:
            return spec.match_file(rel_path)
        except Exception:
            pass
    # Fallback: check against default patterns by name
    parts = Path(rel_path).parts
    for part in parts:
        if part in {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
            "dist", "build", "target",
        }:
            return True
    return False


# ---------------------------------------------------------------------------
# Tag extraction
# ---------------------------------------------------------------------------


def _extract_tags_for_file(
    file_path: Path,
    rel_path: str,
) -> list[SymbolTag]:
    """Extract symbol tags from a single file using tree-sitter.

    Falls back to Pygments for reference extraction when tree-sitter
    query doesn't capture any references.
    """
    if not _HAS_TREE_SITTER:
        return []

    lang_name = filename_to_lang(str(file_path))
    if not lang_name:
        return []

    try:
        language = get_language(lang_name)
        parser = get_parser(lang_name)
    except Exception:
        logger.debug("No tree-sitter parser for %s (%s)", file_path, lang_name, exc_info=True)
        return []

    try:
        code = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.debug("Cannot read file: %s", file_path)
        return []

    if not code.strip():
        return []

    try:
        tree = parser.parse(bytes(code, "utf-8"))
    except Exception:
        logger.debug("Failed to parse %s", file_path, exc_info=True)
        return []

    tags: list[SymbolTag] = []
    saw_kinds: set[str] = set()

    # Try language-specific query first
    query_str = _TAG_QUERIES.get(lang_name)
    if query_str:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                query = Query(language, query_str)
            cursor = QueryCursor(query)
            captures = cursor.captures(tree.root_node)

            for capture_name, nodes in captures.items():
                if capture_name.startswith("name.definition."):
                    kind = "def"
                elif capture_name.startswith("name.reference."):
                    kind = "ref"
                else:
                    continue

                saw_kinds.add(kind)
                for node in nodes:
                    node_text = node.text
                    if node_text is None:
                        continue
                    tags.append(
                        SymbolTag(
                            rel_path=rel_path,
                            abs_path=str(file_path),
                            name=node_text.decode("utf-8"),
                            kind=kind,
                            line=node.start_point[0],
                        )
                    )
        except Exception:
            logger.debug(
                "Tree-sitter query failed for %s (%s)",
                file_path,
                lang_name,
                exc_info=True,
            )

    # Pygments fallback: if we found definitions but no references,
    # use Pygments lexer to extract identifier tokens as references
    if "ref" not in saw_kinds and "def" in saw_kinds and _HAS_PYGMENTS:
        try:
            lexer = guess_lexer_for_filename(str(file_path), code)
            tokens = list(lexer.get_tokens(code))
            for token_type, token_value in tokens:
                if token_type in PygmentsToken.Name:
                    tags.append(
                        SymbolTag(
                            rel_path=rel_path,
                            abs_path=str(file_path),
                            name=token_value,
                            kind="ref",
                            line=-1,
                        )
                    )
        except Exception:
            logger.debug("Pygments fallback failed for %s", file_path, exc_info=True)

    return tags


def extract_tags(
    project_dir: Path,
    files: list[Path] | None = None,
    *,
    use_cache: bool = True,
) -> list[SymbolTag]:
    """Extract symbol tags from source files in a project.

    Parses each file using tree-sitter to find symbol definitions and
    references. Results are cached per file keyed by (path, mtime, size)
    so unchanged files are not re-parsed.

    Args:
        project_dir: Root directory of the project.
        files: Specific files to analyze. If None, discovers all supported
            source files under project_dir (respecting .gitignore).
        use_cache: Whether to use disk/memory caching. Defaults to True.

    Returns:
        List of SymbolTag objects representing definitions and references.
        Returns an empty list if tree-sitter dependencies are unavailable.
    """
    if not _HAS_TREE_SITTER:
        logger.warning(
            "Code intelligence unavailable: tree-sitter dependencies not installed. "
            "Run: pip install grep-ast tree-sitter-language-pack"
        )
        return []

    project_dir = project_dir.resolve()
    cache = _get_disk_cache(project_dir) if use_cache else None
    ignore_spec = _load_gitignore_spec(project_dir)

    # Discover files if not provided
    if files is None:
        files = _discover_source_files(project_dir, ignore_spec)
    else:
        # Resolve relative paths against project_dir
        files = [
            f if f.is_absolute() else project_dir / f
            for f in files
        ]

    all_tags: list[SymbolTag] = []
    for file_path in files:
        file_path = file_path.resolve()
        if not file_path.is_file():
            continue

        try:
            rel_path = str(file_path.relative_to(project_dir))
        except ValueError:
            rel_path = str(file_path)

        if _is_ignored(rel_path, ignore_spec):
            continue

        # Check cache
        key = _cache_key(file_path)
        if use_cache:
            cached = _cache_get(cache, key)
            if cached is not None:
                all_tags.extend(cached)
                continue

        # Extract tags
        file_tags = _extract_tags_for_file(file_path, rel_path)

        # Cache results
        if use_cache:
            _cache_set(cache, key, file_tags)

        all_tags.extend(file_tags)

    return all_tags


def _discover_source_files(
    project_dir: Path,
    ignore_spec: _PathSpecLike | None,
) -> list[Path]:
    """Walk project_dir and discover source files supported by tree-sitter."""
    if not _HAS_TREE_SITTER:
        return []

    found: list[Path] = []
    for root, dirs, filenames in os.walk(project_dir, topdown=True):
        root_path = Path(root)

        # Prune ignored directories in-place
        try:
            rel_root = str(root_path.relative_to(project_dir))
        except ValueError:
            rel_root = str(root_path)

        dirs[:] = [
            d
            for d in dirs
            if not _is_ignored(
                os.path.join(rel_root, d) + "/",
                ignore_spec,
            )
            and not d.startswith(".")
        ]

        for fname in filenames:
            if fname.startswith("."):
                continue
            file_path = root_path / fname
            rel_file = os.path.join(rel_root, fname) if rel_root != "." else fname
            if _is_ignored(rel_file, ignore_spec):
                continue
            lang = filename_to_lang(fname)
            if lang:
                found.append(file_path)

    return found


# ---------------------------------------------------------------------------
# Symbol ranking via PageRank
# ---------------------------------------------------------------------------


def rank_symbols(
    tags: list[SymbolTag],
    token_budget: int = 4096,
    *,
    focus_files: list[str] | None = None,
    mentioned_identifiers: set[str] | None = None,
) -> list[RankedSymbol]:
    """Rank symbols by importance using PageRank on the def/ref graph.

    Builds a directed graph where:
    - Nodes are relative file paths
    - Edges point from a file that references a symbol to the file that
      defines it, weighted by frequency and naming conventions

    Then runs PageRank and distributes file-level scores to individual
    symbol definitions.

    Args:
        tags: List of SymbolTag objects from extract_tags().
        token_budget: Maximum number of tokens worth of symbols to return.
            Each symbol line is estimated at ~10 tokens.
        focus_files: Files to boost in ranking (e.g., files being edited).
        mentioned_identifiers: Identifiers to boost (e.g., from conversation).

    Returns:
        List of RankedSymbol sorted by score (highest first).
        Returns an empty list if networkx is unavailable or tags are empty.
    """
    if not _HAS_NETWORKX:
        logger.warning(
            "Symbol ranking unavailable: networkx not installed. "
            "Run: pip install networkx"
        )
        return []

    if not tags:
        return []

    focus_files_set = set(focus_files) if focus_files else set()
    mentioned_idents = mentioned_identifiers or set()

    # Build definition and reference maps
    # defines: {identifier: set of files that define it}
    # references: {identifier: list of files that reference it}
    defines: dict[str, set[str]] = defaultdict(set)
    references: dict[str, list[str]] = defaultdict(list)
    all_defs: dict[str, list[SymbolTag]] = defaultdict(list)

    for tag in tags:
        if tag.kind == "def":
            defines[tag.name].add(tag.rel_path)
            all_defs[tag.name].append(tag)
        elif tag.kind == "ref":
            references[tag.name].append(tag.rel_path)

    # Build the graph
    graph: nx.MultiDiGraph = nx.MultiDiGraph()

    # Self-edges for definitions without references (low weight)
    for ident, definers in defines.items():
        if ident in references:
            continue
        for definer in definers:
            graph.add_edge(definer, definer, weight=0.1, ident=ident)

    # Cross-file edges from references to definitions
    all_idents = set(defines.keys()) & set(references.keys())

    for ident in all_idents:
        definers = defines[ident]
        weight_mul = 1.0

        # Boost well-named identifiers
        is_snake = "_" in ident and any(c.isalpha() for c in ident)
        is_kebab = "-" in ident and any(c.isalpha() for c in ident)
        is_camel = any(c.isupper() for c in ident) and any(
            c.islower() for c in ident
        )

        if ident in mentioned_idents:
            weight_mul *= 10.0
        if (is_snake or is_kebab or is_camel) and len(ident) >= 8:
            weight_mul *= 10.0
        if ident.startswith("_"):
            weight_mul *= 0.1
        # Penalize overly-common identifiers (defined in many places)
        if len(definers) > 5:
            weight_mul *= 0.1

        for referencer, num_refs in Counter(references[ident]).items():
            for definer in definers:
                use_mul = weight_mul
                if referencer in focus_files_set:
                    use_mul *= 50.0

                edge_weight = use_mul * math.sqrt(num_refs)
                graph.add_edge(
                    referencer, definer, weight=edge_weight, ident=ident
                )

    if not graph.nodes:
        return []

    # Run PageRank
    try:
        personalization: dict[str, float] | None = None
        if focus_files_set:
            personalization = {}
            for node in graph.nodes:
                personalization[node] = (
                    10.0 if node in focus_files_set else 1.0
                )

        pagerank_scores: dict[str, float] = nx.pagerank(
            graph,
            weight="weight",
            personalization=personalization,
        )
    except Exception:
        logger.debug("PageRank computation failed", exc_info=True)
        # Fallback: uniform scores
        n = len(graph.nodes)
        pagerank_scores = {node: 1.0 / n for node in graph.nodes}

    # Distribute file scores to individual definitions
    ranked: list[RankedSymbol] = []
    for ident, def_tags in all_defs.items():
        for tag in def_tags:
            file_score = pagerank_scores.get(tag.rel_path, 0.0)
            # Boost score if this identifier was mentioned
            if ident in mentioned_idents:
                file_score *= 5.0
            ranked.append(
                RankedSymbol(
                    rel_path=tag.rel_path,
                    name=tag.name,
                    kind=tag.kind,
                    line=tag.line,
                    score=file_score,
                )
            )

    # Sort by score descending, then by file path and name for stability
    ranked.sort(key=lambda s: (-s.score, s.rel_path, s.name))

    # Apply token budget: estimate ~10 tokens per symbol line
    max_symbols = max(1, token_budget // 10)
    return ranked[:max_symbols]
