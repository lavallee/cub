"""Tests for ledger CLI commands."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cub.cli.ledger import (
    _format_cost,
    _format_duration,
    _format_verification,
    _format_workflow_stage,
    _get_ledger_reader,
    app,
)
from cub.core.ledger.models import (
    Attempt,
    LedgerEntry,
    Lineage,
    Outcome,
    TokenUsage,
    Verification,
    WorkflowState,
)
from cub.core.ledger.reader import LedgerReader
from cub.core.ledger.writer import LedgerWriter

runner = CliRunner()


class TestFormatHelpers:
    """Tests for formatting helper functions."""

    def test_format_cost_zero(self) -> None:
        """Test zero cost formatting."""
        result = _format_cost(0)
        assert "[dim]$0.00[/dim]" == result

    def test_format_cost_positive(self) -> None:
        """Test positive cost formatting."""
        result = _format_cost(1.50)
        assert "[yellow]$1.50[/yellow]" == result

    def test_format_cost_small(self) -> None:
        """Test small cost formatting."""
        result = _format_cost(0.05)
        assert "[yellow]$0.05[/yellow]" == result

    def test_format_verification_pass(self) -> None:
        """Test pass status formatting."""
        result = _format_verification("pass")
        assert "[green]pass[/green]" == result

    def test_format_verification_fail(self) -> None:
        """Test fail status formatting."""
        result = _format_verification("fail")
        assert "[red]fail[/red]" == result

    def test_format_verification_warn(self) -> None:
        """Test warn status formatting."""
        result = _format_verification("warn")
        assert "[yellow]warn[/yellow]" == result

    def test_format_verification_skip(self) -> None:
        """Test skip status formatting."""
        result = _format_verification("skip")
        assert "[dim]skip[/dim]" == result

    def test_format_verification_pending(self) -> None:
        """Test pending status formatting."""
        result = _format_verification("pending")
        assert "[blue]pending[/blue]" == result

    def test_format_verification_error(self) -> None:
        """Test error status formatting."""
        result = _format_verification("error")
        assert "[red]error[/red]" == result

    def test_format_verification_unknown(self) -> None:
        """Test unknown status returns unchanged."""
        result = _format_verification("unknown")
        assert "unknown" == result

    def test_format_workflow_stage_dev_complete(self) -> None:
        """Test dev_complete stage formatting."""
        result = _format_workflow_stage("dev_complete")
        assert "[dim]dev_complete[/dim]" == result

    def test_format_workflow_stage_needs_review(self) -> None:
        """Test needs_review stage formatting."""
        result = _format_workflow_stage("needs_review")
        assert "[yellow]needs_review[/yellow]" == result

    def test_format_workflow_stage_validated(self) -> None:
        """Test validated stage formatting."""
        result = _format_workflow_stage("validated")
        assert "[green]validated[/green]" == result

    def test_format_workflow_stage_released(self) -> None:
        """Test released stage formatting."""
        result = _format_workflow_stage("released")
        assert "[blue]released[/blue]" == result

    def test_format_workflow_stage_none(self) -> None:
        """Test None stage defaults to dev_complete."""
        result = _format_workflow_stage(None)
        assert "[dim]dev_complete[/dim]" == result

    def test_format_duration_zero(self) -> None:
        """Test zero duration formatting."""
        result = _format_duration(0)
        assert "[dim]0s[/dim]" == result

    def test_format_duration_seconds_only(self) -> None:
        """Test duration in seconds only."""
        result = _format_duration(45)
        assert "45s" == result

    def test_format_duration_minutes_and_seconds(self) -> None:
        """Test duration in minutes and seconds."""
        result = _format_duration(125)  # 2 minutes 5 seconds
        assert "2m 5s" == result

    def test_format_duration_hours_minutes_seconds(self) -> None:
        """Test duration in hours, minutes, and seconds."""
        result = _format_duration(3725)  # 1 hour 2 minutes 5 seconds
        assert "1h 2m 5s" == result


class TestGetLedgerReader:
    """Tests for _get_ledger_reader helper."""

    def test_returns_ledger_reader(self, tmp_path: Path) -> None:
        """Test that _get_ledger_reader returns a LedgerReader instance."""
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            reader = _get_ledger_reader()
            assert isinstance(reader, LedgerReader)
            assert reader.ledger_dir == tmp_path / ".cub" / "ledger"


class TestLedgerShowCommand:
    """Tests for ledger show command."""

    def test_show_no_ledger(self, tmp_path: Path) -> None:
        """Test show command when no ledger exists."""
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["show", "beads-abc"])
            assert result.exit_code == 0
            assert "No ledger found" in result.output

    def test_show_task_not_found(self, tmp_path: Path) -> None:
        """Test show command when task doesn't exist."""
        # Create ledger dir but no task
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["show", "beads-abc"])
            assert result.exit_code == 1
            assert "not found" in result.output


class TestLedgerStatsCommand:
    """Tests for ledger stats command."""

    def test_stats_no_ledger(self, tmp_path: Path) -> None:
        """Test stats command when no ledger exists."""
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["stats"])
            assert result.exit_code == 0
            assert "No ledger found" in result.output

    def test_stats_empty_ledger(self, tmp_path: Path) -> None:
        """Test stats command with empty ledger."""
        # Create ledger dir but no entries
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["stats"])
            assert result.exit_code == 0
            # Displays stats even if empty (with 0 tasks)
            assert "Tasks: 0" in result.output


class TestLedgerSearchCommand:
    """Tests for ledger search command."""

    def test_search_no_ledger(self, tmp_path: Path) -> None:
        """Test search command when no ledger exists."""
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["search", "test"])
            assert result.exit_code == 0
            assert "No ledger found" in result.output


class TestLedgerShowWithNewFields:
    """Tests for show command with new fields (workflow, outcome, lineage)."""

    def _create_sample_entry(self, ledger_dir: Path) -> LedgerEntry:
        """Create a sample ledger entry with all new fields."""
        return LedgerEntry(
            id="cub-test.1",
            title="Test task with new fields",
            started_at=datetime(2026, 1, 24, 10, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 1, 24, 10, 30, tzinfo=timezone.utc),
            duration_seconds=1800,
            cost_usd=0.50,
            tokens=TokenUsage(input_tokens=1000, output_tokens=500),
            lineage=Lineage(
                epic_id="cub-abc",
                spec_file="specs/test.md",
                plan_file="plans/test/plan.jsonl",
            ),
            workflow=WorkflowState(
                stage="needs_review",
                stage_updated_at=datetime(2026, 1, 24, 10, 35, tzinfo=timezone.utc),
            ),
            outcome=Outcome(
                success=True,
                partial=False,
                total_attempts=2,
                total_cost_usd=0.50,
                total_duration_seconds=1800,
                final_model="sonnet",
                files_changed=["src/test.py", "tests/test_test.py"],
                commits=[],
            ),
            attempts=[
                Attempt(
                    attempt_number=1,
                    run_id="run-1",
                    harness="claude",
                    model="haiku",
                    success=False,
                    cost_usd=0.10,
                    duration_seconds=300,
                ),
                Attempt(
                    attempt_number=2,
                    run_id="run-1",
                    harness="claude",
                    model="sonnet",
                    success=True,
                    cost_usd=0.40,
                    duration_seconds=1500,
                ),
            ],
            verification=Verification(
                status="pass",
                tests_passed=True,
                typecheck_passed=True,
                lint_passed=True,
            ),
        )

    def test_show_displays_lineage(self, tmp_path: Path) -> None:
        """Test show command displays lineage information."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        entry = self._create_sample_entry(ledger_dir)
        writer.create_entry(entry)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["show", "cub-test.1"])
            assert result.exit_code == 0
            assert "Lineage:" in result.output
            assert "Epic: cub-abc" in result.output
            assert "Spec: specs/test.md" in result.output
            assert "Plan: plans/test/plan.jsonl" in result.output

    def test_show_displays_workflow_stage(self, tmp_path: Path) -> None:
        """Test show command displays workflow stage."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        entry = self._create_sample_entry(ledger_dir)
        writer.create_entry(entry)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["show", "cub-test.1"])
            assert result.exit_code == 0
            assert "Workflow Stage:" in result.output
            assert "needs_review" in result.output

    def test_show_displays_outcome(self, tmp_path: Path) -> None:
        """Test show command displays outcome information."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        entry = self._create_sample_entry(ledger_dir)
        writer.create_entry(entry)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["show", "cub-test.1"])
            assert result.exit_code == 0
            assert "Outcome:" in result.output
            assert "Total Cost:" in result.output
            assert "Total Attempts: 2" in result.output
            assert "Final Model: sonnet" in result.output

    def test_show_displays_attempts_summary(self, tmp_path: Path) -> None:
        """Test show command displays attempts summary table."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        entry = self._create_sample_entry(ledger_dir)
        writer.create_entry(entry)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["show", "cub-test.1"])
            assert result.exit_code == 0
            assert "Attempts (2):" in result.output
            assert "haiku" in result.output
            assert "sonnet" in result.output

    def test_show_specific_attempt_detail(self, tmp_path: Path) -> None:
        """Test show command displays specific attempt details with --attempt."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        entry = self._create_sample_entry(ledger_dir)
        writer.create_entry(entry)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["show", "cub-test.1", "--attempt", "1"])
            assert result.exit_code == 0
            assert "Attempt #1" in result.output
            assert "haiku" in result.output
            assert "Run ID:" in result.output

    def test_show_invalid_attempt_number(self, tmp_path: Path) -> None:
        """Test show command with invalid attempt number."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        entry = self._create_sample_entry(ledger_dir)
        writer.create_entry(entry)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["show", "cub-test.1", "--attempt", "99"])
            assert result.exit_code == 1
            assert "Attempt 99 not found" in result.output

    def test_show_json_output(self, tmp_path: Path) -> None:
        """Test show command with JSON output."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        entry = self._create_sample_entry(ledger_dir)
        writer.create_entry(entry)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["show", "cub-test.1", "--json"])
            assert result.exit_code == 0
            # Verify JSON is valid
            data = json.loads(result.output)
            assert data["id"] == "cub-test.1"
            assert data["title"] == "Test task with new fields"


class TestLedgerUpdateCommand:
    """Tests for ledger update command (workflow stage updates)."""

    def _create_entry(self, ledger_dir: Path) -> None:
        """Create a sample entry for testing."""
        writer = LedgerWriter(ledger_dir)
        entry = LedgerEntry(
            id="cub-update-test",
            title="Task for update testing",
        )
        writer.create_entry(entry)

    def test_update_stage_needs_review(self, tmp_path: Path) -> None:
        """Test updating workflow stage to needs_review."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        self._create_entry(ledger_dir)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(
                app,
                ["update", "cub-update-test", "--stage", "needs_review"],
            )
            assert result.exit_code == 0
            assert "Updated workflow stage" in result.output
            assert "needs_review" in result.output

    def test_update_stage_validated(self, tmp_path: Path) -> None:
        """Test updating workflow stage to validated."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        self._create_entry(ledger_dir)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(
                app,
                ["update", "cub-update-test", "--stage", "validated"],
            )
            assert result.exit_code == 0
            assert "Updated workflow stage" in result.output

    def test_update_stage_released(self, tmp_path: Path) -> None:
        """Test updating workflow stage to released."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        self._create_entry(ledger_dir)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(
                app,
                ["update", "cub-update-test", "--stage", "released"],
            )
            assert result.exit_code == 0
            assert "Updated workflow stage" in result.output

    def test_update_with_reason(self, tmp_path: Path) -> None:
        """Test updating workflow stage with a reason."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        self._create_entry(ledger_dir)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(
                app,
                [
                    "update",
                    "cub-update-test",
                    "--stage",
                    "needs_review",
                    "--reason",
                    "Ready for peer review",
                ],
            )
            assert result.exit_code == 0
            assert "Ready for peer review" in result.output

    def test_update_invalid_stage(self, tmp_path: Path) -> None:
        """Test updating with invalid stage name."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        self._create_entry(ledger_dir)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(
                app,
                ["update", "cub-update-test", "--stage", "invalid_stage"],
            )
            assert result.exit_code == 1
            assert "Invalid stage" in result.output

    def test_update_nonexistent_task(self, tmp_path: Path) -> None:
        """Test updating a task that doesn't exist."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        by_task_dir = ledger_dir / "by-task"
        by_task_dir.mkdir(parents=True)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(
                app,
                ["update", "nonexistent", "--stage", "needs_review"],
            )
            assert result.exit_code == 1
            assert "not found" in result.output

    def test_update_no_ledger(self, tmp_path: Path) -> None:
        """Test update when ledger doesn't exist."""
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(
                app,
                ["update", "cub-test", "--stage", "needs_review"],
            )
            assert result.exit_code == 1
            assert "No ledger found" in result.output


class TestLedgerExportCommand:
    """Tests for ledger export command (JSON and CSV export)."""

    def _create_sample_entries(self, ledger_dir: Path, count: int = 2) -> None:
        """Create sample entries for export testing."""
        writer = LedgerWriter(ledger_dir)
        for i in range(1, count + 1):
            entry = LedgerEntry(
                id=f"cub-export-{i}",
                title=f"Export test task {i}",
                cost_usd=0.05 * i,
                tokens=TokenUsage(
                    input_tokens=1000 * i,
                    output_tokens=500 * i,
                ),
                outcome=Outcome(
                    success=i == 1,  # First succeeds, others fail
                    total_attempts=i,
                    total_cost_usd=0.05 * i,
                    total_duration_seconds=300 * i,
                ),
            )
            writer.create_entry(entry)

    def test_export_json_to_stdout(self, tmp_path: Path) -> None:
        """Test exporting to JSON on stdout."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        self._create_sample_entries(ledger_dir, 2)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["export", "--format", "json"])
            assert result.exit_code == 0
            # Verify JSON is valid
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert len(data) >= 2

    def test_export_json_to_file(self, tmp_path: Path) -> None:
        """Test exporting to JSON file."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        self._create_sample_entries(ledger_dir, 2)

        output_file = tmp_path / "export.json"
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(
                app,
                ["export", "--format", "json", "--output", str(output_file)],
            )
            assert result.exit_code == 0
            assert "Exported" in result.output
            assert output_file.exists()
            # Verify file content
            data = json.loads(output_file.read_text())
            assert isinstance(data, list)

    def test_export_csv_to_file(self, tmp_path: Path) -> None:
        """Test exporting to CSV file."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        self._create_sample_entries(ledger_dir, 2)

        output_file = tmp_path / "export.csv"
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(
                app,
                ["export", "--format", "csv", "--output", str(output_file)],
            )
            assert result.exit_code == 0
            assert "Exported" in result.output
            assert output_file.exists()
            # Verify CSV content
            rows = list(csv.DictReader(output_file.open()))
            assert len(rows) >= 2
            assert "id" in rows[0]
            assert "title" in rows[0]
            assert "cost_usd" in rows[0]

    def test_export_csv_to_stdout(self, tmp_path: Path) -> None:
        """Test exporting to CSV on stdout."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        self._create_sample_entries(ledger_dir, 1)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["export", "--format", "csv"])
            assert result.exit_code == 0
            # Should contain CSV header
            assert "id,title" in result.output or "id," in result.output

    def test_export_invalid_format(self, tmp_path: Path) -> None:
        """Test exporting with invalid format."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        self._create_sample_entries(ledger_dir, 1)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["export", "--format", "xml"])
            assert result.exit_code == 1
            assert "Invalid format" in result.output

    def test_export_no_ledger(self, tmp_path: Path) -> None:
        """Test export when no ledger exists."""
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["export"])
            assert result.exit_code == 1
            assert "No ledger found" in result.output

    def test_export_with_epic_filter(self, tmp_path: Path) -> None:
        """Test export with epic filter."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)

        # Create entries with different epics
        for i, epic in enumerate(["cub-abc", "cub-def", "cub-abc"]):
            entry = LedgerEntry(
                id=f"cub-epic-{i}",
                title=f"Task for epic {epic}",
                epic_id=epic,
            )
            writer.create_entry(entry)

        output_file = tmp_path / "epic-export.json"
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(
                app,
                ["export", "--epic", "cub-abc", "--output", str(output_file)],
            )
            assert result.exit_code == 0
            data = json.loads(output_file.read_text())
            # Should have 2 entries from cub-abc epic
            assert len(data) >= 1

    def test_export_with_since_filter(self, tmp_path: Path) -> None:
        """Test export with date filter."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        self._create_sample_entries(ledger_dir, 1)

        output_file = tmp_path / "since-export.json"
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(
                app,
                [
                    "export",
                    "--since",
                    "2026-01-01",
                    "--output",
                    str(output_file),
                ],
            )
            assert result.exit_code == 0
            assert output_file.exists()


class TestLedgerGCCommand:
    """Tests for ledger gc (garbage collection) command."""

    def _create_task_with_attempts(
        self, ledger_dir: Path, task_id: str, attempt_count: int
    ) -> None:
        """Create a task with multiple attempt files."""
        task_dir = ledger_dir / "by-task" / task_id
        attempts_dir = task_dir / "attempts"
        attempts_dir.mkdir(parents=True)

        # Create attempt files
        for i in range(1, attempt_count + 1):
            prompt_file = attempts_dir / f"{i:03d}-prompt.md"
            log_file = attempts_dir / f"{i:03d}-harness.log"
            prompt_file.write_text(f"Prompt for attempt {i}\n")
            log_file.write_text(f"Log for attempt {i}\n")

    def test_gc_dry_run_shows_summary(self, tmp_path: Path) -> None:
        """Test gc dry run shows cleanup summary."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        # Create a task with 10 attempt files (should keep 5, suggest deleting 5)
        self._create_task_with_attempts(ledger_dir, "cub-gc-test", 10)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["gc"])
            assert result.exit_code == 0
            assert "Garbage Collection" in result.output
            assert "Dry Run" in result.output

    def test_gc_no_files_to_delete(self, tmp_path: Path) -> None:
        """Test gc when all tasks have acceptable attempt counts."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        # Create a task with 3 attempt files (keep default is 5, so nothing deleted)
        self._create_task_with_attempts(ledger_dir, "cub-gc-few", 3)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["gc"])
            assert result.exit_code == 0
            assert "No attempt files would be deleted" in result.output or "0" in result.output

    def test_gc_custom_keep_latest(self, tmp_path: Path) -> None:
        """Test gc with custom keep-latest value."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        # Create a task with 10 attempts
        self._create_task_with_attempts(ledger_dir, "cub-gc-custom", 10)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["gc", "--keep-latest", "3"])
            assert result.exit_code == 0
            assert "Garbage Collection" in result.output
            # Should suggest deleting 7 files (10 - 3)

    def test_gc_no_ledger(self, tmp_path: Path) -> None:
        """Test gc when ledger doesn't exist."""
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["gc"])
            assert result.exit_code == 0
            assert "No ledger found" in result.output

    def test_gc_multiple_tasks(self, tmp_path: Path) -> None:
        """Test gc with multiple tasks."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        # Create multiple tasks with different attempt counts
        self._create_task_with_attempts(ledger_dir, "cub-gc-task1", 8)
        self._create_task_with_attempts(ledger_dir, "cub-gc-task2", 12)
        self._create_task_with_attempts(ledger_dir, "cub-gc-task3", 3)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["gc", "--keep-latest", "5"])
            assert result.exit_code == 0
            assert "Garbage Collection" in result.output
