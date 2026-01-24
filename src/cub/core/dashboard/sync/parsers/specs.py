"""
Spec parser for the dashboard sync layer.

Converts spec files (specs/**/*.md) into DashboardEntity objects
for the Kanban board. Handles:
- Parsing markdown files with YAML frontmatter
- Computing dashboard stage from spec stage
- Extracting metadata (priority, labels, timestamps)
- Generating source checksums for incremental sync
- Handling edge cases (missing frontmatter, invalid YAML, empty files)

Stage mapping:
- specs/researching/ -> Stage.RESEARCHING
- specs/planned/ -> Stage.PLANNED
- specs/staged/ -> Stage.READY (tasks staged, ready to work)
- specs/implementing/ -> Stage.IN_PROGRESS
- specs/released/ -> Stage.RELEASED
"""

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path

import frontmatter  # type: ignore[import-untyped]
import yaml

from cub.core.dashboard.db.models import DashboardEntity, EntityType, Stage
from cub.core.specs import Spec
from cub.core.specs import Stage as SpecStage

logger = logging.getLogger(__name__)


class SpecParserError(Exception):
    """Base exception for spec parser errors."""

    pass


class SpecParser:
    """
    Parser for converting spec files into DashboardEntity objects.

    The SpecParser reads markdown files from specs/ directories and
    converts them to DashboardEntity objects suitable for display on
    the Kanban board.

    Example:
        >>> parser = SpecParser(specs_root=Path("./specs"))
        >>> entities = parser.parse_all()
        >>> for entity in entities:
        ...     print(f"{entity.id}: {entity.title} [{entity.stage.value}]")
    """

    # Map spec stage to dashboard stage
    STAGE_MAPPING: dict[SpecStage, Stage] = {
        SpecStage.RESEARCHING: Stage.RESEARCHING,
        SpecStage.PLANNED: Stage.PLANNED,
        SpecStage.STAGED: Stage.READY,
        SpecStage.IMPLEMENTING: Stage.IN_PROGRESS,
        SpecStage.RELEASED: Stage.RELEASED,
    }

    # Map spec priority to dashboard priority (0=P0/highest, 4=P4/lowest)
    PRIORITY_MAPPING: dict[str, int] = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }

    def __init__(self, specs_root: Path) -> None:
        """
        Initialize the SpecParser.

        Args:
            specs_root: Root directory containing stage subdirectories (e.g., ./specs)
        """
        self.specs_root = Path(specs_root)

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

    def _map_priority(self, spec: Spec) -> int:
        """
        Map spec priority to dashboard priority level.

        Args:
            spec: Spec object

        Returns:
            Priority level (0=P0/highest, 4=P4/lowest)
        """
        return self.PRIORITY_MAPPING.get(spec.priority.value, 2)

    def _extract_labels(self, spec: Spec) -> list[str]:
        """
        Extract labels from spec metadata.

        Combines:
        - complexity:<value>
        - status:<value> (if present)
        - Dependencies and blocks are stored as relationships, not labels

        Args:
            spec: Spec object

        Returns:
            List of label strings
        """
        labels: list[str] = []

        # Add complexity label
        labels.append(f"complexity:{spec.complexity.value}")

        # Add status label if present
        if spec.status:
            labels.append(f"status:{spec.status.value}")

        return labels

    def _extract_readiness_score(self, spec: Spec) -> float | None:
        """
        Extract readiness score from spec as a normalized 0.0-1.0 value.

        Args:
            spec: Spec object

        Returns:
            Readiness score normalized to 0.0-1.0, or None if not available
        """
        if spec.readiness and spec.readiness.score is not None:
            # Normalize from 0-10 scale to 0.0-1.0
            return spec.readiness.score / 10.0
        return None

    def _count_notes(self, spec: Spec) -> int:
        """
        Count the number of notes/comments in the spec.

        Currently counts:
        - Blockers in readiness
        - Questions in readiness
        - Decisions needed in readiness
        - Notes field presence

        Args:
            spec: Spec object

        Returns:
            Count of note items
        """
        count = 0
        if spec.readiness:
            count += len(spec.readiness.blockers)
            count += len(spec.readiness.questions)
            count += len(spec.readiness.decisions_needed)
        if spec.notes:
            count += 1  # Count the notes field itself as one item
        return count

    def _create_description_excerpt(self, spec: Spec) -> str | None:
        """
        Create a brief description excerpt for card display.

        Args:
            spec: Spec object

        Returns:
            Brief excerpt (max 100 chars) or None
        """
        # Try notes field first
        if spec.notes:
            excerpt = spec.notes.strip()
            if len(excerpt) > 100:
                return excerpt[:97] + "..."
            return excerpt
        return None

    def _spec_to_entity(self, spec: Spec, checksum: str) -> DashboardEntity:
        """
        Convert a Spec object to a DashboardEntity.

        Args:
            spec: Parsed Spec object
            checksum: File content checksum

        Returns:
            DashboardEntity suitable for board display
        """
        # Compute dashboard stage from spec stage
        dashboard_stage = self.STAGE_MAPPING.get(spec.stage, Stage.RESEARCHING)

        # Extract title (prefer title from markdown heading, fallback to name)
        title = spec.title if spec.title else spec.name

        # Convert dates to datetime
        created_at = datetime.combine(spec.created, datetime.min.time()) if spec.created else None
        updated_at = datetime.combine(spec.updated, datetime.min.time()) if spec.updated else None

        # Read full content for detail view
        content = spec.path.read_text() if spec.path.exists() else None

        # Extract card metadata
        readiness_score = self._extract_readiness_score(spec)
        notes_count = self._count_notes(spec)
        description_excerpt = self._create_description_excerpt(spec)

        return DashboardEntity(
            id=spec.name,
            type=EntityType.SPEC,
            title=title,
            description=spec.notes,
            stage=dashboard_stage,
            status=spec.status.value if spec.status else None,
            priority=self._map_priority(spec),
            labels=self._extract_labels(spec),
            created_at=created_at,
            updated_at=updated_at,
            completed_at=None,  # Specs don't have completion timestamps
            parent_id=None,  # Specs are top-level entities
            spec_id=spec.name,  # Self-reference for relationship tracking
            plan_id=None,  # Will be linked by plan parser
            epic_id=None,  # Not applicable to specs
            cost_usd=None,  # Metrics come from ledger
            tokens=None,
            duration_seconds=None,
            verification_status=None,
            source_type="file",
            source_path=str(spec.path),
            source_checksum=checksum,
            content=content,
            frontmatter=spec.to_frontmatter_dict(),
            # Card metadata
            readiness_score=readiness_score,
            notes_count=notes_count,
            description_excerpt=description_excerpt,
        )

    def parse_file(self, file_path: Path, stage: SpecStage) -> DashboardEntity | None:
        """
        Parse a single spec file into a DashboardEntity.

        Handles edge cases gracefully:
        - Missing frontmatter: Creates entity with defaults
        - Invalid YAML: Logs warning and uses defaults
        - Empty files: Returns None
        - Malformed content: Returns partial entity
        - Missing frontmatter delimiters: Treats as no frontmatter
        - Null/empty frontmatter fields: Uses safe defaults

        Args:
            file_path: Path to the spec markdown file
            stage: Stage derived from directory location

        Returns:
            DashboardEntity or None if file is empty/unparseable
        """
        try:
            # Check if file exists
            if not file_path.exists():
                logger.warning(f"Spec file not found: {file_path}")
                return None

            # Check if file is empty
            if file_path.stat().st_size == 0:
                logger.warning(f"Empty spec file: {file_path}")
                return None

            # Read file content for parsing
            try:
                raw_content = file_path.read_text(encoding='utf-8')
            except UnicodeDecodeError as e:
                logger.warning(f"Unable to read {file_path} as UTF-8: {e}. Skipping.")
                return None
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return None

            # Compute checksum for incremental sync
            checksum = self._compute_checksum(file_path)

            # Parse frontmatter with comprehensive error handling
            post = None
            try:
                post = frontmatter.load(file_path)
            except yaml.YAMLError as e:
                logger.warning(
                    f"Invalid YAML frontmatter in {file_path}: {e}. "
                    f"Using defaults and treating entire file as content."
                )
                # Create minimal post with empty metadata
                post = frontmatter.Post(content=raw_content, metadata={})
            except Exception as e:
                logger.warning(
                    f"Error parsing frontmatter in {file_path}: {e}. "
                    f"Treating file as plain markdown."
                )
                # Treat entire file as content
                post = frontmatter.Post(content=raw_content, metadata={})

            # Ensure metadata is a dict (handle null frontmatter)
            if post.metadata is None:
                logger.debug(f"Null frontmatter in {file_path}, using empty dict")
                post.metadata = {}
            elif not isinstance(post.metadata, dict):
                logger.warning(
                    f"Frontmatter in {file_path} is not a dict "
                    f"(got {type(post.metadata).__name__}). Using empty dict."
                )
                post.metadata = {}

            # Get spec name from filename
            name = file_path.stem

            # Extract title from first markdown heading if present
            title: str | None = None
            content = post.content
            if content:
                # Match first # heading
                match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
                if match:
                    title = match.group(1).strip()

            # Parse spec using existing Spec.from_frontmatter_dict
            # This handles all the complex parsing and validation
            try:
                spec = Spec.from_frontmatter_dict(
                    data=post.metadata,
                    name=name,
                    path=file_path,
                    stage=stage,
                    title=title,
                )
            except Exception as e:
                logger.error(
                    f"Failed to parse spec {file_path}: {e}. "
                    f"This spec will be excluded from the dashboard."
                )
                return None

            # Convert to DashboardEntity
            return self._spec_to_entity(spec, checksum)

        except FileNotFoundError:
            logger.warning(f"Spec file disappeared during parsing: {file_path}")
            return None
        except PermissionError as e:
            logger.error(f"Permission denied reading {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error parsing {file_path}: {type(e).__name__}: {e}. "
                f"This spec will be excluded from the dashboard."
            )
            return None

    def parse_all(self) -> list[DashboardEntity]:
        """
        Parse all spec files across all stage directories.

        Scans all stage directories under specs_root and parses
        each .md file into a DashboardEntity.

        Returns:
            List of DashboardEntity objects, sorted by name
        """
        entities: list[DashboardEntity] = []

        if not self.specs_root.exists():
            logger.warning(f"Specs root not found: {self.specs_root}")
            return entities

        # Scan each stage directory
        for stage in SpecStage:
            stage_dir = self.specs_root / stage.value
            if not stage_dir.exists():
                logger.debug(f"Stage directory not found: {stage_dir}")
                continue

            # Parse all .md files in this stage
            for spec_file in stage_dir.glob("*.md"):
                entity = self.parse_file(spec_file, stage)
                if entity:
                    entities.append(entity)

        # Sort by name for consistent ordering
        entities.sort(key=lambda e: e.id)

        logger.info(f"Parsed {len(entities)} specs from {self.specs_root}")
        return entities

    def parse_stage(self, stage: SpecStage) -> list[DashboardEntity]:
        """
        Parse all spec files in a specific stage directory.

        Args:
            stage: Stage to parse (e.g., SpecStage.PLANNED)

        Returns:
            List of DashboardEntity objects from that stage
        """
        entities: list[DashboardEntity] = []
        stage_dir = self.specs_root / stage.value

        if not stage_dir.exists():
            logger.warning(f"Stage directory not found: {stage_dir}")
            return entities

        for spec_file in stage_dir.glob("*.md"):
            entity = self.parse_file(spec_file, stage)
            if entity:
                entities.append(entity)

        entities.sort(key=lambda e: e.id)
        return entities
