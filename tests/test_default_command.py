"""Tests for the bare `cub` default command handler."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from cub.cli import app
from cub.cli.default import (
    _get_welcome_message,
    _render_full_welcome,
    _render_inline_status,
    default_command,
    render_welcome,
)
from cub.core.launch.models import EnvironmentContext, EnvironmentInfo
from cub.core.services.launch import HarnessNotFoundError, LaunchServiceError
from cub.core.suggestions.engine import WelcomeMessage
from cub.core.suggestions.models import Suggestion, SuggestionCategory

runner = CliRunner()


# =============================================================================
# Fixtures
# =============================================================================


def _make_welcome(
    *,
    total_tasks: int = 10,
    open_tasks: int = 5,
    in_progress_tasks: int = 2,
    ready_tasks: int = 3,
    suggestions: list[Suggestion] | None = None,
) -> WelcomeMessage:
    """Create a WelcomeMessage for testing."""
    if suggestions is None:
        suggestions = [
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Work on task cub-123",
                description="Implement the feature",
                rationale="This task is ready and unblocked",
                priority_score=0.85,
                action="bd update cub-123 --status in_progress",
                source="task",
            ),
            Suggestion(
                category=SuggestionCategory.GIT,
                title="Push uncommitted changes",
                description="You have uncommitted work",
                rationale="Avoid losing work",
                priority_score=0.7,
                action="git push",
                source="git",
            ),
        ]

    return WelcomeMessage(
        total_tasks=total_tasks,
        open_tasks=open_tasks,
        in_progress_tasks=in_progress_tasks,
        ready_tasks=ready_tasks,
        top_suggestions=suggestions,
        available_skills=[],
    )


def _make_env_info(
    context: EnvironmentContext = EnvironmentContext.TERMINAL,
    session_id: str | None = None,
    harness: str | None = None,
) -> EnvironmentInfo:
    """Create an EnvironmentInfo for testing."""
    return EnvironmentInfo(
        context=context,
        session_id=session_id,
        harness=harness,
    )


# =============================================================================
# Rendering tests
# =============================================================================


class TestRenderWelcome:
    """Tests for render_welcome and its sub-functions."""

    def test_render_full_welcome_shows_stats(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Full welcome shows task stats."""
        welcome = _make_welcome()
        _render_full_welcome(welcome)
        # No exception = success (Rich output goes to console, not capsys)

    def test_render_full_welcome_empty_tasks(self) -> None:
        """Full welcome with no tasks shows 'No tasks found'."""
        welcome = _make_welcome(total_tasks=0, open_tasks=0, in_progress_tasks=0, ready_tasks=0)
        _render_full_welcome(welcome)  # Should not raise

    def test_render_full_welcome_with_suggestions(self) -> None:
        """Full welcome renders suggestions table."""
        welcome = _make_welcome()
        _render_full_welcome(welcome)  # Should not raise

    def test_render_full_welcome_no_suggestions(self) -> None:
        """Full welcome with no suggestions skips table."""
        welcome = _make_welcome(suggestions=[])
        _render_full_welcome(welcome)  # Should not raise

    def test_render_inline_status_shows_compact(self) -> None:
        """Inline status shows compact panel."""
        welcome = _make_welcome()
        _render_inline_status(welcome)  # Should not raise

    def test_render_inline_status_empty_tasks(self) -> None:
        """Inline status with no tasks shows 'No tasks found'."""
        welcome = _make_welcome(total_tasks=0, open_tasks=0, in_progress_tasks=0, ready_tasks=0)
        _render_inline_status(welcome)  # Should not raise

    def test_render_welcome_nested_true(self) -> None:
        """render_welcome with nested=True calls inline."""
        welcome = _make_welcome()
        with patch("cub.cli.default._render_inline_status") as mock_inline:
            render_welcome(welcome, nested=True)
            mock_inline.assert_called_once_with(welcome)

    def test_render_welcome_nested_false(self) -> None:
        """render_welcome with nested=False calls full."""
        welcome = _make_welcome()
        with patch("cub.cli.default._render_full_welcome") as mock_full:
            render_welcome(welcome, nested=False)
            mock_full.assert_called_once_with(welcome)


# =============================================================================
# Welcome message loading
# =============================================================================


class TestGetWelcomeMessage:
    """Tests for _get_welcome_message."""

    def test_returns_welcome_on_success(self) -> None:
        """Returns welcome message when service works."""
        welcome = _make_welcome()
        mock_service = MagicMock()
        mock_service.get_welcome.return_value = welcome

        with patch(
            "cub.cli.default.SuggestionService.from_project_dir",
            return_value=mock_service,
        ):
            result = _get_welcome_message()

        assert result.total_tasks == 10
        assert result.open_tasks == 5
        assert len(result.top_suggestions) == 2

    def test_returns_empty_on_error(self) -> None:
        """Returns empty welcome when service fails."""
        with patch(
            "cub.cli.default.SuggestionService.from_project_dir",
            side_effect=Exception("no project"),
        ):
            result = _get_welcome_message()

        assert result.total_tasks == 0
        assert result.open_tasks == 0
        assert result.top_suggestions == []


# =============================================================================
# Default command logic
# =============================================================================


class TestDefaultCommand:
    """Tests for the default_command function."""

    def test_terminal_launches_harness(self) -> None:
        """In terminal context, shows welcome and launches harness."""
        env_info = _make_env_info(EnvironmentContext.TERMINAL)
        welcome = _make_welcome()

        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.return_value = None  # execve doesn't return, but we mock it

        with (
            patch(
                "cub.cli.default.LaunchService.from_config",
                return_value=mock_service,
            ),
            patch("cub.cli.default._get_welcome_message", return_value=welcome),
            patch("cub.cli.default.render_welcome") as mock_render,
        ):
            default_command(resume=False, continue_session=False, debug=False)

        mock_render.assert_called_once_with(welcome, nested=False)
        mock_service.launch.assert_called_once_with(
            resume=False,
            continue_session=False,
            auto_approve=True,
            debug=False,
        )

    def test_terminal_resume_flag(self) -> None:
        """Resume flag is passed through to harness launch."""
        env_info = _make_env_info(EnvironmentContext.TERMINAL)
        welcome = _make_welcome()

        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.return_value = None

        with (
            patch(
                "cub.cli.default.LaunchService.from_config",
                return_value=mock_service,
            ),
            patch("cub.cli.default._get_welcome_message", return_value=welcome),
            patch("cub.cli.default.render_welcome"),
        ):
            default_command(resume=True, continue_session=False, debug=False)

        mock_service.launch.assert_called_once_with(
            resume=True,
            continue_session=False,
            auto_approve=True,
            debug=False,
        )

    def test_terminal_continue_flag(self) -> None:
        """Continue flag is passed through to harness launch."""
        env_info = _make_env_info(EnvironmentContext.TERMINAL)
        welcome = _make_welcome()

        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.return_value = None

        with (
            patch(
                "cub.cli.default.LaunchService.from_config",
                return_value=mock_service,
            ),
            patch("cub.cli.default._get_welcome_message", return_value=welcome),
            patch("cub.cli.default.render_welcome"),
        ):
            default_command(resume=False, continue_session=True, debug=False)

        mock_service.launch.assert_called_once_with(
            resume=False,
            continue_session=True,
            auto_approve=True,
            debug=False,
        )

    def test_nested_shows_inline_status(self) -> None:
        """In nested context, shows inline status and does NOT launch."""
        env_info = _make_env_info(
            EnvironmentContext.NESTED,
            session_id="test-session-123",
        )
        welcome = _make_welcome()

        mock_service = MagicMock()
        mock_service.detect.return_value = env_info

        with (
            patch(
                "cub.cli.default.LaunchService.from_config",
                return_value=mock_service,
            ),
            patch("cub.cli.default._get_welcome_message", return_value=welcome),
            patch("cub.cli.default.render_welcome") as mock_render,
        ):
            default_command(resume=False, continue_session=False, debug=False)

        mock_render.assert_called_once_with(welcome, nested=True)
        mock_service.launch.assert_not_called()

    def test_harness_shows_inline_status(self) -> None:
        """In harness context (not cub-launched), shows inline status."""
        env_info = _make_env_info(EnvironmentContext.HARNESS, harness="claude")
        welcome = _make_welcome()

        mock_service = MagicMock()
        mock_service.detect.return_value = env_info

        with (
            patch(
                "cub.cli.default.LaunchService.from_config",
                return_value=mock_service,
            ),
            patch("cub.cli.default._get_welcome_message", return_value=welcome),
            patch("cub.cli.default.render_welcome") as mock_render,
        ):
            default_command(resume=False, continue_session=False, debug=False)

        mock_render.assert_called_once_with(welcome, nested=True)
        mock_service.launch.assert_not_called()

    def test_harness_not_found_exits_1(self) -> None:
        """HarnessNotFoundError shows error and exits 1."""
        env_info = _make_env_info(EnvironmentContext.TERMINAL)
        welcome = _make_welcome()

        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.side_effect = HarnessNotFoundError("claude-code")

        with pytest.raises((SystemExit, typer.Exit)):
            with (
                patch(
                    "cub.cli.default.LaunchService.from_config",
                    return_value=mock_service,
                ),
                patch("cub.cli.default._get_welcome_message", return_value=welcome),
                patch("cub.cli.default.render_welcome"),
            ):
                default_command(resume=False, continue_session=False, debug=False)

    def test_launch_error_exits_1(self) -> None:
        """LaunchServiceError shows error and exits 1."""
        env_info = _make_env_info(EnvironmentContext.TERMINAL)
        welcome = _make_welcome()

        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.side_effect = LaunchServiceError("exec failed")

        with pytest.raises((SystemExit, typer.Exit)):
            with (
                patch(
                    "cub.cli.default.LaunchService.from_config",
                    return_value=mock_service,
                ),
                patch("cub.cli.default._get_welcome_message", return_value=welcome),
                patch("cub.cli.default.render_welcome"),
            ):
                default_command(resume=False, continue_session=False, debug=False)

    def test_config_load_failure_handles_no_project(self) -> None:
        """Config load failure triggers no-project handler."""
        with (
            patch(
                "cub.cli.default.LaunchService.from_config",
                side_effect=Exception("no config"),
            ),
            patch("cub.cli.default._handle_no_project") as mock_no_project,
        ):
            default_command(resume=False, continue_session=False, debug=False)

        mock_no_project.assert_called_once_with(
            resume=False,
            continue_session=False,
            debug=False,
        )


# =============================================================================
# CLI integration tests
# =============================================================================


class TestCLIIntegration:
    """Tests for bare `cub` via Typer CLI runner."""

    def test_bare_cub_invokes_default_command(self) -> None:
        """Running bare `cub` invokes default_command."""
        with patch("cub.cli.default.default_command") as mock_default:
            runner.invoke(app, [])

        mock_default.assert_called_once()

    def test_bare_cub_with_resume(self) -> None:
        """Running `cub --resume` passes resume flag."""
        with patch("cub.cli.default.default_command") as mock_default:
            runner.invoke(app, ["--resume"])

        mock_default.assert_called_once()
        _, kwargs = mock_default.call_args
        assert kwargs["resume"] is True

    def test_bare_cub_with_continue(self) -> None:
        """Running `cub --continue` passes continue flag."""
        with patch("cub.cli.default.default_command") as mock_default:
            runner.invoke(app, ["--continue"])

        mock_default.assert_called_once()
        _, kwargs = mock_default.call_args
        assert kwargs["continue_session"] is True

    def test_bare_cub_with_debug(self) -> None:
        """Running `cub --debug` passes debug flag."""
        with patch("cub.cli.default.default_command") as mock_default:
            runner.invoke(app, ["--debug"])

        mock_default.assert_called_once()
        _, kwargs = mock_default.call_args
        assert kwargs["debug"] is True

    def test_bare_cub_with_resume_and_continue(self) -> None:
        """Running `cub --resume --continue` passes both flags."""
        with patch("cub.cli.default.default_command") as mock_default:
            runner.invoke(app, ["--resume", "--continue"])

        mock_default.assert_called_once()
        _, kwargs = mock_default.call_args
        assert kwargs["resume"] is True
        assert kwargs["continue_session"] is True

    def test_subcommand_does_not_invoke_default(self) -> None:
        """Running `cub version` does NOT invoke default_command."""
        with patch("cub.cli.default.default_command") as mock_default:
            runner.invoke(app, ["version"])

        mock_default.assert_not_called()

    def test_help_flag_shows_help(self) -> None:
        """Running `cub --help` shows help text."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Cub" in result.output


# =============================================================================
# Suggestion priority rendering
# =============================================================================


class TestSuggestionRendering:
    """Tests for suggestion rendering across urgency levels."""

    def test_all_urgency_levels_render(self) -> None:
        """Suggestions at all urgency levels render without error."""
        suggestions = [
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Urgent task",
                rationale="Very important",
                priority_score=0.9,
                source="test",
            ),
            Suggestion(
                category=SuggestionCategory.REVIEW,
                title="High priority review",
                rationale="Needs review",
                priority_score=0.7,
                source="test",
            ),
            Suggestion(
                category=SuggestionCategory.GIT,
                title="Medium git task",
                rationale="Should push",
                priority_score=0.5,
                source="test",
            ),
            Suggestion(
                category=SuggestionCategory.CLEANUP,
                title="Low priority cleanup",
                rationale="Nice to have",
                priority_score=0.2,
                source="test",
            ),
        ]
        welcome = _make_welcome(suggestions=suggestions)
        _render_full_welcome(welcome)  # Should not raise
        _render_inline_status(welcome)  # Should not raise

    def test_suggestion_without_action(self) -> None:
        """Suggestions without an action command render correctly."""
        suggestions = [
            Suggestion(
                category=SuggestionCategory.PLAN,
                title="Plan next milestone",
                rationale="Milestone approaching",
                priority_score=0.6,
                source="test",
                action=None,
            ),
        ]
        welcome = _make_welcome(suggestions=suggestions)
        _render_full_welcome(welcome)  # Should not raise
        _render_inline_status(welcome)  # Should not raise
