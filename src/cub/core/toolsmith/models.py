"""
Tool and catalog models for Toolsmith.

Defines Pydantic models for tools (MCP servers, skills), catalogs,
and related metadata. Provides validation and serialization for
the tool registry system.

Example:
    >>> from cub.core.toolsmith.models import ToolType, Tool, Catalog
    >>> from datetime import datetime, timezone
    >>>
    >>> tool = Tool(
    ...     id="npm:eslint",
    ...     name="ESLint",
    ...     source="npm",
    ...     source_url="https://www.npmjs.com/package/eslint",
    ...     tool_type=ToolType.MCP_SERVER,
    ...     description="JavaScript linter",
    ...     tags=["linter", "javascript"]
    ... )
    >>> tool.id
    'npm:eslint'
    >>>
    >>> catalog = Catalog(version="1.0.0", tools=[tool])
    >>> json_str = catalog.model_dump_json()
    >>> loaded = Catalog.model_validate_json(json_str)
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SyncResult(BaseModel):
    """
    Result of a catalog sync operation.

    Reports how many tools were added or updated during a sync,
    and captures any errors that occurred during the process.

    Attributes:
        tools_added: Number of new tools added to the catalog
        tools_updated: Number of existing tools updated
        errors: List of error messages from failed sources
    """

    tools_added: int = Field(default=0, description="Number of new tools added")
    tools_updated: int = Field(default=0, description="Number of existing tools updated")
    errors: list[str] = Field(
        default_factory=list,
        description="List of error messages from failed sources",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )


class CatalogStats(BaseModel):
    """
    Statistics about the tool catalog.

    Provides summary information about the catalog contents,
    including totals, breakdowns by source and type, and sync timestamps.

    Attributes:
        total_tools: Total number of tools in the catalog
        by_source: Dictionary mapping source names to tool counts
        by_type: Dictionary mapping tool types to tool counts
        last_sync: Timestamp of last catalog sync (ISO 8601)
        sources_synced: List of sources that have been synced
    """

    total_tools: int = Field(default=0, description="Total number of tools in catalog")
    by_source: dict[str, int] = Field(
        default_factory=dict,
        description="Tool counts by source name",
    )
    by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Tool counts by tool type",
    )
    last_sync: datetime | None = Field(
        default=None,
        description="Timestamp of last catalog sync (ISO 8601)",
    )
    sources_synced: list[str] = Field(
        default_factory=list,
        description="List of sources that have been synced",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )


class ToolType(str, Enum):
    """Tool type enumeration."""

    MCP_SERVER = "mcp_server"
    SKILL = "skill"


class Tool(BaseModel):
    """
    A tool representing an MCP server, skill, or extension.

    Tools are cataloged entities that can be discovered, installed,
    and integrated into AI workflows. They have metadata, installation
    hints, and usage tags.

    Attributes:
        id: Unique tool identifier in format "{source}:{slug}"
             Example: "npm:eslint", "custom:my-tool"
        name: Human-readable tool name
        source: Package source (e.g., "npm", "github", "pypi", "custom")
        source_url: URL to the tool's source/documentation
        tool_type: Whether this is an MCP_SERVER or SKILL
        description: Brief description of what the tool does
        install_hint: Installation instructions or CLI command
        tags: Array of tags for categorization and discovery
        last_seen: Timestamp when tool was last verified/updated
    """

    # Required fields
    id: str = Field(..., description='Unique identifier in format "{source}:{slug}"')
    name: str = Field(..., min_length=1, description="Human-readable tool name")
    source: str = Field(..., min_length=1, description="Package source (npm, github, etc.)")
    source_url: str = Field(..., min_length=1, description="URL to tool source/documentation")
    tool_type: ToolType = Field(..., description="Tool type (MCP_SERVER or SKILL)")
    description: str = Field(..., min_length=1, description="Brief description of the tool")

    # Optional fields
    install_hint: str = Field(
        default="",
        description="Installation instructions or CLI command",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Array of tags for categorization and discovery",
    )
    last_seen: datetime | None = Field(
        default=None,
        description="Timestamp when tool was last verified/updated (ISO 8601)",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """
        Validate ID format: {source}:{slug}.

        Args:
            v: The ID value to validate

        Returns:
            The validated ID

        Raises:
            ValueError: If ID format is invalid
        """
        if not isinstance(v, str):
            raise ValueError("ID must be a string")
        if ":" not in v:
            raise ValueError("ID must contain ':' separator (format: {source}:{slug})")
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("ID must have exactly one ':' separator")
        source, slug = parts
        if not source or not source.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                f"Invalid source: '{source}' (alphanumeric, hyphens, underscores allowed)"
            )
        # Slug can contain common identifier characters.
        # We accept:
        # - alphanumeric
        # - hyphens/underscores
        # - forward slashes (namespace/tool)
        # - '@' (scoped namespaces, e.g. @org/tool)
        # - '.' (common in repo/tool ids)
        if not slug:
            raise ValueError("Slug cannot be empty")
        valid_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/@."
        )
        if not all(c in valid_chars for c in slug):
            msg = (
                f"Invalid slug: '{slug}' (alphanumeric, hyphens, underscores, "
                "forward slashes, '@', '.' allowed)"
            )
            raise ValueError(msg)
        return v

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """
        Validate source is non-empty alphanumeric.

        Args:
            v: The source value to validate

        Returns:
            The validated source

        Raises:
            ValueError: If source is empty or contains invalid characters
        """
        if not isinstance(v, str):
            raise ValueError("Source must be a string")
        if not v:
            raise ValueError("Source cannot be empty")
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"Invalid source: '{v}' (alphanumeric, hyphens, underscores allowed)")
        return v

    @field_validator("last_seen", mode="before")
    @classmethod
    def normalize_last_seen(cls, v: datetime | str | None) -> datetime | None:
        """
        Normalize last_seen to timezone-aware datetime.

        Args:
            v: The last_seen value (datetime, ISO string, or None)

        Returns:
            Timezone-aware datetime or None

        Raises:
            ValueError: If datetime string cannot be parsed
        """
        if v is None:
            return None
        if isinstance(v, datetime):
            # Ensure timezone-aware (treat naive as UTC)
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v)
                # Ensure timezone-aware (treat naive as UTC)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError as e:
                raise ValueError(f"Invalid 'last_seen' timestamp format: {v}") from e
        raise ValueError(f"Invalid 'last_seen' type: {type(v)}")


class Catalog(BaseModel):
    """
    A catalog of tools.

    Catalogs group tools with metadata about the catalog itself,
    including version, sync timestamps, and which sources have been
    synchronized.

    Attributes:
        version: Semantic version of the catalog format
        last_sync: Timestamp of last catalog sync (ISO 8601)
        sources_synced: List of tool sources that have been synced
        tools: Array of Tool entries in the catalog
    """

    # Required fields
    version: str = Field(..., description="Semantic version of catalog format")
    tools: list[Tool] = Field(
        default_factory=list,
        description="Array of Tool entries in the catalog",
    )

    # Optional fields
    last_sync: datetime | None = Field(
        default=None,
        description="Timestamp of last catalog sync (ISO 8601)",
    )
    sources_synced: list[str] = Field(
        default_factory=list,
        description="List of tool sources that have been synced",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @field_validator("version", mode="before")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """
        Validate version format (semantic versioning).

        Args:
            v: The version string to validate

        Returns:
            The validated version

        Raises:
            ValueError: If version format is invalid
        """
        if not isinstance(v, str):
            raise ValueError("Version must be a string")
        if not v:
            raise ValueError("Version cannot be empty")
        # Allow common semantic versioning formats: X.Y.Z, X.Y.Z-prerelease, etc.
        import re

        if not re.match(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$", v):
            raise ValueError(
                f"Invalid version format: '{v}' (expected semantic version like 1.0.0)"
            )
        return v

    @field_validator("last_sync", mode="before")
    @classmethod
    def normalize_last_sync(cls, v: datetime | str | None) -> datetime | None:
        """
        Normalize last_sync to timezone-aware datetime.

        Args:
            v: The last_sync value (datetime, ISO string, or None)

        Returns:
            Timezone-aware datetime or None

        Raises:
            ValueError: If datetime string cannot be parsed
        """
        if v is None:
            return None
        if isinstance(v, datetime):
            # Ensure timezone-aware (treat naive as UTC)
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v)
                # Ensure timezone-aware (treat naive as UTC)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError as e:
                raise ValueError(f"Invalid 'last_sync' timestamp format: {v}") from e
        raise ValueError(f"Invalid 'last_sync' type: {type(v)}")

    @field_validator("sources_synced", mode="before")
    @classmethod
    def normalize_sources_synced(cls, v: list[str] | str | None) -> list[str]:
        """
        Normalize sources_synced to a list of strings.

        Args:
            v: The sources_synced value (list, string, or None)

        Returns:
            List of source names

        Raises:
            ValueError: If value cannot be converted to list
        """
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return v
        raise ValueError(f"Invalid 'sources_synced' type: {type(v)}")
