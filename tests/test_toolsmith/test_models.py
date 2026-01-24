"""Tests for Toolsmith data models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cub.core.toolsmith.models import Catalog, SyncResult, Tool, ToolType


class TestTool:
    """Tests for Tool model validation."""

    def test_valid_tool_creation(self) -> None:
        """Test creating a valid Tool object."""
        tool = Tool(
            id="smithery:filesystem",
            name="Filesystem MCP Server",
            source="smithery",
            source_url="https://smithery.ai/server/filesystem",
            tool_type=ToolType.MCP_SERVER,
            description="Access local filesystem",
        )
        assert tool.id == "smithery:filesystem"
        assert tool.name == "Filesystem MCP Server"
        assert tool.source == "smithery"
        assert tool.tool_type == ToolType.MCP_SERVER

    def test_id_validation_missing_separator(self) -> None:
        """Test that ID without ':' separator raises ValueError."""
        with pytest.raises(ValidationError, match="ID must contain ':' separator"):
            Tool(
                id="smithery-eslint",  # Missing ':'
                name="Filesystem",
                source="smithery",
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
            )

    def test_id_validation_multiple_separators(self) -> None:
        """Test that ID with multiple ':' separators raises ValueError."""
        with pytest.raises(ValidationError, match="exactly one ':' separator"):
            Tool(
                id="smithery:@scope:eslint",  # Multiple ':'
                name="Filesystem",
                source="smithery",
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
            )

    def test_id_validation_empty_source(self) -> None:
        """Test that ID with empty source raises ValueError."""
        with pytest.raises(ValidationError, match="Invalid source"):
            Tool(
                id=":eslint",  # Empty source
                name="Filesystem",
                source="smithery",
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
            )

    def test_id_validation_invalid_source_chars(self) -> None:
        """Test that ID with invalid source characters raises ValueError."""
        with pytest.raises(ValidationError, match="Invalid source"):
            Tool(
                id="smithery@:eslint",  # Invalid character '@' in source
                name="Filesystem",
                source="smithery",
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
            )

    def test_id_validation_empty_slug(self) -> None:
        """Test that ID with empty slug raises ValueError."""
        with pytest.raises(ValidationError, match="Slug cannot be empty"):
            Tool(
                id="smithery:",  # Empty slug
                name="Filesystem",
                source="smithery",
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
            )

    def test_id_validation_invalid_slug_chars(self) -> None:
        """Test that ID with invalid slug characters raises ValueError."""
        with pytest.raises(ValidationError, match="Invalid slug"):
            Tool(
                id="smithery:filesystem#latest",  # Invalid character '#' in slug
                name="Filesystem",
                source="smithery",
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
            )

    def test_id_validation_not_string(self) -> None:
        """Test that non-string ID raises ValidationError."""
        with pytest.raises(ValidationError, match="ID must be a string"):
            Tool(
                id=123,  # type: ignore[arg-type]
                name="Filesystem",
                source="smithery",
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
            )

    def test_source_validation_empty(self) -> None:
        """Test that empty source raises ValueError."""
        with pytest.raises(ValidationError, match="Source cannot be empty"):
            Tool(
                id="smithery:filesystem",
                name="Filesystem",
                source="",  # Empty source
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
            )

    def test_source_validation_invalid_chars(self) -> None:
        """Test that source with invalid characters raises ValueError."""
        with pytest.raises(ValidationError, match="Invalid source"):
            Tool(
                id="smithery:filesystem",
                name="Filesystem",
                source="smithery@registry",  # Invalid character '@'
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
            )

    def test_source_validation_not_string(self) -> None:
        """Test that non-string source raises ValidationError."""
        with pytest.raises(ValidationError, match="Source must be a string"):
            Tool(
                id="smithery:filesystem",
                name="Filesystem",
                source=123,  # type: ignore[arg-type]
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
            )

    def test_last_seen_string_conversion(self) -> None:
        """Test that last_seen string is converted to datetime."""
        tool = Tool(
            id="smithery:filesystem",
            name="Filesystem",
            source="smithery",
            source_url="https://smitheryjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Access local filesystem",
            last_seen="2024-01-01T12:00:00+00:00",
        )
        assert isinstance(tool.last_seen, datetime)
        assert tool.last_seen.tzinfo is not None

    def test_last_seen_naive_datetime_becomes_utc(self) -> None:
        """Test that naive datetime is treated as UTC."""
        tool = Tool(
            id="smithery:filesystem",
            name="Filesystem",
            source="smithery",
            source_url="https://smitheryjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Access local filesystem",
            last_seen=datetime(2024, 1, 1, 12, 0, 0),  # Naive datetime
        )
        assert tool.last_seen.tzinfo == timezone.utc

    def test_last_seen_invalid_string_format(self) -> None:
        """Test that invalid last_seen string format raises ValueError."""
        with pytest.raises(ValidationError, match="Invalid 'last_seen' timestamp format"):
            Tool(
                id="smithery:filesystem",
                name="Filesystem",
                source="smithery",
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
                last_seen="not-a-datetime",
            )

    def test_last_seen_invalid_type(self) -> None:
        """Test that invalid last_seen type raises ValueError."""
        with pytest.raises(ValidationError, match="Invalid 'last_seen' type"):
            Tool(
                id="smithery:filesystem",
                name="Filesystem",
                source="smithery",
                source_url="https://smitheryjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Access local filesystem",
                last_seen=12345,  # type: ignore[arg-type]
            )


class TestCatalog:
    """Tests for Catalog model validation."""

    def test_valid_catalog_creation(self) -> None:
        """Test creating a valid Catalog object."""
        tool = Tool(
            id="smithery:filesystem",
            name="Filesystem",
            source="smithery",
            source_url="https://smitheryjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Access local filesystem",
        )
        catalog = Catalog(
            version="1.0.0",
            tools=[tool],
        )
        assert catalog.version == "1.0.0"
        assert len(catalog.tools) == 1

    def test_version_validation_empty(self) -> None:
        """Test that empty version raises ValueError."""
        with pytest.raises(ValidationError, match="Version cannot be empty"):
            Catalog(
                version="",
                tools=[],
            )

    def test_version_validation_not_string(self) -> None:
        """Test that non-string version raises ValidationError."""
        with pytest.raises(ValidationError, match="Version must be a string"):
            Catalog(
                version=1.0,  # type: ignore[arg-type]
                tools=[],
            )

    def test_version_validation_invalid_format(self) -> None:
        """Test that invalid semantic version format raises ValueError."""
        with pytest.raises(ValidationError, match="Invalid version format"):
            Catalog(
                version="v1.0",  # Missing patch version
                tools=[],
            )

    def test_last_sync_string_conversion(self) -> None:
        """Test that last_sync string is converted to datetime."""
        catalog = Catalog(
            version="1.0.0",
            tools=[],
            last_sync="2024-01-01T12:00:00+00:00",
        )
        assert isinstance(catalog.last_sync, datetime)
        assert catalog.last_sync.tzinfo is not None

    def test_last_sync_naive_datetime_becomes_utc(self) -> None:
        """Test that naive datetime is treated as UTC."""
        catalog = Catalog(
            version="1.0.0",
            tools=[],
            last_sync=datetime(2024, 1, 1, 12, 0, 0),  # Naive datetime
        )
        assert catalog.last_sync.tzinfo == timezone.utc

    def test_last_sync_invalid_string_format(self) -> None:
        """Test that invalid last_sync string format raises ValueError."""
        with pytest.raises(ValidationError, match="Invalid 'last_sync' timestamp format"):
            Catalog(
                version="1.0.0",
                tools=[],
                last_sync="not-a-datetime",
            )

    def test_last_sync_invalid_type(self) -> None:
        """Test that invalid last_sync type raises ValueError."""
        with pytest.raises(ValidationError, match="Invalid 'last_sync' type"):
            Catalog(
                version="1.0.0",
                tools=[],
                last_sync=12345,  # type: ignore[arg-type]
            )

    def test_sources_synced_string_conversion(self) -> None:
        """Test that sources_synced string is converted to list."""
        catalog = Catalog(
            version="1.0.0",
            tools=[],
            sources_synced="smithery",
        )
        assert catalog.sources_synced == ["smithery"]

    def test_sources_synced_list_preserved(self) -> None:
        """Test that sources_synced list is preserved."""
        catalog = Catalog(
            version="1.0.0",
            tools=[],
            sources_synced=["smithery", "pypi"],
        )
        assert catalog.sources_synced == ["smithery", "pypi"]

    def test_sources_synced_invalid_type(self) -> None:
        """Test that invalid sources_synced type raises ValueError."""
        with pytest.raises(ValidationError, match="Invalid 'sources_synced' type"):
            Catalog(
                version="1.0.0",
                tools=[],
                sources_synced=123,  # type: ignore[arg-type]
            )


class TestSyncResult:
    """Tests for SyncResult model."""

    def test_valid_sync_result(self) -> None:
        """Test creating a valid SyncResult object."""
        result = SyncResult(
            tools_added=5,
            tools_updated=3,
            errors=["Error 1", "Error 2"],
        )
        assert result.tools_added == 5
        assert result.tools_updated == 3
        assert len(result.errors) == 2

    def test_sync_result_defaults(self) -> None:
        """Test SyncResult with default values."""
        result = SyncResult(
            tools_added=0,
            tools_updated=0,
        )
        assert result.errors == []
