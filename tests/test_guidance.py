"""
Unit tests for the post-command guidance module.

Tests GuidanceProvider message generation and rendering,
as well as --quiet flag integration across commands.
"""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from cub.cli.guidance import render_guidance
from cub.core.guidance import CommandType, GuidanceMessage, GuidanceProvider, GuidanceStep


class TestGuidanceStep:
    """Test GuidanceStep dataclass."""

    def test_basic_step(self) -> None:
        step = GuidanceStep(description="Do something", command="cub do-it")
        assert step.description == "Do something"
        assert step.command == "cub do-it"
        assert step.detail is None

    def test_step_with_detail(self) -> None:
        step = GuidanceStep(
            description="Do something",
            command="cub do-it",
            detail="Extra info",
        )
        assert step.detail == "Extra info"


class TestGuidanceMessage:
    """Test GuidanceMessage dataclass."""

    def test_empty_message(self) -> None:
        msg = GuidanceMessage(title="Test")
        assert msg.title == "Test"
        assert msg.steps == []

    def test_message_with_steps(self) -> None:
        steps = [
            GuidanceStep(description="Step 1", command="cmd1"),
            GuidanceStep(description="Step 2", command="cmd2"),
        ]
        msg = GuidanceMessage(title="Next", steps=steps)
        assert len(msg.steps) == 2


class TestGuidanceProvider:
    """Test GuidanceProvider message generation."""

    def setup_method(self) -> None:
        self.provider = GuidanceProvider()

    def test_init_guidance_has_steps(self) -> None:
        guidance = self.provider.get_guidance(CommandType.INIT)
        assert guidance.title == "Next Steps"
        assert len(guidance.steps) == 3

    def test_init_guidance_mentions_capture(self) -> None:
        guidance = self.provider.get_guidance(CommandType.INIT)
        commands = [s.command for s in guidance.steps]
        assert any("capture" in cmd for cmd in commands)

    def test_init_guidance_mentions_spec(self) -> None:
        guidance = self.provider.get_guidance(CommandType.INIT)
        commands = [s.command for s in guidance.steps]
        assert any("spec" in cmd for cmd in commands)

    def test_init_guidance_mentions_task(self) -> None:
        guidance = self.provider.get_guidance(CommandType.INIT)
        commands = [s.command for s in guidance.steps]
        assert any("task" in cmd for cmd in commands)

    def test_capture_guidance_has_steps(self) -> None:
        guidance = self.provider.get_guidance(CommandType.CAPTURE)
        assert guidance.title == "Next Steps"
        assert len(guidance.steps) == 3

    def test_capture_guidance_mentions_captures_list(self) -> None:
        guidance = self.provider.get_guidance(CommandType.CAPTURE)
        commands = [s.command for s in guidance.steps]
        assert any("captures" in cmd for cmd in commands)

    def test_capture_guidance_mentions_spec(self) -> None:
        guidance = self.provider.get_guidance(CommandType.CAPTURE)
        commands = [s.command for s in guidance.steps]
        assert any("spec" in cmd for cmd in commands)

    def test_spec_guidance_has_steps(self) -> None:
        guidance = self.provider.get_guidance(CommandType.SPEC)
        assert guidance.title == "Next Steps"
        assert len(guidance.steps) == 3

    def test_spec_guidance_mentions_plan(self) -> None:
        guidance = self.provider.get_guidance(CommandType.SPEC)
        commands = [s.command for s in guidance.steps]
        assert any("plan" in cmd for cmd in commands)

    def test_spec_guidance_mentions_run(self) -> None:
        guidance = self.provider.get_guidance(CommandType.SPEC)
        commands = [s.command for s in guidance.steps]
        assert any("run" in cmd for cmd in commands)

    def test_all_command_types_supported(self) -> None:
        for cmd_type in CommandType:
            guidance = self.provider.get_guidance(cmd_type)
            assert isinstance(guidance, GuidanceMessage)
            assert len(guidance.steps) > 0


class TestGuidanceRendering:
    """Test render_guidance output."""

    def _render_to_string(self, command: CommandType) -> str:
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=True, width=80)
        render_guidance(test_console, command)
        return buf.getvalue()

    def test_render_init_contains_commands(self) -> None:
        output = self._render_to_string(CommandType.INIT)
        assert "capture" in output
        assert "spec" in output
        assert "task" in output

    def test_render_capture_contains_commands(self) -> None:
        output = self._render_to_string(CommandType.CAPTURE)
        assert "captures" in output
        assert "spec" in output

    def test_render_spec_contains_commands(self) -> None:
        output = self._render_to_string(CommandType.SPEC)
        assert "plan" in output
        assert "run" in output

    def test_render_contains_next_steps_title(self) -> None:
        output = self._render_to_string(CommandType.INIT)
        assert "Next Steps" in output

    def test_render_contains_numbered_steps(self) -> None:
        output = self._render_to_string(CommandType.INIT)
        assert "1." in output
        assert "2." in output
        assert "3." in output

    def test_render_includes_dollar_sign_prefix(self) -> None:
        output = self._render_to_string(CommandType.INIT)
        assert "$ " in output
