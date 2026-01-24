"""Tool adoption (selection/approval) records.

Toolsmith initially supports *discovery* and *cataloging*. Adoption is the
lightweight bridge from "found" → "we intend to use this".

This deliberately does NOT install or execute tools yet; it records intent and
any required configuration (API keys, notes) so future workflows can act.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class AdoptedTool(BaseModel):
    """A record that a tool has been adopted for this project."""

    tool_id: str = Field(..., description="Tool catalog id, e.g. 'mcp-official:brave-search'")
    adopted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: str | None = Field(default=None, description="Optional human note")


class AdoptionStore:
    """Project-scoped adoption store.

    Stored alongside the project tool catalog under .cub/toolsmith/.
    """

    def __init__(self, toolsmith_dir: Path) -> None:
        self.toolsmith_dir = Path(toolsmith_dir)
        self.adopted_file = self.toolsmith_dir / "adopted.json"

    def list_all(self) -> list[AdoptedTool]:
        if not self.adopted_file.exists():
            return []
        with open(self.adopted_file, encoding="utf-8") as f:
            data = json.load(f)
        return [AdoptedTool.model_validate(item) for item in data]

    def save(self, adopted: list[AdoptedTool]) -> None:
        self.toolsmith_dir.mkdir(parents=True, exist_ok=True)
        json_str = json.dumps([a.model_dump(mode="json") for a in adopted], indent=2)
        self.adopted_file.write_text(json_str, encoding="utf-8")

    def adopt(self, tool_id: str, note: str | None = None) -> AdoptedTool:
        adopted = self.list_all()
        existing = next((a for a in adopted if a.tool_id == tool_id), None)
        if existing is not None:
            # Update note if provided, keep timestamp.
            if note:
                existing.note = note
                self.save(adopted)
            return existing

        record = AdoptedTool(tool_id=tool_id, note=note)
        adopted.append(record)
        self.save(adopted)
        return record

    @classmethod
    def default(cls) -> AdoptionStore:
        toolsmith_dir = Path.cwd() / ".cub" / "toolsmith"
        return cls(toolsmith_dir)
