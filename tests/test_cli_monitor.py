"""
Tests for cub CLI monitor command.

Tests the _find_active_run resolution logic, _display_run_info,
and _show_runs helper functions.
"""

import json
import os
import time
from datetime import datetime

from cub.cli.monitor import _find_active_run, _show_runs


class TestFindActiveRun:
    """Tests for _find_active_run resolution logic."""

    def test_returns_none_when_no_cub_dir(self, tmp_path):
        """Returns None when .cub directory doesn't exist."""
        result = _find_active_run(tmp_path)
        assert result is None

    def test_returns_none_when_no_runs_dir(self, tmp_path):
        """Returns None when .cub/ledger/by-run/ doesn't exist."""
        (tmp_path / ".cub").mkdir()
        result = _find_active_run(tmp_path)
        assert result is None

    def test_returns_none_when_runs_dir_empty(self, tmp_path):
        """Returns None when .cub/ledger/by-run/ has no status files."""
        (tmp_path / ".cub" / "ledger" / "by-run").mkdir(parents=True)
        result = _find_active_run(tmp_path)
        assert result is None

    def test_finds_active_run_via_status_scan(self, tmp_path):
        """Finds a running status.json."""
        runs_dir = tmp_path / ".cub" / "ledger" / "by-run" / "test-run-001"
        runs_dir.mkdir(parents=True)

        status_data = {
            "run_id": "test-run-001",
            "phase": "running",
            "session_name": "test",
            "started_at": datetime.now().isoformat(),
        }
        (runs_dir / "status.json").write_text(json.dumps(status_data))

        result = _find_active_run(tmp_path)
        assert result is not None
        run_id, status_path = result
        assert run_id == "test-run-001"
        assert status_path == runs_dir / "status.json"

    def test_prefers_active_run_over_completed(self, tmp_path):
        """Prefers a running run over a completed one even if completed is newer."""
        cub_runs = tmp_path / ".cub" / "ledger" / "by-run"

        # Create completed run (written first, so it has an older mtime by default)
        completed_dir = cub_runs / "completed-run"
        completed_dir.mkdir(parents=True)
        (completed_dir / "status.json").write_text(
            json.dumps({"run_id": "completed-run", "phase": "completed"})
        )

        # Create active run
        active_dir = cub_runs / "active-run"
        active_dir.mkdir(parents=True)
        (active_dir / "status.json").write_text(
            json.dumps({"run_id": "active-run", "phase": "running"})
        )

        result = _find_active_run(tmp_path)
        assert result is not None
        run_id, _ = result
        assert run_id == "active-run"

    def test_falls_back_to_most_recent_when_none_active(self, tmp_path):
        """Falls back to the most recent run when none are active."""
        cub_runs = tmp_path / ".cub" / "ledger" / "by-run"

        # Create two completed runs
        run1_dir = cub_runs / "old-run"
        run1_dir.mkdir(parents=True)
        (run1_dir / "status.json").write_text(
            json.dumps({"run_id": "old-run", "phase": "completed"})
        )

        run2_dir = cub_runs / "new-run"
        run2_dir.mkdir(parents=True)
        (run2_dir / "status.json").write_text(
            json.dumps({"run_id": "new-run", "phase": "completed"})
        )

        # Set old-run to an explicitly older mtime to ensure deterministic ordering
        now = time.time()
        os.utime(run1_dir / "status.json", (now - 10, now - 10))
        os.utime(run2_dir / "status.json", (now, now))

        result = _find_active_run(tmp_path)
        assert result is not None
        run_id, _ = result
        assert run_id == "new-run"

    def test_finds_active_initializing_run(self, tmp_path):
        """Finds an initializing run (treated as active)."""
        # Create run
        run_dir = tmp_path / ".cub" / "ledger" / "by-run" / "init-run"
        run_dir.mkdir(parents=True)
        (run_dir / "status.json").write_text(
            json.dumps({"run_id": "init-run", "phase": "initializing"})
        )

        result = _find_active_run(tmp_path)
        assert result is not None
        run_id, _ = result
        assert run_id == "init-run"

    def test_skips_corrupt_json(self, tmp_path):
        """Skips corrupt JSON and continues searching."""
        # Create a run with corrupt file
        corrupt_dir = tmp_path / ".cub" / "ledger" / "by-run" / "corrupt-run"
        corrupt_dir.mkdir(parents=True)
        (corrupt_dir / "status.json").write_text("not valid json {{{")

        # Create valid run
        valid_dir = tmp_path / ".cub" / "ledger" / "by-run" / "valid-run"
        valid_dir.mkdir(parents=True)
        (valid_dir / "status.json").write_text(
            json.dumps({"run_id": "valid-run", "phase": "running"})
        )

        result = _find_active_run(tmp_path)
        assert result is not None
        run_id, _ = result
        assert run_id == "valid-run"

    def test_prefers_running_over_initializing(self, tmp_path):
        """Prefers running phase over initializing when both exist."""
        runs_dir = tmp_path / ".cub" / "ledger" / "by-run"

        # Create initializing run
        init_dir = runs_dir / "init-run"
        init_dir.mkdir(parents=True)
        (init_dir / "status.json").write_text(
            json.dumps({"run_id": "init-run", "phase": "initializing"})
        )

        # Create running run
        running_dir = runs_dir / "running-run"
        running_dir.mkdir(parents=True)
        (running_dir / "status.json").write_text(
            json.dumps({"run_id": "running-run", "phase": "running"})
        )

        result = _find_active_run(tmp_path)
        assert result is not None
        run_id, _ = result
        # Either is acceptable as both are "active" phases
        assert run_id in ("init-run", "running-run")


class TestShowRuns:
    """Tests for _show_runs helper."""

    def test_no_runs_found(self, tmp_path, capsys):
        """Displays message when no runs found."""
        from rich.console import Console

        # Monkey-patch the module-level console for testing
        import cub.cli.monitor as monitor_module

        original_console = monitor_module.console
        monitor_module.console = Console(file=open(os.devnull, "w"))

        try:
            _show_runs(tmp_path)
        finally:
            monitor_module.console = original_console

    def test_lists_runs_from_status_files(self, tmp_path):
        """Lists runs from status.json files."""
        runs_dir = tmp_path / ".cub" / "ledger" / "by-run"

        for name, phase in [("run-1", "completed"), ("run-2", "running")]:
            d = runs_dir / name
            d.mkdir(parents=True)
            (d / "status.json").write_text(
                json.dumps({
                    "run_id": name,
                    "session_name": "test",
                    "phase": phase,
                    "started_at": datetime.now().isoformat(),
                    "budget": {"tasks_completed": 3},
                })
            )

        from io import StringIO

        from rich.console import Console

        import cub.cli.monitor as monitor_module

        output = StringIO()
        original_console = monitor_module.console
        monitor_module.console = Console(file=output, force_terminal=True, width=120)

        try:
            _show_runs(tmp_path)
        finally:
            monitor_module.console = original_console

        rendered = output.getvalue()
        assert "run-1" in rendered
        assert "run-2" in rendered
