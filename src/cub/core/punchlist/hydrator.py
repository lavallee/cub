"""
Punchlist item hydration using Claude.

Uses Claude Haiku to expand brief punchlist items into
structured titles and descriptions suitable for task creation.
"""

import re
import subprocess
from pathlib import Path

from cub.core.punchlist.models import HydratedItem, PunchlistItem

# Default timeout for Claude CLI calls (seconds)
CLAUDE_TIMEOUT = 60


def hydrate_item(item: PunchlistItem, timeout: int = CLAUDE_TIMEOUT) -> HydratedItem:
    """
    Hydrate a single punchlist item using Claude.

    Calls Claude Haiku to generate a concise title and
    detailed description from the raw item text.

    Args:
        item: The raw punchlist item to hydrate.
        timeout: Timeout in seconds for the Claude CLI call.

    Returns:
        HydratedItem with AI-generated title and description.

    Raises:
        RuntimeError: If Claude CLI fails or returns invalid output.
    """
    prompt = f"""Given this bug/feature request, generate:
1. A concise title (50 chars max, imperative mood like "Fix X" or "Add Y")
2. A clear description with context and acceptance criteria

Request:
{item.raw_text}

Respond in this exact format (preserve these exact labels):
TITLE: <title here>
DESCRIPTION: <description here>"""

    try:
        result = subprocess.run(
            ["claude", "--model", "haiku", "--print", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            # Fall back to simple extraction
            return _fallback_hydrate(item)

        return _parse_hydration_response(result.stdout, item)

    except subprocess.TimeoutExpired:
        return _fallback_hydrate(item)
    except FileNotFoundError:
        # Claude CLI not installed
        return _fallback_hydrate(item)
    except OSError:
        return _fallback_hydrate(item)


def hydrate_items(
    items: list[PunchlistItem],
    timeout: int = CLAUDE_TIMEOUT,
) -> list[HydratedItem]:
    """
    Hydrate multiple punchlist items.

    Args:
        items: List of raw punchlist items.
        timeout: Timeout per item for Claude CLI calls.

    Returns:
        List of HydratedItem objects.
    """
    return [hydrate_item(item, timeout=timeout) for item in items]


def hydrate_and_write_back(
    path: Path,
    items: list[PunchlistItem],
    timeout: int = CLAUDE_TIMEOUT,
) -> list[HydratedItem]:
    """
    Hydrate all items and rewrite the punchlist file with structured format.

    After hydrating items with Claude, writes a formatted markdown file
    with clear headers and descriptions.

    Args:
        path: Path to the original punchlist file (will be overwritten).
        items: List of raw punchlist items to hydrate.
        timeout: Timeout per item for Claude CLI calls.

    Returns:
        List of HydratedItem objects.
    """
    hydrated = hydrate_items(items, timeout=timeout)

    # Generate structured markdown
    lines = [f"# Punchlist: {path.stem}", ""]

    for h in hydrated:
        lines.extend(
            [
                f"## {h.title}",
                "",
                h.description,
                "",
                "---",
                "",
            ]
        )

    # Write back to original file
    path.write_text("\n".join(lines), encoding="utf-8")

    return hydrated


def _parse_hydration_response(response: str, item: PunchlistItem) -> HydratedItem:
    """
    Parse Claude's response into title and description.

    Args:
        response: Raw output from Claude CLI.
        item: Original punchlist item for fallback.

    Returns:
        HydratedItem parsed from the response.
    """
    # Extract TITLE: line
    title_match = re.search(r"TITLE:\s*(.+?)(?:\n|$)", response, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else ""

    # Extract DESCRIPTION: section (everything after DESCRIPTION: label)
    desc_match = re.search(r"DESCRIPTION:\s*(.+)", response, re.IGNORECASE | re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else ""

    # Validate and fall back if needed
    if not title or not description:
        return _fallback_hydrate(item)

    return HydratedItem(
        title=title[:100],  # Truncate long titles
        description=description,
        raw_item=item,
    )


def _fallback_hydrate(item: PunchlistItem) -> HydratedItem:
    """
    Generate a basic hydration without AI.

    Used when Claude CLI is unavailable or fails.

    Args:
        item: The raw punchlist item.

    Returns:
        HydratedItem with simple title extraction.
    """
    # Use first line or first 50 chars as title
    lines = item.raw_text.strip().split("\n")
    first_line = lines[0].strip()

    # Create title from first line
    if len(first_line) <= 50:
        title = first_line
    else:
        # Truncate at word boundary
        title = first_line[:47]
        if " " in title:
            title = title.rsplit(" ", 1)[0]
        title += "..."

    # Use full text as description
    description = item.raw_text.strip()

    return HydratedItem(
        title=title,
        description=description,
        raw_item=item,
    )
