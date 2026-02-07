"""Tests for core/verify/service.py - data integrity verification."""

import json
from pathlib import Path

import pytest

from cub.core.verify.service import (
    Issue,
    IssueSeverity,
    VerifyResult,
    VerifyService,
)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestIssue:
    def test_str_formatting(self) -> None:
        issue = Issue(
            severity=IssueSeverity.ERROR,
            category="ledger",
            message="Missing field",
            location="index.jsonl:5",
        )
        s = str(issue)
        assert "[ERROR]" in s
        assert "(ledger)" in s
        assert "Missing field" in s
        assert "at index.jsonl:5" in s

    def test_str_without_location(self) -> None:
        issue = Issue(severity=IssueSeverity.WARNING, category="ids", message="bad id")
        s = str(issue)
        assert "[WARNING]" in s
        assert "at" not in s


class TestVerifyResult:
    def test_empty_result(self) -> None:
        result = VerifyResult()
        assert not result.has_errors
        assert not result.has_warnings
        assert result.error_count == 0
        assert result.warning_count == 0
        assert result.info_count == 0

    def test_counts(self) -> None:
        result = VerifyResult(
            issues=[
                Issue(severity=IssueSeverity.ERROR, category="a", message="e1"),
                Issue(severity=IssueSeverity.ERROR, category="a", message="e2"),
                Issue(severity=IssueSeverity.WARNING, category="b", message="w1"),
                Issue(severity=IssueSeverity.INFO, category="c", message="i1"),
            ]
        )
        assert result.has_errors
        assert result.has_warnings
        assert result.error_count == 2
        assert result.warning_count == 1
        assert result.info_count == 1


# ---------------------------------------------------------------------------
# Ledger checks
# ---------------------------------------------------------------------------


class TestLedgerConsistency:
    def test_missing_ledger_dir(self, tmp_path: Path) -> None:
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ids=False, check_counters=False)
        assert result.has_errors
        assert any("Ledger directory does not exist" in i.message for i in result.issues)

    def test_missing_index_file(self, tmp_path: Path) -> None:
        (tmp_path / ".cub" / "ledger").mkdir(parents=True)
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ids=False, check_counters=False)
        assert result.has_warnings
        assert any("index file does not exist" in i.message for i in result.issues)

    def test_valid_index_file(self, tmp_path: Path) -> None:
        ledger = tmp_path / ".cub" / "ledger"
        ledger.mkdir(parents=True)
        index = ledger / "index.jsonl"
        index.write_text(json.dumps({"id": "t1", "title": "Task 1"}) + "\n")
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ids=False, check_counters=False)
        assert not result.has_errors
        assert result.files_checked >= 1

    def test_corrupted_index_line(self, tmp_path: Path) -> None:
        ledger = tmp_path / ".cub" / "ledger"
        ledger.mkdir(parents=True)
        index = ledger / "index.jsonl"
        index.write_text('{"id": "t1"}\n{bad json\n{"id": "t2"}\n')
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ids=False, check_counters=False)
        assert result.has_errors
        assert any("Invalid JSON in index at line 2" in i.message for i in result.issues)

    def test_blank_lines_in_index_ignored(self, tmp_path: Path) -> None:
        ledger = tmp_path / ".cub" / "ledger"
        ledger.mkdir(parents=True)
        index = ledger / "index.jsonl"
        index.write_text('{"id": "t1"}\n\n{"id": "t2"}\n')
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ids=False, check_counters=False)
        assert not result.has_errors

    def test_task_entry_missing_fields(self, tmp_path: Path) -> None:
        ledger = tmp_path / ".cub" / "ledger"
        by_task = ledger / "by-task"
        by_task.mkdir(parents=True)
        (by_task / "t1.json").write_text(json.dumps({"foo": "bar"}))
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ids=False, check_counters=False)
        assert result.has_errors
        assert any("Missing required field" in i.message for i in result.issues)

    def test_task_entry_filename_mismatch(self, tmp_path: Path) -> None:
        ledger = tmp_path / ".cub" / "ledger"
        by_task = ledger / "by-task"
        by_task.mkdir(parents=True)
        (by_task / "wrong-name.json").write_text(
            json.dumps({"id": "cub-001-1", "title": "Task"})
        )
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ids=False, check_counters=False)
        assert result.has_warnings
        assert any("doesn't match filename" in i.message for i in result.issues)

    def test_task_entry_filename_mismatch_auto_fix(self, tmp_path: Path) -> None:
        ledger = tmp_path / ".cub" / "ledger"
        by_task = ledger / "by-task"
        by_task.mkdir(parents=True)
        (by_task / "wrong.json").write_text(
            json.dumps({"id": "cub-001-1", "title": "Task"})
        )
        svc = VerifyService(tmp_path)
        result = svc.verify(fix=True, check_ids=False, check_counters=False)
        assert result.auto_fixed >= 1
        assert (by_task / "cub-001-1.json").exists()
        assert not (by_task / "wrong.json").exists()

    def test_corrupted_task_entry(self, tmp_path: Path) -> None:
        ledger = tmp_path / ".cub" / "ledger"
        by_task = ledger / "by-task"
        by_task.mkdir(parents=True)
        (by_task / "t1.json").write_text("{bad json")
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ids=False, check_counters=False)
        assert result.has_errors
        assert any("Invalid JSON in task file" in i.message for i in result.issues)

    def test_epic_missing_entry_json(self, tmp_path: Path) -> None:
        ledger = tmp_path / ".cub" / "ledger"
        epic_dir = ledger / "by-epic" / "my-epic"
        epic_dir.mkdir(parents=True)
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ids=False, check_counters=False)
        assert result.has_warnings
        assert any("missing entry.json" in i.message for i in result.issues)

    def test_epic_id_directory_mismatch(self, tmp_path: Path) -> None:
        ledger = tmp_path / ".cub" / "ledger"
        epic_dir = ledger / "by-epic" / "wrong-name"
        epic_dir.mkdir(parents=True)
        (epic_dir / "entry.json").write_text(
            json.dumps({"epic": {"id": "actual-epic"}})
        )
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ids=False, check_counters=False)
        assert result.has_warnings
        assert any("doesn't match directory" in i.message for i in result.issues)

    def test_corrupted_epic_entry(self, tmp_path: Path) -> None:
        ledger = tmp_path / ".cub" / "ledger"
        epic_dir = ledger / "by-epic" / "my-epic"
        epic_dir.mkdir(parents=True)
        (epic_dir / "entry.json").write_text("{broken")
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ids=False, check_counters=False)
        assert result.has_errors


# ---------------------------------------------------------------------------
# ID integrity checks
# ---------------------------------------------------------------------------


class TestIdIntegrity:
    def test_no_tasks_file(self, tmp_path: Path) -> None:
        (tmp_path / ".cub" / "ledger").mkdir(parents=True)
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_counters=False)
        assert not result.has_errors

    def test_valid_task_ids(self, tmp_path: Path) -> None:
        (tmp_path / ".cub" / "ledger").mkdir(parents=True)
        tasks = tmp_path / ".cub" / "tasks.jsonl"
        tasks.write_text(
            json.dumps({"id": "cub-001-1", "title": "T1"}) + "\n"
            + json.dumps({"id": "cub-001-2", "title": "T2"}) + "\n"
        )
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_counters=False)
        assert not result.has_errors

    def test_missing_task_id(self, tmp_path: Path) -> None:
        (tmp_path / ".cub" / "ledger").mkdir(parents=True)
        tasks = tmp_path / ".cub" / "tasks.jsonl"
        tasks.write_text(json.dumps({"title": "No ID"}) + "\n")
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_counters=False)
        assert result.has_errors
        assert any("has no ID" in i.message for i in result.issues)

    def test_duplicate_task_id(self, tmp_path: Path) -> None:
        (tmp_path / ".cub" / "ledger").mkdir(parents=True)
        tasks = tmp_path / ".cub" / "tasks.jsonl"
        tasks.write_text(
            json.dumps({"id": "cub-001-1", "title": "T1"}) + "\n"
            + json.dumps({"id": "cub-001-1", "title": "T2"}) + "\n"
        )
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_counters=False)
        assert result.has_errors
        assert any("Duplicate task ID" in i.message for i in result.issues)

    def test_invalid_task_id_format(self, tmp_path: Path) -> None:
        (tmp_path / ".cub" / "ledger").mkdir(parents=True)
        tasks = tmp_path / ".cub" / "tasks.jsonl"
        tasks.write_text(json.dumps({"id": "bad", "title": "T1"}) + "\n")
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_counters=False)
        assert result.has_warnings
        assert any("unexpected format" in i.message for i in result.issues)

    def test_corrupted_tasks_jsonl(self, tmp_path: Path) -> None:
        (tmp_path / ".cub" / "ledger").mkdir(parents=True)
        tasks = tmp_path / ".cub" / "tasks.jsonl"
        tasks.write_text("{bad json\n")
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_counters=False)
        assert result.has_errors
        assert any("Invalid JSON at line" in i.message for i in result.issues)

    def test_cross_reference_ledger_task_not_in_tasks(self, tmp_path: Path) -> None:
        cub_dir = tmp_path / ".cub"
        ledger = cub_dir / "ledger"
        by_task = ledger / "by-task"
        by_task.mkdir(parents=True)
        (by_task / "cub-archived-1.json").write_text(
            json.dumps({"id": "cub-archived-1", "title": "Archived"})
        )
        tasks = cub_dir / "tasks.jsonl"
        tasks.write_text(json.dumps({"id": "cub-001-1", "title": "Active"}) + "\n")
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_counters=False)
        assert any("exists in ledger but not in tasks" in i.message for i in result.issues)


# ---------------------------------------------------------------------------
# Counter sync checks
# ---------------------------------------------------------------------------


class TestCounterSync:
    def test_missing_counters_file(self, tmp_path: Path) -> None:
        (tmp_path / ".cub" / "ledger").mkdir(parents=True)
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_ids=False)
        assert result.has_warnings
        assert any("Counters file does not exist" in i.message for i in result.issues)

    def test_missing_counters_auto_fix(self, tmp_path: Path) -> None:
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        (cub_dir / "ledger").mkdir()
        svc = VerifyService(tmp_path)
        result = svc.verify(fix=True, check_ledger=False, check_ids=False)
        assert result.auto_fixed >= 1
        assert (cub_dir / "counters.json").exists()
        data = json.loads((cub_dir / "counters.json").read_text())
        assert data["spec_number"] == 1
        assert data["standalone_task_number"] == 1

    def test_valid_counters(self, tmp_path: Path) -> None:
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        (cub_dir / "ledger").mkdir()
        (cub_dir / "counters.json").write_text(
            json.dumps({
                "spec_number": 5,
                "standalone_task_number": 3,
                "updated_at": "2026-01-01T00:00:00Z",
            })
        )
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_ids=False)
        assert not result.has_errors

    def test_missing_counter_field(self, tmp_path: Path) -> None:
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        (cub_dir / "ledger").mkdir()
        (cub_dir / "counters.json").write_text(json.dumps({"spec_number": 1}))
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_ids=False)
        assert result.has_warnings
        assert any("Missing counter field" in i.message for i in result.issues)

    def test_missing_counter_field_auto_fix(self, tmp_path: Path) -> None:
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        (cub_dir / "ledger").mkdir()
        (cub_dir / "counters.json").write_text(json.dumps({"spec_number": 1}))
        svc = VerifyService(tmp_path)
        result = svc.verify(fix=True, check_ledger=False, check_ids=False)
        assert result.auto_fixed >= 1
        data = json.loads((cub_dir / "counters.json").read_text())
        assert "standalone_task_number" in data
        assert "updated_at" in data

    def test_invalid_counter_value(self, tmp_path: Path) -> None:
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        (cub_dir / "ledger").mkdir()
        (cub_dir / "counters.json").write_text(
            json.dumps({
                "spec_number": -1,
                "standalone_task_number": 0,
                "updated_at": "2026-01-01T00:00:00Z",
            })
        )
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_ids=False)
        assert result.has_errors
        assert sum(1 for i in result.issues if "Invalid counter value" in i.message) == 2

    def test_corrupted_counters_file(self, tmp_path: Path) -> None:
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        (cub_dir / "ledger").mkdir()
        (cub_dir / "counters.json").write_text("{bad json")
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_ids=False)
        assert result.has_errors
        assert any("Invalid JSON in counters" in i.message for i in result.issues)

    def test_counter_behind_actual_usage(self, tmp_path: Path) -> None:
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        (cub_dir / "ledger").mkdir()
        (cub_dir / "counters.json").write_text(
            json.dumps({
                "spec_number": 3,
                "standalone_task_number": 1,
                "updated_at": "2026-01-01T00:00:00Z",
            })
        )
        (cub_dir / "tasks.jsonl").write_text(
            json.dumps({"id": "cub-005a-1", "title": "Task with spec 5"}) + "\n"
        )
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_ids=False)
        assert result.has_warnings
        assert any("Spec counter" in i.message and "behind" in i.message for i in result.issues)

    def test_counter_sync_auto_fix(self, tmp_path: Path) -> None:
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        (cub_dir / "ledger").mkdir()
        (cub_dir / "counters.json").write_text(
            json.dumps({
                "spec_number": 3,
                "standalone_task_number": 1,
                "updated_at": "2026-01-01T00:00:00Z",
            })
        )
        (cub_dir / "tasks.jsonl").write_text(
            json.dumps({"id": "cub-005a-1", "title": "Task with spec 5"}) + "\n"
        )
        svc = VerifyService(tmp_path)
        result = svc.verify(fix=True, check_ledger=False, check_ids=False)
        assert result.auto_fixed >= 1
        data = json.loads((cub_dir / "counters.json").read_text())
        assert data["spec_number"] == 6


# ---------------------------------------------------------------------------
# Integration: full verify
# ---------------------------------------------------------------------------


class TestFullVerify:
    def test_healthy_project(self, tmp_path: Path) -> None:
        """A well-formed project should have no errors."""
        cub_dir = tmp_path / ".cub"
        ledger = cub_dir / "ledger"
        ledger.mkdir(parents=True)
        (ledger / "index.jsonl").write_text(
            json.dumps({"id": "cub-001-1", "title": "T1"}) + "\n"
        )
        (cub_dir / "tasks.jsonl").write_text(
            json.dumps({"id": "cub-001-1", "title": "T1"}) + "\n"
        )
        (cub_dir / "counters.json").write_text(
            json.dumps({
                "spec_number": 2,
                "standalone_task_number": 1,
                "updated_at": "2026-01-01T00:00:00Z",
            })
        )
        svc = VerifyService(tmp_path)
        result = svc.verify()
        assert not result.has_errors
        assert result.checks_run == 3

    def test_selective_checks(self, tmp_path: Path) -> None:
        """Can disable individual checks."""
        (tmp_path / ".cub" / "ledger").mkdir(parents=True)
        svc = VerifyService(tmp_path)
        result = svc.verify(check_ledger=False, check_ids=False, check_counters=False)
        assert result.checks_run == 0
        assert len(result.issues) == 0


class TestIsValidTaskId:
    def test_valid_ids(self, tmp_path: Path) -> None:
        svc = VerifyService(tmp_path)
        assert svc._is_valid_task_id("cub-001-1")
        assert svc._is_valid_task_id("cub-orphan-42")
        assert svc._is_valid_task_id("cub-abc")

    def test_invalid_ids(self, tmp_path: Path) -> None:
        svc = VerifyService(tmp_path)
        assert not svc._is_valid_task_id("")
        assert not svc._is_valid_task_id("bad")
        assert not svc._is_valid_task_id("nocub")
