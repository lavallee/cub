"""
Cub CLI - Docs command.

Opens documentation in the default web browser.
"""

import webbrowser
from pathlib import Path

import typer
from rich.console import Console

console = Console()


def docs(
    local: bool = typer.Option(
        False,
        "--local",
        help="Open local documentation files instead of online",
    ),
) -> None:
    """
    Open cub documentation in your web browser.

    By default, opens the GitHub README. Use --local to view local docs.

    Examples:
        cub docs                    # Open online docs
        cub docs --local            # Open local documentation
    """
    if local:
        # Try to open local docs
        docs_path = Path(__file__).parent.parent.parent.parent / "docs" / "index.html"
        readme_path = Path(__file__).parent.parent.parent.parent / "README.md"

        # Check if docs/index.html exists (built docs)
        if docs_path.exists():
            docs_url = docs_path.as_uri()
            console.print(f"Opening local docs: {docs_path}")
            if webbrowser.open(docs_url):
                raise typer.Exit(0)
            else:
                console.print("[yellow]Warning: Could not open browser automatically.[/yellow]")
                console.print(f"Open this file manually: {docs_url}")
                raise typer.Exit(1)

        # Fall back to README
        if readme_path.exists():
            readme_url = readme_path.as_uri()
            console.print(f"Opening local README: {readme_path}")
            if webbrowser.open(readme_url):
                raise typer.Exit(0)
            else:
                console.print("[yellow]Warning: Could not open browser automatically.[/yellow]")
                console.print(f"Open this file manually: {readme_url}")
                raise typer.Exit(1)

        console.print("[red]Error: No local documentation found.[/red]")
        raise typer.Exit(1)
    else:
        # Open online docs (GitHub README)
        docs_url = "https://github.com/anthropics/cub#readme"
        console.print(f"Opening documentation: {docs_url}")
        if webbrowser.open(docs_url):
            raise typer.Exit(0)
        else:
            console.print("[yellow]Warning: Could not open browser automatically.[/yellow]")
            console.print(f"Open this URL in your browser: {docs_url}")
            raise typer.Exit(1)
