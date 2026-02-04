"""
Tests for ledger artifact manager.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from cub.core.ledger.artifacts import ArtifactManager


class TestArtifactManager:
    """Test suite for ArtifactManager."""

    def test_get_artifact_path_prompt(self, tmp_path: Path) -> None:
        """Test getting path for prompt artifact."""
        manager = ArtifactManager(tmp_path)

        path = manager.get_artifact_path("cub-048a-0.1", 1, "prompt")

        assert path == tmp_path / "by-task" / "cub-048a-0.1" / "001-prompt.md"

    def test_get_artifact_path_harness(self, tmp_path: Path) -> None:
        """Test getting path for harness artifact."""
        manager = ArtifactManager(tmp_path)

        path = manager.get_artifact_path("cub-048a-0.1", 2, "harness")

        assert path == tmp_path / "by-task" / "cub-048a-0.1" / "002-harness.jsonl"

    def test_get_artifact_path_patch(self, tmp_path: Path) -> None:
        """Test getting path for patch artifact."""
        manager = ArtifactManager(tmp_path)

        path = manager.get_artifact_path("cub-048a-0.1", 3, "patch")

        assert path == tmp_path / "by-task" / "cub-048a-0.1" / "003-patch.diff"

    def test_get_artifact_path_invalid_type(self, tmp_path: Path) -> None:
        """Test getting path with invalid artifact type raises error."""
        manager = ArtifactManager(tmp_path)

        with pytest.raises(ValueError) as exc_info:
            manager.get_artifact_path("cub-048a-0.1", 1, "invalid")

        assert "Invalid artifact type 'invalid'" in str(exc_info.value)
        assert "prompt" in str(exc_info.value)
        assert "harness" in str(exc_info.value)
        assert "patch" in str(exc_info.value)

    def test_get_artifact_path_old_random_id(self, tmp_path: Path) -> None:
        """Test getting path works with old random-style task IDs."""
        manager = ArtifactManager(tmp_path)

        path = manager.get_artifact_path("beads-abc123", 1, "prompt")

        assert path == tmp_path / "by-task" / "beads-abc123" / "001-prompt.md"

    def test_get_artifact_path_zero_padding(self, tmp_path: Path) -> None:
        """Test that attempt numbers are zero-padded to 3 digits."""
        manager = ArtifactManager(tmp_path)

        path1 = manager.get_artifact_path("cub-048a-0.1", 1, "prompt")
        path5 = manager.get_artifact_path("cub-048a-0.1", 5, "prompt")
        path42 = manager.get_artifact_path("cub-048a-0.1", 42, "prompt")
        path123 = manager.get_artifact_path("cub-048a-0.1", 123, "prompt")

        assert path1.name == "001-prompt.md"
        assert path5.name == "005-prompt.md"
        assert path42.name == "042-prompt.md"
        assert path123.name == "123-prompt.md"

    def test_get_next_attempt_number_no_artifacts(self, tmp_path: Path) -> None:
        """Test getting next attempt number when no artifacts exist."""
        manager = ArtifactManager(tmp_path)

        next_num = manager.get_next_attempt_number("cub-048a-0.1")

        assert next_num == 1

    def test_get_next_attempt_number_no_task_dir(self, tmp_path: Path) -> None:
        """Test getting next attempt number when task directory doesn't exist."""
        manager = ArtifactManager(tmp_path)

        next_num = manager.get_next_attempt_number("nonexistent-task")

        assert next_num == 1

    def test_get_next_attempt_number_with_artifacts(self, tmp_path: Path) -> None:
        """Test getting next attempt number with existing artifacts."""
        manager = ArtifactManager(tmp_path)
        task_dir = tmp_path / "by-task" / "cub-048a-0.1"
        task_dir.mkdir(parents=True)

        # Create some artifacts
        (task_dir / "001-prompt.md").touch()
        (task_dir / "001-harness.jsonl").touch()

        next_num = manager.get_next_attempt_number("cub-048a-0.1")

        assert next_num == 2

    def test_get_next_attempt_number_multiple_attempts(self, tmp_path: Path) -> None:
        """Test getting next attempt number with multiple existing attempts."""
        manager = ArtifactManager(tmp_path)
        task_dir = tmp_path / "by-task" / "cub-048a-0.1"
        task_dir.mkdir(parents=True)

        # Create artifacts for attempts 1, 2, and 5
        (task_dir / "001-prompt.md").touch()
        (task_dir / "002-prompt.md").touch()
        (task_dir / "005-prompt.md").touch()
        (task_dir / "005-harness.jsonl").touch()

        next_num = manager.get_next_attempt_number("cub-048a-0.1")

        # Should be max + 1, so 6
        assert next_num == 6

    def test_get_next_attempt_number_ignores_non_artifacts(self, tmp_path: Path) -> None:
        """Test that next attempt number ignores non-artifact files."""
        manager = ArtifactManager(tmp_path)
        task_dir = tmp_path / "by-task" / "cub-048a-0.1"
        task_dir.mkdir(parents=True)

        # Create some artifacts and some non-matching files
        (task_dir / "001-prompt.md").touch()
        (task_dir / "entry.json").touch()
        (task_dir / "README.md").touch()
        (task_dir / "notes.txt").touch()

        next_num = manager.get_next_attempt_number("cub-048a-0.1")

        assert next_num == 2

    def test_get_next_attempt_number_ignores_subdirs(self, tmp_path: Path) -> None:
        """Test that next attempt number ignores subdirectories."""
        manager = ArtifactManager(tmp_path)
        task_dir = tmp_path / "by-task" / "cub-048a-0.1"
        task_dir.mkdir(parents=True)

        # Create artifacts and a subdirectory
        (task_dir / "001-prompt.md").touch()
        (task_dir / "attempts").mkdir()
        (task_dir / "attempts" / "002-prompt.md").touch()

        next_num = manager.get_next_attempt_number("cub-048a-0.1")

        # Should ignore the attempts/ subdirectory
        assert next_num == 2

    def test_list_attempts_empty(self, tmp_path: Path) -> None:
        """Test listing attempts when none exist."""
        manager = ArtifactManager(tmp_path)

        attempts = manager.list_attempts("cub-048a-0.1")

        assert attempts == []

    def test_list_attempts_no_task_dir(self, tmp_path: Path) -> None:
        """Test listing attempts when task directory doesn't exist."""
        manager = ArtifactManager(tmp_path)

        attempts = manager.list_attempts("nonexistent-task")

        assert attempts == []

    def test_list_attempts_single_attempt(self, tmp_path: Path) -> None:
        """Test listing attempts with a single attempt."""
        manager = ArtifactManager(tmp_path)
        task_dir = tmp_path / "by-task" / "cub-048a-0.1"
        task_dir.mkdir(parents=True)

        (task_dir / "001-prompt.md").touch()
        (task_dir / "001-harness.jsonl").touch()

        attempts = manager.list_attempts("cub-048a-0.1")

        assert attempts == [1]

    def test_list_attempts_multiple_attempts(self, tmp_path: Path) -> None:
        """Test listing attempts with multiple attempts."""
        manager = ArtifactManager(tmp_path)
        task_dir = tmp_path / "by-task" / "cub-048a-0.1"
        task_dir.mkdir(parents=True)

        # Create artifacts for attempts 1, 3, and 5
        (task_dir / "001-prompt.md").touch()
        (task_dir / "003-harness.jsonl").touch()
        (task_dir / "005-prompt.md").touch()
        (task_dir / "005-patch.diff").touch()

        attempts = manager.list_attempts("cub-048a-0.1")

        assert attempts == [1, 3, 5]

    def test_list_attempts_sorted(self, tmp_path: Path) -> None:
        """Test that attempts are returned in sorted order."""
        manager = ArtifactManager(tmp_path)
        task_dir = tmp_path / "by-task" / "cub-048a-0.1"
        task_dir.mkdir(parents=True)

        # Create in non-sorted order
        (task_dir / "010-prompt.md").touch()
        (task_dir / "002-prompt.md").touch()
        (task_dir / "005-prompt.md").touch()
        (task_dir / "001-prompt.md").touch()

        attempts = manager.list_attempts("cub-048a-0.1")

        assert attempts == [1, 2, 5, 10]

    def test_get_task_artifacts_empty(self, tmp_path: Path) -> None:
        """Test getting task artifacts when none exist."""
        manager = ArtifactManager(tmp_path)

        artifacts = manager.get_task_artifacts("cub-048a-0.1", 1)

        assert artifacts == {}

    def test_get_task_artifacts_single_type(self, tmp_path: Path) -> None:
        """Test getting task artifacts with only one type."""
        manager = ArtifactManager(tmp_path)
        task_dir = tmp_path / "by-task" / "cub-048a-0.1"
        task_dir.mkdir(parents=True)

        prompt_path = task_dir / "001-prompt.md"
        prompt_path.touch()

        artifacts = manager.get_task_artifacts("cub-048a-0.1", 1)

        assert artifacts == {"prompt": prompt_path}

    def test_get_task_artifacts_multiple_types(self, tmp_path: Path) -> None:
        """Test getting task artifacts with multiple types."""
        manager = ArtifactManager(tmp_path)
        task_dir = tmp_path / "by-task" / "cub-048a-0.1"
        task_dir.mkdir(parents=True)

        prompt_path = task_dir / "001-prompt.md"
        harness_path = task_dir / "001-harness.jsonl"
        patch_path = task_dir / "001-patch.diff"

        prompt_path.touch()
        harness_path.touch()
        patch_path.touch()

        artifacts = manager.get_task_artifacts("cub-048a-0.1", 1)

        assert artifacts == {
            "prompt": prompt_path,
            "harness": harness_path,
            "patch": patch_path,
        }

    def test_get_task_artifacts_different_attempt(self, tmp_path: Path) -> None:
        """Test getting artifacts for specific attempt number."""
        manager = ArtifactManager(tmp_path)
        task_dir = tmp_path / "by-task" / "cub-048a-0.1"
        task_dir.mkdir(parents=True)

        # Create artifacts for attempts 1 and 2
        (task_dir / "001-prompt.md").touch()
        prompt2_path = task_dir / "002-prompt.md"
        harness2_path = task_dir / "002-harness.jsonl"
        prompt2_path.touch()
        harness2_path.touch()

        artifacts = manager.get_task_artifacts("cub-048a-0.1", 2)

        assert artifacts == {
            "prompt": prompt2_path,
            "harness": harness2_path,
        }

    def test_ensure_task_dir_creates_dir(self, tmp_path: Path) -> None:
        """Test that ensure_task_dir creates the directory."""
        manager = ArtifactManager(tmp_path)
        task_id = "cub-048a-0.1"

        task_dir = manager.ensure_task_dir(task_id)

        assert task_dir.exists()
        assert task_dir.is_dir()
        assert task_dir == tmp_path / "by-task" / task_id

    def test_ensure_task_dir_idempotent(self, tmp_path: Path) -> None:
        """Test that ensure_task_dir is idempotent."""
        manager = ArtifactManager(tmp_path)
        task_id = "cub-048a-0.1"

        task_dir1 = manager.ensure_task_dir(task_id)
        task_dir2 = manager.ensure_task_dir(task_id)

        assert task_dir1 == task_dir2
        assert task_dir1.exists()

    def test_ensure_task_dir_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test that ensure_task_dir creates parent directories."""
        # Use a fresh temp directory that doesn't have by-task/ yet
        with TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir) / "ledger"
            manager = ArtifactManager(ledger_dir)

            task_dir = manager.ensure_task_dir("cub-048a-0.1")

            assert task_dir.exists()
            assert task_dir.parent.exists()  # by-task/
            assert task_dir.parent.parent.exists()  # ledger/

    def test_acceptance_criteria_example(self, tmp_path: Path) -> None:
        """Test the example from acceptance criteria."""
        manager = ArtifactManager(tmp_path)

        # Test: get_artifact_path("cub-048a-0.1", 1, "prompt") returns correct Path
        path = manager.get_artifact_path("cub-048a-0.1", 1, "prompt")

        expected = tmp_path / "by-task" / "cub-048a-0.1" / "001-prompt.md"
        assert path == expected

    def test_auto_increment_workflow(self, tmp_path: Path) -> None:
        """Test the full workflow of auto-incrementing attempts."""
        manager = ArtifactManager(tmp_path)
        task_id = "cub-048a-0.1"

        # First attempt
        attempt1 = manager.get_next_attempt_number(task_id)
        assert attempt1 == 1

        # Create first attempt's artifacts
        manager.ensure_task_dir(task_id)
        path1 = manager.get_artifact_path(task_id, attempt1, "prompt")
        path1.write_text("First attempt")

        # Second attempt should auto-increment
        attempt2 = manager.get_next_attempt_number(task_id)
        assert attempt2 == 2

        # Create second attempt's artifacts
        path2 = manager.get_artifact_path(task_id, attempt2, "prompt")
        path2.write_text("Second attempt")

        # Third attempt
        attempt3 = manager.get_next_attempt_number(task_id)
        assert attempt3 == 3

    def test_no_attempts_subdirectory(self, tmp_path: Path) -> None:
        """Test that artifacts are NOT created in attempts/ subdirectory."""
        manager = ArtifactManager(tmp_path)
        task_id = "cub-048a-0.1"

        path = manager.get_artifact_path(task_id, 1, "prompt")

        # Verify the path does NOT contain "attempts"
        assert "attempts" not in path.parts

        # Verify the structure is: by-task/{task_id}/{artifact}
        assert path.parts[-3] == "by-task"
        assert path.parts[-2] == task_id
        assert path.parts[-1] == "001-prompt.md"

    def test_works_with_old_random_ids(self, tmp_path: Path) -> None:
        """Test that the manager works with old random-style task IDs."""
        manager = ArtifactManager(tmp_path)
        old_task_id = "beads-abc123xyz"

        # Should work for get_artifact_path
        path = manager.get_artifact_path(old_task_id, 1, "prompt")
        assert path == tmp_path / "by-task" / old_task_id / "001-prompt.md"

        # Should work for get_next_attempt_number
        next_num = manager.get_next_attempt_number(old_task_id)
        assert next_num == 1

        # Should work for ensure_task_dir
        task_dir = manager.ensure_task_dir(old_task_id)
        assert task_dir.exists()
        assert task_dir.name == old_task_id

    def test_works_with_hierarchical_ids(self, tmp_path: Path) -> None:
        """Test that the manager works with new hierarchical task IDs."""
        manager = ArtifactManager(tmp_path)
        hierarchical_ids = [
            "cub-048a-0.1",
            "cub-048a-1.4",
            "cub-e2p.2",
            "cub-001",
        ]

        for task_id in hierarchical_ids:
            # Should work for all operations
            path = manager.get_artifact_path(task_id, 1, "prompt")
            assert task_id in str(path)

            next_num = manager.get_next_attempt_number(task_id)
            assert next_num == 1

            task_dir = manager.ensure_task_dir(task_id)
            assert task_dir.exists()
