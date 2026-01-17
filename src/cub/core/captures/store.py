"""
Capture storage layer for reading/writing captures from filesystem.

Handles both project-level (captures/) and global (~/.local/share/cub/captures/)
capture storage. Uses python-frontmatter for parsing Markdown files with YAML
frontmatter.
"""

import os
from pathlib import Path

import frontmatter  # type: ignore[import-untyped]

from cub.core.captures.models import Capture


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
        for capture_file in self.captures_dir.glob("cap-*.md"):
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

        Args:
            capture_id: Capture ID (e.g., 'cap-001')

        Returns:
            Capture object

        Raises:
            FileNotFoundError: If capture file doesn't exist
            ValueError: If capture file is malformed
        """
        capture_file = self.captures_dir / f"{capture_id}.md"
        if not capture_file.exists():
            raise FileNotFoundError(f"Capture not found: {capture_id}")

        return self._read_capture_file(capture_file)

    def save_capture(self, capture: Capture, content: str) -> None:
        """
        Write a capture to disk.

        Creates the captures directory if it doesn't exist.

        Args:
            capture: Capture object with metadata
            content: Markdown content body

        Raises:
            OSError: If file cannot be written
        """
        # Ensure directory exists
        self.captures_dir.mkdir(parents=True, exist_ok=True)

        # Create frontmatter post
        post = frontmatter.Post(content)
        post.metadata = capture.to_frontmatter_dict()

        # Write to file
        capture_file = self.captures_dir / f"{capture.id}.md"
        with open(capture_file, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))

    def next_id(self) -> str:
        """
        Generate the next sequential capture ID.

        Scans existing captures and returns the next ID in sequence.
        If no captures exist, returns "cap-001".

        Returns:
            Next capture ID (e.g., "cap-042")

        Raises:
            OSError: If directory cannot be read
        """
        # Create directory if it doesn't exist
        self.captures_dir.mkdir(parents=True, exist_ok=True)

        # Find highest existing ID
        max_num = 0
        for capture_file in self.captures_dir.glob("cap-*.md"):
            # Extract number from filename: cap-NNN.md -> NNN
            stem = capture_file.stem  # cap-NNN
            if stem.startswith("cap-"):
                try:
                    num = int(stem[4:])  # Everything after 'cap-'
                    max_num = max(max_num, num)
                except ValueError:
                    # Skip malformed filenames
                    continue

        # Return next ID
        next_num = max_num + 1
        return f"cap-{next_num:03d}"

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
    def global_store(cls) -> "CaptureStore":
        """
        Create a global capture store.

        Returns:
            CaptureStore for global captures (~/.local/share/cub/captures/)
        """
        # Get XDG data home directory
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if not xdg_data_home:
            xdg_data_home = os.path.expanduser("~/.local/share")

        captures_dir = Path(xdg_data_home) / "cub" / "captures"
        return cls(captures_dir)
