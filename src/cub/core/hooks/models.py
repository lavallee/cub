"""
Hook data models for cub.

Defines context models that carry data to lifecycle hook scripts and models
for hook execution results and configuration.

Lifecycle hooks fire at key points during autonomous execution:
- pre-session: Before harness session starts
- end-of-task: After a task completes
- end-of-epic: After all tasks in an epic complete
- end-of-plan: After all epics in a plan complete

Context models serialize to JSON and are passed to hook scripts via the
CUB_HOOK_CONTEXT environment variable.
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class SessionContext(BaseModel):
    """
    Context for pre-session hook.

    Fires before the harness session begins, providing information about
    the run configuration and environment.
    """

    session_id: str = Field(description="Unique session identifier")
    project_dir: str = Field(description="Absolute path to project root")
    timestamp: datetime = Field(default_factory=datetime.now, description="When session started")
    harness_name: str = Field(description="Harness being used (e.g., 'claude', 'codex')")
    model: str | None = Field(default=None, description="Model name if specified")
    task_count: int = Field(default=0, description="Number of tasks in queue")
    epic_count: int = Field(default=0, description="Number of epics in queue")

    def to_json(self) -> str:
        """Serialize to JSON string for environment variable passing."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "SessionContext":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class TaskContext(BaseModel):
    """
    Context for end-of-task hook.

    Fires after a task completes (success or failure), providing task
    details and execution results.
    """

    task_id: str = Field(description="Task identifier")
    task_title: str = Field(description="Human-readable task title")
    status: str = Field(description="Task completion status (closed, failed, skipped)")
    success: bool = Field(description="Whether task completed successfully")
    project_dir: str = Field(description="Absolute path to project root")
    timestamp: datetime = Field(default_factory=datetime.now, description="When task completed")
    session_id: str | None = Field(default=None, description="Session ID if available")
    parent_epic: str | None = Field(
        default=None, description="Parent epic ID if task is in an epic"
    )
    duration_seconds: float | None = Field(default=None, description="Task execution duration")
    iterations: int = Field(default=0, description="Number of iterations taken")
    error_message: str | None = Field(default=None, description="Error message if task failed")

    def to_json(self) -> str:
        """Serialize to JSON string for environment variable passing."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "TaskContext":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class EpicContext(BaseModel):
    """
    Context for end-of-epic hook.

    Fires after all tasks in an epic complete, providing epic-level
    summary and results.
    """

    epic_id: str = Field(description="Epic identifier")
    epic_title: str = Field(description="Human-readable epic title")
    project_dir: str = Field(description="Absolute path to project root")
    timestamp: datetime = Field(default_factory=datetime.now, description="When epic completed")
    session_id: str | None = Field(default=None, description="Session ID if available")
    parent_plan: str | None = Field(default=None, description="Parent plan ID if epic is in a plan")
    total_tasks: int = Field(default=0, description="Total tasks in epic")
    completed_tasks: int = Field(default=0, description="Tasks completed successfully")
    failed_tasks: int = Field(default=0, description="Tasks that failed")
    skipped_tasks: int = Field(default=0, description="Tasks skipped")
    duration_seconds: float | None = Field(default=None, description="Epic execution duration")

    def to_json(self) -> str:
        """Serialize to JSON string for environment variable passing."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "EpicContext":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class PlanContext(BaseModel):
    """
    Context for end-of-plan hook.

    Fires after all epics in a plan complete, providing plan-level
    summary and final results.
    """

    plan_id: str = Field(description="Plan identifier")
    plan_title: str = Field(description="Human-readable plan title")
    project_dir: str = Field(description="Absolute path to project root")
    timestamp: datetime = Field(default_factory=datetime.now, description="When plan completed")
    session_id: str | None = Field(default=None, description="Session ID if available")
    total_epics: int = Field(default=0, description="Total epics in plan")
    completed_epics: int = Field(default=0, description="Epics completed successfully")
    total_tasks: int = Field(default=0, description="Total tasks across all epics")
    completed_tasks: int = Field(default=0, description="Tasks completed successfully")
    failed_tasks: int = Field(default=0, description="Tasks that failed")
    duration_seconds: float | None = Field(default=None, description="Plan execution duration")

    def to_json(self) -> str:
        """Serialize to JSON string for environment variable passing."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "PlanContext":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class HookResult(BaseModel):
    """
    Result from hook script execution.

    Captures the success/failure status, output, and timing information
    from a hook script invocation.
    """

    success: bool = Field(description="Whether hook executed successfully")
    exit_code: int = Field(default=0, description="Exit code from hook script")
    stdout: str = Field(default="", description="Standard output from hook")
    stderr: str = Field(default="", description="Standard error from hook")
    duration_seconds: float = Field(description="Hook execution duration")
    timestamp: datetime = Field(default_factory=datetime.now, description="When hook was executed")
    error_message: str | None = Field(default=None, description="Error message if execution failed")

    @property
    def failed(self) -> bool:
        """Check if hook execution failed."""
        return not self.success


class HookConfig(BaseModel):
    """
    Configuration for a hook script.

    Defines which hooks are enabled, where to find scripts, and
    execution parameters like timeout.
    """

    enabled: bool = Field(default=True, description="Whether hooks are enabled globally")
    project_hooks_dir: str = Field(
        default=".cub/hooks", description="Project-relative hooks directory"
    )
    global_hooks_dir: str | None = Field(
        default=None, description="Global hooks directory (e.g., ~/.cub/hooks)"
    )
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="Timeout for hook execution")
    fail_on_error: bool = Field(
        default=False,
        description="Whether to fail the run if a hook fails (default: log and continue)",
    )
    enabled_hooks: list[str] = Field(
        default_factory=lambda: ["pre-session", "end-of-task", "end-of-epic", "end-of-plan"],
        description="List of enabled hook names",
    )

    def is_hook_enabled(self, hook_name: str) -> bool:
        """
        Check if a specific hook is enabled.

        Args:
            hook_name: Name of hook (e.g., 'pre-session', 'end-of-task')

        Returns:
            True if hook is enabled
        """
        return self.enabled and hook_name in self.enabled_hooks

    def get_project_hooks_path(self, project_dir: Path) -> Path:
        """
        Get absolute path to project hooks directory.

        Args:
            project_dir: Project root directory

        Returns:
            Absolute path to project hooks directory
        """
        return project_dir / self.project_hooks_dir

    def get_global_hooks_path(self) -> Path | None:
        """
        Get absolute path to global hooks directory.

        Returns:
            Absolute path to global hooks directory, or None if not configured
        """
        if self.global_hooks_dir:
            return Path(self.global_hooks_dir).expanduser()
        return None
