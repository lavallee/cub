#!/usr/bin/env python3
"""
Compare tasks between beads and JSONL backends.

This script loads both backends and compares all tasks to identify divergences.
Useful for validating backend sync and debugging "both" mode.

Exit codes:
    0 - Backends are in sync (no divergences)
    1 - Divergences detected
    2 - Error loading backends
"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Error: rich library not found. Install with: pip install rich", file=sys.stderr)
    sys.exit(2)

try:
    from cub.core.tasks.beads import BeadsBackend
    from cub.core.tasks.both import BothBackend, TaskDivergence
    from cub.core.tasks.jsonl import JsonlBackend
except ImportError as e:
    print(f"Error: Failed to import cub modules: {e}", file=sys.stderr)
    print("Make sure you're running from the project root directory.", file=sys.stderr)
    sys.exit(2)


console = Console()


def format_divergence_summary(diff: str) -> Text:
    """Format divergence summary with color coding."""
    text = Text()

    # Split by semicolon to get individual differences
    parts = diff.split("; ")

    for i, part in enumerate(parts):
        if i > 0:
            text.append("; ", style="dim")

        # Highlight field names in yellow
        if ":" in part:
            field, rest = part.split(":", 1)
            text.append(field, style="yellow bold")
            text.append(":", style="dim")
            text.append(rest, style="red")
        else:
            text.append(part, style="red")

    return text


def print_divergences(divergences: list[TaskDivergence]) -> None:
    """Print divergences in a formatted table."""
    if not divergences:
        console.print(Panel("✓ Backends are in sync!", style="green bold"))
        return

    console.print(Panel(
        f"⚠️  Found {len(divergences)} divergence(s)",
        style="yellow bold"
    ))
    console.print()

    table = Table(title="Backend Divergences", show_header=True, header_style="bold magenta")
    table.add_column("Task ID", style="cyan", no_wrap=True)
    table.add_column("Operation", style="blue")
    table.add_column("Differences", style="red")

    for div in divergences:
        task_id = div.task_id or "N/A"
        operation = div.operation
        diff_text = format_divergence_summary(div.difference_summary)

        table.add_row(task_id, operation, diff_text)

    console.print(table)


def main() -> int:
    """Run backend comparison and print results."""
    console.print("[bold blue]Backend Comparison Tool[/bold blue]")
    console.print()

    # Try to load both backends
    try:
        console.print("Loading beads backend...", style="dim")
        primary = BeadsBackend()
        console.print("✓ Beads backend loaded", style="green")
    except Exception as e:
        console.print(f"[red]✗ Failed to load beads backend: {e}[/red]")
        console.print(
            "[yellow]Tip: Make sure .beads/ directory exists and bd CLI is installed[/yellow]"
        )
        return 2

    try:
        console.print("Loading JSONL backend...", style="dim")
        secondary = JsonlBackend()
        console.print("✓ JSONL backend loaded", style="green")
    except Exception as e:
        console.print(f"[red]✗ Failed to load JSONL backend: {e}[/red]")
        console.print("[yellow]Tip: Make sure .cub/tasks.jsonl exists[/yellow]")
        return 2

    console.print()

    # Create BothBackend wrapper
    both = BothBackend(primary, secondary)

    # Run comparison
    console.print("Comparing all tasks...", style="dim")
    divergences = both.compare_all_tasks()

    console.print()

    # Print results
    print_divergences(divergences)

    # Print summary
    console.print()
    console.print("[bold]Summary:[/bold]")

    try:
        primary_counts = primary.get_task_counts()
        secondary_counts = secondary.get_task_counts()

        console.print(f"  Beads backend: {primary_counts.total} tasks "
                     f"({primary_counts.open} open, {primary_counts.in_progress} in progress, "
                     f"{primary_counts.closed} closed)")
        console.print(f"  JSONL backend: {secondary_counts.total} tasks "
                     f"({secondary_counts.open} open, {secondary_counts.in_progress} in progress, "
                     f"{secondary_counts.closed} closed)")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not get task counts: {e}[/yellow]")

    # Check divergence log
    divergence_count = both.get_divergence_count()
    if divergence_count > 0:
        console.print()
        console.print(f"[yellow]Note: Divergence log contains {divergence_count} entries[/yellow]")
        console.print(f"[dim]Log file: {both.divergence_log}[/dim]")

    # Return exit code
    if divergences:
        return 1
    else:
        return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red bold]Error: {e}[/red bold]")
        import traceback
        console.print("[dim]" + traceback.format_exc() + "[/dim]")
        sys.exit(2)
