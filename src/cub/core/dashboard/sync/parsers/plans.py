"""
Plan parser for the dashboard sync layer.

Converts plan files (.cub/sessions/*/plan.jsonl + session.json) into
DashboardEntity objects for the Kanban board. Handles:
- Parsing JSONL plan files with task definitions
- Reading session metadata from session.json
- Computing dashboard stage from plan/session status
- Extracting metadata (epic_id, priority, labels)
- Generating source checksums for incremental sync
- Handling edge cases (missing files, invalid JSON, incomplete sessions)

Stage mapping:
- Session status 'created' with plan tasks -> Stage.PLANNED
- Epic tasks (issue_type='epic') -> Stage.PLANNED (as planning entities)
- Regular tasks appear as children of epics in the task parser

Plans represent the intermediate planning stage between specs and
executable tasks. Each session can contain multiple tasks/epics.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from cub.core.dashboard.db.models import DashboardEntity, EntityType, Stage

logger = logging.getLogger(__name__)


class PlanParserError(Exception):
    """Base exception for plan parser errors."""

    pass


class PlanParser:
    """
    Parser for converting plan files into DashboardEntity objects.

    The PlanParser reads session directories from .cub/sessions/ and
    converts plan.jsonl and session.json into DashboardEntity objects
    suitable for display on the Kanban board.

    Plans show the intermediate planning stage - after a spec is
    thought through but before tasks are fully broken down and ready.

    Example:
        >>> parser = PlanParser(sessions_root=Path(".cub/sessions"))
        >>> entities = parser.parse_all()
        >>> for entity in entities:
        ...     print(f"{entity.id}: {entity.title} [{entity.stage.value}]")
    """

    # Map priority strings to dashboard priority (0=P0/highest, 4=P4/lowest)
    PRIORITY_MAPPING: dict[int, int] = {
        0: 0,  # P0 -> 0
        1: 1,  # P1 -> 1
        2: 2,  # P2 -> 2
        3: 3,  # P3 -> 3
        4: 4,  # P4 -> 4
    }

    def __init__(self, sessions_root: Path) -> None:
        """
        Initialize the PlanParser.

        Args:
            sessions_root: Root directory containing session subdirectories (e.g., .cub/sessions)
        """
        self.sessions_root = Path(sessions_root)

    def _compute_checksum(self, file_path: Path) -> str:
        """
        Compute MD5 checksum of file contents for change detection.

        Args:
            file_path: Path to the file

        Returns:
            Hex digest string of MD5 hash
        """
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def _parse_session_metadata(self, session_dir: Path) -> dict[str, Any] | None:
        """
        Parse session.json metadata file.

        Args:
            session_dir: Path to session directory

        Returns:
            Dictionary of session metadata or None if parsing fails
        """
        session_file = session_dir / "session.json"
        if not session_file.exists():
            logger.debug(f"No session.json found in {session_dir}")
            return None

        try:
            with open(session_file) as f:
                result: dict[str, Any] = json.load(f)
                return result
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {session_file}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading {session_file}: {e}")
            return None

    def _parse_plan_tasks(self, session_dir: Path) -> list[dict[str, Any]] | None:
        """
        Parse plan.jsonl file containing task definitions.

        Args:
            session_dir: Path to session directory

        Returns:
            List of task dictionaries or None if parsing fails
        """
        plan_file = session_dir / "plan.jsonl"
        if not plan_file.exists():
            logger.debug(f"No plan.jsonl found in {session_dir}")
            return None

        tasks = []
        try:
            with open(plan_file) as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        task = json.loads(line)
                        tasks.append(task)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON at {plan_file}:{line_num}: {e}")
                        continue

            return tasks if tasks else None

        except Exception as e:
            logger.error(f"Error reading {plan_file}: {e}")
            return None

    def _map_priority(self, task: dict[str, Any]) -> int:
        """
        Map task priority to dashboard priority level.

        Args:
            task: Task dictionary from plan.jsonl

        Returns:
            Priority level (0=P0/highest, 4=P4/lowest)
        """
        priority = task.get("priority", 2)
        return self.PRIORITY_MAPPING.get(priority, 2)

    def _extract_labels(self, task: dict[str, Any]) -> list[str]:
        """
        Extract labels from task metadata.

        Args:
            task: Task dictionary from plan.jsonl

        Returns:
            List of label strings
        """
        labels = task.get("labels", [])
        if isinstance(labels, list):
            return labels
        return []

    def _create_description_excerpt(self, task: dict[str, Any]) -> str | None:
        """
        Create a brief description excerpt for card display.

        Args:
            task: Task dictionary from plan.jsonl

        Returns:
            Brief excerpt (max 100 chars) or None
        """
        description = task.get("description")
        if description and isinstance(description, str):
            excerpt: str = description.strip()
            if len(excerpt) > 100:
                return str(excerpt[:97] + "...")
            return str(excerpt)
        return None

    def _task_to_entity(
        self,
        task: dict[str, Any],
        session_metadata: dict[str, Any],
        session_dir: Path,
        checksum: str,
    ) -> DashboardEntity | None:
        """
        Convert a task from plan.jsonl to a DashboardEntity.

        Only converts epic tasks to entities. Regular tasks will be
        handled by the task parser once they're in the task backend.

        Args:
            task: Task dictionary from plan.jsonl
            session_metadata: Session metadata from session.json
            session_dir: Path to session directory
            checksum: Combined checksum of session.json + plan.jsonl

        Returns:
            DashboardEntity for epic tasks, None for regular tasks
        """
        # Only create entities for epics at the plan stage
        # Regular tasks will be handled by the task parser
        issue_type = task.get("issue_type", "task")
        if issue_type != "epic":
            return None

        task_id = task.get("id")
        if not task_id:
            logger.warning(f"Task missing id in {session_dir}")
            return None

        title = task.get("title", task_id)
        description = task.get("description")
        status = task.get("status", "open")

        # Plans are in the PLANNED stage (planning complete, not yet ready to work)
        stage = Stage.PLANNED

        # Extract timestamps
        created_at = None
        updated_at = None

        # Try to parse created/updated from session metadata
        if session_created := session_metadata.get("created"):
            try:
                created_at = datetime.fromisoformat(session_created.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        if session_updated := session_metadata.get("updated"):
            try:
                updated_at = datetime.fromisoformat(session_updated.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Get epic_id from session metadata if present
        epic_id = session_metadata.get("epic_id")

        # Get spec_id if task references a spec (not common, but possible)
        spec_id = task.get("spec_id")

        # Extract card metadata
        description_excerpt = self._create_description_excerpt(task)

        return DashboardEntity(
            id=task_id,
            type=EntityType.PLAN,
            title=title,
            description=description,
            stage=stage,
            status=status,
            priority=self._map_priority(task),
            labels=self._extract_labels(task),
            created_at=created_at,
            updated_at=updated_at,
            completed_at=None,
            parent_id=None,
            spec_id=spec_id,
            plan_id=session_metadata.get("id"),  # Link to session/plan
            epic_id=epic_id,
            cost_usd=None,
            tokens=None,
            duration_seconds=None,
            verification_status=None,
            source_type="plan",
            source_path=str(session_dir / "plan.jsonl"),
            source_checksum=checksum,
            content=description,
            frontmatter=task,  # Store full task dict as frontmatter
            # Card metadata (epic_count computed during resolution)
            description_excerpt=description_excerpt,
        )

    def parse_session(self, session_dir: Path) -> list[DashboardEntity]:
        """
        Parse a single session directory into DashboardEntity objects.

        Handles edge cases:
        - Missing session.json: Uses defaults
        - Missing plan.jsonl: Returns empty list
        - Invalid JSON: Logs warning and skips
        - Empty files: Returns empty list

        Args:
            session_dir: Path to the session directory

        Returns:
            List of DashboardEntity objects (may be empty)
        """
        entities: list[DashboardEntity] = []

        if not session_dir.is_dir():
            logger.debug(f"Not a directory: {session_dir}")
            return entities

        # Parse session metadata
        session_metadata = self._parse_session_metadata(session_dir)
        if not session_metadata:
            logger.debug(f"No valid session metadata in {session_dir}")
            # Use directory name as fallback session ID
            session_metadata = {"id": session_dir.name}

        # Parse plan tasks
        tasks = self._parse_plan_tasks(session_dir)
        if not tasks:
            logger.debug(f"No tasks found in {session_dir}")
            return entities

        # Compute combined checksum for incremental sync
        # Combine both session.json and plan.jsonl checksums
        checksums = []
        session_file = session_dir / "session.json"
        plan_file = session_dir / "plan.jsonl"

        if session_file.exists():
            checksums.append(self._compute_checksum(session_file))
        if plan_file.exists():
            checksums.append(self._compute_checksum(plan_file))

        combined_checksum = hashlib.md5("|".join(checksums).encode()).hexdigest()

        # Convert tasks to entities
        for task in tasks:
            entity = self._task_to_entity(task, session_metadata, session_dir, combined_checksum)
            if entity:
                entities.append(entity)

        return entities

    def parse_all(self) -> list[DashboardEntity]:
        """
        Parse all session directories.

        Scans all subdirectories under sessions_root and parses
        each as a session directory.

        Returns:
            List of DashboardEntity objects, sorted by ID
        """
        entities: list[DashboardEntity] = []

        if not self.sessions_root.exists():
            logger.warning(f"Sessions root not found: {self.sessions_root}")
            return entities

        # Scan all session directories
        for session_dir in sorted(self.sessions_root.iterdir()):
            if not session_dir.is_dir():
                continue

            session_entities = self.parse_session(session_dir)
            entities.extend(session_entities)

        # Sort by ID for consistent ordering
        entities.sort(key=lambda e: e.id)

        logger.info(f"Parsed {len(entities)} plan entities from {self.sessions_root}")
        return entities
