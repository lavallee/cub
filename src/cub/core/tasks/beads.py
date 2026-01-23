"""
Beads task backend implementation.

This backend wraps the beads CLI (`bd`) to provide task management
when a project uses beads (.beads/ directory present).
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .backend import register_backend
from .models import Task, TaskCounts, TaskStatus


class BeadsNotAvailableError(Exception):
    """Raised when beads CLI is not installed or not available."""

    pass


class BeadsCommandError(Exception):
    """Raised when a beads CLI command fails."""

    pass


@register_backend("beads")
class BeadsBackend:
    """
    Task backend that uses the beads CLI (`bd`).

    This backend calls the `bd` CLI tool via subprocess and parses
    the JSON output into Task models. All beads commands use --json
    flag for machine-readable output.

    Example:
        >>> backend = BeadsBackend()
        >>> tasks = backend.list_tasks(status=TaskStatus.OPEN)
        >>> task = backend.get_task("cub-001")
    """

    def __init__(self, project_dir: Path | None = None):
        """
        Initialize the beads backend.

        Args:
            project_dir: Project directory (defaults to current directory)

        Raises:
            BeadsNotAvailableError: If bd CLI is not installed
        """
        self.project_dir = project_dir or Path.cwd()

        # Check if bd is available
        if not self._is_bd_available():
            raise BeadsNotAvailableError(
                "beads CLI (bd) is not installed. "
                "Install with: npm install -g @beads/bd OR brew install steveyegge/beads/bd"
            )

    def _is_bd_available(self) -> bool:
        """Check if bd CLI is available in PATH."""
        return shutil.which("bd") is not None

    def _run_bd(
        self, args: list[str], check: bool = True, expect_json: bool = True
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Run a bd CLI command and optionally parse JSON output.

        Args:
            args: Command arguments (e.g., ["list", "--json"])
            check: Whether to raise exception on command failure
            expect_json: Whether to parse output as JSON. Set to False for
                commands like 'update', 'close', 'comment' that return
                human-readable output.

        Returns:
            Parsed JSON output as dict or list (if expect_json=True),
            or empty dict (if expect_json=False)

        Raises:
            BeadsCommandError: If command fails and check=True
        """
        cmd = ["bd"] + args

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=check,
            )

            # Skip JSON parsing for commands that don't return JSON
            if not expect_json:
                return {}

            # Parse JSON output
            if result.stdout:
                try:
                    parsed: dict[str, Any] | list[dict[str, Any]] = json.loads(result.stdout)
                    return parsed
                except json.JSONDecodeError as e:
                    raise BeadsCommandError(
                        f"Failed to parse bd output as JSON: {e}\n"
                        f"Command: {' '.join(cmd)}\n"
                        f"Output: {result.stdout[:200]}"
                    )

            # Empty output - return empty list
            return []

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            raise BeadsCommandError(f"bd command failed: {' '.join(cmd)}\nError: {error_msg}")

    def _transform_beads_task(self, raw_task: dict[str, Any]) -> Task:
        """
        Transform raw beads JSON into a Task model.

        Beads uses different field names than our Task model:
        - issue_type -> type
        - priority (int 0-4) -> priority (P0-P4)
        - blocks -> depends_on

        Args:
            raw_task: Raw task dict from bd JSON output

        Returns:
            Task model instance
        """
        # Map beads fields to Task model fields
        task_data = {
            "id": raw_task["id"],
            "title": raw_task["title"],
            "status": raw_task.get("status", "open"),
            "type": raw_task.get("issue_type", raw_task.get("type", "task")),
            "description": raw_task.get("description", ""),
            "labels": raw_task.get("labels", []),
            "assignee": raw_task.get("assignee"),
            "parent": raw_task.get("parent"),
            "depends_on": raw_task.get("blocks", []),  # beads uses "blocks" for dependencies
            "acceptance_criteria": raw_task.get("acceptance_criteria", []),
            "notes": raw_task.get("notes", ""),
        }

        # Convert priority (beads uses 0-4 int, we use P0-P4)
        priority = raw_task.get("priority", 2)
        if isinstance(priority, int):
            task_data["priority"] = f"P{priority}"
        else:
            task_data["priority"] = priority

        # Parse timestamps if present
        if "created_at" in raw_task:
            task_data["created_at"] = raw_task["created_at"]
        if "updated_at" in raw_task:
            task_data["updated_at"] = raw_task["updated_at"]
        if "closed_at" in raw_task:
            task_data["closed_at"] = raw_task["closed_at"]

        return Task(**task_data)

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        """
        List all tasks, optionally filtered.

        Args:
            status: Filter by task status (open, in_progress, closed)
            parent: Filter by parent epic/task ID
            label: Filter by label (tasks with this label)

        Returns:
            List of tasks matching the filter criteria
        """
        args = ["list", "--json"]

        if status:
            args.extend(["--status", status.value])
        if parent:
            args.extend(["--parent", parent])
        if label:
            args.extend(["--label", label])

        result = self._run_bd(args)

        # Handle both list and single-item responses
        if not isinstance(result, list):
            raw_tasks = [result] if result else []
        else:
            raw_tasks = result

        return [self._transform_beads_task(t) for t in raw_tasks]

    def get_task(self, task_id: str) -> Task | None:
        """
        Get a specific task by ID.

        Args:
            task_id: Unique task identifier

        Returns:
            Task object if found, None otherwise
        """
        try:
            raw_tasks = self._run_bd(["show", task_id, "--json"])

            # bd show returns a list with one item
            if isinstance(raw_tasks, list) and len(raw_tasks) > 0:
                return self._transform_beads_task(raw_tasks[0])
            elif isinstance(raw_tasks, dict):
                return self._transform_beads_task(raw_tasks)

            return None

        except BeadsCommandError:
            # Task not found
            return None

    def get_ready_tasks(
        self,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        """
        Get all tasks that are ready to work on.

        A task is ready if:
        - Status is OPEN
        - All dependencies are CLOSED

        Tasks are returned sorted by priority (P0 first).

        Args:
            parent: Filter by parent epic/task ID
            label: Filter by label

        Returns:
            List of ready tasks sorted by priority
        """
        args = ["ready", "--json"]

        if parent:
            # Support both label formats for epic association:
            # - Punchlist tasks use the epic ID directly (e.g., "cub-xyz")
            # - Legacy tasks may use "epic:<epic-id>" format
            # Use --label-any for OR logic to match either format
            args.extend(["--label-any", parent, "--label-any", f"epic:{parent}"])
        if label:
            args.extend(["--label", label])

        try:
            result = self._run_bd(args)

            # Handle both list and single-item responses
            if not isinstance(result, list):
                raw_tasks = [result] if result else []
            else:
                raw_tasks = result

            tasks = [self._transform_beads_task(t) for t in raw_tasks]

            # Sort by priority (P0 = 0 is highest priority)
            return sorted(tasks, key=lambda t: t.priority_numeric)

        except BeadsCommandError:
            # If bd ready fails, return empty list
            return []

    def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        assignee: str | None = None,
        description: str | None = None,
        labels: list[str] | None = None,
    ) -> Task:
        """
        Update a task's fields.

        Args:
            task_id: Task to update
            status: New status
            assignee: New assignee
            description: New description
            labels: New labels list

        Returns:
            Updated task object

        Raises:
            ValueError: If task not found or update fails
        """
        args = ["update", task_id]

        if status:
            args.extend(["--status", status.value])
        if assignee:
            args.extend(["--assignee", assignee])
        if description:
            args.extend(["--description", description])
        if labels:
            # bd update expects labels as comma-separated string
            args.extend(["--labels", ",".join(labels)])

        try:
            # bd update doesn't return JSON, so we need to fetch the updated task
            self._run_bd(args, expect_json=False)
            updated_task = self.get_task(task_id)

            if updated_task is None:
                raise ValueError(f"Task {task_id} not found after update")

            return updated_task

        except BeadsCommandError as e:
            raise ValueError(f"Failed to update task {task_id}: {e}")

    def close_task(self, task_id: str, reason: str | None = None) -> Task:
        """
        Close a task.

        Marks the task as closed and optionally adds a closing note.

        Args:
            task_id: Task to close
            reason: Optional reason for closing

        Returns:
            Closed task object

        Raises:
            ValueError: If task not found or already closed
        """
        args = ["close", task_id]

        if reason:
            args.extend(["-r", reason])

        try:
            # bd close doesn't return JSON
            self._run_bd(args, expect_json=False)
            closed_task = self.get_task(task_id)

            if closed_task is None:
                raise ValueError(f"Task {task_id} not found after close")

            return closed_task

        except BeadsCommandError as e:
            raise ValueError(f"Failed to close task {task_id}: {e}")

    def create_task(
        self,
        title: str,
        description: str = "",
        task_type: str = "task",
        priority: int = 2,
        labels: list[str] | None = None,
        depends_on: list[str] | None = None,
        parent: str | None = None,
    ) -> Task:
        """
        Create a new task.

        Args:
            title: Task title
            description: Task description
            task_type: Task type (task, feature, bug, epic, gate)
            priority: Priority level (0-4, where 0 is highest)
            labels: Task labels
            depends_on: List of task IDs this task depends on
            parent: Parent epic/task ID

        Returns:
            Created task object

        Raises:
            ValueError: If task creation fails
        """
        args = ["create", title, "--json"]

        # Add type and priority
        args.extend(["--type", task_type])
        args.extend(["-p", str(priority)])

        # Add optional fields
        if parent:
            args.extend(["--parent", parent])
        if labels:
            args.extend(["--labels", ",".join(labels)])

        try:
            # Create the task and get its ID
            result = self._run_bd(args)
            if isinstance(result, dict):
                new_id_raw = result.get("id")
                if new_id_raw is None:
                    raise ValueError("bd create did not return a task ID")
                new_id = str(new_id_raw)
            else:
                raise ValueError(f"Unexpected result from bd create: {result}")

            # Add description if present (bd create doesn't support --description)
            if description:
                self.update_task(new_id, description=description)

            # Add dependencies
            if depends_on:
                for dep_id in depends_on:
                    # bd dep add <task> <depends-on> --type blocks
                    # This means task blocks the dependency (dependency must complete first)
                    # bd dep add doesn't return JSON
                    self._run_bd(
                        ["dep", "add", new_id, dep_id, "--type", "blocks"], expect_json=False
                    )

            # Fetch and return the created task
            created_task = self.get_task(new_id)
            if created_task is None:
                raise ValueError(f"Failed to fetch created task {new_id}")

            return created_task

        except BeadsCommandError as e:
            raise ValueError(f"Failed to create task: {e}")

    def get_task_counts(self) -> TaskCounts:
        """
        Get count statistics for tasks.

        Returns:
            TaskCounts object with total, open, in_progress, closed counts
        """
        try:
            result = self._run_bd(["list", "--json"])

            # Handle both list and single-item responses
            if not isinstance(result, list):
                raw_tasks = [result] if result else []
            else:
                raw_tasks = result

            # Count tasks by status
            total = len(raw_tasks)
            open_count = sum(1 for t in raw_tasks if t.get("status") == "open")
            in_progress = sum(1 for t in raw_tasks if t.get("status") == "in_progress")
            closed = sum(1 for t in raw_tasks if t.get("status") == "closed")

            return TaskCounts(
                total=total,
                open=open_count,
                in_progress=in_progress,
                closed=closed,
            )

        except BeadsCommandError:
            # Return zero counts on error
            return TaskCounts()

    def add_task_note(self, task_id: str, note: str) -> Task:
        """
        Add a note/comment to a task.

        Args:
            task_id: Task to add note to
            note: Note text to add

        Returns:
            Updated task object

        Raises:
            ValueError: If task not found
        """
        try:
            # bd comment doesn't return JSON
            self._run_bd(["comment", task_id, note], expect_json=False)

            # Fetch and return the updated task
            updated_task = self.get_task(task_id)
            if updated_task is None:
                raise ValueError(f"Task {task_id} not found after adding note")

            return updated_task

        except BeadsCommandError as e:
            raise ValueError(f"Failed to add note to task {task_id}: {e}")

    def import_tasks(self, tasks: list[Task]) -> list[Task]:
        """
        Bulk import tasks using bd import with JSONL.

        This method enables efficient bulk import of multiple tasks at once,
        preserving the explicit IDs from the tasks. It uses `bd import` with
        JSONL format rather than individual `bd create` calls.

        Args:
            tasks: List of Task objects to import

        Returns:
            List of imported Task objects

        Raises:
            ValueError: If import fails
        """
        import tempfile
        from datetime import datetime, timezone

        if not tasks:
            return []

        # Build reverse mapping: for each task, what blocks it (what it depends on)
        # If task A blocks [B, C], then B and C depend on A
        blocked_by: dict[str, list[str]] = {}
        for task in tasks:
            if task.blocks:
                for blocked_id in task.blocks:
                    if blocked_id not in blocked_by:
                        blocked_by[blocked_id] = []
                    blocked_by[blocked_id].append(task.id)

        # Convert tasks to beads JSONL format
        jsonl_lines = []
        for task in tasks:
            # Build dependencies array for parent-child and blocks relationships
            dependencies = []
            if task.parent:
                dependencies.append({
                    "issue_id": task.id,
                    "depends_on_id": task.parent,
                    "type": "parent-child",
                })
            # Add blocks dependencies: this task is blocked by (depends on) these tasks
            if task.id in blocked_by:
                for blocker_id in blocked_by[task.id]:
                    dependencies.append({
                        "issue_id": task.id,
                        "depends_on_id": blocker_id,
                        "type": "blocks",
                    })

            beads_issue = {
                "id": task.id,
                "title": task.title,
                "description": task.description or "",
                "status": "open",
                "priority": task.priority_numeric,
                "issue_type": task.type.value,
                "labels": task.labels or [],
                "dependencies": dependencies,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            jsonl_lines.append(json.dumps(beads_issue))

        # Write to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".jsonl",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write("\n".join(jsonl_lines))
            temp_path = f.name

        try:
            # Run bd import
            result = subprocess.run(
                ["bd", "import", "-i", temp_path, "--json"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise ValueError(
                    f"bd import failed: {result.stderr.strip() or result.stdout.strip()}"
                )

            # Fetch the imported tasks
            imported_tasks = []
            for task in tasks:
                imported = self.get_task(task.id)
                if imported:
                    imported_tasks.append(imported)
                else:
                    # Task may not exist if there was a silent failure
                    raise ValueError(
                        f"Task '{task.id}' was not found after import"
                    )

            return imported_tasks

        finally:
            # Clean up temp file
            import os
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    @property
    def backend_name(self) -> str:
        """Get the name of this backend."""
        return "beads"

    def get_agent_instructions(self, task_id: str) -> str:
        """
        Get instructions for an AI agent on how to interact with beads.

        Args:
            task_id: The current task ID for context

        Returns:
            Multiline string with agent instructions
        """
        return f"""This project uses the beads task backend (`bd` CLI).

**Task lifecycle:**
- `bd update {task_id} --status in_progress` - Claim the task (do this first)
- `bd close {task_id}` - Mark task complete (after all checks pass)
- `bd close {task_id} -r "reason"` - Close with explanation

**Useful commands:**
- `bd show {task_id}` - View task details and dependencies
- `bd list --status open` - See remaining open tasks
- `bd ready` - See tasks ready to work on (no blockers)

**Important:** Always run feedback loops (tests, typecheck, lint) BEFORE closing the task."""

    def bind_branch(
        self,
        epic_id: str,
        branch_name: str,
        base_branch: str = "main",
    ) -> bool:
        """
        Bind a git branch to an epic using beads branch store.

        Args:
            epic_id: Epic ID to bind
            branch_name: Git branch name
            base_branch: Base branch for merging

        Returns:
            True if binding was created, False if already exists
        """
        from cub.core.branches.store import BranchStore, BranchStoreError

        try:
            store = BranchStore()
            # Check if binding already exists
            existing = store.get_binding(epic_id)
            if existing:
                return False
            existing_branch = store.get_binding_by_branch(branch_name)
            if existing_branch:
                return False
            # Create new binding
            store.add_binding(epic_id, branch_name, base_branch)
            return True
        except BranchStoreError:
            # .beads directory might not exist or other issue
            return False

    def try_close_epic(self, epic_id: str) -> tuple[bool, str]:
        """
        Attempt to close an epic if all its tasks are complete.

        Checks all tasks belonging to the epic and closes the epic if
        all tasks have status CLOSED.

        Args:
            epic_id: The epic ID to potentially close

        Returns:
            Tuple of (closed: bool, message: str)
        """
        # First, check if the epic exists and get its current status
        epic = self.get_task(epic_id)
        if epic is None:
            return False, f"Epic '{epic_id}' not found"

        if epic.status == TaskStatus.CLOSED:
            return False, f"Epic '{epic_id}' is already closed"

        # Get all tasks that belong to this epic (using parent filter)
        # Also check for tasks labeled with the epic ID
        tasks_by_parent = self.list_tasks(parent=epic_id)
        tasks_by_label = self.list_tasks(label=epic_id)

        # Combine and deduplicate
        seen_ids: set[str] = set()
        all_epic_tasks: list[Task] = []
        for task in tasks_by_parent + tasks_by_label:
            if task.id not in seen_ids and task.id != epic_id:
                seen_ids.add(task.id)
                all_epic_tasks.append(task)

        if not all_epic_tasks:
            return False, f"No tasks found for epic '{epic_id}'"

        # Check status of all tasks
        open_count = 0
        in_progress_count = 0
        closed_count = 0

        for task in all_epic_tasks:
            if task.status == TaskStatus.CLOSED:
                closed_count += 1
            elif task.status == TaskStatus.IN_PROGRESS:
                in_progress_count += 1
            else:
                open_count += 1

        # If any tasks are not closed, don't close the epic
        if open_count > 0 or in_progress_count > 0:
            return False, (
                f"Epic '{epic_id}' has {open_count} open and "
                f"{in_progress_count} in-progress tasks remaining "
                f"({closed_count} closed)"
            )

        # All tasks are closed - close the epic
        try:
            self.close_task(epic_id, reason="All tasks completed")
            return True, f"Epic '{epic_id}' auto-closed ({closed_count} tasks completed)"
        except (ValueError, BeadsCommandError) as e:
            return False, f"Failed to close epic '{epic_id}': {e}"
