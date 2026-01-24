"""
Integration tests for the complete sync pipeline.

Tests cover the full sync process from multiple data sources (specs, plans, tasks)
through relationship resolution to database persistence.

Test scenarios:
- Full sync with all sources configured
- Partial failures (one source fails, others continue)
- Relationship resolution and enrichment
- Stage computation based on ledger and changelog
- Real project structure simulation
"""

import json
from pathlib import Path

import pytest

from cub.core.dashboard.db import get_connection
from cub.core.dashboard.sync.orchestrator import SyncOrchestrator
from cub.core.specs import Stage as SpecStage


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """
    Create a complete temporary project structure with all data sources.

    Structure:
    - specs/
      - researching/
      - planned/
      - staged/
    - .cub/
      - sessions/
      - ledger/
      - dashboard.db
    - CHANGELOG.md
    """
    project_root = tmp_path / "project"
    project_root.mkdir()

    # Create specs directories
    specs_root = project_root / "specs"
    for stage in SpecStage:
        (specs_root / stage.value).mkdir(parents=True)

    # Create .cub directories
    cub_dir = project_root / ".cub"
    (cub_dir / "sessions").mkdir(parents=True)
    (cub_dir / "ledger").mkdir(parents=True)

    return project_root


@pytest.fixture
def sample_specs(tmp_project: Path) -> list[Path]:
    """Create sample spec files."""
    specs_root = tmp_project / "specs"
    spec_files = []

    # Create specs in different stages
    for i, stage in enumerate(["researching", "planned", "staged"]):
        spec_file = specs_root / stage / f"spec-{stage}-{i}.md"
        spec_content = f"""---
priority: {i}
complexity: medium
status: {stage}
---

# {stage.title()} Spec {i}

This is a test specification in {stage} stage.

## Description

Test content for integration testing.
"""
        spec_file.write_text(spec_content)
        spec_files.append(spec_file)

    return spec_files


@pytest.fixture
def sample_plans(tmp_project: Path) -> list[Path]:
    """Create sample plan files."""
    sessions_root = tmp_project / ".cub" / "sessions"
    plan_files = []

    # Create 2 sessions with plan.jsonl files
    for i in range(2):
        session_dir = sessions_root / f"session-{i}"
        session_dir.mkdir()

        # Create session.json
        session_data = {
            "id": f"session-{i}",
            "created": "2026-01-15T10:00:00Z",
            "updated": "2026-01-15T12:00:00Z",
        }
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Create plan.jsonl with an epic task
        plan_tasks = [
            {
                "id": f"epic-{i}",
                "title": f"Epic {i}",
                "description": f"Test epic {i}",
                "issue_type": "epic",
                "status": "open",
                "priority": i,
                "labels": ["integration-test"],
            }
        ]

        plan_file = session_dir / "plan.jsonl"
        with open(plan_file, "w") as f:
            for task in plan_tasks:
                f.write(json.dumps(task) + "\n")

        plan_files.append(plan_file)

    return plan_files


@pytest.fixture
def sample_changelog(tmp_project: Path) -> Path:
    """Create sample CHANGELOG.md."""
    changelog_path = tmp_project / "CHANGELOG.md"
    changelog_content = """# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-01-20

### Added
- Implemented epic-0 feature
- Completed spec-planned-1 implementation

## [0.1.0] - 2026-01-10

### Added
- Initial release with basic features
"""
    changelog_path.write_text(changelog_content)
    return changelog_path


class TestSyncIntegration:
    """Integration tests for full sync pipeline."""

    def test_full_sync_all_sources(
        self, tmp_project: Path, sample_specs: list[Path], sample_plans: list[Path]
    ) -> None:
        """Test complete sync with specs and plans."""
        db_path = tmp_project / ".cub" / "dashboard.db"

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=tmp_project / "specs",
            plans_root=tmp_project / ".cub" / "sessions",
        )

        result = orchestrator.sync()

        # Verify sync succeeded
        assert result.success is True
        assert result.entities_added > 0
        assert "specs" in result.sources_synced
        assert "plans" in result.sources_synced
        assert result.duration_seconds > 0

        # Verify entities in database
        with get_connection(db_path) as conn:
            cursor = conn.execute("SELECT type, COUNT(*) as count FROM entities GROUP BY type")
            type_counts = {row["type"]: row["count"] for row in cursor.fetchall()}

            # Should have specs and plans
            assert "spec" in type_counts
            assert "plan" in type_counts
            assert type_counts["spec"] == len(sample_specs)
            assert type_counts["plan"] == len(sample_plans)

    def test_sync_with_changelog_and_ledger(
        self, tmp_project: Path, sample_specs: list[Path], sample_changelog: Path
    ) -> None:
        """Test sync with changelog for release detection."""
        db_path = tmp_project / ".cub" / "dashboard.db"

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=tmp_project / "specs",
            changelog_path=sample_changelog,
        )

        result = orchestrator.sync()

        assert result.success is True
        assert result.entities_added > 0

        # Verify changelog was processed (relationship resolver used it)
        # Note: We can't directly verify RELEASED stage without tasks in the changelog
        # But we can verify the sync completed successfully with changelog configured
        assert result.sources_synced == ["specs"]

    def test_partial_failure_handling(self, tmp_project: Path, sample_specs: list[Path]) -> None:
        """Test that sync continues when one source fails."""
        db_path = tmp_project / ".cub" / "dashboard.db"

        # Configure with nonexistent plans root to trigger failure
        nonexistent_plans = tmp_project / "nonexistent_sessions"

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=tmp_project / "specs",
            plans_root=nonexistent_plans,
        )

        result = orchestrator.sync()

        # Sync should still succeed because specs parsed successfully
        assert result.success is True
        assert result.entities_added == len(sample_specs)
        assert "specs" in result.sources_synced
        # Plans should not be in sources_synced since directory doesn't exist

    def test_relationship_resolution(
        self,
        tmp_project: Path,
        sample_specs: list[Path],
        sample_plans: list[Path],
    ) -> None:
        """Test that relationships are created between entities."""
        db_path = tmp_project / ".cub" / "dashboard.db"

        # Create a plan that references a spec
        sessions_root = tmp_project / ".cub" / "sessions"
        session_dir = sessions_root / "session-with-ref"
        session_dir.mkdir()

        session_data = {
            "id": "session-with-ref",
            "created": "2026-01-20T10:00:00Z",
        }
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Create plan that references a spec
        plan_task = {
            "id": "epic-with-spec",
            "title": "Epic with Spec Reference",
            "description": "Test epic",
            "issue_type": "epic",
            "status": "open",
            "spec_id": "spec-planned-1",  # Reference to spec
        }

        with open(session_dir / "plan.jsonl", "w") as f:
            f.write(json.dumps(plan_task) + "\n")

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=tmp_project / "specs",
            plans_root=tmp_project / ".cub" / "sessions",
        )

        result = orchestrator.sync()

        assert result.success is True
        assert result.relationships_added > 0

        # Verify relationships in database
        with get_connection(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM relationships")
            row = cursor.fetchone()
            count = row["count"]
            assert count > 0

    def test_incremental_sync_skips_unchanged(
        self, tmp_project: Path, sample_specs: list[Path]
    ) -> None:
        """Test that incremental sync skips unchanged entities."""
        db_path = tmp_project / ".cub" / "dashboard.db"

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=tmp_project / "specs",
        )

        # First sync
        result1 = orchestrator.sync()
        assert result1.entities_added == len(sample_specs)

        # Second sync (nothing changed)
        result2 = orchestrator.sync()
        assert result2.entities_added == 0  # All skipped due to unchanged checksums

    def test_incremental_sync_updates_changed(
        self, tmp_project: Path, sample_specs: list[Path]
    ) -> None:
        """Test that incremental sync updates changed entities."""
        db_path = tmp_project / ".cub" / "dashboard.db"

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=tmp_project / "specs",
        )

        # First sync
        result1 = orchestrator.sync()
        assert result1.entities_added > 0

        # Modify a spec file
        spec_file = sample_specs[0]
        modified_content = """---
priority: 0
complexity: high
status: researching
---

# Modified Spec

This content has been modified.
"""
        spec_file.write_text(modified_content)

        # Second sync
        result2 = orchestrator.sync()

        # Should update the modified spec
        assert result2.entities_added == 1

        # Verify title was updated
        with get_connection(db_path) as conn:
            cursor = conn.execute(
                "SELECT title FROM entities WHERE file_path LIKE ?",
                (f"%{spec_file.name}%",),
            )
            row = cursor.fetchone()
            assert row["title"] == "Modified Spec"

    def test_sync_empty_project(self, tmp_project: Path) -> None:
        """Test sync with no data sources configured."""
        db_path = tmp_project / ".cub" / "dashboard.db"

        orchestrator = SyncOrchestrator(db_path=db_path)

        result = orchestrator.sync()

        assert result.success is True
        assert result.entities_added == 0
        assert len(result.sources_synced) == 0

    def test_get_stats_after_sync(
        self, tmp_project: Path, sample_specs: list[Path], sample_plans: list[Path]
    ) -> None:
        """Test database statistics after sync."""
        db_path = tmp_project / ".cub" / "dashboard.db"

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=tmp_project / "specs",
            plans_root=tmp_project / ".cub" / "sessions",
        )

        orchestrator.sync()

        stats = orchestrator.get_stats()

        assert stats["total"] == len(sample_specs) + len(sample_plans)
        assert "spec" in stats["by_type"]
        assert "plan" in stats["by_type"]
        assert len(stats["by_stage"]) > 0

    def test_transaction_rollback_on_error(
        self, tmp_project: Path, sample_specs: list[Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that transaction is rolled back when an error occurs."""
        db_path = tmp_project / ".cub" / "dashboard.db"

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=tmp_project / "specs",
        )

        # Mock the writer to raise an error during entity writing
        from cub.core.dashboard.sync.writer import EntityWriter

        def failing_write_entities(self, entities):
            raise RuntimeError("Simulated write error")

        monkeypatch.setattr(EntityWriter, "write_entities", failing_write_entities)

        result = orchestrator.sync()

        # Sync should fail
        assert result.success is False
        assert len(result.errors) > 0

        # Verify no entities in database (transaction rolled back)
        with get_connection(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM entities")
            row = cursor.fetchone()
            count = row["count"]
            assert count == 0


class TestComplexIntegration:
    """More complex integration scenarios."""

    def test_multiple_sync_rounds(
        self, tmp_project: Path, sample_specs: list[Path]
    ) -> None:
        """Test multiple sync rounds with additions and modifications."""
        db_path = tmp_project / ".cub" / "dashboard.db"
        specs_root = tmp_project / "specs"

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=specs_root,
        )

        # Round 1: Initial sync
        result1 = orchestrator.sync()
        count1 = result1.entities_added

        # Round 2: Add new spec
        new_spec = specs_root / "planned" / "new-spec.md"
        new_spec.write_text("---\npriority: 1\n---\n# New Spec")
        result2 = orchestrator.sync()

        assert result2.entities_added == 1  # Just the new one

        # Round 3: Modify existing and add another
        sample_specs[0].write_text("---\npriority: 0\n---\n# Modified")
        another_spec = specs_root / "staged" / "another-spec.md"
        another_spec.write_text("---\npriority: 2\n---\n# Another")

        result3 = orchestrator.sync()

        assert result3.entities_added == 2  # Modified + new

        # Verify final count
        stats = orchestrator.get_stats()
        assert stats["total"] == count1 + 2  # Original + 2 new specs

    def test_sync_with_all_sources_and_enrichment(
        self,
        tmp_project: Path,
        sample_specs: list[Path],
        sample_plans: list[Path],
        sample_changelog: Path,
    ) -> None:
        """Test full sync with all sources and relationship enrichment."""
        db_path = tmp_project / ".cub" / "dashboard.db"

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=tmp_project / "specs",
            plans_root=tmp_project / ".cub" / "sessions",
            changelog_path=sample_changelog,
            ledger_path=tmp_project / ".cub" / "ledger",
        )

        result = orchestrator.sync()

        # Should succeed with all sources
        assert result.success is True
        assert result.entities_added > 0

        # Verify comprehensive sync
        with get_connection(db_path) as conn:
            # Check entities
            cursor = conn.execute("SELECT COUNT(*) as count FROM entities")
            entity_count = cursor.fetchone()["count"]
            assert entity_count == len(sample_specs) + len(sample_plans)

            # Check that data was enriched (has search_text)
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM entities WHERE search_text IS NOT NULL"
            )
            with_search = cursor.fetchone()["count"]
            assert with_search > 0
