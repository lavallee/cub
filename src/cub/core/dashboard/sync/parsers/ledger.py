"""
Ledger parser for the dashboard sync layer.

Converts ledger entries from .cub/ledger/ into DashboardEntity objects
for the Kanban board. Handles:
- Reading from index.jsonl for fast enumeration
- Loading full ledger JSON files for detailed metrics
- Computing dashboard stage from workflow stage
- Extracting cost, token, and verification metrics
- Handling both task and epic ledger entries

Stage mapping:
- workflow.stage='dev_complete' -> Stage.COMPLETE
- workflow.stage='needs_review' -> Stage.NEEDS_REVIEW
- workflow.stage='validated' -> Stage.VALIDATED
- workflow.stage='released' -> Stage.RELEASED
"""

import hashlib
import json
import logging
from pathlib import Path

from cub.core.dashboard.db.models import DashboardEntity, EntityType, Stage
from cub.core.ledger.models import LedgerEntry, LedgerIndex

logger = logging.getLogger(__name__)


class LedgerParserError(Exception):
    """Base exception for ledger parser errors."""

    pass


class LedgerParser:
    """
    Parser for converting ledger entries into DashboardEntity objects.

    The LedgerParser reads from .cub/ledger/index.jsonl for fast lookups
    and loads full JSON files from by-task/ when detailed metrics are needed.

    Example:
        >>> from pathlib import Path
        >>> parser = LedgerParser(ledger_dir=Path(".cub/ledger"))
        >>> entities = parser.parse()
        >>> for entity in entities:
        ...     print(f"{entity.id}: {entity.title} [{entity.stage.value}]")
    """

    def __init__(self, ledger_dir: Path) -> None:
        """
        Initialize the LedgerParser.

        Args:
            ledger_dir: Path to .cub/ledger directory
        """
        self.ledger_dir = ledger_dir
        self.index_file = ledger_dir / "index.jsonl"
        self.by_task_dir = ledger_dir / "by-task"

    def _read_index(self) -> list[LedgerIndex]:
        """
        Read all entries from index.jsonl.

        Returns:
            List of LedgerIndex entries
        """
        if not self.index_file.exists():
            return []

        entries: list[LedgerIndex] = []
        with open(self.index_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        entry = LedgerIndex.model_validate(data)
                        entries.append(entry)
                    except Exception as e:
                        logger.warning(f"Error parsing index line: {e}")
                        continue
        return entries

    def _load_full_entry(self, task_id: str) -> LedgerEntry | None:
        """
        Load full ledger entry from JSON file.

        Args:
            task_id: Task ID to load

        Returns:
            Full LedgerEntry or None if not found
        """
        task_file = self.by_task_dir / f"{task_id}.json"
        if not task_file.exists():
            return None

        try:
            with open(task_file, encoding="utf-8") as f:
                data = json.load(f)
                return LedgerEntry.model_validate(data)
        except Exception as e:
            logger.error(f"Error loading ledger entry {task_id}: {e}")
            return None

    def _compute_checksum(self, entry: LedgerEntry) -> str:
        """
        Compute checksum for ledger entry for change detection.

        Uses a hash of the entry's serialized JSON to detect changes.

        Args:
            entry: LedgerEntry object

        Returns:
            Hex digest string of MD5 hash
        """
        # Serialize entry to JSON and compute hash
        entry_json = entry.model_dump_json(exclude_none=True, by_alias=True)
        return hashlib.md5(entry_json.encode()).hexdigest()

    def _compute_stage(self, entry: LedgerEntry) -> Stage:
        """
        Compute dashboard stage from ledger workflow stage.

        Stage logic:
        - workflow.stage='dev_complete' -> COMPLETE (default)
        - workflow.stage='needs_review' -> NEEDS_REVIEW
        - workflow.stage='validated' -> VALIDATED
        - workflow.stage='released' -> RELEASED

        Args:
            entry: LedgerEntry object

        Returns:
            Stage enum value
        """
        # Map workflow stage to dashboard stage
        workflow_stage = entry.workflow.stage

        if workflow_stage == "needs_review":
            return Stage.NEEDS_REVIEW
        elif workflow_stage == "validated":
            return Stage.VALIDATED
        elif workflow_stage == "released":
            return Stage.RELEASED
        else:
            # Default to COMPLETE for 'dev_complete' or any other value
            return Stage.COMPLETE

    def _to_dashboard_entity(self, entry: LedgerEntry, checksum: str) -> DashboardEntity:
        """
        Convert a LedgerEntry to a DashboardEntity.

        Args:
            entry: Parsed LedgerEntry object
            checksum: Entry content checksum

        Returns:
            DashboardEntity suitable for board display
        """
        # Determine entity type (ledger entries can be for tasks or epics)
        # For now, assume all ledger entries are for tasks
        # In the future, we could check if entry.id matches an epic pattern
        entity_type = EntityType.LEDGER

        # Compute dashboard stage from workflow
        dashboard_stage = self._compute_stage(entry)

        # Extract metrics from outcome (preferred) or fallback to legacy fields
        if entry.outcome:
            cost_usd = entry.outcome.total_cost_usd
            tokens = entry.tokens.total_tokens  # Legacy field still tracks total
            duration_seconds = entry.outcome.total_duration_seconds
        else:
            # Fallback to legacy fields
            cost_usd = entry.cost_usd
            tokens = entry.tokens.total_tokens
            duration_seconds = entry.duration_seconds

        # Extract verification status
        verification_status = entry.verification.status

        # Extract epic_id from lineage (preferred) or fallback to legacy field
        epic_id = entry.lineage.epic_id if entry.lineage.epic_id else entry.epic_id

        # Build source path string
        source_path = f".cub/ledger/by-task/{entry.id}.json"

        # Create brief description excerpt from task snapshot or outcome
        description = None
        if entry.task:
            description = entry.task.description
        elif entry.outcome and entry.outcome.approach:
            description = entry.outcome.approach

        description_excerpt = None
        if description:
            excerpt = description.strip()
            if len(excerpt) > 100:
                description_excerpt = excerpt[:97] + "..."
            else:
                description_excerpt = excerpt

        return DashboardEntity(
            id=entry.id,
            type=entity_type,
            title=entry.title,
            description=description,
            stage=dashboard_stage,
            status=entry.workflow.stage,
            priority=entry.task.priority if entry.task else None,
            labels=entry.task.labels if entry.task else [],
            created_at=entry.task.created_at if entry.task else None,
            updated_at=entry.workflow.stage_updated_at,
            completed_at=entry.completed_at,
            parent_id=None,  # Ledger entries don't have parent_id
            spec_id=entry.lineage.spec_file,  # Will be normalized by relationship resolver
            plan_id=entry.lineage.plan_file,  # Will be normalized by relationship resolver
            epic_id=epic_id,
            cost_usd=cost_usd,
            tokens=tokens,
            duration_seconds=duration_seconds,
            verification_status=verification_status,
            source_type="ledger",
            source_path=source_path,
            source_checksum=checksum,
            content=description,
            frontmatter=entry.model_dump(exclude_none=True, by_alias=True),
            # Card metadata
            description_excerpt=description_excerpt,
        )

    def parse(self) -> list[DashboardEntity]:
        """
        Parse all ledger entries from the ledger directory.

        Reads from index.jsonl for enumeration, then loads full JSON
        entries to extract detailed metrics. Returns DashboardEntity
        objects suitable for board display.

        Returns:
            List of DashboardEntity objects, sorted by completion date (newest first)
        """
        if not self.ledger_dir.exists():
            logger.warning(f"Ledger directory does not exist: {self.ledger_dir}")
            return []

        entities: list[DashboardEntity] = []

        try:
            # Read index for fast enumeration
            index_entries = self._read_index()

            for index_entry in index_entries:
                # Load full entry for detailed metrics
                full_entry = self._load_full_entry(index_entry.id)
                if not full_entry:
                    logger.warning(f"Could not load full entry for {index_entry.id}")
                    continue

                try:
                    checksum = self._compute_checksum(full_entry)
                    entity = self._to_dashboard_entity(full_entry, checksum)
                    entities.append(entity)
                except Exception as e:
                    logger.error(f"Error converting ledger entry {index_entry.id}: {e}")
                    continue

            # Sort by completion date (newest first)
            # Use a default datetime for None values to handle sorting
            from datetime import datetime, timezone

            def sort_key(e: DashboardEntity) -> datetime:
                return e.completed_at or e.created_at or datetime.min.replace(tzinfo=timezone.utc)

            entities.sort(key=sort_key, reverse=True)

            logger.info(f"Parsed {len(entities)} ledger entries from {self.ledger_dir}")
            return entities

        except Exception as e:
            logger.error(f"Error parsing ledger entries: {e}")
            raise LedgerParserError(f"Failed to parse ledger: {e}") from e

    def parse_by_epic(self, epic_id: str) -> list[DashboardEntity]:
        """
        Parse ledger entries for a specific epic.

        Args:
            epic_id: Epic ID to filter by

        Returns:
            List of DashboardEntity objects for tasks in that epic
        """
        all_entities = self.parse()
        return [e for e in all_entities if e.epic_id == epic_id]

    def parse_by_stage(self, stage: Stage) -> list[DashboardEntity]:
        """
        Parse ledger entries in a specific workflow stage.

        Args:
            stage: Stage to filter by

        Returns:
            List of DashboardEntity objects in that stage
        """
        all_entities = self.parse()
        return [e for e in all_entities if e.stage == stage]
