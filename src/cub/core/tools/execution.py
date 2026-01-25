"""
Tool execution service for orchestrating tool runs.

This module provides ExecutionService, the main entry point for executing tools
with the appropriate adapter, enforcing timeouts, and writing execution artifacts.

Example:
    >>> from pathlib import Path
    >>> from cub.core.tools.execution import ExecutionService
    >>> from cub.core.tools.registry import RegistryService
    >>> from cub.core.tools.models import HTTPConfig
    >>>
    >>> # Initialize with registry service for adopt-before-execute flow
    >>> registry_service = RegistryService()
    >>> service = ExecutionService(
    ...     artifact_dir=Path(".cub/toolsmith/runs"),
    ...     registry_service=registry_service
    ... )
    >>>
    >>> # Check if a tool is ready to run
    >>> readiness = await service.check_readiness(
    ...     tool_id="brave-search",
    ...     adapter_type="http",
    ...     config={"auth_env_var": "BRAVE_API_KEY"}
    ... )
    >>>
    >>> if readiness.ready:
    ...     # Execute the tool (raises ToolNotAdoptedError if not in registry)
    ...     result = await service.execute(
    ...         tool_id="brave-search",
    ...         action="search",
    ...         adapter_type="http",
    ...         params={"query": "Python async patterns"},
    ...         timeout=10.0
    ...     )
    ...
    ...     if result.success:
    ...         print(f"Result: {result.output}")
    ...         print(f"Artifact saved to: {result.artifact_path}")
    ... else:
    ...     print(f"Tool not ready: {readiness.missing}")
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from cub.core.tools.adapter import get_adapter
from cub.core.tools.exceptions import (
    ToolApprovalRequiredError,
    ToolNotAdoptedError,
)
from cub.core.tools.models import ToolMetrics, ToolResult

if TYPE_CHECKING:
    from cub.core.tools.approvals import ApprovalService
    from cub.core.tools.metrics import MetricsStore
    from cub.core.tools.registry import RegistryService

logger = logging.getLogger(__name__)


class ReadinessCheck(BaseModel):
    """
    Result of a tool readiness check.

    Indicates whether a tool is ready to execute and what dependencies
    are missing if not ready.

    Attributes:
        ready: Whether the tool is ready to execute
        missing: List of missing dependencies/requirements (e.g., env vars, commands)
    """

    ready: bool = Field(..., description="Whether the tool is ready to execute")
    missing: list[str] = Field(
        default_factory=list,
        description="List of missing dependencies/requirements",
    )


class ExecutionService:
    """
    Service for orchestrating tool execution.

    ExecutionService is the main entry point for running tools. It handles:
    - Adapter selection (HTTP, CLI, MCP stdio)
    - Readiness checks (auth credentials, command availability)
    - Timeout enforcement
    - Artifact persistence (atomic writes to disk)

    The service uses the adapter registry to select the appropriate execution
    backend based on the adapter_type parameter.

    Attributes:
        artifact_dir: Directory where execution artifacts are saved
            (default: .cub/toolsmith/runs)
        registry_service: Optional RegistryService for enforcing adopt-before-execute
        metrics_store: Optional MetricsStore for recording execution metrics
        approval_service: Optional ApprovalService for enforcing freedom-level-based approvals

    Example:
        >>> from cub.core.tools.registry import RegistryService
        >>>
        >>> # Initialize with registry service
        >>> registry_service = RegistryService()
        >>> service = ExecutionService(registry_service=registry_service)
        >>>
        >>> # Check readiness (includes registry check)
        >>> readiness = await service.check_readiness(
        ...     tool_id="brave-search",
        ...     adapter_type="http",
        ...     config={"auth_env_var": "BRAVE_API_KEY"}
        ... )
        >>>
        >>> if not readiness.ready:
        ...     print(f"Missing: {', '.join(readiness.missing)}")
        ...
        >>> # Execute tool (raises ToolNotAdoptedError if not in registry)
        >>> result = await service.execute(
        ...     tool_id="brave-search",
        ...     action="search",
        ...     adapter_type="http",
        ...     params={"query": "test", "_http_config": config},
        ...     timeout=30.0
        ... )
        >>>
        >>> print(f"Success: {result.success}")
        >>> print(f"Artifact: {result.artifact_path}")
    """

    def __init__(
        self,
        artifact_dir: Path | None = None,
        registry_service: RegistryService | None = None,
        metrics_store: MetricsStore | None = None,
        approval_service: ApprovalService | None = None,
    ):
        """
        Initialize the execution service.

        Args:
            artifact_dir: Directory where execution artifacts are saved.
                If None, defaults to .cub/toolsmith/runs
            registry_service: RegistryService for looking up tool configurations.
                If None, registry checks are disabled (tools can execute without adoption).
            metrics_store: MetricsStore for recording execution metrics.
                If None, metrics recording is disabled.
            approval_service: ApprovalService for checking approval requirements.
                If None, approval checks are disabled (tools execute without prompting).
        """
        self.artifact_dir = artifact_dir or Path(".cub/toolsmith/runs")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.registry_service = registry_service
        self.metrics_store = metrics_store
        self.approval_service = approval_service

    async def execute(
        self,
        tool_id: str,
        action: str,
        adapter_type: str,
        params: dict[str, Any],
        timeout: float = 30.0,
        save_artifact: bool = True,
    ) -> ToolResult:
        """
        Execute a tool with the appropriate adapter.

        Selects the adapter based on adapter_type, executes the tool action,
        and optionally saves the execution artifact to disk using atomic writes.

        If a registry_service is configured, verifies that the tool has been
        adopted before allowing execution.

        Args:
            tool_id: Tool identifier (e.g., "brave-search", "gh")
            action: Action to invoke (e.g., "search", "pr create")
            adapter_type: Adapter type ("http", "cli", "mcp_stdio")
            params: Parameters for the action
            timeout: Execution timeout in seconds (default: 30.0)
            save_artifact: Whether to save execution artifact to disk (default: True)

        Returns:
            ToolResult with execution results and artifact path if saved

        Raises:
            ToolNotAdoptedError: If registry_service is configured and tool is not adopted
            ToolApprovalRequiredError: If approval_service is configured and tool requires approval
            ValueError: If adapter_type is not registered
            TimeoutError: If execution exceeds timeout
            RuntimeError: If tool execution fails critically

        Example:
            >>> result = await service.execute(
            ...     tool_id="brave-search",
            ...     action="search",
            ...     adapter_type="http",
            ...     params={"query": "test", "_http_config": config},
            ...     timeout=10.0
            ... )
            >>> if result.success:
            ...     print(result.output)
        """
        # Check if tool is adopted (if registry service is configured)
        if self.registry_service is not None:
            if not self.registry_service.is_approved(tool_id):
                raise ToolNotAdoptedError(
                    tool_id,
                    f"Tool '{tool_id}' must be adopted before execution. "
                    f"Use 'cub tools adopt {tool_id}' to adopt this tool.",
                )

        # Check if tool requires approval (if approval service is configured)
        if self.approval_service is not None:
            if self.approval_service.requires_approval(tool_id, action):
                freedom_level = self.approval_service.get_freedom_level()
                raise ToolApprovalRequiredError(
                    tool_id,
                    action,
                    f"Tool '{tool_id}' requires user approval at "
                    f"freedom level '{freedom_level.value}'. "
                    f"Either approve this execution or increase the freedom level.",
                )

        # Get the appropriate adapter
        adapter = get_adapter(adapter_type)

        # Execute the tool
        result = await adapter.execute(
            tool_id=tool_id,
            action=action,
            params=params,
            timeout=timeout,
        )

        # Save artifact if requested
        if save_artifact:
            artifact_path = self._write_artifact(result)
            # Update result with artifact path
            result.artifact_path = str(artifact_path)

        # Record metrics if metrics_store is configured
        if self.metrics_store is not None:
            self.metrics_store.record_execution(result)

        return result

    async def check_readiness(
        self,
        tool_id: str,
        adapter_type: str,
        config: dict[str, Any] | None = None,
    ) -> ReadinessCheck:
        """
        Check if a tool is ready to execute.

        Verifies that:
        1. The tool is adopted in the registry (if registry_service is configured)
        2. The adapter is available and healthy
        3. Required authentication credentials are present (if applicable)
        4. Required commands/executables are available (for CLI tools)

        Args:
            tool_id: Tool identifier
            adapter_type: Adapter type ("http", "cli", "mcp_stdio")
            config: Optional tool configuration for checking auth requirements

        Returns:
            ReadinessCheck indicating readiness status and missing dependencies

        Example:
            >>> readiness = await service.check_readiness(
            ...     tool_id="brave-search",
            ...     adapter_type="http",
            ...     config={"auth_env_var": "BRAVE_API_KEY"}
            ... )
            >>> if not readiness.ready:
            ...     print(f"Missing: {', '.join(readiness.missing)}")
        """
        missing: list[str] = []

        # Check if tool is adopted in registry (if registry service is configured)
        if self.registry_service is not None:
            if not self.registry_service.is_approved(tool_id):
                missing.append(
                    f"Tool '{tool_id}' not adopted in registry. "
                    f"Use 'cub tools adopt {tool_id}' to adopt this tool."
                )
                # Return early - no point checking other things if not adopted
                return ReadinessCheck(ready=False, missing=missing)

        try:
            # Get the adapter
            adapter = get_adapter(adapter_type)
        except ValueError as e:
            # Adapter not registered
            return ReadinessCheck(ready=False, missing=[str(e)])

        # Check adapter health
        try:
            is_healthy = await adapter.health_check()
            if not is_healthy:
                missing.append(f"{adapter_type} adapter health check failed")
        except Exception as e:
            logger.warning(f"Health check failed for {adapter_type}: {e}")
            missing.append(f"{adapter_type} adapter unavailable: {e}")

        # Check tool availability
        try:
            is_available = await adapter.is_available(tool_id)
            if not is_available:
                missing.append(f"Tool '{tool_id}' not available")
        except Exception as e:
            logger.warning(f"Availability check failed for {tool_id}: {e}")
            missing.append(f"Tool '{tool_id}' availability check failed: {e}")

        # Check auth credentials if config provided
        if config:
            auth_env_var = config.get("auth_env_var")
            if auth_env_var and not os.environ.get(auth_env_var):
                missing.append(f"Environment variable '{auth_env_var}' not set")

        return ReadinessCheck(ready=len(missing) == 0, missing=missing)

    def _write_artifact(self, result: ToolResult) -> Path:
        """
        Write execution artifact to disk using atomic write pattern.

        Uses temp file + rename to ensure atomic writes and prevent corruption.

        Args:
            result: ToolResult to serialize

        Returns:
            Path to the saved artifact file

        Raises:
            Exception: If writing fails

        Note:
            Artifact filename format: {timestamp}-{tool_id}-{action}.json
            Example: 20260124T120000Z-brave-search-search.json
        """
        # Generate artifact filename
        timestamp = result.started_at.strftime("%Y%m%dT%H%M%SZ")
        filename = f"{timestamp}-{result.tool_id}-{result.action}.json"
        artifact_path = self.artifact_dir / filename

        # Serialize result to JSON
        data = result.model_dump(mode="json")

        # Custom JSON serializer for datetime and enum objects
        def json_serializer(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            if hasattr(obj, "value"):
                return obj.value
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        # Write atomically using temp file + rename
        # Use the same directory to ensure atomic rename (same filesystem)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.artifact_dir,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            json.dump(data, tmp, indent=2, default=json_serializer)
            tmp.flush()
            tmp_path = Path(tmp.name)

        try:
            # Atomic rename
            tmp_path.replace(artifact_path)
        except Exception:
            # Clean up temp file on failure
            if tmp_path.exists():
                tmp_path.unlink()
            raise

        logger.debug(f"Saved execution artifact to {artifact_path}")
        return artifact_path

    def read_artifact(self, artifact_path: Path) -> ToolResult | None:
        """
        Read an execution artifact from disk.

        Args:
            artifact_path: Path to artifact file

        Returns:
            ToolResult if file exists and is valid, None otherwise

        Example:
            >>> artifact_path = Path(
            ...     ".cub/toolsmith/runs/20260124T120000Z-brave-search-search.json"
            ... )
            >>> result = service.read_artifact(artifact_path)
            >>> if result:
            ...     print(f"Tool: {result.tool_id}, Success: {result.success}")
        """
        if not artifact_path.exists():
            logger.warning(f"Artifact not found: {artifact_path}")
            return None

        try:
            with artifact_path.open() as f:
                data = json.load(f)
            return ToolResult(**data)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to read artifact {artifact_path}: {e}")
            return None

    def list_artifacts(
        self,
        tool_id: str | None = None,
        action: str | None = None,
    ) -> list[Path]:
        """
        List execution artifacts in the artifact directory.

        Args:
            tool_id: Optional filter by tool ID
            action: Optional filter by action

        Returns:
            List of artifact paths matching the filters, sorted by modification time
            (most recent first)

        Example:
            >>> # List all artifacts
            >>> all_artifacts = service.list_artifacts()
            >>>
            >>> # List artifacts for a specific tool
            >>> brave_artifacts = service.list_artifacts(tool_id="brave-search")
            >>>
            >>> # List artifacts for a specific action
            >>> search_artifacts = service.list_artifacts(action="search")
        """
        if not self.artifact_dir.exists():
            return []

        artifacts = []
        for artifact_path in self.artifact_dir.glob("*.json"):
            # Skip temp files
            if artifact_path.suffix == ".tmp":
                continue

            # Parse filename: {timestamp}-{tool_id}-{action}.json
            # Timestamp format: YYYYMMDDTHHMMSSZ (16 chars)
            # Extract parts after timestamp
            name = artifact_path.stem
            if len(name) < 18:  # Minimum: timestamp(16) + 1 dash + 1 char
                continue

            # Everything after the timestamp (17th char onwards) is tool_id-action
            remainder = name[17:]  # Skip "YYYYMMDDTHHMMSSZ-"

            # Split by last dash to separate tool_id from action
            # This handles tool IDs with dashes (e.g., "brave-search")
            last_dash = remainder.rfind("-")
            if last_dash == -1:
                continue

            artifact_tool_id = remainder[:last_dash]
            artifact_action = remainder[last_dash + 1:]

            # Apply filters
            if tool_id and artifact_tool_id != tool_id:
                continue
            if action and artifact_action != action:
                continue

            artifacts.append(artifact_path)

        # Sort by modification time (most recent first)
        artifacts.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return artifacts

    def get_metrics(self, tool_id: str) -> ToolMetrics | None:
        """
        Get execution metrics for a specific tool.

        Args:
            tool_id: Tool identifier

        Returns:
            ToolMetrics for the tool, or None if metrics_store is not configured
            or no metrics exist for the tool

        Example:
            >>> metrics = service.get_metrics("brave-search")
            >>> if metrics:
            ...     print(f"Success rate: {metrics.success_rate():.1f}%")
            ...     print(f"Avg duration: {metrics.avg_duration_ms}ms")
        """
        if self.metrics_store is None:
            return None
        return self.metrics_store.get(tool_id)

    def get_degraded_tools(self, threshold: float = 80.0) -> list[ToolMetrics]:
        """
        Get tools with success rates below a threshold.

        Args:
            threshold: Success rate threshold percentage (default: 80.0)

        Returns:
            List of ToolMetrics for tools with success rates below the threshold.
            Returns empty list if metrics_store is not configured.

        Example:
            >>> # Get tools with success rate below 80%
            >>> degraded = service.get_degraded_tools(threshold=80.0)
            >>> for metrics in degraded:
            ...     print(f"{metrics.tool_id}: {metrics.success_rate():.1f}%")
        """
        if self.metrics_store is None:
            return []
        return self.metrics_store.filter(lambda m: m.success_rate() < threshold)
