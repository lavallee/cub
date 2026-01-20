"""
Harness backend protocol and registry.

This module defines the HarnessBackend protocol that all harness backends
must implement, enabling pluggable AI coding assistants (Claude, Codex, etc.).
"""

import os
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from .models import HarnessCapabilities, HarnessResult


@runtime_checkable
class HarnessBackend(Protocol):
    """
    Protocol for harness backend implementations.

    All harness backends (claude, codex, gemini, opencode) must implement
    this interface to be compatible with the cub harness system.

    Backends are responsible for:
    - Detecting harness availability (CLI tool installed)
    - Reporting capabilities (streaming, token reporting, etc.)
    - Invoking the harness with prompts
    - Parsing output and extracting token usage
    """

    @property
    def name(self) -> str:
        """
        Harness name (e.g., 'claude', 'codex').

        Returns:
            Lowercase harness identifier
        """
        ...

    @property
    def capabilities(self) -> HarnessCapabilities:
        """
        Get harness capabilities.

        Returns:
            HarnessCapabilities object describing what this harness supports
        """
        ...

    def is_available(self) -> bool:
        """
        Check if harness CLI is available on the system.

        Returns:
            True if harness can be invoked (CLI tool found in PATH)
        """
        ...

    def invoke(
        self,
        system_prompt: str,
        task_prompt: str,
        model: str | None = None,
        debug: bool = False,
    ) -> HarnessResult:
        """
        Invoke the harness with blocking execution.

        Runs the harness CLI and waits for completion. Use this when
        streaming output is not needed or not supported.

        Args:
            system_prompt: System prompt (prepended instructions)
            task_prompt: User/task prompt (specific request)
            model: Optional model name (e.g., 'sonnet', 'opus')
            debug: Enable debug logging

        Returns:
            HarnessResult with output, usage, and timing info

        Raises:
            RuntimeError: If harness invocation fails
        """
        ...

    def invoke_streaming(
        self,
        system_prompt: str,
        task_prompt: str,
        model: str | None = None,
        debug: bool = False,
        callback: Callable[[str], None] | None = None,
    ) -> HarnessResult:
        """
        Invoke the harness with streaming output.

        Runs the harness CLI and streams output as it's generated.
        If streaming is not supported, falls back to blocking invoke.

        Args:
            system_prompt: System prompt (prepended instructions)
            task_prompt: User/task prompt (specific request)
            model: Optional model name
            debug: Enable debug logging
            callback: Optional callback for each output chunk

        Returns:
            HarnessResult with complete output, usage, and timing

        Raises:
            RuntimeError: If harness invocation fails
        """
        ...

    def get_version(self) -> str:
        """
        Get harness CLI version.

        Returns:
            Version string (e.g., '1.0.0') or 'unknown'
        """
        ...


# Backend registry
_backends: dict[str, type[HarnessBackend]] = {}


def register_backend(name: str) -> Callable[[type[HarnessBackend]], type[HarnessBackend]]:
    """
    Decorator to register a harness backend implementation.

    Usage:
        @register_backend('claude')
        class ClaudeBackend:
            @property
            def name(self) -> str:
                return 'claude'
            ...

    Args:
        name: Backend name (e.g., 'claude', 'codex')

    Returns:
        Decorator function
    """

    def decorator(backend_class: type[HarnessBackend]) -> type[HarnessBackend]:
        _backends[name] = backend_class
        return backend_class

    return decorator


def get_backend(name: str | None = None) -> HarnessBackend:
    """
    Get a harness backend by name or auto-detect.

    If name is not provided, auto-detects based on:
    1. HARNESS environment variable
    2. Config harness.priority setting
    3. Default detection order (claude > opencode > codex > gemini)

    Args:
        name: Backend name ('claude', 'codex', etc.) or None for auto-detect

    Returns:
        HarnessBackend instance

    Raises:
        ValueError: If backend name is invalid or no harness available
    """
    # Auto-detect if name not provided
    if name is None or name == "auto":
        name = detect_harness()
        if name is None:
            raise ValueError(
                "No harness available. Install one of: claude, opencode, codex, gemini"
            )

    # Get backend class from registry
    backend_class = _backends.get(name)
    if backend_class is None:
        raise ValueError(
            f"Backend '{name}' not registered. Available backends: {', '.join(_backends.keys())}"
        )

    # Instantiate and return
    return backend_class()


def detect_harness(
    priority_list: list[str] | None = None,
) -> str | None:
    """
    Auto-detect which harness to use.

    Detection order:
    1. HARNESS environment variable (if set and not 'auto')
    2. Priority list (if provided)
    3. Default detection order: claude-legacy > codex > opencode > gemini

    Only returns harnesses that are both:
    - Available (backend.is_available() returns True)
    - Registered (has a Python backend in _backends registry)

    Args:
        priority_list: Optional ordered list of harness names to try

    Returns:
        Harness name if found, None if no harness available
    """
    # Check for explicit override
    harness_env = os.environ.get("HARNESS", "").lower()
    if harness_env and harness_env != "auto":
        # Verify it's available AND registered
        if harness_env in _backends:
            try:
                backend = _backends[harness_env]()
                if backend.is_available():
                    return harness_env
            except Exception:
                pass

    # Try priority list if provided
    if priority_list:
        for harness in priority_list:
            if harness in _backends:
                try:
                    backend = _backends[harness]()
                    if backend.is_available():
                        return harness
                except Exception:
                    continue

    # Default detection order
    # Note: Prefer SDK-based harnesses (async registry) for new code
    # This sync registry is for backward compatibility
    for harness in ["claude-legacy", "codex", "opencode", "gemini"]:
        if harness in _backends:
            try:
                backend = _backends[harness]()
                if backend.is_available():
                    return harness
            except Exception:
                continue

    return None


def list_backends() -> list[str]:
    """
    List all registered backend names.

    Returns:
        List of backend names
    """
    return list(_backends.keys())


def list_available_backends() -> list[str]:
    """
    List all registered backends that are currently available.

    Returns:
        List of backend names where the CLI is installed
    """
    available = []
    for name, backend_class in _backends.items():
        try:
            backend = backend_class()
            if backend.is_available():
                available.append(name)
        except Exception:
            # Skip backends that fail to instantiate
            continue
    return available


def is_backend_available(name: str) -> bool:
    """
    Check if a backend is available.

    Args:
        name: Backend name to check

    Returns:
        True if backend is registered and its CLI is available
    """
    if name not in _backends:
        return False

    try:
        backend = _backends[name]()
        return backend.is_available()
    except Exception:
        return False


def get_capabilities(name: str) -> HarnessCapabilities | None:
    """
    Get capabilities for a specific harness.

    Args:
        name: Harness name

    Returns:
        HarnessCapabilities object, or None if harness not found
    """
    if name not in _backends:
        return None

    try:
        backend = _backends[name]()
        return backend.capabilities
    except Exception:
        return None
