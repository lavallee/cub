"""
Tests for the changelog parser in the dashboard sync layer.

Tests cover:
- Parsing valid CHANGELOG with multiple releases
- Extracting task IDs in various formats (cub-xxx, cub-xxx.n, #123)
- Handling missing CHANGELOG file (graceful degradation)
- Handling empty CHANGELOG file
- Handling malformed release headers
- Handling unparseable content
- Release date parsing
- Task ID normalization (case-insensitive)
- Finding which release a task belongs to
- Getting all released task IDs
"""

from datetime import datetime
from pathlib import Path

import pytest

from cub.core.dashboard.sync.parsers.changelog import ChangelogParser, Release


@pytest.fixture
def tmp_changelog(tmp_path: Path) -> Path:
    """Create temporary CHANGELOG.md path."""
    return tmp_path / "CHANGELOG.md"


class TestChangelogParser:
    """Tests for the ChangelogParser class."""

    def test_parse_valid_changelog(self, tmp_changelog: Path) -> None:
        """Test parsing a valid CHANGELOG with multiple releases."""
        changelog_content = """# Changelog

All notable changes to this project are documented in this file.

---

## [0.27.1] - 2026-01-23

### Added

- Add cub punchlist command (cub-abc.1)
- Implement dashboard sync (cub-xyz.2)
- Feature/test (#54)

### Fixed

- Fix authentication bug (cub-auth.5)
- Resolve memory leak (#123)

---

## [0.27.0] - 2026-01-22

### Added

- New dashboard UI (cub-ui.1, cub-ui.2)
- Epic cub-data completed

### Changed

- Update dependencies

---
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        releases = parser.parse()

        assert len(releases) == 2

        # Check first release
        release_1 = releases[0]
        assert release_1.version == "0.27.1"
        assert release_1.date == datetime(2026, 1, 23)
        assert "cub-abc.1" in release_1.task_ids
        assert "cub-xyz.2" in release_1.task_ids
        assert "cub-auth.5" in release_1.task_ids
        assert "#54" in release_1.task_ids
        assert "#123" in release_1.task_ids
        assert len(release_1.task_ids) == 5

        # Check second release
        release_2 = releases[1]
        assert release_2.version == "0.27.0"
        assert release_2.date == datetime(2026, 1, 22)
        assert "cub-ui.1" in release_2.task_ids
        assert "cub-ui.2" in release_2.task_ids
        assert "cub-data" in release_2.task_ids

    def test_parse_missing_changelog(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing when CHANGELOG.md doesn't exist."""
        nonexistent = tmp_path / "nonexistent" / "CHANGELOG.md"
        parser = ChangelogParser(nonexistent)

        releases = parser.parse()

        assert len(releases) == 0
        assert "CHANGELOG not found" in caplog.text

    def test_parse_empty_changelog(
        self, tmp_changelog: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing an empty CHANGELOG file."""
        tmp_changelog.write_text("")
        parser = ChangelogParser(tmp_changelog)

        releases = parser.parse()

        assert len(releases) == 0
        assert "CHANGELOG is empty" in caplog.text

    def test_extract_task_id_formats(self, tmp_changelog: Path) -> None:
        """Test extraction of various task ID formats."""
        changelog_content = """# Changelog

## [1.0.0] - 2026-01-23

### Tasks Completed

- cub-abc.1: Simple task ID
- CUB-XYZ.2: Uppercase ID (should normalize)
- epic:cub-foo: Epic prefix
- Fixed #456 and #789
- Merged PR (#999)
- cub-test: Epic without task number
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        releases = parser.parse()

        assert len(releases) == 1
        release = releases[0]

        # All IDs should be normalized to lowercase
        assert "cub-abc.1" in release.task_ids
        assert "cub-xyz.2" in release.task_ids
        assert "cub-foo" in release.task_ids
        assert "#456" in release.task_ids
        assert "#789" in release.task_ids
        assert "#999" in release.task_ids
        assert "cub-test" in release.task_ids

    def test_parse_malformed_date(
        self, tmp_changelog: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing release with malformed date."""
        changelog_content = """# Changelog

## [1.0.0] - not-a-date

### Fixed

- Task cub-abc.1
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        releases = parser.parse()

        assert len(releases) == 1
        assert releases[0].version == "1.0.0"
        assert releases[0].date is None  # Date parsing failed gracefully
        # Should log debug message (not warning) when no date pattern found
        assert "cub-abc.1" in releases[0].task_ids

    def test_parse_no_releases(self, tmp_changelog: Path) -> None:
        """Test parsing CHANGELOG with no valid release headers."""
        changelog_content = """# Changelog

This is just a regular changelog without proper headers.

Some changes:
- Did something
- Did something else
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        releases = parser.parse()

        assert len(releases) == 0

    def test_get_released_task_ids(self, tmp_changelog: Path) -> None:
        """Test getting all released task IDs across all releases."""
        changelog_content = """# Changelog

## [2.0.0] - 2026-01-23

- Task cub-new.1
- Task cub-new.2

---

## [1.0.0] - 2026-01-22

- Task cub-old.1
- Task cub-old.2
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        released_ids = parser.get_released_task_ids()

        assert len(released_ids) == 4
        assert "cub-new.1" in released_ids
        assert "cub-new.2" in released_ids
        assert "cub-old.1" in released_ids
        assert "cub-old.2" in released_ids

    def test_get_task_release(self, tmp_changelog: Path) -> None:
        """Test finding which release a specific task belongs to."""
        changelog_content = """# Changelog

## [2.0.0] - 2026-01-23

- Task cub-new.1

---

## [1.0.0] - 2026-01-22

- Task cub-old.1
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        # Find task in first release
        release_new = parser.get_task_release("cub-new.1")
        assert release_new is not None
        assert release_new.version == "2.0.0"

        # Find task in second release
        release_old = parser.get_task_release("cub-old.1")
        assert release_old is not None
        assert release_old.version == "1.0.0"

        # Task not found
        release_missing = parser.get_task_release("cub-missing.1")
        assert release_missing is None

    def test_get_task_release_case_insensitive(self, tmp_changelog: Path) -> None:
        """Test that task release lookup is case-insensitive."""
        changelog_content = """# Changelog

## [1.0.0] - 2026-01-23

- Task cub-test.1
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        # Should find with different cases
        release_lower = parser.get_task_release("cub-test.1")
        release_upper = parser.get_task_release("CUB-TEST.1")
        release_mixed = parser.get_task_release("Cub-Test.1")

        assert release_lower is not None
        assert release_upper is not None
        assert release_mixed is not None
        assert release_lower.version == "1.0.0"
        assert release_upper.version == "1.0.0"
        assert release_mixed.version == "1.0.0"

    def test_is_released(self, tmp_changelog: Path) -> None:
        """Test checking if a task has been released."""
        changelog_content = """# Changelog

## [1.0.0] - 2026-01-23

- Task cub-released.1
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        assert parser.is_released("cub-released.1") is True
        assert parser.is_released("CUB-RELEASED.1") is True  # Case-insensitive
        assert parser.is_released("cub-not-released.1") is False

    def test_parse_with_version_summary_section(self, tmp_changelog: Path) -> None:
        """Test that parsing stops at version summary section."""
        changelog_content = """# Changelog

## [1.0.0] - 2026-01-23

- Task cub-real.1

---

## Version Summary

| Version | Date | Highlight |
|---------|------|-----------|
| 1.0.0 | 2026-01-23 | cub-fake.1 should not be parsed |
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        released_ids = parser.get_released_task_ids()

        assert "cub-real.1" in released_ids
        assert "cub-fake.1" not in released_ids  # Should stop at Version Summary

    def test_parse_real_changelog_format(self, tmp_changelog: Path) -> None:
        """Test parsing with format similar to actual project CHANGELOG."""
        # This is based on the actual CHANGELOG.md format from the codebase
        changelog_content = """# Changelog

All notable changes to Cub are documented in this file.

---

## [0.23.3] - 2026-01-15

### Added - Codebase Health Audit

- **`cub audit` Command** - Unified codebase health checking

### Tasks Completed

- cub-069: Implement dead code detection for Python
- cub-070: Implement dead code detection for Bash
- cub-071: Implement documentation validation

---

## [0.23.0] - 2026-01-15

### Added - Live Dashboard

- **Rich-Based Dashboard Renderer**
- **Status File Polling**

### Tasks Completed

- cub-074: Implement Rich-based dashboard renderer
- cub-075: Implement status file polling
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        releases = parser.parse()

        assert len(releases) == 2

        # Check first release
        release_1 = releases[0]
        assert release_1.version == "0.23.3"
        assert "cub-069" in release_1.task_ids
        assert "cub-070" in release_1.task_ids
        assert "cub-071" in release_1.task_ids

        # Check second release
        release_2 = releases[1]
        assert release_2.version == "0.23.0"
        assert "cub-074" in release_2.task_ids
        assert "cub-075" in release_2.task_ids

    def test_parse_changelog_with_no_task_ids(self, tmp_changelog: Path) -> None:
        """Test parsing changelog where releases have no task IDs."""
        changelog_content = """# Changelog

## [1.0.0] - 2026-01-23

### Added

- Some feature without task ID
- Another feature

### Changed

- Updated documentation
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        releases = parser.parse()

        assert len(releases) == 1
        assert releases[0].version == "1.0.0"
        assert len(releases[0].task_ids) == 0  # No task IDs found

    def test_parse_multiple_ids_same_line(self, tmp_changelog: Path) -> None:
        """Test extracting multiple task IDs from a single line."""
        changelog_content = """# Changelog

## [1.0.0] - 2026-01-23

- Completed cub-abc.1, cub-xyz.2, and cub-foo.3 together
- Fixed #123, #456, and #789 in one go
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        releases = parser.parse()

        assert len(releases) == 1
        release = releases[0]
        assert "cub-abc.1" in release.task_ids
        assert "cub-xyz.2" in release.task_ids
        assert "cub-foo.3" in release.task_ids
        assert "#123" in release.task_ids
        assert "#456" in release.task_ids
        assert "#789" in release.task_ids

    def test_release_repr(self) -> None:
        """Test Release object string representation."""
        release_with_date = Release("1.0.0", datetime(2026, 1, 23), {"cub-1", "cub-2"})
        repr_str = repr(release_with_date)

        assert "1.0.0" in repr_str
        assert "2026-01-23" in repr_str
        assert "2 tasks" in repr_str

        release_without_date = Release("2.0.0", None, {"cub-3"})
        repr_str_no_date = repr(release_without_date)

        assert "no date" in repr_str_no_date

    def test_parse_changelog_with_unicode(self, tmp_changelog: Path) -> None:
        """Test parsing changelog with unicode characters."""
        changelog_content = """# Changelog

## [1.0.0] - 2026-01-23

### Added

- ✨ New feature (cub-test.1)
- 🐛 Bug fix (cub-test.2)
- 📚 Documentation update (#123)
"""
        tmp_changelog.write_text(changelog_content, encoding="utf-8")
        parser = ChangelogParser(tmp_changelog)

        releases = parser.parse()

        assert len(releases) == 1
        assert "cub-test.1" in releases[0].task_ids
        assert "cub-test.2" in releases[0].task_ids
        assert "#123" in releases[0].task_ids

    def test_parse_changelog_read_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test handling of file read errors."""
        changelog_path = tmp_path / "CHANGELOG.md"
        changelog_path.write_text("# Changelog")

        # Mock read_text to raise an exception
        def mock_read_text(*args: object, **kwargs: object) -> str:
            raise PermissionError("Access denied")

        monkeypatch.setattr(Path, "read_text", mock_read_text)
        parser = ChangelogParser(changelog_path)

        releases = parser.parse()

        assert len(releases) == 0
        assert "Failed to read CHANGELOG" in caplog.text

    def test_task_in_multiple_releases(self, tmp_changelog: Path) -> None:
        """Test task appearing in multiple releases (returns first one)."""
        changelog_content = """# Changelog

## [2.0.0] - 2026-01-24

- Mentioned cub-test.1 again

---

## [1.0.0] - 2026-01-23

- First release of cub-test.1
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        release = parser.get_task_release("cub-test.1")

        # Should return the first release (most recent)
        assert release is not None
        assert release.version == "2.0.0"

    def test_parse_changelog_with_subsections(self, tmp_changelog: Path) -> None:
        """Test parsing changelog with nested subsections."""
        changelog_content = """# Changelog

## [1.0.0] - 2026-01-23

### Added

#### Core Features

- Feature A (cub-a.1)
- Feature B (cub-b.2)

#### Documentation

- Updated README (#123)

### Fixed

- Bug fix (cub-fix.1)
"""
        tmp_changelog.write_text(changelog_content)
        parser = ChangelogParser(tmp_changelog)

        releases = parser.parse()

        assert len(releases) == 1
        release = releases[0]
        assert "cub-a.1" in release.task_ids
        assert "cub-b.2" in release.task_ids
        assert "#123" in release.task_ids
        assert "cub-fix.1" in release.task_ids
