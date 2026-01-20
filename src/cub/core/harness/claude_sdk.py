"""
Claude SDK harness backend implementation.

This backend wraps the Claude Agent SDK for AI coding assistance with full
async support, hooks, custom tools, and native streaming.

Requires:
    - claude-agent-sdk Python package (pip install claude-agent-sdk)
    - Claude Code CLI (bundled with the package)
"""

import shutil
import subprocess
import time
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .async_backend import register_async_backend
from .models import (
    HarnessCapabilities,
    HarnessFeature,
    Message,
    TaskInput,
    TaskResult,
    TokenUsage,
    ToolUse,
)

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgentOptions
    from claude_agent_sdk import Message as SDKMessage


def _sdk_available() -> bool:
    """Check if claude-agent-sdk is installed."""
    try:
        import claude_agent_sdk  # noqa: F401

        return True
    except ImportError:
        return False


def _cli_available() -> bool:
    """Check if Claude Code CLI is available."""
    return shutil.which("claude") is not None


def _build_options(task_input: TaskInput) -> "ClaudeAgentOptions":
    """
    Build ClaudeAgentOptions from TaskInput.

    Maps cub's TaskInput model to the SDK's ClaudeAgentOptions.

    Args:
        task_input: Task parameters from cub

    Returns:
        ClaudeAgentOptions configured for the task
    """
    from claude_agent_sdk import ClaudeAgentOptions

    # Determine permission mode based on auto_approve
    permission_mode: str | None = None
    if task_input.auto_approve:
        permission_mode = "acceptEdits"

    # Build options - SDK expects specific types
    options = ClaudeAgentOptions(
        system_prompt=task_input.system_prompt,
        cwd=task_input.working_dir,
        permission_mode=permission_mode,
        max_turns=None,  # We don't limit turns by default
        model=task_input.model,
    )

    return options


def _parse_sdk_message(sdk_message: "SDKMessage") -> Message | None:
    """
    Parse an SDK message into our Message model.

    Handles AssistantMessage, UserMessage, and extracts tool uses.

    Args:
        sdk_message: Raw message from the SDK

    Returns:
        Our Message model, or None if message type is not relevant
    """
    from claude_agent_sdk import AssistantMessage, SystemMessage, UserMessage
    from claude_agent_sdk.types import TextBlock, ToolResultBlock, ToolUseBlock

    # Determine role and content
    role: str
    content_text: str = ""
    tool_uses: list[ToolUse] = []

    if isinstance(sdk_message, UserMessage):
        role = "user"
        if isinstance(sdk_message.content, str):
            content_text = sdk_message.content
        elif isinstance(sdk_message.content, list):
            # Extract text from content blocks
            for block in sdk_message.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    content_text += block.get("text", "")
                elif hasattr(block, "text"):
                    content_text += str(block.text)

    elif isinstance(sdk_message, AssistantMessage):
        role = "assistant"
        for block in sdk_message.content:
            if isinstance(block, TextBlock):
                content_text += block.text
            elif isinstance(block, ToolUseBlock):
                tool_uses.append(
                    ToolUse(
                        tool_name=block.name,
                        tool_input=dict(block.input) if block.input else {},
                        tool_output=None,  # Output comes in ToolResultBlock
                        success=True,
                    )
                )
            elif isinstance(block, ToolResultBlock):
                # Find matching tool use and add output
                for tu in tool_uses:
                    if tu.tool_output is None:
                        if block.content:
                            if isinstance(block.content, str):
                                tu.tool_output = block.content
                            else:
                                tu.tool_output = str(block.content)
                        tu.success = not (block.is_error or False)
                        break

    elif isinstance(sdk_message, SystemMessage):
        role = "system"
        if hasattr(sdk_message, "data") and isinstance(sdk_message.data, dict):
            content_text = str(sdk_message.data.get("message", ""))

    else:
        # ResultMessage or other types - skip for message history
        return None

    return Message(
        role=role,
        content=content_text,
        tool_uses=tool_uses,
        timestamp=datetime.now(),
    )


def _extract_usage(sdk_message: Any) -> TokenUsage | None:
    """
    Extract token usage from SDK ResultMessage.

    Args:
        sdk_message: Message that may contain usage info

    Returns:
        TokenUsage if available, None otherwise
    """
    from claude_agent_sdk import ResultMessage

    if not isinstance(sdk_message, ResultMessage):
        return None

    # ResultMessage has usage dict and total_cost_usd
    usage_data = sdk_message.usage or {}

    return TokenUsage(
        input_tokens=usage_data.get("input_tokens", 0),
        output_tokens=usage_data.get("output_tokens", 0),
        cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
        cache_creation_tokens=usage_data.get("cache_creation_input_tokens", 0),
        cost_usd=sdk_message.total_cost_usd,
        estimated=False,
    )


def _extract_text_from_message(sdk_message: Any) -> str:
    """
    Extract text content from an SDK message.

    Args:
        sdk_message: SDK message (usually AssistantMessage)

    Returns:
        Extracted text content
    """
    from claude_agent_sdk import AssistantMessage
    from claude_agent_sdk.types import TextBlock

    if not isinstance(sdk_message, AssistantMessage):
        return ""

    text_parts: list[str] = []
    for block in sdk_message.content:
        if isinstance(block, TextBlock):
            text_parts.append(block.text)

    return "".join(text_parts)


@register_async_backend("claude")
class ClaudeSDKHarness:
    """
    Claude SDK harness backend.

    Uses the Claude Agent SDK for full-featured async execution with:
    - Native async streaming via query()
    - Hooks support for circuit breakers and tool interception
    - Custom tool definitions via MCP servers
    - Stateful sessions via ClaudeSDKClient
    - Token usage and cost tracking from ResultMessage
    """

    @property
    def name(self) -> str:
        """Return 'claude' as the harness name."""
        return "claude"

    @property
    def capabilities(self) -> HarnessCapabilities:
        """
        Claude SDK supports all capabilities.

        Returns:
            HarnessCapabilities with all features enabled
        """
        return HarnessCapabilities(
            streaming=True,
            token_reporting=True,
            system_prompt=True,
            auto_mode=True,
            json_output=True,
            model_selection=True,
            hooks=True,
            custom_tools=True,
            sessions=True,
            session_forking=True,
            subagents=True,
        )

    def is_available(self) -> bool:
        """
        Check if Claude SDK is available.

        Requires both the Python SDK and the Claude Code CLI.

        Returns:
            True if both SDK and CLI are available
        """
        return _sdk_available() and _cli_available()

    def supports_feature(self, feature: HarnessFeature) -> bool:
        """
        Check if harness supports a specific feature.

        Claude SDK supports all features in HarnessFeature.

        Args:
            feature: Feature to check

        Returns:
            True (all features supported)
        """
        return True

    async def run_task(
        self,
        task_input: TaskInput,
        debug: bool = False,
    ) -> TaskResult:
        """
        Execute task with blocking execution (async).

        Uses the SDK's query() function to run a single-shot task.
        Collects all messages and returns complete result.

        Args:
            task_input: Task parameters (prompt, model, permissions, etc.)
            debug: Enable debug logging

        Returns:
            TaskResult with output, usage, messages, and file changes

        Raises:
            RuntimeError: If SDK is not available or invocation fails
        """
        if not self.is_available():
            raise RuntimeError(
                "Claude SDK not available. Install with: pip install claude-agent-sdk"
            )

        from claude_agent_sdk import (
            CLIConnectionError,
            CLINotFoundError,
            ProcessError,
            ResultMessage,
            query,
        )

        start_time = time.time()
        options = _build_options(task_input)

        # Collect messages and output
        messages: list[Message] = []
        output_chunks: list[str] = []
        usage: TokenUsage = TokenUsage()
        error: str | None = None
        exit_code = 0
        session_id: str | None = None

        try:
            async for sdk_message in query(prompt=task_input.prompt, options=options):
                # Parse message for history
                parsed = _parse_sdk_message(sdk_message)
                if parsed is not None:
                    messages.append(parsed)

                # Extract text for output
                text = _extract_text_from_message(sdk_message)
                if text:
                    output_chunks.append(text)

                # Extract usage from ResultMessage
                msg_usage = _extract_usage(sdk_message)
                if msg_usage is not None:
                    usage = msg_usage

                # Extract session ID from ResultMessage
                if isinstance(sdk_message, ResultMessage):
                    session_id = sdk_message.session_id
                    if sdk_message.is_error:
                        exit_code = 1
                        error = sdk_message.result or "Task failed"

        except CLINotFoundError as e:
            duration = time.time() - start_time
            return TaskResult(
                output="",
                usage=TokenUsage(),
                duration_seconds=duration,
                exit_code=1,
                error=f"Claude Code CLI not found: {e}",
                messages=[],
            )

        except CLIConnectionError as e:
            duration = time.time() - start_time
            return TaskResult(
                output="",
                usage=TokenUsage(),
                duration_seconds=duration,
                exit_code=1,
                error=f"Failed to connect to Claude Code: {e}",
                messages=[],
            )

        except ProcessError as e:
            duration = time.time() - start_time
            return TaskResult(
                output="",
                usage=TokenUsage(),
                duration_seconds=duration,
                exit_code=e.exit_code or 1,
                error=f"Claude Code process failed: {e}",
                messages=[],
            )

        except Exception as e:
            duration = time.time() - start_time
            return TaskResult(
                output="",
                usage=TokenUsage(),
                duration_seconds=duration,
                exit_code=1,
                error=f"Unexpected error: {e}",
                messages=[],
            )

        duration = time.time() - start_time
        output_text = "".join(output_chunks)

        return TaskResult(
            output=output_text,
            usage=usage,
            duration_seconds=duration,
            exit_code=exit_code,
            error=error,
            messages=messages,
            session_id=session_id,
        )

    async def stream_task(
        self,
        task_input: TaskInput,
        debug: bool = False,
    ) -> AsyncIterator[str]:
        """
        Execute task with streaming output (async generator).

        Uses the SDK's query() function with real-time text extraction.
        Yields text chunks as they're generated.

        Args:
            task_input: Task parameters
            debug: Enable debug logging

        Yields:
            Output chunks as strings

        Raises:
            RuntimeError: If SDK is not available or invocation fails
        """
        if not self.is_available():
            raise RuntimeError(
                "Claude SDK not available. Install with: pip install claude-agent-sdk"
            )

        from claude_agent_sdk import (
            CLIConnectionError,
            CLINotFoundError,
            ProcessError,
            query,
        )

        options = _build_options(task_input)

        try:
            async for sdk_message in query(prompt=task_input.prompt, options=options):
                # Extract and yield text chunks
                text = _extract_text_from_message(sdk_message)
                if text:
                    yield text

        except CLINotFoundError as e:
            raise RuntimeError(f"Claude Code CLI not found: {e}") from e

        except CLIConnectionError as e:
            raise RuntimeError(f"Failed to connect to Claude Code: {e}") from e

        except ProcessError as e:
            raise RuntimeError(f"Claude Code process failed: {e}") from e

    def get_version(self) -> str:
        """
        Get Claude Code version.

        Returns:
            Version string or 'unknown' if unavailable
        """
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout.strip() or "unknown"
        except Exception:
            return "unknown"
