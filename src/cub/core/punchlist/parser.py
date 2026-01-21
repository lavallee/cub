"""
Punchlist markdown parser.

Parses markdown files containing punchlist items separated by
em-dash delimiters (——) into structured PunchlistItem objects.
"""

import re
from pathlib import Path

from cub.core.punchlist.models import PunchlistItem

# Match em-dash separator: at least two em-dashes or regular dashes
# on their own line (possibly with horizontal whitespace)
# Use [^\S\n] to match whitespace excluding newlines
SEPARATOR_PATTERN = re.compile(r"\n[^\S\n]*[—\-]{2,}[^\S\n]*\n")


def parse_punchlist(path: Path) -> list[PunchlistItem]:
    """
    Parse a punchlist markdown file into items.

    Items are separated by em-dash delimiters (—— or --).
    Empty items (only whitespace) are filtered out.

    Args:
        path: Path to the punchlist markdown file.

    Returns:
        List of PunchlistItem objects, one per delimited section.

    Raises:
        FileNotFoundError: If the file does not exist.
        PermissionError: If the file cannot be read.

    Example:
        >>> items = parse_punchlist(Path("bugs.md"))
        >>> len(items)
        9
        >>> items[0].raw_text
        'Fix the typo in README...'
    """
    content = path.read_text(encoding="utf-8")
    return parse_punchlist_content(content)


def parse_punchlist_content(content: str) -> list[PunchlistItem]:
    """
    Parse punchlist content string into items.

    This is the core parsing function, useful for testing
    without file I/O.

    Args:
        content: Raw markdown content with em-dash separators.

    Returns:
        List of PunchlistItem objects.
    """
    # Split on em-dash separator pattern
    raw_items = SEPARATOR_PATTERN.split(content)

    items: list[PunchlistItem] = []
    for index, raw_text in enumerate(raw_items):
        # Strip whitespace and skip empty items
        text = raw_text.strip()
        if text:
            items.append(PunchlistItem(raw_text=text, index=index))

    return items
