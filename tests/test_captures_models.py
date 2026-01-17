"""
Unit tests for capture data models.

Tests Capture model validation, serialization, and frontmatter parsing.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from cub.core.captures import Capture, CaptureSource, CaptureStatus


class TestCaptureSource:
    """Test CaptureSource enum."""

    def test_source_cli(self) -> None:
        """Test CLI source."""
        assert CaptureSource.CLI.value == "cli"

    def test_source_pipe(self) -> None:
        """Test PIPE source."""
        assert CaptureSource.PIPE.value == "pipe"

    def test_source_interactive(self) -> None:
        """Test INTERACTIVE source."""
        assert CaptureSource.INTERACTIVE.value == "interactive"

    def test_source_manual(self) -> None:
        """Test MANUAL source."""
        assert CaptureSource.MANUAL.value == "manual"


class TestCaptureStatus:
    """Test CaptureStatus enum."""

    def test_status_active(self) -> None:
        """Test ACTIVE status."""
        assert CaptureStatus.ACTIVE.value == "active"

    def test_status_archived(self) -> None:
        """Test ARCHIVED status."""
        assert CaptureStatus.ARCHIVED.value == "archived"


class TestCaptureCreation:
    """Test Capture model creation and validation."""

    def test_minimal_capture(self) -> None:
        """Test creating a capture with minimal required fields."""
        capture = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0),
            title="Test idea",
        )
        assert capture.id == "cap-001"
        assert capture.title == "Test idea"
        assert capture.status == CaptureStatus.ACTIVE
        assert capture.source == CaptureSource.CLI
        assert capture.tags == []
        assert capture.priority is None

    def test_full_capture(self) -> None:
        """Test creating a capture with all fields."""
        now = datetime(2026, 1, 16, 14, 32, 0)
        capture = Capture(
            id="cap-002",
            created=now,
            title="Important idea",
            tags=["feature", "urgent"],
            source=CaptureSource.INTERACTIVE,
            status=CaptureStatus.ACTIVE,
            priority=1,
        )
        assert capture.id == "cap-002"
        assert capture.created == now
        assert capture.title == "Important idea"
        assert capture.tags == ["feature", "urgent"]
        assert capture.source == CaptureSource.INTERACTIVE
        assert capture.status == CaptureStatus.ACTIVE
        assert capture.priority == 1

    def test_invalid_id_format(self) -> None:
        """Test that invalid ID format is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Capture(
                id="invalid-001",
                created=datetime.now(),
                title="Test",
            )
        assert "cap-" in str(exc_info.value)

    def test_invalid_id_no_digits(self) -> None:
        """Test that ID without digits is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Capture(
                id="cap-abc",
                created=datetime.now(),
                title="Test",
            )
        assert "digit" in str(exc_info.value).lower()

    def test_id_with_leading_zeros(self) -> None:
        """Test that ID with leading zeros is accepted."""
        capture = Capture(
            id="cap-001",
            created=datetime.now(),
            title="Test",
        )
        assert capture.id == "cap-001"

    def test_id_with_large_number(self) -> None:
        """Test that ID with large number is accepted."""
        capture = Capture(
            id="cap-99999",
            created=datetime.now(),
            title="Test",
        )
        assert capture.id == "cap-99999"

    def test_empty_title_rejected(self) -> None:
        """Test that empty title is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Capture(
                id="cap-001",
                created=datetime.now(),
                title="",
            )
        assert "at least 1 character" in str(exc_info.value).lower()

    def test_invalid_priority(self) -> None:
        """Test that negative priority is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Capture(
                id="cap-001",
                created=datetime.now(),
                title="Test",
                priority=0,  # Must be >= 1
            )
        assert "greater than or equal to 1" in str(exc_info.value).lower()


class TestFrontmatterSerialization:
    """Test frontmatter dict serialization."""

    def test_minimal_frontmatter(self) -> None:
        """Test frontmatter output for minimal capture."""
        capture = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0),
            title="Test idea",
        )
        frontmatter = capture.to_frontmatter_dict()

        assert frontmatter["id"] == "cap-001"
        assert frontmatter["created"] == "2026-01-16T14:32:00"
        assert frontmatter["title"] == "Test idea"
        # Optional fields should not be in output if not set
        assert "tags" not in frontmatter
        assert "source" not in frontmatter
        assert "status" not in frontmatter
        assert "priority" not in frontmatter

    def test_full_frontmatter(self) -> None:
        """Test frontmatter output for capture with all fields."""
        capture = Capture(
            id="cap-002",
            created=datetime(2026, 1, 16, 14, 32, 0),
            title="Important idea",
            tags=["feature", "urgent"],
            source=CaptureSource.INTERACTIVE,
            status=CaptureStatus.ARCHIVED,
            priority=1,
        )
        frontmatter = capture.to_frontmatter_dict()

        assert frontmatter["id"] == "cap-002"
        assert frontmatter["title"] == "Important idea"
        assert frontmatter["tags"] == ["feature", "urgent"]
        assert frontmatter["source"] == "interactive"
        assert frontmatter["status"] == "archived"
        assert frontmatter["priority"] == 1

    def test_frontmatter_omits_defaults(self) -> None:
        """Test that default values are omitted from frontmatter."""
        capture = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0),
            title="Test",
            source=CaptureSource.CLI,  # Default
            status=CaptureStatus.ACTIVE,  # Default
        )
        frontmatter = capture.to_frontmatter_dict()

        # Default values should be omitted
        assert "source" not in frontmatter
        assert "status" not in frontmatter

    def test_frontmatter_empty_tags_omitted(self) -> None:
        """Test that empty tags list is omitted."""
        capture = Capture(
            id="cap-001",
            created=datetime.now(),
            title="Test",
            tags=[],
        )
        frontmatter = capture.to_frontmatter_dict()
        assert "tags" not in frontmatter


class TestFrontmatterParsing:
    """Test parsing from frontmatter dict."""

    def test_parse_minimal_frontmatter(self) -> None:
        """Test parsing minimal frontmatter."""
        data = {
            "id": "cap-001",
            "created": "2026-01-16T14:32:00",
            "title": "Test idea",
        }
        capture = Capture.from_frontmatter_dict(data)

        assert capture.id == "cap-001"
        assert capture.created == datetime(2026, 1, 16, 14, 32, 0)
        assert capture.title == "Test idea"
        assert capture.status == CaptureStatus.ACTIVE
        assert capture.source == CaptureSource.CLI
        assert capture.tags == []
        assert capture.priority is None

    def test_parse_full_frontmatter(self) -> None:
        """Test parsing full frontmatter."""
        data = {
            "id": "cap-002",
            "created": "2026-01-16T14:32:00",
            "title": "Important idea",
            "tags": ["feature", "urgent"],
            "source": "interactive",
            "status": "archived",
            "priority": 2,
        }
        capture = Capture.from_frontmatter_dict(data)

        assert capture.id == "cap-002"
        assert capture.title == "Important idea"
        assert capture.tags == ["feature", "urgent"]
        assert capture.source == CaptureSource.INTERACTIVE
        assert capture.status == CaptureStatus.ARCHIVED
        assert capture.priority == 2

    def test_parse_missing_required_field(self) -> None:
        """Test that missing required field raises error."""
        data = {
            "created": "2026-01-16T14:32:00",
            "title": "Test",
        }
        with pytest.raises(ValueError, match="'id' must be a string"):
            Capture.from_frontmatter_dict(data)

    def test_parse_invalid_created_timestamp(self) -> None:
        """Test that invalid timestamp raises error."""
        data = {
            "id": "cap-001",
            "created": "not-a-timestamp",
            "title": "Test",
        }
        with pytest.raises(ValueError, match="Invalid 'created' timestamp"):
            Capture.from_frontmatter_dict(data)

    def test_parse_missing_created_field(self) -> None:
        """Test that missing created field raises error."""
        data = {
            "id": "cap-001",
            "title": "Test",
        }
        with pytest.raises(ValueError, match="'created' field is required"):
            Capture.from_frontmatter_dict(data)

    def test_parse_string_tags_converted_to_list(self) -> None:
        """Test that string tag is converted to list."""
        data = {
            "id": "cap-001",
            "created": "2026-01-16T14:32:00",
            "title": "Test",
            "tags": "feature",
        }
        capture = Capture.from_frontmatter_dict(data)
        assert capture.tags == ["feature"]

    def test_parse_invalid_source(self) -> None:
        """Test that invalid source value raises error."""
        data = {
            "id": "cap-001",
            "created": "2026-01-16T14:32:00",
            "title": "Test",
            "source": "invalid_source",
        }
        with pytest.raises(ValueError, match="Invalid 'source' value"):
            Capture.from_frontmatter_dict(data)

    def test_parse_invalid_status(self) -> None:
        """Test that invalid status value raises error."""
        data = {
            "id": "cap-001",
            "created": "2026-01-16T14:32:00",
            "title": "Test",
            "status": "invalid_status",
        }
        with pytest.raises(ValueError, match="Invalid 'status' value"):
            Capture.from_frontmatter_dict(data)

    def test_parse_string_priority_converted_to_int(self) -> None:
        """Test that string priority is converted to int."""
        data = {
            "id": "cap-001",
            "created": "2026-01-16T14:32:00",
            "title": "Test",
            "priority": "1",
        }
        capture = Capture.from_frontmatter_dict(data)
        assert capture.priority == 1
        assert isinstance(capture.priority, int)

    def test_parse_invalid_priority(self) -> None:
        """Test that invalid priority value raises error."""
        data = {
            "id": "cap-001",
            "created": "2026-01-16T14:32:00",
            "title": "Test",
            "priority": "not-a-number",
        }
        with pytest.raises(ValueError, match="Invalid 'priority' value"):
            Capture.from_frontmatter_dict(data)

    def test_parse_datetime_object_created(self) -> None:
        """Test parsing when created is already a datetime object."""
        now = datetime(2026, 1, 16, 14, 32, 0)
        data = {
            "id": "cap-001",
            "created": now,
            "title": "Test",
        }
        capture = Capture.from_frontmatter_dict(data)
        assert capture.created == now


class TestRoundTrip:
    """Test serialization and deserialization round-trips."""

    def test_roundtrip_minimal(self) -> None:
        """Test round-trip with minimal capture."""
        original = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0),
            title="Test idea",
        )
        frontmatter = original.to_frontmatter_dict()
        restored = Capture.from_frontmatter_dict(frontmatter)

        assert restored.id == original.id
        assert restored.created == original.created
        assert restored.title == original.title
        assert restored.tags == original.tags
        assert restored.source == original.source
        assert restored.status == original.status
        assert restored.priority == original.priority

    def test_roundtrip_full(self) -> None:
        """Test round-trip with all fields."""
        original = Capture(
            id="cap-002",
            created=datetime(2026, 1, 16, 14, 32, 0),
            title="Important idea",
            tags=["feature", "urgent"],
            source=CaptureSource.INTERACTIVE,
            status=CaptureStatus.ARCHIVED,
            priority=1,
        )
        frontmatter = original.to_frontmatter_dict()
        restored = Capture.from_frontmatter_dict(frontmatter)

        assert restored.id == original.id
        assert restored.created == original.created
        assert restored.title == original.title
        assert restored.tags == original.tags
        assert restored.source == original.source
        assert restored.status == original.status
        assert restored.priority == original.priority
