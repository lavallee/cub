"""
Unit tests for punchlist parser.

Tests the markdown parsing functionality that extracts items
separated by em-dash delimiters.
"""

from pathlib import Path

import pytest

from cub.core.punchlist.models import PunchlistItem
from cub.core.punchlist.parser import parse_punchlist, parse_punchlist_content


class TestParseContent:
    """Test parse_punchlist_content function."""

    def test_single_item(self) -> None:
        """Test parsing content with a single item (no separators)."""
        content = "Fix the typo in README"
        items = parse_punchlist_content(content)

        assert len(items) == 1
        assert items[0].raw_text == "Fix the typo in README"
        assert items[0].index == 0

    def test_two_items_em_dash(self) -> None:
        """Test parsing two items separated by em-dash."""
        content = """Fix the typo in README

——

Add --verbose flag to cub run"""
        items = parse_punchlist_content(content)

        assert len(items) == 2
        assert items[0].raw_text == "Fix the typo in README"
        assert items[1].raw_text == "Add --verbose flag to cub run"

    def test_two_items_regular_dash(self) -> None:
        """Test parsing two items separated by regular dashes."""
        content = """First item

--

Second item"""
        items = parse_punchlist_content(content)

        assert len(items) == 2
        assert items[0].raw_text == "First item"
        assert items[1].raw_text == "Second item"

    def test_multiple_items(self) -> None:
        """Test parsing multiple items."""
        content = """Item one

——

Item two

——

Item three"""
        items = parse_punchlist_content(content)

        assert len(items) == 3
        assert items[0].index == 0
        assert items[1].index == 1
        assert items[2].index == 2

    def test_empty_items_filtered(self) -> None:
        """Test that empty items (only whitespace) are filtered."""
        content = "Item one\n\n——\n\n\n\n——\n\nItem two"
        items = parse_punchlist_content(content)

        assert len(items) == 2
        assert items[0].raw_text == "Item one"
        assert items[1].raw_text == "Item two"

    def test_multiline_item(self) -> None:
        """Test parsing items with multiple lines."""
        content = """First line of first item
Second line of first item

——

First line of second item
Second line of second item
Third line"""
        items = parse_punchlist_content(content)

        assert len(items) == 2
        assert "Second line of first item" in items[0].raw_text
        assert "Third line" in items[1].raw_text

    def test_separator_with_extra_dashes(self) -> None:
        """Test separator with more than two dashes."""
        content = """First item

————

Second item"""
        items = parse_punchlist_content(content)

        assert len(items) == 2

    def test_separator_with_whitespace(self) -> None:
        """Test separator with surrounding whitespace."""
        content = """First item

  ——

Second item"""
        items = parse_punchlist_content(content)

        assert len(items) == 2

    def test_empty_content(self) -> None:
        """Test parsing empty content."""
        items = parse_punchlist_content("")
        assert len(items) == 0

    def test_only_whitespace(self) -> None:
        """Test parsing content with only whitespace."""
        items = parse_punchlist_content("   \n\n   ")
        assert len(items) == 0

    def test_inline_dashes_not_separator(self) -> None:
        """Test that dashes within text are not treated as separators."""
        content = """Item with --flag option in it

——

Another item"""
        items = parse_punchlist_content(content)

        assert len(items) == 2
        assert "--flag" in items[0].raw_text

    def test_preserves_internal_formatting(self) -> None:
        """Test that markdown formatting is preserved within items."""
        content = """## Item One

- Bullet point 1
- Bullet point 2

```python
code here
```

——

Item Two"""
        items = parse_punchlist_content(content)

        assert len(items) == 2
        assert "## Item One" in items[0].raw_text
        assert "- Bullet point 1" in items[0].raw_text
        assert "```python" in items[0].raw_text

    def test_real_world_example(self) -> None:
        """Test parsing a realistic punchlist content."""
        content = """at the end of a cub run with —epic, we should check if there are any tasks remaining for that epic. if all tasks are complete/closed, we can close/complete the epic as well.

——

cub doctor should look for epics with no incomplete tasks and close them

——

by default, a cub run should create a new branch off of main (or —from-branch if it is specified). let's add a flag —use-current-branch to explicitly allow cub run to work in the current branch.

because main can be out of date due to the way beads does worktrees, we should branch from origin/main, not local main."""
        items = parse_punchlist_content(content)

        assert len(items) == 3
        assert "cub run with —epic" in items[0].raw_text
        assert "cub doctor" in items[1].raw_text
        assert "—use-current-branch" in items[2].raw_text


class TestParseFile:
    """Test parse_punchlist function with file I/O."""

    def test_parse_file(self, tmp_path: Path) -> None:
        """Test parsing a punchlist from a file."""
        file_path = tmp_path / "test-punchlist.md"
        file_path.write_text(
            """Item one

——

Item two""",
            encoding="utf-8",
        )

        items = parse_punchlist(file_path)

        assert len(items) == 2
        assert items[0].raw_text == "Item one"
        assert items[1].raw_text == "Item two"

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Test that FileNotFoundError is raised for missing file."""
        file_path = tmp_path / "nonexistent.md"

        with pytest.raises(FileNotFoundError):
            parse_punchlist(file_path)

    def test_utf8_encoding(self, tmp_path: Path) -> None:
        """Test parsing file with UTF-8 characters."""
        file_path = tmp_path / "unicode.md"
        file_path.write_text(
            """Item with émojis 🎉

——

Item with — em-dashes — in text""",
            encoding="utf-8",
        )

        items = parse_punchlist(file_path)

        assert len(items) == 2
        assert "🎉" in items[0].raw_text
        assert "— em-dashes —" in items[1].raw_text


class TestPunchlistItemModel:
    """Test PunchlistItem dataclass."""

    def test_item_attributes(self) -> None:
        """Test PunchlistItem has expected attributes."""
        item = PunchlistItem(raw_text="Test content", index=5)

        assert item.raw_text == "Test content"
        assert item.index == 5

    def test_item_equality(self) -> None:
        """Test PunchlistItem equality."""
        item1 = PunchlistItem(raw_text="Test", index=0)
        item2 = PunchlistItem(raw_text="Test", index=0)

        assert item1 == item2

    def test_item_inequality(self) -> None:
        """Test PunchlistItem inequality."""
        item1 = PunchlistItem(raw_text="Test", index=0)
        item2 = PunchlistItem(raw_text="Test", index=1)

        assert item1 != item2
