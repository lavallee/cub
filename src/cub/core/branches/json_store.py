"""
JSON branch bindings store for reading/writing .cub/branches.json.

Provides a store class for managing branch-epic bindings persisted
in JSON format for projects not using beads.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cub.core.branches.models import BranchBinding, BranchBindingsFile


class JsonBranchStoreError(Exception):
    """Error from JSON branch store operations."""

    pass


class JsonBranchStore:
    """
    Store for branch-epic bindings using JSON format.

    Reads and writes bindings from .cub/branches.json in the project directory.
    This is the JSON backend equivalent of the beads BranchStore.

    Example:
        >>> store = JsonBranchStore(Path.cwd())
        >>> bindings = store.read()
        >>> binding = store.get_binding("cub-vd6")
    """

    BRANCHES_FILE = ".cub/branches.json"

    def __init__(self, project_dir: Path | None = None) -> None:
        """
        Initialize JsonBranchStore.

        Args:
            project_dir: Project directory containing .cub/ (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()
        self._file_path = self.project_dir / self.BRANCHES_FILE

    @property
    def file_path(self) -> Path:
        """Get the path to the branches.json file."""
        return self._file_path

    def file_exists(self) -> bool:
        """Check if the branches file exists."""
        return self._file_path.exists()

    def _ensure_cub_dir(self) -> None:
        """Ensure .cub directory exists."""
        cub_dir = self.project_dir / ".cub"
        if not cub_dir.exists():
            cub_dir.mkdir(parents=True, exist_ok=True)

    def _init_file(self) -> None:
        """Initialize branches file if it doesn't exist."""
        self._ensure_cub_dir()
        if not self._file_path.exists():
            content = BranchBindingsFile(bindings=[])
            self._write_file(content)

    def _read_file(self) -> BranchBindingsFile:
        """Read and parse the branches.json file."""
        if not self._file_path.exists():
            return BranchBindingsFile(bindings=[])

        try:
            content = self._file_path.read_text()
            data = json.loads(content)

            # Handle empty bindings
            if "bindings" not in data:
                return BranchBindingsFile(bindings=[])

            # Convert datetime strings if needed
            bindings = []
            for b in data.get("bindings", []):
                if b is None:
                    continue
                # Handle created_at datetime
                if isinstance(b.get("created_at"), str):
                    try:
                        b["created_at"] = datetime.fromisoformat(
                            b["created_at"].replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass
                bindings.append(BranchBinding.model_validate(b))

            return BranchBindingsFile(bindings=bindings)
        except json.JSONDecodeError as e:
            raise JsonBranchStoreError(f"Failed to parse branches.json: {e}")

    def _write_file(self, content: BranchBindingsFile) -> None:
        """Write bindings to the branches.json file atomically."""
        self._ensure_cub_dir()

        # Convert to dict for JSON serialization
        bindings_data = []
        for b in content.bindings:
            binding_dict = b.model_dump()
            # Format datetime as ISO string with Z suffix
            if isinstance(binding_dict.get("created_at"), datetime):
                binding_dict["created_at"] = binding_dict["created_at"].strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            bindings_data.append(binding_dict)

        data = {"bindings": bindings_data}

        # Atomic write: temp file + replace
        fd, temp_path = tempfile.mkstemp(
            dir=self._file_path.parent,
            prefix=".branches_",
            suffix=".json.tmp",
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")  # Add trailing newline

            # Atomic rename (replaces existing file)
            os.replace(temp_path, self._file_path)

        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def read(self) -> list[BranchBinding]:
        """
        Read all bindings from the store.

        Returns:
            List of BranchBinding objects
        """
        return self._read_file().bindings

    def get_binding(self, epic_id: str) -> BranchBinding | None:
        """
        Get binding for an epic ID.

        Args:
            epic_id: The epic ID to look up

        Returns:
            BranchBinding if found, None otherwise
        """
        bindings = self.read()
        for binding in bindings:
            if binding.epic_id == epic_id:
                return binding
        return None

    def get_binding_by_branch(self, branch: str) -> BranchBinding | None:
        """
        Get binding for a branch name.

        Args:
            branch: The branch name to look up

        Returns:
            BranchBinding if found, None otherwise
        """
        bindings = self.read()
        for binding in bindings:
            if binding.branch_name == branch:
                return binding
        return None

    def add_binding(
        self,
        epic_id: str,
        branch_name: str,
        base_branch: str = "main",
    ) -> BranchBinding:
        """
        Add a new branch binding.

        Args:
            epic_id: Epic ID to bind
            branch_name: Git branch name
            base_branch: Target branch for merging

        Returns:
            The created BranchBinding

        Raises:
            JsonBranchStoreError: If epic or branch already has a binding
        """
        self._init_file()
        content = self._read_file()

        # Check for existing bindings
        for binding in content.bindings:
            if binding.epic_id == epic_id:
                raise JsonBranchStoreError(
                    f"Epic {epic_id} is already bound to branch: {binding.branch_name}"
                )
            if binding.branch_name == branch_name:
                raise JsonBranchStoreError(
                    f"Branch {branch_name} is already bound to epic: {binding.epic_id}"
                )

        # Create new binding
        new_binding = BranchBinding(
            epic_id=epic_id,
            branch_name=branch_name,
            base_branch=base_branch,
            status="active",
            created_at=datetime.now(timezone.utc),
            pr_number=None,
            merged=False,
        )

        content.bindings.append(new_binding)
        self._write_file(content)
        return new_binding

    def update_pr(self, epic_id: str, pr_number: int | None) -> None:
        """
        Update the PR number for a binding.

        Args:
            epic_id: Epic ID to update
            pr_number: PR number (or None to clear)

        Raises:
            JsonBranchStoreError: If binding not found
        """
        content = self._read_file()
        found = False
        for binding in content.bindings:
            if binding.epic_id == epic_id:
                binding.pr_number = pr_number
                found = True
                break

        if not found:
            raise JsonBranchStoreError(f"No binding found for epic {epic_id}")

        self._write_file(content)

    def update_status(self, epic_id: str, status: str) -> None:
        """
        Update the status of a binding.

        Args:
            epic_id: Epic ID to update
            status: New status (active, merged, closed)

        Raises:
            JsonBranchStoreError: If binding not found
        """
        content = self._read_file()
        found = False
        for binding in content.bindings:
            if binding.epic_id == epic_id:
                binding.status = status
                if status == "merged":
                    binding.merged = True
                found = True
                break

        if not found:
            raise JsonBranchStoreError(f"No binding found for epic {epic_id}")

        self._write_file(content)

    def remove_binding(self, epic_id: str) -> None:
        """
        Remove a binding for an epic.

        Args:
            epic_id: Epic ID to unbind
        """
        content = self._read_file()
        content.bindings = [b for b in content.bindings if b.epic_id != epic_id]
        self._write_file(content)

    def get_bindings_by_status(self, status: str) -> list[BranchBinding]:
        """
        Get all bindings with a specific status.

        Args:
            status: Status to filter by (active, merged, closed)

        Returns:
            List of matching BranchBinding objects
        """
        return [b for b in self.read() if b.status == status]

    @staticmethod
    def get_current_branch() -> str | None:
        """
        Get the current git branch name.

        Returns:
            Branch name or None if not in a git repo
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
                if branch and branch != "HEAD":
                    return branch
            return None
        except (OSError, FileNotFoundError):
            return None

    @staticmethod
    def git_branch_exists(branch: str) -> bool:
        """
        Check if a git branch exists.

        Args:
            branch: Branch name to check

        Returns:
            True if branch exists
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", branch],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except (OSError, FileNotFoundError):
            return False
