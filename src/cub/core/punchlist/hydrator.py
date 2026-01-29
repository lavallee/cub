"""
Punchlist-specific hydration using the core hydrate engine.

Provides the punchlist-specific prompt template and wraps the
generic hydration engine for punchlist items.
"""

from cub.core.hydrate.engine import (
    DebugCallback,
    OnCompleteCallback,
    OnStartCallback,
    StreamCallback,
    hydrate,
    hydrate_batch,
)
from cub.core.hydrate.models import HydrationResult
from cub.core.punchlist.models import PunchlistItem

# Default timeout for Claude CLI calls (seconds)
CLAUDE_TIMEOUT = 60

# Punchlist-specific prompt template
PUNCHLIST_PROMPT = """Given this bug/feature request, generate a structured task description.

Request:
{text}

Respond in this exact format (preserve these exact labels):
TITLE: <concise title, 50 chars max, imperative mood like "Fix X" or "Add Y">
CONTEXT: <one paragraph explaining the problem/feature and why it matters>
STEPS:
1. <implementation step>
2. <implementation step>
CRITERIA:
- [ ] <acceptance criterion>
- [ ] <acceptance criterion>"""


def hydrate_item(
    item: PunchlistItem,
    timeout: int = CLAUDE_TIMEOUT,
    stream: bool = False,
    debug: bool = False,
    stream_callback: StreamCallback | None = None,
    debug_callback: DebugCallback | None = None,
) -> HydrationResult:
    """
    Hydrate a single punchlist item using Claude.

    Args:
        item: The raw punchlist item to hydrate.
        timeout: Timeout in seconds for the Claude CLI call.
        stream: If True, stream stdout line-by-line.
        debug: If True, emit debug info.
        stream_callback: Called with each line when streaming.
        debug_callback: Called with debug messages.

    Returns:
        HydrationResult with structured output.
    """
    return hydrate(
        text=item.raw_text,
        prompt_template=PUNCHLIST_PROMPT,
        timeout=timeout,
        stream=stream,
        debug=debug,
        stream_callback=stream_callback,
        debug_callback=debug_callback,
    )


def hydrate_items(
    items: list[PunchlistItem],
    timeout: int = CLAUDE_TIMEOUT,
    stream: bool = False,
    debug: bool = False,
    stream_callback: StreamCallback | None = None,
    debug_callback: DebugCallback | None = None,
    on_start: OnStartCallback | None = None,
    on_complete: OnCompleteCallback | None = None,
) -> list[HydrationResult]:
    """
    Hydrate multiple punchlist items with progress callbacks.

    Args:
        items: List of raw punchlist items.
        timeout: Timeout per item for Claude CLI calls.
        stream: If True, stream each item's output.
        debug: If True, emit debug info.
        stream_callback: Called with each line when streaming.
        debug_callback: Called with debug messages.
        on_start: Called before each item with (index, total, source_text).
        on_complete: Called after each item with (index, total, result).

    Returns:
        List of HydrationResult objects.
    """
    texts = [item.raw_text for item in items]
    return hydrate_batch(
        texts=texts,
        prompt_template=PUNCHLIST_PROMPT,
        timeout=timeout,
        stream=stream,
        debug=debug,
        stream_callback=stream_callback,
        debug_callback=debug_callback,
        on_start=on_start,
        on_complete=on_complete,
    )
