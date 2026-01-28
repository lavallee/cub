"""
Launch service — clean API for environment detection and harness launching.

Provides a service layer wrapper around the launch package for detecting
execution environment and launching harnesses with proper context.

Usage:
    >>> from cub.core.services.launch import LaunchService
    >>> service = LaunchService.from_config()
    >>>
    >>> # Detect environment
    >>> env_info = service.detect()
    >>> if env_info.is_nested:
    ...     print("Already in a harness, showing status...")
    ...     return
    >>>
    >>> # Launch default harness
    >>> service.launch()  # Does not return, replaces process
"""

from __future__ import annotations

from pathlib import Path

from cub.core.config.loader import load_config
from cub.core.config.models import CubConfig
from cub.core.launch import (
    HarnessBinaryNotFoundError,
    LauncherError,
    detect_environment,
    launch_harness,
    resolve_harness_binary,
)
from cub.core.launch.models import EnvironmentInfo, LaunchConfig

# ============================================================================
# Typed exceptions
# ============================================================================


class LaunchServiceError(Exception):
    """Base exception for LaunchService errors."""


class HarnessNotFoundError(LaunchServiceError):
    """Harness binary not found."""

    def __init__(self, harness_name: str) -> None:
        self.harness_name = harness_name
        super().__init__(f"Harness '{harness_name}' not found in PATH")


# ============================================================================
# LaunchService
# ============================================================================


class LaunchService:
    """
    Service for environment detection and harness launching.

    Orchestrates the bare `cub` command flow: detect environment,
    resolve harness, and launch with proper session tracking.

    Example:
        >>> service = LaunchService.from_config()
        >>> env = service.detect()
        >>> if not env.is_nested:
        ...     service.launch(resume=True)
    """

    def __init__(
        self,
        config: CubConfig,
        project_dir: Path,
    ) -> None:
        """
        Initialize service with dependencies.

        Args:
            config: Cub configuration
            project_dir: Project root directory
        """
        self._config = config
        self._project_dir = project_dir

    @classmethod
    def from_config(cls, config: CubConfig | None = None) -> LaunchService:
        """
        Create service from configuration.

        Args:
            config: Optional cub configuration (auto-loaded if None)

        Returns:
            Configured LaunchService instance

        Example:
            >>> service = LaunchService.from_config()
        """
        if config is None:
            config = load_config()

        project_dir = Path.cwd()

        return cls(config, project_dir)

    @property
    def config(self) -> CubConfig:
        """The resolved cub configuration."""
        return self._config

    @property
    def project_dir(self) -> Path:
        """The project root directory."""
        return self._project_dir

    # ============================================================================
    # Detection methods
    # ============================================================================

    def detect(self) -> EnvironmentInfo:
        """
        Detect the current execution environment.

        Checks environment variables to determine if we're in a terminal,
        harness session, or nested cub session.

        Returns:
            EnvironmentInfo describing the detected environment

        Example:
            >>> service = LaunchService.from_config()
            >>> env = service.detect()
            >>> if env.is_nested:
            ...     print("Already in a cub session")
        """
        return detect_environment()

    # ============================================================================
    # Launch methods
    # ============================================================================

    def launch(
        self,
        *,
        harness_name: str | None = None,
        resume: bool = False,
        continue_session: bool = False,
        session_id: str | None = None,
        auto_approve: bool = False,
        debug: bool = False,
    ) -> None:
        """
        Launch a harness with proper configuration.

        This function does NOT return on success - it replaces the current
        process with the harness process.

        Args:
            harness_name: Name of harness to launch (uses config default if None)
            resume: Resume previous session if available
            continue_session: Continue from previous session
            session_id: Explicit session ID to resume
            auto_approve: Skip permission prompts
            debug: Enable debug mode

        Raises:
            HarnessNotFoundError: If harness binary not found
            LaunchServiceError: If launch fails

        Example:
            >>> service = LaunchService.from_config()
            >>> service.launch(resume=True, debug=True)
            # Process replaced, does not return
        """
        # Resolve harness name
        if harness_name is None:
            harness_name = self._config.harness.name or "claude-code"

        # Resolve binary path
        try:
            binary_path = resolve_harness_binary(harness_name)
        except HarnessBinaryNotFoundError as e:
            raise HarnessNotFoundError(harness_name) from e

        # Build launch config
        config = LaunchConfig(
            harness_name=harness_name,
            binary_path=binary_path,
            working_dir=str(self._project_dir),
            resume=resume,
            continue_session=continue_session,
            session_id=session_id,
            auto_approve=auto_approve,
            debug=debug,
        )

        # Launch (does not return)
        try:
            launch_harness(config)
        except LauncherError as e:
            raise LaunchServiceError(f"Failed to launch harness: {e}") from e
        except OSError as e:
            raise LaunchServiceError(f"Failed to launch harness: {e}") from e


__all__ = [
    "LaunchService",
    "LaunchServiceError",
    "HarnessNotFoundError",
]
