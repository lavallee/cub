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

    By default, opens https://docs.cub.tools. Use --local to view local docs.

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
            if webbrowser.open(docs_url):
                console.print(f"Opened local docs: {docs_path}")
            else:
                console.print(f"Open this file: [bold]{docs_url}[/bold]")
            raise typer.Exit(0)

        # Fall back to README
        if readme_path.exists():
            readme_url = readme_path.as_uri()
            if webbrowser.open(readme_url):
                console.print(f"Opened local README: {readme_path}")
            else:
                console.print(f"Open this file: [bold]{readme_url}[/bold]")
            raise typer.Exit(0)

        console.print("[red]Error: No local documentation found.[/red]")
        raise typer.Exit(1)
    else:
        # Open online docs
        docs_url = "https://docs.cub.tools"
        if webbrowser.open(docs_url):
            console.print(f"Opened documentation: {docs_url}")
        else:
            console.print(f"Visit: [bold]{docs_url}[/bold]")
        raise typer.Exit(0)
