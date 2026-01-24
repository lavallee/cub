"""
Tests for Toolsmith models (Tool, ToolType, Catalog).

Tests cover:
- Enum values and basic model instantiation
- Field validation (ID format, source format, timestamps)
- Serialization/deserialization (JSON, dict)
- Edge cases and error conditions
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cub.core.toolsmith.models import Catalog, Tool, ToolType


class TestToolType:
    """Tests for ToolType enum."""

    def test_tool_type_values(self) -> None:
        """Verify ToolType enum has required values."""
        assert ToolType.MCP_SERVER.value == "mcp_server"
        assert ToolType.SKILL.value == "skill"

    def test_tool_type_members(self) -> None:
        """Verify all expected enum members exist."""
        members = {e.name for e in ToolType}
        assert members == {"MCP_SERVER", "SKILL"}


class TestToolBasics:
    """Tests for basic Tool model instantiation."""

    def test_tool_creation_minimal(self) -> None:
        """Create Tool with minimal required fields."""
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="JavaScript linter",
        )
        assert tool.id == "npm:eslint"
        assert tool.name == "ESLint"
        assert tool.source == "npm"
        assert tool.tool_type == ToolType.MCP_SERVER
        assert tool.install_hint == ""
        assert tool.tags == []
        assert tool.last_seen is None

    def test_tool_creation_with_optional_fields(self) -> None:
        """Create Tool with all optional fields."""
        now = datetime.now(timezone.utc)
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.SKILL,
            description="JavaScript linter",
            install_hint="npm install eslint",
            tags=["linter", "javascript"],
            last_seen=now,
        )
        assert tool.install_hint == "npm install eslint"
        assert tool.tags == ["linter", "javascript"]
        assert tool.last_seen == now

    def test_tool_with_multiple_sources(self) -> None:
        """Create tools from different sources."""
        sources = [
            ("npm:eslint", "npm"),
            ("github:opensearch-project/opensearch", "github"),
            ("pypi:black", "pypi"),
            ("custom:my-tool", "custom"),
        ]
        for tool_id, source in sources:
            tool = Tool(
                id=tool_id,
                name="Test Tool",
                source=source,
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="Test",
            )
            assert tool.source == source


class TestToolIDValidation:
    """Tests for Tool ID validation."""

    def test_id_valid_formats(self) -> None:
        """Valid ID formats pass validation."""
        valid_ids = [
            "npm:eslint",
            "npm:my-package",
            "npm:my_package",
            "npm:MyPackage",
            "github:owner/repo",
            "pypi:black",
            "custom:tool-123",
        ]
        for valid_id in valid_ids:
            tool = Tool(
                id=valid_id,
                name="Test",
                source=valid_id.split(":")[0],
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="Test",
            )
            assert tool.id == valid_id

    def test_id_missing_separator(self) -> None:
        """ID without ':' separator raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            Tool(
                id="eslint",
                name="Test",
                source="npm",
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="Test",
            )
        assert "':' separator" in str(exc_info.value)

    def test_id_multiple_separators(self) -> None:
        """ID with multiple ':' raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            Tool(
                id="npm:my:package",
                name="Test",
                source="npm",
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="Test",
            )
        assert "exactly one ':' separator" in str(exc_info.value)

    def test_id_empty_source(self) -> None:
        """ID with empty source part raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            Tool(
                id=":eslint",
                name="Test",
                source="npm",
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="Test",
            )
        assert "Invalid source" in str(exc_info.value)

    def test_id_empty_slug(self) -> None:
        """ID with empty slug part raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            Tool(
                id="npm:",
                name="Test",
                source="npm",
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="Test",
            )
        assert "empty" in str(exc_info.value).lower()

    def test_id_invalid_characters(self) -> None:
        """ID with invalid characters raises ValueError."""
        invalid_ids = [
            "npm:eslint!",  # ! special char
            "npm:eslint#config",  # # special char
        ]
        for invalid_id in invalid_ids:
            with pytest.raises(ValidationError):
                Tool(
                    id=invalid_id,
                    name="Test",
                    source=invalid_id.split(":")[0],
                    source_url="http://example.com",
                    tool_type=ToolType.MCP_SERVER,
                    description="Test",
                )


class TestToolSourceValidation:
    """Tests for Tool source field validation."""

    def test_source_valid_formats(self) -> None:
        """Valid source formats pass validation."""
        valid_sources = ["npm", "github", "pypi", "custom", "my-source", "my_source"]
        for source in valid_sources:
            tool = Tool(
                id=f"{source}:tool",
                name="Test",
                source=source,
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="Test",
            )
            assert tool.source == source

    def test_source_empty_raises(self) -> None:
        """Empty source raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Tool(
                id="npm:tool",
                name="Test",
                source="",
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="Test",
            )
        assert "empty" in str(exc_info.value).lower()

    def test_source_invalid_chars_raises(self) -> None:
        """Source with invalid characters raises ValidationError."""
        invalid_sources = ["npm!", "my source", "source@org", "source/path"]
        for source in invalid_sources:
            with pytest.raises(ValidationError):
                Tool(
                    id="npm:tool",
                    name="Test",
                    source=source,
                    source_url="http://example.com",
                    tool_type=ToolType.MCP_SERVER,
                    description="Test",
                )


class TestToolTimestamps:
    """Tests for Tool timestamp handling."""

    def test_last_seen_none(self) -> None:
        """last_seen defaults to None."""
        tool = Tool(
            id="npm:tool",
            name="Test",
            source="npm",
            source_url="http://example.com",
            tool_type=ToolType.MCP_SERVER,
            description="Test",
        )
        assert tool.last_seen is None

    def test_last_seen_datetime(self) -> None:
        """last_seen accepts datetime objects."""
        now = datetime.now(timezone.utc)
        tool = Tool(
            id="npm:tool",
            name="Test",
            source="npm",
            source_url="http://example.com",
            tool_type=ToolType.MCP_SERVER,
            description="Test",
            last_seen=now,
        )
        assert tool.last_seen == now
        assert tool.last_seen.tzinfo is not None

    def test_last_seen_naive_datetime_becomes_utc(self) -> None:
        """Naive datetime is converted to UTC."""
        naive_dt = datetime(2026, 1, 23, 12, 0, 0)
        tool = Tool(
            id="npm:tool",
            name="Test",
            source="npm",
            source_url="http://example.com",
            tool_type=ToolType.MCP_SERVER,
            description="Test",
            last_seen=naive_dt,
        )
        assert tool.last_seen.tzinfo == timezone.utc
        assert tool.last_seen.year == 2026

    def test_last_seen_iso_string(self) -> None:
        """last_seen accepts ISO 8601 strings."""
        iso_str = "2026-01-23T12:30:45Z"
        tool = Tool(
            id="npm:tool",
            name="Test",
            source="npm",
            source_url="http://example.com",
            tool_type=ToolType.MCP_SERVER,
            description="Test",
            last_seen=iso_str,
        )
        assert tool.last_seen is not None
        assert tool.last_seen.year == 2026

    def test_last_seen_invalid_string_raises(self) -> None:
        """Invalid ISO string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Tool(
                id="npm:tool",
                name="Test",
                source="npm",
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="Test",
                last_seen="not-a-date",
            )
        assert "timestamp format" in str(exc_info.value).lower()


class TestCatalogBasics:
    """Tests for basic Catalog model instantiation."""

    def test_catalog_minimal(self) -> None:
        """Create Catalog with minimal fields."""
        catalog = Catalog(version="1.0.0")
        assert catalog.version == "1.0.0"
        assert catalog.tools == []
        assert catalog.last_sync is None
        assert catalog.sources_synced == []

    def test_catalog_with_tools(self) -> None:
        """Create Catalog with tools."""
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
        )
        catalog = Catalog(version="1.0.0", tools=[tool])
        assert len(catalog.tools) == 1
        assert catalog.tools[0].id == "npm:eslint"

    def test_catalog_with_all_fields(self) -> None:
        """Create Catalog with all fields."""
        now = datetime.now(timezone.utc)
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
        )
        catalog = Catalog(
            version="1.2.3",
            tools=[tool],
            last_sync=now,
            sources_synced=["npm", "github"],
        )
        assert catalog.version == "1.2.3"
        assert len(catalog.tools) == 1
        assert catalog.last_sync == now
        assert catalog.sources_synced == ["npm", "github"]


class TestCatalogVersionValidation:
    """Tests for Catalog version validation."""

    def test_version_valid_formats(self) -> None:
        """Valid semantic versions pass validation."""
        valid_versions = [
            "1.0.0",
            "0.0.1",
            "10.20.30",
            "1.0.0-alpha",
            "1.0.0-beta.1",
            "1.0.0-rc.1",
        ]
        for version in valid_versions:
            catalog = Catalog(version=version)
            assert catalog.version == version

    def test_version_invalid_format_raises(self) -> None:
        """Invalid version formats raise ValidationError."""
        invalid_versions = [
            "1.0",  # Missing patch
            "v1.0.0",  # v prefix
            "1",  # Too short
            "latest",  # Non-numeric
            "1.0.0.0",  # Too many parts
        ]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                Catalog(version=version)

    def test_version_empty_raises(self) -> None:
        """Empty version raises ValidationError."""
        with pytest.raises(ValidationError):
            Catalog(version="")


class TestCatalogTimestamps:
    """Tests for Catalog timestamp handling."""

    def test_last_sync_none(self) -> None:
        """last_sync defaults to None."""
        catalog = Catalog(version="1.0.0")
        assert catalog.last_sync is None

    def test_last_sync_datetime(self) -> None:
        """last_sync accepts datetime objects."""
        now = datetime.now(timezone.utc)
        catalog = Catalog(version="1.0.0", last_sync=now)
        assert catalog.last_sync == now

    def test_last_sync_naive_becomes_utc(self) -> None:
        """Naive datetime is converted to UTC."""
        naive_dt = datetime(2026, 1, 23, 12, 0, 0)
        catalog = Catalog(version="1.0.0", last_sync=naive_dt)
        assert catalog.last_sync.tzinfo == timezone.utc

    def test_last_sync_iso_string(self) -> None:
        """last_sync accepts ISO 8601 strings."""
        iso_str = "2026-01-23T14:30:00Z"
        catalog = Catalog(version="1.0.0", last_sync=iso_str)
        assert catalog.last_sync is not None
        assert catalog.last_sync.year == 2026


class TestCatalogSourcesValidation:
    """Tests for Catalog sources_synced validation."""

    def test_sources_synced_empty_default(self) -> None:
        """sources_synced defaults to empty list."""
        catalog = Catalog(version="1.0.0")
        assert catalog.sources_synced == []

    def test_sources_synced_list(self) -> None:
        """sources_synced accepts list of strings."""
        catalog = Catalog(
            version="1.0.0",
            sources_synced=["npm", "github", "pypi"],
        )
        assert catalog.sources_synced == ["npm", "github", "pypi"]

    def test_sources_synced_single_string_converted(self) -> None:
        """Single source string is converted to list."""
        catalog = Catalog(version="1.0.0", sources_synced="npm")  # type: ignore
        assert catalog.sources_synced == ["npm"]


class TestSerialization:
    """Tests for JSON serialization/deserialization."""

    def test_tool_model_dump(self) -> None:
        """Tool.model_dump() produces correct dict."""
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
            tags=["linter", "js"],
        )
        data = tool.model_dump()
        assert data["id"] == "npm:eslint"
        assert data["name"] == "ESLint"
        assert data["tool_type"] == "mcp_server"
        assert data["tags"] == ["linter", "js"]

    def test_tool_model_dump_json(self) -> None:
        """Tool.model_dump_json() produces valid JSON."""
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
        )
        json_str = tool.model_dump_json()
        assert isinstance(json_str, str)
        assert "npm:eslint" in json_str
        assert "mcp_server" in json_str

    def test_tool_model_validate(self) -> None:
        """Tool.model_validate() restores from dict."""
        original = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
        )
        data = original.model_dump()
        restored = Tool.model_validate(data)
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.tool_type == original.tool_type

    def test_tool_model_validate_json(self) -> None:
        """Tool.model_validate_json() restores from JSON string."""
        original = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
        )
        json_str = original.model_dump_json()
        restored = Tool.model_validate_json(json_str)
        assert restored.id == original.id

    def test_catalog_roundtrip(self) -> None:
        """Catalog serialization/deserialization roundtrip works."""
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
            tags=["linter"],
        )
        original = Catalog(
            version="1.0.0",
            tools=[tool],
            sources_synced=["npm"],
        )
        json_str = original.model_dump_json()
        restored = Catalog.model_validate_json(json_str)
        assert restored.version == original.version
        assert len(restored.tools) == 1
        assert restored.tools[0].id == "npm:eslint"
        assert restored.sources_synced == ["npm"]


class TestFieldValidation:
    """Tests for required field validation."""

    def test_tool_missing_required_fields(self) -> None:
        """Tool requires all mandatory fields."""
        # Test missing id
        with pytest.raises(ValidationError):
            Tool(
                id=None,  # type: ignore
                name="name",
                source="npm",
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="desc",
            )
        # Test missing name
        with pytest.raises(ValidationError):
            Tool(
                id="npm:tool",
                name=None,  # type: ignore
                source="npm",
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="desc",
            )
        # Test missing source
        with pytest.raises(ValidationError):
            Tool(
                id="npm:tool",
                name="name",
                source=None,  # type: ignore
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description="desc",
            )
        # Test missing description
        with pytest.raises(ValidationError):
            Tool(
                id="npm:tool",
                name="name",
                source="npm",
                source_url="http://example.com",
                tool_type=ToolType.MCP_SERVER,
                description=None,  # type: ignore
            )

    def test_catalog_missing_version_raises(self) -> None:
        """Catalog requires version."""
        with pytest.raises(ValidationError):
            Catalog()  # type: ignore


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_tool_empty_strings_for_optional_fields(self) -> None:
        """Empty strings for optional fields are accepted."""
        tool = Tool(
            id="npm:tool",
            name="Test",
            source="npm",
            source_url="http://example.com",
            tool_type=ToolType.MCP_SERVER,
            description="Test",
            install_hint="",
        )
        assert tool.install_hint == ""

    def test_tool_empty_tags_list(self) -> None:
        """Empty tags list is valid."""
        tool = Tool(
            id="npm:tool",
            name="Test",
            source="npm",
            source_url="http://example.com",
            tool_type=ToolType.MCP_SERVER,
            description="Test",
            tags=[],
        )
        assert tool.tags == []

    def test_catalog_many_tools(self) -> None:
        """Catalog can hold many tools."""
        tools = [
            Tool(
                id=f"npm:tool{i}",
                name=f"Tool {i}",
                source="npm",
                source_url=f"http://example.com/{i}",
                tool_type=ToolType.MCP_SERVER,
                description=f"Tool {i}",
            )
            for i in range(100)
        ]
        catalog = Catalog(version="1.0.0", tools=tools)
        assert len(catalog.tools) == 100

    def test_tool_long_description(self) -> None:
        """Tool with very long description is accepted."""
        long_desc = "x" * 10000
        tool = Tool(
            id="npm:tool",
            name="Test",
            source="npm",
            source_url="http://example.com",
            tool_type=ToolType.MCP_SERVER,
            description=long_desc,
        )
        assert len(tool.description) == 10000
