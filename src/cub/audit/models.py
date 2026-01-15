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


class LinkFinding(BaseModel):
    """A link issue found in documentation."""

    file_path: str = Field(description="Path to the file containing the link")
    line_number: int = Field(ge=1, description="Line number where the link appears")
    url: str = Field(description="The URL or reference that is broken")
    issue: Literal["broken_link", "invalid_url", "missing_file", "timeout"] = Field(
        description="Type of link issue"
    )
    status_code: int | None = Field(
        default=None, description="HTTP status code if applicable"
    )


class CodeBlockFinding(BaseModel):
    """A code block issue found in documentation."""

    file_path: str = Field(description="Path to the file containing the code block")
    line_number: int = Field(ge=1, description="Line number where the code block starts")
    language: str = Field(description="Language of the code block")
    issue: Literal["syntax_error", "invalid_language"] = Field(
        description="Type of code block issue"
    )
    error_message: str = Field(description="Error message describing the issue")


class DocsReport(BaseModel):
    """Report of all documentation validation findings."""

    link_findings: list[LinkFinding] = Field(
        default_factory=list, description="List of link issues"
    )
    code_findings: list[CodeBlockFinding] = Field(
        default_factory=list, description="List of code block issues"
    )
    files_scanned: int = Field(ge=0, description="Number of markdown files scanned")
    links_checked: int = Field(ge=0, description="Total number of links checked")
    code_blocks_checked: int = Field(ge=0, description="Total number of code blocks checked")

    @property
    def has_findings(self) -> bool:
        """Return True if there are any findings."""
        return len(self.link_findings) > 0 or len(self.code_findings) > 0

    @property
    def total_issues(self) -> int:
        """Return total count of all issues."""
        return len(self.link_findings) + len(self.code_findings)
