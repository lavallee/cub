"""
Tests for CLI hooks commands.

Tests the `cub hooks log` command for viewing hook forensics.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cub.cli.hooks import app

runner = CliRunner()


@pytest.fixture
def temp_project_with_forensics(tmp_path: Path) -> Path:
    """Create a temporary project with forensics files."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create forensics directory
    forensics_dir = project_dir / ".cub" / "ledger" / "forensics"
    forensics_dir.mkdir(parents=True)

    # Create a forensics file with sample events
    session_file = forensics_dir / "test-session-001.jsonl"
    events = [
        {
            "event_type": "session_start",
            "timestamp": "2026-01-28T12:00:00.000000+00:00",
            "session_id": "test-session-001",
            "cwd": str(project_dir),
        },
        {
            "event_type": "task_claim",
            "timestamp": "2026-01-28T12:01:00.000000+00:00",
            "session_id": "test-session-001",
            "task_id": "proj-abc.1",
            "command": "cub task claim proj-abc.1",
        },
        {
            "event_type": "file_write",
            "timestamp": "2026-01-28T12:02:00.000000+00:00",
            "session_id": "test-session-001",
            "file_path": str(project_dir / "src" / "main.py"),
            "tool_name": "Write",
            "file_category": "source",
        },
        {
            "event_type": "git_commit",
            "timestamp": "2026-01-28T12:03:00.000000+00:00",
            "session_id": "test-session-001",
            "command": 'git commit -m "feat: add main"',
            "message_preview": "feat: add main",
        },
        {
            "event_type": "session_end",
            "timestamp": "2026-01-28T12:04:00.000000+00:00",
            "session_id": "test-session-001",
            "transcript_path": "/home/user/.claude/sessions/123.jsonl",
        },
    ]

    with session_file.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    # Create a second session file
    session_file_2 = forensics_dir / "test-session-002.jsonl"
    events_2 = [
        {
            "event_type": "session_start",
            "timestamp": "2026-01-28T13:00:00.000000+00:00",
            "session_id": "test-session-002",
            "cwd": str(project_dir),
        },
    ]

    with session_file_2.open("w", encoding="utf-8") as f:
        for event in events_2:
            f.write(json.dumps(event) + "\n")

    return project_dir


class TestHooksLogCommand:
    """Tests for `cub hooks log` command."""

    def test_log_shows_recent_events(self, temp_project_with_forensics: Path) -> None:
        """Test that log shows recent events."""
        result = runner.invoke(
            app, ["log", "--project", str(temp_project_with_forensics)]
        )
        assert result.exit_code == 0
        assert "Hook Forensics" in result.output
        assert "session_start" in result.output
        assert "test-session-001" in result.output or "test-session-00..." in result.output

    def test_log_filters_by_session(self, temp_project_with_forensics: Path) -> None:
        """Test that --session flag filters events."""
        result = runner.invoke(
            app,
            [
                "log",
                "--project",
                str(temp_project_with_forensics),
                "--session",
                "test-session-001",
            ],
        )
        assert result.exit_code == 0
        # Should see session 001 events
        assert "task_claim" in result.output
        assert "file_write" in result.output

    def test_log_filters_by_event_type(self, temp_project_with_forensics: Path) -> None:
        """Test that --type flag filters events."""
        result = runner.invoke(
            app,
            [
                "log",
                "--project",
                str(temp_project_with_forensics),
                "--type",
                "file_write",
            ],
        )
        assert result.exit_code == 0
        assert "file_write" in result.output
        # Should not see other event types in the same row
        assert "task_claim" not in result.output

    def test_log_limits_events(self, temp_project_with_forensics: Path) -> None:
        """Test that --limit flag limits output."""
        result = runner.invoke(
            app,
            [
                "log",
                "--project",
                str(temp_project_with_forensics),
                "--limit",
                "2",
            ],
        )
        assert result.exit_code == 0
        assert "showing 2 of" in result.output

    def test_log_json_output(self, temp_project_with_forensics: Path) -> None:
        """Test that --json outputs valid JSON."""
        result = runner.invoke(
            app,
            [
                "log",
                "--project",
                str(temp_project_with_forensics),
                "--json",
            ],
        )
        assert result.exit_code == 0
        # Should be valid JSON
        events = json.loads(result.output)
        assert isinstance(events, list)
        assert len(events) > 0
        assert "event_type" in events[0]

    def test_log_no_forensics_directory(self, tmp_path: Path) -> None:
        """Test message when no forensics exist."""
        project_dir = tmp_path / "empty-project"
        project_dir.mkdir()

        result = runner.invoke(app, ["log", "--project", str(project_dir)])
        assert result.exit_code == 0
        assert "No forensics found" in result.output

    def test_log_no_matching_session(self, temp_project_with_forensics: Path) -> None:
        """Test message when session filter matches nothing."""
        result = runner.invoke(
            app,
            [
                "log",
                "--project",
                str(temp_project_with_forensics),
                "--session",
                "nonexistent-session",
            ],
        )
        assert result.exit_code == 0
        assert "No forensics found for session" in result.output

    def test_log_no_matching_event_type(
        self, temp_project_with_forensics: Path
    ) -> None:
        """Test message when event type filter matches nothing."""
        result = runner.invoke(
            app,
            [
                "log",
                "--project",
                str(temp_project_with_forensics),
                "--type",
                "nonexistent_type",
            ],
        )
        assert result.exit_code == 0
        assert "No events of type" in result.output

    def test_log_shows_event_details(self, temp_project_with_forensics: Path) -> None:
        """Test that log shows relevant event details."""
        result = runner.invoke(
            app, ["log", "--project", str(temp_project_with_forensics)]
        )
        assert result.exit_code == 0
        # Should show task details
        assert "proj-abc.1" in result.output or "task:" in result.output
        # Should show commit message
        assert "feat: add main" in result.output or "git_commit" in result.output

    def test_log_partial_session_match(
        self, temp_project_with_forensics: Path
    ) -> None:
        """Test that partial session ID matches work."""
        result = runner.invoke(
            app,
            [
                "log",
                "--project",
                str(temp_project_with_forensics),
                "--session",
                "test-session",  # Partial match
            ],
        )
        assert result.exit_code == 0
        # Should find events from both sessions
        assert "Hook Forensics" in result.output
