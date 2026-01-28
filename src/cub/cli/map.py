"""
Cub CLI - Map command.

Generate a project map that combines structure analysis and code intelligence.
The map provides an AI-digestible overview of the codebase including:
- Tech stacks and build commands
- Key files and module boundaries
- Directory structure
- Important symbols ranked by PageRank

This command is typically called automatically by `cub init` and `cub update`
but can be run standalone to regenerate the map.
"""

from pathlib import Path

import typer
from rich.console import Console

from cub.core.map import (
    analyze_structure,
    extract_tags,
    rank_symbols,
    render_map,
)

console = Console()


def generate_map(
    project_dir: Path,
    token_budget: int = 4096,
    max_depth: int = 4,
    include_ledger: bool = False,
    debug: bool = False,
) -> str:
    """
    Generate a project map combining structure analysis and code intelligence.

    Args:
        project_dir: Path to the project root directory
        token_budget: Maximum token budget for the map (default: 4096)
        max_depth: Maximum directory tree depth (default: 4)
        include_ledger: Include ledger statistics in the map (default: False)
        debug: Show debug output (default: False)

    Returns:
        Markdown-formatted project map string

    Raises:
        Exception: If map generation fails
    """
    if debug:
        console.print(f"[dim]Analyzing project structure at {project_dir}[/dim]")

    # Step 1: Analyze project structure
    structure = analyze_structure(project_dir, max_depth=max_depth)

    if debug:
        console.print(
            f"[dim]Found {len(structure.tech_stacks)} tech stack(s), "
            f"{len(structure.build_commands)} build command(s), "
            f"{len(structure.key_files)} key file(s)[/dim]"
        )

    # Step 2: Extract and rank symbols
    if debug:
        console.print("[dim]Extracting symbols with tree-sitter[/dim]")

    tags = extract_tags(project_dir, use_cache=True)

    if debug:
        console.print(f"[dim]Extracted {len(tags)} symbol tags[/dim]")

    # Step 3: Rank symbols by PageRank
    ranked_symbols = rank_symbols(tags, token_budget=token_budget)

    if debug:
        console.print(f"[dim]Ranked {len(ranked_symbols)} symbols[/dim]")

    # Step 4: Render map
    ledger_reader = None
    if include_ledger:
        try:
            from cub.core.ledger.reader import LedgerReader

            ledger_reader = LedgerReader(project_dir)
            if debug:
                console.print("[dim]Including ledger statistics[/dim]")
        except Exception as e:
            if debug:
                console.print(f"[yellow]Warning: Could not load ledger: {e}[/yellow]")

    map_markdown = render_map(
        structure,
        ranked_symbols,
        token_budget=token_budget,
        include_ledger_stats=include_ledger,
        ledger_reader=ledger_reader,
    )

    return map_markdown


def main(
    project_dir: str = typer.Argument(
        ".",
        help="Project directory to analyze (default: current directory)",
    ),
    output: str = typer.Option(
        ".cub/map.md",
        "--output",
        "-o",
        help="Output file path (default: .cub/map.md)",
    ),
    token_budget: int = typer.Option(
        4096,
        "--token-budget",
        "-t",
        help="Maximum token budget for the map",
    ),
    max_depth: int = typer.Option(
        4,
        "--max-depth",
        "-d",
        help="Maximum directory tree depth",
    ),
    include_ledger: bool = typer.Option(
        False,
        "--include-ledger",
        "-l",
        help="Include ledger statistics in the map",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing map file",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show debug output",
    ),
) -> None:
    """
    Generate a project map with structure analysis and code intelligence.

    The map provides an AI-digestible overview of the codebase including:
    - Tech stacks, build commands, and key files
    - Module boundaries and directory structure
    - Important symbols ranked by PageRank

    This command is typically called automatically by `cub init` and `cub update`
    but can be run standalone to regenerate the map.

    Examples:
        cub map                          # Generate map at .cub/map.md
        cub map --output mymap.md        # Custom output path
        cub map --token-budget 8192      # Larger token budget
        cub map --include-ledger         # Include ledger stats
        cub map --force                  # Overwrite existing map
    """
    project_path = Path(project_dir).resolve()

    if not project_path.exists():
        console.print(f"[red]Error: Directory does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    if not project_path.is_dir():
        console.print(f"[red]Error: Not a directory: {project_path}[/red]")
        raise typer.Exit(1)

    output_path = Path(output) if Path(output).is_absolute() else project_path / output

    # Check if output file exists
    if output_path.exists() and not force:
        console.print(
            f"[yellow]Warning: {output_path} already exists. Use --force to overwrite.[/yellow]"
        )
        raise typer.Exit(1)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Generate the map
        console.print(f"[cyan]Generating project map for {project_path}...[/cyan]")
        map_content = generate_map(
            project_path,
            token_budget=token_budget,
            max_depth=max_depth,
            include_ledger=include_ledger,
            debug=debug,
        )

        # Write to file
        output_path.write_text(map_content, encoding="utf-8")

        console.print(f"[green]✓[/green] Project map saved to {output_path}")

        if debug:
            console.print(f"[dim]Map size: {len(map_content)} characters[/dim]")

    except Exception as e:
        console.print(f"[red]Error generating map: {e}[/red]")
        if debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(main)
