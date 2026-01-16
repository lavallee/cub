"""
Sandbox provider protocol and registry.

This module defines the SandboxProvider protocol that all sandbox providers
must implement, enabling pluggable sandbox backends (Docker, Sprites, etc.).
"""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

from .models import SandboxCapabilities, SandboxConfig, SandboxStatus


@runtime_checkable
class SandboxProvider(Protocol):
    """
    Protocol for sandbox provider implementations.

    All sandbox providers (docker, sprites, etc.) must implement this interface
    to be compatible with the cub sandbox system.

    Providers are responsible for:
    - Detecting provider availability (Docker daemon, cloud auth, etc.)
    - Reporting capabilities (network isolation, snapshots, etc.)
    - Starting and stopping sandboxes
    - Monitoring sandbox status and resource usage
    - Streaming logs from sandbox execution
    - Extracting changed files from sandbox
    - Cleaning up sandbox resources
    """

    @property
    def name(self) -> str:
        """
        Provider name (e.g., 'docker', 'sprites').

        Returns:
            Lowercase provider identifier
        """
        ...

    @property
    def capabilities(self) -> SandboxCapabilities:
        """
        Get provider capabilities.

        Returns:
            SandboxCapabilities object describing what this provider supports
        """
        ...

    def is_available(self) -> bool:
        """
        Check if provider is available on the system.

        For local providers (Docker): checks if daemon is running
        For cloud providers (Sprites): checks if authenticated

        Returns:
            True if provider can be used
        """
        ...

    def start(
        self,
        project_dir: Path,
        config: SandboxConfig,
    ) -> str:
        """
        Start a new sandbox with the project.

        Creates an isolated environment, copies the project files,
        and starts cub execution inside the sandbox.

        Args:
            project_dir: Local project directory to sandbox
            config: Sandbox configuration (resources, network, etc.)

        Returns:
            Sandbox ID (provider-specific identifier)

        Raises:
            RuntimeError: If sandbox creation fails
        """
        ...

    def stop(self, sandbox_id: str) -> None:
        """
        Stop a running sandbox.

        Gracefully stops the sandbox execution. Does not delete
        the sandbox - use cleanup() for full removal.

        Args:
            sandbox_id: Sandbox to stop

        Raises:
            ValueError: If sandbox not found
            RuntimeError: If stop operation fails
        """
        ...

    def status(self, sandbox_id: str) -> SandboxStatus:
        """
        Get current sandbox status.

        Returns runtime state, resource usage, and execution metadata.

        Args:
            sandbox_id: Sandbox to query

        Returns:
            SandboxStatus object with current state

        Raises:
            ValueError: If sandbox not found
        """
        ...

    def logs(
        self,
        sandbox_id: str,
        follow: bool = False,
        callback: Callable[[str], None] | None = None,
    ) -> str:
        """
        Get sandbox logs.

        Returns stdout/stderr from the sandbox. If follow=True,
        streams logs until sandbox stops. If callback is provided,
        calls it with each log chunk.

        Args:
            sandbox_id: Sandbox to get logs from
            follow: Stream logs until sandbox stops
            callback: Optional callback for each log chunk

        Returns:
            Complete log output (or final output if streaming)

        Raises:
            ValueError: If sandbox not found
        """
        ...

    def diff(self, sandbox_id: str) -> str:
        """
        Get changes made in sandbox.

        Returns a unified diff of all file changes made during
        sandbox execution.

        Args:
            sandbox_id: Sandbox to diff

        Returns:
            Git-style unified diff

        Raises:
            ValueError: If sandbox not found
        """
        ...

    def export(
        self,
        sandbox_id: str,
        dest_path: Path,
        changed_only: bool = True,
    ) -> None:
        """
        Export files from sandbox to local path.

        Copies changed files (or all files) from the sandbox back
        to the local filesystem.

        Args:
            sandbox_id: Sandbox to export from
            dest_path: Local destination directory
            changed_only: Only export changed files (default: True)

        Raises:
            ValueError: If sandbox not found
            RuntimeError: If export fails
        """
        ...

    def cleanup(self, sandbox_id: str) -> None:
        """
        Full cleanup of sandbox resources.

        Stops the sandbox (if running) and removes all associated
        resources (containers, volumes, snapshots, etc.).

        Args:
            sandbox_id: Sandbox to clean up

        Raises:
            ValueError: If sandbox not found
        """
        ...

    def get_version(self) -> str:
        """
        Get provider version.

        Returns:
            Version string (e.g., '1.0.0') or 'unknown'
        """
        ...


# Provider registry
_providers: dict[str, type[SandboxProvider]] = {}


def register_provider(
    name: str,
) -> Callable[[type[SandboxProvider]], type[SandboxProvider]]:
    """
    Decorator to register a sandbox provider implementation.

    Usage:
        @register_provider('docker')
        class DockerProvider:
            @property
            def name(self) -> str:
                return 'docker'
            ...

    Args:
        name: Provider name (e.g., 'docker', 'sprites')

    Returns:
        Decorator function
    """

    def decorator(provider_class: type[SandboxProvider]) -> type[SandboxProvider]:
        _providers[name] = provider_class
        return provider_class

    return decorator


def get_provider(name: str | None = None) -> SandboxProvider:
    """
    Get a sandbox provider by name or auto-detect.

    If name is not provided, auto-detects based on:
    1. CUB_SANDBOX_PROVIDER environment variable
    2. Default detection order (docker > sprites)

    Args:
        name: Provider name ('docker', 'sprites', etc.) or None for auto-detect

    Returns:
        SandboxProvider instance

    Raises:
        ValueError: If provider name is invalid or no provider available
    """
    # Auto-detect if name not provided
    if name is None or name == "auto":
        name = detect_provider()
        if name is None:
            raise ValueError("No sandbox provider available. Install Docker or configure Sprites.")

    # Get provider class from registry
    provider_class = _providers.get(name)
    if provider_class is None:
        raise ValueError(
            f"Provider '{name}' not registered. Available providers: {', '.join(_providers.keys())}"
        )

    # Instantiate and return
    return provider_class()


def detect_provider(
    priority_list: list[str] | None = None,
) -> str | None:
    """
    Auto-detect which sandbox provider to use.

    Detection order:
    1. CUB_SANDBOX_PROVIDER environment variable (if set and not 'auto')
    2. Priority list (if provided)
    3. Default detection order: docker > sprites

    Args:
        priority_list: Optional ordered list of provider names to try

    Returns:
        Provider name if found, None if no provider available
    """
    # Check for explicit override
    provider_env = os.environ.get("CUB_SANDBOX_PROVIDER", "").lower()
    if provider_env and provider_env != "auto":
        # Verify it's available
        if provider_env in _providers:
            try:
                provider = _providers[provider_env]()
                if provider.is_available():
                    return provider_env
            except Exception:
                pass

    # Try priority list if provided
    if priority_list:
        for provider_name in priority_list:
            if provider_name in _providers:
                try:
                    provider = _providers[provider_name]()
                    if provider.is_available():
                        return provider_name
                except Exception:
                    continue

    # Default detection order
    for provider_name in ["docker", "sprites"]:
        if provider_name in _providers:
            try:
                provider = _providers[provider_name]()
                if provider.is_available():
                    return provider_name
            except Exception:
                continue

    return None


def list_providers() -> list[str]:
    """
    List all registered provider names.

    Returns:
        List of provider names
    """
    return list(_providers.keys())


def list_available_providers() -> list[str]:
    """
    List all registered providers that are currently available.

    Returns:
        List of provider names that are available for use
    """
    available = []
    for name, provider_class in _providers.items():
        try:
            provider = provider_class()
            if provider.is_available():
                available.append(name)
        except Exception:
            # Skip providers that fail to instantiate
            continue
    return available


def is_provider_available(name: str) -> bool:
    """
    Check if a provider is available.

    Args:
        name: Provider name to check

    Returns:
        True if provider is registered and available for use
    """
    if name not in _providers:
        return False

    try:
        provider = _providers[name]()
        return provider.is_available()
    except Exception:
        return False


def get_capabilities(name: str) -> SandboxCapabilities | None:
    """
    Get capabilities for a specific provider.

    Args:
        name: Provider name

    Returns:
        SandboxCapabilities object, or None if provider not found
    """
    if name not in _providers:
        return None

    try:
        provider = _providers[name]()
        return provider.capabilities
    except Exception:
        return None
