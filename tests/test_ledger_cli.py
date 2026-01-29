"""
Tests for ledger CLI commands.

Tests the CLI interface for ledger operations including show, update,
export, and gc commands using Typer's CliRunner.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cub.cli.ledger import app
from cub.core.ledger.models import (
    Attempt,
    LedgerEntry,
    Lineage,
    Outcome,
    StateTransition,
    TaskSnapshot,
    TokenUsage,
    WorkflowState,
)
from cub.core.ledger.writer import LedgerWriter

runner = CliRunner()


@pytest.fixture
def ledger_dir(tmp_path: Path) -> Path:
    """Create a temporary ledger directory."""
    ledger = tmp_path / ".cub" / "ledger"
    ledger.mkdir(parents=True)
    return ledger


@pytest.fixture
def sample_entry() -> LedgerEntry:
    """Create a sample ledger entry for testing."""
    now = datetime.now(timezone.utc)
    return LedgerEntry(
        id="cub-test-1",
        title="Test Task",
        lineage=Lineage(epic_id="cub-epic", spec_file="specs/test.md"),
        task=TaskSnapshot(
            title="Test Task",
            description="A test task",
            type="task",
            priority=1,
        ),
        attempts=[
            Attempt(
                attempt_number=1,
                run_id="cub-20260124-100000",
                started_at=now,
                completed_at=now,
                harness="claude",
                model="haiku",
                success=True,
                tokens=TokenUsage(input_tokens=1000, output_tokens=500),
                cost_usd=0.01,
                duration_seconds=30,
            ),
        ],
        outcome=Outcome(
            success=True,
            partial=False,
            completed_at=now,
            total_cost_usd=0.01,
            total_attempts=1,
            total_duration_seconds=30,
            final_model="haiku",
            files_changed=["src/test.py"],
            commits=[],
        ),
        workflow=WorkflowState(stage="dev_complete", stage_updated_at=now),
        state_history=[
            StateTransition(stage="dev_complete", at=now, by="cub-run"),
        ],
        started_at=now,
        completed_at=now,
        tokens=TokenUsage(input_tokens=1000, output_tokens=500),
        cost_usd=0.01,
        duration_seconds=30,
        harness_name="claude",
        harness_model="haiku",
    )


@pytest.fixture
def populated_ledger(ledger_dir: Path, sample_entry: LedgerEntry, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a ledger with sample entries."""
    writer = LedgerWriter(ledger_dir)
    writer.create_entry(sample_entry)

    # Patch the ledger directory lookup
    monkeypatch.setenv("CUB_LEDGER_DIR", str(ledger_dir))

    # Patch the _get_ledger_reader, _get_ledger_writer, and _get_ledger_service
    from cub.core.ledger.reader import LedgerReader
    from cub.core.services.ledger import LedgerService

    def mock_get_reader() -> LedgerReader:
        return LedgerReader(ledger_dir)

    def mock_get_writer() -> LedgerWriter:
        return LedgerWriter(ledger_dir)

    def mock_get_service() -> LedgerService:
        return LedgerService(ledger_dir)

    monkeypatch.setattr("cub.cli.ledger._get_ledger_reader", mock_get_reader)
    monkeypatch.setattr("cub.cli.ledger._get_ledger_writer", mock_get_writer)
    monkeypatch.setattr("cub.cli.ledger._get_ledger_service", mock_get_service)

    return ledger_dir


class TestShowCommand:
    """Tests for the 'ledger show' command."""

    def test_show_task_not_found(self, populated_ledger: Path) -> None:
        """Test show command with non-existent task."""
        result = runner.invoke(app, ["show", "nonexistent-task"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_show_basic(self, populated_ledger: Path) -> None:
        """Test basic show command output."""
        result = runner.invoke(app, ["show", "cub-test-1"])
        assert result.exit_code == 0
        assert "Test Task" in result.output
        assert "cub-test-1" in result.output

    def test_show_json_output(self, populated_ledger: Path) -> None:
        """Test show command with --json flag."""
        result = runner.invoke(app, ["show", "cub-test-1", "--json"])
        assert result.exit_code == 0
        # Should be valid JSON
        data = json.loads(result.output)
        assert data["id"] == "cub-test-1"
        assert data["title"] == "Test Task"

    def test_show_with_changes_flag(self, populated_ledger: Path) -> None:
        """Test show command with --changes flag."""
        result = runner.invoke(app, ["show", "cub-test-1", "--changes"])
        assert result.exit_code == 0
        # Should show file changes
        assert "src/test.py" in result.output or "Files Changed" in result.output

    def test_show_with_history_flag(self, populated_ledger: Path) -> None:
        """Test show command with --history flag."""
        result = runner.invoke(app, ["show", "cub-test-1", "--history"])
        assert result.exit_code == 0
        # Should show state history
        assert "dev_complete" in result.output.lower() or "history" in result.output.lower()

    def test_show_with_attempt_flag(self, populated_ledger: Path) -> None:
        """Test show command with --attempt flag."""
        result = runner.invoke(app, ["show", "cub-test-1", "--attempt", "1"])
        assert result.exit_code == 0
        # Should show attempt details
        assert "haiku" in result.output.lower() or "attempt" in result.output.lower()

    def test_show_attempt_not_found(self, populated_ledger: Path) -> None:
        """Test show command with non-existent attempt."""
        result = runner.invoke(app, ["show", "cub-test-1", "--attempt", "99"])
        # Should handle gracefully
        assert "99" in result.output or result.exit_code != 0


class TestUpdateCommand:
    """Tests for the 'ledger update' command."""

    def test_update_task_not_found(self, populated_ledger: Path) -> None:
        """Test update command with non-existent task."""
        result = runner.invoke(app, ["update", "nonexistent", "--stage", "validated"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_update_invalid_stage(self, populated_ledger: Path) -> None:
        """Test update command with invalid stage."""
        result = runner.invoke(app, ["update", "cub-test-1", "--stage", "invalid"])
        assert result.exit_code == 1
        assert "invalid" in result.output.lower()

    def test_update_valid_stage(self, populated_ledger: Path) -> None:
        """Test update command with valid stage."""
        result = runner.invoke(app, ["update", "cub-test-1", "--stage", "needs_review"])
        assert result.exit_code == 0
        assert "needs_review" in result.output.lower() or "updated" in result.output.lower()

    def test_update_with_reason(self, populated_ledger: Path) -> None:
        """Test update command with --reason flag."""
        result = runner.invoke(
            app,
            ["update", "cub-test-1", "--stage", "validated", "--reason", "Tests passed"],
        )
        assert result.exit_code == 0
        assert "validated" in result.output.lower() or "updated" in result.output.lower()

    def test_update_all_valid_stages(self, populated_ledger: Path) -> None:
        """Test that all valid stages can be set."""
        valid_stages = ["dev_complete", "needs_review", "validated", "released"]
        for stage in valid_stages:
            result = runner.invoke(app, ["update", "cub-test-1", "--stage", stage])
            assert result.exit_code == 0, f"Failed to set stage '{stage}'"


class TestExportCommand:
    """Tests for the 'ledger export' command."""

    def test_export_json_stdout(self, populated_ledger: Path) -> None:
        """Test export command with JSON format to stdout."""
        result = runner.invoke(app, ["export", "--format", "json"])
        assert result.exit_code == 0
        # Should be valid JSON array
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["id"] == "cub-test-1"

    def test_export_csv_stdout(self, populated_ledger: Path) -> None:
        """Test export command with CSV format to stdout."""
        result = runner.invoke(app, ["export", "--format", "csv"])
        assert result.exit_code == 0
        # Should have CSV headers
        lines = result.output.strip().split("\n")
        assert len(lines) >= 2  # Header + at least one data row
        assert "id" in lines[0]
        assert "cub-test-1" in lines[1]

    def test_export_to_file(self, populated_ledger: Path, tmp_path: Path) -> None:
        """Test export command with --output flag."""
        output_file = tmp_path / "export.json"
        result = runner.invoke(
            app, ["export", "--format", "json", "--output", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert len(data) >= 1

    def test_export_invalid_format(self, populated_ledger: Path) -> None:
        """Test export command with invalid format."""
        result = runner.invoke(app, ["export", "--format", "xml"])
        assert result.exit_code == 1
        assert "invalid" in result.output.lower()

    def test_export_with_epic_filter(
        self, ledger_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test export command with --epic filter."""
        # Create entries with different epics
        writer = LedgerWriter(ledger_dir)
        now = datetime.now(timezone.utc)

        # Need to set both lineage.epic_id and epic_id for index compatibility
        entry1 = LedgerEntry(
            id="task-epic-a",
            title="Task in Epic A",
            lineage=Lineage(epic_id="epic-a"),
            epic_id="epic-a",  # Legacy field used by index
            completed_at=now,
        )
        entry2 = LedgerEntry(
            id="task-epic-b",
            title="Task in Epic B",
            lineage=Lineage(epic_id="epic-b"),
            epic_id="epic-b",  # Legacy field used by index
            completed_at=now,
        )
        writer.create_entry(entry1)
        writer.create_entry(entry2)

        from cub.core.services.ledger import LedgerService
        monkeypatch.setattr("cub.cli.ledger._get_ledger_service", lambda: LedgerService(ledger_dir))

        result = runner.invoke(app, ["export", "--format", "json", "--epic", "epic-a"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["id"] == "task-epic-a"


class TestGcCommand:
    """Tests for the 'ledger gc' command."""

    def test_gc_empty_ledger(self, ledger_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test gc command with no attempt files."""
        from cub.core.ledger.reader import LedgerReader
        monkeypatch.setattr("cub.cli.ledger._get_ledger_reader", lambda: LedgerReader(ledger_dir))

        result = runner.invoke(app, ["gc"])
        assert result.exit_code == 0
        # Should report nothing to delete or no ledger
        assert "no" in result.output.lower() or "warning" in result.output.lower()

    def test_gc_with_attempt_files(
        self, populated_ledger: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test gc command with attempt files."""
        # Create attempt files
        attempts_dir = populated_ledger / "by-task" / "cub-test-1" / "attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)

        # Create 10 attempt files
        for i in range(1, 11):
            prompt_file = attempts_dir / f"{i:03d}-prompt.md"
            log_file = attempts_dir / f"{i:03d}-harness.log"
            prompt_file.write_text(f"Prompt {i}")
            log_file.write_text(f"Log {i}")

        result = runner.invoke(app, ["gc", "--keep-latest", "5"])
        assert result.exit_code == 0
        # Should report files that would be deleted
        assert "dry run" in result.output.lower() or "would be deleted" in result.output.lower()

    def test_gc_keep_latest_default(self, populated_ledger: Path) -> None:
        """Test gc command uses default keep-latest of 5."""
        result = runner.invoke(app, ["gc"])
        # Just verify it runs successfully
        assert result.exit_code == 0

    def test_gc_custom_keep_latest(self, populated_ledger: Path) -> None:
        """Test gc command with custom --keep-latest value."""
        result = runner.invoke(app, ["gc", "-k", "3"])
        assert result.exit_code == 0


class TestNoLedgerScenarios:
    """Tests for commands when no ledger exists."""

    def test_show_no_ledger(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test show command when no ledger exists."""
        empty_ledger = tmp_path / ".cub" / "ledger"
        empty_ledger.mkdir(parents=True)

        monkeypatch.setattr("cub.cli.ledger._get_ledger_service", lambda: None)

        result = runner.invoke(app, ["show", "any-task"])
        # Should handle gracefully
        assert "warning" in result.output.lower() or "not found" in result.output.lower()

    def test_update_no_ledger(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test update command when no ledger exists."""
        empty_ledger = tmp_path / ".cub" / "ledger"
        # Don't create directory

        from cub.core.ledger.writer import LedgerWriter
        monkeypatch.setattr("cub.cli.ledger._get_ledger_writer", lambda: LedgerWriter(empty_ledger))

        result = runner.invoke(app, ["update", "any-task", "--stage", "validated"])
        assert result.exit_code == 1

    def test_export_no_ledger(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test export command when no ledger exists."""
        monkeypatch.setattr("cub.cli.ledger._get_ledger_service", lambda: None)

        result = runner.invoke(app, ["export"])
        # Should handle gracefully
        assert "warning" in result.output.lower() or result.exit_code in [0, 1]
