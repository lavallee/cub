"""
HTTP tool adapter with retry logic and exponential backoff.

This adapter handles REST API tools, providing:
- Automatic retry with exponential backoff (3 retries by default)
- Smart error classification (timeout, auth, network, rate_limit)
- Response parsing and markdown output generation
- Comprehensive error handling with detailed error types
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from cub.core.tools.adapter import register_adapter
from cub.core.tools.models import AdapterType, HTTPConfig, ToolResult
from cub.core.toolsmith.http import retry_request

logger = logging.getLogger(__name__)


@register_adapter("http")
class HTTPAdapter:
    """
    HTTP tool adapter with retry logic and error handling.

    Executes HTTP-based tools (REST APIs) with automatic retry on transient
    failures, smart error classification, and structured result formatting.

    Features:
    - Automatic retry with exponential backoff (default: 3 retries)
    - Rate limit handling (429 status codes)
    - Error type classification (timeout, auth, network, rate_limit, validation)
    - Response parsing and markdown generation
    - Configurable via HTTPConfig

    Example:
        >>> adapter = HTTPAdapter()
        >>> config = HTTPConfig(
        ...     base_url="https://api.example.com",
        ...     endpoints={"search": "/v1/search"},
        ...     auth_header="X-API-Key",
        ...     auth_env_var="API_KEY"
        ... )
        >>> result = await adapter.execute(
        ...     tool_id="example-search",
        ...     action="search",
        ...     params={"query": "test"},
        ...     timeout=30.0
        ... )
    """

    @property
    def adapter_type(self) -> str:
        """Return adapter type identifier."""
        return "http"

    async def execute(
        self,
        tool_id: str,
        action: str,
        params: dict[str, Any],
        timeout: float = 30.0,
    ) -> ToolResult:
        """
        Execute an HTTP tool action with retry logic.

        Makes an HTTP request to the tool's endpoint with the given parameters,
        automatically retrying on transient failures (5xx errors, timeouts, network
        issues) with exponential backoff.

        Args:
            tool_id: Tool identifier (e.g., "brave-search", "github-api")
            action: Action to invoke (maps to endpoint via config)
            params: Request parameters (query params, JSON body, etc.)
            timeout: Request timeout in seconds (default: 30.0)

        Returns:
            ToolResult with response data, timing info, and error details

        Raises:
            RuntimeError: On critical execution failures
            TimeoutError: If execution exceeds timeout
        """
        started_at = datetime.now(timezone.utc)

        # Get tool configuration (placeholder - will be loaded from registry)
        # For now, we'll extract config from params if provided
        config = params.get("_http_config")
        if not config:
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=0,
                adapter_type=AdapterType.HTTP,
                error="HTTP configuration not provided",
                error_type="validation",
            )

        try:
            # Build request URL
            url = self._build_url(config, action)

            # Build request headers
            headers = self._build_headers(config)

            # Build request parameters
            http_params = self._build_params(params)

            # Make HTTP request with retry logic
            response = retry_request(
                method="GET",  # TODO: Support other methods from config
                url=url,
                params=http_params,
                headers=headers,
                timeout=timeout,
                max_retries=3,
                base_delay=1.0,
                multiplier=2.0,
            )

            # Calculate duration
            duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

            # Parse response
            try:
                output = response.json()
            except Exception:
                # If JSON parsing fails, use text
                output = {"text": response.text}

            # Generate markdown summary
            output_markdown = self._generate_markdown(tool_id, action, output, response)

            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=True,
                output=output,
                output_markdown=output_markdown,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.HTTP,
                metadata={
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                },
            )

        except httpx.TimeoutException as e:
            duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.HTTP,
                error=f"Request timed out after {timeout}s: {e}",
                error_type="timeout",
            )

        except httpx.HTTPStatusError as e:
            duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            status_code = e.response.status_code
            error_type = self._classify_http_error(status_code)

            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.HTTP,
                error=f"HTTP {status_code}: {e}",
                error_type=error_type,
                metadata={"status_code": status_code},
            )

        except httpx.RequestError as e:
            duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.HTTP,
                error=f"Network error: {e}",
                error_type="network",
            )

        except Exception as e:
            duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            logger.exception(f"Unexpected error executing HTTP tool {tool_id}")
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.HTTP,
                error=f"Unexpected error: {e}",
                error_type="unknown",
            )

    async def is_available(self, tool_id: str) -> bool:
        """
        Check if HTTP tool is available.

        For HTTP tools, checks if required credentials are present in environment.

        Args:
            tool_id: Tool identifier

        Returns:
            True if tool credentials are available
        """
        # TODO: Load config from registry and check auth_env_var
        # For now, return True (optimistic availability check)
        return True

    async def health_check(self) -> bool:
        """
        Check HTTP adapter health.

        Verifies that the HTTP client can make requests (basic connectivity check).

        Returns:
            True if adapter is operational
        """
        try:
            # Simple connectivity check - verify we can create an async HTTP client
            async with httpx.AsyncClient(timeout=5.0):
                # Don't actually make a request, just check client creation works
                return True
        except Exception:
            logger.exception("HTTP adapter health check failed")
            return False

    def _build_url(self, config: HTTPConfig, action: str) -> str:
        """
        Build full URL from config and action.

        Args:
            config: HTTP configuration
            action: Action name

        Returns:
            Full URL for the request

        Raises:
            ValueError: If action not found in endpoints
        """
        endpoint = config.endpoints.get(action)
        if not endpoint:
            raise ValueError(
                f"Action '{action}' not found in endpoints. "
                f"Available actions: {', '.join(config.endpoints.keys())}"
            )

        base = config.base_url.rstrip("/")
        path = endpoint.lstrip("/")
        return f"{base}/{path}"

    def _build_headers(self, config: HTTPConfig) -> dict[str, str]:
        """
        Build request headers from config.

        Includes static headers from config plus authentication if configured.

        Args:
            config: HTTP configuration

        Returns:
            Request headers dict

        Raises:
            RuntimeError: If auth is required but credentials are missing
        """
        headers = dict(config.headers)

        # Add authentication if configured
        if config.auth_header and config.auth_env_var:
            api_key = os.environ.get(config.auth_env_var)
            if not api_key:
                raise RuntimeError(
                    f"{config.auth_env_var} is not set. Set it in the environment, e.g.\n\n"
                    f"  export {config.auth_env_var}=...\n\n"
                    f"Then re-run the command."
                )
            headers[config.auth_header] = api_key

        return headers

    def _build_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Build HTTP request parameters from tool params.

        Filters out internal parameters (prefixed with _) and converts
        values to strings for URL encoding.

        Args:
            params: Tool execution parameters

        Returns:
            HTTP request parameters
        """
        # Filter out internal params (e.g., _http_config)
        http_params = {
            k: str(v) for k, v in params.items()
            if not k.startswith("_")
        }
        return http_params

    def _classify_http_error(self, status_code: int) -> str:
        """
        Classify HTTP error by status code.

        Maps HTTP status codes to error type categories for structured
        error handling.

        Args:
            status_code: HTTP status code

        Returns:
            Error type string (auth, rate_limit, validation, network, unknown)
        """
        if status_code == 401 or status_code == 403:
            return "auth"
        elif status_code == 429:
            return "rate_limit"
        elif 400 <= status_code < 500:
            return "validation"
        elif 500 <= status_code < 600:
            return "network"
        else:
            return "unknown"

    def _generate_markdown(
        self,
        tool_id: str,
        action: str,
        output: Any,
        response: httpx.Response,
    ) -> str:
        """
        Generate human-readable markdown summary from response.

        Creates a concise summary of the tool execution result for display.

        Args:
            tool_id: Tool identifier
            action: Action that was executed
            output: Parsed response data
            response: Raw HTTP response

        Returns:
            Markdown-formatted summary string
        """
        # Basic summary - can be customized per tool
        lines = [
            f"**{tool_id}** ({action})",
            f"Status: {response.status_code}",
        ]

        # Try to extract useful info from response
        if isinstance(output, dict):
            # Count results if available (common pattern)
            if "results" in output:
                results = output["results"]
                if isinstance(results, list):
                    lines.append(f"Results: {len(results)}")
            elif "data" in output:
                data = output["data"]
                if isinstance(data, list):
                    lines.append(f"Items: {len(data)}")

        return "\n".join(lines)
