"""
Rich rendering for post-command guidance messages.

Renders GuidanceMessage data from cub.core.guidance as Rich panels.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from cub.core.guidance import CommandType, GuidanceProvider


def render_guidance(console: Console, command: CommandType) -> None:
    """Render post-command guidance to the console as a Rich panel.

    Args:
        console: Rich Console to print to.
        command: The command type to generate guidance for.
    """
    provider = GuidanceProvider()
    guidance = provider.get_guidance(command)

    lines: list[str] = []
    for i, step in enumerate(guidance.steps, 1):
        lines.append(f"[bold]{i}.[/bold] {step.description}")
        lines.append(f"   [cyan]$ {step.command}[/cyan]")
        if step.detail:
            lines.append(f"   [dim]{step.detail}[/dim]")
    content = "\n".join(lines)

    panel = Panel(
        content,
        title=f"[bold]{guidance.title}[/bold]",
        title_align="left",
        border_style="dim",
        padding=(0, 1),
    )
    console.print()
    console.print(panel)
