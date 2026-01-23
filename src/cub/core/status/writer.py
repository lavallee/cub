"""
Status writer for cub runs.

Writes RunStatus to status.json for real-time monitoring.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import RunArtifact, RunStatus


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
        self.run_artifact_path = self.run_dir / "run.json"

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

    def write_run_artifact(self, artifact: RunArtifact) -> None:
        """
        Write run artifact to run.json.

        Uses atomic write (temp file + rename) to prevent corruption.
        This is typically called once at run completion to persist
        final budget totals and completion time.

        Args:
            artifact: RunArtifact to serialize
        """
        # Serialize to JSON
        data = artifact.model_dump(mode="json")

        # Write atomically
        temp_path = self.run_artifact_path.with_suffix(".json.tmp")
        try:
            with temp_path.open("w") as f:
                json.dump(data, f, indent=2, default=self._json_serializer)
            temp_path.rename(self.run_artifact_path)
        except Exception:
            # Clean up temp file on failure
            if temp_path.exists():
                temp_path.unlink()
            raise

    def read_run_artifact(self) -> RunArtifact | None:
        """
        Read run artifact from run.json.

        Returns:
            RunArtifact if file exists and is valid, None otherwise
        """
        if not self.run_artifact_path.exists():
            return None

        try:
            with self.run_artifact_path.open() as f:
                data = json.load(f)
            return RunArtifact(**data)
        except (json.JSONDecodeError, Exception):
            return None

    def get_task_dir(self, task_id: str) -> Path:
        """
        Get the task directory for a specific task.

        Creates the directory if it doesn't exist.

        Args:
            task_id: Task identifier (e.g., "cub-r7k.5")

        Returns:
            Path to task directory (.cub/runs/{session}/tasks/{task-id}/)
        """
        task_dir = self.run_dir / "tasks" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def get_harness_log_path(self, task_id: str) -> Path:
        """
        Get the path to harness.log for a specific task.

        Args:
            task_id: Task identifier

        Returns:
            Path to harness.log file
        """
        return self.get_task_dir(task_id) / "harness.log"

    def get_prompt_path(self, task_id: str) -> Path:
        """
        Get the path to prompt.md for a specific task.

        Args:
            task_id: Task identifier

        Returns:
            Path to prompt.md file
        """
        return self.get_task_dir(task_id) / "prompt.md"

    def write_prompt(
        self, task_id: str, system_prompt: str, task_prompt: str
    ) -> None:
        """
        Write the rendered prompt to prompt.md.

        Writes both system prompt and task prompt with clear sections
        for audit trail and debugging.

        Args:
            task_id: Task identifier
            system_prompt: System prompt content
            task_prompt: Task prompt content

        Raises:
            Exception: If writing fails
        """
        prompt_path = self.get_prompt_path(task_id)

        # Format the prompt with clear sections
        content = f"""# Rendered Prompt

## System Prompt

{system_prompt}

## Task Prompt

{task_prompt}
"""

        # Write to file
        prompt_path.write_text(content, encoding="utf-8")

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
            runs.append(
                {
                    "run_id": data.get("run_id"),
                    "session_name": data.get("session_name"),
                    "phase": data.get("phase"),
                    "started_at": data.get("started_at"),
                    "completed_at": data.get("completed_at"),
                    "tasks_completed": data.get("budget", {}).get("tasks_completed", 0),
                }
            )
        except (json.JSONDecodeError, Exception):
            continue

    # Sort by started_at (most recent first)
    runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
    return runs
