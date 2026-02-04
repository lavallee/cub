"""
Artifact path management for cub ledger.

Manages artifact storage with flattened numbering at the task level.
Replaces the old attempts/ subdirectory structure with direct task-level
artifact files: {task_id}/{attempt:03d}-{type}.{ext}
"""

from pathlib import Path


class ArtifactManager:
    """Manages artifact paths and auto-numbering for task attempts.

    Artifacts are stored directly in the task directory without an attempts/
    subdirectory, using a flattened numbering scheme:
    - .cub/ledger/by-task/{task_id}/001-prompt.md
    - .cub/ledger/by-task/{task_id}/001-harness.jsonl
    - .cub/ledger/by-task/{task_id}/001-patch.diff
    - .cub/ledger/by-task/{task_id}/002-prompt.md

    Supported artifact types:
    - prompt: Task prompt with YAML frontmatter (.md)
    - harness: Harness execution log in JSONL format (.jsonl)
    - patch: Git diff/patch file (.diff)

    Example:
        >>> manager = ArtifactManager(Path(".cub/ledger"))
        >>> path = manager.get_artifact_path("cub-048a-0.1", 1, "prompt")
        >>> print(path)
        .cub/ledger/by-task/cub-048a-0.1/001-prompt.md

        >>> # Auto-detect next attempt number
        >>> next_num = manager.get_next_attempt_number("cub-048a-0.1")
        >>> path = manager.get_artifact_path("cub-048a-0.1", next_num, "prompt")
    """

    # Artifact type to file extension mapping
    ARTIFACT_EXTENSIONS = {
        "prompt": ".md",
        "harness": ".jsonl",
        "patch": ".diff",
    }

    def __init__(self, ledger_dir: Path) -> None:
        """Initialize artifact manager.

        Args:
            ledger_dir: Path to .cub/ledger directory
        """
        self.ledger_dir = ledger_dir
        self.by_task_dir = ledger_dir / "by-task"

    def get_artifact_path(
        self,
        task_id: str,
        attempt_number: int,
        artifact_type: str
    ) -> Path:
        """Get the path for an artifact file.

        Args:
            task_id: Task ID (e.g., 'cub-048a-0.1' or 'beads-abc')
            attempt_number: Attempt sequence number (1-based)
            artifact_type: Type of artifact ('prompt', 'harness', or 'patch')

        Returns:
            Path to the artifact file

        Raises:
            ValueError: If artifact_type is not recognized

        Example:
            >>> manager = ArtifactManager(Path(".cub/ledger"))
            >>> path = manager.get_artifact_path("cub-048a-0.1", 1, "prompt")
            >>> str(path)
            '.cub/ledger/by-task/cub-048a-0.1/001-prompt.md'
        """
        if artifact_type not in self.ARTIFACT_EXTENSIONS:
            valid_types = ", ".join(self.ARTIFACT_EXTENSIONS.keys())
            raise ValueError(
                f"Invalid artifact type '{artifact_type}'. "
                f"Must be one of: {valid_types}"
            )

        ext = self.ARTIFACT_EXTENSIONS[artifact_type]
        task_dir = self.by_task_dir / task_id

        # Format: {attempt:03d}-{type}.{ext}
        # Example: 001-prompt.md, 002-harness.jsonl
        filename = f"{attempt_number:03d}-{artifact_type}{ext}"

        return task_dir / filename

    def get_next_attempt_number(self, task_id: str) -> int:
        """Auto-detect the next attempt number based on existing files.

        Scans the task directory for existing artifact files and determines
        the next available attempt number by finding the highest existing
        attempt number and adding 1.

        Args:
            task_id: Task ID to check

        Returns:
            Next attempt number (1-based). Returns 1 if no artifacts exist.

        Example:
            >>> manager = ArtifactManager(Path(".cub/ledger"))
            >>> # If 001-prompt.md and 001-harness.jsonl exist:
            >>> manager.get_next_attempt_number("cub-048a-0.1")
            2
            >>> # If no artifacts exist:
            >>> manager.get_next_attempt_number("cub-new-task")
            1
        """
        task_dir = self.by_task_dir / task_id

        # If task directory doesn't exist, start at 1
        if not task_dir.exists():
            return 1

        max_attempt = 0

        # Scan for all artifact files matching pattern: NNN-*.ext
        for artifact_file in task_dir.iterdir():
            if not artifact_file.is_file():
                continue

            # Parse attempt number from filename (e.g., "001-prompt.md" -> 1)
            name = artifact_file.name
            if len(name) >= 4 and name[3] == "-":
                try:
                    attempt_num = int(name[:3])
                    max_attempt = max(max_attempt, attempt_num)
                except ValueError:
                    # Not a valid attempt number, skip
                    continue

        return max_attempt + 1

    def list_attempts(self, task_id: str) -> list[int]:
        """List all attempt numbers for a task.

        Scans the task directory and returns a sorted list of all attempt
        numbers that have at least one artifact file.

        Args:
            task_id: Task ID to check

        Returns:
            Sorted list of attempt numbers (1-based)

        Example:
            >>> manager = ArtifactManager(Path(".cub/ledger"))
            >>> manager.list_attempts("cub-048a-0.1")
            [1, 2, 3]
        """
        task_dir = self.by_task_dir / task_id

        if not task_dir.exists():
            return []

        attempts = set()

        for artifact_file in task_dir.iterdir():
            if not artifact_file.is_file():
                continue

            # Parse attempt number from filename
            name = artifact_file.name
            if len(name) >= 4 and name[3] == "-":
                try:
                    attempt_num = int(name[:3])
                    attempts.add(attempt_num)
                except ValueError:
                    continue

        return sorted(list(attempts))

    def get_task_artifacts(
        self,
        task_id: str,
        attempt_number: int
    ) -> dict[str, Path]:
        """Get all artifact paths for a specific attempt.

        Returns a dictionary mapping artifact type to path for all artifacts
        that exist for the given attempt.

        Args:
            task_id: Task ID to check
            attempt_number: Attempt number to get artifacts for

        Returns:
            Dictionary mapping artifact type to Path (only for existing files)

        Example:
            >>> manager = ArtifactManager(Path(".cub/ledger"))
            >>> artifacts = manager.get_task_artifacts("cub-048a-0.1", 1)
            >>> print(artifacts)
            {'prompt': PosixPath('.cub/ledger/by-task/cub-048a-0.1/001-prompt.md'),
             'harness': PosixPath('.cub/ledger/by-task/cub-048a-0.1/001-harness.jsonl')}
        """
        artifacts = {}

        for artifact_type in self.ARTIFACT_EXTENSIONS:
            path = self.get_artifact_path(task_id, attempt_number, artifact_type)
            if path.exists():
                artifacts[artifact_type] = path

        return artifacts

    def ensure_task_dir(self, task_id: str) -> Path:
        """Ensure task directory exists and return its path.

        Creates the task directory if it doesn't exist.

        Args:
            task_id: Task ID

        Returns:
            Path to task directory

        Example:
            >>> manager = ArtifactManager(Path(".cub/ledger"))
            >>> task_dir = manager.ensure_task_dir("cub-new-task")
            >>> task_dir.exists()
            True
        """
        task_dir = self.by_task_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir
