"""
Harness data models for cub.

Defines models for AI coding assistant integration, including
capabilities detection, invocation results, and usage tracking.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HarnessFeature(str, Enum):
    """
    Enum for type-safe feature queries.

    Provides type-safe way to query harness capabilities via
    supports_feature() method.
    """

    STREAMING = "streaming"
    TOKEN_REPORTING = "token_reporting"
    SYSTEM_PROMPT = "system_prompt"
    AUTO_MODE = "auto_mode"
    JSON_OUTPUT = "json_output"
    MODEL_SELECTION = "model_selection"
    HOOKS = "hooks"
    CUSTOM_TOOLS = "custom_tools"
    SESSIONS = "sessions"
    SESSION_FORKING = "session_forking"
    SUBAGENTS = "subagents"


class HookEvent(str, Enum):
    """
    Events that can trigger hooks.

    Hooks intercept these events during task execution, allowing
    external code to block or modify behavior.
    """

    PRE_TASK = "pre_task"  # Before task execution starts
    POST_TASK = "post_task"  # After task execution completes
    PRE_TOOL_USE = "pre_tool_use"  # Before a tool is invoked
    POST_TOOL_USE = "post_tool_use"  # After a tool completes
    ON_ERROR = "on_error"  # When an error occurs
    ON_MESSAGE = "on_message"  # When a message is received


@dataclass
class HookContext:
    """
    Context provided to hook handlers.

    Contains information about the current event and relevant data
    for the hook to make decisions.
    """

    event: HookEvent
    task_id: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: str | None = None
    message_content: str | None = None
    message_role: str | None = None
    error: Exception | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    """
    Result returned from a hook handler.

    Indicates whether to block the action and provides optional
    modifications to the input.
    """

    block: bool = False  # Whether to block the action
    reason: str | None = None  # Reason for blocking (for logging/debugging)
    modified_input: dict[str, Any] | None = None  # Modified input for tool calls


# Type alias for hook handlers
# Handlers receive context and return an optional result (None = allow action)
HookHandler = Callable[["HookContext"], Awaitable["HookResult | None"]]


class HarnessCapabilities(BaseModel):
    """
    Capabilities for a specific harness.

    Different harnesses have different features. This model tracks
    what a harness can do so cub can adapt its behavior accordingly.

    Capabilities:
        streaming: Real-time output streaming with JSON events
        token_reporting: Reports token usage after invocation
        system_prompt: Supports separate system prompt parameter
        auto_mode: Has autonomous/auto-approve mode
        json_output: Supports JSON output format
        model_selection: Supports model selection via CLI flag
        hooks: Supports SDK hooks (circuit breakers, tool interception)
        custom_tools: Supports custom tool definitions
        sessions: Supports stateful multi-turn sessions
        session_forking: Supports forking sessions to preserve context
        subagents: Supports launching subagents within a session
    """

    streaming: bool = Field(
        default=False, description="Supports real-time streaming output with JSON events"
    )
    token_reporting: bool = Field(default=False, description="Reports token usage in output")
    system_prompt: bool = Field(
        default=False, description="Supports separate system prompt parameter"
    )
    auto_mode: bool = Field(
        default=False, description="Has autonomous mode for unattended operation"
    )
    json_output: bool = Field(default=False, description="Supports JSON output format")
    model_selection: bool = Field(
        default=False, description="Supports model selection via CLI flag"
    )
    hooks: bool = Field(
        default=False, description="Supports SDK hooks for circuit breakers and tool interception"
    )
    custom_tools: bool = Field(
        default=False, description="Supports custom tool definitions"
    )
    sessions: bool = Field(
        default=False, description="Supports stateful multi-turn sessions"
    )
    session_forking: bool = Field(
        default=False, description="Supports forking sessions to preserve context"
    )
    subagents: bool = Field(
        default=False, description="Supports launching subagents within a session"
    )

    def has(self, capability: str) -> bool:
        """
        Check if harness has a specific capability.

        Args:
            capability: Capability name to check

        Returns:
            True if capability is supported
        """
        return getattr(self, capability, False)


class TokenUsage(BaseModel):
    """
    Token usage for a harness invocation.

    Tracks input/output tokens and cache usage for cost estimation
    and budget tracking.
    """

    input_tokens: int = Field(default=0, description="Input tokens consumed")
    output_tokens: int = Field(default=0, description="Output tokens generated")
    cache_read_tokens: int = Field(default=0, description="Tokens read from prompt cache")
    cache_creation_tokens: int = Field(default=0, description="Tokens written to prompt cache")
    cost_usd: float | None = Field(default=None, description="Estimated cost in USD (if available)")
    estimated: bool = Field(default=False, description="Whether usage is estimated (not from API)")

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed (input + output)."""
        return self.input_tokens + self.output_tokens

    @property
    def effective_input_tokens(self) -> int:
        """
        Effective input tokens after cache.

        Returns the number of input tokens that weren't served from cache.
        """
        return max(0, self.input_tokens - self.cache_read_tokens)


class HarnessResult(BaseModel):
    """
    Result from a harness invocation.

    Contains the output text, token usage, and timing information
    for a single AI coding assistant session.
    """

    output: str = Field(default="", description="Text output from harness")
    usage: TokenUsage = Field(default_factory=TokenUsage, description="Token usage statistics")
    duration_seconds: float = Field(default=0.0, description="How long the invocation took")
    exit_code: int = Field(default=0, description="Exit code from harness CLI")
    error: str | None = Field(default=None, description="Error message if invocation failed")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the invocation occurred"
    )

    @property
    def success(self) -> bool:
        """Check if invocation was successful."""
        return self.exit_code == 0 and self.error is None

    @property
    def failed(self) -> bool:
        """Check if invocation failed."""
        return not self.success


# Capability constants for consistency with bash code
HARNESS_CAP_STREAMING = "streaming"
HARNESS_CAP_TOKEN_REPORTING = "token_reporting"
HARNESS_CAP_SYSTEM_PROMPT = "system_prompt"
HARNESS_CAP_AUTO_MODE = "auto_mode"
HARNESS_CAP_JSON_OUTPUT = "json_output"
HARNESS_CAP_MODEL_SELECTION = "model_selection"


class TaskInput(BaseModel):
    """
    Input parameters for async harness execution.

    Distinct from beads Task model to avoid coupling harness
    interface to specific task backend implementation.
    """

    prompt: str = Field(description="User/task prompt to execute")
    system_prompt: str | None = Field(default=None, description="System prompt (prepended instructions)")
    working_dir: str | None = Field(default=None, description="Working directory for task execution")
    model: str | None = Field(default=None, description="Model name (e.g., 'sonnet', 'opus')")
    auto_approve: bool = Field(default=False, description="Auto-approve mode for unattended execution")
    permissions: dict[str, bool] | None = Field(
        default=None, description="Permission flags (e.g., network access, file writes)"
    )
    session_id: str | None = Field(default=None, description="Session ID for stateful execution")
    parent_session_id: str | None = Field(default=None, description="Parent session ID for forking")
    custom_tools: list[dict[str, object]] | None = Field(
        default=None, description="Custom tool definitions for SDK"
    )


class ToolUse(BaseModel):
    """
    Tool invocation from SDK message parsing.

    Tracks tool calls made during harness execution.
    """

    tool_name: str = Field(description="Name of tool invoked")
    tool_input: dict[str, object] = Field(default_factory=dict, description="Input parameters to tool")
    tool_output: str | None = Field(default=None, description="Output from tool execution")
    success: bool = Field(default=True, description="Whether tool execution succeeded")


class Message(BaseModel):
    """
    Message from SDK message parsing.

    Represents a single turn in the conversation history.
    """

    role: str = Field(description="Message role (user, assistant, system)")
    content: str = Field(description="Message content text")
    tool_uses: list[ToolUse] = Field(default_factory=list, description="Tool invocations in this message")
    timestamp: datetime = Field(default_factory=datetime.now, description="When message was created")


class TaskResult(BaseModel):
    """
    Extended result from async harness execution.

    Extends HarnessResult with SDK-specific fields for message
    history, file tracking, and rich execution metadata.
    """

    output: str = Field(default="", description="Text output from harness")
    usage: TokenUsage = Field(default_factory=TokenUsage, description="Token usage statistics")
    duration_seconds: float = Field(default=0.0, description="How long the invocation took")
    exit_code: int = Field(default=0, description="Exit code from harness")
    error: str | None = Field(default=None, description="Error message if invocation failed")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the invocation occurred"
    )
    messages: list[Message] = Field(default_factory=list, description="Conversation history from SDK")
    files_changed: list[str] = Field(default_factory=list, description="Files modified during execution")
    files_created: list[str] = Field(default_factory=list, description="Files created during execution")
    session_id: str | None = Field(default=None, description="Session ID if stateful execution")

    @property
    def success(self) -> bool:
        """Check if invocation was successful."""
        return self.exit_code == 0 and self.error is None

    @property
    def failed(self) -> bool:
        """Check if invocation failed."""
        return not self.success
