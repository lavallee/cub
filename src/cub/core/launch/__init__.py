"""
Launch service for environment detection and harness launching.

This package provides the core logic for the bare `cub` command:
detecting the execution environment (terminal, harness, or nested),
resolving harness binaries, and launching harnesses with proper
session tracking.

Modules:
    detector: Environment detection (CUB_SESSION_ACTIVE, CLAUDE_CODE, etc.)
    launcher: Harness binary resolution, flag assembly, exec-based launch
    models: Data models (EnvironmentInfo, LaunchConfig)

Example Usage:
    >>> from cub.core.launch import detect_environment, launch_harness, LaunchConfig
    >>>
    >>> # Detect environment
    >>> env_info = detect_environment()
    >>> if env_info.is_nested:
    ...     print("Already in a cub session, showing status...")
    ...     return
    >>>
    >>> # Launch harness
    >>> config = LaunchConfig(
    ...     harness_name="claude-code",
    ...     binary_path="/usr/bin/claude",
    ...     working_dir="/path/to/project",
    ...     resume=False,
    ...     debug=False
    ... )
    >>> launch_harness(config)  # Replaces process, does not return
"""

from cub.core.launch.detector import detect_environment
from cub.core.launch.launcher import (
    HarnessBinaryNotFoundError,
    LauncherError,
    build_launch_args,
    build_launch_env,
    launch_harness,
    resolve_harness_binary,
)
from cub.core.launch.models import (
    EnvironmentContext,
    EnvironmentInfo,
    LaunchConfig,
)

__all__ = [
    # Detector
    "detect_environment",
    # Launcher
    "launch_harness",
    "resolve_harness_binary",
    "build_launch_args",
    "build_launch_env",
    "LauncherError",
    "HarnessBinaryNotFoundError",
    # Models
    "EnvironmentContext",
    "EnvironmentInfo",
    "LaunchConfig",
]
