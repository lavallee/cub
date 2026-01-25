"""
Prompts and context builders for LLM-based code review analysis.

This module provides functions to build analysis contexts from ledger
entries, spec files, and implementation files for deep review analysis.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cub.core.ledger.models import LedgerEntry
from cub.core.review.models import IssueSeverity, IssueType, ReviewIssue

logger = logging.getLogger(__name__)


def build_analysis_context(
    entry: LedgerEntry,
    spec_content: str | None = None,
    implementation_files: dict[str, str] | None = None,
) -> str:
    """Build analysis context from a ledger entry.

    Constructs a detailed context string that provides the LLM with
    all necessary information to perform implementation review.

    Args:
        entry: Ledger entry containing task metadata
        spec_content: Optional spec file content
        implementation_files: Optional dict of file paths to contents

    Returns:
        Formatted context string for analysis
    """
    parts: list[str] = []

    # Task information
    parts.append("# Task Information\n")
    parts.append(f"**Task ID:** {entry.id}\n")
    parts.append(f"**Title:** {entry.title}\n")

    if entry.task:
        parts.append(f"**Type:** {entry.task.type}\n")
        if entry.task.description:
            parts.append(f"\n**Description:**\n{entry.task.description}\n")

    # Lineage information
    if entry.lineage.epic_id:
        parts.append(f"**Epic:** {entry.lineage.epic_id}\n")
    if entry.lineage.spec_file:
        parts.append(f"**Spec File:** {entry.lineage.spec_file}\n")

    # Outcome information
    if entry.outcome:
        parts.append(
            f"\n**Completion Status:** {'Success' if entry.outcome.success else 'Failed'}\n"
        )
        if entry.outcome.partial:
            parts.append("**Note:** Task was only partially completed.\n")
        if entry.outcome.approach:
            parts.append(f"\n**Approach Taken:**\n{entry.outcome.approach}\n")
        if entry.outcome.decisions:
            parts.append("\n**Key Decisions:**\n")
            for decision in entry.outcome.decisions:
                parts.append(f"- {decision}\n")

    # Files changed
    files_changed = entry.outcome.files_changed if entry.outcome else entry.files_changed
    if files_changed:
        parts.append("\n**Files Changed:**\n")
        for f in files_changed:
            parts.append(f"- {f}\n")

    # Drift information
    if entry.drift.severity != "none":
        parts.append(f"\n**Drift Severity:** {entry.drift.severity}\n")
        if entry.drift.additions:
            parts.append("**Additions beyond spec:**\n")
            for add in entry.drift.additions:
                parts.append(f"- {add}\n")
        if entry.drift.omissions:
            parts.append("**Omissions from spec:**\n")
            for omit in entry.drift.omissions:
                parts.append(f"- {omit}\n")

    # Spec content
    if spec_content:
        parts.append("\n# Specification\n")
        parts.append(
            "The following is the specification that the implementation should satisfy:\n\n"
        )
        parts.append(spec_content)
        parts.append("\n")

    # Note about implementation files
    if implementation_files:
        parts.append(f"\n# Implementation Files ({len(implementation_files)} files)\n")
        parts.append("The implementation files are provided separately for analysis.\n")

    return "".join(parts)


def parse_analysis_issues(analysis_text: str) -> list[ReviewIssue]:
    """Parse LLM analysis output into ReviewIssue objects.

    Extracts structured issues from the analysis text by looking for
    severity markers like [CRITICAL], [WARNING], [INFO].

    Args:
        analysis_text: Raw analysis output from LLM

    Returns:
        List of ReviewIssue objects parsed from the analysis
    """
    issues: list[ReviewIssue] = []

    # Mapping of severity markers to IssueSeverity
    severity_map = {
        "CRITICAL": IssueSeverity.CRITICAL,
        "WARNING": IssueSeverity.WARNING,
        "INFO": IssueSeverity.INFO,
    }

    lines = analysis_text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Look for severity markers
        for marker, severity in severity_map.items():
            if f"[{marker}]" in line:
                # Extract description after the marker
                parts = line.split(f"[{marker}]", 1)
                if len(parts) > 1:
                    description = parts[1].strip()

                    # Try to extract recommendation if present
                    recommendation = ""
                    if " - " in description:
                        desc_parts = description.split(" - ", 1)
                        description = desc_parts[0].strip()
                        recommendation = desc_parts[1].strip()

                    # Remove leading bullet/dash
                    description = description.lstrip("-•* ").strip()

                    if description:
                        issues.append(
                            ReviewIssue(
                                type=IssueType.DEEP_ANALYSIS_FINDING,
                                severity=severity,
                                description=description,
                                recommendation=recommendation,
                            )
                        )
                break

    return issues


def read_spec_file(spec_path: str | None, project_root: Path) -> str | None:
    """Read specification file content.

    Args:
        spec_path: Path to spec file (relative or absolute)
        project_root: Project root directory

    Returns:
        Spec file content or None if not found
    """
    if not spec_path:
        return None

    # Try as-is first (could be absolute)
    path = Path(spec_path)
    if not path.is_absolute():
        path = project_root / spec_path

    if path.exists() and path.is_file():
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read spec file {path}: {e}")
            return None

    # Try common spec locations
    for prefix in ["specs/", "specs/planned/", "specs/researching/", ""]:
        candidate = project_root / prefix / spec_path
        if candidate.exists() and candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to read spec file {candidate}: {e}")
                continue

    logger.debug(f"Spec file not found: {spec_path}")
    return None


def read_implementation_files(
    file_paths: list[str],
    project_root: Path,
    max_files: int = 10,
    max_file_size: int = 100000,
) -> dict[str, str]:
    """Read implementation files for analysis.

    Args:
        file_paths: List of file paths to read
        project_root: Project root directory
        max_files: Maximum number of files to read
        max_file_size: Maximum size per file in bytes

    Returns:
        Dict mapping file paths to their contents
    """
    contents: dict[str, str] = {}

    for file_path in file_paths[:max_files]:
        # Skip non-source files
        if not _is_analyzable_file(file_path):
            continue

        # Try to find the file
        path = Path(file_path)
        if not path.is_absolute():
            path = project_root / file_path

        if not path.exists():
            # Try with src/ prefix
            path = project_root / "src" / file_path
            if not path.exists():
                continue

        if not path.is_file():
            continue

        try:
            # Check file size
            if path.stat().st_size > max_file_size:
                logger.debug(f"Skipping large file {file_path}")
                continue

            content = path.read_text(encoding="utf-8")
            contents[file_path] = content
        except Exception as e:
            logger.debug(f"Failed to read {file_path}: {e}")
            continue

    return contents


def _is_analyzable_file(file_path: str) -> bool:
    """Check if a file should be included in analysis.

    Args:
        file_path: Path to check

    Returns:
        True if file should be analyzed
    """
    # Skip binary and non-source files
    skip_extensions = {
        ".pyc",
        ".pyo",
        ".so",
        ".dll",
        ".exe",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".svg",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".db",
        ".sqlite",
        ".sqlite3",
    }

    # Skip certain directories
    skip_dirs = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
    }

    path = Path(file_path)

    # Check extension
    if path.suffix.lower() in skip_extensions:
        return False

    # Check if in skipped directory
    for part in path.parts:
        if part in skip_dirs:
            return False

    return True
