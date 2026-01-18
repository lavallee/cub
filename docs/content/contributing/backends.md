---
title: Adding Task Backends
description: How to add new task storage backends to Cub.
---

# Adding Task Backends

Task backends manage the work queue for Cub. This guide shows you how to add support for a new task storage system.

## What is a Task Backend?

A task backend provides task storage and retrieval. It handles:

- **Storage** - Persisting tasks to files, databases, or APIs
- **Querying** - Filtering tasks by status, dependencies, labels
- **Lifecycle** - Creating, updating, and closing tasks
- **Agent instructions** - Telling AI how to interact with the backend

---

## The TaskBackend Protocol

All backends implement the `TaskBackend` protocol:

```python
from typing import Protocol, runtime_checkable
from cub.core.tasks.models import Task, TaskCounts, TaskStatus

@runtime_checkable
class TaskBackend(Protocol):
    """Protocol for task backend implementations."""

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]: ...

    def get_task(self, task_id: str) -> Task | None: ...

    def get_ready_tasks(
        self,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]: ...

    def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        assignee: str | None = None,
        description: str | None = None,
        labels: list[str] | None = None,
    ) -> Task: ...

    def close_task(self, task_id: str, reason: str | None = None) -> Task: ...

    def create_task(
        self,
        title: str,
        description: str = "",
        task_type: str = "task",
        priority: int = 2,
        labels: list[str] | None = None,
        depends_on: list[str] | None = None,
        parent: str | None = None,
    ) -> Task: ...

    def get_task_counts(self) -> TaskCounts: ...

    def add_task_note(self, task_id: str, note: str) -> Task: ...

    @property
    def backend_name(self) -> str: ...

    def get_agent_instructions(self, task_id: str) -> str: ...
```

---

## Step-by-Step Guide

### Step 1: Create the Backend Module

Create `src/cub/core/tasks/mybackend.py`:

```python
"""MyBackend task management implementation."""

from __future__ import annotations

import json
from pathlib import Path

from .backend import register_backend
from .models import Task, TaskCounts, TaskStatus


@register_backend("mybackend")
class MyTaskBackend:
    """MyBackend task management system."""

    def __init__(self, project_dir: Path | None = None) -> None:
        """Initialize backend.

        Args:
            project_dir: Project directory (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()
        self._task_file = self.project_dir / ".mybackend" / "tasks.json"

    @property
    def backend_name(self) -> str:
        """Return backend name."""
        return "mybackend"

    def _load_tasks(self) -> list[dict]:
        """Load tasks from storage."""
        if not self._task_file.exists():
            return []
        with open(self._task_file) as f:
            data = json.load(f)
        return data.get("tasks", [])

    def _save_tasks(self, tasks: list[dict]) -> None:
        """Save tasks to storage."""
        self._task_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._task_file, "w") as f:
            json.dump({"tasks": tasks}, f, indent=2)

    def _dict_to_task(self, data: dict) -> Task:
        """Convert dict to Task model."""
        return Task(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "open")),
            priority=data.get("priority", 2),
            task_type=data.get("type", "task"),
            labels=data.get("labels", []),
            depends_on=data.get("depends_on", []),
            parent=data.get("parent"),
        )

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        """List all tasks, optionally filtered."""
        tasks = self._load_tasks()
        result = []

        for t in tasks:
            # Apply filters
            if status and t.get("status") != status.value:
                continue
            if parent and t.get("parent") != parent:
                continue
            if label and label not in t.get("labels", []):
                continue
            result.append(self._dict_to_task(t))

        return result

    def get_task(self, task_id: str) -> Task | None:
        """Get a specific task by ID."""
        tasks = self._load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                return self._dict_to_task(t)
        return None

    def get_ready_tasks(
        self,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        """Get all tasks ready to work on.

        A task is ready if:
        - Status is OPEN
        - All dependencies are CLOSED
        """
        all_tasks = self._load_tasks()

        # Build set of closed task IDs
        closed_ids = {t["id"] for t in all_tasks if t.get("status") == "closed"}

        ready = []
        for t in all_tasks:
            # Must be open
            if t.get("status") != "open":
                continue

            # Apply filters
            if parent and t.get("parent") != parent:
                continue
            if label and label not in t.get("labels", []):
                continue

            # All dependencies must be closed
            deps = t.get("depends_on", [])
            if all(dep in closed_ids for dep in deps):
                ready.append(self._dict_to_task(t))

        # Sort by priority (lower = higher priority)
        ready.sort(key=lambda x: x.priority)
        return ready

    def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        assignee: str | None = None,
        description: str | None = None,
        labels: list[str] | None = None,
    ) -> Task:
        """Update a task's fields."""
        tasks = self._load_tasks()

        for t in tasks:
            if t["id"] == task_id:
                if status:
                    t["status"] = status.value
                if assignee is not None:
                    t["assignee"] = assignee
                if description is not None:
                    t["description"] = description
                if labels is not None:
                    t["labels"] = labels

                self._save_tasks(tasks)
                return self._dict_to_task(t)

        raise ValueError(f"Task not found: {task_id}")

    def close_task(self, task_id: str, reason: str | None = None) -> Task:
        """Close a task."""
        tasks = self._load_tasks()

        for t in tasks:
            if t["id"] == task_id:
                t["status"] = "closed"
                if reason:
                    notes = t.get("notes", [])
                    notes.append(f"Closed: {reason}")
                    t["notes"] = notes

                self._save_tasks(tasks)
                return self._dict_to_task(t)

        raise ValueError(f"Task not found: {task_id}")

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
        """Create a new task."""
        tasks = self._load_tasks()

        # Generate ID
        task_id = f"myb-{len(tasks) + 1:03d}"

        new_task = {
            "id": task_id,
            "title": title,
            "description": description,
            "type": task_type,
            "status": "open",
            "priority": priority,
            "labels": labels or [],
            "depends_on": depends_on or [],
            "parent": parent,
        }

        tasks.append(new_task)
        self._save_tasks(tasks)
        return self._dict_to_task(new_task)

    def get_task_counts(self) -> TaskCounts:
        """Get count statistics for tasks."""
        tasks = self._load_tasks()

        counts = {"open": 0, "in_progress": 0, "closed": 0}
        for t in tasks:
            status = t.get("status", "open")
            if status in counts:
                counts[status] += 1

        return TaskCounts(
            total=len(tasks),
            open=counts["open"],
            in_progress=counts["in_progress"],
            closed=counts["closed"],
        )

    def add_task_note(self, task_id: str, note: str) -> Task:
        """Add a note to a task."""
        tasks = self._load_tasks()

        for t in tasks:
            if t["id"] == task_id:
                notes = t.get("notes", [])
                notes.append(note)
                t["notes"] = notes
                self._save_tasks(tasks)
                return self._dict_to_task(t)

        raise ValueError(f"Task not found: {task_id}")

    def get_agent_instructions(self, task_id: str) -> str:
        """Get instructions for AI agent interaction."""
        return f"""This project uses the mybackend task backend.

To complete this task, use the mybackend CLI:
- mybackend close {task_id} - Mark this task complete
- mybackend show {task_id} - Check task status
- mybackend list - See all tasks

When finished, run: mybackend close {task_id}
"""
```

### Step 2: Register the Import

Add to `src/cub/core/tasks/__init__.py`:

```python
"""Task backends for task management."""

from .backend import (
    TaskBackend,
    detect_backend,
    get_backend,
    is_backend_available,
    list_backends,
    register_backend,
)
from .models import Task, TaskCounts, TaskStatus

# Import backends to trigger registration
from . import beads
from . import json_backend
from . import mybackend  # Add your backend

__all__ = [
    "Task",
    "TaskBackend",
    "TaskCounts",
    "TaskStatus",
    "detect_backend",
    "get_backend",
    "is_backend_available",
    "list_backends",
    "register_backend",
]
```

### Step 3: Add Auto-Detection (Optional)

Update detection in `backend.py`:

```python
def detect_backend(project_dir: Path | None = None) -> str:
    """Auto-detect which task backend to use."""
    if project_dir is None:
        project_dir = Path.cwd()

    # Check for explicit override
    backend_env = os.environ.get("CUB_BACKEND", "").lower()
    if backend_env == "mybackend":
        return "mybackend"

    # Auto-detect based on directory contents
    if (project_dir / ".beads").exists():
        return "beads"
    if (project_dir / ".mybackend").exists():
        return "mybackend"  # Add detection
    if (project_dir / "prd.json").exists():
        return "json"

    return "json"
```

---

## Task Model Reference

The `Task` model used by all backends:

```python
from enum import Enum
from pydantic import BaseModel

class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"

class Task(BaseModel):
    """Task data model."""
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.OPEN
    priority: int = 2  # 0=P0 (highest) to 4=P4 (lowest)
    task_type: str = "task"  # task, feature, bug, epic, gate
    labels: list[str] = []
    depends_on: list[str] = []  # Task IDs that must complete first
    parent: str | None = None  # Parent epic ID
    assignee: str | None = None
    acceptance_criteria: list[str] = []
    notes: list[str] = []

class TaskCounts(BaseModel):
    """Task count statistics."""
    total: int
    open: int
    in_progress: int
    closed: int
```

---

## Agent Instructions

The `get_agent_instructions()` method is critical. It tells the AI how to interact with your backend:

```python
def get_agent_instructions(self, task_id: str) -> str:
    """Instructions sent to AI with each task."""
    return f"""This project uses {self.backend_name} for task management.

Commands available:
- `mybackend close {task_id}` - Mark this task complete
- `mybackend show {task_id}` - Check task details
- `mybackend list` - List all tasks

IMPORTANT: When you finish this task, you MUST run:
  mybackend close {task_id}

This signals completion to the cub run loop.
"""
```

!!! warning "Task Closure"
    The AI must be able to close tasks. Without clear instructions, the run loop cannot detect completion.

---

## Testing Your Backend

### Unit Tests

Create `tests/test_tasks_mybackend.py`:

```python
"""Tests for MyBackend task backend."""

import pytest
from pathlib import Path
from cub.core.tasks.mybackend import MyTaskBackend
from cub.core.tasks.models import TaskStatus


@pytest.fixture
def backend(tmp_path: Path) -> MyTaskBackend:
    """Create backend with temp directory."""
    return MyTaskBackend(project_dir=tmp_path)


class TestMyBackend:
    """Test MyBackend implementation."""

    def test_backend_name(self, backend):
        """Test backend name."""
        assert backend.backend_name == "mybackend"

    def test_create_task(self, backend):
        """Test task creation."""
        task = backend.create_task(
            title="Test task",
            description="A test",
            priority=1,
        )
        assert task.id.startswith("myb-")
        assert task.title == "Test task"
        assert task.status == TaskStatus.OPEN

    def test_get_task(self, backend):
        """Test getting a task by ID."""
        created = backend.create_task(title="Test")
        retrieved = backend.get_task(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_task_not_found(self, backend):
        """Test getting non-existent task."""
        task = backend.get_task("nonexistent")
        assert task is None

    def test_list_tasks_filter_status(self, backend):
        """Test filtering by status."""
        backend.create_task(title="Open task")
        task2 = backend.create_task(title="Closed task")
        backend.close_task(task2.id)

        open_tasks = backend.list_tasks(status=TaskStatus.OPEN)
        assert len(open_tasks) == 1
        assert open_tasks[0].title == "Open task"

    def test_get_ready_tasks_respects_deps(self, backend):
        """Test that ready tasks excludes blocked tasks."""
        task1 = backend.create_task(title="First")
        task2 = backend.create_task(
            title="Second",
            depends_on=[task1.id],
        )

        # Only task1 should be ready
        ready = backend.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == task1.id

        # Close task1
        backend.close_task(task1.id)

        # Now task2 should be ready
        ready = backend.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == task2.id

    def test_close_task(self, backend):
        """Test closing a task."""
        task = backend.create_task(title="Test")
        closed = backend.close_task(task.id, reason="Done")
        assert closed.status == TaskStatus.CLOSED

    def test_get_task_counts(self, backend):
        """Test task count statistics."""
        backend.create_task(title="Open 1")
        backend.create_task(title="Open 2")
        task3 = backend.create_task(title="Will close")
        backend.close_task(task3.id)

        counts = backend.get_task_counts()
        assert counts.total == 3
        assert counts.open == 2
        assert counts.closed == 1

    def test_agent_instructions(self, backend):
        """Test agent instructions contain task ID."""
        instructions = backend.get_agent_instructions("myb-001")
        assert "myb-001" in instructions
        assert "close" in instructions.lower()
```

### Integration with Cub

Test that cub run works with your backend:

```python
@pytest.mark.integration
def test_cub_run_with_backend(tmp_path, mock_harness):
    """Test cub run loop with backend."""
    backend = MyTaskBackend(project_dir=tmp_path)
    backend.create_task(title="Test task")

    # Mock the run loop to use this backend
    # ...
```

---

## Backend Features

### Supporting Model Labels

Tasks with `model:X` labels trigger automatic model selection:

```python
def get_ready_tasks(self, ...) -> list[Task]:
    # Include labels in returned tasks
    return [
        Task(
            id="myb-001",
            title="Quick fix",
            labels=["urgent", "model:haiku"],  # Include model label
            # ...
        )
    ]
```

### Dependency Handling

The `depends_on` field lists task IDs that must complete first:

```python
def get_ready_tasks(self, ...) -> list[Task]:
    """Only return tasks with all dependencies closed."""
    closed_ids = {t.id for t in self.list_tasks(status=TaskStatus.CLOSED)}

    ready = []
    for task in self.list_tasks(status=TaskStatus.OPEN):
        if all(dep in closed_ids for dep in task.depends_on):
            ready.append(task)

    return sorted(ready, key=lambda t: t.priority)
```

---

## Checklist

Before submitting your backend:

- [ ] Implements all `TaskBackend` protocol methods
- [ ] Registered with `@register_backend` decorator
- [ ] Import added to `__init__.py`
- [ ] Auto-detection added (if applicable)
- [ ] `get_agent_instructions()` includes close command
- [ ] Respects task dependencies in `get_ready_tasks()`
- [ ] Priority sorting implemented
- [ ] Unit tests written
- [ ] Documentation added

---

## Next Steps

<div class="grid cards" markdown>

-   :material-robot: **Adding Harnesses**

    ---

    Add AI coding assistant support.

    [:octicons-arrow-right-24: Harness Guide](harnesses.md)

-   :material-map: **Roadmap**

    ---

    See planned features.

    [:octicons-arrow-right-24: Roadmap](roadmap.md)

</div>
