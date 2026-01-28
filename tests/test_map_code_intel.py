"""
Tests for code intelligence module (tree-sitter + PageRank).

Tests cover:
- SymbolTag and RankedSymbol Pydantic models
- Tag extraction from Python source files
- Pygments fallback for reference extraction
- File discovery and .gitignore filtering
- Cache key generation and caching behavior
- PageRank-based symbol ranking
- Graceful degradation when dependencies are missing
- Integration test against the cub repo itself
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from cub.core.map.code_intel import (
    RankedSymbol,
    SymbolTag,
    _cache_get,
    _cache_key,
    _cache_set,
    _discover_source_files,
    _extract_tags_for_file,
    _is_ignored,
    _load_gitignore_spec,
    _memory_cache,
    extract_tags,
    rank_symbols,
)

# ==============================================================================
# SymbolTag Model Tests
# ==============================================================================


class TestSymbolTag:
    """Test SymbolTag Pydantic model."""

    def test_create_definition_tag(self) -> None:
        """Test creating a definition tag."""
        tag = SymbolTag(
            rel_path="src/main.py",
            abs_path="/project/src/main.py",
            name="MyClass",
            kind="def",
            line=10,
        )
        assert tag.rel_path == "src/main.py"
        assert tag.abs_path == "/project/src/main.py"
        assert tag.name == "MyClass"
        assert tag.kind == "def"
        assert tag.line == 10

    def test_create_reference_tag(self) -> None:
        """Test creating a reference tag."""
        tag = SymbolTag(
            rel_path="src/utils.py",
            abs_path="/project/src/utils.py",
            name="helper_func",
            kind="ref",
            line=25,
        )
        assert tag.kind == "ref"
        assert tag.name == "helper_func"

    def test_synthetic_reference_line(self) -> None:
        """Test reference with line=-1 (Pygments fallback)."""
        tag = SymbolTag(
            rel_path="src/main.py",
            abs_path="/project/src/main.py",
            name="SomeToken",
            kind="ref",
            line=-1,
        )
        assert tag.line == -1

    def test_immutable(self) -> None:
        """Test that SymbolTag is frozen (immutable)."""
        tag = SymbolTag(
            rel_path="src/main.py",
            abs_path="/project/src/main.py",
            name="foo",
            kind="def",
            line=1,
        )
        with pytest.raises(Exception):
            tag.name = "bar"  # type: ignore[misc]

    def test_serialization(self) -> None:
        """Test model_dump and model_validate round-trip."""
        tag = SymbolTag(
            rel_path="src/main.py",
            abs_path="/project/src/main.py",
            name="my_func",
            kind="def",
            line=42,
        )
        data = tag.model_dump()
        assert isinstance(data, dict)
        restored = SymbolTag.model_validate(data)
        assert restored == tag


# ==============================================================================
# RankedSymbol Model Tests
# ==============================================================================


class TestRankedSymbol:
    """Test RankedSymbol Pydantic model."""

    def test_create_ranked_symbol(self) -> None:
        """Test creating a ranked symbol."""
        ranked = RankedSymbol(
            rel_path="src/core.py",
            name="Engine",
            kind="def",
            line=5,
            score=0.85,
        )
        assert ranked.rel_path == "src/core.py"
        assert ranked.name == "Engine"
        assert ranked.score == 0.85

    def test_immutable(self) -> None:
        """Test that RankedSymbol is frozen."""
        ranked = RankedSymbol(
            rel_path="src/core.py",
            name="Engine",
            kind="def",
            line=5,
            score=0.85,
        )
        with pytest.raises(Exception):
            ranked.score = 0.5  # type: ignore[misc]


# ==============================================================================
# Tag Extraction Tests (Unit)
# ==============================================================================


class TestExtractTagsForFile:
    """Test _extract_tags_for_file with real tree-sitter parsing."""

    def test_extract_python_definitions(self, tmp_path: Path) -> None:
        """Test extracting class and function definitions from Python."""
        source = tmp_path / "example.py"
        source.write_text(
            "class Greeter:\n"
            "    def greet(self, name):\n"
            "        return f'Hello {name}'\n"
            "\n"
            "def main():\n"
            "    g = Greeter()\n"
            "    g.greet('world')\n"
        )
        tags = _extract_tags_for_file(source, "example.py")
        def_names = {t.name for t in tags if t.kind == "def"}
        assert "Greeter" in def_names
        assert "greet" in def_names
        assert "main" in def_names

    def test_extract_python_references(self, tmp_path: Path) -> None:
        """Test extracting call references from Python."""
        source = tmp_path / "caller.py"
        source.write_text(
            "def main():\n"
            "    result = compute(42)\n"
            "    print(result)\n"
        )
        tags = _extract_tags_for_file(source, "caller.py")
        ref_names = {t.name for t in tags if t.kind == "ref"}
        assert "compute" in ref_names
        assert "print" in ref_names

    def test_extract_empty_file(self, tmp_path: Path) -> None:
        """Test that empty files produce no tags."""
        source = tmp_path / "empty.py"
        source.write_text("")
        tags = _extract_tags_for_file(source, "empty.py")
        assert tags == []

    def test_extract_whitespace_only_file(self, tmp_path: Path) -> None:
        """Test that whitespace-only files produce no tags."""
        source = tmp_path / "blank.py"
        source.write_text("   \n\n  \n")
        tags = _extract_tags_for_file(source, "blank.py")
        assert tags == []

    def test_extract_unsupported_language(self, tmp_path: Path) -> None:
        """Test that unsupported file types return empty tags."""
        source = tmp_path / "data.xyz"
        source.write_text("some random data")
        tags = _extract_tags_for_file(source, "data.xyz")
        assert tags == []

    def test_extract_nonexistent_file(self) -> None:
        """Test that nonexistent files return empty tags."""
        tags = _extract_tags_for_file(Path("/nonexistent/file.py"), "file.py")
        assert tags == []

    def test_tag_has_correct_paths(self, tmp_path: Path) -> None:
        """Test that tags have correct relative and absolute paths."""
        source = tmp_path / "module.py"
        source.write_text("def hello(): pass\n")
        tags = _extract_tags_for_file(source, "src/module.py")
        def_tags = [t for t in tags if t.kind == "def"]
        assert len(def_tags) >= 1
        assert def_tags[0].rel_path == "src/module.py"
        assert def_tags[0].abs_path == str(source)

    def test_tag_line_numbers(self, tmp_path: Path) -> None:
        """Test that tags have correct 0-indexed line numbers."""
        source = tmp_path / "lines.py"
        source.write_text(
            "# comment\n"
            "class First:\n"
            "    pass\n"
            "\n"
            "class Second:\n"
            "    pass\n"
        )
        tags = _extract_tags_for_file(source, "lines.py")
        def_tags = {t.name: t.line for t in tags if t.kind == "def"}
        assert def_tags.get("First") == 1  # 0-indexed
        assert def_tags.get("Second") == 4

    def test_pygments_fallback_for_references(self, tmp_path: Path) -> None:
        """Test that Pygments fallback adds references when tree-sitter doesn't.

        When tree-sitter finds definitions but no references (e.g., for a
        language with limited query), Pygments lexer is used as fallback.
        """
        # Create a file with only definitions (no calls)
        source = tmp_path / "defs_only.py"
        source.write_text(
            "class MyModel:\n"
            "    name: str\n"
            "    value: int\n"
        )
        tags = _extract_tags_for_file(source, "defs_only.py")
        # Should have at least the class definition
        def_tags = [t for t in tags if t.kind == "def"]
        assert any(t.name == "MyModel" for t in def_tags)
        # Should also have reference tags (from Pygments fallback)
        ref_tags = [t for t in tags if t.kind == "ref"]
        # Pygments should pick up identifier tokens
        assert len(ref_tags) > 0


# ==============================================================================
# extract_tags() Integration Tests
# ==============================================================================


class TestExtractTags:
    """Test the main extract_tags() function."""

    def test_extract_from_specific_files(self, tmp_path: Path) -> None:
        """Test extracting tags from a list of specific files."""
        (tmp_path / "a.py").write_text("class Alpha:\n    pass\n")
        (tmp_path / "b.py").write_text("def beta(): pass\n")

        tags = extract_tags(
            tmp_path,
            [Path("a.py"), Path("b.py")],
            use_cache=False,
        )
        names = {t.name for t in tags if t.kind == "def"}
        assert "Alpha" in names
        assert "beta" in names

    def test_extract_with_auto_discovery(self, tmp_path: Path) -> None:
        """Test auto-discovery of source files in project directory."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def entry_point(): pass\n")
        (src / "utils.py").write_text("def helper(): pass\n")

        tags = extract_tags(tmp_path, use_cache=False)
        names = {t.name for t in tags if t.kind == "def"}
        assert "entry_point" in names
        assert "helper" in names

    def test_skips_ignored_files(self, tmp_path: Path) -> None:
        """Test that .gitignore patterns are respected."""
        (tmp_path / ".gitignore").write_text("ignored/\n")
        (tmp_path / "kept.py").write_text("def kept(): pass\n")
        ignored = tmp_path / "ignored"
        ignored.mkdir()
        (ignored / "secret.py").write_text("def secret(): pass\n")

        tags = extract_tags(tmp_path, use_cache=False)
        names = {t.name for t in tags if t.kind == "def"}
        assert "kept" in names
        assert "secret" not in names

    def test_skips_default_ignored_dirs(self, tmp_path: Path) -> None:
        """Test that __pycache__, node_modules, etc. are always skipped."""
        (tmp_path / "good.py").write_text("def good(): pass\n")
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("def cached(): pass\n")

        tags = extract_tags(tmp_path, use_cache=False)
        names = {t.name for t in tags if t.kind == "def"}
        assert "good" in names
        assert "cached" not in names

    def test_cache_hit(self, tmp_path: Path) -> None:
        """Test that second extraction uses cache."""
        (tmp_path / "cached.py").write_text("def cached_func(): pass\n")

        # Clear memory cache
        _memory_cache.clear()

        # First call populates cache
        tags1 = extract_tags(
            tmp_path, [Path("cached.py")], use_cache=True
        )
        assert len(tags1) > 0

        # Second call should use cache
        tags2 = extract_tags(
            tmp_path, [Path("cached.py")], use_cache=True
        )
        assert len(tags2) == len(tags1)

    def test_nonexistent_files_skipped(self, tmp_path: Path) -> None:
        """Test that nonexistent files are gracefully skipped."""
        tags = extract_tags(
            tmp_path,
            [Path("does_not_exist.py")],
            use_cache=False,
        )
        assert tags == []

    def test_empty_project(self, tmp_path: Path) -> None:
        """Test extracting from a project with no source files."""
        tags = extract_tags(tmp_path, use_cache=False)
        assert tags == []


# ==============================================================================
# File Discovery Tests
# ==============================================================================


class TestDiscoverSourceFiles:
    """Test _discover_source_files."""

    def test_discovers_python_files(self, tmp_path: Path) -> None:
        """Test that Python files are discovered."""
        (tmp_path / "app.py").write_text("x = 1\n")
        (tmp_path / "readme.md").write_text("# Readme\n")
        spec = _load_gitignore_spec(tmp_path)
        files = _discover_source_files(tmp_path, spec)
        py_files = [f for f in files if f.name == "app.py"]
        assert len(py_files) == 1
        # .md is not a recognized tree-sitter language via filename_to_lang
        # (may or may not be included depending on grep_ast version)

    def test_skips_hidden_files(self, tmp_path: Path) -> None:
        """Test that dotfiles are skipped."""
        (tmp_path / ".hidden.py").write_text("x = 1\n")
        (tmp_path / "visible.py").write_text("y = 2\n")
        spec = _load_gitignore_spec(tmp_path)
        files = _discover_source_files(tmp_path, spec)
        names = {f.name for f in files}
        assert "visible.py" in names
        assert ".hidden.py" not in names

    def test_skips_hidden_dirs(self, tmp_path: Path) -> None:
        """Test that hidden directories are skipped."""
        hidden = tmp_path / ".secret"
        hidden.mkdir()
        (hidden / "code.py").write_text("x = 1\n")
        (tmp_path / "public.py").write_text("y = 2\n")
        spec = _load_gitignore_spec(tmp_path)
        files = _discover_source_files(tmp_path, spec)
        names = {f.name for f in files}
        assert "public.py" in names
        assert "code.py" not in names

    def test_respects_gitignore(self, tmp_path: Path) -> None:
        """Test that .gitignore patterns filter discovered files."""
        (tmp_path / ".gitignore").write_text("vendor/\n*.generated.py\n")
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        (vendor / "dep.py").write_text("x = 1\n")
        (tmp_path / "app.generated.py").write_text("y = 2\n")
        (tmp_path / "main.py").write_text("z = 3\n")

        spec = _load_gitignore_spec(tmp_path)
        files = _discover_source_files(tmp_path, spec)
        names = {f.name for f in files}
        assert "main.py" in names
        assert "dep.py" not in names
        assert "app.generated.py" not in names


# ==============================================================================
# Ignore Pattern Tests
# ==============================================================================


class TestIsIgnored:
    """Test _is_ignored path filtering."""

    def test_ignores_pycache(self) -> None:
        """Test __pycache__ is ignored."""
        assert _is_ignored("__pycache__/foo.py", None)

    def test_ignores_node_modules(self) -> None:
        """Test node_modules is ignored."""
        assert _is_ignored("node_modules/pkg/index.js", None)

    def test_ignores_venv(self) -> None:
        """Test .venv is ignored."""
        assert _is_ignored(".venv/lib/python/site.py", None)

    def test_allows_normal_paths(self) -> None:
        """Test normal paths are not ignored."""
        assert not _is_ignored("src/main.py", None)
        assert not _is_ignored("tests/test_foo.py", None)

    def test_with_pathspec(self, tmp_path: Path) -> None:
        """Test ignoring with a pathspec matcher."""
        (tmp_path / ".gitignore").write_text("build/\n*.tmp\n")
        spec = _load_gitignore_spec(tmp_path)
        assert _is_ignored("build/output.js", spec)
        assert _is_ignored("data.tmp", spec)
        assert not _is_ignored("src/app.py", spec)


# ==============================================================================
# Cache Tests
# ==============================================================================


class TestCacheKey:
    """Test _cache_key generation."""

    def test_key_for_existing_file(self, tmp_path: Path) -> None:
        """Test cache key generation for an existing file."""
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        key = _cache_key(f)
        assert isinstance(key, str)
        assert len(key) == 64  # SHA-256 hex digest

    def test_key_changes_with_content(self, tmp_path: Path) -> None:
        """Test cache key changes when file content changes."""
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        key1 = _cache_key(f)

        # Modify the file (changes mtime and possibly size)
        f.write_text("x = 2; y = 3\n")
        key2 = _cache_key(f)

        # Keys should differ (mtime and/or size changed)
        assert key1 != key2

    def test_key_for_missing_file(self) -> None:
        """Test cache key for a nonexistent file."""
        key = _cache_key(Path("/does/not/exist.py"))
        assert isinstance(key, str)
        assert len(key) == 64


class TestCacheOperations:
    """Test cache get/set operations."""

    def test_memory_cache_round_trip(self) -> None:
        """Test storing and retrieving from memory cache."""
        tags = [
            SymbolTag(
                rel_path="test.py",
                abs_path="/test.py",
                name="foo",
                kind="def",
                line=1,
            ),
        ]
        _cache_set(None, "test_key_rt", tags)
        result = _cache_get(None, "test_key_rt")
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "foo"

    def test_cache_miss(self) -> None:
        """Test cache miss returns None."""
        result = _cache_get(None, "nonexistent_key_xyz_123")
        assert result is None


# ==============================================================================
# Symbol Ranking Tests
# ==============================================================================


class TestRankSymbols:
    """Test rank_symbols() PageRank-based ranking."""

    def _make_tags(self) -> list[SymbolTag]:
        """Create a set of tags that form a meaningful graph.

        Graph structure:
        - core.py defines Engine and Config
        - api.py defines handle_request and references Engine, Config
        - cli.py defines main and references handle_request, Engine
        - utils.py defines helper (referenced by nobody cross-file)
        """
        tags: list[SymbolTag] = []

        # core.py definitions
        tags.append(SymbolTag(
            rel_path="core.py", abs_path="/p/core.py",
            name="Engine", kind="def", line=1,
        ))
        tags.append(SymbolTag(
            rel_path="core.py", abs_path="/p/core.py",
            name="Config", kind="def", line=20,
        ))

        # api.py definitions and references
        tags.append(SymbolTag(
            rel_path="api.py", abs_path="/p/api.py",
            name="handle_request", kind="def", line=1,
        ))
        tags.append(SymbolTag(
            rel_path="api.py", abs_path="/p/api.py",
            name="Engine", kind="ref", line=5,
        ))
        tags.append(SymbolTag(
            rel_path="api.py", abs_path="/p/api.py",
            name="Config", kind="ref", line=6,
        ))

        # cli.py definitions and references
        tags.append(SymbolTag(
            rel_path="cli.py", abs_path="/p/cli.py",
            name="main", kind="def", line=1,
        ))
        tags.append(SymbolTag(
            rel_path="cli.py", abs_path="/p/cli.py",
            name="handle_request", kind="ref", line=10,
        ))
        tags.append(SymbolTag(
            rel_path="cli.py", abs_path="/p/cli.py",
            name="Engine", kind="ref", line=15,
        ))

        # utils.py (isolated definition)
        tags.append(SymbolTag(
            rel_path="utils.py", abs_path="/p/utils.py",
            name="helper", kind="def", line=1,
        ))

        return tags

    def test_returns_ranked_symbols(self) -> None:
        """Test that rank_symbols returns RankedSymbol objects."""
        tags = self._make_tags()
        ranked = rank_symbols(tags, token_budget=4096)
        assert len(ranked) > 0
        for r in ranked:
            assert isinstance(r, RankedSymbol)
            assert r.score >= 0.0

    def test_sorted_by_score_descending(self) -> None:
        """Test that results are sorted by score (highest first)."""
        tags = self._make_tags()
        ranked = rank_symbols(tags, token_budget=4096)
        scores = [r.score for r in ranked]
        # Should be sorted descending (or equal — ties broken by path/name)
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_core_module_ranks_higher(self) -> None:
        """Test that symbols in core.py rank higher (most referenced)."""
        tags = self._make_tags()
        ranked = rank_symbols(tags, token_budget=4096)
        # Engine (defined in core.py, referenced by api.py and cli.py)
        # should rank higher than helper (defined in utils.py, unreferenced)
        engine_rank = next(
            (i for i, r in enumerate(ranked) if r.name == "Engine"),
            len(ranked),
        )
        helper_rank = next(
            (i for i, r in enumerate(ranked) if r.name == "helper"),
            len(ranked),
        )
        assert engine_rank < helper_rank, (
            f"Engine should rank above helper: Engine={engine_rank}, helper={helper_rank}"
        )

    def test_token_budget_limits_output(self) -> None:
        """Test that token_budget limits the number of returned symbols."""
        tags = self._make_tags()
        # With budget=30, should get at most 3 symbols (30 // 10)
        ranked = rank_symbols(tags, token_budget=30)
        assert len(ranked) <= 3

    def test_focus_files_boost(self) -> None:
        """Test that focus_files boost ranking of related symbols."""
        tags = self._make_tags()

        # Without focus
        ranked_normal = rank_symbols(tags, token_budget=4096)

        # With cli.py as focus file — should boost symbols referenced by cli.py
        ranked_focused = rank_symbols(
            tags, token_budget=4096, focus_files=["cli.py"]
        )

        # handle_request is referenced by cli.py
        # With focus on cli.py, files referenced by cli.py should rank higher
        hr_score_normal = next(
            (r.score for r in ranked_normal if r.name == "handle_request"),
            0.0,
        )
        hr_score_focused = next(
            (r.score for r in ranked_focused if r.name == "handle_request"),
            0.0,
        )
        # Focused score should be >= normal (the boost effect)
        assert hr_score_focused >= hr_score_normal

    def test_mentioned_identifiers_boost(self) -> None:
        """Test that mentioned_identifiers boost matching symbols."""
        tags = self._make_tags()

        ranked = rank_symbols(
            tags,
            token_budget=4096,
            mentioned_identifiers={"Config"},
        )

        # Config should appear in results
        config_symbols = [r for r in ranked if r.name == "Config"]
        assert len(config_symbols) > 0

    def test_empty_tags_returns_empty(self) -> None:
        """Test that empty tags produce empty results."""
        ranked = rank_symbols([], token_budget=4096)
        assert ranked == []

    def test_minimum_one_result(self) -> None:
        """Test that at least one result is returned when tags exist."""
        tags = self._make_tags()
        ranked = rank_symbols(tags, token_budget=1)  # Very small budget
        assert len(ranked) >= 1  # min 1 from max(1, budget // 10)


# ==============================================================================
# Graceful Degradation Tests
# ==============================================================================


class TestGracefulDegradation:
    """Test graceful fallback when dependencies are missing."""

    def test_extract_tags_without_tree_sitter(self, tmp_path: Path) -> None:
        """Test that extract_tags returns empty list when tree-sitter missing."""
        with patch("cub.core.map.code_intel._HAS_TREE_SITTER", False):
            tags = extract_tags(tmp_path, use_cache=False)
            assert tags == []

    def test_rank_symbols_without_networkx(self) -> None:
        """Test that rank_symbols returns empty list when networkx missing."""
        tags = [
            SymbolTag(
                rel_path="test.py",
                abs_path="/test.py",
                name="foo",
                kind="def",
                line=1,
            ),
        ]
        with patch("cub.core.map.code_intel._HAS_NETWORKX", False):
            ranked = rank_symbols(tags, token_budget=4096)
            assert ranked == []

    def test_discover_files_without_tree_sitter(self, tmp_path: Path) -> None:
        """Test that file discovery returns empty without tree-sitter."""
        with patch("cub.core.map.code_intel._HAS_TREE_SITTER", False):
            files = _discover_source_files(tmp_path, None)
            assert files == []


# ==============================================================================
# Gitignore / Pathspec Tests
# ==============================================================================


class TestLoadGitignoreSpec:
    """Test .gitignore loading."""

    def test_loads_gitignore(self, tmp_path: Path) -> None:
        """Test loading .gitignore file."""
        (tmp_path / ".gitignore").write_text("*.pyc\nbuild/\n")
        spec = _load_gitignore_spec(tmp_path)
        assert spec is not None

    def test_missing_gitignore(self, tmp_path: Path) -> None:
        """Test graceful handling of missing .gitignore."""
        spec = _load_gitignore_spec(tmp_path)
        # Should still return spec (with default patterns)
        assert spec is not None

    def test_default_patterns_applied(self, tmp_path: Path) -> None:
        """Test that default ignore patterns are always applied."""
        spec = _load_gitignore_spec(tmp_path)
        if spec is not None:
            from cub.core.map.code_intel import _HAS_PATHSPEC

            if _HAS_PATHSPEC:
                assert _is_ignored("__pycache__/foo.py", spec)
                assert _is_ignored("node_modules/pkg/index.js", spec)


# ==============================================================================
# Integration Test: Against the Cub Repo
# ==============================================================================


class TestIntegration:
    """Integration tests using the actual cub repository."""

    @pytest.mark.slow
    def test_extract_tags_from_cub_repo(self) -> None:
        """Test extracting tags from actual cub source files."""
        project_dir = Path(__file__).parent.parent
        # Use a small subset of files for speed
        test_files = [
            Path("src/cub/core/map/models.py"),
            Path("src/cub/core/map/structure.py"),
        ]
        # Only test files that exist
        test_files = [f for f in test_files if (project_dir / f).exists()]
        if not test_files:
            pytest.skip("Test files not found in expected location")

        tags = extract_tags(project_dir, test_files, use_cache=False)
        assert len(tags) > 0

        # Should find known symbols
        def_names = {t.name for t in tags if t.kind == "def"}
        # models.py should define TechStack, BuildCommand, etc.
        assert "TechStack" in def_names or "BuildCommand" in def_names

    @pytest.mark.slow
    def test_rank_cub_repo_symbols(self) -> None:
        """Test ranking symbols from actual cub source files."""
        project_dir = Path(__file__).parent.parent
        test_files = [
            Path("src/cub/core/map/models.py"),
            Path("src/cub/core/map/structure.py"),
            Path("src/cub/core/map/code_intel.py"),
        ]
        test_files = [f for f in test_files if (project_dir / f).exists()]
        if not test_files:
            pytest.skip("Test files not found in expected location")

        tags = extract_tags(project_dir, test_files, use_cache=False)
        ranked = rank_symbols(tags, token_budget=1024)

        assert len(ranked) > 0
        # All ranked symbols should have positive scores
        for r in ranked:
            assert r.score > 0.0

    def test_extract_tags_from_code_intel_itself(self) -> None:
        """Test extracting tags from this module's own code."""
        project_dir = Path(__file__).parent.parent
        code_intel_path = Path("src/cub/core/map/code_intel.py")
        if not (project_dir / code_intel_path).exists():
            pytest.skip("code_intel.py not found")

        tags = extract_tags(project_dir, [code_intel_path], use_cache=False)
        def_names = {t.name for t in tags if t.kind == "def"}

        # Should find the main public functions
        assert "extract_tags" in def_names
        assert "rank_symbols" in def_names
        # Should find the model classes
        assert "SymbolTag" in def_names
        assert "RankedSymbol" in def_names
