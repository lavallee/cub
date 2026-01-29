"""
Tests for AgentFormatter module.

Includes snapshot tests for each format method with representative inputs
(0, 1, 10, 20 items) and token budget tests.
"""

from datetime import datetime, timezone

import pytest

from cub.core.ledger.models import LedgerEntry, LedgerStats, TokenUsage
from cub.core.services.agent_format import AgentFormatter
from cub.core.services.models import EpicProgress, ProjectStats
from cub.core.suggestions.models import Suggestion, SuggestionCategory
from cub.core.tasks.graph import DependencyGraph
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_tasks() -> list[Task]:
    """Create sample tasks for testing."""
    return [
        Task(
            id="cub-001",
            title="Implement feature X",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
            blocks=["cub-002", "cub-003"],
        ),
        Task(
            id="cub-002",
            title="Add tests for feature X",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            depends_on=["cub-001"],
        ),
        Task(
            id="cub-003",
            title="Document feature X",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            depends_on=["cub-001"],
        ),
        Task(
            id="cub-004",
            title="Implement feature Y",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P0,
            type=TaskType.TASK,
            blocks=["cub-005"],
        ),
        Task(
            id="cub-005",
            title="Test feature Y",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
            depends_on=["cub-004"],
        ),
    ]


@pytest.fixture
def sample_graph(sample_tasks: list[Task]) -> DependencyGraph:
    """Create a dependency graph from sample tasks."""
    return DependencyGraph(sample_tasks)


@pytest.fixture
def sample_project_stats() -> ProjectStats:
    """Create sample project stats."""
    return ProjectStats(
        total_tasks=42,
        open_tasks=15,
        in_progress_tasks=3,
        closed_tasks=24,
        ready_tasks=3,
        blocked_tasks=18,
        total_epics=5,
        active_epics=3,
        completion_percentage=57.1,
        total_cost_usd=42.50,
        total_tokens=125000,
        tasks_in_ledger=24,
        current_branch="feature/agent-formatter",
        has_uncommitted_changes=True,
        commits_since_main=5,
    )


@pytest.fixture
def sample_epic_progress() -> EpicProgress:
    """Create sample epic progress."""
    return EpicProgress(
        epic_id="cub-a1f",
        epic_title="AgentFormatter & --agent Flag",
        total_tasks=6,
        open_tasks=3,
        in_progress_tasks=1,
        closed_tasks=2,
        ready_tasks=2,
        completion_percentage=33.3,
        total_cost_usd=1.20,
        total_tokens=35000,
        tasks_with_cost=2,
    )


@pytest.fixture
def sample_suggestions() -> list[Suggestion]:
    """Create sample suggestions."""
    return [
        Suggestion(
            category=SuggestionCategory.TASK,
            title="Work on cub-001",
            rationale="P1 task that unblocks 2 downstream tasks",
            priority_score=0.85,
            action="bd update cub-001 --status in_progress",
        ),
        Suggestion(
            category=SuggestionCategory.TASK,
            title="Work on cub-004",
            rationale="P0 task with high priority",
            priority_score=0.90,
            action="bd update cub-004 --status in_progress",
        ),
        Suggestion(
            category=SuggestionCategory.GIT,
            title="Commit changes",
            rationale="Uncommitted changes detected",
            priority_score=0.60,
            action="git add . && git commit",
        ),
    ]


@pytest.fixture
def sample_ledger_entries() -> list[LedgerEntry]:
    """Create sample ledger entries."""
    return [
        LedgerEntry(
            id="cub-001",
            title="Implement feature X",
            completed_at=datetime(2026, 1, 18, 10, 45, tzinfo=timezone.utc),
            cost_usd=0.09,
            tokens=TokenUsage(input_tokens=45000, output_tokens=12000),
        ),
        LedgerEntry(
            id="cub-002",
            title="Add tests for feature X",
            completed_at=datetime(2026, 1, 18, 11, 30, tzinfo=timezone.utc),
            cost_usd=0.05,
            tokens=TokenUsage(input_tokens=25000, output_tokens=8000),
        ),
        LedgerEntry(
            id="cub-003",
            title="Document feature X",
            completed_at=datetime(2026, 1, 18, 12, 15, tzinfo=timezone.utc),
            cost_usd=0.03,
            tokens=TokenUsage(input_tokens=15000, output_tokens=5000),
        ),
    ]


@pytest.fixture
def sample_ledger_stats() -> LedgerStats:
    """Create sample ledger stats."""
    return LedgerStats(
        total_tasks=24,
        total_cost_usd=2.16,
        total_tokens=288000,
        average_cost_per_task=0.09,
        total_duration_seconds=15000,
        tasks_verified=20,
        tasks_failed=4,
    )


@pytest.fixture
def blocked_tasks(sample_tasks: list[Task]) -> list[Task]:
    """Create blocked tasks for testing."""
    return [
        Task(
            id="cub-010",
            title="Task blocked by one",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
            depends_on=["cub-001"],
        ),
        Task(
            id="cub-011",
            title="Task blocked by multiple",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            depends_on=["cub-001", "cub-002"],
        ),
        Task(
            id="cub-012",
            title="Another blocked task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
            depends_on=["cub-001"],
        ),
    ]


# ============================================================================
# format_ready tests
# ============================================================================


def test_format_ready_empty() -> None:
    """Test format_ready with 0 tasks."""
    output = AgentFormatter.format_ready([])

    assert "# cub task ready" in output
    assert "0 tasks ready to work on" in output
    assert "## Ready Tasks" not in output


def test_format_ready_one_task(sample_tasks: list[Task]) -> None:
    """Test format_ready with 1 task."""
    tasks = [sample_tasks[0]]
    output = AgentFormatter.format_ready(tasks)

    assert "# cub task ready" in output
    assert "1 task ready to work on" in output
    assert "## Ready Tasks" in output
    assert "cub-001" in output
    assert "Implement feature X" in output


def test_format_ready_with_graph(
    sample_tasks: list[Task], sample_graph: DependencyGraph
) -> None:
    """Test format_ready with dependency graph."""
    ready = [t for t in sample_tasks if t.is_ready]
    output = AgentFormatter.format_ready(ready, sample_graph)

    assert "# cub task ready" in output
    assert "## Ready Tasks" in output
    assert "## Analysis" in output
    assert "Highest impact" in output or "Highest priority" in output


def test_format_ready_many_tasks() -> None:
    """Test format_ready with 20 tasks (truncation test)."""
    tasks = [
        Task(
            id=f"cub-{i:03d}",
            title=f"Task {i}",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
        )
        for i in range(20)
    ]

    output = AgentFormatter.format_ready(tasks)

    assert "# cub task ready" in output
    assert "20 tasks ready to work on" in output
    assert "Showing 10 of 20" in output


def test_format_ready_no_graph(sample_tasks: list[Task]) -> None:
    """Test format_ready without dependency graph."""
    ready = [t for t in sample_tasks if t.is_ready]
    output = AgentFormatter.format_ready(ready, graph=None)

    assert "# cub task ready" in output
    assert "## Analysis" not in output  # No analysis without graph


# ============================================================================
# format_task_detail tests
# ============================================================================


def test_format_task_detail_basic(sample_tasks: list[Task]) -> None:
    """Test format_task_detail with basic task."""
    task = sample_tasks[0]
    output = AgentFormatter.format_task_detail(task)

    assert f"# cub task show {task.id}" in output
    assert f"## {task.title}" in output
    assert f"**Priority**: {task.priority.value}" in output
    assert f"**Status**: {task.status.value}" in output
    assert f"**Type**: {task.type.value}" in output


def test_format_task_detail_with_description() -> None:
    """Test format_task_detail with description."""
    task = Task(
        id="cub-001",
        title="Test task",
        description="This is a test task with a description that explains what to do.",
    )

    output = AgentFormatter.format_task_detail(task)

    assert "## Description" in output
    assert "This is a test task" in output


def test_format_task_detail_long_description() -> None:
    """Test format_task_detail with long description (truncation)."""
    long_desc = "A" * 600  # Exceeds 500 char limit
    task = Task(
        id="cub-001",
        title="Test task",
        description=long_desc,
    )

    output = AgentFormatter.format_task_detail(task)

    assert "## Description" in output
    assert "..." in output
    assert len(output.split("## Description")[1].split("\n\n")[1]) <= 510


def test_format_task_detail_with_dependencies(sample_tasks: list[Task]) -> None:
    """Test format_task_detail with dependencies."""
    task = sample_tasks[1]  # Has depends_on
    output = AgentFormatter.format_task_detail(task)

    assert "## Dependencies" in output
    assert "**Blocked by**:" in output
    assert "cub-001" in output


def test_format_task_detail_with_epic(
    sample_tasks: list[Task], sample_epic_progress: EpicProgress
) -> None:
    """Test format_task_detail with epic progress."""
    task = sample_tasks[0]
    task.parent = "cub-a1f"

    output = AgentFormatter.format_task_detail(task, epic_progress=sample_epic_progress)

    assert "**Epic**:" in output
    assert "cub-a1f" in output
    assert sample_epic_progress.epic_title in output
    assert "**Epic progress**:" in output


def test_format_task_detail_with_graph(
    sample_tasks: list[Task], sample_graph: DependencyGraph
) -> None:
    """Test format_task_detail with dependency graph."""
    task = sample_tasks[0]  # Blocks 2 tasks
    output = AgentFormatter.format_task_detail(task, sample_graph)

    assert "## Analysis" in output
    # May have impact or recommendation depending on task


def test_format_task_detail_with_labels() -> None:
    """Test format_task_detail with labels."""
    task = Task(
        id="cub-001",
        title="Test task",
        labels=["phase-1", "complexity:high", "model:sonnet"],
    )

    output = AgentFormatter.format_task_detail(task)

    assert "**Labels**:" in output
    assert "phase-1" in output
    assert "complexity:high" in output


# ============================================================================
# format_status tests
# ============================================================================


def test_format_status_basic(sample_project_stats: ProjectStats) -> None:
    """Test format_status with basic stats."""
    output = AgentFormatter.format_status(sample_project_stats)

    assert "# cub status" in output
    assert "42 tasks:" in output
    assert "24 closed" in output
    assert "57%" in output
    assert "## Breakdown" in output
    assert "## Analysis" in output


def test_format_status_empty() -> None:
    """Test format_status with no tasks."""
    stats = ProjectStats()
    output = AgentFormatter.format_status(stats)

    assert "# cub status" in output
    assert "0 tasks:" in output
    assert "No tasks" in output


def test_format_status_with_epic(
    sample_project_stats: ProjectStats, sample_epic_progress: EpicProgress
) -> None:
    """Test format_status with epic progress."""
    output = AgentFormatter.format_status(sample_project_stats, sample_epic_progress)

    assert "## Epic Progress" in output
    assert sample_epic_progress.epic_id in output
    assert sample_epic_progress.epic_title in output
    assert "Progress" in output


def test_format_status_with_git_info(sample_project_stats: ProjectStats) -> None:
    """Test format_status with git information."""
    output = AgentFormatter.format_status(sample_project_stats)

    assert "**Git**:" in output
    assert "Uncommitted changes" in output
    assert "5 commits ahead of main" in output


def test_format_status_with_ledger(sample_project_stats: ProjectStats) -> None:
    """Test format_status with ledger information."""
    output = AgentFormatter.format_status(sample_project_stats)

    assert "**Ledger**:" in output
    assert "24 tasks tracked" in output
    assert "$42.50" in output


# ============================================================================
# format_suggestions tests
# ============================================================================


def test_format_suggestions_empty() -> None:
    """Test format_suggestions with 0 suggestions."""
    output = AgentFormatter.format_suggestions([])

    assert "# cub suggest" in output
    assert "0 recommendations" in output
    assert "## Suggestions" not in output


def test_format_suggestions_basic(sample_suggestions: list[Suggestion]) -> None:
    """Test format_suggestions with basic suggestions."""
    output = AgentFormatter.format_suggestions(sample_suggestions)

    assert "# cub suggest" in output
    assert "3 recommendations" in output
    assert "## Suggestions" in output
    assert "Priority" in output
    assert "Category" in output


def test_format_suggestions_many() -> None:
    """Test format_suggestions with 15 suggestions (truncation)."""
    suggestions = [
        Suggestion(
            category=SuggestionCategory.TASK,
            title=f"Task {i}",
            rationale=f"Rationale for task {i}",
            priority_score=0.5,
        )
        for i in range(15)
    ]

    output = AgentFormatter.format_suggestions(suggestions)

    assert "15 recommendations" in output
    assert "Showing 10 of 15" in output


def test_format_suggestions_long_rationale() -> None:
    """Test format_suggestions with long rationale (truncation)."""
    suggestion = Suggestion(
        category=SuggestionCategory.TASK,
        title="Test",
        rationale="A" * 100,  # Long rationale
        priority_score=0.5,
    )

    output = AgentFormatter.format_suggestions([suggestion])

    # Check that rationale is truncated in table
    lines = output.split("\n")
    table_lines = [line for line in lines if line.startswith("|") and "Test" in line]
    assert len(table_lines) > 0
    # Rationale should be truncated with ...
    assert "..." in table_lines[0]


# ============================================================================
# Token budget tests
# ============================================================================


def test_token_budget_format_ready(
    sample_tasks: list[Task], sample_graph: DependencyGraph
) -> None:
    """Test that format_ready output is under token budget."""
    # Use 10 tasks (typical case)
    tasks = sample_tasks[:5] + sample_tasks[:5]  # Duplicate to get 10

    output = AgentFormatter.format_ready(tasks, sample_graph)

    # Target: <500 tokens (~2000 chars)
    assert len(output) < 2000, f"Output too long: {len(output)} chars"


def test_token_budget_format_task_detail(
    sample_tasks: list[Task],
    sample_graph: DependencyGraph,
    sample_epic_progress: EpicProgress,
) -> None:
    """Test that format_task_detail output is under token budget."""
    task = sample_tasks[0]
    task.parent = "cub-a1f"
    task.description = "This is a description. " * 20  # Medium length

    output = AgentFormatter.format_task_detail(
        task, sample_graph, sample_epic_progress
    )

    # Target: <500 tokens (~2000 chars)
    assert len(output) < 2000, f"Output too long: {len(output)} chars"


def test_token_budget_format_status(
    sample_project_stats: ProjectStats, sample_epic_progress: EpicProgress
) -> None:
    """Test that format_status output is under token budget."""
    output = AgentFormatter.format_status(sample_project_stats, sample_epic_progress)

    # Target: <500 tokens (~2000 chars)
    assert len(output) < 2000, f"Output too long: {len(output)} chars"


def test_token_budget_format_suggestions(sample_suggestions: list[Suggestion]) -> None:
    """Test that format_suggestions output is under token budget."""
    # Use 10 suggestions (typical case)
    suggestions = sample_suggestions * 4  # 12 suggestions

    output = AgentFormatter.format_suggestions(suggestions)

    # Target: <500 tokens (~2000 chars)
    assert len(output) < 2000, f"Output too long: {len(output)} chars"


def test_token_budget_format_blocked(
    sample_tasks: list[Task], blocked_tasks: list[Task]
) -> None:
    """Test that format_blocked output is under token budget."""
    # Use 10 blocked tasks (typical case)
    all_tasks = sample_tasks + blocked_tasks
    graph = DependencyGraph(all_tasks)

    output = AgentFormatter.format_blocked(blocked_tasks, graph)

    # Target: <500 tokens (~2000 chars)
    assert len(output) < 2000, f"Output too long: {len(output)} chars"


def test_token_budget_format_list(sample_tasks: list[Task]) -> None:
    """Test that format_list output is under token budget."""
    # Use 10 tasks (typical case)
    tasks = sample_tasks + sample_tasks  # 10 tasks

    output = AgentFormatter.format_list(tasks)

    # Target: <500 tokens (~2000 chars)
    assert len(output) < 2000, f"Output too long: {len(output)} chars"


def test_token_budget_format_ledger(
    sample_ledger_entries: list[LedgerEntry], sample_ledger_stats: LedgerStats
) -> None:
    """Test that format_ledger output is under token budget."""
    # Use 10 entries (typical case)
    entries = sample_ledger_entries * 4  # 12 entries

    output = AgentFormatter.format_ledger(entries, sample_ledger_stats)

    # Target: <500 tokens (~2000 chars)
    assert len(output) < 2000, f"Output too long: {len(output)} chars"


# ============================================================================
# Helper method tests
# ============================================================================


def test_truncate_table_no_limit() -> None:
    """Test _truncate_table with no limit."""
    rows = [f"| Row {i} |" for i in range(5)]
    output = AgentFormatter._truncate_table(rows, limit=None)

    assert "Row 0" in output
    assert "Row 4" in output
    assert "Showing" not in output


def test_truncate_table_with_limit() -> None:
    """Test _truncate_table with limit."""
    rows = [f"| Row {i} |" for i in range(20)]
    output = AgentFormatter._truncate_table(rows, limit=5, total=20)

    assert "Row 0" in output
    assert "Row 4" in output
    assert "Row 5" not in output
    assert "Showing 5 of 20" in output


def test_format_blocks_count() -> None:
    """Test _format_blocks_count helper."""
    assert AgentFormatter._format_blocks_count(0) == "none"
    assert AgentFormatter._format_blocks_count(1) == "1 task"
    assert AgentFormatter._format_blocks_count(5) == "5 tasks"


def test_truncate_description_short() -> None:
    """Test _truncate_description with short text."""
    text = "Short description"
    output = AgentFormatter._truncate_description(text, max_chars=500)

    assert output == text
    assert "..." not in output


def test_truncate_description_long() -> None:
    """Test _truncate_description with long text."""
    text = "A" * 600
    output = AgentFormatter._truncate_description(text, max_chars=500)

    assert len(output) <= 503  # 500 + "..."
    assert output.endswith("...")


# ============================================================================
# format_blocked tests
# ============================================================================


def test_format_blocked_empty() -> None:
    """Test format_blocked with 0 tasks."""
    output = AgentFormatter.format_blocked([])

    assert "# cub task blocked" in output
    assert "0 tasks blocked" in output
    assert "## Blocked Tasks" not in output


def test_format_blocked_one_task(blocked_tasks: list[Task]) -> None:
    """Test format_blocked with 1 task."""
    tasks = [blocked_tasks[0]]
    output = AgentFormatter.format_blocked(tasks)

    assert "# cub task blocked" in output
    assert "1 task blocked" in output
    assert "## Blocked Tasks" in output
    assert "cub-010" in output
    assert "Task blocked by one" in output
    assert "cub-001" in output


def test_format_blocked_with_graph(
    sample_tasks: list[Task], blocked_tasks: list[Task]
) -> None:
    """Test format_blocked with dependency graph."""
    all_tasks = sample_tasks + blocked_tasks
    graph = DependencyGraph(all_tasks)
    output = AgentFormatter.format_blocked(blocked_tasks, graph)

    assert "# cub task blocked" in output
    assert "## Blocked Tasks" in output
    assert "## Analysis" in output
    assert "Root blockers" in output or "Top blocker" in output


def test_format_blocked_many_tasks() -> None:
    """Test format_blocked with 20 tasks (truncation test)."""
    tasks = [
        Task(
            id=f"cub-{i:03d}",
            title=f"Blocked task {i}",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            depends_on=["cub-base"],
        )
        for i in range(20)
    ]

    output = AgentFormatter.format_blocked(tasks)

    assert "# cub task blocked" in output
    assert "20 tasks blocked" in output
    assert "Showing 10 of 20" in output


def test_format_blocked_no_graph(blocked_tasks: list[Task]) -> None:
    """Test format_blocked without dependency graph."""
    output = AgentFormatter.format_blocked(blocked_tasks, graph=None)

    assert "# cub task blocked" in output
    assert "## Analysis" not in output  # No analysis without graph


def test_format_blocked_singular_plural() -> None:
    """Test format_blocked handles singular/plural correctly."""
    # Singular
    task = Task(id="cub-001", title="Blocked task", depends_on=["cub-base"])
    output = AgentFormatter.format_blocked([task])
    assert "1 task blocked" in output

    # Plural
    tasks = [task, task]  # Duplicate for test
    output = AgentFormatter.format_blocked(tasks)
    assert "2 tasks blocked" in output


def test_format_blocked_blocked_by_formatting(blocked_tasks: list[Task]) -> None:
    """Test format_blocked formats 'blocked by' column correctly."""
    output = AgentFormatter.format_blocked(blocked_tasks)

    # Single blocker
    assert "cub-001" in output

    # Multiple blockers
    assert "2 tasks" in output


# ============================================================================
# format_list tests
# ============================================================================


def test_format_list_empty() -> None:
    """Test format_list with 0 tasks."""
    output = AgentFormatter.format_list([])

    assert "# cub task list" in output
    assert "0 tasks across all statuses" in output
    assert "## Tasks" not in output


def test_format_list_one_task(sample_tasks: list[Task]) -> None:
    """Test format_list with 1 task."""
    tasks = [sample_tasks[0]]
    output = AgentFormatter.format_list(tasks)

    assert "# cub task list" in output
    assert "1 task across all statuses" in output
    assert "## Tasks" in output
    assert "cub-001" in output
    assert "Implement feature X" in output
    assert "open" in output
    assert "P1" in output


def test_format_list_multiple_tasks(sample_tasks: list[Task]) -> None:
    """Test format_list with multiple tasks."""
    output = AgentFormatter.format_list(sample_tasks)

    assert "# cub task list" in output
    assert "5 tasks across all statuses" in output
    assert "## Tasks" in output

    # Check all tasks are included
    for task in sample_tasks:
        assert task.id in output


def test_format_list_many_tasks() -> None:
    """Test format_list with 20 tasks (truncation test)."""
    tasks = [
        Task(
            id=f"cub-{i:03d}",
            title=f"Task {i}",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
        )
        for i in range(20)
    ]

    output = AgentFormatter.format_list(tasks)

    assert "# cub task list" in output
    assert "20 tasks across all statuses" in output
    assert "Showing 10 of 20" in output


def test_format_list_mixed_statuses() -> None:
    """Test format_list with tasks in different statuses."""
    tasks = [
        Task(id="cub-001", title="Open task", status=TaskStatus.OPEN),
        Task(id="cub-002", title="In progress", status=TaskStatus.IN_PROGRESS),
        Task(id="cub-003", title="Closed task", status=TaskStatus.CLOSED),
    ]

    output = AgentFormatter.format_list(tasks)

    assert "open" in output
    assert "in_progress" in output
    assert "closed" in output


def test_format_list_with_dependencies(sample_tasks: list[Task]) -> None:
    """Test format_list shows dependency information."""
    output = AgentFormatter.format_list(sample_tasks)

    # Check blocks column
    assert "2 tasks" in output  # cub-001 blocks 2 tasks

    # Check blocked by column
    assert "none" in output  # Some tasks have no dependencies


# ============================================================================
# format_ledger tests
# ============================================================================


def test_format_ledger_empty() -> None:
    """Test format_ledger with 0 entries."""
    output = AgentFormatter.format_ledger([])

    assert "# cub ledger" in output
    assert "0 tasks in ledger" in output
    assert "## Recent Completions" not in output


def test_format_ledger_one_entry(sample_ledger_entries: list[LedgerEntry]) -> None:
    """Test format_ledger with 1 entry."""
    entries = [sample_ledger_entries[0]]
    output = AgentFormatter.format_ledger(entries)

    assert "# cub ledger" in output
    assert "1 task in ledger" in output
    assert "## Recent Completions" in output
    assert "cub-001" in output
    assert "Implement feature X" in output
    assert "2026-01-18" in output
    assert "$0.09" in output


def test_format_ledger_with_stats(
    sample_ledger_entries: list[LedgerEntry], sample_ledger_stats: LedgerStats
) -> None:
    """Test format_ledger with stats."""
    output = AgentFormatter.format_ledger(sample_ledger_entries, sample_ledger_stats)

    assert "# cub ledger" in output
    assert "24 tasks completed" in output
    assert "$2.16" in output
    assert "## Analysis" in output
    assert "Average cost" in output


def test_format_ledger_many_entries() -> None:
    """Test format_ledger with 20 entries (truncation test)."""
    entries = [
        LedgerEntry(
            id=f"cub-{i:03d}",
            title=f"Task {i}",
            completed_at=datetime(2026, 1, 18, tzinfo=timezone.utc),
            cost_usd=0.05,
            tokens=TokenUsage(input_tokens=10000, output_tokens=5000),
        )
        for i in range(20)
    ]

    output = AgentFormatter.format_ledger(entries)

    assert "# cub ledger" in output
    assert "20 tasks in ledger" in output
    assert "Showing 10 of 20" in output


def test_format_ledger_no_stats(sample_ledger_entries: list[LedgerEntry]) -> None:
    """Test format_ledger without stats."""
    output = AgentFormatter.format_ledger(sample_ledger_entries, stats=None)

    assert "# cub ledger" in output
    assert "3 tasks in ledger" in output
    assert "## Analysis" not in output


def test_format_ledger_token_formatting() -> None:
    """Test format_ledger formats tokens correctly (K, M)."""
    # Small tokens (< 1K)
    entry1 = LedgerEntry(
        id="cub-001",
        title="Small task",
        completed_at=datetime(2026, 1, 18, tzinfo=timezone.utc),
        cost_usd=0.01,
        tokens=TokenUsage(input_tokens=500, output_tokens=200),
    )

    # Medium tokens (K range)
    entry2 = LedgerEntry(
        id="cub-002",
        title="Medium task",
        completed_at=datetime(2026, 1, 18, tzinfo=timezone.utc),
        cost_usd=0.05,
        tokens=TokenUsage(input_tokens=25000, output_tokens=8000),
    )

    # Large tokens (M range)
    entry3 = LedgerEntry(
        id="cub-003",
        title="Large task",
        completed_at=datetime(2026, 1, 18, tzinfo=timezone.utc),
        cost_usd=0.50,
        tokens=TokenUsage(input_tokens=1500000, output_tokens=500000),
    )

    output = AgentFormatter.format_ledger([entry1, entry2, entry3])

    assert "700" in output  # Small tokens (no suffix)
    assert "33K" in output  # Medium tokens
    assert "2.0M" in output  # Large tokens


def test_format_ledger_verification_rate() -> None:
    """Test format_ledger shows verification rate in analysis."""
    entries = [
        LedgerEntry(
            id="cub-001",
            title="Task 1",
            completed_at=datetime(2026, 1, 18, tzinfo=timezone.utc),
        )
    ]

    stats = LedgerStats(
        total_tasks=10,
        total_cost_usd=1.0,
        tasks_verified=8,
        tasks_failed=2,
    )

    output = AgentFormatter.format_ledger(entries, stats)

    assert "Verification" in output
    assert "8/10" in output
    assert "80%" in output


# ============================================================================
# Edge cases
# ============================================================================


def test_format_ready_single_vs_plural() -> None:
    """Test format_ready handles singular/plural correctly."""
    # Singular
    task = Task(id="cub-001", title="Test", blocks=["cub-002"])
    output = AgentFormatter.format_ready([task])
    assert "1 task ready" in output

    # Plural
    tasks = [task, task]  # Duplicate for test
    output = AgentFormatter.format_ready(tasks)
    assert "2 tasks ready" in output


def test_format_status_no_epic() -> None:
    """Test format_status without epic progress."""
    stats = ProjectStats(total_tasks=5, closed_tasks=2)
    output = AgentFormatter.format_status(stats, epic_progress=None)

    assert "## Epic Progress" not in output


def test_format_task_detail_minimal() -> None:
    """Test format_task_detail with minimal task (only required fields)."""
    task = Task(id="cub-001", title="Minimal task")
    output = AgentFormatter.format_task_detail(task)

    assert "# cub task show cub-001" in output
    assert "## Minimal task" in output
    # Should have basic fields but not fail
    assert "**Priority**:" in output
    assert "**Status**:" in output


def test_format_suggestions_one() -> None:
    """Test format_suggestions with exactly 1 suggestion (singular)."""
    suggestion = Suggestion(
        category=SuggestionCategory.TASK,
        title="Test",
        rationale="Test rationale",
        priority_score=0.5,
    )

    output = AgentFormatter.format_suggestions([suggestion])

    assert "1 recommendation" in output
    assert "recommendations" not in output  # Should be singular
