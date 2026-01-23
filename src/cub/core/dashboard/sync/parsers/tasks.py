"""
Task parser for the dashboard sync layer.

Converts tasks and epics from the task backend into DashboardEntity objects
for the Kanban board. Handles:
- Using TaskBackend abstraction to query tasks (beads or JSON)
- Computing dashboard stage from task status and labels
- Extracting metadata (priority, labels, timestamps)
- Handling both epic and regular task types
- Creating relationships between epics and their tasks

Stage mapping:
- Epic with status='open' -> Stage.PLANNED
- Epic with status='in_progress' -> Stage.IN_PROGRESS
- Task with status='open' -> Stage.READY
- Task with status='in_progress' -> Stage.IN_PROGRESS
- Task with label='pr' or 'review' -> Stage.NEEDS_REVIEW
- Task with status='closed' but no ledger -> Stage.COMPLETE
- Task in CHANGELOG -> Stage.RELEASED
"""

import hashlib
import logging

from cub.core.dashboard.db.models import DashboardEntity, EntityType, Stage
from cub.core.tasks.backend import TaskBackend
from cub.core.tasks.models import Task, TaskStatus, TaskType

logger = logging.getLogger(__name__)


class TaskParserError(Exception):
    """Base exception for task parser errors."""

    pass


class TaskParser:
    """
    Parser for converting task backend data into DashboardEntity objects.

    The TaskParser uses the TaskBackend abstraction to query tasks and epics
    from the configured backend (beads or JSON), then converts them to
    DashboardEntity objects suitable for display on the Kanban board.

    Example:
        >>> from cub.core.tasks.backend import get_backend
        >>> backend = get_backend()
        >>> parser = TaskParser(backend=backend)
        >>> entities = parser.parse_all()
        >>> for entity in entities:
        ...     print(f"{entity.id}: {entity.title} [{entity.stage.value}]")
    """

    def __init__(self, backend: TaskBackend) -> None:
        """
        Initialize the TaskParser.

        Args:
            backend: TaskBackend instance (beads, JSON, etc.)
        """
        self.backend = backend

    def _compute_checksum(self, task: Task) -> str:
        """
        Compute checksum for task data for change detection.

        Uses a hash of the task's serialized JSON to detect changes.

        Args:
            task: Task object

        Returns:
            Hex digest string of MD5 hash
        """
        # Serialize task to JSON and compute hash
        task_json = task.model_dump_json(exclude_none=True, by_alias=True)
        return hashlib.md5(task_json.encode()).hexdigest()

    def _compute_stage(self, task: Task) -> Stage:
        """
        Compute dashboard stage from task status and metadata.

        Stage logic:
        - Epics in 'open' -> PLANNED (planning stage)
        - Epics in 'in_progress' -> IN_PROGRESS
        - Tasks in 'open' -> READY (ready to work)
        - Tasks in 'in_progress' -> IN_PROGRESS
        - Tasks with 'pr' or 'review' label -> NEEDS_REVIEW
        - Tasks in 'closed' -> COMPLETE (or RELEASED if in changelog)

        Args:
            task: Task object

        Returns:
            Stage enum value
        """
        # Check for review labels first (highest priority)
        if task.has_label("pr") or task.has_label("review"):
            return Stage.NEEDS_REVIEW

        # Map status to stage based on task type
        if task.type == TaskType.EPIC:
            if task.status == TaskStatus.OPEN:
                return Stage.PLANNED
            elif task.status == TaskStatus.IN_PROGRESS:
                return Stage.IN_PROGRESS
            elif task.status == TaskStatus.CLOSED:
                # Closed epics go to COMPLETE (RELEASED determined by changelog)
                return Stage.COMPLETE
        else:
            # Regular tasks
            if task.status == TaskStatus.OPEN:
                return Stage.READY
            elif task.status == TaskStatus.IN_PROGRESS:
                return Stage.IN_PROGRESS
            elif task.status == TaskStatus.CLOSED:
                # Closed tasks go to COMPLETE (RELEASED determined by changelog)
                return Stage.COMPLETE

        # Default fallback
        return Stage.READY

    def _task_to_entity(self, task: Task, checksum: str) -> DashboardEntity:
        """
        Convert a Task object to a DashboardEntity.

        Args:
            task: Parsed Task object
            checksum: Task content checksum

        Returns:
            DashboardEntity suitable for board display
        """
        # Determine entity type based on task type
        entity_type = EntityType.EPIC if task.type == TaskType.EPIC else EntityType.TASK

        # Compute dashboard stage
        dashboard_stage = self._compute_stage(task)

        # Convert priority from TaskPriority to numeric (0-4)
        priority = task.priority_numeric

        # Build source path string (backend-specific)
        source_path = f"{self.backend.backend_name}:{task.id}"

        return DashboardEntity(
            id=task.id,
            type=entity_type,
            title=task.title,
            description=task.description,
            stage=dashboard_stage,
            status=task.status.value,
            priority=priority,
            labels=task.labels,
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_at=task.closed_at,
            parent_id=task.parent,
            spec_id=None,  # Will be linked by relationship resolver
            plan_id=None,  # Will be linked by relationship resolver
            epic_id=task.parent if task.type != TaskType.EPIC else None,
            cost_usd=None,  # Metrics come from ledger
            tokens=None,
            duration_seconds=None,
            verification_status=None,
            source_type=self.backend.backend_name,
            source_path=source_path,
            source_checksum=checksum,
            content=task.description,
            frontmatter=task.model_dump(exclude_none=True, by_alias=True),
        )

    def parse_all(self) -> list[DashboardEntity]:
        """
        Parse all tasks and epics from the task backend.

        Queries the backend for all tasks and converts them to
        DashboardEntity objects.

        Returns:
            List of DashboardEntity objects, sorted by ID
        """
        entities: list[DashboardEntity] = []

        try:
            # Get all tasks from backend (no status filter to get everything)
            tasks = self.backend.list_tasks()

            for task in tasks:
                try:
                    checksum = self._compute_checksum(task)
                    entity = self._task_to_entity(task, checksum)
                    entities.append(entity)
                except Exception as e:
                    logger.error(f"Error converting task {task.id}: {e}")
                    continue

            # Sort by ID for consistent ordering
            entities.sort(key=lambda e: e.id)

            logger.info(
                f"Parsed {len(entities)} tasks/epics from {self.backend.backend_name} backend"
            )
            return entities

        except Exception as e:
            logger.error(f"Error querying task backend: {e}")
            raise TaskParserError(f"Failed to parse tasks: {e}") from e

    def parse_by_status(self, status: TaskStatus) -> list[DashboardEntity]:
        """
        Parse tasks with a specific status from the task backend.

        Args:
            status: TaskStatus to filter by (OPEN, IN_PROGRESS, CLOSED)

        Returns:
            List of DashboardEntity objects for that status
        """
        entities: list[DashboardEntity] = []

        try:
            # Get tasks with specific status
            tasks = self.backend.list_tasks(status=status)

            for task in tasks:
                try:
                    checksum = self._compute_checksum(task)
                    entity = self._task_to_entity(task, checksum)
                    entities.append(entity)
                except Exception as e:
                    logger.error(f"Error converting task {task.id}: {e}")
                    continue

            entities.sort(key=lambda e: e.id)
            return entities

        except Exception as e:
            logger.error(f"Error querying task backend for status {status}: {e}")
            raise TaskParserError(f"Failed to parse tasks with status {status}: {e}") from e

    def parse_by_epic(self, epic_id: str) -> list[DashboardEntity]:
        """
        Parse all tasks belonging to a specific epic.

        Args:
            epic_id: Epic ID to filter by

        Returns:
            List of DashboardEntity objects for tasks in that epic
        """
        entities: list[DashboardEntity] = []

        try:
            # Get tasks with specific parent
            tasks = self.backend.list_tasks(parent=epic_id)

            for task in tasks:
                try:
                    checksum = self._compute_checksum(task)
                    entity = self._task_to_entity(task, checksum)
                    entities.append(entity)
                except Exception as e:
                    logger.error(f"Error converting task {task.id}: {e}")
                    continue

            entities.sort(key=lambda e: e.id)
            return entities

        except Exception as e:
            logger.error(f"Error querying task backend for epic {epic_id}: {e}")
            raise TaskParserError(f"Failed to parse tasks for epic {epic_id}: {e}") from e

    def parse_epics_only(self) -> list[DashboardEntity]:
        """
        Parse only epic entities from the task backend.

        Returns:
            List of DashboardEntity objects for epics only
        """
        entities: list[DashboardEntity] = []

        try:
            # Get all tasks and filter for epics
            tasks = self.backend.list_tasks()

            for task in tasks:
                if task.type != TaskType.EPIC:
                    continue

                try:
                    checksum = self._compute_checksum(task)
                    entity = self._task_to_entity(task, checksum)
                    entities.append(entity)
                except Exception as e:
                    logger.error(f"Error converting epic {task.id}: {e}")
                    continue

            entities.sort(key=lambda e: e.id)

            logger.info(f"Parsed {len(entities)} epics from {self.backend.backend_name} backend")
            return entities

        except Exception as e:
            logger.error(f"Error querying epics from task backend: {e}")
            raise TaskParserError(f"Failed to parse epics: {e}") from e
