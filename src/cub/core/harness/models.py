"""
Harness data models for cub.

Defines models for AI coding assistant integration, including
capabilities detection, invocation results, and usage tracking.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


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
    """

    streaming: bool = Field(
        default=False,
        description="Supports real-time streaming output with JSON events"
    )
    token_reporting: bool = Field(
        default=False,
        description="Reports token usage in output"
    )
    system_prompt: bool = Field(
        default=False,
        description="Supports separate system prompt parameter"
    )
    auto_mode: bool = Field(
        default=False,
        description="Has autonomous mode for unattended operation"
    )
    json_output: bool = Field(
        default=False,
        description="Supports JSON output format"
    )
    model_selection: bool = Field(
        default=False,
        description="Supports model selection via CLI flag"
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
    cache_read_tokens: int = Field(
        default=0,
        description="Tokens read from prompt cache"
    )
    cache_creation_tokens: int = Field(
        default=0,
        description="Tokens written to prompt cache"
    )
    cost_usd: Optional[float] = Field(
        default=None,
        description="Estimated cost in USD (if available)"
    )
    estimated: bool = Field(
        default=False,
        description="Whether usage is estimated (not from API)"
    )

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
    usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Token usage statistics"
    )
    duration_seconds: float = Field(
        default=0.0,
        description="How long the invocation took"
    )
    exit_code: int = Field(default=0, description="Exit code from harness CLI")
    error: Optional[str] = Field(
        default=None,
        description="Error message if invocation failed"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the invocation occurred"
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
