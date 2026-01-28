"""
Cub map module.

Provides structure analysis, codebase mapping, and code intelligence.
This module analyzes project structure, detects tech stacks, extracts
build commands, identifies key files and module boundaries, and uses
tree-sitter + PageRank for symbol extraction and ranking.

Main entry points:
    - analyze_structure(): Project structure analysis
    - extract_tags(): Tree-sitter symbol extraction
    - rank_symbols(): PageRank-based symbol ranking
    - render_map(): Combine structure and symbols into markdown with token budgeting

Example:
    >>> from cub.core.map import analyze_structure
    >>> structure = analyze_structure("/path/to/project", max_depth=4)
    >>> structure.primary_tech_stack
    <TechStack.PYTHON: 'python'>
    >>> len(structure.build_commands)
    5

    >>> from cub.core.map import extract_tags, rank_symbols, render_map
    >>> tags = extract_tags(Path("/path/to/project"))
    >>> ranked = rank_symbols(tags, token_budget=2048)
    >>> map_markdown = render_map(structure, ranked, token_budget=4096)
"""

from cub.core.map.code_intel import (
    RankedSymbol,
    SymbolTag,
    extract_tags,
    rank_symbols,
)
from cub.core.map.models import (
    BuildCommand,
    DirectoryNode,
    DirectoryTree,
    KeyFile,
    ModuleInfo,
    ProjectStructure,
    TechStack,
)
from cub.core.map.renderer import estimate_tokens, render_map
from cub.core.map.structure import analyze_structure

__all__ = [
    # Structure analysis
    "analyze_structure",
    # Code intelligence
    "extract_tags",
    "rank_symbols",
    # Rendering
    "render_map",
    "estimate_tokens",
    # Structure models
    "BuildCommand",
    "DirectoryNode",
    "DirectoryTree",
    "KeyFile",
    "ModuleInfo",
    "ProjectStructure",
    "TechStack",
    # Code intelligence models
    "RankedSymbol",
    "SymbolTag",
]
