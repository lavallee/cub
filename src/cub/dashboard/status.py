"""
Status file polling for cub dashboard.

Watches status.json for changes and notifies consumers of updates.
"""

import json
from collections.abc import Callable
from pathlib import Path

from cub.core.status.models import RunStatus


class StatusWatcher:
    """
    Poll status.json and detect changes.

    Reads status.json at a configured interval and invokes a callback
    when changes are detected. Handles file existence, invalid JSON,
    and partial writes gracefully.

    Example:
        >>> def on_change(status: RunStatus) -> None:
        ...     print(f"Phase: {status.phase}")
        >>> watcher = StatusWatcher(
        ...     status_path=Path(".cub/runs/camel-20260115/status.json"),
        ...     on_change=on_change
        ... )
        >>> status = watcher.poll()  # Returns latest status
    """

    def __init__(
        self,
        status_path: Path,
        on_change: Callable[[RunStatus], None] | None = None,
        poll_interval: float = 1.0,
    ):
        """
        Initialize the status watcher.

        Args:
            status_path: Path to status.json file
            on_change: Callback function invoked when status changes
            poll_interval: Polling interval in seconds (default: 1.0)
        """
        self.status_path = Path(status_path)
        self.on_change = on_change
        self.poll_interval = poll_interval

        # Track last known state for change detection
        self._last_mtime: float | None = None
        self._last_status: RunStatus | None = None

    def poll(self) -> RunStatus | None:
        """
        Poll status.json for updates.

        Detects changes using file modification time (mtime) and reads
        the file only if it has changed. Returns the current status
        whether changed or not.

        Returns:
            RunStatus if file exists and is valid, None otherwise
        """
        if not self.status_path.exists():
            # File doesn't exist yet - reset tracking state
            if self._last_mtime is not None:
                self._last_status = None
                self._last_mtime = None
            return None

        try:
            # Check if file has been modified
            current_mtime = self.status_path.stat().st_mtime
            if self._last_mtime == current_mtime:
                # File hasn't changed
                return self._last_status

            # File has changed, read it
            status = self._read_status()
            if status is None:
                return None

            # Check if content actually changed
            if self._last_status != status:
                self._last_status = status
                self._last_mtime = current_mtime
                if self.on_change:
                    self.on_change(status)
            else:
                # mtime changed but content didn't
                self._last_mtime = current_mtime

            return status

        except OSError:
            # File system error (deleted, permission denied, etc.)
            return None

    def _read_status(self) -> RunStatus | None:
        """
        Read and parse status.json.

        Handles invalid JSON and returns None if parsing fails.

        Returns:
            RunStatus if file is valid, None otherwise
        """
        try:
            with self.status_path.open() as f:
                data = json.load(f)
            return RunStatus(**data)
        except json.JSONDecodeError:
            # Invalid JSON - likely partial write or corruption
            return None
        except (TypeError, ValueError):
            # Pydantic validation error - invalid data structure
            return None
        except OSError:
            # File access error
            return None

    def get_interval(self) -> float:
        """Get the configured poll interval in seconds."""
        return self.poll_interval

    def set_on_change(self, callback: Callable[[RunStatus], None]) -> None:
        """Update the change callback."""
        self.on_change = callback
