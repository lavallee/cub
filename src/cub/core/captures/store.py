"""
Capture storage layer for reading/writing captures from filesystem.

Two-tier storage model:
1. Global captures (default): ~/.local/share/cub/captures/{project_id}/
   - Safe from branch deletion
   - Organized by project for cross-project browsing
2. Project captures (imported): {project}/captures/
   - Version-controlled with the project
   - For captures ready to be permanent project records

Uses python-frontmatter for parsing Markdown files with YAML frontmatter.
"""

import os
import secrets
import string
from pathlib import Path

import frontmatter

from cub.core.captures.models import Capture, CaptureStatus
from cub.core.captures.project_id import get_project_id

# Characters for random ID generation (lowercase alphanumeric)
ID_CHARS = string.ascii_lowercase + string.digits
ID_LENGTH = 6


class CaptureStore:
    """
    Storage layer for captures.

    Manages reading/writing capture files from either project directory
    (captures/) or global directory (~/.local/share/cub/captures/).

    Example:
        # Project-level store
        store = CaptureStore.project()
        captures = store.list_captures()
        capture = store.get_capture("cap-001")

        # Global store
        store = CaptureStore.global_store()
        new_id = store.next_id()
        store.save_capture(capture, content)
    """

    def __init__(self, captures_dir: Path):
        """
        Initialize store with a captures directory.

        Args:
            captures_dir: Directory containing capture files
        """
        self.captures_dir = Path(captures_dir)

    def get_captures_dir(self) -> Path:
        """
        Get the captures directory path.

        Returns:
            Path to the captures directory
        """
        return self.captures_dir

    def list_captures(self) -> list[Capture]:
        """
        List all captures in the directory.

        Returns:
            List of Capture objects, sorted by creation date (newest first)

        Raises:
            FileNotFoundError: If captures directory doesn't exist
        """
        if not self.captures_dir.exists():
            raise FileNotFoundError(f"Captures directory not found: {self.captures_dir}")

        captures: list[Capture] = []
        for capture_file in self.captures_dir.glob("*.md"):
            try:
                capture = self._read_capture_file(capture_file)
                captures.append(capture)
            except Exception as e:
                # Skip malformed files but continue processing
                print(f"Warning: Failed to parse {capture_file}: {e}")
                continue

        # Sort by creation date, newest first
        captures.sort(key=lambda c: c.created, reverse=True)
        return captures

    def get_capture(self, capture_id: str) -> Capture:
        """
        Get a single capture by ID.

        Searches all .md files in the directory for a capture with matching ID
        in its frontmatter (since filenames may be slugs).

        Args:
            capture_id: Capture ID (e.g., 'cap-a7x3m2')

        Returns:
            Capture object

        Raises:
            FileNotFoundError: If capture file doesn't exist
            ValueError: If capture file is malformed
        """
        if not self.captures_dir.exists():
            raise FileNotFoundError(f"Capture not found: {capture_id}")

        # First try direct lookup by ID filename (legacy or fallback)
        direct_file = self.captures_dir / f"{capture_id}.md"
        if direct_file.exists():
            return self._read_capture_file(direct_file)

        # Search all .md files for matching ID in frontmatter
        for capture_file in self.captures_dir.glob("*.md"):
            try:
                capture = self._read_capture_file(capture_file)
                if capture.id == capture_id:
                    return capture
            except Exception:
                continue

        raise FileNotFoundError(f"Capture not found: {capture_id}")

    def save_capture(
        self, capture: Capture, content: str, filename: str | None = None
    ) -> Path:
        """
        Write a capture to disk.

        Creates the captures directory if it doesn't exist.

        Args:
            capture: Capture object with metadata
            content: Markdown content body
            filename: Optional custom filename (without .md extension).
                      If not provided, uses capture ID.

        Returns:
            Path to the saved capture file

        Raises:
            OSError: If file cannot be written
        """
        # Ensure directory exists
        self.captures_dir.mkdir(parents=True, exist_ok=True)

        # Create frontmatter post
        post = frontmatter.Post(content)
        post.metadata = capture.to_frontmatter_dict()

        # Use custom filename or fall back to ID
        base_name = filename if filename else capture.id
        capture_file = self.captures_dir / f"{base_name}.md"

        with open(capture_file, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))

        return capture_file

    def archive_capture(self, capture_id: str) -> Path:
        """
        Archive a capture by updating its status and moving to archived/ directory.

        Args:
            capture_id: Capture ID to archive (e.g., 'cap-a7x3m2')

        Returns:
            Path to the archived capture file

        Raises:
            FileNotFoundError: If capture doesn't exist
        """
        # Get current capture file path and read it
        capture_file = self.get_capture_file_path(capture_id)
        post = frontmatter.load(capture_file)

        # Update status in frontmatter
        post.metadata["status"] = CaptureStatus.ARCHIVED.value

        # Create archived directory
        archived_dir = self.captures_dir / "archived"
        archived_dir.mkdir(parents=True, exist_ok=True)

        # Move file to archived directory
        archived_file = archived_dir / capture_file.name
        with open(archived_file, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))

        # Remove original file
        capture_file.unlink()

        return archived_file

    def update_capture(
        self,
        capture_id: str,
        needs_human_review: bool | None = None,
        append_content: str | None = None,
    ) -> Path:
        """
        Update a capture's metadata and/or content.

        Args:
            capture_id: Capture ID to update
            needs_human_review: If provided, set the needs_human_review flag
            append_content: If provided, append this text to the capture body

        Returns:
            Path to the updated capture file

        Raises:
            FileNotFoundError: If capture doesn't exist
        """
        capture_file = self.get_capture_file_path(capture_id)
        post = frontmatter.load(capture_file)

        if needs_human_review is not None:
            post.metadata["needs_human_review"] = needs_human_review

        if append_content is not None:
            post.content = post.content + "\n\n" + append_content

        with open(capture_file, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))

        return capture_file

    def next_id(self, max_attempts: int = 10) -> str:
        """
        Generate a unique random capture ID.

        Generates a random 6-character alphanumeric ID with collision detection.
        Format: cap-XXXXXX (e.g., "cap-a7x3m2")

        Args:
            max_attempts: Maximum collision retry attempts (default 10)

        Returns:
            Unique capture ID (e.g., "cap-a7x3m2")

        Raises:
            RuntimeError: If unable to generate unique ID after max_attempts
        """
        # Create directory if it doesn't exist
        self.captures_dir.mkdir(parents=True, exist_ok=True)

        # Collect existing IDs for collision detection
        existing_ids: set[str] = set()
        for capture_file in self.captures_dir.glob("*.md"):
            try:
                capture = self._read_capture_file(capture_file)
                existing_ids.add(capture.id)
            except Exception:
                # Also check filename-based IDs
                stem = capture_file.stem
                if stem.startswith("cap-"):
                    existing_ids.add(stem)

        # Generate random ID with collision detection
        for _ in range(max_attempts):
            random_suffix = "".join(secrets.choice(ID_CHARS) for _ in range(ID_LENGTH))
            new_id = f"cap-{random_suffix}"
            if new_id not in existing_ids:
                return new_id

        raise RuntimeError(
            f"Failed to generate unique capture ID after {max_attempts} attempts"
        )

    def get_capture_file_path(self, capture_id: str) -> Path:
        """
        Get the file path for a capture by ID.

        Args:
            capture_id: Capture ID (e.g., 'cap-a7x3m2')

        Returns:
            Path to the capture file

        Raises:
            FileNotFoundError: If capture file doesn't exist
        """
        if not self.captures_dir.exists():
            raise FileNotFoundError(f"Capture not found: {capture_id}")

        # First try direct lookup by ID filename
        direct_file = self.captures_dir / f"{capture_id}.md"
        if direct_file.exists():
            return direct_file

        # Search all .md files for matching ID in frontmatter
        for capture_file in self.captures_dir.glob("*.md"):
            try:
                capture = self._read_capture_file(capture_file)
                if capture.id == capture_id:
                    return capture_file
            except Exception:
                continue

        raise FileNotFoundError(f"Capture not found: {capture_id}")

    def _read_capture_file(self, capture_file: Path) -> Capture:
        """
        Read and parse a capture file.

        Args:
            capture_file: Path to capture markdown file

        Returns:
            Capture object

        Raises:
            ValueError: If file is malformed or missing required fields
        """
        # Parse frontmatter
        post = frontmatter.load(capture_file)

        # Convert to Capture model
        return Capture.from_frontmatter_dict(post.metadata)

    @classmethod
    def project(cls, project_dir: Path | None = None) -> "CaptureStore":
        """
        Create a project-level capture store.

        Args:
            project_dir: Project root directory (defaults to current directory)

        Returns:
            CaptureStore for project captures
        """
        if project_dir is None:
            project_dir = Path.cwd()
        captures_dir = project_dir / "captures"
        return cls(captures_dir)

    @classmethod
    def global_store(cls, project_id: str | None = None) -> "CaptureStore":
        """
        Create a global capture store for a specific project.

        Global captures are stored at ~/.local/share/cub/captures/{project_id}/.
        If no project_id is provided, infers it from the current directory.

        Args:
            project_id: Optional project identifier. If None, auto-inferred.

        Returns:
            CaptureStore for project's global captures
        """
        if project_id is None:
            project_id = get_project_id()

        # Get XDG data home directory
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if not xdg_data_home:
            xdg_data_home = os.path.expanduser("~/.local/share")

        captures_dir = Path(xdg_data_home) / "cub" / "captures" / project_id
        return cls(captures_dir)

    @classmethod
    def global_unscoped(cls) -> "CaptureStore":
        """
        Create a global capture store for captures made outside any project.

        Used when not in a git repository or when project cannot be determined.
        Stores captures at ~/.local/share/cub/captures/_global/.

        Returns:
            CaptureStore for unscoped global captures
        """
        # Get XDG data home directory
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if not xdg_data_home:
            xdg_data_home = os.path.expanduser("~/.local/share")

        captures_dir = Path(xdg_data_home) / "cub" / "captures" / "_global"
        return cls(captures_dir)
