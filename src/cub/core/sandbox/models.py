"""
Sandbox data models.

This module defines Pydantic models for sandbox execution state,
capabilities, and configuration.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SandboxState(str, Enum):
    """Sandbox execution state."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    CLEANING_UP = "cleaning_up"


class SandboxCapabilities(BaseModel):
    """
    Sandbox provider capabilities.

    Defines what features a sandbox provider supports, enabling
    feature detection and provider selection.
    """

    network_isolation: bool = Field(
        default=False,
        description="Can disable network access",
    )
    resource_limits: bool = Field(
        default=False,
        description="Can enforce CPU/memory limits",
    )
    snapshots: bool = Field(
        default=False,
        description="Supports creating/restoring snapshots",
    )
    remote: bool = Field(
        default=False,
        description="Executes remotely (cloud VM)",
    )
    gpu: bool = Field(
        default=False,
        description="Supports GPU acceleration",
    )
    streaming_logs: bool = Field(
        default=True,
        description="Can stream logs in real-time",
    )
    file_sync: bool = Field(
        default=True,
        description="Can sync file changes back to host",
    )


class ResourceUsage(BaseModel):
    """Resource usage statistics."""

    memory_used: str | None = Field(
        default=None,
        description="Memory usage (e.g., '1.2g', '512m')",
    )
    memory_limit: str | None = Field(
        default=None,
        description="Memory limit (e.g., '4g')",
    )
    cpu_percent: float | None = Field(
        default=None,
        description="CPU usage percentage (0-100)",
    )
    cpu_limit: float | None = Field(
        default=None,
        description="CPU limit (number of cores)",
    )


class SandboxStatus(BaseModel):
    """
    Sandbox runtime status.

    Captures the current state of a running or stopped sandbox,
    including resource usage and execution metadata.
    """

    id: str = Field(
        description="Sandbox identifier (provider-specific)",
    )
    provider: str = Field(
        description="Provider name (docker, sprites, etc.)",
    )
    state: SandboxState = Field(
        description="Current execution state",
    )
    started_at: datetime | None = Field(
        default=None,
        description="When sandbox was started (ISO8601)",
    )
    stopped_at: datetime | None = Field(
        default=None,
        description="When sandbox was stopped (ISO8601)",
    )
    resources: ResourceUsage | None = Field(
        default=None,
        description="Resource usage statistics",
    )
    exit_code: int | None = Field(
        default=None,
        description="Exit code if stopped/failed",
    )
    error: str | None = Field(
        default=None,
        description="Error message if failed",
    )
    cub_status: dict[str, object] | None = Field(
        default=None,
        description="Cub run status from status.json (if available)",
    )


class SandboxConfig(BaseModel):
    """
    Sandbox configuration options.

    Common options that work across all providers (though not all
    providers support all options - check capabilities).
    """

    memory: str | None = Field(
        default=None,
        description="Memory limit (e.g., '4g', '512m')",
    )
    cpus: float | None = Field(
        default=None,
        description="CPU limit (number of cores)",
    )
    timeout: str | None = Field(
        default=None,
        description="Max execution time (e.g., '4h', '30m')",
    )
    network: bool = Field(
        default=True,
        description="Allow network access",
    )
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables",
    )
    cub_args: list[str] = Field(
        default_factory=list,
        description="Arguments to pass to cub run",
    )
    provider_opts: dict[str, object] = Field(
        default_factory=dict,
        description="Provider-specific options (passthrough)",
    )
