"""
Harness abstraction layer for AI coding assistants.

This package provides a pluggable interface for different AI coding
assistant CLI tools (Claude Code, Codex, Gemini, OpenCode).

Usage:
    from cub.core.harness import (
        get_backend,
        detect_harness,
        HarnessBackend,
        HarnessCapabilities,
        HarnessResult,
    )

    # Auto-detect harness
    harness = get_backend()

    # Invoke with prompts
    result = harness.invoke(
        system_prompt="You are a helpful coding assistant.",
        task_prompt="Write a function to check if a number is prime."
    )

    print(result.output)
    print(f"Used {result.usage.total_tokens} tokens")
"""

# Import backends to trigger registration
from . import (
    claude,  # noqa: F401
    codex,  # noqa: F401
)
from .backend import (
    HarnessBackend,
    detect_harness,
    get_backend,
    get_capabilities,
    is_backend_available,
    list_available_backends,
    list_backends,
    register_backend,
)
from .models import (
    HARNESS_CAP_AUTO_MODE,
    HARNESS_CAP_JSON_OUTPUT,
    HARNESS_CAP_MODEL_SELECTION,
    HARNESS_CAP_STREAMING,
    HARNESS_CAP_SYSTEM_PROMPT,
    HARNESS_CAP_TOKEN_REPORTING,
    HarnessCapabilities,
    HarnessResult,
    TokenUsage,
)

__all__ = [
    # Backend interface
    "HarnessBackend",
    "register_backend",
    "get_backend",
    "detect_harness",
    "list_backends",
    "list_available_backends",
    "is_backend_available",
    "get_capabilities",
    # Models
    "HarnessCapabilities",
    "HarnessResult",
    "TokenUsage",
    # Constants
    "HARNESS_CAP_STREAMING",
    "HARNESS_CAP_TOKEN_REPORTING",
    "HARNESS_CAP_SYSTEM_PROMPT",
    "HARNESS_CAP_AUTO_MODE",
    "HARNESS_CAP_JSON_OUTPUT",
    "HARNESS_CAP_MODEL_SELECTION",
]
