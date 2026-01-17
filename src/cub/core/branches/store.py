"""
Branch bindings store for reading/writing .beads/branches.yaml.

Provides a store class for managing branch-epic bindings persisted
in YAML format.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

import yaml

from cub.core.branches.models import BranchBinding, BranchBindingsFile


class BranchStoreError(Exception):
    """Error from branch store operations."""

    pass


class BranchStore:
    """
    Store for branch-epic bindings.

    Reads and writes bindings from .beads/branches.yaml in the project directory.

    Example:
        >>> store = BranchStore(Path.cwd())
        >>> bindings = store.read()
        >>> binding = store.get_binding("cub-vd6")
    """

    BRANCHES_FILE = ".beads/branches.yaml"

    def __init__(self, project_dir: Path | None = None) -> None:
        """
        Initialize BranchStore.

        Args:
            project_dir: Project directory containing .beads/ (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()
        self._file_path = self.project_dir / self.BRANCHES_FILE

    @property
    def file_path(self) -> Path:
        """Get the path to the branches.yaml file."""
        return self._file_path

    def file_exists(self) -> bool:
        """Check if the branches file exists."""
        return self._file_path.exists()

    def _ensure_beads_dir(self) -> None:
        """Ensure .beads directory exists."""
        beads_dir = self.project_dir / ".beads"
        if not beads_dir.exists():
            raise BranchStoreError(f".beads directory does not exist in {self.project_dir}")

    def _init_file(self) -> None:
        """Initialize branches file if it doesn't exist."""
        self._ensure_beads_dir()
        if not self._file_path.exists():
            content = BranchBindingsFile(bindings=[])
            self._write_file(content)

    def _read_file(self) -> BranchBindingsFile:
        """Read and parse the branches.yaml file."""
        if not self._file_path.exists():
            return BranchBindingsFile(bindings=[])

        try:
            content = self._file_path.read_text()
            data = yaml.safe_load(content) or {}

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
        except yaml.YAMLError as e:
            raise BranchStoreError(f"Failed to parse branches.yaml: {e}")

    def _write_file(self, content: BranchBindingsFile) -> None:
        """Write bindings to the branches.yaml file."""
        self._ensure_beads_dir()

        # Build YAML content with header
        header = """# Branch-Epic Bindings
# Managed by cub - do not edit manually
# Format: YAML with branch bindings array

"""
        # Convert to dict for YAML serialization
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

        yaml_content = yaml.dump(
            data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

        self._file_path.write_text(header + yaml_content)

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
            BranchStoreError: If epic or branch already has a binding
        """
        self._init_file()
        content = self._read_file()

        # Check for existing bindings
        for binding in content.bindings:
            if binding.epic_id == epic_id:
                raise BranchStoreError(
                    f"Epic {epic_id} is already bound to branch: {binding.branch_name}"
                )
            if binding.branch_name == branch_name:
                raise BranchStoreError(
                    f"Branch {branch_name} is already bound to epic: {binding.epic_id}"
                )

        # Create new binding
        new_binding = BranchBinding(
            epic_id=epic_id,
            branch_name=branch_name,
            base_branch=base_branch,
            status="active",
            created_at=datetime.utcnow(),
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
            BranchStoreError: If binding not found
        """
        content = self._read_file()
        found = False
        for binding in content.bindings:
            if binding.epic_id == epic_id:
                binding.pr_number = pr_number
                found = True
                break

        if not found:
            raise BranchStoreError(f"No binding found for epic {epic_id}")

        self._write_file(content)

    def update_status(self, epic_id: str, status: str) -> None:
        """
        Update the status of a binding.

        Args:
            epic_id: Epic ID to update
            status: New status (active, merged, closed)

        Raises:
            BranchStoreError: If binding not found
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
            raise BranchStoreError(f"No binding found for epic {epic_id}")

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
