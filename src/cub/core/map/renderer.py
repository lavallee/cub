"""
Map renderer with token budgeting.

Combines structural analysis and ranked symbols into a single markdown document
within a token budget. Prioritizes structural information (always useful) and
fills remaining budget with ranked symbols (valuable but cuttable).
"""

from __future__ import annotations

from pathlib import Path

from cub.core.ledger.reader import LedgerReader
from cub.core.map.code_intel import RankedSymbol
from cub.core.map.models import (
    BuildCommand,
    DirectoryNode,
    DirectoryTree,
    KeyFile,
    ModuleInfo,
    ProjectStructure,
    TechStack,
)


def estimate_tokens(text: str) -> int:
    """Estimate token count from text using word count heuristic.

    Uses the approximation: tokens ≈ words / 0.75
    This is model-agnostic and avoids tiktoken dependency.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count (rounded up to be conservative)
    """
    if not text:
        return 0

    # Split on whitespace to count words
    words = len(text.split())

    # Apply the heuristic: words / 0.75 ≈ tokens
    # We use ceiling division to be conservative
    return int((words + 2) // 0.75)


def render_map(
    structure: ProjectStructure,
    ranked_symbols: list[RankedSymbol],
    token_budget: int,
    include_ledger_stats: bool = False,
    ledger_reader: LedgerReader | None = None,
) -> str:
    """Render project map within token budget.

    Combines structural analysis and ranked symbols into a markdown document.
    Applies token budgeting with priority: structure (40%) > symbols (60%),
    with optional ledger stats capped at 10%.

    Args:
        structure: Project structure analysis result
        ranked_symbols: List of symbols ranked by importance (descending score)
        token_budget: Maximum tokens to use for the entire map
        include_ledger_stats: Whether to include ledger statistics section
        ledger_reader: LedgerReader instance for reading ledger stats
            (required if include_ledger_stats)

    Returns:
        Markdown-formatted project map

    Raises:
        ValueError: If include_ledger_stats is True but ledger_reader is None
    """
    if include_ledger_stats and ledger_reader is None:
        raise ValueError("ledger_reader is required when include_ledger_stats is True")

    # Calculate budget allocations
    # Ledger stats (if enabled): up to 10% of total budget
    ledger_budget = int(token_budget * 0.10) if include_ledger_stats else 0
    # Remaining budget split: structure 40%, symbols 60%
    remaining_budget = token_budget - ledger_budget
    structure_budget = int(remaining_budget * 0.40)
    symbols_budget = remaining_budget - structure_budget

    sections: list[str] = []

    # Section 1: Header
    header = _render_header(structure)
    sections.append(header)

    # Section 2: Tech Stacks
    tech_stacks = _render_tech_stacks(structure.tech_stacks)
    sections.append(tech_stacks)

    # Section 3: Build Commands
    build_cmds = _render_build_commands(structure.build_commands)
    sections.append(build_cmds)

    # Section 4: Key Files
    key_files_section = _render_key_files(structure.key_files)
    sections.append(key_files_section)

    # Section 5: Modules
    modules = _render_modules(structure.modules)
    sections.append(modules)

    # Section 6: Directory Tree (budget-aware)
    tree = _render_directory_tree(structure.directory_tree, structure_budget)
    sections.append(tree)

    # Section 7: Ranked Symbols (budget-aware)
    symbols = _render_ranked_symbols(ranked_symbols, symbols_budget)
    sections.append(symbols)

    # Section 8: Ledger Stats (optional, budget-aware)
    if include_ledger_stats and ledger_reader:
        stats = _render_ledger_stats(ledger_reader, ledger_budget)
        sections.append(stats)

    # Combine all sections
    return "\n\n".join(filter(None, sections))


def _render_header(structure: ProjectStructure) -> str:
    """Render map header with project directory."""
    project_name = Path(structure.project_dir).name
    return f"# Project Map: {project_name}\n\n**Project Directory:** `{structure.project_dir}`"


def _render_tech_stacks(tech_stacks: list[TechStack]) -> str:
    """Render tech stacks section."""
    if not tech_stacks:
        return ""

    lines = ["## Tech Stacks", ""]
    for stack in tech_stacks:
        lines.append(f"- {stack.value}")

    return "\n".join(lines)


def _render_build_commands(build_commands: list[BuildCommand]) -> str:
    """Render build commands section."""
    if not build_commands:
        return ""

    lines = ["## Build Commands", ""]
    for cmd in build_commands:
        lines.append(f"- **{cmd.name}**: `{cmd.command}` (from {cmd.source})")

    return "\n".join(lines)


def _render_key_files(key_files: list[KeyFile]) -> str:
    """Render key files section."""
    if not key_files:
        return ""

    lines = ["## Key Files", ""]
    for kf in key_files:
        desc = f" - {kf.description}" if kf.description else ""
        lines.append(f"- `{kf.path}` ({kf.type}){desc}")

    return "\n".join(lines)


def _render_modules(modules: list[ModuleInfo]) -> str:
    """Render modules section."""
    if not modules:
        return ""

    lines = ["## Modules", ""]
    for mod in modules:
        entry = f" (entry: {mod.entry_file})" if mod.entry_file else ""
        lines.append(f"- **{mod.name}**: `{mod.path}` ({mod.file_count} files){entry}")

    return "\n".join(lines)


def _render_directory_tree(
    tree: DirectoryTree | None,
    budget: int,
) -> str:
    """Render directory tree within budget.

    Args:
        tree: Directory tree structure
        budget: Token budget for this section

    Returns:
        Markdown-formatted directory tree, truncated if needed
    """
    if not tree:
        return ""

    lines = ["## Directory Structure", ""]

    # Render tree recursively from root node
    tree_lines = _render_tree_node(tree.root, prefix="", is_last=True)
    lines.extend(tree_lines)

    # Check budget and truncate if needed
    content = "\n".join(lines)
    estimated = estimate_tokens(content)

    if estimated > budget:
        # Calculate how many lines we can keep (approximately)
        ratio = budget / estimated
        keep_lines = int(len(lines) * ratio)
        # Keep at least header + 2 lines
        keep_lines = max(3, keep_lines)
        lines = lines[:keep_lines]
        lines.append("... (truncated to fit budget)")

    return "\n".join(lines)


def _render_tree_node(node: DirectoryNode, prefix: str, is_last: bool) -> list[str]:
    """Recursively render a directory tree node.

    Args:
        node: Directory node to render
        prefix: Prefix for tree drawing characters
        is_last: Whether this is the last child of its parent

    Returns:
        List of formatted lines
    """
    lines = []

    # Determine connector characters
    connector = "└── " if is_last else "├── "
    extension = "    " if is_last else "│   "

    # Render current node
    name = node.name
    if node.is_file:
        lines.append(f"{prefix}{connector}{name}")
    else:
        lines.append(f"{prefix}{connector}{name}/")

    # Render children
    if not node.is_file and node.children:
        child_count = len(node.children)
        for i, child in enumerate(node.children):
            child_is_last = (i == child_count - 1)
            child_lines = _render_tree_node(
                child,
                prefix=prefix + extension,
                is_last=child_is_last,
            )
            lines.extend(child_lines)

    return lines


def _render_ranked_symbols(symbols: list[RankedSymbol], budget: int) -> str:
    """Render ranked symbols within budget.

    Args:
        symbols: List of ranked symbols (descending score)
        budget: Token budget for this section

    Returns:
        Markdown-formatted symbols list, truncated if needed
    """
    if not symbols:
        return ""

    lines = ["## Ranked Symbols", ""]
    lines.append("Symbols ranked by importance (PageRank score):")
    lines.append("")

    # Group symbols by file for better readability
    by_file: dict[str, list[RankedSymbol]] = {}
    for sym in symbols:
        by_file.setdefault(sym.rel_path, []).append(sym)

    # Estimate tokens per symbol entry (~10 tokens per line)
    # This matches the heuristic used in code_intel.py
    used_tokens = estimate_tokens("\n".join(lines))

    # Add symbols until budget is exhausted
    symbol_count = 0
    for file_path in sorted(by_file.keys()):
        file_symbols = by_file[file_path]

        # File header
        file_header = f"\n### {file_path}"
        file_header_tokens = estimate_tokens(file_header)

        if used_tokens + file_header_tokens > budget:
            break

        lines.append(file_header)
        lines.append("")
        used_tokens += file_header_tokens

        # Add symbols for this file
        for sym in file_symbols:
            sym_line = f"- **{sym.name}** ({sym.kind}, line {sym.line + 1}, score: {sym.score:.4f})"
            sym_tokens = estimate_tokens(sym_line)

            if used_tokens + sym_tokens > budget:
                # Budget exhausted
                lines.append("")
                omitted_count = len(symbols) - symbol_count
                lines.append(
                    f"... ({omitted_count} more symbols omitted to fit budget)"
                )
                return "\n".join(lines)

            lines.append(sym_line)
            used_tokens += sym_tokens
            symbol_count += 1

    return "\n".join(lines)


def _render_ledger_stats(ledger_reader: LedgerReader, budget: int) -> str:
    """Render ledger statistics within budget.

    Args:
        ledger_reader: LedgerReader instance
        budget: Token budget for this section

    Returns:
        Markdown-formatted ledger stats, or empty if ledger doesn't exist
    """
    if not ledger_reader.exists():
        return ""

    stats = ledger_reader.get_stats()

    lines = ["## Ledger Statistics", ""]
    lines.append(f"- **Total Tasks**: {stats.total_tasks}")
    lines.append(f"- **Total Cost**: ${stats.total_cost_usd:.2f}")
    lines.append(f"- **Total Tokens**: {stats.total_tokens:,}")
    lines.append(f"- **Average Cost/Task**: ${stats.average_cost_per_task:.2f}")
    lines.append(f"- **Average Tokens/Task**: {stats.average_tokens_per_task:,}")

    # Verification stats if available
    if hasattr(stats, "verification_pass_rate"):
        lines.append(f"- **Verification Pass Rate**: {stats.verification_pass_rate:.1%}")

    # Check budget and truncate if needed
    content = "\n".join(lines)
    estimated = estimate_tokens(content)

    if estimated > budget:
        # Keep only the first few lines
        lines = lines[:5]
        lines.append("... (truncated to fit budget)")

    return "\n".join(lines)
