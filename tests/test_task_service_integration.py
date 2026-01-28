"""
Integration tests for TaskService with real backends.

Tests that TaskService methods work correctly with both JSONL and Beads backends.
"""

import subprocess

import pytest

from cub.core.tasks.json import JsonBackend
from cub.core.tasks.models import TaskStatus
from cub.core.tasks.service import TaskService

# ==============================================================================
# JSONL Backend Integration Tests
# ==============================================================================


class TestTaskServiceWithJsonBackend:
    """Integration tests for TaskService with JSONL backend."""

    @pytest.fixture
    def project_dir(self, tmp_path):
        """Create a temporary project directory."""
        project = tmp_path / "test-project"
        project.mkdir()
        return project

    @pytest.fixture
    def backend(self, project_dir):
        """Create a JSONL backend."""
        return JsonBackend(project_dir=project_dir)

    @pytest.fixture
    def service(self, backend):
        """Create TaskService with JSONL backend."""
        service = TaskService()
        service._backend = backend
        return service

    def test_ready_with_jsonl_backend(self, service, backend):
        """Test ready() returns tasks with no dependencies."""
        # Create some tasks
        backend.create_task(
            title="Ready Task",
            description="No dependencies",
            priority=0,
        )
        backend.create_task(
            title="Blocked Task",
            description="Has dependency",
            depends_on=["test-001"],
            priority=1,
        )
        backend.create_task(
            title="Another Ready Task",
            description="No dependencies",
            priority=2,
        )

        # Get ready tasks
        ready_tasks = service.ready()

        # Should return 2 tasks (task-001 and task-003)
        assert len(ready_tasks) == 2
        assert ready_tasks[0].title == "Ready Task"
        assert ready_tasks[1].title == "Another Ready Task"

    def test_stale_epics_with_jsonl_backend(self, service, backend):
        """Test stale_epics() finds epics with all closed children."""
        # Create an epic
        epic1 = backend.create_task(
            title="Epic 1",
            description="Epic with all closed tasks",
            task_type="epic",
        )

        # Create child tasks (all closed)
        task1 = backend.create_task(
            title="Task 1",
            description="Child of Epic 1",
            parent=epic1.id,
        )
        task2 = backend.create_task(
            title="Task 2",
            description="Child of Epic 1",
            parent=epic1.id,
        )

        # Close the child tasks
        backend.close_task(task1.id)
        backend.close_task(task2.id)

        # Get stale epics
        stale = service.stale_epics()

        # Should find epic1
        assert len(stale) == 1
        assert stale[0].id == epic1.id

    def test_stale_epics_excludes_active_epics(self, service, backend):
        """Test stale_epics() excludes epics with open children."""
        # Create an epic
        epic2 = backend.create_task(
            title="Epic 2",
            description="Epic with open tasks",
            task_type="epic",
        )

        # Create child tasks (one open, one closed)
        backend.create_task(
            title="Task 1",
            description="Child of Epic 2",
            parent=epic2.id,
        )
        task2 = backend.create_task(
            title="Task 2",
            description="Child of Epic 2",
            parent=epic2.id,
        )

        # Close only one task
        backend.close_task(task2.id)

        # Get stale epics
        stale = service.stale_epics()

        # Should not find epic2 (has open child)
        assert len(stale) == 0

    def test_claim_with_jsonl_backend(self, service, backend):
        """Test claim() marks task as in progress."""
        # Create a task
        task = backend.create_task(
            title="Claimable Task",
            description="Task to claim",
        )

        # Claim it
        claimed = service.claim(task.id, "session-123")

        # Should be in progress with assignee
        assert claimed.status == TaskStatus.IN_PROGRESS
        assert claimed.assignee == "session-123"

        # Verify in backend
        retrieved = backend.get_task(task.id)
        assert retrieved.status == TaskStatus.IN_PROGRESS
        assert retrieved.assignee == "session-123"

    def test_claim_raises_on_already_claimed(self, service, backend):
        """Test claim() raises error on already claimed task."""
        # Create and claim a task
        task = backend.create_task(title="Task")
        service.claim(task.id, "session-1")

        # Try to claim again
        with pytest.raises(ValueError, match="already in progress"):
            service.claim(task.id, "session-2")

    def test_close_with_jsonl_backend(self, service, backend):
        """Test close() marks task as closed."""
        # Create a task
        task = backend.create_task(
            title="Task to close",
            description="Will be closed",
        )

        # Close it
        closed = service.close(task.id, reason="All done")

        # Should be closed
        assert closed.status == TaskStatus.CLOSED

        # Verify in backend
        retrieved = backend.get_task(task.id)
        assert retrieved.status == TaskStatus.CLOSED


# ==============================================================================
# Beads Backend Integration Tests
# ==============================================================================


class TestTaskServiceWithBeadsBackend:
    """Integration tests for TaskService with Beads backend."""

    @pytest.fixture
    def project_dir(self, tmp_path):
        """Create a temporary project directory with beads."""
        project = tmp_path / "beads-project"
        project.mkdir()

        # Initialize beads repository
        subprocess.run(
            ["bd", "init", "--prefix", "tst"],
            cwd=project,
            check=True,
            capture_output=True,
        )

        return project

    @pytest.fixture
    def backend(self, project_dir):
        """Create a Beads backend."""
        from cub.core.tasks.beads import BeadsBackend

        return BeadsBackend(project_dir=project_dir)

    @pytest.fixture
    def service(self, backend):
        """Create TaskService with Beads backend."""
        service = TaskService()
        service._backend = backend
        return service

    def test_ready_with_beads_backend(self, service, backend):
        """Test ready() returns tasks with no dependencies."""
        # Create some tasks
        task1 = backend.create_task(
            title="Ready Task",
            description="No dependencies",
            priority=0,
        )
        backend.create_task(
            title="Blocked Task",
            description="Has dependency",
            depends_on=[task1.id],
            priority=1,
        )

        # Get ready tasks
        ready_tasks = service.ready()

        # Should return 1 task (the ready task without dependencies)
        assert len(ready_tasks) == 1
        assert ready_tasks[0].title == "Ready Task"

    def test_stale_epics_with_beads_backend(self, service, backend):
        """Test stale_epics() finds epics with all closed children."""
        # Create an epic
        epic1 = backend.create_task(
            title="Epic 1",
            description="Epic with all closed tasks",
            task_type="epic",
        )

        # Create child tasks
        task1 = backend.create_task(
            title="Task 1",
            description="Child of Epic 1",
            parent=epic1.id,
        )
        task2 = backend.create_task(
            title="Task 2",
            description="Child of Epic 1",
            parent=epic1.id,
        )

        # Close the child tasks
        backend.close_task(task1.id)
        backend.close_task(task2.id)

        # Get stale epics
        stale = service.stale_epics()

        # Should find epic1
        assert len(stale) == 1
        assert stale[0].id == epic1.id

    def test_claim_with_beads_backend(self, service, backend):
        """Test claim() marks task as in progress."""
        # Create a task
        task = backend.create_task(
            title="Claimable Task",
            description="Task to claim",
        )

        # Claim it
        claimed = service.claim(task.id, "session-456")

        # Should be in progress with assignee
        assert claimed.status == TaskStatus.IN_PROGRESS
        assert claimed.assignee == "session-456"

    def test_close_with_beads_backend(self, service, backend):
        """Test close() marks task as closed."""
        # Create a task
        task = backend.create_task(
            title="Task to close",
            description="Will be closed",
        )

        # Close it
        closed = service.close(task.id, reason="Completed")

        # Should be closed
        assert closed.status == TaskStatus.CLOSED

    @pytest.mark.skip(reason="Requires bd CLI to be available")
    def test_skip_if_bd_not_available(self):
        """This test class requires bd CLI to be installed."""
        pass
