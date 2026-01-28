"""
Transcript parser for extracting token usage and cost from Claude Code transcripts.

Claude Code provides the transcript path in hook payloads. Parsing it post-session
can extract token usage, cost, and model info that hooks themselves can't observe.
This closes the gap between `cub run` (which gets token data from the harness) and
direct sessions.

The transcript is a JSONL file where each line represents a turn (user input or
assistant output) in the conversation. Each assistant output contains usage data
from the Claude API.

Example transcript line:
    {
        "type": "output",
        "content": [...],
        "model": "claude-sonnet-4-5-20250929",
        "usage": {
            "input_tokens": 12543,
            "output_tokens": 892,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 8234
        },
        "timestamp": "2026-01-28T10:30:15.123Z"
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cub.core.ledger.models import TokenUsage

# Pricing per million tokens (as of 2026-01-28)
# Source: https://platform.claude.com/docs/en/about-claude/pricing
PRICING_PER_MILLION: dict[str, dict[str, float]] = {
    # Opus 4.5
    "claude-opus-4-5": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_creation": 18.75,
    },
    "claude-opus-4-5-20251101": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_creation": 18.75,
    },
    # Opus 4
    "claude-opus-4-20250514": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_creation": 18.75,
    },
    # Sonnet 4.5
    "claude-sonnet-4-5": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    # Sonnet 4
    "claude-sonnet-4-20250514": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    # Sonnet 3.7
    "claude-3-7-sonnet-latest": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    "claude-3-7-sonnet-20250219": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    # Sonnet 3.5
    "claude-3-5-sonnet-latest": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    "claude-3-5-sonnet-20240620": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    # Haiku 3.5
    "claude-3-5-haiku-latest": {
        "input": 1.00,
        "output": 5.00,
        "cache_read": 0.10,
        "cache_creation": 1.25,
    },
    "claude-3-5-haiku-20241022": {
        "input": 1.00,
        "output": 5.00,
        "cache_read": 0.10,
        "cache_creation": 1.25,
    },
    # Haiku 3
    "claude-3-haiku-20240307": {
        "input": 0.25,
        "output": 1.25,
        "cache_read": 0.03,
        "cache_creation": 0.30,
    },
}


@dataclass
class TranscriptData:
    """Extracted data from transcript parsing.

    Attributes:
        total_input_tokens: Sum of all input tokens
        total_output_tokens: Sum of all output tokens
        total_cache_read_tokens: Sum of all cache read tokens
        total_cache_creation_tokens: Sum of all cache creation tokens
        model: Model name from transcript (e.g., "claude-sonnet-4-5-20250929")
        normalized_model: Normalized model name (e.g., "sonnet", "opus", "haiku")
        total_cost_usd: Estimated total cost in USD
        num_turns: Number of assistant turns in the transcript
    """

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    model: str = ""
    normalized_model: str = ""
    total_cost_usd: float = 0.0
    num_turns: int = 0


def normalize_model_name(model: str) -> str:
    """Normalize full model identifier to short name.

    Args:
        model: Full model identifier (e.g., "claude-sonnet-4-5-20250929")

    Returns:
        Normalized model name (e.g., "sonnet", "opus", "haiku")

    Examples:
        >>> normalize_model_name("claude-sonnet-4-5-20250929")
        'sonnet'
        >>> normalize_model_name("claude-opus-4-5")
        'opus'
        >>> normalize_model_name("claude-3-5-haiku-latest")
        'haiku'
    """
    lower = model.lower()
    if "opus" in lower:
        return "opus"
    elif "sonnet" in lower:
        return "sonnet"
    elif "haiku" in lower:
        return "haiku"
    else:
        return "unknown"


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
    model: str,
) -> float:
    """Calculate cost in USD for token usage.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cache_read_tokens: Number of cache read tokens
        cache_creation_tokens: Number of cache creation tokens
        model: Model identifier

    Returns:
        Cost in USD

    Examples:
        >>> calculate_cost(10000, 5000, 0, 0, "claude-sonnet-4-5-20250929")
        0.105
        >>> calculate_cost(10000, 5000, 8000, 0, "claude-sonnet-4-5-20250929")
        0.1074
    """
    pricing = PRICING_PER_MILLION.get(model)
    if not pricing:
        # Default to Sonnet pricing if unknown
        pricing = PRICING_PER_MILLION.get("claude-sonnet-4-5-20250929", {
            "input": 3.00,
            "output": 15.00,
            "cache_read": 0.30,
            "cache_creation": 3.75,
        })

    cost = (
        (input_tokens * pricing["input"] / 1_000_000)
        + (output_tokens * pricing["output"] / 1_000_000)
        + (cache_read_tokens * pricing["cache_read"] / 1_000_000)
        + (cache_creation_tokens * pricing["cache_creation"] / 1_000_000)
    )

    return cost


def parse_transcript(transcript_path: Path) -> TranscriptData:
    """Parse Claude Code transcript to extract token usage and model info.

    Reads a transcript JSONL file and aggregates token usage across all assistant
    turns. Each line in the transcript represents either a user input or assistant
    output. We only process assistant outputs as they contain usage data.

    Args:
        transcript_path: Path to transcript JSONL file

    Returns:
        TranscriptData with aggregated metrics

    Raises:
        FileNotFoundError: If transcript file doesn't exist

    Examples:
        >>> data = parse_transcript(Path("session.jsonl"))
        >>> data.total_input_tokens
        45230
        >>> data.model
        'claude-sonnet-4-5-20250929'
        >>> data.normalized_model
        'sonnet'
    """
    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

    data = TranscriptData()

    with transcript_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed lines
                continue

            # Only process assistant outputs (they contain usage data)
            if entry.get("type") != "output":
                continue

            data.num_turns += 1

            # Extract model (should be consistent across turns)
            if not data.model and "model" in entry:
                data.model = entry["model"]
                data.normalized_model = normalize_model_name(data.model)

            # Extract usage data
            usage = entry.get("usage", {})
            if usage:
                data.total_input_tokens += usage.get("input_tokens", 0)
                data.total_output_tokens += usage.get("output_tokens", 0)
                data.total_cache_read_tokens += usage.get("cache_read_input_tokens", 0)
                data.total_cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)

    # Calculate total cost
    data.total_cost_usd = calculate_cost(
        data.total_input_tokens,
        data.total_output_tokens,
        data.total_cache_read_tokens,
        data.total_cache_creation_tokens,
        data.model,
    )

    return data


def to_token_usage(data: TranscriptData) -> TokenUsage:
    """Convert TranscriptData to TokenUsage model.

    Args:
        data: Parsed transcript data

    Returns:
        TokenUsage instance

    Examples:
        >>> data = TranscriptData(
        ...     total_input_tokens=10000,
        ...     total_output_tokens=5000,
        ...     total_cache_read_tokens=2000,
        ...     total_cache_creation_tokens=500
        ... )
        >>> usage = to_token_usage(data)
        >>> usage.input_tokens
        10000
    """
    return TokenUsage(
        input_tokens=data.total_input_tokens,
        output_tokens=data.total_output_tokens,
        cache_read_tokens=data.total_cache_read_tokens,
        cache_creation_tokens=data.total_cache_creation_tokens,
    )
