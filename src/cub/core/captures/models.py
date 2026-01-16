"""
Capture data models for cub.

Defines the Capture model representing ideas, notes, and observations
stored as Markdown files with YAML frontmatter. Captures are the raw
material for the vision-to-tasks pipeline.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CaptureSource(str, Enum):
    """How a capture was created."""

    CLI = "cli"
    PIPE = "pipe"
    INTERACTIVE = "interactive"
    MANUAL = "manual"


class CaptureStatus(str, Enum):
    """Capture status values."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class Capture(BaseModel):
    """
    A single capture (idea, note, observation).

    Captures are stored as Markdown files with YAML frontmatter and represent
    low-friction idea collection. They serve as raw material for the
    vision-to-tasks pipeline.

    Example:
        >>> capture = Capture(
        ...     id="cap-001",
        ...     created=datetime(2026, 1, 16, 14, 32, 0),
        ...     title="Parallel Clones Instead of Worktrees",
        ...     tags=["git", "workflow"],
        ...     source=CaptureSource.CLI,
        ...     status=CaptureStatus.ACTIVE
        ... )
        >>> capture.id
        'cap-001'
        >>> capture.status
        <CaptureStatus.ACTIVE: 'active'>
    """

    # Required fields
    id: str = Field(..., description="Unique capture identifier (e.g., 'cap-001')")
    created: datetime = Field(..., description="Creation timestamp (ISO 8601)")
    title: str = Field(..., min_length=1, description="Short capture title")

    # Optional fields with sensible defaults
    tags: list[str] = Field(
        default_factory=list,
        description="Array of tags for organization and discovery",
    )
    source: CaptureSource = Field(
        default=CaptureSource.CLI,
        description="How the capture was created",
    )
    status: CaptureStatus = Field(
        default=CaptureStatus.ACTIVE,
        description="Capture status (active or archived)",
    )
    priority: int | None = Field(
        default=None,
        description="Optional priority signal for later processing",
        ge=1,
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate ID format: cap-NNN where N is a digit."""
        if not isinstance(v, str):
            raise ValueError("ID must be a string")
        if not v.startswith("cap-"):
            raise ValueError("ID must start with 'cap-'")
        suffix = v[4:]  # Everything after 'cap-'
        if not suffix.isdigit():
            raise ValueError("ID must end with digits (format: cap-NNN)")
        if len(suffix) == 0:
            raise ValueError("ID must have at least one digit (format: cap-NNN)")
        return v

    def to_frontmatter_dict(self) -> dict[str, str | list[str] | int | None]:
        """
        Convert capture to frontmatter dictionary for serialization to YAML.

        Returns:
            Dictionary suitable for YAML frontmatter representation
        """
        frontmatter: dict[str, str | list[str] | int | None] = {
            "id": self.id,
            "created": self.created.isoformat(),
            "title": self.title,
        }

        # Include optional fields only if they have values
        if self.tags:
            frontmatter["tags"] = self.tags

        if self.source != CaptureSource.CLI:
            frontmatter["source"] = self.source.value

        if self.status != CaptureStatus.ACTIVE:
            frontmatter["status"] = self.status.value

        if self.priority is not None:
            frontmatter["priority"] = self.priority

        return frontmatter

    @classmethod
    def from_frontmatter_dict(cls, data: dict[str, str | list[str] | int | None]) -> "Capture":
        """
        Create a Capture instance from frontmatter dictionary.

        Args:
            data: Dictionary parsed from YAML frontmatter

        Returns:
            Capture instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Parse created timestamp
        created_str = data.get("created")
        if not created_str:
            raise ValueError("'created' field is required")
        if isinstance(created_str, str):
            # Handle ISO 8601 format
            try:
                created = datetime.fromisoformat(created_str)
            except ValueError as e:
                raise ValueError(f"Invalid 'created' timestamp format: {created_str}") from e
        elif isinstance(created_str, datetime):
            created = created_str
        else:
            raise ValueError(f"Invalid 'created' type: {type(created_str)}")

        # Parse tags
        tags_raw = data.get("tags", [])
        if isinstance(tags_raw, str):
            tags = [tags_raw]
        elif isinstance(tags_raw, list):
            tags = tags_raw
        else:
            tags = []

        # Parse source
        source_raw = data.get("source", "cli")
        if isinstance(source_raw, str):
            try:
                source = CaptureSource(source_raw)
            except ValueError as e:
                raise ValueError(f"Invalid 'source' value: {source_raw}") from e
        else:
            source = CaptureSource.CLI

        # Parse status
        status_raw = data.get("status", "active")
        if isinstance(status_raw, str):
            try:
                status = CaptureStatus(status_raw)
            except ValueError as e:
                raise ValueError(f"Invalid 'status' value: {status_raw}") from e
        else:
            status = CaptureStatus.ACTIVE

        # Parse priority
        priority_raw = data.get("priority")
        priority: int | None = None
        if priority_raw is not None:
            if isinstance(priority_raw, int):
                priority = priority_raw
            elif isinstance(priority_raw, str):
                try:
                    priority = int(priority_raw)
                except ValueError as e:
                    raise ValueError(f"Invalid 'priority' value: {priority_raw}") from e

        # Extract id and title with proper type checking
        id_value = data.get("id")
        if not isinstance(id_value, str):
            raise ValueError(f"'id' must be a string, got {type(id_value)}")

        title_value = data.get("title")
        if not isinstance(title_value, str):
            raise ValueError(f"'title' must be a string, got {type(title_value)}")

        return cls(
            id=id_value,
            created=created,
            title=title_value,
            tags=tags,
            source=source,
            status=status,
            priority=priority,
        )
