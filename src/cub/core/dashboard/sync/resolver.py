"""
Relationship resolver and stage computation for the dashboard sync layer.

The RelationshipResolver links entities via explicit markers (spec_id, plan_id,
epic_id) and creates Relationship objects. The compute_stage() function determines
the correct stage for each entity based on multiple signals.

Stage Computation Logic:
1. CAPTURES: Capture-type entities
2. RESEARCHING: Specs in researching stage
3. PLANNED: Specs in planned stage, Plan entities
4. BLOCKED: Tasks/epics with status=open but have blocking dependencies
5. READY: Tasks with status=open and no blockers
6. IN_PROGRESS: Tasks/specs with status=in_progress
7. NEEDS_REVIEW: Tasks with 'pr' or 'review' label
8. COMPLETE: Tasks with ledger entry (closed but not released)
9. RELEASED: Tasks/specs in CHANGELOG

Relationship Types:
- SPEC_TO_PLAN: Spec -> Plan (via plan.spec_id)
- PLAN_TO_EPIC: Plan -> Epic (via epic.plan_id or plan.epic_id)
- EPIC_TO_TASK: Epic -> Task (via task.epic_id or task.parent_id)
- TASK_TO_LEDGER: Task -> Ledger entry (same ID)
- TASK_TO_RELEASE: Task -> Release (via CHANGELOG)
- DEPENDS_ON: Task -> Task (via dependencies)
"""

import logging
from pathlib import Path
from typing import Any

from cub.core.dashboard.db.models import (
    DashboardEntity,
    EntityType,
    Relationship,
    RelationType,
    Stage,
)
from cub.core.dashboard.sync.parsers.changelog import ChangelogParser
from cub.core.ledger.models import LedgerIndex
from cub.core.ledger.reader import LedgerReader

logger = logging.getLogger(__name__)


class RelationshipResolverError(Exception):
    """Base exception for relationship resolver errors."""

    pass


class RelationshipResolver:
    """
    Resolver for creating relationships between dashboard entities.

    The RelationshipResolver processes parsed entities and creates explicit
    Relationship objects based on markers like spec_id, plan_id, and epic_id.

    Example:
        >>> resolver = RelationshipResolver(
        ...     changelog_path=Path("CHANGELOG.md"),
        ...     ledger_path=Path(".cub/ledger")
        ... )
        >>> entities = [spec_entity, plan_entity, task_entity]
        >>> resolved_entities, relationships = resolver.resolve(entities)
        >>> for rel in relationships:
        ...     print(f"{rel.source_id} -> {rel.target_id} ({rel.rel_type.value})")
    """

    def __init__(
        self,
        changelog_path: Path | None = None,
        ledger_path: Path | None = None,
    ) -> None:
        """
        Initialize the RelationshipResolver.

        Args:
            changelog_path: Path to CHANGELOG.md for release detection
            ledger_path: Path to .cub/ledger directory for ledger data
        """
        self.changelog_path = changelog_path
        self.ledger_path = ledger_path

        # Lazy-loaded data
        self._released_task_ids: set[str] | None = None
        self._ledger_entries: dict[str, LedgerIndex] | None = None

    def _get_released_task_ids(self) -> set[str]:
        """
        Get the set of task IDs that have been released.

        Caches the result for repeated calls.

        Returns:
            Set of released task IDs (normalized to lowercase)
        """
        if self._released_task_ids is None:
            if self.changelog_path and self.changelog_path.exists():
                parser = ChangelogParser(self.changelog_path)
                self._released_task_ids = parser.get_released_task_ids()
            else:
                self._released_task_ids = set()

        return self._released_task_ids

    def _get_ledger_entries(self) -> dict[str, LedgerIndex]:
        """
        Get ledger entries indexed by task ID.

        Caches the result for repeated calls.

        Returns:
            Dict mapping task ID to LedgerIndex
        """
        if self._ledger_entries is None:
            self._ledger_entries = {}

            if self.ledger_path:
                reader = LedgerReader(self.ledger_path)
                if reader.exists():
                    entries = reader.list_tasks()
                    for entry in entries:
                        self._ledger_entries[entry.id.lower()] = entry

        return self._ledger_entries

    def _is_released(self, entity_id: str) -> bool:
        """
        Check if an entity has been released.

        Args:
            entity_id: Entity ID to check

        Returns:
            True if entity is in CHANGELOG
        """
        released_ids = self._get_released_task_ids()
        return entity_id.lower() in released_ids

    def _get_ledger_entry(self, entity_id: str) -> LedgerIndex | None:
        """
        Get ledger entry for an entity.

        Args:
            entity_id: Entity ID to look up

        Returns:
            LedgerIndex if found, None otherwise
        """
        entries = self._get_ledger_entries()
        return entries.get(entity_id.lower())

    def _has_blockers(self, entity: DashboardEntity, entity_index: dict[str, DashboardEntity]) -> bool:
        """
        Check if an entity has unresolved blockers.

        An entity is blocked if it has dependencies (depends_on) that are not yet completed.

        Args:
            entity: Entity to check for blockers
            entity_index: Dict mapping entity ID to entity for dependency lookup

        Returns:
            True if entity has unresolved blockers
        """
        # Check if entity has depends_on in frontmatter
        if not entity.frontmatter:
            return False

        depends_on = entity.frontmatter.get("depends_on") or entity.frontmatter.get("dependsOn")
        if not depends_on:
            return False

        # If depends_on is a list, check if any dependencies are not completed
        if isinstance(depends_on, list):
            for dep_id in depends_on:
                # Normalize dep_id if it's a dict
                if isinstance(dep_id, dict):
                    dep_id = dep_id.get("id") or dep_id.get("depends_on_id")
                    if not dep_id:
                        continue

                # Check if dependency exists and is not completed
                dep_entity = entity_index.get(dep_id)
                if dep_entity:
                    # If dependency is NOT closed, we're blocked
                    if dep_entity.status != "closed":
                        return True
                else:
                    # If dependency doesn't exist in our index, assume it's external and blocking
                    return True

        return False

    def _build_entity_index(self, entities: list[DashboardEntity]) -> dict[str, DashboardEntity]:
        """
        Build an index of entities by ID for quick lookup.

        Args:
            entities: List of entities to index

        Returns:
            Dict mapping entity ID to entity
        """
        return {entity.id: entity for entity in entities}

    def _create_relationships(
        self,
        entities: list[DashboardEntity],
        entity_index: dict[str, DashboardEntity],
    ) -> list[Relationship]:
        """
        Create relationships between entities based on explicit markers.

        Relationship creation logic:
        1. spec_id -> creates SPEC_TO_PLAN or reference relationship
        2. plan_id -> creates PLAN_TO_EPIC relationship
        3. epic_id -> creates EPIC_TO_TASK relationship
        4. parent_id -> creates CONTAINS relationship
        5. ledger entries -> creates TASK_TO_LEDGER relationship
        6. CHANGELOG -> creates TASK_TO_RELEASE relationship

        Args:
            entities: List of entities
            entity_index: Dict mapping entity ID to entity

        Returns:
            List of Relationship objects
        """
        relationships: list[Relationship] = []
        seen_rels: set[tuple[str, str, str]] = set()

        def add_relationship(
            source_id: str,
            target_id: str,
            rel_type: RelationType,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            """Add relationship if not already seen."""
            key = (source_id, target_id, rel_type.value)
            if key not in seen_rels:
                seen_rels.add(key)
                relationships.append(
                    Relationship(
                        source_id=source_id,
                        target_id=target_id,
                        rel_type=rel_type,
                        metadata=metadata,
                    )
                )

        for entity in entities:
            # SPEC_TO_PLAN: If entity has spec_id and is a plan-type entity
            if entity.spec_id and entity.spec_id in entity_index:
                if entity.type in (EntityType.PLAN,):
                    add_relationship(entity.spec_id, entity.id, RelationType.SPEC_TO_PLAN)
                elif entity.type in (EntityType.EPIC, EntityType.TASK):
                    # Tasks/epics can also reference specs
                    add_relationship(entity.spec_id, entity.id, RelationType.REFERENCES)

            # PLAN_TO_EPIC: If entity has plan_id and is an epic
            if entity.plan_id and entity.plan_id in entity_index:
                if entity.type == EntityType.EPIC:
                    add_relationship(entity.plan_id, entity.id, RelationType.PLAN_TO_EPIC)

            # EPIC_TO_TASK: If entity has epic_id and is a task
            if entity.epic_id and entity.epic_id in entity_index:
                if entity.type == EntityType.TASK:
                    add_relationship(entity.epic_id, entity.id, RelationType.EPIC_TO_TASK)

            # CONTAINS: If entity has parent_id (general containment)
            if entity.parent_id and entity.parent_id in entity_index:
                parent = entity_index[entity.parent_id]
                if parent.type == EntityType.EPIC and entity.type == EntityType.TASK:
                    add_relationship(entity.parent_id, entity.id, RelationType.EPIC_TO_TASK)
                else:
                    add_relationship(entity.parent_id, entity.id, RelationType.CONTAINS)

            # TASK_TO_LEDGER: If entity has ledger entry
            ledger_entry = self._get_ledger_entry(entity.id)
            if ledger_entry:
                # Create a virtual ledger entity ID
                ledger_id = f"ledger:{entity.id}"
                add_relationship(entity.id, ledger_id, RelationType.TASK_TO_LEDGER)

            # TASK_TO_RELEASE: If entity is in CHANGELOG
            if self._is_released(entity.id):
                # Create a virtual release entity ID
                release_id = f"release:{entity.id}"
                add_relationship(entity.id, release_id, RelationType.TASK_TO_RELEASE)

            # DEPENDS_ON: Check frontmatter for dependencies
            if entity.frontmatter and "dependencies" in entity.frontmatter:
                deps = entity.frontmatter.get("dependencies", [])
                if isinstance(deps, list):
                    for dep in deps:
                        if isinstance(dep, dict):
                            dep_id = dep.get("depends_on_id") or dep.get("id")
                            if dep_id and dep_id in entity_index:
                                add_relationship(entity.id, dep_id, RelationType.DEPENDS_ON)
                        elif isinstance(dep, str) and dep in entity_index:
                            add_relationship(entity.id, dep, RelationType.DEPENDS_ON)

        return relationships

    def _enrich_with_ledger(self, entity: DashboardEntity) -> DashboardEntity:
        """
        Enrich an entity with ledger data (cost, tokens, verification status).

        Args:
            entity: Entity to enrich

        Returns:
            Entity with ledger data added (or unchanged if no ledger entry)
        """
        ledger_entry = self._get_ledger_entry(entity.id)
        if not ledger_entry:
            return entity

        # Create a copy with ledger data
        # We need to use model_copy to properly copy the Pydantic model
        return entity.model_copy(
            update={
                "cost_usd": ledger_entry.cost_usd,
                "tokens": ledger_entry.tokens,
                "verification_status": ledger_entry.verification,
            }
        )

    def _compute_task_counts(
        self, entities: list[DashboardEntity], entity_index: dict[str, DashboardEntity]
    ) -> dict[str, int]:
        """
        Compute task counts for epics and plans.

        Args:
            entities: List of all entities
            entity_index: Dict mapping entity ID to entity

        Returns:
            Dict mapping entity ID to task count
        """
        task_counts: dict[str, int] = {}

        for entity in entities:
            # Count tasks for epics
            if entity.type == EntityType.EPIC:
                count = sum(
                    1
                    for e in entities
                    if e.type == EntityType.TASK
                    and (e.epic_id == entity.id or e.parent_id == entity.id)
                )
                task_counts[entity.id] = count

            # Count tasks for plans (via epics or direct)
            elif entity.type == EntityType.PLAN:
                # Count epics linked to this plan
                epic_count = sum(
                    1 for e in entities if e.type == EntityType.EPIC and e.plan_id == entity.id
                )
                task_counts[f"{entity.id}:epics"] = epic_count

                # Count total tasks (direct or via epics)
                task_count = 0
                for e in entities:
                    if e.type == EntityType.TASK:
                        # Task directly linked to plan
                        if e.plan_id == entity.id:
                            task_count += 1
                        # Task linked via epic
                        elif e.epic_id or e.parent_id:
                            parent_id = e.epic_id or e.parent_id
                            if parent_id:
                                parent = entity_index.get(parent_id)
                                if parent and parent.plan_id == entity.id:
                                    task_count += 1
                task_counts[entity.id] = task_count

        return task_counts

    def resolve(
        self, entities: list[DashboardEntity]
    ) -> tuple[list[DashboardEntity], list[Relationship]]:
        """
        Resolve relationships and enrich entities with external data.

        This is the main entry point for the resolver. It:
        1. Recomputes stages based on all signals (ledger, CHANGELOG)
        2. Enriches entities with ledger data
        3. Computes task counts for epics and plans
        4. Creates relationship objects based on explicit markers

        Args:
            entities: List of parsed entities from all sources

        Returns:
            Tuple of (resolved_entities, relationships)
        """
        # Build initial index for task counting
        entity_index = self._build_entity_index(entities)

        # Compute task counts for epics and plans
        task_counts = self._compute_task_counts(entities, entity_index)

        # Process each entity
        resolved_entities: list[DashboardEntity] = []
        for entity in entities:
            # Check if entity has blockers
            has_blockers = self._has_blockers(entity, entity_index)

            # Recompute stage with all signals
            new_stage = compute_stage(
                entity,
                is_released=self._is_released(entity.id),
                has_ledger=self._get_ledger_entry(entity.id) is not None,
                has_blockers=has_blockers,
            )

            # Enrich with ledger data
            enriched = self._enrich_with_ledger(entity)

            # Update stage if changed
            if new_stage != enriched.stage:
                enriched = enriched.model_copy(update={"stage": new_stage})

            # Add task/epic counts
            updates: dict[str, Any] = {}
            if entity.type in (EntityType.EPIC, EntityType.TASK):
                if entity.id in task_counts:
                    updates["task_count"] = task_counts[entity.id]
            elif entity.type == EntityType.PLAN:
                if entity.id in task_counts:
                    updates["task_count"] = task_counts[entity.id]
                epic_key = f"{entity.id}:epics"
                if epic_key in task_counts:
                    updates["epic_count"] = task_counts[epic_key]

            if updates:
                enriched = enriched.model_copy(update=updates)

            resolved_entities.append(enriched)

        # Rebuild index with resolved entities
        resolved_index = self._build_entity_index(resolved_entities)

        # Create relationships
        relationships = self._create_relationships(resolved_entities, resolved_index)

        logger.info(
            f"Resolved {len(resolved_entities)} entities with {len(relationships)} relationships"
        )

        return resolved_entities, relationships


def compute_stage(
    entity: DashboardEntity,
    is_released: bool = False,
    has_ledger: bool = False,
    has_blockers: bool = False,
) -> Stage:
    """
    Compute the dashboard stage for an entity based on multiple signals.

    Stage computation follows this priority order:
    1. RELEASED: Entity is in CHANGELOG (highest priority for closed items)
    2. COMPLETE: Entity has ledger entry but not released
    3. NEEDS_REVIEW: Entity has 'pr' or 'review' label
    4. IN_PROGRESS: Entity status is in_progress
    5. BLOCKED: Entity status is open but has blocking dependencies (tasks/epics)
    6. READY: Entity status is open with no blockers (tasks only)
    7. PLANNED: Entity status is open (epics, plans)
    8. RESEARCHING: Spec entities in researching stage
    9. CAPTURES: Capture entities

    Args:
        entity: Entity to compute stage for
        is_released: Whether entity is in CHANGELOG
        has_ledger: Whether entity has a ledger entry
        has_blockers: Whether entity has unresolved blockers

    Returns:
        Computed Stage enum value

    Example:
        >>> entity = DashboardEntity(
        ...     id="cub-123",
        ...     type=EntityType.TASK,
        ...     title="Test",
        ...     stage=Stage.READY,  # Initial stage from parser
        ...     status="closed",
        ...     source_type="beads",
        ...     source_path="test"
        ... )
        >>> compute_stage(entity, is_released=True)
        Stage.RELEASED
        >>> compute_stage(entity, has_ledger=True)
        Stage.COMPLETE
    """
    # Check for review labels first (can apply to any status)
    labels_lower = [label.lower() for label in entity.labels]
    if "pr" in labels_lower or "review" in labels_lower:
        return Stage.NEEDS_REVIEW

    # Released takes priority for closed items
    if is_released:
        return Stage.RELEASED

    # Ledger entry means complete (but not yet released)
    if has_ledger and entity.status in ("closed", None):
        return Stage.COMPLETE

    # Handle by entity type and status
    if entity.type == EntityType.CAPTURE:
        return Stage.CAPTURES

    if entity.type == EntityType.SPEC:
        # Specs use their existing stage (set by SpecParser based on directory)
        return entity.stage

    if entity.type == EntityType.PLAN:
        # Plans are always in PLANNED stage
        return Stage.PLANNED

    if entity.type == EntityType.EPIC:
        # Epic stage based on status
        if entity.status == "closed":
            return Stage.COMPLETE
        elif entity.status == "in_progress":
            return Stage.IN_PROGRESS
        elif entity.status == "open":
            # Open epics with blockers go to BLOCKED
            if has_blockers:
                return Stage.BLOCKED
            return Stage.PLANNED
        else:
            return Stage.PLANNED

    if entity.type == EntityType.TASK:
        # Task stage based on status
        if entity.status == "closed":
            return Stage.COMPLETE
        elif entity.status == "in_progress":
            return Stage.IN_PROGRESS
        elif entity.status == "open":
            # Open tasks with blockers go to BLOCKED
            if has_blockers:
                return Stage.BLOCKED
            return Stage.READY

    # Default fallback based on existing stage
    return entity.stage
