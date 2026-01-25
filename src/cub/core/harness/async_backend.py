"""
Async harness backend protocol and registry.

This module defines the AsyncHarnessBackend protocol for async-first
harness backends, enabling advanced features like SDK hooks, custom tools,
and stateful sessions.
"""

import os
from collections.abc import AsyncIterator, Callable
from typing import Protocol, TypeVar, runtime_checkable

from .models import HarnessCapabilities, HarnessFeature, TaskInput, TaskResult

# Type variable for the backend class
_T = TypeVar("_T")


@runtime_checkable
class AsyncHarnessBackend(Protocol):
    """
    Protocol for async harness backend implementations.

    Async-first interface for harness backends that support advanced
    features like SDK hooks, custom tools, and stateful sessions.

    Backends implementing this protocol should:
    - Be async-only (no sync wrappers)
    - Support graceful feature degradation via supports_feature()
    - Provide rich execution metadata (messages, file changes)
    - Enable SDK-specific features when available
    """

    @property
    def name(self) -> str:
        """
        Harness name (e.g., 'claude', 'openai').

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
        Check if harness is available on the system.

        Returns:
            True if harness can be invoked (SDK/CLI installed)
        """
        ...

    def supports_feature(self, feature: HarnessFeature) -> bool:
        """
        Check if harness supports a specific feature.

        Args:
            feature: Feature to check (from HarnessFeature enum)

        Returns:
            True if feature is supported
        """
        ...

    async def run_task(
        self,
        task_input: TaskInput,
        debug: bool = False,
    ) -> TaskResult:
        """
        Execute task with blocking execution (async).

        Runs the harness and waits for completion. Returns complete
        result with messages, file changes, and usage.

        Args:
            task_input: Task parameters (prompt, model, permissions, etc.)
            debug: Enable debug logging

        Returns:
            TaskResult with output, usage, messages, and file changes

        Raises:
            RuntimeError: If harness invocation fails
        """
        ...

    async def stream_task(
        self,
        task_input: TaskInput,
        debug: bool = False,
    ) -> AsyncIterator[str]:
        """
        Execute task with streaming output (async generator).

        Streams output chunks as they're generated. Yields strings
        incrementally until task completes.

        Args:
            task_input: Task parameters
            debug: Enable debug logging

        Yields:
            Output chunks as strings

        Raises:
            RuntimeError: If harness invocation fails
        """
        ...

    def get_version(self) -> str:
        """
        Get harness version.

        Returns:
            Version string (e.g., '1.0.0') or 'unknown'
        """
        ...

    async def analyze(
        self,
        context: str,
        files_content: dict[str, str] | None = None,
        analysis_type: str = "implementation_review",
        model: str | None = None,
    ) -> TaskResult:
        """
        Run LLM-based analysis without modifying files.

        This is a read-only analysis operation, unlike run_task() which
        can modify files. Use this for code review, spec comparison,
        and quality assessment.

        Args:
            context: Context about what to analyze (task description,
                requirements, etc.)
            files_content: Optional dict mapping file paths to their
                contents for analysis. If None, harness may read files
                from the working directory.
            analysis_type: Type of analysis to perform:
                - "implementation_review": Compare implementation vs spec
                - "code_quality": General code quality analysis
                - "spec_gap": Find gaps between spec and implementation
            model: Optional model override (e.g., 'opus' for deep analysis)

        Returns:
            TaskResult with analysis text in output field

        Raises:
            RuntimeError: If harness doesn't support analysis or fails
        """
        ...


# Backend registry
_async_backends: dict[str, type[AsyncHarnessBackend]] = {}


def register_async_backend(
    name: str,
) -> Callable[[type[_T]], type[_T]]:
    """
    Decorator to register an async harness backend implementation.

    Usage:
        @register_async_backend('claude')
        class ClaudeAsyncBackend:
            @property
            def name(self) -> str:
                return 'claude'
            ...

    Args:
        name: Backend name (e.g., 'claude', 'openai')

    Returns:
        Decorator function
    """

    def decorator(backend_class: type[_T]) -> type[_T]:
        # Store as AsyncHarnessBackend compatible type
        _async_backends[name] = backend_class  # type: ignore[assignment]
        return backend_class

    return decorator


def get_async_backend(name: str | None = None) -> AsyncHarnessBackend:
    """
    Get an async harness backend by name or auto-detect.

    If name is not provided, auto-detects based on:
    1. HARNESS environment variable
    2. Default detection order (claude > openai > gemini > local)

    Args:
        name: Backend name or None for auto-detect

    Returns:
        AsyncHarnessBackend instance

    Raises:
        ValueError: If backend name is invalid or no harness available
    """
    # Auto-detect if name not provided
    if name is None or name == "auto":
        name = detect_async_harness()
        if name is None:
            raise ValueError(
                "No async harness available. Install one of: claude, openai, gemini"
            )

    # Get backend class from registry
    backend_class = _async_backends.get(name)
    if backend_class is None:
        raise ValueError(
            f"Async backend '{name}' not registered. "
            f"Available backends: {', '.join(_async_backends.keys())}"
        )

    # Instantiate and return
    return backend_class()


def detect_async_harness(
    priority_list: list[str] | None = None,
) -> str | None:
    """
    Auto-detect which async harness to use.

    Detection order:
    1. HARNESS environment variable (if set and not 'auto')
    2. Priority list (if provided)
    3. Default detection order: claude-sdk > codex > claude-cli > openai > gemini > local

    Only returns harnesses that are both:
    - Available (SDK/CLI installed)
    - Registered (has an async backend in registry)

    Args:
        priority_list: Optional ordered list of harness names to try

    Returns:
        Harness name if found, None if no harness available
    """
    # Check for explicit override
    harness_env = os.environ.get("HARNESS", "").lower()
    if harness_env and harness_env != "auto":
        # Verify it's available AND registered
        if harness_env in _async_backends:
            try:
                backend = _async_backends[harness_env]()
                if backend.is_available():
                    return harness_env
            except Exception:
                pass

    # Try priority list if provided
    if priority_list:
        for harness in priority_list:
            if harness in _async_backends:
                try:
                    backend = _async_backends[harness]()
                    if backend.is_available():
                        return harness
                except Exception:
                    continue

    # Default detection order
    # Priority: claude-sdk > codex > claude-cli > openai > gemini > local
    default_priority = [
        "claude-sdk",  # SDK-based (preferred)
        "codex",  # Shell-out but primary implementation
        "claude-cli",  # CLI shell-out fallback
        "openai",
        "gemini",
        "local",
    ]

    for harness in default_priority:
        if harness in _async_backends:
            try:
                backend = _async_backends[harness]()
                if backend.is_available():
                    return harness
            except Exception:
                continue

    return None


def list_async_backends() -> list[str]:
    """
    List all registered async backend names.

    Returns:
        List of backend names
    """
    return list(_async_backends.keys())


def list_available_async_backends() -> list[str]:
    """
    List all registered async backends that are currently available.

    Returns:
        List of backend names where the SDK/CLI is installed
    """
    available = []
    for name, backend_class in _async_backends.items():
        try:
            backend = backend_class()
            if backend.is_available():
                available.append(name)
        except Exception:
            # Skip backends that fail to instantiate
            continue
    return available


def is_async_backend_available(name: str) -> bool:
    """
    Check if an async backend is available.

    Args:
        name: Backend name to check

    Returns:
        True if backend is registered and its SDK/CLI is available
    """
    if name not in _async_backends:
        return False

    try:
        backend = _async_backends[name]()
        return backend.is_available()
    except Exception:
        return False


def get_async_capabilities(name: str) -> HarnessCapabilities | None:
    """
    Get capabilities for a specific async harness.

    Args:
        name: Harness name

    Returns:
        HarnessCapabilities object, or None if harness not found
    """
    if name not in _async_backends:
        return None

    try:
        backend = _async_backends[name]()
        return backend.capabilities
    except Exception:
        return None
