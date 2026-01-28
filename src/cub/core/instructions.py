"""
Instruction file generation for direct harness sessions.

This module generates CLAUDE.md and AGENTS.md files that guide AI assistants
to use cub commands when running directly (not via `cub run`). This enables
a symbiotic workflow where work is tracked in the ledger regardless of whether
it came from autonomous mode or direct harness sessions.

Key Functions:
    - generate_agents_md: Creates harness-agnostic instructions (AGENTS.md)
    - generate_claude_md: Creates Claude-specific instructions (CLAUDE.md)
    - detect_managed_section: Detect managed section markers in a file
    - upsert_managed_section: Insert or update a managed section in a file

Architecture:
    The instruction generator produces markdown files that:
    1. Guide agents to use `cub task` commands for task management
    2. Instruct agents to use `cub` commands for logging and status
    3. Include escape hatch language for signaling when stuck
    4. Provide workflow instructions for finding, claiming, and completing tasks

    Managed sections use HTML comment markers to non-destructively embed
    cub-managed content in user-owned files (CLAUDE.md, AGENTS.md):

        <!-- BEGIN CUB MANAGED SECTION v1 -->
        <!-- sha256:abc123... -->
        (managed content here)
        <!-- END CUB MANAGED SECTION -->

Usage:
    >>> from pathlib import Path
    >>> from cub.core.config.loader import load_config
    >>> from cub.core.instructions import generate_agents_md, generate_claude_md
    >>>
    >>> project_dir = Path.cwd()
    >>> config = load_config(project_dir)
    >>>
    >>> # Generate AGENTS.md for cross-harness compatibility
    >>> agents_content = generate_agents_md(project_dir, config)
    >>> (project_dir / "AGENTS.md").write_text(agents_content)
    >>>
    >>> # Generate CLAUDE.md with Claude-specific additions
    >>> claude_content = generate_claude_md(project_dir, config)
    >>> (project_dir / "CLAUDE.md").write_text(claude_content)
    >>>
    >>> # Non-destructive upsert into existing file
    >>> from cub.core.instructions import upsert_managed_section
    >>> result = upsert_managed_section(Path("CLAUDE.md"), claude_content, version=1)

Dependencies:
    - pathlib: For file path handling
    - hashlib: For content hashing (sha256)
    - re: For regex-based marker detection
    - logging: For warnings on edge cases
    - cub.core.config.models: For CubConfig type hints
    - pydantic: For UpsertResult and SectionInfo models
"""

from __future__ import annotations

import hashlib
import logging
import re
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from cub.core.config.models import CubConfig

logger = logging.getLogger(__name__)

# --- Marker format constants ---
BEGIN_MARKER_PATTERN = re.compile(
    r"^<!-- BEGIN CUB MANAGED SECTION v(\d+) -->$", re.MULTILINE
)
END_MARKER = "<!-- END CUB MANAGED SECTION -->"
END_MARKER_PATTERN = re.compile(
    r"^<!-- END CUB MANAGED SECTION -->$", re.MULTILINE
)
HASH_LINE_PATTERN = re.compile(
    r"^<!-- sha256:([a-f0-9]{64}) -->$", re.MULTILINE
)


def _content_hash(content: str) -> str:
    """Compute sha256 hex digest of content string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _format_managed_block(content: str, version: int) -> str:
    """Format content into a complete managed section block with markers."""
    content_stripped = content.strip()
    h = _content_hash(content_stripped)
    return (
        f"<!-- BEGIN CUB MANAGED SECTION v{version} -->\n"
        f"<!-- sha256:{h} -->\n"
        f"{content_stripped}\n"
        f"<!-- END CUB MANAGED SECTION -->"
    )


# --- Pydantic models ---


class UpsertAction(str, Enum):
    """Action taken by upsert_managed_section."""

    CREATED = "created"
    APPENDED = "appended"
    REPLACED = "replaced"


class SectionInfo(BaseModel):
    """Information about a detected managed section in a file.

    Attributes:
        found: Whether a managed section was detected.
        version: The version number from the begin marker, or None.
        start_line: 0-based line index of the begin marker, or None.
        end_line: 0-based line index of the end marker, or None.
        content_hash: The sha256 hash from the marker, or None.
        actual_hash: The sha256 hash of the actual content between markers, or None.
        has_begin: Whether a begin marker was found.
        has_end: Whether an end marker was found.
        content_modified: Whether the content hash differs from the marker hash.
    """

    found: bool = False
    version: int | None = None
    start_line: int | None = None
    end_line: int | None = None
    content_hash: str | None = None
    actual_hash: str | None = None
    has_begin: bool = False
    has_end: bool = False
    content_modified: bool = False


class UpsertResult(BaseModel):
    """Result of an upsert_managed_section operation.

    Attributes:
        action: What action was taken (created, appended, replaced).
        file_path: Path to the file that was written.
        version: Version number used in the managed section.
        content_hash: sha256 hash of the managed content.
        previous_hash: Hash of the previous managed content, if replaced.
        content_was_modified: Whether the previous section had manual edits.
        warnings: List of warning messages about edge cases encountered.
    """

    action: UpsertAction
    file_path: Path
    version: int
    content_hash: str
    previous_hash: str | None = None
    content_was_modified: bool = False
    warnings: list[str] = []

    model_config = {"arbitrary_types_allowed": True}


# --- Core functions ---


def detect_managed_section(file_path: Path) -> SectionInfo:
    """Detect a managed section in a file using regex-based marker detection.

    Scans the file for BEGIN/END CUB MANAGED SECTION markers and extracts
    version, line range, and content hash information.

    Args:
        file_path: Path to the file to scan.

    Returns:
        SectionInfo with detection results. If no file exists or no markers
        are found, returns SectionInfo(found=False).
    """
    if not file_path.exists():
        return SectionInfo()

    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    begin_line: int | None = None
    end_line: int | None = None
    version: int | None = None
    marker_hash: str | None = None

    for i, line in enumerate(lines):
        begin_match = BEGIN_MARKER_PATTERN.match(line)
        if begin_match:
            begin_line = i
            version = int(begin_match.group(1))
            continue

        if END_MARKER_PATTERN.match(line):
            end_line = i
            # Only use the first end marker after a begin marker
            if begin_line is not None:
                break

    has_begin = begin_line is not None
    has_end = end_line is not None

    if not has_begin and not has_end:
        return SectionInfo()

    # Extract hash from the line after begin marker
    if has_begin and begin_line is not None:
        hash_line_idx = begin_line + 1
        if hash_line_idx < len(lines):
            hash_match = HASH_LINE_PATTERN.match(lines[hash_line_idx])
            if hash_match:
                marker_hash = hash_match.group(1)

    # Compute actual hash of content between markers
    actual_hash: str | None = None
    if has_begin and has_end and begin_line is not None and end_line is not None:
        # Content is between the hash line (or begin+1) and end marker
        content_start = begin_line + 1
        # Skip hash line if present
        if content_start < len(lines) and HASH_LINE_PATTERN.match(
            lines[content_start]
        ):
            content_start += 1
        content_lines = lines[content_start:end_line]
        content_text = "\n".join(content_lines).strip()
        actual_hash = _content_hash(content_text) if content_text else None

    content_modified = False
    if marker_hash and actual_hash:
        content_modified = marker_hash != actual_hash

    return SectionInfo(
        found=has_begin and has_end,
        version=version,
        start_line=begin_line,
        end_line=end_line,
        content_hash=marker_hash,
        actual_hash=actual_hash,
        has_begin=has_begin,
        has_end=has_end,
        content_modified=content_modified,
    )


def upsert_managed_section(
    file_path: Path, content: str, version: int = 1
) -> UpsertResult:
    """Insert or update a managed section in a file.

    Handles all cases non-destructively:
    - File doesn't exist: creates new file with managed section only
    - File exists, no markers: appends managed section at end
    - File exists, markers present: replaces content between markers
    - Partial markers (begin without end, end without begin): error recovery

    Uses sha256 hash to detect manual edits inside markers. If the content
    between markers has been manually edited (hash mismatch), a warning is
    logged but the update proceeds.

    Args:
        file_path: Path to the file to upsert into.
        content: The content to place inside the managed section.
        version: Version number for the managed section markers.

    Returns:
        UpsertResult describing what action was taken.
    """
    managed_block = _format_managed_block(content, version)
    content_hash = _content_hash(content.strip())
    warnings: list[str] = []

    # Case 1: File doesn't exist — create it
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(managed_block + "\n", encoding="utf-8")
        return UpsertResult(
            action=UpsertAction.CREATED,
            file_path=file_path,
            version=version,
            content_hash=content_hash,
        )

    existing_text = file_path.read_text(encoding="utf-8")
    lines = existing_text.splitlines()

    section = detect_managed_section(file_path)

    # Case 2: No markers at all — append to end
    if not section.has_begin and not section.has_end:
        # Ensure there's a blank line before the managed section
        separator = "\n\n" if existing_text.strip() else ""
        new_text = existing_text.rstrip() + separator + managed_block + "\n"
        file_path.write_text(new_text, encoding="utf-8")
        return UpsertResult(
            action=UpsertAction.APPENDED,
            file_path=file_path,
            version=version,
            content_hash=content_hash,
        )

    # Case 3: Partial markers — error recovery
    if section.has_begin and not section.has_end:
        # Begin marker without end — treat everything from begin to EOF as section
        warn_msg = (
            f"Begin marker found at line {section.start_line} without matching "
            f"end marker in {file_path}. Appending end marker."
        )
        logger.warning(warn_msg)
        warnings.append(warn_msg)

        assert section.start_line is not None
        before = lines[: section.start_line]
        before_text = "\n".join(before)
        separator = "\n" if before_text.strip() else ""
        new_text = (
            (before_text.rstrip() + separator if before_text.strip() else "")
            + managed_block
            + "\n"
        )
        file_path.write_text(new_text, encoding="utf-8")
        return UpsertResult(
            action=UpsertAction.REPLACED,
            file_path=file_path,
            version=version,
            content_hash=content_hash,
            previous_hash=section.content_hash,
            warnings=warnings,
        )

    if section.has_end and not section.has_begin:
        # End marker without begin — treat everything from start of file to end marker
        warn_msg = (
            f"End marker found at line {section.end_line} without matching "
            f"begin marker in {file_path}. Prepending begin marker."
        )
        logger.warning(warn_msg)
        warnings.append(warn_msg)

        assert section.end_line is not None
        after = lines[section.end_line + 1 :]
        after_text = "\n".join(after)
        separator = "\n" if after_text.strip() else ""
        new_text = (
            managed_block
            + (separator + after_text.rstrip() if after_text.strip() else "")
            + "\n"
        )
        file_path.write_text(new_text, encoding="utf-8")
        return UpsertResult(
            action=UpsertAction.REPLACED,
            file_path=file_path,
            version=version,
            content_hash=content_hash,
            warnings=warnings,
        )

    # Case 4: Both markers present — replace section
    assert section.start_line is not None
    assert section.end_line is not None

    content_was_modified = section.content_modified
    if content_was_modified:
        warn_msg = (
            f"Managed section in {file_path} has been manually edited "
            f"(hash mismatch: marker={section.content_hash}, "
            f"actual={section.actual_hash}). Overwriting with new content."
        )
        logger.warning(warn_msg)
        warnings.append(warn_msg)

    before = lines[: section.start_line]
    after = lines[section.end_line + 1 :]

    before_text = "\n".join(before)
    after_text = "\n".join(after)

    parts: list[str] = []
    if before_text.strip():
        parts.append(before_text.rstrip())
    parts.append(managed_block)
    if after_text.strip():
        parts.append(after_text.lstrip("\n"))

    new_text = "\n".join(parts) + "\n"
    file_path.write_text(new_text, encoding="utf-8")

    return UpsertResult(
        action=UpsertAction.REPLACED,
        file_path=file_path,
        version=version,
        content_hash=content_hash,
        previous_hash=section.content_hash,
        content_was_modified=content_was_modified,
        warnings=warnings,
    )

# Escape hatch language from E5 spec
ESCAPE_HATCH_SECTION = """## Escape Hatch: Signal When Stuck

If you get stuck and cannot make progress despite a genuine attempt to solve
the task, signal your state to the autonomous loop so it can stop gracefully
instead of consuming time and budget on a blocked task.

**How to signal "stuck":**

Output this XML tag with your reason:

```
<stuck>REASON FOR BEING STUCK</stuck>
```

**Example:**
```
<stuck>Cannot find the required configuration file after exhaustive search.
The file may not exist in this repository, preventing further progress on
dependency injection setup.</stuck>
```

**What "stuck" means:**

- You have genuinely attempted to solve the task (multiple approaches, searched
  codebase, read docs)
- An external blocker prevents progress (missing file, dependency not found,
  environment issue, unclear requirements)
- Continuing to work on this task will waste time and money without producing
  value
- The blocker cannot be resolved within the scope of this task

**What "stuck" does NOT mean:**

- "This task is hard" — Keep working
- "I'm confused about how something works" — Search docs, read code, ask in a
  follow-up task
- "I've spent 30 minutes" — Time spent is not a blocker; genuine blockers are

**Effect of signaling "stuck":**

- The autonomous loop detects this signal and stops the run gracefully
- Your work so far is captured in artifacts and the ledger
- The task is marked with context for manual review
- This complements the time-based circuit breaker which trips after inactivity
  timeout

**Important:** This is not a replacement for the time-based circuit breaker.
The circuit breaker monitors subprocess activity. This escape hatch is your
active signal that you, the agent, are genuinely blocked and should stop.
"""


def generate_managed_section(
    project_dir: Path, config: CubConfig, harness: str = "generic"
) -> str:
    """
    Generate condensed managed section content for instruction files.

    Produces concise (~15-25 lines) instructions that reference external context
    files rather than embedding full documentation inline.

    Args:
        project_dir: Path to the project root directory
        config: CubConfig instance with project configuration
        harness: Type of harness ("generic" for AGENTS.md, "claude" for CLAUDE.md)

    Returns:
        Condensed managed section content as a string (without markers)

    Example:
        >>> config = load_config()
        >>> content = generate_managed_section(Path.cwd(), config, "generic")
    """
    project_name = project_dir.name

    if harness == "generic":
        # Generic harness-agnostic instructions for AGENTS.md
        content = f"""# Cub Task Workflow

**Project:** `{project_name}` | **Context:** @.cub/map.md | **Principles:** @.cub/constitution.md

## Quick Start

1. **Find work**: `cub task ready` or `cub task list --status open`
2. **Claim task**: `cub task claim <task-id>`
3. **Build/test**: See @.cub/agent.md for commands
4. **Complete**: `cub task close <task-id> --reason "what you did"`
5. **Log**: `cub log --notes="session summary"` (optional)

## Task Commands

- `cub task show <id>` - View task details
- `cub status` - Project status and progress

## When Stuck

If genuinely blocked (missing files, unclear requirements, external blocker):
```xml
<stuck>Clear description of the blocker</stuck>
```

See @.cub/agent.md for full workflow documentation."""

    elif harness == "claude":
        # Claude-specific instructions for CLAUDE.md
        content = f"""# Cub Task Workflow (Claude Code)

**Project:** `{project_name}` | **Context:** @.cub/map.md | **Principles:** @.cub/constitution.md

## Quick Start

1. **Find work**: `cub task ready` or `cub task list --status open`
2. **Claim task**: `cub task claim <task-id>`
3. **Build/test**: See @.cub/agent.md for commands
4. **Complete**: `cub task close <task-id> --reason "what you did"`
5. **Log**: `cub log --notes="session summary"` (optional)

## Task Commands

- `cub task show <id>` - View task details
- `cub status` - Project status and progress

## Claude-Specific Tips

- **Plan mode**: Save complex plans to `plans/<name>/plan.md`
- **Skills**: Use `/commit`, `/review-pr`, and other skills as needed
- **@ References**: Use @.cub/map.md for codebase context, @.cub/constitution.md for principles

## When Stuck

If genuinely blocked (missing files, unclear requirements, external blocker):
```xml
<stuck>Clear description of the blocker</stuck>
```

See @.cub/agent.md for full workflow documentation."""

    else:
        raise ValueError(f"Unknown harness type: {harness}")

    return content


def generate_agents_md(project_dir: Path, config: CubConfig) -> str:
    """
    Generate AGENTS.md with harness-agnostic workflow instructions.

    Creates instructions for AI assistants running in direct mode (not via `cub run`)
    to use cub commands for task tracking and work logging. This file is compatible
    with Claude Code, Codex, OpenCode, and other AI coding assistants.

    The generated content is designed to be upserted into AGENTS.md as a managed
    section, preserving any user-written content outside the markers.

    Args:
        project_dir: Path to the project root directory
        config: CubConfig instance with project configuration

    Returns:
        Complete managed section content (ready for upsert_managed_section)

    Example:
        >>> config = load_config()
        >>> content = generate_agents_md(Path.cwd(), config)
        >>> result = upsert_managed_section(Path("AGENTS.md"), content)
    """
    return generate_managed_section(project_dir, config, harness="generic")


def generate_claude_md(project_dir: Path, config: CubConfig) -> str:
    """
    Generate CLAUDE.md with Claude Code-specific workflow instructions.

    Creates instructions tailored for Claude Code, including the core workflow
    plus Claude-specific features like plan mode integration and skills.

    The generated content is designed to be upserted into CLAUDE.md as a managed
    section, preserving any user-written content outside the markers.

    Args:
        project_dir: Path to the project root directory
        config: CubConfig instance with project configuration

    Returns:
        Complete managed section content (ready for upsert_managed_section)

    Example:
        >>> config = load_config()
        >>> content = generate_claude_md(Path.cwd(), config)
        >>> result = upsert_managed_section(Path("CLAUDE.md"), content)
    """
    return generate_managed_section(project_dir, config, harness="claude")


__all__ = [
    "generate_managed_section",
    "generate_agents_md",
    "generate_claude_md",
    "detect_managed_section",
    "upsert_managed_section",
    "ESCAPE_HATCH_SECTION",
    "SectionInfo",
    "UpsertAction",
    "UpsertResult",
]
