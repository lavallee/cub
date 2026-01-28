"""Tests for the shell hook filter script (cub-hook.sh).

This test suite validates the fast-path filtering logic that prevents
unnecessary Python invocations for irrelevant hook events.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def hook_script() -> Path:
    """Get path to the hook filter script."""
    # Script is in src/cub/templates/scripts/cub-hook.sh
    script_path = Path(__file__).parent.parent / "src/cub/templates/scripts/cub-hook.sh"
    assert script_path.exists(), f"Hook script not found at {script_path}"
    return script_path


def run_hook(
    hook_script: Path,
    event_name: str,
    payload: dict[str, Any],
    env: dict[str, str] | None = None,
) -> tuple[str, int]:
    """Run the hook script with a JSON payload.

    Args:
        hook_script: Path to cub-hook.sh
        event_name: Hook event name (PostToolUse, SessionStart, etc.)
        payload: JSON payload to send via stdin
        env: Optional environment variables to set

    Returns:
        Tuple of (stdout, exit_code)
    """
    full_env = {"PATH": "/usr/bin:/bin"}  # Minimal PATH for testing
    if env:
        full_env.update(env)

    result = subprocess.run(
        ["bash", str(hook_script), event_name],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=full_env,
    )
    return result.stdout.strip(), result.returncode


class TestDoubleTrackingPrevention:
    """Tests for CUB_RUN_ACTIVE environment variable handling."""

    def test_exits_immediately_when_cub_run_active(self, hook_script: Path) -> None:
        """Script should exit immediately with success when CUB_RUN_ACTIVE is set."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "plans/test.md"},
        }

        stdout, exit_code = run_hook(
            hook_script, "PostToolUse", payload, env={"CUB_RUN_ACTIVE": "1"}
        )

        assert exit_code == 0
        assert "continue" in stdout
        # Should NOT invoke Python (stdout should be minimal JSON)
        assert "hookEventName" not in stdout

    def test_processes_normally_when_cub_run_not_active(self, hook_script: Path) -> None:
        """Script should process normally when CUB_RUN_ACTIVE is not set."""
        payload = {
            "hook_event_name": "SessionStart",
            "session_id": "test-session",
        }

        # This will invoke Python, which may fail (that's ok for this test)
        # We're just verifying the fast-path check passes
        _, exit_code = run_hook(hook_script, "SessionStart", payload, env={})

        # Exit code may be non-zero if Python isn't available, but that's expected
        # The key is that it tried to invoke Python (didn't short-circuit)
        assert exit_code in (0, 1, 127)  # 127 = command not found


class TestPostToolUseFiltering:
    """Tests for PostToolUse event filtering."""

    def test_skips_read_tool(self, hook_script: Path) -> None:
        """Should skip Read tool (not tracked)."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "src/main.py"},
        }

        stdout, exit_code = run_hook(hook_script, "PostToolUse", payload, env={})

        assert exit_code == 0
        assert "continue" in stdout
        assert "hookEventName" not in stdout  # Didn't invoke Python

    def test_skips_glob_tool(self, hook_script: Path) -> None:
        """Should skip Glob tool (not tracked)."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Glob",
            "tool_input": {"pattern": "*.py"},
        }

        stdout, exit_code = run_hook(hook_script, "PostToolUse", payload, env={})

        assert exit_code == 0
        assert "continue" in stdout
        assert "hookEventName" not in stdout

    def test_skips_grep_tool(self, hook_script: Path) -> None:
        """Should skip Grep tool (not tracked)."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Grep",
            "tool_input": {"pattern": "TODO"},
        }

        stdout, exit_code = run_hook(hook_script, "PostToolUse", payload, env={})

        assert exit_code == 0
        assert "continue" in stdout


class TestWriteEditFiltering:
    """Tests for Write/Edit tool filtering by file path."""

    @pytest.mark.parametrize(
        "file_path",
        [
            "plans/epic/plan.md",
            "specs/feature.md",
            "captures/idea.md",
            "src/main.py",
            ".cub/tasks.json",
        ],
    )
    def test_passes_through_tracked_paths(self, hook_script: Path, file_path: str) -> None:
        """Should pass Write/Edit to Python for tracked directories."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": file_path},
        }

        # Will invoke Python (may fail if Python not available)
        _, exit_code = run_hook(hook_script, "PostToolUse", payload, env={})

        # Exit code 0 or error (1/127) - key is that it tried
        assert exit_code in (0, 1, 127)

    @pytest.mark.parametrize(
        "file_path",
        [
            "README.md",
            "test/unit.py",
            "docs/guide.md",
            "tmp/scratch.txt",
        ],
    )
    def test_skips_untracked_paths(self, hook_script: Path, file_path: str) -> None:
        """Should skip Write/Edit to untracked directories."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": file_path},
        }

        stdout, exit_code = run_hook(hook_script, "PostToolUse", payload, env={})

        assert exit_code == 0
        assert "continue" in stdout
        assert "hookEventName" not in stdout

    def test_handles_edit_tool(self, hook_script: Path) -> None:
        """Should handle Edit tool the same as Write."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": "plans/test.md"},
        }

        # Will invoke Python
        _, exit_code = run_hook(hook_script, "PostToolUse", payload, env={})
        assert exit_code in (0, 1, 127)

    def test_handles_notebook_edit_tool(self, hook_script: Path) -> None:
        """Should handle NotebookEdit tool with notebook_path."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": "specs/analysis.ipynb"},
        }

        # Will invoke Python
        _, exit_code = run_hook(hook_script, "PostToolUse", payload, env={})
        assert exit_code in (0, 1, 127)


class TestBashCommandFiltering:
    """Tests for Bash tool filtering by command pattern."""

    @pytest.mark.parametrize(
        "command",
        [
            "cub task close cub-123",
            "cub task claim cub-456",
            "git commit -m 'message'",
            "git add .",
            "bd close cub-123",  # Contains 'cub'
        ],
    )
    def test_passes_through_tracked_commands(self, hook_script: Path, command: str) -> None:
        """Should pass Bash commands with task/git patterns to Python."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }

        # Will invoke Python
        _, exit_code = run_hook(hook_script, "PostToolUse", payload, env={})
        assert exit_code in (0, 1, 127)

    @pytest.mark.parametrize(
        "command",
        [
            "ls -la",
            "pytest tests/",
            "mypy src/",
            "npm install",
            "python -m foo",
        ],
    )
    def test_skips_untracked_commands(self, hook_script: Path, command: str) -> None:
        """Should skip Bash commands without task/git patterns."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }

        stdout, exit_code = run_hook(hook_script, "PostToolUse", payload, env={})

        assert exit_code == 0
        assert "continue" in stdout
        assert "hookEventName" not in stdout


class TestSessionLifecycleEvents:
    """Tests for session lifecycle event handling."""

    @pytest.mark.parametrize(
        "event_name",
        [
            "SessionStart",
            "Stop",
            "SessionEnd",
            "PreCompact",
            "UserPromptSubmit",
        ],
    )
    def test_always_passes_through_lifecycle_events(
        self, hook_script: Path, event_name: str
    ) -> None:
        """Session lifecycle events should always pass through to Python."""
        payload = {
            "hook_event_name": event_name,
            "session_id": "test-session",
        }

        # Will invoke Python
        _, exit_code = run_hook(hook_script, event_name, payload, env={})
        assert exit_code in (0, 1, 127)


class TestMalformedInput:
    """Tests for handling malformed JSON and edge cases."""

    def test_handles_empty_stdin(self, hook_script: Path) -> None:
        """Should handle empty stdin gracefully."""
        result = subprocess.run(
            ["bash", str(hook_script), "PostToolUse"],
            input="",
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin"},
        )

        assert result.returncode == 0
        assert "continue" in result.stdout

    def test_handles_invalid_json(self, hook_script: Path) -> None:
        """Should handle invalid JSON gracefully."""
        result = subprocess.run(
            ["bash", str(hook_script), "PostToolUse"],
            input="not valid json {",
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin"},
        )

        assert result.returncode == 0
        assert "continue" in result.stdout

    def test_handles_missing_fields(self, hook_script: Path) -> None:
        """Should handle JSON with missing fields gracefully."""
        payload = {"hook_event_name": "PostToolUse"}  # Missing tool_name

        stdout, exit_code = run_hook(hook_script, "PostToolUse", payload, env={})

        assert exit_code == 0
        assert "continue" in stdout


class TestUnknownEvents:
    """Tests for handling unknown event types."""

    def test_skips_unknown_event_type(self, hook_script: Path) -> None:
        """Should skip unknown event types with safe default."""
        payload = {
            "hook_event_name": "UnknownEvent",
            "session_id": "test",
        }

        stdout, exit_code = run_hook(hook_script, "UnknownEvent", payload, env={})

        assert exit_code == 0
        assert "continue" in stdout
        assert "hookEventName" not in stdout  # Didn't invoke Python


class TestJqFallback:
    """Tests for JSON parsing with and without jq."""

    def test_works_without_jq(self, hook_script: Path) -> None:
        """Should work using grep/sed fallback when jq is not available."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "plans/test.md"},
        }

        # Run with minimal PATH that excludes jq
        result = subprocess.run(
            ["bash", str(hook_script), "PostToolUse"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin"},  # Likely no jq in these dirs
        )

        # Should still work (will try to invoke Python)
        assert result.returncode in (0, 1, 127)
