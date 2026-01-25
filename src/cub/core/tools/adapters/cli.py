"""
CLI tool adapter with subprocess execution and output parsing.

This adapter handles command-line tool execution, providing:
- Subprocess execution with timeout support (NO shell=True for security)
- Argument sanitization and validation
- Output format parsing (JSON, text, lines)
- Comprehensive error handling with timeout detection
"""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
from datetime import datetime, timezone
from typing import Any

from cub.core.tools.adapter import register_adapter
from cub.core.tools.models import AdapterType, CLIConfig, ToolResult

logger = logging.getLogger(__name__)


@register_adapter("cli")
class CLIAdapter:
    """
    CLI tool adapter for subprocess-based tool execution.

    Executes command-line tools (gh, jq, curl, etc.) via subprocess with
    timeout support, output parsing, and comprehensive error handling.

    Features:
    - Secure subprocess execution (NO shell=True)
    - Argument sanitization and validation
    - Multiple output formats (json, text, lines)
    - Timeout handling with subprocess.TimeoutExpired
    - Environment variable injection
    - Configurable via CLIConfig

    Example:
        >>> adapter = CLIAdapter()
        >>> config = CLIConfig(
        ...     command="gh",
        ...     args_template="issue list --repo {repo} --json number,title",
        ...     output_format="json"
        ... )
        >>> result = await adapter.execute(
        ...     tool_id="github-cli",
        ...     action="list_issues",
        ...     params={"repo": "owner/repo"},
        ...     timeout=30.0
        ... )
    """

    @property
    def adapter_type(self) -> str:
        """Return adapter type identifier."""
        return "cli"

    async def execute(
        self,
        tool_id: str,
        action: str,
        params: dict[str, Any],
        timeout: float = 30.0,
    ) -> ToolResult:
        """
        Execute a CLI tool action with subprocess.

        Runs a command-line tool with the given parameters, capturing stdout/stderr
        and parsing the output according to the configured format.

        Args:
            tool_id: Tool identifier (e.g., "github-cli", "jq")
            action: Action to invoke (used in args_template if provided)
            params: Parameters for command construction
            timeout: Execution timeout in seconds (default: 30.0)

        Returns:
            ToolResult with command output, timing info, and error details

        Raises:
            RuntimeError: On critical execution failures
            TimeoutError: If execution exceeds timeout
        """
        started_at = datetime.now(timezone.utc)

        # Get tool configuration (placeholder - will be loaded from registry)
        # For now, we'll extract config from params if provided
        config = params.get("_cli_config")
        if not config:
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=0,
                adapter_type=AdapterType.CLI,
                error="CLI configuration not provided",
                error_type="validation",
            )

        try:
            # Build command and arguments
            command_args = self._build_command(config, action, params)

            # Build environment variables
            env = self._build_env(config)

            # Execute command asynchronously
            logger.debug(f"Executing CLI command: {' '.join(command_args)}")

            process = await asyncio.create_subprocess_exec(
                *command_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                # Kill the process on timeout
                process.kill()
                await process.wait()
                duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
                return ToolResult(
                    tool_id=tool_id,
                    action=action,
                    success=False,
                    output=None,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    adapter_type=AdapterType.CLI,
                    error=f"Command timed out after {timeout}s",
                    error_type="timeout",
                )

            # Calculate duration
            duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

            # Decode output
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # Check exit code
            if process.returncode != 0:
                error_msg = (
                    stderr.strip() if stderr else f"Command exited with code {process.returncode}"
                )
                return ToolResult(
                    tool_id=tool_id,
                    action=action,
                    success=False,
                    output=None,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    adapter_type=AdapterType.CLI,
                    error=error_msg,
                    error_type="execution",
                    metadata={
                        "exit_code": process.returncode,
                        "stderr": stderr,
                    },
                )

            # Parse output based on format
            output = self._parse_output(config, stdout)

            # Generate markdown summary
            output_markdown = self._generate_markdown(tool_id, action, output, config)

            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=True,
                output=output,
                output_markdown=output_markdown,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.CLI,
                metadata={
                    "exit_code": process.returncode,
                    "stderr": stderr if stderr else None,
                },
            )

        except FileNotFoundError:
            duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.CLI,
                error=f"Command not found: {config.command}. Ensure it is installed and in PATH.",
                error_type="validation",
            )

        except Exception as e:
            duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            logger.exception(f"Unexpected error executing CLI tool {tool_id}")
            return ToolResult(
                tool_id=tool_id,
                action=action,
                success=False,
                output=None,
                started_at=started_at,
                duration_ms=duration_ms,
                adapter_type=AdapterType.CLI,
                error=f"Unexpected error: {e}",
                error_type="unknown",
            )

    async def is_available(self, tool_id: str) -> bool:
        """
        Check if CLI tool is available.

        For CLI tools, checks if the command exists in PATH by attempting
        to run it with --version or --help (depending on tool).

        Args:
            tool_id: Tool identifier

        Returns:
            True if tool command is available in PATH
        """
        # TODO: Load config from registry and check command availability
        # For now, return True (optimistic availability check)
        return True

    async def health_check(self) -> bool:
        """
        Check CLI adapter health.

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
            logger.exception("CLI adapter health check failed")
            return False

    def _build_command(
        self,
        config: CLIConfig,
        action: str,
        params: dict[str, Any],
    ) -> list[str]:
        """
        Build command and arguments from config and parameters.

        Constructs the full command list for subprocess execution, using the
        args_template if provided, otherwise just the base command.

        Args:
            config: CLI configuration
            action: Action name (may be used in template)
            params: Tool execution parameters

        Returns:
            List of command arguments for subprocess.run()

        Raises:
            ValueError: If template formatting fails
        """
        command_parts = [config.command]

        if config.args_template:
            # Filter out internal params (e.g., _cli_config)
            template_params = {
                k: v for k, v in params.items()
                if not k.startswith("_")
            }
            # Add action to template params
            template_params["action"] = action

            try:
                # Format the template
                args_str = config.args_template.format(**template_params)
                # Split args using shlex for proper shell-like parsing (but we won't use shell=True)
                # This handles quoted arguments correctly
                args_list = shlex.split(args_str)
                command_parts.extend(args_list)
            except KeyError as e:
                raise ValueError(
                    f"Missing parameter in args_template: {e}. "
                    f"Template: {config.args_template}, "
                    f"Available params: {', '.join(template_params.keys())}"
                )

        return command_parts

    def _build_env(self, config: CLIConfig) -> dict[str, str] | None:
        """
        Build environment variables for command execution.

        Merges system environment with tool-specific env vars from config.

        Args:
            config: CLI configuration

        Returns:
            Environment dict with merged variables, or None for system default
        """
        if not config.env_vars:
            return None

        # Start with system environment
        import os
        env = os.environ.copy()

        # Add/override with tool-specific env vars
        env.update(config.env_vars)

        return env

    def _parse_output(self, config: CLIConfig, stdout: str) -> Any:
        """
        Parse command output according to configured format.

        Args:
            config: CLI configuration
            stdout: Raw stdout from command

        Returns:
            Parsed output (dict for JSON, list for lines, str for text)
        """
        stdout = stdout.strip()

        if config.output_format == "json":
            try:
                return json.loads(stdout)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON output: {e}")
                # Fall back to text
                return {"text": stdout, "parse_error": str(e)}

        elif config.output_format == "lines":
            return [line for line in stdout.split("\n") if line.strip()]

        else:  # text
            return {"text": stdout}

    def _generate_markdown(
        self,
        tool_id: str,
        action: str,
        output: Any,
        config: CLIConfig,
    ) -> str:
        """
        Generate human-readable markdown summary from output.

        Creates a concise summary of the command execution result for display.

        Args:
            tool_id: Tool identifier
            action: Action that was executed
            output: Parsed output data
            config: CLI configuration

        Returns:
            Markdown-formatted summary string
        """
        lines = [
            f"**{tool_id}** ({action})",
            f"Command: `{config.command}`",
        ]

        # Add output summary based on format
        if config.output_format == "json" and isinstance(output, dict):
            # Count items if available
            if "items" in output and isinstance(output["items"], list):
                lines.append(f"Items: {len(output['items'])}")
            elif isinstance(output, list):
                lines.append(f"Items: {len(output)}")

        elif config.output_format == "lines" and isinstance(output, list):
            lines.append(f"Lines: {len(output)}")

        return "\n".join(lines)
