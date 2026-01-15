"""CLI module for cub."""

import typer

app = typer.Typer(
    name="cub",
    help="CLI tool for autonomous AI-powered coding sessions",
)


@app.command()
def run():
    """Run an autonomous coding session."""
    typer.echo("Running cub session...")


@app.command()
def status():
    """Show current session status."""
    typer.echo("Session status...")


@app.command()
def init():
    """Initialize cub in a project."""
    typer.echo("Initializing cub...")


if __name__ == "__main__":
    app()
