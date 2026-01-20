"""
Parser for itemized-plan.md files.

Parses the markdown format of itemized-plan.md into structured Epic and Task objects.
Extracts epics, tasks, metadata, and acceptance criteria for use with the task system.

The itemized-plan.md format:
    # Itemized Plan: {title}

    > Source: [spec.md](path/to/spec)
    > Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
    > Generated: YYYY-MM-DD

    ## Context Summary
    {summary text}

    **Mindset:** {mindset} | **Scale:** {scale}

    ---

    ## Epic: {epic_id} - {title}
    Priority: {int}
    Labels: label1, label2

    {description}

    ### Task: {task_id} - {title}
    Priority: {int}
    Labels: label1, label2
    Blocks: task-id1, task-id2  (optional)

    **Context**: {context}

    **Implementation Steps**:
    1. Step one
    2. Step two

    **Acceptance Criteria**:
    - [ ] Criterion one
    - [ ] Criterion two

    **Files**: file1.py, file2.py  (optional)

    ---

    ## Summary
    | Epic | Tasks | Priority | Description |
    ...

Example:
    >>> from pathlib import Path
    >>> from cub.core.plan.parser import parse_itemized_plan
    >>> result = parse_itemized_plan(Path("plans/my-feature/itemized-plan.md"))
    >>> len(result.epics)
    3
    >>> len(result.tasks)
    11
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class ParsedEpic:
    """An epic parsed from itemized-plan.md."""

    id: str
    title: str
    priority: int = 0
    labels: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ParsedTask:
    """A task parsed from itemized-plan.md."""

    id: str
    title: str
    priority: int = 0
    labels: list[str] = field(default_factory=list)
    epic_id: str = ""
    blocks: list[str] = field(default_factory=list)
    context: str = ""
    implementation_steps: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass
class PlanMetadata:
    """Metadata parsed from the header of itemized-plan.md."""

    title: str = ""
    source_spec: str | None = None
    source_spec_path: str | None = None
    orientation_path: str | None = None
    architecture_path: str | None = None
    generated_date: datetime | None = None
    context_summary: str = ""
    mindset: str | None = None
    scale: str | None = None


@dataclass
class ParsedPlan:
    """Result of parsing an itemized-plan.md file."""

    metadata: PlanMetadata
    epics: list[ParsedEpic]
    tasks: list[ParsedTask]
    raw_content: str

    @property
    def total_epics(self) -> int:
        """Get the total number of epics."""
        return len(self.epics)

    @property
    def total_tasks(self) -> int:
        """Get the total number of tasks."""
        return len(self.tasks)

    def get_tasks_for_epic(self, epic_id: str) -> list[ParsedTask]:
        """Get all tasks belonging to an epic."""
        return [t for t in self.tasks if t.epic_id == epic_id]


class PlanParseError(Exception):
    """Base exception for plan parsing errors."""

    pass


class PlanFileNotFoundError(PlanParseError):
    """Raised when the plan file is not found."""

    pass


class PlanFormatError(PlanParseError):
    """Raised when the plan file has invalid format."""

    pass


# Regex patterns for parsing
_TITLE_RE = re.compile(r"^#\s+Itemized Plan:\s*(.+?)\s*$", re.MULTILINE)
_SOURCE_RE = re.compile(r">\s*Source:\s*\[([^\]]*)\]\(([^)]*)\)")
_ORIENT_RE = re.compile(r"Orient:\s*\[([^\]]*)\]\(([^)]*)\)")
_ARCHITECT_RE = re.compile(r"Architect:\s*\[([^\]]*)\]\(([^)]*)\)")
_GENERATED_RE = re.compile(r">\s*Generated:\s*(\d{4}-\d{2}-\d{2})")
_MINDSET_SCALE_RE = re.compile(r"\*\*Mindset:\*\*\s*(\w+)\s*\|\s*\*\*Scale:\*\*\s*(\w+)")

# Epic format: ## Epic: cub-abc - Title (ID can have hyphens and dots)
_EPIC_RE = re.compile(r"^##\s+Epic:\s*([a-z][a-z0-9-]+)\s+-\s+(.+?)\s*$", re.MULTILINE)
# Task format: ### Task: cub-abc.1 - Title (ID can have hyphens and dots)
_TASK_RE = re.compile(r"^###\s+Task:\s*([a-z][a-z0-9.-]+)\s+-\s+(.+?)\s*$", re.MULTILINE)

_PRIORITY_RE = re.compile(r"^Priority:\s*(\d+)\s*$", re.MULTILINE)
_LABELS_RE = re.compile(r"^Labels:\s*(.+?)\s*$", re.MULTILINE)
_BLOCKS_RE = re.compile(r"^Blocks:\s*(.+?)\s*$", re.MULTILINE)

_CONTEXT_RE = re.compile(r"\*\*Context\*\*:\s*(.+?)(?=\n\n|\n\*\*|$)", re.DOTALL)
# These patterns capture everything until the next section
_IMPL_STEPS_RE = re.compile(
    r"\*\*Implementation Steps\*\*:\s*\n([\s\S]*?)(?=\n\*\*|\n---|\n##|$)"
)
_ACCEPTANCE_RE = re.compile(
    r"\*\*Acceptance Criteria\*\*:\s*\n([\s\S]*?)(?=\n\*\*|\n---|\n##|$)"
)
_FILES_RE = re.compile(r"\*\*Files\*\*:\s*(.+?)(?=\n|$)")


def _parse_csv(value: str) -> list[str]:
    """Parse a comma-separated string into a list of stripped values."""
    items = [v.strip() for v in value.split(",")]
    return [v for v in items if v]


def _parse_metadata(content: str) -> PlanMetadata:
    """Parse the metadata section of the plan."""
    metadata = PlanMetadata()

    # Extract title
    title_match = _TITLE_RE.search(content)
    if title_match:
        metadata.title = title_match.group(1).strip()

    # Extract source spec info
    source_match = _SOURCE_RE.search(content)
    if source_match:
        metadata.source_spec = source_match.group(1).strip()
        metadata.source_spec_path = source_match.group(2).strip()

    # Extract orient/architect paths
    orient_match = _ORIENT_RE.search(content)
    if orient_match:
        metadata.orientation_path = orient_match.group(2).strip()

    architect_match = _ARCHITECT_RE.search(content)
    if architect_match:
        metadata.architecture_path = architect_match.group(2).strip()

    # Extract generated date
    date_match = _GENERATED_RE.search(content)
    if date_match:
        try:
            metadata.generated_date = datetime.strptime(
                date_match.group(1), "%Y-%m-%d"
            )
        except ValueError:
            pass

    # Extract context summary (between "## Context Summary" and next section)
    context_match = re.search(
        r"##\s+Context Summary\s*\n([\s\S]*?)(?=\n##|\n---|\n\*\*Mindset|\Z)",
        content,
        re.IGNORECASE,
    )
    if context_match:
        metadata.context_summary = context_match.group(1).strip()

    # Extract mindset and scale
    mindset_match = _MINDSET_SCALE_RE.search(content)
    if mindset_match:
        metadata.mindset = mindset_match.group(1).strip()
        metadata.scale = mindset_match.group(2).strip()

    return metadata


def _extract_section(content: str, start_pos: int, end_pattern: re.Pattern[str]) -> str:
    """Extract content from start_pos until the next section match or end of content."""
    remaining = content[start_pos:]
    next_match = end_pattern.search(remaining)
    if next_match:
        return remaining[: next_match.start()]
    return remaining


def _parse_epic_section(section: str, epic_id: str, epic_title: str) -> ParsedEpic:
    """Parse an epic section to extract metadata."""
    epic = ParsedEpic(id=epic_id, title=epic_title)

    # Extract priority
    priority_match = _PRIORITY_RE.search(section)
    if priority_match:
        try:
            epic.priority = int(priority_match.group(1))
        except ValueError:
            pass

    # Extract labels
    labels_match = _LABELS_RE.search(section)
    if labels_match:
        epic.labels = _parse_csv(labels_match.group(1))

    # Extract description (after Labels: line, before first ### or ---)
    # Look for content after the key-value pairs
    desc_match = re.search(
        r"^Labels:[^\n]*\n\n(.*?)(?=\n###|\n---|$)",
        section,
        re.MULTILINE | re.DOTALL,
    )
    if desc_match:
        epic.description = desc_match.group(1).strip()
    else:
        # Try to get description after priority if no labels
        desc_match2 = re.search(
            r"^Priority:[^\n]*\n\n(.*?)(?=\n###|\n---|$)",
            section,
            re.MULTILINE | re.DOTALL,
        )
        if desc_match2:
            epic.description = desc_match2.group(1).strip()

    return epic


def _parse_task_section(
    section: str, task_id: str, task_title: str, epic_id: str
) -> ParsedTask:
    """Parse a task section to extract all metadata."""
    task = ParsedTask(id=task_id, title=task_title, epic_id=epic_id)

    # Extract priority
    priority_match = _PRIORITY_RE.search(section)
    if priority_match:
        try:
            task.priority = int(priority_match.group(1))
        except ValueError:
            pass

    # Extract labels
    labels_match = _LABELS_RE.search(section)
    if labels_match:
        task.labels = _parse_csv(labels_match.group(1))

    # Extract blocks
    blocks_match = _BLOCKS_RE.search(section)
    if blocks_match:
        task.blocks = _parse_csv(blocks_match.group(1))

    # Extract context
    context_match = _CONTEXT_RE.search(section)
    if context_match:
        task.context = context_match.group(1).strip()

    # Extract implementation steps
    impl_match = _IMPL_STEPS_RE.search(section)
    if impl_match:
        steps_text = impl_match.group(1)
        # Parse numbered list items (one per line)
        steps = re.findall(r"^\d+\.\s*(.+)$", steps_text, re.MULTILINE)
        task.implementation_steps = [s.strip() for s in steps if s.strip()]

    # Extract acceptance criteria
    accept_match = _ACCEPTANCE_RE.search(section)
    if accept_match:
        criteria_text = accept_match.group(1)
        # Parse checkbox items (one per line), removing the checkbox syntax
        criteria = re.findall(r"^-\s*\[[ x]\]\s*(.+)$", criteria_text, re.MULTILINE)
        task.acceptance_criteria = [c.strip() for c in criteria if c.strip()]

    # Extract files
    files_match = _FILES_RE.search(section)
    if files_match:
        task.files = _parse_csv(files_match.group(1))

    return task


def _parse_epics_and_tasks(content: str) -> tuple[list[ParsedEpic], list[ParsedTask]]:
    """Parse all epics and tasks from the content."""
    epics: list[ParsedEpic] = []
    tasks: list[ParsedTask] = []

    # Find all epic positions
    epic_matches = list(_EPIC_RE.finditer(content))

    # Find the summary section to know where to stop parsing
    summary_match = re.search(r"^##\s+Summary\s*$", content, re.MULTILINE)
    content_end = summary_match.start() if summary_match else len(content)

    for i, epic_match in enumerate(epic_matches):
        epic_id = epic_match.group(1).strip()
        epic_title = epic_match.group(2).strip()

        # Determine the end of this epic section
        if i + 1 < len(epic_matches):
            epic_end = epic_matches[i + 1].start()
        else:
            epic_end = content_end

        epic_section = content[epic_match.end() : epic_end]

        # Parse the epic
        epic = _parse_epic_section(epic_section, epic_id, epic_title)
        epics.append(epic)

        # Find all tasks within this epic section
        task_matches = list(_TASK_RE.finditer(epic_section))

        for j, task_match in enumerate(task_matches):
            task_id = task_match.group(1).strip()
            task_title = task_match.group(2).strip()

            # Determine the end of this task section
            if j + 1 < len(task_matches):
                task_end = task_matches[j + 1].start()
            else:
                task_end = len(epic_section)

            task_section = epic_section[task_match.end() : task_end]

            # Parse the task
            task = _parse_task_section(task_section, task_id, task_title, epic_id)
            tasks.append(task)

    return epics, tasks


def parse_itemized_plan(path: Path) -> ParsedPlan:
    """
    Parse an itemized-plan.md file into structured data.

    Args:
        path: Path to the itemized-plan.md file.

    Returns:
        ParsedPlan containing metadata, epics, and tasks.

    Raises:
        PlanFileNotFoundError: If the file doesn't exist.
        PlanFormatError: If the file has invalid format.

    Example:
        >>> from pathlib import Path
        >>> result = parse_itemized_plan(Path("plans/my-feature/itemized-plan.md"))
        >>> result.metadata.title
        'My Feature'
        >>> len(result.epics)
        3
    """
    if not path.exists():
        raise PlanFileNotFoundError(f"Plan file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        raise PlanFileNotFoundError(f"Cannot read plan file: {e}") from e

    return parse_itemized_plan_content(content)


def parse_itemized_plan_content(content: str) -> ParsedPlan:
    """
    Parse itemized-plan.md content string into structured data.

    Args:
        content: The raw markdown content of an itemized-plan.md file.

    Returns:
        ParsedPlan containing metadata, epics, and tasks.

    Raises:
        PlanFormatError: If the content has invalid format.

    Example:
        >>> content = '''# Itemized Plan: Test
        ... > Generated: 2024-01-15
        ... ## Epic: cub-abc - Test Epic
        ... Priority: 0
        ... Labels: test
        ... ### Task: cub-abc.1 - Test Task
        ... Priority: 0
        ... Labels: test
        ... **Context**: Test context.
        ... '''
        >>> result = parse_itemized_plan_content(content)
        >>> result.metadata.title
        'Test'
    """
    if not content.strip():
        raise PlanFormatError("Plan content is empty")

    # Check for basic structure
    if "# Itemized Plan:" not in content and "## Epic:" not in content:
        raise PlanFormatError(
            "Invalid plan format: missing '# Itemized Plan:' header or '## Epic:' sections"
        )

    # Parse metadata
    metadata = _parse_metadata(content)

    # Parse epics and tasks
    epics, tasks = _parse_epics_and_tasks(content)

    return ParsedPlan(
        metadata=metadata,
        epics=epics,
        tasks=tasks,
        raw_content=content,
    )


def convert_to_task_models(
    parsed_plan: ParsedPlan,
) -> tuple[list[ParsedEpic], list[dict[str, object]]]:
    """
    Convert parsed plan to task model dictionaries.

    This converts ParsedTask objects to dictionaries suitable for
    creating Task objects from cub.core.tasks.models.

    Args:
        parsed_plan: A ParsedPlan from parse_itemized_plan.

    Returns:
        Tuple of (epics, task_dicts) where task_dicts can be used
        to create Task model instances.

    Example:
        >>> parsed = parse_itemized_plan(Path("plans/feature/itemized-plan.md"))
        >>> epics, task_dicts = convert_to_task_models(parsed)
        >>> from cub.core.tasks.models import Task
        >>> tasks = [Task(**d) for d in task_dicts]
    """
    task_dicts: list[dict[str, object]] = []

    for task in parsed_plan.tasks:
        task_dict: dict[str, object] = {
            "id": task.id,
            "title": task.title,
            "priority": task.priority,
            "labels": task.labels,
            "parent": task.epic_id,
            "blocks": task.blocks,
            "acceptance_criteria": task.acceptance_criteria,
            "description": _build_description(task),
        }
        task_dicts.append(task_dict)

    return parsed_plan.epics, task_dicts


def _build_description(task: ParsedTask) -> str:
    """Build a description string from task fields."""
    parts: list[str] = []

    if task.context:
        parts.append(task.context)

    if task.implementation_steps:
        parts.append("\n**Implementation Steps:**")
        for i, step in enumerate(task.implementation_steps, 1):
            parts.append(f"{i}. {step}")

    if task.files:
        parts.append(f"\n**Files:** {', '.join(task.files)}")

    return "\n".join(parts) if parts else ""
