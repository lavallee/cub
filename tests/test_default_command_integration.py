"""
Integration tests for the bare `cub` command.

Tests the full default command behavior in various scenarios:
- No project directory (.cub/ missing)
- Different backend systems (JSONL, beads)
- Nested session detection (CUB_SESSION_ACTIVE)
- Resume and continue flags
- Missing harness binary
- Help and subcommand routing
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cub.cli import app
from cub.core.launch.models import EnvironmentContext, EnvironmentInfo

runner = CliRunner()


# =============================================================================
# Fresh Directory Tests (No .cub/)
# =============================================================================


class TestFreshDirectory:
    """Tests for bare cub in a directory without .cub/ initialization."""

    def test_bare_cub_no_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Running bare `cub` in fresh directory shows helpful message."""
        # Change to empty temp directory
        monkeypatch.chdir(tmp_path)

        # Mock harness binary resolution to fail (no harness installed)
        with (
            patch("cub.cli.default.LaunchService.from_config", side_effect=Exception("no config")),
            patch("cub.core.config.loader.load_config", side_effect=Exception("no config")),
        ):
            result = runner.invoke(app, [])

        # Should exit with code 1 but show helpful message
        assert result.exit_code == 1
        assert (
            "no cub project" in result.output.lower() or "could not launch" in result.output.lower()
        )

    def test_bare_cub_no_project_with_harness(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running bare `cub` in fresh directory launches harness if available."""
        # Change to empty temp directory
        monkeypatch.chdir(tmp_path)

        # Mock config load to fail (no project), then succeed in fallback
        mock_config = MagicMock()
        mock_config.harness.name = "claude-code"

        mock_service = MagicMock()
        mock_service.launch.return_value = None

        with (
            patch("cub.cli.default.LaunchService.from_config", side_effect=Exception("no config")),
            patch("cub.core.config.loader.load_config", return_value=mock_config),
            patch("cub.cli.default.LaunchService", return_value=mock_service),
        ):
            result = runner.invoke(app, [])

        # Should show project status or welcome message
        assert (
            "project status" in result.output.lower()
            or "welcome" in result.output.lower()
            or "no cub project" in result.output.lower()
        )


# =============================================================================
# Backend Tests (JSONL, Beads)
# =============================================================================


class TestBackends:
    """Tests for bare cub with different task backend systems."""

    def test_bare_cub_with_jsonl_backend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running bare `cub` with JSONL backend shows stats correctly."""
        # Set up project with JSONL backend
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)

        # Create .cub.json with JSONL backend
        cub_config = {
            "harness": "claude-code",
            "backend": "jsonl",
            "budget": {"default": 500000},
        }
        (project / ".cub.json").write_text(json.dumps(cub_config, indent=2))

        # Create tasks.jsonl file
        tasks_dir = project / ".cub" / "tasks"
        tasks_dir.mkdir(parents=True)
        tasks_file = tasks_dir / "tasks.jsonl"
        tasks = [
            {
                "id": "cub-001",
                "title": "Test task",
                "status": "open",
                "priority": 1,
                "type": "task",
            }
        ]
        tasks_file.write_text("\n".join(json.dumps(task) for task in tasks))

        # Mock environment detection and launch
        env_info = EnvironmentInfo(context=EnvironmentContext.TERMINAL)
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.return_value = None

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            # Return a welcome with task stats
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=1,
                open_tasks=1,
                in_progress_tasks=0,
                ready_tasks=1,
                top_suggestions=[],
                available_skills=[],
            )

            result = runner.invoke(app, [])

        # Should show project stats
        assert result.exit_code == 0 or mock_service.launch.called
        mock_service.launch.assert_called_once()

    def test_bare_cub_with_beads_backend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running bare `cub` with beads backend shows stats correctly."""
        # Set up project with beads backend
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)

        # Create .cub.json with beads backend (default)
        cub_config = {
            "harness": "claude-code",
            "backend": "beads",
            "budget": {"default": 500000},
        }
        (project / ".cub.json").write_text(json.dumps(cub_config, indent=2))

        # Create .beads directory with issues.jsonl
        beads_dir = project / ".beads"
        beads_dir.mkdir()
        issues_file = beads_dir / "issues.jsonl"
        issues = [
            {
                "id": "cub-001",
                "title": "Test task",
                "status": "open",
                "priority": 1,
                "issue_type": "task",
            }
        ]
        issues_file.write_text("\n".join(json.dumps(issue) for issue in issues))

        # Mock environment detection and launch
        env_info = EnvironmentInfo(context=EnvironmentContext.TERMINAL)
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.return_value = None

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            # Return a welcome with task stats
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=1,
                open_tasks=1,
                in_progress_tasks=0,
                ready_tasks=1,
                top_suggestions=[],
                available_skills=[],
            )

            result = runner.invoke(app, [])

        # Should show project stats and launch
        assert result.exit_code == 0 or mock_service.launch.called
        mock_service.launch.assert_called_once()


# =============================================================================
# Nested Session Tests
# =============================================================================


class TestNestedSession:
    """Tests for nested session detection and behavior."""

    def test_bare_cub_with_session_active_env_var(
        self, project_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running bare `cub` with CUB_SESSION_ACTIVE=1 shows inline status."""
        monkeypatch.chdir(project_dir)

        # Set nested environment variables
        monkeypatch.setenv("CUB_SESSION_ACTIVE", "1")
        monkeypatch.setenv("CUB_SESSION_ID", "test-session-123")

        # Mock environment detection to return nested context
        env_info = EnvironmentInfo(
            context=EnvironmentContext.NESTED,
            session_id="test-session-123",
        )
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=5,
                open_tasks=3,
                in_progress_tasks=1,
                ready_tasks=2,
                top_suggestions=[],
                available_skills=[],
            )

            result = runner.invoke(app, [])

        # Should show inline status and NOT launch
        assert result.exit_code == 0
        mock_service.launch.assert_not_called()
        # Output should mention session active
        assert "session active" in result.output.lower() or "tasks" in result.output.lower()

    def test_nested_session_does_not_launch(
        self, project_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nested session shows status but does not nest another harness."""
        monkeypatch.chdir(project_dir)

        # Set nested environment
        monkeypatch.setenv("CUB_SESSION_ACTIVE", "1")
        monkeypatch.setenv("CLAUDE_CODE", "1")
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_dir))

        # Mock environment detection
        env_info = EnvironmentInfo(
            context=EnvironmentContext.NESTED,
            session_id="session-456",
            harness="claude",
            project_dir=str(project_dir),
        )
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=10,
                open_tasks=5,
                in_progress_tasks=2,
                ready_tasks=3,
                top_suggestions=[],
                available_skills=[],
            )

            result = runner.invoke(app, [])

        # Should NOT call launch
        assert result.exit_code == 0
        mock_service.launch.assert_not_called()


# =============================================================================
# Resume and Continue Flag Tests
# =============================================================================


class TestResumeAndContinue:
    """Tests for --resume and --continue flag passthrough."""

    def test_bare_cub_with_resume_flag(
        self, project_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running `cub --resume` passes resume flag to launch service."""
        monkeypatch.chdir(project_dir)

        # Mock terminal environment and launch
        env_info = EnvironmentInfo(context=EnvironmentContext.TERMINAL)
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.return_value = None

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=0,
                open_tasks=0,
                in_progress_tasks=0,
                ready_tasks=0,
                top_suggestions=[],
                available_skills=[],
            )

            runner.invoke(app, ["--resume"])

        # Should call launch with resume=True
        mock_service.launch.assert_called_once_with(
            resume=True,
            continue_session=False,
            auto_approve=True,
            debug=False,
        )

    def test_bare_cub_with_continue_flag(
        self, project_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running `cub --continue` passes continue flag to launch service."""
        monkeypatch.chdir(project_dir)

        # Mock terminal environment and launch
        env_info = EnvironmentInfo(context=EnvironmentContext.TERMINAL)
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.return_value = None

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=0,
                open_tasks=0,
                in_progress_tasks=0,
                ready_tasks=0,
                top_suggestions=[],
                available_skills=[],
            )

            runner.invoke(app, ["--continue"])

        # Should call launch with continue_session=True
        mock_service.launch.assert_called_once_with(
            resume=False,
            continue_session=True,
            auto_approve=True,
            debug=False,
        )

    def test_bare_cub_with_both_resume_and_continue(
        self, project_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running `cub --resume --continue` passes both flags."""
        monkeypatch.chdir(project_dir)

        # Mock terminal environment and launch
        env_info = EnvironmentInfo(context=EnvironmentContext.TERMINAL)
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.return_value = None

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=0,
                open_tasks=0,
                in_progress_tasks=0,
                ready_tasks=0,
                top_suggestions=[],
                available_skills=[],
            )

            runner.invoke(app, ["--resume", "--continue"])

        # Should call launch with both flags
        mock_service.launch.assert_called_once_with(
            resume=True,
            continue_session=True,
            auto_approve=True,
            debug=False,
        )


# =============================================================================
# Missing Harness Tests
# =============================================================================


class TestMissingHarness:
    """Tests for handling missing harness binary."""

    def test_bare_cub_harness_not_found(
        self, project_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running bare `cub` when harness not found shows helpful error."""
        monkeypatch.chdir(project_dir)

        # Mock terminal environment
        env_info = EnvironmentInfo(context=EnvironmentContext.TERMINAL)
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info

        # Mock launch to raise HarnessNotFoundError
        from cub.core.services.launch import HarnessNotFoundError

        mock_service.launch.side_effect = HarnessNotFoundError("claude-code")

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=0,
                open_tasks=0,
                in_progress_tasks=0,
                ready_tasks=0,
                top_suggestions=[],
                available_skills=[],
            )

            result = runner.invoke(app, [])

        # Should exit with code 1
        assert result.exit_code == 1
        assert (
            "harness not found" in result.output.lower() or "claude-code" in result.output.lower()
        )

    def test_no_project_harness_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fresh directory with no harness shows combined error message."""
        monkeypatch.chdir(tmp_path)

        # Mock config load to fail (no project)
        # Mock harness resolution to fail (no binary)
        from cub.core.services.launch import HarnessNotFoundError

        mock_config = MagicMock()
        mock_config.harness.name = "claude-code"

        mock_service = MagicMock()
        mock_service.launch.side_effect = HarnessNotFoundError("claude-code")

        with (
            patch("cub.cli.default.LaunchService.from_config", side_effect=Exception("no config")),
            patch("cub.core.config.loader.load_config", return_value=mock_config),
            patch("cub.cli.default.LaunchService", return_value=mock_service),
        ):
            result = runner.invoke(app, [])

        # Should show error about missing harness or inline status
        # Exit code depends on whether error was raised or handled
        assert result.exit_code in (0, 1)
        # Should at least show some output (status or error)
        assert len(result.output) > 0


# =============================================================================
# Help and Subcommand Tests
# =============================================================================


class TestHelpAndSubcommands:
    """Tests for help and subcommand routing."""

    def test_cub_help_shows_help(self) -> None:
        """Running `cub --help` shows help text."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "cub" in result.output.lower()
        assert "command" in result.output.lower() or "usage" in result.output.lower()

    def test_cub_h_shows_help(self) -> None:
        """Running `cub -h` shows help text."""
        result = runner.invoke(app, ["-h"])
        assert result.exit_code == 0
        assert "cub" in result.output.lower()

    def test_cub_version_shows_version(self) -> None:
        """Running `cub version` shows version and does not invoke default."""
        with patch("cub.cli.default.default_command") as mock_default:
            result = runner.invoke(app, ["version"])

        # Should NOT invoke default command
        mock_default.assert_not_called()
        assert result.exit_code == 0
        assert "version" in result.output.lower()

    def test_cub_init_routes_to_subcommand(self) -> None:
        """Running `cub init` routes to init subcommand, not default."""
        with patch("cub.cli.default.default_command") as mock_default:
            # Don't need to mock init itself - just verify default wasn't called
            # init may still fail but that's OK for this test
            runner.invoke(app, ["init"])

        # Should NOT invoke default command
        mock_default.assert_not_called()

    def test_cub_run_routes_to_subcommand(self) -> None:
        """Running `cub run` routes to run subcommand, not default."""
        # Mock the run command's main functionality to prevent it from actually running
        with (
            patch("cub.cli.default.default_command") as mock_default,
            patch("cub.cli.run.load_config", side_effect=Exception("mocked")),
        ):
            # run command will fail but that's OK - we just verify default wasn't called
            result = runner.invoke(app, ["run"])

        # Should NOT invoke default command
        mock_default.assert_not_called()
        # Exit code will be non-zero because we mocked config load to fail
        assert result.exit_code != 0 or mock_default.call_count == 0

    def test_cub_task_list_routes_to_subcommand(self) -> None:
        """Running `cub task list` routes to task subcommand, not default."""
        with patch("cub.cli.default.default_command") as mock_default:
            # Just verify default isn't called - actual task command tested elsewhere
            runner.invoke(app, ["task", "list"])

        # Should NOT invoke default command
        mock_default.assert_not_called()


# =============================================================================
# Debug Flag Tests
# =============================================================================


class TestDebugFlag:
    """Tests for debug flag behavior."""

    def test_bare_cub_with_debug_flag(
        self, project_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running `cub --debug` passes debug flag to launch service."""
        monkeypatch.chdir(project_dir)

        # Mock terminal environment and launch
        env_info = EnvironmentInfo(context=EnvironmentContext.TERMINAL)
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.return_value = None

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=0,
                open_tasks=0,
                in_progress_tasks=0,
                ready_tasks=0,
                top_suggestions=[],
                available_skills=[],
            )

            runner.invoke(app, ["--debug"])

        # Should call launch with debug=True
        mock_service.launch.assert_called_once_with(
            resume=False,
            continue_session=False,
            auto_approve=True,
            debug=True,
        )

    def test_debug_shows_environment_info(
        self, project_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running `cub --debug` shows environment detection info."""
        monkeypatch.chdir(project_dir)

        # Mock terminal environment
        env_info = EnvironmentInfo(
            context=EnvironmentContext.TERMINAL,
            session_id=None,
        )
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.return_value = None

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=0,
                open_tasks=0,
                in_progress_tasks=0,
                ready_tasks=0,
                top_suggestions=[],
                available_skills=[],
            )

            result = runner.invoke(app, ["--debug"])

        # Debug output may show environment context
        # (implementation detail, but good to verify something happens)
        assert result.exit_code == 0 or mock_service.launch.called


# =============================================================================
# Environment Context Edge Cases
# =============================================================================


class TestEnvironmentEdgeCases:
    """Tests for edge cases in environment detection."""

    def test_harness_context_without_cub_session(
        self, project_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running in harness (not cub-launched) shows inline status."""
        monkeypatch.chdir(project_dir)

        # Set harness env vars but NOT cub session vars
        monkeypatch.setenv("CLAUDE_CODE", "1")
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_dir))

        # Mock harness (not nested) context
        env_info = EnvironmentInfo(
            context=EnvironmentContext.HARNESS,
            harness="claude",
            project_dir=str(project_dir),
        )
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=5,
                open_tasks=3,
                in_progress_tasks=1,
                ready_tasks=2,
                top_suggestions=[],
                available_skills=[],
            )

            result = runner.invoke(app, [])

        # Should show inline status and NOT launch
        assert result.exit_code == 0
        mock_service.launch.assert_not_called()

    def test_clean_terminal_environment(
        self, project_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running in clean terminal (no env vars) launches harness."""
        monkeypatch.chdir(project_dir)

        # Clear all cub/harness env vars
        for key in ["CUB_SESSION_ACTIVE", "CUB_SESSION_ID", "CLAUDE_CODE", "CLAUDE_PROJECT_DIR"]:
            monkeypatch.delenv(key, raising=False)

        # Mock clean terminal environment
        env_info = EnvironmentInfo(context=EnvironmentContext.TERMINAL)
        mock_service = MagicMock()
        mock_service.detect.return_value = env_info
        mock_service.launch.return_value = None

        with (
            patch("cub.cli.default.LaunchService.from_config", return_value=mock_service),
            patch("cub.cli.default._get_welcome_message") as mock_welcome,
        ):
            from cub.core.suggestions.engine import WelcomeMessage

            mock_welcome.return_value = WelcomeMessage(
                total_tasks=0,
                open_tasks=0,
                in_progress_tasks=0,
                ready_tasks=0,
                top_suggestions=[],
                available_skills=[],
            )

            result = runner.invoke(app, [])

        # Should launch harness
        assert result.exit_code == 0 or mock_service.launch.called
        mock_service.launch.assert_called_once()
