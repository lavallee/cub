"""
Status writer for cub runs.

Writes RunStatus to status.json for real-time monitoring.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import RunStatus


class StatusWriter:
    """
    Writer for run status to JSON files.

    Writes status.json to .cub/runs/{session}/status.json for
    consumption by the dashboard UI or other monitoring tools.

    Example:
        >>> writer = StatusWriter(project_dir, "camel-20260114")
        >>> writer.write(status)
        >>> # status.json is now at .cub/runs/camel-20260114/status.json
    """

    def __init__(self, project_dir: Path, run_id: str):
        """
        Initialize the status writer.

        Args:
            project_dir: Project root directory
            run_id: Unique run identifier (used as directory name)
        """
        self.project_dir = project_dir
        self.run_id = run_id

        # Create the run directory
        self.run_dir = project_dir / ".cub" / "runs" / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.status_path = self.run_dir / "status.json"

    def write(self, status: RunStatus) -> None:
        """
        Write status to status.json.

        Uses atomic write (temp file + rename) to prevent corruption.

        Args:
            status: RunStatus to serialize
        """
        # Update timestamp before writing
        status.updated_at = datetime.now()

        # Serialize to JSON
        data = status.model_dump(mode="json")

        # Write atomically
        temp_path = self.status_path.with_suffix(".json.tmp")
        try:
            with temp_path.open("w") as f:
                json.dump(data, f, indent=2, default=self._json_serializer)
            temp_path.rename(self.status_path)
        except Exception:
            # Clean up temp file on failure
            if temp_path.exists():
                temp_path.unlink()
            raise

    def read(self) -> RunStatus | None:
        """
        Read status from status.json.

        Returns:
            RunStatus if file exists and is valid, None otherwise
        """
        if not self.status_path.exists():
            return None

        try:
            with self.status_path.open() as f:
                data = json.load(f)
            return RunStatus(**data)
        except (json.JSONDecodeError, Exception):
            return None

    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for datetime and enum objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "value"):
            return obj.value
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def get_latest_status(project_dir: Path) -> RunStatus | None:
    """
    Get the most recent run status from the project.

    Searches .cub/runs/ for the most recently modified status.json.

    Args:
        project_dir: Project root directory

    Returns:
        RunStatus from most recent run, or None if no runs found
    """
    runs_dir = project_dir / ".cub" / "runs"
    if not runs_dir.exists():
        return None

    # Find all status.json files
    status_files = list(runs_dir.glob("*/status.json"))
    if not status_files:
        return None

    # Sort by modification time (most recent first)
    status_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Load the most recent
    try:
        with status_files[0].open() as f:
            data = json.load(f)
        return RunStatus(**data)
    except (json.JSONDecodeError, Exception):
        return None


def list_runs(project_dir: Path) -> list[dict[str, Any]]:
    """
    List all runs in the project.

    Args:
        project_dir: Project root directory

    Returns:
        List of run summaries (run_id, phase, started_at, etc.)
    """
    runs_dir = project_dir / ".cub" / "runs"
    if not runs_dir.exists():
        return []

    runs = []
    for status_file in runs_dir.glob("*/status.json"):
        try:
            with status_file.open() as f:
                data = json.load(f)
            runs.append({
                "run_id": data.get("run_id"),
                "session_name": data.get("session_name"),
                "phase": data.get("phase"),
                "started_at": data.get("started_at"),
                "completed_at": data.get("completed_at"),
                "tasks_completed": data.get("budget", {}).get("tasks_completed", 0),
            })
        except (json.JSONDecodeError, Exception):
            continue

    # Sort by started_at (most recent first)
    runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
    return runs
