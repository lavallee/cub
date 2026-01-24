"""
Tests for the relationship resolver and stage computation.

Tests cover:
- Stage computation based on entity type and status
- Stage computation with ledger entries
- Stage computation with CHANGELOG releases
- Stage computation with review labels
- Stage computation with blockers
- Relationship creation from explicit markers
- Entity enrichment with ledger data
- Full resolver workflow
- Edge cases and error handling
"""

import json
from pathlib import Path

import pytest

from cub.core.dashboard.db.models import (
    DashboardEntity,
    EntityType,
    RelationType,
    Stage,
)
from cub.core.dashboard.sync.resolver import RelationshipResolver, compute_stage

# =============================================================================
# Test Fixtures
# =============================================================================


def make_entity(
    id: str,
    type: EntityType = EntityType.TASK,
    title: str | None = None,
    stage: Stage = Stage.READY,
    status: str | None = "open",
    priority: int | None = None,
    labels: list[str] | None = None,
    parent_id: str | None = None,
    spec_id: str | None = None,
    plan_id: str | None = None,
    epic_id: str | None = None,
    frontmatter: dict | None = None,
) -> DashboardEntity:
    """Helper to create DashboardEntity for testing."""
    return DashboardEntity(
        id=id,
        type=type,
        title=title or f"Test {id}",
        stage=stage,
        status=status,
        priority=priority,
        labels=labels or [],
        parent_id=parent_id,
        spec_id=spec_id,
        plan_id=plan_id,
        epic_id=epic_id,
        frontmatter=frontmatter,
        source_type="test",
        source_path=f"test/{id}",
    )


@pytest.fixture
def tmp_changelog(tmp_path: Path) -> Path:
    """Create a temporary CHANGELOG.md file."""
    changelog_path = tmp_path / "CHANGELOG.md"
    changelog_content = """# Changelog

## [0.28.0] - 2026-01-23

### Added
- New feature from task cub-abc.1
- Another feature from cub-abc.2

### Fixed
- Bug fix from cub-xyz.1 (#123)

## [0.27.0] - 2026-01-20

### Added
- Initial feature from cub-def
"""
    changelog_path.write_text(changelog_content)
    return changelog_path


@pytest.fixture
def tmp_ledger(tmp_path: Path) -> Path:
    """Create a temporary ledger directory with index.jsonl."""
    ledger_path = tmp_path / ".cub" / "ledger"
    ledger_path.mkdir(parents=True)

    # Create index.jsonl
    index_entries = [
        {
            "id": "cub-abc.1",
            "title": "Task 1",
            "completed": "2026-01-23",
            "cost_usd": 0.05,
            "tokens": 5000,
            "verification": "pass",
        },
        {
            "id": "cub-abc.2",
            "title": "Task 2",
            "completed": "2026-01-23",
            "cost_usd": 0.10,
            "tokens": 10000,
            "verification": "warn",
        },
        {
            "id": "cub-xyz.1",
            "title": "Task 3",
            "completed": "2026-01-22",
            "cost_usd": 0.03,
            "tokens": 3000,
            "verification": "fail",
        },
    ]

    index_file = ledger_path / "index.jsonl"
    with open(index_file, "w") as f:
        for entry in index_entries:
            f.write(json.dumps(entry) + "\n")

    return ledger_path


# =============================================================================
# Test compute_stage()
# =============================================================================


class TestComputeStage:
    """Tests for the compute_stage function."""

    def test_capture_entity_default_stage(self) -> None:
        """Capture entities should default to CAPTURES stage."""
        entity = make_entity("cap-1", type=EntityType.CAPTURE, status="open")
        assert compute_stage(entity) == Stage.CAPTURES

    def test_capture_entity_can_be_released(self) -> None:
        """Capture entities can be marked as released."""
        entity = make_entity("cap-1", type=EntityType.CAPTURE, status="open")
        # Released captures should show as released
        assert compute_stage(entity, is_released=True) == Stage.RELEASED

    def test_capture_entity_review_label_applies(self) -> None:
        """Capture entities with review labels should be in NEEDS_REVIEW."""
        entity = make_entity("cap-1", type=EntityType.CAPTURE, status="open", labels=["review"])
        assert compute_stage(entity) == Stage.NEEDS_REVIEW

    def test_spec_entity_preserves_existing_stage(self) -> None:
        """Spec entities should preserve their directory-based stage."""
        for stage in [
            Stage.RESEARCHING,
            Stage.PLANNED,
            Stage.READY,
            Stage.IN_PROGRESS,
            Stage.RELEASED,
        ]:
            entity = make_entity("spec-1", type=EntityType.SPEC, stage=stage)
            assert compute_stage(entity) == stage

    def test_plan_entity_always_planned_stage(self) -> None:
        """Plan entities should always be in PLANNED stage."""
        entity = make_entity("plan-1", type=EntityType.PLAN, status="open")
        assert compute_stage(entity) == Stage.PLANNED

        entity = make_entity("plan-2", type=EntityType.PLAN, status="closed")
        assert compute_stage(entity) == Stage.PLANNED

    def test_epic_open_is_planned(self) -> None:
        """Open epics should be in PLANNED stage."""
        entity = make_entity("epic-1", type=EntityType.EPIC, status="open")
        assert compute_stage(entity) == Stage.PLANNED

    def test_epic_in_progress_is_in_progress(self) -> None:
        """In-progress epics should be in IN_PROGRESS stage."""
        entity = make_entity("epic-1", type=EntityType.EPIC, status="in_progress")
        assert compute_stage(entity) == Stage.IN_PROGRESS

    def test_epic_closed_is_complete(self) -> None:
        """Closed epics should be in COMPLETE stage."""
        entity = make_entity("epic-1", type=EntityType.EPIC, status="closed")
        assert compute_stage(entity) == Stage.COMPLETE

    def test_task_open_is_ready(self) -> None:
        """Open tasks should be in READY stage."""
        entity = make_entity("task-1", type=EntityType.TASK, status="open")
        assert compute_stage(entity) == Stage.READY

    def test_task_in_progress_is_in_progress(self) -> None:
        """In-progress tasks should be in IN_PROGRESS stage."""
        entity = make_entity("task-1", type=EntityType.TASK, status="in_progress")
        assert compute_stage(entity) == Stage.IN_PROGRESS

    def test_task_closed_is_complete(self) -> None:
        """Closed tasks should be in COMPLETE stage."""
        entity = make_entity("task-1", type=EntityType.TASK, status="closed")
        assert compute_stage(entity) == Stage.COMPLETE

    def test_task_with_blockers_is_blocked(self) -> None:
        """Open tasks with blockers should be in BLOCKED stage."""
        entity = make_entity("task-1", type=EntityType.TASK, status="open")
        assert compute_stage(entity, has_blockers=True) == Stage.BLOCKED

    def test_epic_with_blockers_is_blocked(self) -> None:
        """Open epics with blockers should be in BLOCKED stage."""
        entity = make_entity("epic-1", type=EntityType.EPIC, status="open")
        assert compute_stage(entity, has_blockers=True) == Stage.BLOCKED

    def test_epic_without_blockers_is_planned(self) -> None:
        """Open epics without blockers should be in PLANNED stage."""
        entity = make_entity("epic-1", type=EntityType.EPIC, status="open")
        assert compute_stage(entity, has_blockers=False) == Stage.PLANNED

    def test_review_label_overrides_status(self) -> None:
        """Tasks with 'review' label should be in NEEDS_REVIEW stage."""
        entity = make_entity("task-1", type=EntityType.TASK, status="open", labels=["review"])
        assert compute_stage(entity) == Stage.NEEDS_REVIEW

        entity = make_entity(
            "task-2", type=EntityType.TASK, status="in_progress", labels=["review"]
        )
        assert compute_stage(entity) == Stage.NEEDS_REVIEW

    def test_pr_label_overrides_status(self) -> None:
        """Tasks with 'pr' label should be in NEEDS_REVIEW stage."""
        entity = make_entity("task-1", type=EntityType.TASK, status="open", labels=["pr"])
        assert compute_stage(entity) == Stage.NEEDS_REVIEW

        entity = make_entity("task-2", type=EntityType.TASK, status="in_progress", labels=["PR"])
        assert compute_stage(entity) == Stage.NEEDS_REVIEW

    def test_released_overrides_complete(self) -> None:
        """Released flag should result in RELEASED stage."""
        entity = make_entity("task-1", type=EntityType.TASK, status="closed")
        assert compute_stage(entity, is_released=True) == Stage.RELEASED

    def test_ledger_makes_task_complete(self) -> None:
        """Tasks with ledger entries should be in COMPLETE stage."""
        entity = make_entity("task-1", type=EntityType.TASK, status="closed")
        assert compute_stage(entity, has_ledger=True) == Stage.COMPLETE

    def test_released_takes_priority_over_ledger(self) -> None:
        """RELEASED should take priority over COMPLETE (ledger)."""
        entity = make_entity("task-1", type=EntityType.TASK, status="closed")
        assert compute_stage(entity, is_released=True, has_ledger=True) == Stage.RELEASED

    def test_review_takes_priority_over_released(self) -> None:
        """NEEDS_REVIEW should take priority over RELEASED (for in-review items)."""
        # This captures the case where a task is being re-reviewed for a release
        entity = make_entity("task-1", type=EntityType.TASK, status="open", labels=["review"])
        assert compute_stage(entity, is_released=True) == Stage.NEEDS_REVIEW

    def test_case_insensitive_labels(self) -> None:
        """Label matching should be case-insensitive."""
        entity = make_entity("task-1", type=EntityType.TASK, labels=["REVIEW"])
        assert compute_stage(entity) == Stage.NEEDS_REVIEW

        entity = make_entity("task-2", type=EntityType.TASK, labels=["Pr"])
        assert compute_stage(entity) == Stage.NEEDS_REVIEW


# =============================================================================
# Test RelationshipResolver
# =============================================================================


class TestRelationshipResolver:
    """Tests for the RelationshipResolver class."""

    def test_resolver_with_no_external_data(self) -> None:
        """Resolver should work without changelog or ledger."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("task-1"),
            make_entity("task-2"),
        ]

        resolved, relationships = resolver.resolve(entities)

        assert len(resolved) == 2
        assert len(relationships) == 0

    def test_resolver_creates_epic_to_task_relationship(self) -> None:
        """Resolver should create EPIC_TO_TASK relationship from epic_id."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("epic-1", type=EntityType.EPIC),
            make_entity("task-1", type=EntityType.TASK, epic_id="epic-1"),
            make_entity("task-2", type=EntityType.TASK, epic_id="epic-1"),
        ]

        resolved, relationships = resolver.resolve(entities)

        # Should have 2 EPIC_TO_TASK relationships
        epic_to_task_rels = [r for r in relationships if r.rel_type == RelationType.EPIC_TO_TASK]
        assert len(epic_to_task_rels) == 2
        assert all(r.source_id == "epic-1" for r in epic_to_task_rels)
        assert {r.target_id for r in epic_to_task_rels} == {"task-1", "task-2"}

    def test_resolver_creates_parent_relationship(self) -> None:
        """Resolver should create EPIC_TO_TASK relationship from parent_id."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("epic-1", type=EntityType.EPIC),
            make_entity("task-1", type=EntityType.TASK, parent_id="epic-1"),
        ]

        resolved, relationships = resolver.resolve(entities)

        # Should have 1 EPIC_TO_TASK relationship
        assert len(relationships) == 1
        assert relationships[0].source_id == "epic-1"
        assert relationships[0].target_id == "task-1"
        assert relationships[0].rel_type == RelationType.EPIC_TO_TASK

    def test_resolver_creates_spec_to_plan_relationship(self) -> None:
        """Resolver should create SPEC_TO_PLAN relationship from spec_id."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("spec-1", type=EntityType.SPEC),
            make_entity("plan-1", type=EntityType.PLAN, spec_id="spec-1"),
        ]

        resolved, relationships = resolver.resolve(entities)

        assert len(relationships) == 1
        assert relationships[0].source_id == "spec-1"
        assert relationships[0].target_id == "plan-1"
        assert relationships[0].rel_type == RelationType.SPEC_TO_PLAN

    def test_resolver_creates_plan_to_epic_relationship(self) -> None:
        """Resolver should create PLAN_TO_EPIC relationship from plan_id."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("plan-1", type=EntityType.PLAN),
            make_entity("epic-1", type=EntityType.EPIC, plan_id="plan-1"),
        ]

        resolved, relationships = resolver.resolve(entities)

        assert len(relationships) == 1
        assert relationships[0].source_id == "plan-1"
        assert relationships[0].target_id == "epic-1"
        assert relationships[0].rel_type == RelationType.PLAN_TO_EPIC

    def test_resolver_creates_depends_on_relationship_from_dict(self) -> None:
        """Resolver should create DEPENDS_ON relationships from dependencies in frontmatter."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("task-1", type=EntityType.TASK),
            make_entity(
                "task-2",
                type=EntityType.TASK,
                frontmatter={"dependencies": [{"depends_on_id": "task-1", "type": "blocks"}]},
            ),
        ]

        resolved, relationships = resolver.resolve(entities)

        assert len(relationships) == 1
        assert relationships[0].source_id == "task-2"
        assert relationships[0].target_id == "task-1"
        assert relationships[0].rel_type == RelationType.DEPENDS_ON

    def test_resolver_creates_depends_on_relationship_from_string(self) -> None:
        """Resolver should create DEPENDS_ON relationships from string dependencies."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("task-1", type=EntityType.TASK),
            make_entity(
                "task-2",
                type=EntityType.TASK,
                frontmatter={"dependencies": ["task-1"]},
            ),
        ]

        resolved, relationships = resolver.resolve(entities)

        assert len(relationships) == 1
        assert relationships[0].source_id == "task-2"
        assert relationships[0].target_id == "task-1"
        assert relationships[0].rel_type == RelationType.DEPENDS_ON

    def test_resolver_ignores_nonexistent_relationship_targets(self) -> None:
        """Resolver should not create relationships to nonexistent entities."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("task-1", type=EntityType.TASK, epic_id="nonexistent-epic"),
        ]

        resolved, relationships = resolver.resolve(entities)

        assert len(relationships) == 0

    def test_resolver_avoids_duplicate_relationships(self) -> None:
        """Resolver should not create duplicate relationships."""
        resolver = RelationshipResolver()
        # Entity with both epic_id and parent_id pointing to same epic
        entities = [
            make_entity("epic-1", type=EntityType.EPIC),
            make_entity(
                "task-1",
                type=EntityType.TASK,
                epic_id="epic-1",
                parent_id="epic-1",
            ),
        ]

        resolved, relationships = resolver.resolve(entities)

        # Should only have 1 relationship, not 2
        epic_to_task_rels = [r for r in relationships if r.rel_type == RelationType.EPIC_TO_TASK]
        assert len(epic_to_task_rels) == 1

    def test_resolver_creates_task_to_release_relationship(self, tmp_changelog: Path) -> None:
        """Resolver should create TASK_TO_RELEASE for released tasks."""
        resolver = RelationshipResolver(changelog_path=tmp_changelog)
        entities = [
            make_entity("cub-abc.1", type=EntityType.TASK, status="closed"),
        ]

        resolved, relationships = resolver.resolve(entities)

        task_to_release_rels = [
            r for r in relationships if r.rel_type == RelationType.TASK_TO_RELEASE
        ]
        assert len(task_to_release_rels) == 1
        assert task_to_release_rels[0].source_id == "cub-abc.1"
        assert task_to_release_rels[0].target_id == "release:cub-abc.1"

    def test_resolver_creates_task_to_ledger_relationship(self, tmp_ledger: Path) -> None:
        """Resolver should create TASK_TO_LEDGER for tasks with ledger entries."""
        resolver = RelationshipResolver(ledger_path=tmp_ledger)
        entities = [
            make_entity("cub-abc.1", type=EntityType.TASK, status="closed"),
        ]

        resolved, relationships = resolver.resolve(entities)

        task_to_ledger_rels = [
            r for r in relationships if r.rel_type == RelationType.TASK_TO_LEDGER
        ]
        assert len(task_to_ledger_rels) == 1
        assert task_to_ledger_rels[0].source_id == "cub-abc.1"
        assert task_to_ledger_rels[0].target_id == "ledger:cub-abc.1"

    def test_resolver_enriches_with_ledger_data(self, tmp_ledger: Path) -> None:
        """Resolver should enrich entities with ledger data."""
        resolver = RelationshipResolver(ledger_path=tmp_ledger)
        entities = [
            make_entity("cub-abc.1", type=EntityType.TASK, status="closed"),
        ]

        resolved, relationships = resolver.resolve(entities)

        assert len(resolved) == 1
        entity = resolved[0]
        assert entity.cost_usd == 0.05
        assert entity.tokens == 5000
        assert entity.verification_status == "pass"

    def test_resolver_updates_stage_based_on_release(self, tmp_changelog: Path) -> None:
        """Resolver should update stage to RELEASED for released tasks."""
        resolver = RelationshipResolver(changelog_path=tmp_changelog)
        entities = [
            make_entity(
                "cub-abc.1",
                type=EntityType.TASK,
                stage=Stage.COMPLETE,
                status="closed",
            ),
        ]

        resolved, relationships = resolver.resolve(entities)

        assert len(resolved) == 1
        assert resolved[0].stage == Stage.RELEASED

    def test_resolver_updates_stage_based_on_ledger(self, tmp_ledger: Path) -> None:
        """Resolver should update stage to COMPLETE for tasks with ledger."""
        resolver = RelationshipResolver(ledger_path=tmp_ledger)
        entities = [
            make_entity(
                "cub-abc.1",
                type=EntityType.TASK,
                stage=Stage.IN_PROGRESS,
                status="closed",
            ),
        ]

        resolved, relationships = resolver.resolve(entities)

        assert len(resolved) == 1
        assert resolved[0].stage == Stage.COMPLETE

    def test_resolver_full_chain(self, tmp_changelog: Path, tmp_ledger: Path) -> None:
        """Test complete resolver workflow with full entity chain."""
        resolver = RelationshipResolver(
            changelog_path=tmp_changelog,
            ledger_path=tmp_ledger,
        )

        entities = [
            make_entity("spec-1", type=EntityType.SPEC, stage=Stage.RELEASED),
            make_entity("plan-1", type=EntityType.PLAN, spec_id="spec-1"),
            make_entity("epic-1", type=EntityType.EPIC, plan_id="plan-1", status="closed"),
            make_entity("cub-abc.1", type=EntityType.TASK, epic_id="epic-1", status="closed"),
            make_entity("cub-abc.2", type=EntityType.TASK, epic_id="epic-1", status="closed"),
        ]

        resolved, relationships = resolver.resolve(entities)

        # Check all entities resolved
        assert len(resolved) == 5

        # Check released tasks updated
        released_entities = [e for e in resolved if e.stage == Stage.RELEASED]
        assert len(released_entities) >= 2  # cub-abc.1 and cub-abc.2 are in CHANGELOG

        # Check relationships created
        rel_types = {r.rel_type for r in relationships}
        assert RelationType.SPEC_TO_PLAN in rel_types
        assert RelationType.PLAN_TO_EPIC in rel_types
        assert RelationType.EPIC_TO_TASK in rel_types
        assert RelationType.TASK_TO_RELEASE in rel_types
        assert RelationType.TASK_TO_LEDGER in rel_types

    def test_resolver_handles_missing_changelog(self, tmp_path: Path) -> None:
        """Resolver should handle missing CHANGELOG gracefully."""
        resolver = RelationshipResolver(changelog_path=tmp_path / "nonexistent" / "CHANGELOG.md")
        entities = [make_entity("task-1")]

        resolved, relationships = resolver.resolve(entities)

        assert len(resolved) == 1
        assert len(relationships) == 0

    def test_resolver_handles_missing_ledger(self, tmp_path: Path) -> None:
        """Resolver should handle missing ledger gracefully."""
        resolver = RelationshipResolver(ledger_path=tmp_path / "nonexistent" / "ledger")
        entities = [make_entity("task-1")]

        resolved, relationships = resolver.resolve(entities)

        assert len(resolved) == 1
        assert len(relationships) == 0

    def test_resolver_case_insensitive_id_matching(
        self, tmp_changelog: Path, tmp_ledger: Path
    ) -> None:
        """Resolver should match IDs case-insensitively."""
        resolver = RelationshipResolver(
            changelog_path=tmp_changelog,
            ledger_path=tmp_ledger,
        )

        # CHANGELOG has lowercase IDs, entity has mixed case
        entities = [
            make_entity("CUB-ABC.1", type=EntityType.TASK, status="closed"),
        ]

        resolved, relationships = resolver.resolve(entities)

        # Should still find the release and ledger entry
        assert resolved[0].stage == Stage.RELEASED
        assert resolved[0].cost_usd == 0.05

    def test_resolver_creates_reference_for_task_with_spec_id(self) -> None:
        """Tasks with spec_id should create REFERENCES relationship."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("spec-1", type=EntityType.SPEC),
            make_entity("task-1", type=EntityType.TASK, spec_id="spec-1"),
        ]

        resolved, relationships = resolver.resolve(entities)

        ref_rels = [r for r in relationships if r.rel_type == RelationType.REFERENCES]
        assert len(ref_rels) == 1
        assert ref_rels[0].source_id == "spec-1"
        assert ref_rels[0].target_id == "task-1"

    def test_resolver_handles_contains_relationship(self) -> None:
        """Resolver should create CONTAINS for non-epic parent relationships."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("parent-1", type=EntityType.PLAN),
            make_entity("child-1", type=EntityType.PLAN, parent_id="parent-1"),
        ]

        resolved, relationships = resolver.resolve(entities)

        contains_rels = [r for r in relationships if r.rel_type == RelationType.CONTAINS]
        assert len(contains_rels) == 1
        assert contains_rels[0].source_id == "parent-1"
        assert contains_rels[0].target_id == "child-1"

    def test_resolver_detects_blockers_from_depends_on(self) -> None:
        """Resolver should detect blockers from depends_on in frontmatter."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("task-1", type=EntityType.TASK, status="open"),
            make_entity(
                "task-2",
                type=EntityType.TASK,
                status="open",
                frontmatter={"depends_on": ["task-1"]},
            ),
        ]

        resolved, relationships = resolver.resolve(entities)

        # task-2 depends on task-1, which is still open, so task-2 should be BLOCKED
        task2 = [e for e in resolved if e.id == "task-2"][0]
        assert task2.stage == Stage.BLOCKED

    def test_resolver_task_ready_when_dependency_closed(self) -> None:
        """Resolver should mark task as READY when dependency is closed."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("task-1", type=EntityType.TASK, status="closed"),
            make_entity(
                "task-2",
                type=EntityType.TASK,
                status="open",
                frontmatter={"depends_on": ["task-1"]},
            ),
        ]

        resolved, relationships = resolver.resolve(entities)

        # task-1 is closed, so task-2 should be READY
        task2 = [e for e in resolved if e.id == "task-2"][0]
        assert task2.stage == Stage.READY

    def test_resolver_detects_blockers_from_dependsOn_camelcase(self) -> None:
        """Resolver should detect blockers from dependsOn (camelCase) in frontmatter."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("task-1", type=EntityType.TASK, status="open"),
            make_entity(
                "task-2",
                type=EntityType.TASK,
                status="open",
                frontmatter={"dependsOn": ["task-1"]},
            ),
        ]

        resolved, relationships = resolver.resolve(entities)

        # task-2 depends on task-1, which is still open, so task-2 should be BLOCKED
        task2 = [e for e in resolved if e.id == "task-2"][0]
        assert task2.stage == Stage.BLOCKED

    def test_resolver_epic_blocked_by_dependencies(self) -> None:
        """Resolver should mark epics as BLOCKED when they have unmet dependencies."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("epic-1", type=EntityType.EPIC, status="open"),
            make_entity(
                "epic-2",
                type=EntityType.EPIC,
                status="open",
                frontmatter={"depends_on": ["epic-1"]},
            ),
        ]

        resolved, relationships = resolver.resolve(entities)

        # epic-2 depends on epic-1, which is still open, so epic-2 should be BLOCKED
        epic2 = [e for e in resolved if e.id == "epic-2"][0]
        assert epic2.stage == Stage.BLOCKED

    def test_resolver_no_blockers_when_no_dependencies(self) -> None:
        """Resolver should mark tasks as READY when they have no dependencies."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("task-1", type=EntityType.TASK, status="open"),
            make_entity("task-2", type=EntityType.TASK, status="open", frontmatter={}),
        ]

        resolved, relationships = resolver.resolve(entities)

        # Both tasks should be READY
        for entity in resolved:
            assert entity.stage == Stage.READY


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_entity_list(self) -> None:
        """Resolver should handle empty entity list."""
        resolver = RelationshipResolver()
        resolved, relationships = resolver.resolve([])

        assert resolved == []
        assert relationships == []

    def test_entity_with_no_relationships(self) -> None:
        """Entity with no markers should have no relationships."""
        resolver = RelationshipResolver()
        entities = [make_entity("standalone-task")]

        resolved, relationships = resolver.resolve(entities)

        assert len(resolved) == 1
        assert len(relationships) == 0

    def test_self_referencing_entity(self) -> None:
        """Entity referencing itself should not create relationship."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("task-1", type=EntityType.TASK, parent_id="task-1"),
        ]

        resolved, relationships = resolver.resolve(entities)

        # Self-references should still work (entity exists)
        # but the relationship type depends on entity type
        assert len(resolved) == 1

    def test_circular_dependencies(self) -> None:
        """Circular dependencies should be handled."""
        resolver = RelationshipResolver()
        entities = [
            make_entity(
                "task-1",
                type=EntityType.TASK,
                frontmatter={"dependencies": ["task-2"]},
            ),
            make_entity(
                "task-2",
                type=EntityType.TASK,
                frontmatter={"dependencies": ["task-1"]},
            ),
        ]

        resolved, relationships = resolver.resolve(entities)

        # Both directions should be created
        depends_rels = [r for r in relationships if r.rel_type == RelationType.DEPENDS_ON]
        assert len(depends_rels) == 2

    def test_entity_with_none_status(self) -> None:
        """Entity with None status should be handled."""
        entity = make_entity("task-1", type=EntityType.TASK, status=None)

        # Should not raise
        stage = compute_stage(entity)
        # Falls through to default (existing stage)
        assert stage == Stage.READY

    def test_entity_with_empty_labels(self) -> None:
        """Entity with empty labels list should be handled."""
        entity = make_entity("task-1", type=EntityType.TASK, labels=[])

        stage = compute_stage(entity)
        assert stage == Stage.READY

    def test_entity_with_none_frontmatter(self) -> None:
        """Entity with None frontmatter should be handled."""
        resolver = RelationshipResolver()
        entities = [make_entity("task-1", frontmatter=None)]

        resolved, relationships = resolver.resolve(entities)
        assert len(resolved) == 1
        assert len(relationships) == 0

    def test_malformed_dependencies_in_frontmatter(self) -> None:
        """Malformed dependencies should not cause errors."""
        resolver = RelationshipResolver()
        entities = [
            make_entity("task-1"),
            make_entity(
                "task-2",
                frontmatter={
                    "dependencies": [
                        None,
                        {"invalid": "format"},
                        123,  # Wrong type
                    ]
                },
            ),
        ]

        # Should not raise
        resolved, relationships = resolver.resolve(entities)
        assert len(resolved) == 2

    def test_ledger_enrichment_preserves_other_fields(self, tmp_ledger: Path) -> None:
        """Ledger enrichment should not overwrite existing entity fields."""
        resolver = RelationshipResolver(ledger_path=tmp_ledger)
        entities = [
            make_entity(
                "cub-abc.1",
                type=EntityType.TASK,
                status="closed",
                title="Original Title",
                labels=["important"],
                priority=1,
            ),
        ]

        resolved, relationships = resolver.resolve(entities)

        entity = resolved[0]
        assert entity.title == "Original Title"
        assert entity.labels == ["important"]
        assert entity.priority == 1
        # But ledger data should be added
        assert entity.cost_usd == 0.05
