"""
Claude SDK harness backend implementation.

This backend wraps the Claude Agent SDK for AI coding assistance with full
async support, hooks, custom tools, and native streaming.

Use 'claude-sdk' or 'claude' to select this backend. The 'claude' alias
defaults to this SDK-based implementation. For the CLI shell-out approach,
use 'claude-cli' explicitly.

Requires:
    - claude-agent-sdk Python package (pip install claude-agent-sdk)
    - Claude Code CLI (bundled with the package)
"""

import logging
import shutil
import subprocess
import time
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from .async_backend import register_async_backend

# SDK permission mode type
PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]
from .models import (
    HarnessCapabilities,
    HarnessFeature,
    HookContext,
    HookEvent,
    HookHandler,
    HookResult,
    Message,
    TaskInput,
    TaskResult,
    TokenUsage,
    ToolUse,
)

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgentOptions
    from claude_agent_sdk import Message as SDKMessage

logger = logging.getLogger(__name__)


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
    permission_mode: PermissionMode | None = None
    if task_input.auto_approve:
        permission_mode = "bypassPermissions"

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


@register_async_backend("claude-sdk")
@register_async_backend("claude")  # Alias: 'claude' defaults to SDK backend
class ClaudeSDKBackend:
    """
    Claude SDK harness backend.

    Uses the Claude Agent SDK for full-featured async execution with:
    - Native async streaming via query()
    - Hooks support for circuit breakers and tool interception
    - Custom tool definitions via MCP servers
    - Stateful sessions via ClaudeSDKClient
    - Token usage and cost tracking from ResultMessage

    Hook System:
        The harness supports registering hooks for various events (PRE_TASK,
        POST_TASK, PRE_TOOL_USE, POST_TOOL_USE, ON_ERROR, ON_MESSAGE).
        PRE_TOOL_USE hooks are mapped to the SDK's PreToolUse hook mechanism.
    """

    def __init__(self) -> None:
        """Initialize the harness with empty hook registry."""
        self._hooks: dict[HookEvent, list[HookHandler]] = {event: [] for event in HookEvent}

    @property
    def name(self) -> str:
        """Return 'claude-sdk' as the harness name."""
        return "claude-sdk"

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

        Claude SDK supports all features in HarnessFeature, including
        ANALYSIS for LLM-based code review.

        Args:
            feature: Feature to check

        Returns:
            True (all features supported)
        """
        # Claude SDK supports all features including analysis
        return True

    def register_hook(
        self,
        event: HookEvent,
        handler: HookHandler,
    ) -> None:
        """
        Register a hook handler for an event.

        Multiple handlers can be registered for the same event and will
        be executed in registration order. If any handler returns a
        HookResult with block=True, subsequent handlers are not called.

        Currently supported events:
        - PRE_TASK: Executed before task starts (can block task)
        - POST_TASK: Executed after task completes (run_task only)
        - ON_ERROR: Executed when an error occurs
        - ON_MESSAGE: Executed when a message is received (run_task only)

        Future SDK integration (requires ClaudeSDKClient):
        - PRE_TOOL_USE: Will map to SDK's PreToolUse hook
        - POST_TOOL_USE: Will map to SDK's PostToolUse hook

        Args:
            event: Event to hook (PRE_TASK, POST_TASK, PRE_TOOL_USE, etc.)
            handler: Async function that receives HookContext and returns
                     HookResult or None

        Note:
            PRE_TOOL_USE and POST_TOOL_USE hooks are registered but not yet
            executed via the SDK. Full SDK hook integration requires using
            ClaudeSDKClient instead of query() function. These hooks will be
            activated in a future update.
        """
        self._hooks[event].append(handler)
        if event in (HookEvent.PRE_TOOL_USE, HookEvent.POST_TOOL_USE):
            logger.warning(
                "Hook for event %s registered but not yet active. "
                "Tool-level hooks require ClaudeSDKClient (future feature).",
                event.value,
            )
        logger.debug("Registered hook for event %s: %s", event.value, handler.__name__)

    def unregister_hook(
        self,
        event: HookEvent,
        handler: HookHandler,
    ) -> bool:
        """
        Unregister a hook handler.

        Args:
            event: Event the handler was registered for
            handler: Handler function to remove

        Returns:
            True if handler was found and removed, False otherwise
        """
        try:
            self._hooks[event].remove(handler)
            logger.debug("Unregistered hook for event %s: %s", event.value, handler.__name__)
            return True
        except ValueError:
            return False

    def clear_hooks(self, event: HookEvent | None = None) -> None:
        """
        Clear all hooks for an event, or all hooks if no event specified.

        Args:
            event: Event to clear hooks for, or None to clear all
        """
        if event is None:
            for ev in HookEvent:
                self._hooks[ev] = []
            logger.debug("Cleared all hooks")
        else:
            self._hooks[event] = []
            logger.debug("Cleared hooks for event %s", event.value)

    async def _execute_hooks(
        self,
        event: HookEvent,
        context: HookContext,
    ) -> HookResult:
        """
        Execute all registered hooks for an event.

        Hooks are executed in registration order. If any hook returns
        a HookResult with block=True, execution stops and that result
        is returned. Otherwise, a non-blocking result is returned.

        Args:
            event: Event being triggered
            context: Context with event details

        Returns:
            HookResult with block status and optional modifications
        """
        for handler in self._hooks[event]:
            try:
                result = await handler(context)
                if result is not None and result.block:
                    logger.debug(
                        "Hook blocked event %s: %s (reason: %s)",
                        event.value,
                        handler.__name__,
                        result.reason,
                    )
                    return result
            except Exception as e:
                logger.warning(
                    "Hook %s raised exception for event %s: %s",
                    handler.__name__,
                    event.value,
                    e,
                )
                # Continue with other hooks on exception

        return HookResult(block=False)

    async def run_task(
        self,
        task_input: TaskInput,
        debug: bool = False,
    ) -> TaskResult:
        """
        Execute task with blocking execution (async).

        Uses the SDK's query() function to run a single-shot task.
        Collects all messages and returns complete result.

        Hook execution points:
        - PRE_TASK: Before task execution (can block task)
        - POST_TASK: After task completion
        - ON_ERROR: When an error occurs
        - ON_MESSAGE: When a message is received (per-message)

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

        # Execute PRE_TASK hooks - can block task execution
        pre_task_context = HookContext(
            event=HookEvent.PRE_TASK,
            task_id=task_input.session_id,
            metadata={"prompt": task_input.prompt, "model": task_input.model},
        )
        pre_task_result = await self._execute_hooks(HookEvent.PRE_TASK, pre_task_context)
        if pre_task_result.block:
            duration = time.time() - start_time
            return TaskResult(
                output="",
                usage=TokenUsage(),
                duration_seconds=duration,
                exit_code=1,
                error=f"Task blocked by hook: {pre_task_result.reason or 'No reason given'}",
                messages=[],
            )

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

                    # Execute ON_MESSAGE hooks
                    msg_context = HookContext(
                        event=HookEvent.ON_MESSAGE,
                        task_id=task_input.session_id,
                        message_content=parsed.content,
                        message_role=parsed.role,
                    )
                    await self._execute_hooks(HookEvent.ON_MESSAGE, msg_context)

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
            # Execute ON_ERROR hooks
            error_context = HookContext(
                event=HookEvent.ON_ERROR,
                task_id=task_input.session_id,
                error=e,
            )
            await self._execute_hooks(HookEvent.ON_ERROR, error_context)
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
            # Execute ON_ERROR hooks
            error_context = HookContext(
                event=HookEvent.ON_ERROR,
                task_id=task_input.session_id,
                error=e,
            )
            await self._execute_hooks(HookEvent.ON_ERROR, error_context)
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
            # Execute ON_ERROR hooks
            error_context = HookContext(
                event=HookEvent.ON_ERROR,
                task_id=task_input.session_id,
                error=e,
            )
            await self._execute_hooks(HookEvent.ON_ERROR, error_context)
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
            # Execute ON_ERROR hooks
            error_context = HookContext(
                event=HookEvent.ON_ERROR,
                task_id=task_input.session_id,
                error=e,
            )
            await self._execute_hooks(HookEvent.ON_ERROR, error_context)
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

        result = TaskResult(
            output=output_text,
            usage=usage,
            duration_seconds=duration,
            exit_code=exit_code,
            error=error,
            messages=messages,
            session_id=session_id,
        )

        # Execute POST_TASK hooks
        post_task_context = HookContext(
            event=HookEvent.POST_TASK,
            task_id=session_id,
            metadata={
                "output": output_text,
                "exit_code": exit_code,
                "usage": usage.model_dump() if usage else {},
            },
        )
        await self._execute_hooks(HookEvent.POST_TASK, post_task_context)

        return result

    async def stream_task(
        self,
        task_input: TaskInput,
        debug: bool = False,
    ) -> AsyncIterator[str]:
        """
        Execute task with streaming output (async generator).

        Uses the SDK's query() function with real-time text extraction.
        Yields text chunks as they're generated.

        Hook execution points:
        - PRE_TASK: Before task execution (can block task)
        - ON_ERROR: When an error occurs

        Note: POST_TASK hooks are not executed in streaming mode since
        the caller controls when iteration ends.

        Args:
            task_input: Task parameters
            debug: Enable debug logging

        Yields:
            Output chunks as strings

        Raises:
            RuntimeError: If SDK is not available, invocation fails,
                         or task is blocked by PRE_TASK hook
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

        # Execute PRE_TASK hooks - can block task execution
        pre_task_context = HookContext(
            event=HookEvent.PRE_TASK,
            task_id=task_input.session_id,
            metadata={"prompt": task_input.prompt, "model": task_input.model},
        )
        pre_task_result = await self._execute_hooks(HookEvent.PRE_TASK, pre_task_context)
        if pre_task_result.block:
            raise RuntimeError(
                f"Task blocked by hook: {pre_task_result.reason or 'No reason given'}"
            )

        options = _build_options(task_input)

        try:
            async for sdk_message in query(prompt=task_input.prompt, options=options):
                # Extract and yield text chunks
                text = _extract_text_from_message(sdk_message)
                if text:
                    yield text

        except CLINotFoundError as e:
            # Execute ON_ERROR hooks
            error_context = HookContext(
                event=HookEvent.ON_ERROR,
                task_id=task_input.session_id,
                error=e,
            )
            await self._execute_hooks(HookEvent.ON_ERROR, error_context)
            raise RuntimeError(f"Claude Code CLI not found: {e}") from e

        except CLIConnectionError as e:
            # Execute ON_ERROR hooks
            error_context = HookContext(
                event=HookEvent.ON_ERROR,
                task_id=task_input.session_id,
                error=e,
            )
            await self._execute_hooks(HookEvent.ON_ERROR, error_context)
            raise RuntimeError(f"Failed to connect to Claude Code: {e}") from e

        except ProcessError as e:
            # Execute ON_ERROR hooks
            error_context = HookContext(
                event=HookEvent.ON_ERROR,
                task_id=task_input.session_id,
                error=e,
            )
            await self._execute_hooks(HookEvent.ON_ERROR, error_context)
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

    async def analyze(
        self,
        context: str,
        files_content: dict[str, str] | None = None,
        analysis_type: str = "implementation_review",
        model: str | None = None,
    ) -> TaskResult:
        """
        Run LLM-based analysis without modifying files.

        Uses run_task() internally with a specialized system prompt
        that instructs the LLM to analyze without making changes.

        Args:
            context: Context about what to analyze
            files_content: Dict mapping file paths to contents
            analysis_type: Type of analysis to perform
            model: Optional model override (defaults to 'sonnet')

        Returns:
            TaskResult with analysis text in output field
        """
        # Build analysis prompt
        system_prompt = self._build_analysis_system_prompt(analysis_type)
        user_prompt = self._build_analysis_user_prompt(context, files_content, analysis_type)

        # Create task input with read-only settings
        task_input = TaskInput(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=model or "sonnet",  # Default to sonnet for analysis
            auto_approve=True,  # No user interaction needed
            # Don't pass working_dir to prevent file access
        )

        return await self.run_task(task_input)

    def _build_analysis_system_prompt(self, analysis_type: str) -> str:
        """Build system prompt for analysis based on type."""
        base_prompt = """You are a code review assistant. Your task is to analyze code and provide detailed feedback.

IMPORTANT RULES:
1. This is a READ-ONLY analysis. Do NOT suggest using any tools to modify files.
2. Do NOT attempt to run commands, create files, or make changes.
3. Focus solely on analyzing the provided code and specifications.
4. Provide your analysis as structured text output only.
"""

        type_prompts = {
            "implementation_review": """
Your goal is to compare implementation against specifications and identify:
- Missing features or incomplete implementations
- Deviations from the spec
- Potential bugs or issues
- Areas that need improvement

Format your response with these sections:
## Summary
Brief overview of the implementation status.

## Issues Found
List specific issues with severity (CRITICAL, WARNING, INFO).
Format: [SEVERITY] Description - Recommendation

## Coverage Analysis
What percentage of the spec appears to be implemented.

## Recommendations
Prioritized list of actions to address issues.
""",
            "code_quality": """
Your goal is to analyze code quality and identify:
- Code style and consistency issues
- Potential bugs or error-prone patterns
- Performance concerns
- Security vulnerabilities
- Test coverage gaps

Format your response with these sections:
## Summary
Brief quality assessment.

## Issues Found
List issues with severity (CRITICAL, WARNING, INFO).

## Recommendations
Prioritized improvements.
""",
            "spec_gap": """
Your goal is to find gaps between specification and implementation:
- Features in spec but not in code
- Features in code but not in spec
- Partial implementations
- Behavioral differences

Format your response with these sections:
## Summary
Overview of spec coverage.

## Gaps Found
List gaps with impact assessment.

## Alignment Score
Estimate of spec-to-implementation alignment (0-100%).
""",
        }

        return base_prompt + type_prompts.get(analysis_type, type_prompts["implementation_review"])

    def _build_analysis_user_prompt(
        self,
        context: str,
        files_content: dict[str, str] | None,
        analysis_type: str,
    ) -> str:
        """Build user prompt with context and file contents."""
        parts = [f"# Analysis Request\n\n{context}"]

        if files_content:
            parts.append("\n\n# Files to Analyze\n")
            for path, content in files_content.items():
                # Truncate very large files
                if len(content) > 50000:
                    content = content[:50000] + "\n... [truncated]"
                parts.append(f"\n## {path}\n```\n{content}\n```\n")

        parts.append(f"\n\nPlease perform a {analysis_type.replace('_', ' ')} analysis.")

        return "".join(parts)
