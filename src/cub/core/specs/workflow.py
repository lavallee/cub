"""
Spec workflow management for cub.

Provides the SpecWorkflow class that handles finding specs across stage
directories and managing spec lifecycle transitions via git mv.
"""

import re
import subprocess
from pathlib import Path

import frontmatter  # type: ignore[import-untyped]

from cub.core.specs.models import Spec, Stage


class SpecWorkflowError(Exception):
    """Base exception for spec workflow errors."""

    pass


class SpecNotFoundError(SpecWorkflowError):
    """Raised when a spec file cannot be found."""

    pass


class SpecMoveError(SpecWorkflowError):
    """Raised when moving a spec file fails."""

    pass


class InvalidStageTransitionError(SpecWorkflowError):
    """Raised when an invalid stage transition is attempted."""

    pass


class SpecWorkflow:
    """
    Manages spec lifecycle including finding specs and moving between stages.

    The SpecWorkflow class handles:
    - Finding all specs across stage directories
    - Finding specs by name
    - Moving specs between stages using git mv
    - Validating stage transitions

    Stage directories are expected under the specs/ root:
    - specs/researching/
    - specs/planned/
    - specs/completed/

    Example:
        >>> workflow = SpecWorkflow(Path("./specs"))
        >>> specs = workflow.list_specs()
        >>> spec = workflow.find_spec("my-feature")
        >>> workflow.move_to_stage(spec, Stage.PLANNED)
    """

    # Valid stage transitions (from -> allowed destinations)
    # The primary flow is: researching -> planned -> staged -> implementing -> released
    # Some backtracking is allowed for corrections
    VALID_TRANSITIONS: dict[Stage, list[Stage]] = {
        Stage.RESEARCHING: [Stage.PLANNED],
        Stage.PLANNED: [Stage.STAGED, Stage.RESEARCHING],
        Stage.STAGED: [Stage.IMPLEMENTING, Stage.PLANNED],
        Stage.IMPLEMENTING: [Stage.RELEASED, Stage.STAGED],
        Stage.RELEASED: [Stage.IMPLEMENTING],  # Re-open for fixes
    }

    def __init__(self, specs_root: Path, use_git: bool = True) -> None:
        """
        Initialize the SpecWorkflow.

        Args:
            specs_root: Root directory containing stage subdirectories (e.g., ./specs)
            use_git: Whether to use git mv for moving files (default: True)
        """
        self.specs_root = Path(specs_root)
        self.use_git = use_git

    def _get_stage_dir(self, stage: Stage) -> Path:
        """Get the directory path for a stage."""
        return self.specs_root / stage.value

    def _ensure_stage_dirs_exist(self) -> None:
        """Ensure all stage directories exist."""
        for stage in Stage:
            stage_dir = self._get_stage_dir(stage)
            stage_dir.mkdir(parents=True, exist_ok=True)

    def _parse_spec_file(self, path: Path, stage: Stage) -> Spec:
        """
        Parse a spec file and return a Spec model.

        Args:
            path: Path to the spec markdown file
            stage: Stage derived from the file's directory

        Returns:
            Parsed Spec model

        Raises:
            ValueError: If file cannot be parsed
        """
        post = frontmatter.load(path)
        name = path.stem  # Filename without extension

        # Extract title from first markdown heading if present
        title: str | None = None
        content = post.content
        if content:
            # Match first # heading
            match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
            if match:
                title = match.group(1).strip()

        return Spec.from_frontmatter_dict(
            data=post.metadata,
            name=name,
            path=path,
            stage=stage,
            title=title,
        )

    def list_specs(self, stage: Stage | None = None) -> list[Spec]:
        """
        List all specs, optionally filtered by stage.

        Args:
            stage: If provided, only return specs in this stage.
                   If None, return specs from all stages.

        Returns:
            List of Spec objects, sorted by name

        Raises:
            FileNotFoundError: If specs_root doesn't exist
        """
        if not self.specs_root.exists():
            raise FileNotFoundError(f"Specs root not found: {self.specs_root}")

        specs: list[Spec] = []
        # Note: Stage.COMPLETED is an alias for RELEASED and doesn't appear
        # in iteration over Stage (Python enum behavior for aliases)
        stages_to_scan = [stage] if stage else list(Stage)

        for s in stages_to_scan:
            stage_dir = self._get_stage_dir(s)
            if not stage_dir.exists():
                continue

            for spec_file in stage_dir.glob("*.md"):
                try:
                    spec = self._parse_spec_file(spec_file, s)
                    specs.append(spec)
                except Exception as e:
                    # Skip malformed files but continue processing
                    print(f"Warning: Failed to parse {spec_file}: {e}")
                    continue

        # Sort by name
        specs.sort(key=lambda s: s.name)
        return specs

    def find_spec(self, name: str) -> Spec:
        """
        Find a spec by name across all stages.

        Searches all stage directories for a spec with the given name
        (filename without .md extension).

        Args:
            name: Spec name to find (e.g., 'my-feature')

        Returns:
            Found Spec object

        Raises:
            SpecNotFoundError: If spec cannot be found
        """
        # Normalize name (remove .md if present)
        if name.endswith(".md"):
            name = name[:-3]

        for stage in Stage:
            stage_dir = self._get_stage_dir(stage)
            spec_path = stage_dir / f"{name}.md"
            if spec_path.exists():
                return self._parse_spec_file(spec_path, stage)

        raise SpecNotFoundError(f"Spec not found: {name}")

    def get_spec_path(self, name: str) -> Path:
        """
        Get the path to a spec file by name.

        Args:
            name: Spec name to find

        Returns:
            Path to the spec file

        Raises:
            SpecNotFoundError: If spec cannot be found
        """
        spec = self.find_spec(name)
        return spec.path

    def spec_exists(self, name: str) -> bool:
        """
        Check if a spec exists.

        Args:
            name: Spec name to check

        Returns:
            True if spec exists, False otherwise
        """
        try:
            self.find_spec(name)
            return True
        except SpecNotFoundError:
            return False

    def validate_transition(self, from_stage: Stage, to_stage: Stage) -> bool:
        """
        Validate if a stage transition is allowed.

        Args:
            from_stage: Current stage
            to_stage: Target stage

        Returns:
            True if transition is valid

        Raises:
            InvalidStageTransitionError: If transition is not allowed
        """
        if from_stage == to_stage:
            raise InvalidStageTransitionError(
                f"Spec is already in stage: {to_stage.value}"
            )

        allowed = self.VALID_TRANSITIONS.get(from_stage, [])
        if to_stage not in allowed:
            raise InvalidStageTransitionError(
                f"Cannot move from {from_stage.value} to {to_stage.value}. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            )

        return True

    def move_to_stage(
        self,
        spec: Spec | str,
        target_stage: Stage,
        validate: bool = True,
    ) -> Spec:
        """
        Move a spec to a different stage directory.

        Uses git mv if use_git is True (default), otherwise uses regular
        file move. Creates target directory if it doesn't exist.

        Args:
            spec: Spec object or spec name to move
            target_stage: Stage to move the spec to
            validate: If True, validate the transition is allowed (default: True)

        Returns:
            Updated Spec object with new path and stage

        Raises:
            SpecNotFoundError: If spec cannot be found
            InvalidStageTransitionError: If transition is not allowed and validate=True
            SpecMoveError: If the move operation fails
        """
        # Resolve spec if given as string
        if isinstance(spec, str):
            spec = self.find_spec(spec)

        # Validate transition
        if validate:
            self.validate_transition(spec.stage, target_stage)

        # Ensure target directory exists
        target_dir = self._get_stage_dir(target_stage)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Calculate new path
        new_path = target_dir / spec.filename
        old_path = spec.path

        # Check for conflict
        if new_path.exists() and new_path != old_path:
            raise SpecMoveError(
                f"Target file already exists: {new_path}"
            )

        # Perform the move
        if self.use_git:
            self._git_mv(old_path, new_path)
        else:
            old_path.rename(new_path)

        # Return updated spec
        return self._parse_spec_file(new_path, target_stage)

    def _git_mv(self, source: Path, dest: Path) -> None:
        """
        Move a file using git mv.

        Args:
            source: Source file path
            dest: Destination file path

        Raises:
            SpecMoveError: If git mv fails
        """
        try:
            result = subprocess.run(
                ["git", "mv", str(source), str(dest)],
                capture_output=True,
                text=True,
                check=False,
                cwd=self.specs_root.parent,  # Run from project root
            )
            if result.returncode != 0:
                # If git mv fails, try regular move
                # (file might not be tracked)
                if "not under version control" in result.stderr:
                    source.rename(dest)
                else:
                    raise SpecMoveError(
                        f"git mv failed: {result.stderr.strip()}"
                    )
        except FileNotFoundError:
            # git not available, fall back to regular move
            source.rename(dest)

    def promote(self, spec: Spec | str) -> Spec:
        """
        Promote a spec to the next stage.

        Promotion order: researching -> planned -> staged -> implementing -> released

        Args:
            spec: Spec object or spec name to promote

        Returns:
            Updated Spec object

        Raises:
            SpecNotFoundError: If spec cannot be found
            InvalidStageTransitionError: If spec is already released
        """
        if isinstance(spec, str):
            spec = self.find_spec(spec)

        # Define promotion order
        promotion_map: dict[Stage, Stage] = {
            Stage.RESEARCHING: Stage.PLANNED,
            Stage.PLANNED: Stage.STAGED,
            Stage.STAGED: Stage.IMPLEMENTING,
            Stage.IMPLEMENTING: Stage.RELEASED,
        }

        if spec.stage in promotion_map:
            return self.move_to_stage(spec, promotion_map[spec.stage])
        else:
            raise InvalidStageTransitionError(
                f"Cannot promote spec in {spec.stage.value} stage - already released"
            )

    def demote(self, spec: Spec | str) -> Spec:
        """
        Demote a spec to the previous stage.

        Demotion order: released -> implementing -> staged -> planned -> researching

        Args:
            spec: Spec object or spec name to demote

        Returns:
            Updated Spec object

        Raises:
            SpecNotFoundError: If spec cannot be found
            InvalidStageTransitionError: If spec is already in researching
        """
        if isinstance(spec, str):
            spec = self.find_spec(spec)

        # Define demotion order
        demotion_map: dict[Stage, Stage] = {
            Stage.RELEASED: Stage.IMPLEMENTING,
            Stage.IMPLEMENTING: Stage.STAGED,
            Stage.STAGED: Stage.PLANNED,
            Stage.PLANNED: Stage.RESEARCHING,
        }

        if spec.stage in demotion_map:
            return self.move_to_stage(spec, demotion_map[spec.stage])
        else:
            raise InvalidStageTransitionError(
                f"Cannot demote spec in {spec.stage.value} stage - already at earliest stage"
            )

    def count_by_stage(self) -> dict[Stage, int]:
        """
        Count specs in each stage.

        Returns:
            Dictionary mapping stages to spec counts
        """
        counts: dict[Stage, int] = {stage: 0 for stage in Stage}

        for stage in Stage:
            stage_dir = self._get_stage_dir(stage)
            if stage_dir.exists():
                counts[stage] = len(list(stage_dir.glob("*.md")))

        return counts

    def get_ready_specs(self) -> list[Spec]:
        """
        Get specs that are ready for implementation.

        Returns specs in the PLANNED stage with readiness score >= 7
        and no blockers.

        Returns:
            List of ready Spec objects
        """
        planned_specs = self.list_specs(Stage.PLANNED)
        return [s for s in planned_specs if s.is_ready_for_implementation]

    def get_blocked_specs(self) -> list[Spec]:
        """
        Get specs that have blockers.

        Returns specs with non-empty blockers list.

        Returns:
            List of blocked Spec objects
        """
        all_specs = self.list_specs()
        return [s for s in all_specs if len(s.readiness.blockers) > 0]
