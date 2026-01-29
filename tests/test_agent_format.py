"""
Tests for AgentFormatter module.

Includes snapshot tests for each format method with representative inputs
(0, 1, 10, 20 items) and token budget tests.
"""


import pytest

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
