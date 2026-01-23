"""
Tests for the spec workflow module.

Tests cover:
- Stage enum behavior
- Spec model parsing and serialization
- SpecWorkflow listing, finding, and moving specs
- Stage transition validation
- Git mv integration
"""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.specs import (
    InvalidStageTransitionError,
    Readiness,
    Spec,
    SpecComplexity,
    SpecMoveError,
    SpecNotFoundError,
    SpecPriority,
    SpecStatus,
    SpecWorkflow,
    Stage,
)

# =============================================================================
# Stage Enum Tests
# =============================================================================


class TestStage:
    """Tests for the Stage enum."""

    def test_stage_values(self) -> None:
        """Test that Stage enum has expected values."""
        assert Stage.RESEARCHING.value == "researching"
        assert Stage.PLANNED.value == "planned"
        assert Stage.STAGED.value == "staged"
        assert Stage.IMPLEMENTING.value == "implementing"
        assert Stage.RELEASED.value == "released"
        # COMPLETED is backwards-compat alias for RELEASED
        assert Stage.COMPLETED.value == "released"

    def test_from_directory_valid(self) -> None:
        """Test Stage.from_directory with valid directory names."""
        assert Stage.from_directory("researching") == Stage.RESEARCHING
        assert Stage.from_directory("planned") == Stage.PLANNED
        assert Stage.from_directory("staged") == Stage.STAGED
        assert Stage.from_directory("implementing") == Stage.IMPLEMENTING
        assert Stage.from_directory("released") == Stage.RELEASED
        # "completed" maps to RELEASED for backwards compatibility
        assert Stage.from_directory("completed") == Stage.RELEASED

    def test_from_directory_invalid(self) -> None:
        """Test Stage.from_directory with invalid directory name."""
        with pytest.raises(ValueError, match="Unknown stage directory"):
            Stage.from_directory("invalid")

    def test_is_active(self) -> None:
        """Test is_active property for active vs at-rest stages."""
        assert Stage.RESEARCHING.is_active is True
        assert Stage.PLANNED.is_active is False
        assert Stage.STAGED.is_active is False
        assert Stage.IMPLEMENTING.is_active is True
        assert Stage.RELEASED.is_active is False


# =============================================================================
# Readiness Model Tests
# =============================================================================


class TestReadiness:
    """Tests for the Readiness model."""

    def test_readiness_defaults(self) -> None:
        """Test Readiness model default values."""
        readiness = Readiness()
        assert readiness.score == 0
        assert readiness.blockers == []
        assert readiness.questions == []
        assert readiness.decisions_needed == []
        assert readiness.tools_needed == []

    def test_readiness_with_values(self) -> None:
        """Test Readiness model with explicit values."""
        readiness = Readiness(
            score=7,
            blockers=["needs API approval"],
            questions=["which database?"],
            decisions_needed=["choose framework"],
            tools_needed=["profiler"],
        )
        assert readiness.score == 7
        assert readiness.blockers == ["needs API approval"]
        assert readiness.questions == ["which database?"]

    def test_readiness_score_bounds(self) -> None:
        """Test that score is bounded 0-10."""
        with pytest.raises(ValueError):
            Readiness(score=-1)
        with pytest.raises(ValueError):
            Readiness(score=11)


class TestReadinessFlexibleParsing:
    """Tests for flexible YAML parsing in Readiness fields."""

    def test_from_frontmatter_dict_string_format(self) -> None:
        """Test that string format works (current behavior)."""
        data = {
            "priority": "high",
            "complexity": "medium",
            "readiness": {
                "score": 7,
                "tools_needed": [
                    "API Design Validator (design registry format)",
                    "Technical Feasibility Checker (verify approach)",
                ],
            },
        }

        spec = Spec.from_frontmatter_dict(
            data=data,
            name="test-spec",
            path=Path("test.md"),
            stage=Stage.RESEARCHING,
        )

        assert len(spec.readiness.tools_needed) == 2
        assert spec.readiness.tools_needed[0] == "API Design Validator (design registry format)"
        assert spec.readiness.tools_needed[1] == "Technical Feasibility Checker (verify approach)"

    def test_from_frontmatter_dict_dict_format(self) -> None:
        """Test that dict format is converted to string."""
        data = {
            "priority": "high",
            "complexity": "medium",
            "readiness": {
                "score": 7,
                "tools_needed": [
                    "Simple string tool",
                    {"name": "Complex Tool", "description": "does complex things"},
                    {"name": "Tool with only name"},
                ],
            },
        }

        spec = Spec.from_frontmatter_dict(
            data=data,
            name="test-spec",
            path=Path("test.md"),
            stage=Stage.RESEARCHING,
        )

        assert len(spec.readiness.tools_needed) == 3
        assert spec.readiness.tools_needed[0] == "Simple string tool"
        assert spec.readiness.tools_needed[1] == "Complex Tool (does complex things)"
        assert spec.readiness.tools_needed[2] == "Tool with only name"

    def test_from_frontmatter_all_fields_handle_dicts(self) -> None:
        """Test that all readiness list fields handle dict format."""
        data = {
            "priority": "high",
            "complexity": "medium",
            "readiness": {
                "score": 5,
                "blockers": [
                    "Simple blocker",
                    {"name": "Complex blocker", "description": "needs resolution"},
                ],
                "questions": [
                    "Simple question?",
                    {"name": "Complex question", "description": "needs answer"},
                ],
                "decisions_needed": [
                    "Simple decision",
                    {"name": "Complex decision", "description": "needs choice"},
                ],
                "tools_needed": [
                    "Simple tool",
                    {"name": "Complex tool", "description": "needs building"},
                ],
            },
        }

        spec = Spec.from_frontmatter_dict(
            data=data,
            name="test-spec",
            path=Path("test.md"),
            stage=Stage.RESEARCHING,
        )

        # All fields should handle both formats
        assert len(spec.readiness.blockers) == 2
        assert spec.readiness.blockers[1] == "Complex blocker (needs resolution)"

        assert len(spec.readiness.questions) == 2
        assert spec.readiness.questions[1] == "Complex question (needs answer)"

        assert len(spec.readiness.decisions_needed) == 2
        assert spec.readiness.decisions_needed[1] == "Complex decision (needs choice)"

        assert len(spec.readiness.tools_needed) == 2
        assert spec.readiness.tools_needed[1] == "Complex tool (needs building)"


# =============================================================================
# Spec Model Tests
# =============================================================================


class TestSpec:
    """Tests for the Spec model."""

    def test_spec_basic(self) -> None:
        """Test basic Spec creation."""
        spec = Spec(
            name="my-feature",
            path=Path("specs/planned/my-feature.md"),
            stage=Stage.PLANNED,
        )
        assert spec.name == "my-feature"
        assert spec.stage == Stage.PLANNED
        assert spec.filename == "my-feature.md"

    def test_spec_with_all_fields(self) -> None:
        """Test Spec with all fields populated."""
        spec = Spec(
            name="full-spec",
            path=Path("specs/researching/full-spec.md"),
            stage=Stage.RESEARCHING,
            status=SpecStatus.DRAFT,
            priority=SpecPriority.HIGH,
            complexity=SpecComplexity.HIGH,
            dependencies=["other-spec.md"],
            blocks=["blocked-spec.md"],
            created=date(2026, 1, 15),
            updated=date(2026, 1, 20),
            readiness=Readiness(score=4, blockers=["needs research"]),
            notes="Some notes",
            title="Full Feature Spec",
        )
        assert spec.status == SpecStatus.DRAFT
        assert spec.priority == SpecPriority.HIGH
        assert spec.complexity == SpecComplexity.HIGH
        assert spec.dependencies == ["other-spec.md"]
        assert spec.created == date(2026, 1, 15)
        assert spec.title == "Full Feature Spec"

    def test_is_ready_for_implementation(self) -> None:
        """Test is_ready_for_implementation property."""
        # Ready: planned, high score, no blockers
        ready_spec = Spec(
            name="ready",
            path=Path("specs/planned/ready.md"),
            stage=Stage.PLANNED,
            readiness=Readiness(score=8),
        )
        assert ready_spec.is_ready_for_implementation is True

        # Not ready: wrong stage
        wrong_stage = Spec(
            name="wrong-stage",
            path=Path("specs/researching/wrong-stage.md"),
            stage=Stage.RESEARCHING,
            readiness=Readiness(score=9),
        )
        assert wrong_stage.is_ready_for_implementation is False

        # Not ready: low score
        low_score = Spec(
            name="low-score",
            path=Path("specs/planned/low-score.md"),
            stage=Stage.PLANNED,
            readiness=Readiness(score=5),
        )
        assert low_score.is_ready_for_implementation is False

        # Not ready: has blockers
        has_blockers = Spec(
            name="blocked",
            path=Path("specs/planned/blocked.md"),
            stage=Stage.PLANNED,
            readiness=Readiness(score=9, blockers=["needs approval"]),
        )
        assert has_blockers.is_ready_for_implementation is False

    def test_spec_path_string_conversion(self) -> None:
        """Test that path can be provided as string."""
        spec = Spec(
            name="string-path",
            path="specs/planned/string-path.md",  # type: ignore[arg-type]
            stage=Stage.PLANNED,
        )
        assert isinstance(spec.path, Path)

    def test_to_frontmatter_dict(self) -> None:
        """Test converting Spec to frontmatter dictionary."""
        spec = Spec(
            name="test",
            path=Path("specs/planned/test.md"),
            stage=Stage.PLANNED,
            status=SpecStatus.READY,
            priority=SpecPriority.HIGH,
            complexity=SpecComplexity.LOW,
            dependencies=["dep1.md"],
            created=date(2026, 1, 15),
            readiness=Readiness(score=8, questions=["which API?"]),
        )
        frontmatter = spec.to_frontmatter_dict()

        assert frontmatter["status"] == "ready"
        assert frontmatter["priority"] == "high"
        assert frontmatter["complexity"] == "low"
        assert frontmatter["dependencies"] == ["dep1.md"]
        assert frontmatter["created"] == "2026-01-15"
        readiness_dict = frontmatter["readiness"]
        assert isinstance(readiness_dict, dict)
        assert readiness_dict["score"] == 8
        assert readiness_dict["questions"] == ["which API?"]

    def test_from_frontmatter_dict(self) -> None:
        """Test creating Spec from frontmatter dictionary."""
        data = {
            "status": "draft",
            "priority": "high",
            "complexity": "medium",
            "dependencies": ["dep.md"],
            "blocks": [],
            "created": "2026-01-15",
            "updated": "2026-01-20",
            "readiness": {
                "score": 5,
                "blockers": ["needs design"],
                "questions": ["how?"],
                "decisions_needed": [],
                "tools_needed": [],
            },
            "notes": "Some notes here",
        }
        spec = Spec.from_frontmatter_dict(
            data=data,
            name="from-dict",
            path=Path("specs/researching/from-dict.md"),
            stage=Stage.RESEARCHING,
            title="From Dictionary",
        )

        assert spec.name == "from-dict"
        assert spec.status == SpecStatus.DRAFT
        assert spec.priority == SpecPriority.HIGH
        assert spec.complexity == SpecComplexity.MEDIUM
        assert spec.dependencies == ["dep.md"]
        assert spec.created == date(2026, 1, 15)
        assert spec.updated == date(2026, 1, 20)
        assert spec.readiness.score == 5
        assert spec.readiness.blockers == ["needs design"]
        assert spec.notes == "Some notes here"
        assert spec.title == "From Dictionary"

    def test_from_frontmatter_dict_minimal(self) -> None:
        """Test creating Spec from minimal frontmatter."""
        spec = Spec.from_frontmatter_dict(
            data={},
            name="minimal",
            path=Path("specs/planned/minimal.md"),
            stage=Stage.PLANNED,
        )
        assert spec.name == "minimal"
        assert spec.status is None
        assert spec.priority == SpecPriority.MEDIUM
        assert spec.complexity == SpecComplexity.MEDIUM
        assert spec.dependencies == []
        assert spec.readiness.score == 0


# =============================================================================
# SpecWorkflow Tests
# =============================================================================


class TestSpecWorkflowInit:
    """Tests for SpecWorkflow initialization."""

    def test_init(self, tmp_path: Path) -> None:
        """Test basic initialization."""
        workflow = SpecWorkflow(tmp_path / "specs")
        assert workflow.specs_root == tmp_path / "specs"
        assert workflow.use_git is True

    def test_init_no_git(self, tmp_path: Path) -> None:
        """Test initialization without git."""
        workflow = SpecWorkflow(tmp_path / "specs", use_git=False)
        assert workflow.use_git is False


class TestSpecWorkflowList:
    """Tests for listing specs."""

    @pytest.fixture
    def specs_dir(self, tmp_path: Path) -> Path:
        """Create a specs directory structure with test files."""
        specs_root = tmp_path / "specs"

        # Create all stage directories
        (specs_root / "researching").mkdir(parents=True)
        (specs_root / "planned").mkdir(parents=True)
        (specs_root / "staged").mkdir(parents=True)
        (specs_root / "implementing").mkdir(parents=True)
        (specs_root / "released").mkdir(parents=True)

        # Create test specs
        researching_spec = """---
status: researching
priority: medium
complexity: high
dependencies: []
created: 2026-01-15
readiness:
  score: 3
  blockers:
    - needs research
---

# Research Feature

Some content here.
"""
        (specs_root / "researching" / "research-feature.md").write_text(researching_spec)

        planned_spec = """---
status: ready
priority: high
complexity: medium
dependencies:
  - research-feature.md
created: 2026-01-16
readiness:
  score: 8
---

# Planned Feature

Ready to implement.
"""
        (specs_root / "planned" / "planned-feature.md").write_text(planned_spec)

        return specs_root

    def test_list_all_specs(self, specs_dir: Path) -> None:
        """Test listing all specs."""
        workflow = SpecWorkflow(specs_dir)
        specs = workflow.list_specs()

        # Only 2 specs in the fixture now (researching and planned)
        assert len(specs) == 2
        names = [s.name for s in specs]
        assert "research-feature" in names
        assert "planned-feature" in names

    def test_list_specs_by_stage(self, specs_dir: Path) -> None:
        """Test listing specs filtered by stage."""
        workflow = SpecWorkflow(specs_dir)

        researching = workflow.list_specs(Stage.RESEARCHING)
        assert len(researching) == 1
        assert researching[0].name == "research-feature"

        planned = workflow.list_specs(Stage.PLANNED)
        assert len(planned) == 1
        assert planned[0].name == "planned-feature"

        # No specs in other stages
        assert len(workflow.list_specs(Stage.STAGED)) == 0
        assert len(workflow.list_specs(Stage.IMPLEMENTING)) == 0
        assert len(workflow.list_specs(Stage.RELEASED)) == 0

    def test_list_specs_nonexistent_root(self, tmp_path: Path) -> None:
        """Test listing specs when root doesn't exist."""
        workflow = SpecWorkflow(tmp_path / "nonexistent")
        with pytest.raises(FileNotFoundError):
            workflow.list_specs()

    def test_list_specs_empty_stage(self, specs_dir: Path) -> None:
        """Test listing specs from empty stage returns empty list."""
        workflow = SpecWorkflow(specs_dir)
        # staged/ exists but has no specs
        staged = workflow.list_specs(Stage.STAGED)
        assert staged == []

    def test_list_specs_extracts_title(self, specs_dir: Path) -> None:
        """Test that spec title is extracted from heading."""
        workflow = SpecWorkflow(specs_dir)
        specs = workflow.list_specs(Stage.RESEARCHING)

        assert len(specs) == 1
        assert specs[0].title == "Research Feature"


class TestSpecWorkflowFind:
    """Tests for finding specs."""

    @pytest.fixture
    def specs_dir(self, tmp_path: Path) -> Path:
        """Create a specs directory with a single spec."""
        specs_root = tmp_path / "specs"
        (specs_root / "planned").mkdir(parents=True)

        spec_content = """---
status: ready
priority: high
---

# Test Feature
"""
        (specs_root / "planned" / "test-feature.md").write_text(spec_content)
        return specs_root

    def test_find_spec(self, specs_dir: Path) -> None:
        """Test finding a spec by name."""
        workflow = SpecWorkflow(specs_dir)
        spec = workflow.find_spec("test-feature")

        assert spec.name == "test-feature"
        assert spec.stage == Stage.PLANNED

    def test_find_spec_with_extension(self, specs_dir: Path) -> None:
        """Test finding a spec when .md extension is included."""
        workflow = SpecWorkflow(specs_dir)
        spec = workflow.find_spec("test-feature.md")

        assert spec.name == "test-feature"

    def test_find_spec_not_found(self, specs_dir: Path) -> None:
        """Test SpecNotFoundError when spec doesn't exist."""
        workflow = SpecWorkflow(specs_dir)
        with pytest.raises(SpecNotFoundError, match="Spec not found"):
            workflow.find_spec("nonexistent")

    def test_spec_exists(self, specs_dir: Path) -> None:
        """Test spec_exists method."""
        workflow = SpecWorkflow(specs_dir)
        assert workflow.spec_exists("test-feature") is True
        assert workflow.spec_exists("nonexistent") is False

    def test_get_spec_path(self, specs_dir: Path) -> None:
        """Test getting spec path."""
        workflow = SpecWorkflow(specs_dir)
        path = workflow.get_spec_path("test-feature")

        assert path == specs_dir / "planned" / "test-feature.md"


class TestSpecWorkflowMove:
    """Tests for moving specs between stages."""

    @pytest.fixture
    def specs_dir(self, tmp_path: Path) -> Path:
        """Create a specs directory with spec to move."""
        specs_root = tmp_path / "specs"
        # Create all stage directories
        (specs_root / "researching").mkdir(parents=True)
        (specs_root / "planned").mkdir(parents=True)
        (specs_root / "staged").mkdir(parents=True)
        (specs_root / "implementing").mkdir(parents=True)
        (specs_root / "released").mkdir(parents=True)

        spec_content = """---
status: researching
priority: medium
readiness:
  score: 6
---

# Feature to Move
"""
        (specs_root / "researching" / "movable.md").write_text(spec_content)
        return specs_root

    def test_move_to_stage(self, specs_dir: Path) -> None:
        """Test moving a spec to a new stage."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        spec = workflow.find_spec("movable")
        assert spec.stage == Stage.RESEARCHING

        moved = workflow.move_to_stage(spec, Stage.PLANNED)

        assert moved.stage == Stage.PLANNED
        assert moved.path == specs_dir / "planned" / "movable.md"
        assert not (specs_dir / "researching" / "movable.md").exists()
        assert (specs_dir / "planned" / "movable.md").exists()

    def test_move_to_stage_by_name(self, specs_dir: Path) -> None:
        """Test moving a spec by name."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        moved = workflow.move_to_stage("movable", Stage.PLANNED)

        assert moved.stage == Stage.PLANNED
        assert (specs_dir / "planned" / "movable.md").exists()

    def test_move_to_same_stage_fails(self, specs_dir: Path) -> None:
        """Test that moving to same stage raises error."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        with pytest.raises(InvalidStageTransitionError, match="already in stage"):
            workflow.move_to_stage("movable", Stage.RESEARCHING)

    def test_move_creates_target_dir(self, tmp_path: Path) -> None:
        """Test that move creates target directory if missing."""
        specs_root = tmp_path / "specs"
        (specs_root / "researching").mkdir(parents=True)

        spec_content = """---
status: researching
---

# Test
"""
        (specs_root / "researching" / "test.md").write_text(spec_content)

        workflow = SpecWorkflow(specs_root, use_git=False)
        # planned/ doesn't exist yet
        assert not (specs_root / "planned").exists()

        moved = workflow.move_to_stage("test", Stage.PLANNED)

        assert moved.stage == Stage.PLANNED
        assert (specs_root / "planned").exists()

    def test_move_conflict_raises_error(self, specs_dir: Path) -> None:
        """Test that moving to existing file raises error."""
        # Create a conflicting file
        conflict_content = """---
status: ready
---

# Conflict
"""
        (specs_dir / "planned" / "movable.md").write_text(conflict_content)

        workflow = SpecWorkflow(specs_dir, use_git=False)

        with pytest.raises(SpecMoveError, match="already exists"):
            workflow.move_to_stage("movable", Stage.PLANNED)

    def test_move_with_git(self, specs_dir: Path) -> None:
        """Test moving with git mv."""
        workflow = SpecWorkflow(specs_dir, use_git=True)

        source = specs_dir / "researching" / "movable.md"
        dest = specs_dir / "planned" / "movable.md"

        def mock_git_mv(*args: object, **kwargs: object) -> MagicMock:
            """Simulate git mv by actually moving the file."""
            # Extract paths from the command
            cmd = args[0]
            if isinstance(cmd, list) and cmd[0:2] == ["git", "mv"]:
                # Perform the actual move
                source.rename(dest)
            return MagicMock(returncode=0)

        # Mock subprocess.run for git mv
        with patch("subprocess.run", side_effect=mock_git_mv) as mock_run:
            moved = workflow.move_to_stage("movable", Stage.PLANNED)

            # Verify git mv was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0][0:2] == ["git", "mv"]

            assert moved.stage == Stage.PLANNED

    def test_move_git_not_tracked_fallback(self, specs_dir: Path) -> None:
        """Test fallback to regular move when file not tracked."""
        workflow = SpecWorkflow(specs_dir, use_git=True)

        # Mock git mv returning error for untracked file
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="not under version control"
            )

            moved = workflow.move_to_stage("movable", Stage.PLANNED)

            assert moved.stage == Stage.PLANNED
            assert (specs_dir / "planned" / "movable.md").exists()


class TestSpecWorkflowTransitions:
    """Tests for stage transition validation."""

    @pytest.fixture
    def workflow(self, tmp_path: Path) -> SpecWorkflow:
        """Create a workflow instance."""
        return SpecWorkflow(tmp_path / "specs", use_git=False)

    def test_valid_transitions(self, workflow: SpecWorkflow) -> None:
        """Test valid stage transitions through the 5-stage pipeline."""
        # Forward flow: researching -> planned -> staged -> implementing -> released
        assert workflow.validate_transition(Stage.RESEARCHING, Stage.PLANNED)
        assert workflow.validate_transition(Stage.PLANNED, Stage.STAGED)
        assert workflow.validate_transition(Stage.STAGED, Stage.IMPLEMENTING)
        assert workflow.validate_transition(Stage.IMPLEMENTING, Stage.RELEASED)

        # Allowed backtracking
        assert workflow.validate_transition(Stage.PLANNED, Stage.RESEARCHING)
        assert workflow.validate_transition(Stage.STAGED, Stage.PLANNED)
        assert workflow.validate_transition(Stage.IMPLEMENTING, Stage.STAGED)
        assert workflow.validate_transition(Stage.RELEASED, Stage.IMPLEMENTING)

    def test_invalid_transitions(self, workflow: SpecWorkflow) -> None:
        """Test that invalid transitions raise errors."""
        # Cannot skip stages in forward direction
        with pytest.raises(InvalidStageTransitionError):
            workflow.validate_transition(Stage.RESEARCHING, Stage.STAGED)

        with pytest.raises(InvalidStageTransitionError):
            workflow.validate_transition(Stage.PLANNED, Stage.IMPLEMENTING)

    def test_same_stage_transition_fails(self, workflow: SpecWorkflow) -> None:
        """Test that same stage transition fails."""
        with pytest.raises(InvalidStageTransitionError, match="already in stage"):
            workflow.validate_transition(Stage.PLANNED, Stage.PLANNED)


class TestSpecWorkflowPromoteDemote:
    """Tests for promote and demote operations."""

    @pytest.fixture
    def specs_dir(self, tmp_path: Path) -> Path:
        """Create specs in different stages."""
        specs_root = tmp_path / "specs"
        # Create all stage directories (excluding COMPLETED alias)
        for stage in [Stage.RESEARCHING, Stage.PLANNED, Stage.STAGED,
                      Stage.IMPLEMENTING, Stage.RELEASED]:
            (specs_root / stage.value).mkdir(parents=True)

        # Create specs in each stage
        for stage, name in [
            (Stage.RESEARCHING, "researching-spec"),
            (Stage.PLANNED, "planned-spec"),
            (Stage.STAGED, "staged-spec"),
            (Stage.IMPLEMENTING, "implementing-spec"),
            (Stage.RELEASED, "released-spec"),
        ]:
            content = f"""---
status: {stage.value}
---

# {name}
"""
            (specs_root / stage.value / f"{name}.md").write_text(content)

        return specs_root

    def test_promote_researching_to_planned(self, specs_dir: Path) -> None:
        """Test promoting from researching to planned."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        promoted = workflow.promote("researching-spec")

        assert promoted.stage == Stage.PLANNED

    def test_promote_planned_to_staged(self, specs_dir: Path) -> None:
        """Test promoting from planned to staged."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        promoted = workflow.promote("planned-spec")

        assert promoted.stage == Stage.STAGED

    def test_promote_staged_to_implementing(self, specs_dir: Path) -> None:
        """Test promoting from staged to implementing."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        promoted = workflow.promote("staged-spec")

        assert promoted.stage == Stage.IMPLEMENTING

    def test_promote_implementing_to_released(self, specs_dir: Path) -> None:
        """Test promoting from implementing to released."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        promoted = workflow.promote("implementing-spec")

        assert promoted.stage == Stage.RELEASED

    def test_promote_released_fails(self, specs_dir: Path) -> None:
        """Test that promoting released spec fails."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        with pytest.raises(InvalidStageTransitionError, match="already released"):
            workflow.promote("released-spec")

    def test_demote_released_to_implementing(self, specs_dir: Path) -> None:
        """Test demoting from released to implementing."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        demoted = workflow.demote("released-spec")

        assert demoted.stage == Stage.IMPLEMENTING

    def test_demote_implementing_to_staged(self, specs_dir: Path) -> None:
        """Test demoting from implementing to staged."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        demoted = workflow.demote("implementing-spec")

        assert demoted.stage == Stage.STAGED

    def test_demote_staged_to_planned(self, specs_dir: Path) -> None:
        """Test demoting from staged to planned."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        demoted = workflow.demote("staged-spec")

        assert demoted.stage == Stage.PLANNED

    def test_demote_planned_to_researching(self, specs_dir: Path) -> None:
        """Test demoting from planned to researching."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        demoted = workflow.demote("planned-spec")

        assert demoted.stage == Stage.RESEARCHING

    def test_demote_researching_fails(self, specs_dir: Path) -> None:
        """Test that demoting researching spec fails."""
        workflow = SpecWorkflow(specs_dir, use_git=False)

        with pytest.raises(InvalidStageTransitionError, match="earliest stage"):
            workflow.demote("researching-spec")


class TestSpecWorkflowCounts:
    """Tests for spec counting and filtering."""

    @pytest.fixture
    def specs_dir(self, tmp_path: Path) -> Path:
        """Create specs directory with multiple specs."""
        specs_root = tmp_path / "specs"

        # Create all stage directories (excluding COMPLETED alias)
        for stage in [Stage.RESEARCHING, Stage.PLANNED, Stage.STAGED,
                      Stage.IMPLEMENTING, Stage.RELEASED]:
            (specs_root / stage.value).mkdir(parents=True)

        # 2 researching specs
        for i in range(2):
            (specs_root / "researching" / f"research-{i}.md").write_text("""---
status: researching
readiness:
  score: 3
  blockers:
    - needs work
---
# Research
""")

        # 3 planned specs (1 ready, 2 not ready)
        (specs_root / "planned" / "ready-spec.md").write_text("""---
status: ready
readiness:
  score: 9
---
# Ready Spec
""")
        for i in range(2):
            (specs_root / "planned" / f"not-ready-{i}.md").write_text("""---
status: draft
readiness:
  score: 5
  blockers:
    - blocker
---
# Not Ready
""")

        # 1 released spec
        (specs_root / "released" / "done.md").write_text("""---
status: complete
readiness:
  score: 10
---
# Done
""")

        return specs_root

    def test_count_by_stage(self, specs_dir: Path) -> None:
        """Test counting specs by stage."""
        workflow = SpecWorkflow(specs_dir)
        counts = workflow.count_by_stage()

        assert counts[Stage.RESEARCHING] == 2
        assert counts[Stage.PLANNED] == 3
        assert counts[Stage.STAGED] == 0
        assert counts[Stage.IMPLEMENTING] == 0
        assert counts[Stage.RELEASED] == 1

    def test_get_ready_specs(self, specs_dir: Path) -> None:
        """Test getting specs ready for implementation."""
        workflow = SpecWorkflow(specs_dir)
        ready = workflow.get_ready_specs()

        assert len(ready) == 1
        assert ready[0].name == "ready-spec"

    def test_get_blocked_specs(self, specs_dir: Path) -> None:
        """Test getting blocked specs."""
        workflow = SpecWorkflow(specs_dir)
        blocked = workflow.get_blocked_specs()

        # 2 researching + 2 not-ready planned = 4 blocked
        assert len(blocked) == 4
        names = [s.name for s in blocked]
        assert "research-0" in names
        assert "research-1" in names
        assert "not-ready-0" in names
        assert "not-ready-1" in names
