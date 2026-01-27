"""
MCP stdio adapter for Model Context Protocol server execution.

This adapter handles MCP servers via JSON-RPC over stdio, providing:
- Spawn-per-call process model (no persistent servers)
- JSON-RPC 2.0 request/response handling
- Timeout handling with process group termination
- Stderr capture for debugging (not exposed to users)
- Comprehensive error handling for protocol errors
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from cub.core.tools.adapter import register_adapter
from cub.core.tools.models import AdapterType, MCPConfig, ToolResult

logger = logging.getLogger(__name__)


@register_adapter("mcp_stdio")
class MCPStdioAdapter:
    """
    MCP stdio adapter for JSON-RPC over stdio communication.

    Executes MCP servers by spawning a process, sending a JSON-RPC request via
    stdin, reading the response from stdout, and terminating the process.

    Features:
    - Spawn-per-call model (fresh process for each execution)
    - JSON-RPC 2.0 protocol compliance
    - Timeout handling with process group termination
    - Stderr capture for debugging
    - Comprehensive error handling for protocol errors
    - Configurable via MCPConfig

    Example:
        >>> adapter = MCPStdioAdapter()
        >>> config = MCPConfig(
        ...     command="uvx",
        ...     args=["mcp-server-filesystem", "/path/to/dir"],
        ... )
        >>> result = await adapter.execute(
        ...     tool_id="filesystem-server",
        ...     action="read_file",
        ...     params={"_mcp_config": config, "path": "/path/to/file.txt"},
        ...     timeout=30.0
        ... )
    """

    @property
    def adapter_type(self) -> str:
        """Return adapter type identifier."""
        return "mcp_stdio"

    async def execute(
        self,
        tool_id: str,
        action: str,
        params: dict[str, Any],
        timeout: float = 30.0,
    ) -> ToolResult:
        """
        Execute an MCP server action via JSON-RPC over stdio.

        Spawns the MCP server process, sends a JSON-RPC request, waits for the
        response, and terminates the process. Handles timeout and protocol errors.

        Args:
            tool_id: Tool identifier (e.g., "filesystem-server")
            action: Method to invoke (e.g., "read_file", "tools/call")
            params: Parameters for the action (must include _mcp_config)
            timeout: Execution timeout in seconds (default: 30.0)

        Returns:
            ToolResult with response data, timing info, and error details

        Note:
            The params dict must contain a "_mcp_config" key with an MCPConfig
            object specifying how to spawn the MCP server.
        """
        started_at = datetime.now(timezone.utc)

        # Get MCP configuration from params
        config = params.get("_mcp_config")
        if not config:
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=0,
                adapter_type=AdapterType.MCP_STDIO,
                error="MCP configuration not provided",
                error_type="validation",
            )

        # Build environment with config env_vars merged into current env
        env = self._build_env(config)

        # Build command list
        command = [config.command, *config.args]

        # Generate JSON-RPC request
        request_id = str(uuid.uuid4())
        jsonrpc_request = self._build_jsonrpc_request(action, params, request_id)

        process: asyncio.subprocess.Process | None = None
        stderr_output = ""

        try:
            # Spawn the MCP server process
            logger.debug(f"Spawning MCP server: {' '.join(command)}")

            # Use start_new_session on Unix to create a process group for clean termination
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                start_new_session=True,  # Create new process group for clean kill
            )

            # Send JSON-RPC request and read response with timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    self._communicate_jsonrpc(process, jsonrpc_request),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                # Kill the process group on timeout
                await self._kill_process_group(process)
                duration_ms = int(
                    (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
                )
                return ToolResult(
                    tool_id=tool_id,
                    action=action,
                    success=False,
                    output=None,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    adapter_type=AdapterType.MCP_STDIO,
                    error=f"MCP server timed out after {timeout}s",
                    error_type="timeout",
                )

            # Calculate duration
            duration_ms = int(
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
            )

            # Decode output
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr_output = stderr_bytes.decode("utf-8", errors="replace")

            # Log stderr for debugging (not exposed to user)
            if stderr_output.strip():
                logger.debug(f"MCP server stderr: {stderr_output[:500]}")

            # Parse JSON-RPC response
            return self._parse_jsonrpc_response(
                tool_id=tool_id,
                action=action,
                stdout=stdout,
                request_id=request_id,
                started_at=started_at,
                duration_ms=duration_ms,
            )

        except FileNotFoundError:
            duration_ms = int(
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
            )
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.MCP_STDIO,
                error=f"MCP server command not found: {config.command}. "
                "Ensure it is installed and in PATH.",
                error_type="validation",
            )

        except Exception as e:
            duration_ms = int(
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
            )
            logger.exception(f"Unexpected error executing MCP tool {tool_id}")
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.MCP_STDIO,
                error=f"Unexpected error: {e}",
                error_type="unknown",
            )

        finally:
            # Ensure process is terminated
            if process is not None:
                await self._ensure_process_terminated(process)

    async def is_available(self, tool_id: str) -> bool:
        """
        Check if MCP tool is available.

        For MCP tools, checks if the command exists in PATH.

        Args:
            tool_id: Tool identifier

        Returns:
            True if tool command is available
        """
        # TODO: Load config from registry and check command availability
        # For now, return True (optimistic availability check)
        return True

    async def health_check(self) -> bool:
        """
        Check MCP adapter health.

        Verifies that the subprocess module can execute commands.

        Returns:
            True if adapter is operational
        """
        try:
            # Simple check - verify we can run a basic command
            process = await asyncio.create_subprocess_exec(
                "echo",
                "test",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except Exception:
            logger.exception("MCP adapter health check failed")
            return False

    def _build_env(self, config: MCPConfig) -> dict[str, str] | None:
        """
        Build environment variables for MCP server execution.

        Merges system environment with tool-specific env vars from config.

        Args:
            config: MCP configuration

        Returns:
            Environment dict with merged variables, or None for system default
        """
        if not config.env_vars:
            return None

        # Start with system environment
        env = os.environ.copy()

        # Add/override with tool-specific env vars
        env.update(config.env_vars)

        return env

    def _build_jsonrpc_request(
        self,
        method: str,
        params: dict[str, Any],
        request_id: str,
    ) -> str:
        """
        Build a JSON-RPC 2.0 request message.

        Args:
            method: The method to call
            params: Method parameters (excluding internal _* params)
            request_id: Unique request identifier

        Returns:
            JSON-RPC request as string with newline terminator
        """
        # Filter out internal params (prefixed with _)
        rpc_params = {k: v for k, v in params.items() if not k.startswith("_")}

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": rpc_params,
        }

        # JSON-RPC messages are newline-delimited
        return json.dumps(request) + "\n"

    async def _communicate_jsonrpc(
        self,
        process: asyncio.subprocess.Process,
        request: str,
    ) -> tuple[bytes, bytes]:
        """
        Send JSON-RPC request and receive response.

        Writes the request to stdin, closes stdin, and reads the response
        from stdout along with any stderr output.

        Args:
            process: The subprocess to communicate with
            request: JSON-RPC request string

        Returns:
            Tuple of (stdout_bytes, stderr_bytes)
        """
        # Write request to stdin and close it to signal end of input
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None

        process.stdin.write(request.encode("utf-8"))
        await process.stdin.drain()
        process.stdin.close()
        await process.stdin.wait_closed()

        # Read response - MCP servers typically send a single JSON-RPC response
        # then exit or continue running. We read until EOF or get a complete response.
        stdout_bytes = await process.stdout.read()
        stderr_bytes = await process.stderr.read()

        return stdout_bytes, stderr_bytes

    def _parse_jsonrpc_response(
        self,
        tool_id: str,
        action: str,
        stdout: str,
        request_id: str,
        started_at: datetime,
        duration_ms: int,
    ) -> ToolResult:
        """
        Parse JSON-RPC response and return ToolResult.

        Handles both success responses (result field) and error responses
        (error field) according to JSON-RPC 2.0 specification.

        Args:
            tool_id: Tool identifier
            action: Action that was executed
            stdout: Raw stdout from process
            request_id: Expected request ID for validation
            started_at: Execution start timestamp
            duration_ms: Execution duration in milliseconds

        Returns:
            ToolResult with parsed response or error details
        """
        stdout = stdout.strip()

        if not stdout:
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.MCP_STDIO,
                error="MCP server returned empty response",
                error_type="protocol",
            )

        # Try to parse JSON-RPC response
        try:
            # Handle multiple JSON objects (newline-delimited) - take the last one
            # Some MCP servers may output multiple messages
            lines = [line.strip() for line in stdout.split("\n") if line.strip()]
            if not lines:
                return ToolResult(
                    tool_id=tool_id,
                    action=action,
                    success=False,
                    output=None,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    adapter_type=AdapterType.MCP_STDIO,
                    error="MCP server returned no valid response lines",
                    error_type="protocol",
                )

            # Parse each line to find the response matching our request
            response = None
            for line in lines:
                try:
                    parsed = json.loads(line)
                    # Look for JSON-RPC response (has "id" field matching our request)
                    if isinstance(parsed, dict) and parsed.get("id") == request_id:
                        response = parsed
                        break
                except json.JSONDecodeError:
                    continue

            # If no matching response found, try the last valid JSON object
            if response is None:
                for line in reversed(lines):
                    try:
                        response = json.loads(line)
                        if isinstance(response, dict):
                            break
                    except json.JSONDecodeError:
                        continue

            if response is None:
                return ToolResult(
                    tool_id=tool_id,
                    action=action,
                    success=False,
                    output=None,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    adapter_type=AdapterType.MCP_STDIO,
                    error="Failed to parse JSON-RPC response from MCP server",
                    error_type="protocol",
                    metadata={"raw_output": stdout[:500]},
                )

        except json.JSONDecodeError as e:
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.MCP_STDIO,
                error=f"Invalid JSON in MCP server response: {e}",
                error_type="protocol",
                metadata={"raw_output": stdout[:500]},
            )

        # Check for JSON-RPC error response
        if "error" in response:
            error_obj = response["error"]
            error_code = error_obj.get("code", "unknown")
            error_message = error_obj.get("message", "Unknown error")
            error_data = error_obj.get("data")

            # Classify error type based on JSON-RPC error code
            error_type = self._classify_jsonrpc_error(error_code)

            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.MCP_STDIO,
                error=f"MCP error ({error_code}): {error_message}",
                error_type=error_type,
                metadata={"error_code": error_code, "error_data": error_data},
            )

        # Success - extract result
        result = response.get("result")

        # Generate markdown summary
        output_markdown = self._generate_markdown(tool_id, action, result)

        return ToolResult(
            tool_id=tool_id,
            action=action,
            success=True,
            output=result,
            output_markdown=output_markdown,
            started_at=started_at,
            duration_ms=duration_ms,
            adapter_type=AdapterType.MCP_STDIO,
            metadata={"jsonrpc_id": response.get("id")},
        )

    def _classify_jsonrpc_error(self, error_code: int | str) -> str:
        """
        Classify JSON-RPC error code to error type.

        Maps JSON-RPC 2.0 error codes to our error type categories.

        Args:
            error_code: JSON-RPC error code

        Returns:
            Error type string (validation, execution, protocol, unknown)
        """
        try:
            code = int(error_code)
        except (TypeError, ValueError):
            return "unknown"

        # JSON-RPC 2.0 standard error codes
        if code == -32700:  # Parse error
            return "protocol"
        elif code == -32600:  # Invalid Request
            return "validation"
        elif code == -32601:  # Method not found
            return "validation"
        elif code == -32602:  # Invalid params
            return "validation"
        elif code == -32603:  # Internal error
            return "execution"
        elif -32099 <= code <= -32000:  # Server error (reserved range)
            return "execution"
        else:
            return "unknown"

    def _generate_markdown(
        self,
        tool_id: str,
        action: str,
        result: Any,
    ) -> str:
        """
        Generate human-readable markdown summary from result.

        Creates a concise summary of the MCP execution result for display.

        Args:
            tool_id: Tool identifier
            action: Action that was executed
            result: Parsed result data

        Returns:
            Markdown-formatted summary string
        """
        lines = [
            f"**{tool_id}** ({action})",
            "Protocol: MCP (JSON-RPC over stdio)",
        ]

        # Try to extract useful info from result
        if isinstance(result, dict):
            # Count items if available (common pattern)
            if "content" in result:
                content = result["content"]
                if isinstance(content, list):
                    lines.append(f"Content items: {len(content)}")
                elif isinstance(content, str):
                    lines.append(f"Content length: {len(content)} chars")
            elif "tools" in result and isinstance(result["tools"], list):
                lines.append(f"Tools: {len(result['tools'])}")
        elif isinstance(result, list):
            lines.append(f"Items: {len(result)}")

        return "\n".join(lines)

    async def _kill_process_group(self, process: asyncio.subprocess.Process) -> None:
        """
        Kill the process group to ensure all child processes are terminated.

        Uses SIGKILL on the process group to ensure clean termination on timeout.

        Args:
            process: The subprocess to kill
        """
        if process.returncode is not None:
            return  # Already terminated

        if sys.platform != "win32":
            try:
                # Get the process group ID (same as PID due to start_new_session=True)
                pgid = os.getpgid(process.pid)
                # Kill the entire process group
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                # Process may have already terminated
                pass
        else:
            # Windows: no process groups, kill directly
            try:
                process.kill()
            except ProcessLookupError:
                pass

        # Wait for process to terminate
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            # Last resort - force kill the process directly
            process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass

    async def _ensure_process_terminated(
        self, process: asyncio.subprocess.Process
    ) -> None:
        """
        Ensure the process is fully terminated.

        Called in finally block to clean up the process.

        Args:
            process: The subprocess to terminate
        """
        if process.returncode is not None:
            return  # Already terminated

        try:
            # Try graceful termination first
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                # Force kill if terminate didn't work
                await self._kill_process_group(process)
        except ProcessLookupError:
            # Process already terminated
            pass
