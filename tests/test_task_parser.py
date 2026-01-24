"""
Tests for TaskParser.

Tests the task parser's ability to convert task backend data
into DashboardEntity objects with proper stage computation.
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from cub.core.dashboard.db.models import EntityType, Stage
from cub.core.dashboard.sync.parsers.tasks import TaskParser
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType


class MockTaskBackend:
    """Mock task backend for testing."""

    def __init__(self, tasks: list[Task] | None = None):
        self.tasks = tasks or []
        self._backend_name = "mock"

    @property
    def backend_name(self) -> str:
        return self._backend_name

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        """Filter tasks by criteria."""
        result = self.tasks

        if status:
            result = [t for t in result if t.status == status]
        if parent:
            result = [t for t in result if t.parent == parent]
        if label:
            result = [t for t in result if label in t.labels]

        return result

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None


@pytest.fixture
def sample_tasks() -> list[Task]:
    """Create sample tasks for testing."""
    return [
        # Epic in planning
        Task(
            id="cub-001",
            title="Authentication System",
            description="Implement user authentication",
            type=TaskType.EPIC,
            status=TaskStatus.OPEN,
            priority=TaskPriority.P0,
            labels=["security"],
            created_at=datetime(2024, 1, 1, 10, 0, 0),
        ),
        # Task ready to work
        Task(
            id="cub-001.1",
            title="Add login form",
            description="Create login form component",
            type=TaskType.TASK,
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            parent="cub-001",
            labels=["frontend"],
            created_at=datetime(2024, 1, 2, 10, 0, 0),
        ),
        # Task in progress
        Task(
            id="cub-001.2",
            title="Setup JWT tokens",
            description="Configure JWT authentication",
            type=TaskType.TASK,
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P0,
            parent="cub-001",
            labels=["backend"],
            created_at=datetime(2024, 1, 2, 11, 0, 0),
            updated_at=datetime(2024, 1, 3, 9, 0, 0),
        ),
        # Task in review
        Task(
            id="cub-001.3",
            title="Add password hashing",
            description="Implement bcrypt password hashing",
            type=TaskType.TASK,
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P1,
            parent="cub-001",
            labels=["backend", "pr"],
            created_at=datetime(2024, 1, 2, 12, 0, 0),
            updated_at=datetime(2024, 1, 4, 14, 0, 0),
        ),
        # Closed task
        Task(
            id="cub-001.4",
            title="Write auth docs",
            description="Document authentication flow",
            type=TaskType.TASK,
            status=TaskStatus.CLOSED,
            priority=TaskPriority.P2,
            parent="cub-001",
            labels=["docs"],
            created_at=datetime(2024, 1, 2, 13, 0, 0),
            closed_at=datetime(2024, 1, 5, 16, 0, 0),
        ),
        # Epic in progress
        Task(
            id="cub-002",
            title="Dashboard UI",
            description="Build project dashboard",
            type=TaskType.EPIC,
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P1,
            labels=["frontend"],
            created_at=datetime(2024, 1, 10, 10, 0, 0),
            updated_at=datetime(2024, 1, 11, 9, 0, 0),
        ),
    ]


@pytest.fixture
def mock_backend(sample_tasks: list[Task]) -> MockTaskBackend:
    """Create mock backend with sample tasks."""
    return MockTaskBackend(tasks=sample_tasks)


@pytest.fixture
def parser(mock_backend: MockTaskBackend) -> TaskParser:
    """Create TaskParser with mock backend."""
    return TaskParser(backend=mock_backend)


class TestTaskParser:
    """Test suite for TaskParser."""

    def test_parse_all(self, parser: TaskParser, sample_tasks: list[Task]) -> None:
        """Test parsing all tasks from backend."""
        entities = parser.parse_all()

        # Should get all tasks
        assert len(entities) == len(sample_tasks)

        # Should be sorted by ID
        assert entities[0].id == "cub-001"
        assert entities[-1].id == "cub-002"

        # Check entity types
        epic_entities = [e for e in entities if e.type == EntityType.EPIC]
        task_entities = [e for e in entities if e.type == EntityType.TASK]
        assert len(epic_entities) == 2
        assert len(task_entities) == 4

    def test_stage_computation_epic_open(self, parser: TaskParser) -> None:
        """Test stage computation for open epic."""
        task = Task(
            id="epic-1",
            title="Test Epic",
            type=TaskType.EPIC,
            status=TaskStatus.OPEN,
        )
        checksum = parser._compute_checksum(task)
        entity = parser._task_to_entity(task, checksum)

        assert entity.stage == Stage.PLANNED
        assert entity.type == EntityType.EPIC

    def test_stage_computation_epic_in_progress(self, parser: TaskParser) -> None:
        """Test stage computation for in-progress epic."""
        task = Task(
            id="epic-1",
            title="Test Epic",
            type=TaskType.EPIC,
            status=TaskStatus.IN_PROGRESS,
        )
        checksum = parser._compute_checksum(task)
        entity = parser._task_to_entity(task, checksum)

        assert entity.stage == Stage.IN_PROGRESS
        assert entity.type == EntityType.EPIC

    def test_stage_computation_task_open(self, parser: TaskParser) -> None:
        """Test stage computation for open task."""
        task = Task(
            id="task-1",
            title="Test Task",
            type=TaskType.TASK,
            status=TaskStatus.OPEN,
        )
        checksum = parser._compute_checksum(task)
        entity = parser._task_to_entity(task, checksum)

        assert entity.stage == Stage.READY
        assert entity.type == EntityType.TASK

    def test_stage_computation_task_in_progress(self, parser: TaskParser) -> None:
        """Test stage computation for in-progress task."""
        task = Task(
            id="task-1",
            title="Test Task",
            type=TaskType.TASK,
            status=TaskStatus.IN_PROGRESS,
        )
        checksum = parser._compute_checksum(task)
        entity = parser._task_to_entity(task, checksum)

        assert entity.stage == Stage.IN_PROGRESS
        assert entity.type == EntityType.TASK

    def test_stage_computation_task_review(self, parser: TaskParser) -> None:
        """Test stage computation for task in review."""
        task = Task(
            id="task-1",
            title="Test Task",
            type=TaskType.TASK,
            status=TaskStatus.IN_PROGRESS,
            labels=["pr"],
        )
        checksum = parser._compute_checksum(task)
        entity = parser._task_to_entity(task, checksum)

        assert entity.stage == Stage.NEEDS_REVIEW
        assert entity.type == EntityType.TASK

    def test_stage_computation_task_closed(self, parser: TaskParser) -> None:
        """Test stage computation for closed task."""
        task = Task(
            id="task-1",
            title="Test Task",
            type=TaskType.TASK,
            status=TaskStatus.CLOSED,
        )
        checksum = parser._compute_checksum(task)
        entity = parser._task_to_entity(task, checksum)

        assert entity.stage == Stage.COMPLETE
        assert entity.type == EntityType.TASK

    def test_entity_metadata(self, parser: TaskParser) -> None:
        """Test entity metadata mapping."""
        task = Task(
            id="task-1",
            title="Test Task",
            description="Test description",
            type=TaskType.TASK,
            status=TaskStatus.OPEN,
            priority=TaskPriority.P0,
            labels=["frontend", "urgent"],
            parent="epic-1",
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            updated_at=datetime(2024, 1, 2, 11, 0, 0),
        )
        checksum = parser._compute_checksum(task)
        entity = parser._task_to_entity(task, checksum)

        assert entity.id == "task-1"
        assert entity.title == "Test Task"
        assert entity.description == "Test description"
        assert entity.priority == 0  # P0 -> 0
        assert entity.labels == ["frontend", "urgent"]
        assert entity.epic_id == "epic-1"
        assert entity.parent_id == "epic-1"
        assert entity.created_at == datetime(2024, 1, 1, 10, 0, 0)
        assert entity.updated_at == datetime(2024, 1, 2, 11, 0, 0)
        assert entity.source_type == "mock"

    def test_parse_by_status(self, parser: TaskParser, sample_tasks: list[Task]) -> None:
        """Test parsing tasks by status."""
        # Get open tasks
        open_entities = parser.parse_by_status(TaskStatus.OPEN)
        assert len(open_entities) == 2  # 1 epic + 1 task

        # Get in-progress tasks
        in_progress_entities = parser.parse_by_status(TaskStatus.IN_PROGRESS)
        assert len(in_progress_entities) == 3  # 1 epic + 2 tasks

        # Get closed tasks
        closed_entities = parser.parse_by_status(TaskStatus.CLOSED)
        assert len(closed_entities) == 1

    def test_parse_by_epic(self, parser: TaskParser) -> None:
        """Test parsing tasks by epic."""
        entities = parser.parse_by_epic("cub-001")

        # Should get all tasks under cub-001
        assert len(entities) == 4
        assert all(e.epic_id == "cub-001" for e in entities)
        assert all(e.type == EntityType.TASK for e in entities)

    def test_parse_epics_only(self, parser: TaskParser) -> None:
        """Test parsing only epics."""
        entities = parser.parse_epics_only()

        # Should get only epics
        assert len(entities) == 2
        assert all(e.type == EntityType.EPIC for e in entities)
        assert entities[0].id == "cub-001"
        assert entities[1].id == "cub-002"

    def test_checksum_computation(self, parser: TaskParser) -> None:
        """Test checksum computation for change detection."""
        task1 = Task(id="task-1", title="Test Task")
        task2 = Task(id="task-1", title="Test Task")
        task3 = Task(id="task-1", title="Modified Task")

        checksum1 = parser._compute_checksum(task1)
        checksum2 = parser._compute_checksum(task2)
        checksum3 = parser._compute_checksum(task3)

        # Same task should have same checksum
        assert checksum1 == checksum2

        # Modified task should have different checksum
        assert checksum1 != checksum3

    def test_priority_mapping(self, parser: TaskParser) -> None:
        """Test priority mapping from TaskPriority to numeric."""
        test_cases = [
            (TaskPriority.P0, 0),
            (TaskPriority.P1, 1),
            (TaskPriority.P2, 2),
            (TaskPriority.P3, 3),
            (TaskPriority.P4, 4),
        ]

        for task_priority, expected_numeric in test_cases:
            task = Task(
                id="task-1",
                title="Test",
                priority=task_priority,
            )
            checksum = parser._compute_checksum(task)
            entity = parser._task_to_entity(task, checksum)
            assert entity.priority == expected_numeric

    def test_timestamps_preserved(self, parser: TaskParser) -> None:
        """Test that timestamps are preserved in entity."""
        created = datetime(2024, 1, 1, 10, 0, 0)
        updated = datetime(2024, 1, 2, 11, 0, 0)
        closed = datetime(2024, 1, 3, 12, 0, 0)

        task = Task(
            id="task-1",
            title="Test",
            status=TaskStatus.CLOSED,
            created_at=created,
            updated_at=updated,
            closed_at=closed,
        )
        checksum = parser._compute_checksum(task)
        entity = parser._task_to_entity(task, checksum)

        assert entity.created_at == created
        assert entity.updated_at == updated
        assert entity.completed_at == closed

    def test_backend_error_handling(self) -> None:
        """Test error handling when backend fails."""
        # Create backend that raises error
        error_backend = Mock(spec=MockTaskBackend)
        error_backend.backend_name = "error"
        error_backend.list_tasks.side_effect = RuntimeError("Backend error")

        parser = TaskParser(backend=error_backend)

        # The parser now catches errors for individual status fetches and continues,
        # logging warnings but returning whatever tasks it could fetch.
        # When all fetches fail, it returns an empty list rather than raising.
        result = parser.parse_all()
        assert result == []

    def test_empty_backend(self) -> None:
        """Test parsing with empty backend."""
        empty_backend = MockTaskBackend(tasks=[])
        parser = TaskParser(backend=empty_backend)

        entities = parser.parse_all()
        assert len(entities) == 0

    def test_review_label_variants(self, parser: TaskParser) -> None:
        """Test that both 'pr' and 'review' labels trigger review stage."""
        task_pr = Task(
            id="task-1",
            title="Test",
            status=TaskStatus.IN_PROGRESS,
            labels=["pr"],
        )
        task_review = Task(
            id="task-2",
            title="Test",
            status=TaskStatus.IN_PROGRESS,
            labels=["review"],
        )

        stage_pr = parser._compute_stage(task_pr)
        stage_review = parser._compute_stage(task_review)

        assert stage_pr == Stage.NEEDS_REVIEW
        assert stage_review == Stage.NEEDS_REVIEW

    def test_frontmatter_preservation(self, parser: TaskParser) -> None:
        """Test that task data is preserved in frontmatter."""
        task = Task(
            id="task-1",
            title="Test Task",
            description="Test description",
            labels=["test"],
            depends_on=["task-0"],
        )
        checksum = parser._compute_checksum(task)
        entity = parser._task_to_entity(task, checksum)

        assert entity.frontmatter is not None
        assert entity.frontmatter["id"] == "task-1"
        assert entity.frontmatter["title"] == "Test Task"
        assert "test" in entity.frontmatter["labels"]
