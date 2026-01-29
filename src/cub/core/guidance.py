"""
Post-command guidance data for cub workflows.

Provides contextual next-step message data after key commands complete,
helping users (especially new ones) understand what to do next.

This module contains only data models and generation logic.
Rendering is handled by the CLI layer (cub.cli.guidance).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CommandType(str, Enum):
    """Commands that produce guidance messages."""

    INIT = "init"
    CAPTURE = "capture"
    SPEC = "spec"


@dataclass
class GuidanceStep:
    """A single suggested next step."""

    description: str
    command: str
    detail: str | None = None


@dataclass
class GuidanceMessage:
    """A complete guidance message with multiple steps."""

    title: str
    steps: list[GuidanceStep] = field(default_factory=list)


class GuidanceProvider:
    """Generate contextual post-command guidance messages.

    Produces actionable next-step suggestions based on which command
    just completed, helping new users navigate the cub workflow.
    """

    def get_guidance(self, command: CommandType) -> GuidanceMessage:
        """Return guidance for the given command type.

        Args:
            command: The command that just completed.

        Returns:
            A GuidanceMessage with suggested next steps.
        """
        handlers = {
            CommandType.INIT: self._init_guidance,
            CommandType.CAPTURE: self._capture_guidance,
            CommandType.SPEC: self._spec_guidance,
        }
        handler = handlers[command]
        return handler()

    def _init_guidance(self) -> GuidanceMessage:
        return GuidanceMessage(
            title="Next Steps",
            steps=[
                GuidanceStep(
                    description="Capture an idea or feature request",
                    command='cub capture "Your idea here"',
                ),
                GuidanceStep(
                    description="Create a detailed feature spec",
                    command="cub spec",
                    detail="Starts an interactive interview to define requirements",
                ),
                GuidanceStep(
                    description="Create a task and start working",
                    command='cub task create "Task title"',
                ),
            ],
        )

    def _capture_guidance(self) -> GuidanceMessage:
        return GuidanceMessage(
            title="Next Steps",
            steps=[
                GuidanceStep(
                    description="Review your captures",
                    command="cub captures list",
                ),
                GuidanceStep(
                    description="Turn this idea into a detailed spec",
                    command="cub spec",
                    detail="Starts an interactive interview to flesh out the idea",
                ),
                GuidanceStep(
                    description="Organize captures into specs",
                    command="cub organize-captures",
                ),
            ],
        )

    def _spec_guidance(self) -> GuidanceMessage:
        return GuidanceMessage(
            title="Next Steps",
            steps=[
                GuidanceStep(
                    description="View all specs and their stages",
                    command="cub spec --list",
                ),
                GuidanceStep(
                    description="Plan implementation from a spec",
                    command="cub plan run specs/researching/<name>.md",
                    detail="Generates tasks from your spec",
                ),
                GuidanceStep(
                    description="Start working on planned tasks",
                    command="cub run",
                ),
            ],
        )
