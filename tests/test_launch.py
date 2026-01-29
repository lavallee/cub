"""
Tests for launch service and related modules.

Tests environment detection, harness launching, and the LaunchService API.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.launch import (
    EnvironmentContext,
    EnvironmentInfo,
    HarnessBinaryNotFoundError,
    LaunchConfig,
    build_launch_args,
    build_launch_env,
    detect_environment,
    resolve_harness_binary,
)
from cub.core.services.launch import (
    HarnessNotFoundError,
    LaunchService,
    LaunchServiceError,
)

# ============================================================================
# Environment Detection Tests
# ============================================================================


class TestDetectEnvironment:
    """Tests for detect_environment function."""

    def test_terminal_context(self) -> None:
        """Test detection of terminal context (no env vars)."""
        with patch.dict(os.environ, {}, clear=True):
            env = detect_environment()
            assert env.context == EnvironmentContext.TERMINAL
            assert not env.in_harness
            assert not env.is_nested
            assert env.harness is None
            assert env.session_id is None

    def test_claude_code_context(self) -> None:
        """Test detection of Claude Code harness context."""
        with patch.dict(
            os.environ,
            {"CLAUDE_CODE": "1", "CLAUDE_PROJECT_DIR": "/project"},
            clear=True,
        ):
            env = detect_environment()
            assert env.context == EnvironmentContext.HARNESS
            assert env.in_harness
            assert not env.is_nested
            assert env.harness == "claude"
            assert env.project_dir == "/project"

    def test_nested_context(self) -> None:
        """Test detection of nested cub session."""
        with patch.dict(
            os.environ,
            {
                "CUB_SESSION_ACTIVE": "1",
                "CUB_SESSION_ID": "session-123",
                "CLAUDE_PROJECT_DIR": "/project",
            },
            clear=True,
        ):
            env = detect_environment()
            assert env.context == EnvironmentContext.NESTED
            assert env.in_harness
            assert env.is_nested
            assert env.session_id == "session-123"
            assert env.project_dir == "/project"

    def test_nested_takes_priority_over_harness(self) -> None:
        """Test that nested detection takes priority over harness detection."""
        with patch.dict(
            os.environ,
            {
                "CUB_SESSION_ACTIVE": "1",
                "CUB_SESSION_ID": "session-123",
                "CLAUDE_CODE": "1",
            },
            clear=True,
        ):
            env = detect_environment()
            assert env.context == EnvironmentContext.NESTED
            assert env.is_nested

    def test_claude_code_not_set(self) -> None:
        """Test that CLAUDE_CODE must be '1' to detect harness."""
        with patch.dict(os.environ, {"CLAUDE_CODE": "0"}, clear=True):
            env = detect_environment()
            assert env.context == EnvironmentContext.TERMINAL


# ============================================================================
# Harness Resolution Tests
# ============================================================================


class TestResolveHarnessBinary:
    """Tests for resolve_harness_binary function."""

    def test_resolve_claude_code(self) -> None:
        """Test resolving Claude Code binary."""
        with patch("shutil.which", return_value="/usr/bin/claude"):
            binary = resolve_harness_binary("claude-code")
            assert binary == "/usr/bin/claude"

    def test_resolve_claude_alias(self) -> None:
        """Test resolving 'claude' alias."""
        with patch("shutil.which", return_value="/usr/bin/claude"):
            binary = resolve_harness_binary("claude")
            assert binary == "/usr/bin/claude"

    def test_resolve_codex(self) -> None:
        """Test resolving Codex binary."""
        with patch("shutil.which", return_value="/usr/bin/codex"):
            binary = resolve_harness_binary("codex")
            assert binary == "/usr/bin/codex"

    def test_binary_not_found(self) -> None:
        """Test error when binary not found in PATH."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(HarnessBinaryNotFoundError) as exc_info:
                resolve_harness_binary("claude-code")
            assert exc_info.value.harness_name == "claude-code"
            assert "claude" in str(exc_info.value)


# ============================================================================
# Launch Args Tests
# ============================================================================


class TestBuildLaunchArgs:
    """Tests for build_launch_args function."""

    def test_minimal_args(self) -> None:
        """Test building args with minimal config."""
        config = LaunchConfig(
            harness_name="claude-code",
            binary_path="/usr/bin/claude",
            working_dir="/project",
        )
        args = build_launch_args(config)
        assert args == []

    def test_resume_flag(self) -> None:
        """Test resume flag is included."""
        config = LaunchConfig(
            harness_name="claude-code",
            binary_path="/usr/bin/claude",
            working_dir="/project",
            resume=True,
        )
        args = build_launch_args(config)
        assert "--resume" in args

    def test_continue_flag(self) -> None:
        """Test continue flag is included."""
        config = LaunchConfig(
            harness_name="claude-code",
            binary_path="/usr/bin/claude",
            working_dir="/project",
            continue_session=True,
        )
        args = build_launch_args(config)
        assert "--continue" in args

    def test_debug_flag(self) -> None:
        """Test debug flag is included."""
        config = LaunchConfig(
            harness_name="claude-code",
            binary_path="/usr/bin/claude",
            working_dir="/project",
            debug=True,
        )
        args = build_launch_args(config)
        assert "--debug" in args

    def test_auto_approve_claude(self) -> None:
        """Test auto-approve flag for Claude Code."""
        config = LaunchConfig(
            harness_name="claude-code",
            binary_path="/usr/bin/claude",
            working_dir="/project",
            auto_approve=True,
        )
        args = build_launch_args(config)
        assert "--dangerously-skip-permissions" in args

    def test_all_flags(self) -> None:
        """Test building args with all flags enabled."""
        config = LaunchConfig(
            harness_name="claude-code",
            binary_path="/usr/bin/claude",
            working_dir="/project",
            resume=True,
            continue_session=True,
            debug=True,
            auto_approve=True,
        )
        args = build_launch_args(config)
        assert "--resume" in args
        assert "--continue" in args
        assert "--debug" in args
        assert "--dangerously-skip-permissions" in args


# ============================================================================
# Launch Environment Tests
# ============================================================================


class TestBuildLaunchEnv:
    """Tests for build_launch_env function."""

    def test_sets_session_active(self) -> None:
        """Test CUB_SESSION_ACTIVE is set."""
        config = LaunchConfig(
            harness_name="claude-code",
            binary_path="/usr/bin/claude",
            working_dir="/project",
        )
        env = build_launch_env(config)
        assert env["CUB_SESSION_ACTIVE"] == "1"

    def test_generates_session_id(self) -> None:
        """Test CUB_SESSION_ID is generated if not provided."""
        config = LaunchConfig(
            harness_name="claude-code",
            binary_path="/usr/bin/claude",
            working_dir="/project",
        )
        env = build_launch_env(config)
        assert "CUB_SESSION_ID" in env
        assert len(env["CUB_SESSION_ID"]) > 0

    def test_uses_provided_session_id(self) -> None:
        """Test provided session_id is used."""
        config = LaunchConfig(
            harness_name="claude-code",
            binary_path="/usr/bin/claude",
            working_dir="/project",
            session_id="custom-session-123",
        )
        env = build_launch_env(config)
        assert env["CUB_SESSION_ID"] == "custom-session-123"

    def test_preserves_existing_env(self) -> None:
        """Test existing environment variables are preserved."""
        with patch.dict(os.environ, {"CUSTOM_VAR": "value"}, clear=True):
            config = LaunchConfig(
                harness_name="claude-code",
                binary_path="/usr/bin/claude",
                working_dir="/project",
            )
            env = build_launch_env(config)
            assert env["CUSTOM_VAR"] == "value"


# ============================================================================
# LaunchService Tests
# ============================================================================


class TestLaunchService:
    """Tests for LaunchService."""

    def test_from_config(self) -> None:
        """Test service creation from config."""
        with patch("cub.core.services.launch.load_config") as mock_load:
            mock_config = MagicMock()
            mock_config.harness.name = "claude-code"
            mock_load.return_value = mock_config

            service = LaunchService.from_config()
            assert service.config == mock_config
            assert service.project_dir == Path.cwd()

    def test_detect_environment(self) -> None:
        """Test detect method delegates to detect_environment."""
        with patch("cub.core.services.launch.load_config"):
            service = LaunchService.from_config()

            with patch.dict(os.environ, {}, clear=True):
                env = service.detect()
                assert env.context == EnvironmentContext.TERMINAL

    def test_launch_with_defaults(self) -> None:
        """Test launch with default configuration."""
        mock_config = MagicMock()
        mock_config.harness.name = "claude-code"

        with patch("cub.core.services.launch.load_config", return_value=mock_config):
            service = LaunchService.from_config()

            with patch("cub.core.services.launch.resolve_harness_binary") as mock_resolve:
                with patch("cub.core.services.launch.launch_harness") as mock_launch:
                    mock_resolve.return_value = "/usr/bin/claude"

                    service.launch()

                    # Verify binary resolution
                    mock_resolve.assert_called_once_with("claude-code")

                    # Verify launch was called with correct config
                    mock_launch.assert_called_once()
                    config = mock_launch.call_args[0][0]
                    assert config.harness_name == "claude-code"
                    assert config.binary_path == "/usr/bin/claude"
                    assert not config.resume
                    assert not config.debug

    def test_launch_with_explicit_harness(self) -> None:
        """Test launch with explicit harness name."""
        mock_config = MagicMock()
        mock_config.harness.name = "claude-code"

        with patch("cub.core.services.launch.load_config", return_value=mock_config):
            service = LaunchService.from_config()

            with patch("cub.core.services.launch.resolve_harness_binary") as mock_resolve:
                with patch("cub.core.services.launch.launch_harness") as mock_launch:
                    mock_resolve.return_value = "/usr/bin/codex"

                    service.launch(harness_name="codex")

                    mock_resolve.assert_called_once_with("codex")
                    config = mock_launch.call_args[0][0]
                    assert config.harness_name == "codex"

    def test_launch_with_flags(self) -> None:
        """Test launch with resume, debug, and auto_approve flags."""
        mock_config = MagicMock()
        mock_config.harness.name = "claude-code"

        with patch("cub.core.services.launch.load_config", return_value=mock_config):
            service = LaunchService.from_config()

            with patch("cub.core.services.launch.resolve_harness_binary") as mock_resolve:
                with patch("cub.core.services.launch.launch_harness") as mock_launch:
                    mock_resolve.return_value = "/usr/bin/claude"

                    service.launch(resume=True, debug=True, auto_approve=True)

                    config = mock_launch.call_args[0][0]
                    assert config.resume
                    assert config.debug
                    assert config.auto_approve

    def test_launch_harness_not_found(self) -> None:
        """Test error when harness binary not found."""
        mock_config = MagicMock()
        mock_config.harness.name = "nonexistent"

        with patch("cub.core.services.launch.load_config", return_value=mock_config):
            service = LaunchService.from_config()

            with patch(
                "cub.core.services.launch.resolve_harness_binary",
                side_effect=HarnessBinaryNotFoundError("nonexistent", "nonexistent"),
            ):
                with pytest.raises(HarnessNotFoundError) as exc_info:
                    service.launch()
                assert exc_info.value.harness_name == "nonexistent"

    def test_launch_error_handling(self) -> None:
        """Test error handling during launch."""
        mock_config = MagicMock()
        mock_config.harness.name = "claude-code"

        with patch("cub.core.services.launch.load_config", return_value=mock_config):
            service = LaunchService.from_config()

            with patch("cub.core.services.launch.resolve_harness_binary") as mock_resolve:
                with patch(
                    "cub.core.services.launch.launch_harness",
                    side_effect=OSError("Launch failed"),
                ):
                    mock_resolve.return_value = "/usr/bin/claude"

                    with pytest.raises(LaunchServiceError) as exc_info:
                        service.launch()
                    assert "Failed to launch harness" in str(exc_info.value)


# ============================================================================
# EnvironmentInfo Model Tests
# ============================================================================


class TestEnvironmentInfo:
    """Tests for EnvironmentInfo model."""

    def test_is_nested_property(self) -> None:
        """Test is_nested property."""
        nested = EnvironmentInfo(context=EnvironmentContext.NESTED)
        assert nested.is_nested

        terminal = EnvironmentInfo(context=EnvironmentContext.TERMINAL)
        assert not terminal.is_nested

    def test_in_harness_property(self) -> None:
        """Test in_harness property."""
        harness = EnvironmentInfo(context=EnvironmentContext.HARNESS)
        assert harness.in_harness

        nested = EnvironmentInfo(context=EnvironmentContext.NESTED)
        assert nested.in_harness

        terminal = EnvironmentInfo(context=EnvironmentContext.TERMINAL)
        assert not terminal.in_harness
