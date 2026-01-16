"""
Sandbox execution system.

This module provides a pluggable sandbox system for safe autonomous execution.
Multiple providers are supported (Docker, Sprites, etc.) with a unified interface.

Example usage:
    from cub.core.sandbox import get_provider, SandboxConfig

    # Auto-detect provider
    provider = get_provider()

    # Configure sandbox
    config = SandboxConfig(
        memory="4g",
        cpus=2,
        network=False,
        timeout="2h",
    )

    # Start sandbox
    sandbox_id = provider.start(Path("."), config)

    # Monitor status
    status = provider.status(sandbox_id)
    print(f"State: {status.state}")

    # Get logs
    logs = provider.logs(sandbox_id, follow=True)

    # Export changes
    provider.export(sandbox_id, Path("./output"))

    # Cleanup
    provider.cleanup(sandbox_id)
"""

from .models import (
    ResourceUsage,
    SandboxCapabilities,
    SandboxConfig,
    SandboxState,
    SandboxStatus,
)
from .provider import (
    SandboxProvider,
    detect_provider,
    get_capabilities,
    get_provider,
    is_provider_available,
    list_available_providers,
    list_providers,
    register_provider,
)

__all__ = [
    # Models
    "ResourceUsage",
    "SandboxCapabilities",
    "SandboxConfig",
    "SandboxState",
    "SandboxStatus",
    # Provider protocol and registry
    "SandboxProvider",
    "register_provider",
    "get_provider",
    "detect_provider",
    "list_providers",
    "list_available_providers",
    "is_provider_available",
    "get_capabilities",
]
