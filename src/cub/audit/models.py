"""
Data models for code audit reports.

These models define the structure of dead code detection and other audit findings.
"""

from typing import Literal

from pydantic import BaseModel, Field


class DeadCodeFinding(BaseModel):
    """
    A single dead code finding (unused import, function, class, or variable).
    """

    file_path: str = Field(description="Path to the file containing the dead code")
    line_number: int = Field(ge=1, description="Line number where the definition occurs")
    name: str = Field(description="Name of the unused symbol")
    kind: Literal["import", "function", "class", "variable", "method", "bash_function"] = Field(
        description="Type of the unused symbol"
    )
    reason: str = Field(
        default="No references found",
        description="Why this code is considered dead",
    )


class DeadCodeReport(BaseModel):
    """
    Report of all dead code findings in a project.
    """

    findings: list[DeadCodeFinding] = Field(
        default_factory=list, description="List of dead code findings"
    )
    files_scanned: int = Field(ge=0, description="Number of Python files scanned")
    total_definitions: int = Field(ge=0, description="Total number of definitions analyzed")

    @property
    def has_findings(self) -> bool:
        """Return True if there are any dead code findings."""
        return len(self.findings) > 0

    @property
    def findings_by_kind(self) -> dict[str, int]:
        """Return count of findings grouped by kind."""
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.kind] = counts.get(finding.kind, 0) + 1
        return counts
