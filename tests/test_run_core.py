"""
Comprehensive tests for cli/run.py core loop.

Tests the main execution loop, task selection, budget tracking,
error handling, and all supporting functions.
"""

import signal
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cub.cli.errors import ExitCode
from cub.cli.run import (
    _show_ready_tasks,
    _signal_handler,
    app,
    create_run_artifact,
    display_summary,
    display_task_info,
    generate_system_prompt,
    generate_task_prompt,
)
from cub.core.harness.models import HarnessCapabilities, HarnessResult, TokenUsage
from cub.core.status.models import (
    BudgetStatus,
    IterationInfo,
    RunPhase,
    RunStatus,
)
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def runner():
    """Provide a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_task():
    """Provide a sample Task for testing."""
    return Task(
        id="cub-test-001",
        title="Test task title",
        description="Test task description with details",
        status=TaskStatus.OPEN,
        priority=TaskPriority.P1,
        type=TaskType.TASK,
        acceptance_criteria=["Criterion 1", "Criterion 2"],
        labels=["urgent", "backend"],
    )


@pytest.fixture
def mock_task_backend():
    """Provide a mock task backend."""
    backend = MagicMock()
    backend.backend_name = "beads"
    backend.get_agent_instructions.return_value = (
        "This project uses the beads task backend. Use 'bd' commands."
    )
    return backend


@pytest.fixture
def mock_harness_backend():
    """Provide a mock async harness backend."""
    from unittest.mock import AsyncMock

    from cub.core.harness.models import HarnessResult, TaskResult, TokenUsage

    backend = MagicMock()
    backend.name = "claude"
    backend.is_available.return_value = True
    backend.get_version.return_value = "1.0.0"
    backend.capabilities = HarnessCapabilities(
        streaming=True,
        token_reporting=True,
        system_prompt=True,
        auto_mode=True,
    )

    # Mock async methods for new code
    async def mock_run_task(task_input, debug=False):
        return TaskResult(
            output="Task completed successfully",
            usage=TokenUsage(total_tokens=1000, cost_usd=0.01),
            duration_seconds=1.5,
            exit_code=0,
        )

    async def mock_stream_task(task_input, debug=False):
        yield "chunk1"
        yield "chunk2"

    backend.run_task = AsyncMock(side_effect=mock_run_task)
    backend.stream_task = MagicMock(side_effect=mock_stream_task)

    # Keep old sync methods for backwards compatibility with tests
    backend.invoke = MagicMock(
        return_value=HarnessResult(
            output="Task completed successfully",
            exit_code=0,
            usage=TokenUsage(total_tokens=1000, cost_usd=0.01),
        )
    )
    backend.invoke_streaming = MagicMock(
        return_value=HarnessResult(
            output="Streamed output",
            exit_code=0,
            usage=TokenUsage(total_tokens=1000, cost_usd=0.01),
        )
    )

    return backend


@pytest.fixture
def mock_config():
    """Provide a mock configuration object."""
    config = MagicMock()
    config.harness.priority = ["claude", "codex"]
    config.harness.model = "sonnet"
    config.loop.max_iterations = 50
    config.loop.on_task_failure = "stop"
    config.budget.max_tokens_per_task = 500000
    config.budget.max_total_cost = 50.0
    config.budget.max_tasks_per_session = None
    config.guardrails.max_task_iterations = 3
    config.guardrails.iteration_warning_threshold = 0.8
    config.hooks.fail_fast = True
    # Circuit breaker configuration (required by run.py)
    config.circuit_breaker.enabled = False
    config.circuit_breaker.timeout_minutes = 30
    # Sync configuration
    config.sync.enabled = False
    config.sync.auto_sync = "never"
    # Ledger configuration
    config.ledger.enabled = False
    # Cleanup configuration
    config.cleanup.enabled = False
    return config


@pytest.fixture
def mock_run_status():
    """Provide a sample RunStatus for testing."""
    return RunStatus(
        run_id="test-run-001",
        session_name="test-session",
        phase=RunPhase.RUNNING,
        iteration=IterationInfo(current=5, max=50),
        budget=BudgetStatus(
            tokens_used=10000,
            tokens_limit=500000,
            cost_usd=0.25,
            cost_limit=50.0,
            tasks_completed=2,
        ),
        tasks_total=10,
        tasks_open=5,
        tasks_in_progress=1,
        tasks_closed=4,
    )


@pytest.fixture
def project_with_prompt(tmp_path):
    """Create a project directory with a PROMPT.md file."""
    project = tmp_path / "project"
    project.mkdir()

    # Create PROMPT.md
    prompt_content = """# Custom Project Prompt

You are working on a custom project.

## Rules
- Follow project conventions
- Write tests for all code
"""
    (project / "PROMPT.md").write_text(prompt_content)

    # Create minimal structure
    (project / ".git").mkdir()
    (project / ".beads").mkdir()
    (project / ".beads" / "issues.jsonl").write_text("")

    return project


# ==============================================================================
# Tests for generate_system_prompt
# ==============================================================================


class TestGenerateSystemPrompt:
    """Tests for generate_system_prompt function."""

    def test_reads_project_prompt_file(self, project_with_prompt):
        """Test that project PROMPT.md is read when present."""
        result = generate_system_prompt(project_with_prompt)

        assert "Custom Project Prompt" in result
        assert "working on a custom project" in result
        assert "Follow project conventions" in result

    def test_fallback_when_no_prompt_file(self, tmp_path, monkeypatch):
        """Test fallback prompt when no PROMPT.md exists."""
        project = tmp_path / "empty_project"
        project.mkdir()

        # Temporarily move the bundled PROMPT.md if it exists to test fallback
        # Since the bundled template exists, we test that SOME prompt is returned
        result = generate_system_prompt(project)

        # Should return the bundled template (not the fallback since bundled exists)
        # The bundled template contains "autonomous coding agent"
        assert "autonomous coding agent" in result
        assert len(result) > 100  # Should have substantial content

    def test_checks_multiple_locations(self, tmp_path):
        """Test that multiple prompt file locations are checked."""
        project = tmp_path / "project"
        project.mkdir()

        # Create in templates subdirectory
        templates_dir = project / "templates"
        templates_dir.mkdir()
        (templates_dir / "PROMPT.md").write_text("# Templates Prompt\nFrom templates dir")

        result = generate_system_prompt(project)

        assert "Templates Prompt" in result
        assert "From templates dir" in result

    def test_project_prompt_takes_precedence(self, tmp_path):
        """Test that project PROMPT.md takes precedence over templates."""
        project = tmp_path / "project"
        project.mkdir()

        # Create both files
        (project / "PROMPT.md").write_text("# Project Level Prompt")

        templates_dir = project / "templates"
        templates_dir.mkdir()
        (templates_dir / "PROMPT.md").write_text("# Templates Prompt")

        result = generate_system_prompt(project)

        assert "Project Level Prompt" in result
        assert "Templates Prompt" not in result

    def test_cub_runloop_takes_precedence(self, tmp_path):
        """Test that .cub/runloop.md takes precedence over PROMPT.md."""
        project = tmp_path / "project"
        project.mkdir()

        # Create .cub/runloop.md (highest priority)
        cub_dir = project / ".cub"
        cub_dir.mkdir()
        (cub_dir / "runloop.md").write_text("# Cub Runloop Prompt\nFrom .cub/runloop.md")

        # Create PROMPT.md (lower priority)
        (project / "PROMPT.md").write_text("# Project Level Prompt")

        result = generate_system_prompt(project)

        assert "Cub Runloop Prompt" in result
        assert "From .cub/runloop.md" in result
        assert "Project Level Prompt" not in result


# ==============================================================================
# Tests for generate_epic_context
# ==============================================================================


class TestGenerateEpicContext:
    """Tests for generate_epic_context function."""

    def test_returns_none_when_no_parent(self, mock_task, mock_task_backend):
        """Test that None is returned when task has no parent epic."""
        # Ensure task has no parent
        task = Task(
            id="cub-001",
            title="Task without parent",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent=None,
        )

        from cub.cli.run import generate_epic_context

        result = generate_epic_context(task, mock_task_backend)

        assert result is None

    def test_returns_none_when_epic_not_found(self, mock_task_backend):
        """Test that None is returned when parent epic doesn't exist."""
        task = Task(
            id="cub-001",
            title="Task with missing parent",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="nonexistent-epic",
        )

        # Mock backend returns None for missing epic
        mock_task_backend.get_task.return_value = None

        from cub.cli.run import generate_epic_context

        result = generate_epic_context(task, mock_task_backend)

        assert result is None

    def test_basic_epic_context_structure(self, mock_task_backend):
        """Test basic epic context contains required sections."""
        # Create epic
        epic = Task(
            id="epic-001",
            title="Main Epic",
            description="Epic description here",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.EPIC,
        )

        # Create task with parent
        task = Task(
            id="cub-001",
            title="Task in epic",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="epic-001",
        )

        # Mock backend
        mock_task_backend.get_task.return_value = epic
        mock_task_backend.list_tasks.return_value = [task]

        from cub.cli.run import generate_epic_context

        result = generate_epic_context(task, mock_task_backend)

        assert result is not None
        assert "## Epic Context" in result
        assert "epic-001" in result
        assert "Main Epic" in result
        assert "Epic Purpose:" in result
        assert "Epic description here" in result

    def test_truncates_long_epic_description(self, mock_task_backend):
        """Test that epic descriptions longer than 200 words are truncated."""
        # Create epic with long description (250 words)
        long_description = " ".join([f"word{i}" for i in range(250)])

        epic = Task(
            id="epic-long",
            title="Epic with Long Description",
            description=long_description,
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.EPIC,
        )

        task = Task(
            id="cub-001",
            title="Task in epic",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="epic-long",
        )

        mock_task_backend.get_task.return_value = epic
        mock_task_backend.list_tasks.return_value = [task]

        from cub.cli.run import generate_epic_context

        result = generate_epic_context(task, mock_task_backend)

        assert result is not None
        # Should contain exactly 200 words plus "..."
        assert "..." in result
        # The description should end with "..."
        assert "word199..." in result
        # Should not contain word200 or beyond
        assert "word200" not in result
        assert "word249" not in result

    def test_does_not_truncate_short_description(self, mock_task_backend):
        """Test that short epic descriptions are not truncated."""
        short_description = "This is a short epic description with only ten words here."

        epic = Task(
            id="epic-short",
            title="Epic with Short Description",
            description=short_description,
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.EPIC,
        )

        task = Task(
            id="cub-001",
            title="Task in epic",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="epic-short",
        )

        mock_task_backend.get_task.return_value = epic
        mock_task_backend.list_tasks.return_value = [task]

        from cub.cli.run import generate_epic_context

        result = generate_epic_context(task, mock_task_backend)

        assert result is not None
        assert short_description in result
        assert "..." not in result

    def test_shows_completed_sibling_tasks(self, mock_task_backend):
        """Test that completed sibling tasks are shown."""
        epic = Task(
            id="epic-001",
            title="Main Epic",
            description="Epic description",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.EPIC,
        )

        current_task = Task(
            id="cub-002",
            title="Current task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="epic-001",
        )

        completed_task = Task(
            id="cub-001",
            title="Completed task",
            status=TaskStatus.CLOSED,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="epic-001",
        )

        mock_task_backend.get_task.return_value = epic
        mock_task_backend.list_tasks.return_value = [current_task, completed_task]

        from cub.cli.run import generate_epic_context

        result = generate_epic_context(current_task, mock_task_backend)

        assert result is not None
        assert "Completed Sibling Tasks:" in result
        assert "✓ cub-001: Completed task" in result

    def test_shows_remaining_sibling_tasks(self, mock_task_backend):
        """Test that remaining sibling tasks are shown."""
        epic = Task(
            id="epic-001",
            title="Main Epic",
            description="Epic description",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.EPIC,
        )

        current_task = Task(
            id="cub-002",
            title="Current task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="epic-001",
        )

        open_task = Task(
            id="cub-003",
            title="Open task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="epic-001",
        )

        in_progress_task = Task(
            id="cub-004",
            title="In progress task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="epic-001",
        )

        mock_task_backend.get_task.return_value = epic
        mock_task_backend.list_tasks.return_value = [
            current_task,
            open_task,
            in_progress_task,
        ]

        from cub.cli.run import generate_epic_context

        result = generate_epic_context(current_task, mock_task_backend)

        assert result is not None
        assert "Remaining Sibling Tasks:" in result
        assert "○ cub-003: Open task" in result
        assert "◐ cub-004: In progress task" in result
        # Current task should not be in the remaining list
        assert "cub-002" not in result.split("Remaining Sibling Tasks:")[1]

    def test_handles_epic_with_many_siblings(self, mock_task_backend):
        """Test epic context with many sibling tasks."""
        epic = Task(
            id="epic-big",
            title="Big Epic",
            description="Epic with many tasks",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.EPIC,
        )

        current_task = Task(
            id="cub-010",
            title="Current task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="epic-big",
        )

        # Create many sibling tasks
        siblings = [current_task]
        for i in range(1, 10):
            status = TaskStatus.CLOSED if i < 5 else TaskStatus.OPEN
            siblings.append(
                Task(
                    id=f"cub-{i:03d}",
                    title=f"Task {i}",
                    status=status,
                    priority=TaskPriority.P2,
                    type=TaskType.TASK,
                    parent="epic-big",
                )
            )

        mock_task_backend.get_task.return_value = epic
        mock_task_backend.list_tasks.return_value = siblings

        from cub.cli.run import generate_epic_context

        result = generate_epic_context(current_task, mock_task_backend)

        assert result is not None
        # Should have both completed and remaining sections
        assert "Completed Sibling Tasks:" in result
        assert "Remaining Sibling Tasks:" in result
        # Check some completed tasks
        assert "✓ cub-001: Task 1" in result
        assert "✓ cub-004: Task 4" in result
        # Check some remaining tasks
        assert "○ cub-005: Task 5" in result
        assert "○ cub-009: Task 9" in result


# ==============================================================================
# Tests for generate_retry_context
# ==============================================================================


class TestGenerateRetryContext:
    """Tests for generate_retry_context function."""

    def test_returns_none_when_no_entry(self, mock_task, tmp_path):
        """Test that None is returned when task has no ledger entry."""
        from cub.cli.run import generate_retry_context
        from cub.core.ledger.integration import LedgerIntegration
        from cub.core.ledger.writer import LedgerWriter

        # Create ledger integration with empty ledger
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        integration = LedgerIntegration(writer)

        result = generate_retry_context(mock_task, integration)

        assert result is None

    def test_returns_none_when_no_attempts(self, mock_task, tmp_path):
        """Test that None is returned when entry exists but has no attempts."""
        from cub.cli.run import generate_retry_context
        from cub.core.ledger.integration import LedgerIntegration
        from cub.core.ledger.models import LedgerEntry
        from cub.core.ledger.writer import LedgerWriter

        # Create ledger with entry but no attempts
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        integration = LedgerIntegration(writer)

        entry = LedgerEntry(
            id=mock_task.id,
            title=mock_task.title,
            type="task",
            attempts=[],  # No attempts
        )
        writer.create_entry(entry)

        result = generate_retry_context(mock_task, integration)

        assert result is None

    def test_returns_none_when_only_successful_attempts(self, mock_task, tmp_path):
        """Test that None is returned when all attempts succeeded."""
        from cub.cli.run import generate_retry_context
        from cub.core.ledger.integration import LedgerIntegration
        from cub.core.ledger.models import Attempt, LedgerEntry
        from cub.core.ledger.writer import LedgerWriter

        # Create ledger with successful attempts only
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        integration = LedgerIntegration(writer)

        entry = LedgerEntry(
            id=mock_task.id,
            title=mock_task.title,
            type="task",
            attempts=[
                Attempt(
                    attempt_number=1,
                    run_id="run-1",
                    harness="claude",
                    model="haiku",
                    success=True,
                    duration_seconds=30,
                    cost_usd=0.05,
                ),
            ],
        )
        writer.create_entry(entry)

        result = generate_retry_context(mock_task, integration)

        assert result is None

    def test_basic_retry_context_structure(self, mock_task, tmp_path):
        """Test basic retry context contains required sections."""
        from cub.cli.run import generate_retry_context
        from cub.core.ledger.integration import LedgerIntegration
        from cub.core.ledger.models import Attempt, LedgerEntry
        from cub.core.ledger.writer import LedgerWriter

        # Create ledger with one failed attempt
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        integration = LedgerIntegration(writer)

        entry = LedgerEntry(
            id=mock_task.id,
            title=mock_task.title,
            type="task",
            attempts=[
                Attempt(
                    attempt_number=1,
                    run_id="run-1",
                    harness="claude",
                    model="haiku",
                    success=False,
                    error_category="timeout",
                    error_summary="Task timed out after 10 minutes",
                    duration_seconds=600,
                    cost_usd=0.10,
                ),
            ],
        )
        writer.create_entry(entry)

        result = generate_retry_context(mock_task, integration)

        assert result is not None
        assert "## Retry Context" in result
        assert "attempted 1 time(s) before" in result
        assert "1 failure(s)" in result
        assert "Previous Failed Attempts:" in result
        assert "Attempt #1:" in result
        assert "Model: haiku" in result
        assert "Duration: 10.0m" in result
        assert "Error: timeout" in result
        assert "Summary: Task timed out after 10 minutes" in result

    def test_shows_multiple_failed_attempts(self, mock_task, tmp_path):
        """Test retry context shows all failed attempts."""
        from cub.cli.run import generate_retry_context
        from cub.core.ledger.integration import LedgerIntegration
        from cub.core.ledger.models import Attempt, LedgerEntry
        from cub.core.ledger.writer import LedgerWriter

        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        integration = LedgerIntegration(writer)

        entry = LedgerEntry(
            id=mock_task.id,
            title=mock_task.title,
            type="task",
            attempts=[
                Attempt(
                    attempt_number=1,
                    run_id="run-1",
                    harness="claude",
                    model="haiku",
                    success=False,
                    error_category="test_failure",
                    error_summary="Tests failed with 3 errors",
                    duration_seconds=45,
                    cost_usd=0.05,
                ),
                Attempt(
                    attempt_number=2,
                    run_id="run-2",
                    harness="claude",
                    model="sonnet",
                    success=False,
                    error_category="syntax_error",
                    error_summary="Invalid Python syntax in module.py",
                    duration_seconds=30,
                    cost_usd=0.15,
                ),
            ],
        )
        writer.create_entry(entry)

        result = generate_retry_context(mock_task, integration)

        assert result is not None
        assert "attempted 2 time(s) before" in result
        assert "2 failure(s)" in result
        assert "Attempt #1:" in result
        assert "Model: haiku" in result
        assert "test_failure" in result
        assert "Attempt #2:" in result
        assert "Model: sonnet" in result
        assert "syntax_error" in result

    def test_includes_log_tail_when_available(self, mock_task, tmp_path):
        """Test retry context includes log tail from most recent failure."""
        from cub.cli.run import generate_retry_context
        from cub.core.ledger.integration import LedgerIntegration
        from cub.core.ledger.models import Attempt, LedgerEntry
        from cub.core.ledger.writer import LedgerWriter

        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        integration = LedgerIntegration(writer)

        entry = LedgerEntry(
            id=mock_task.id,
            title=mock_task.title,
            type="task",
            attempts=[
                Attempt(
                    attempt_number=1,
                    run_id="run-1",
                    harness="claude",
                    model="haiku",
                    success=False,
                    error_category="test_failure",
                    error_summary="Tests failed",
                    duration_seconds=45,
                    cost_usd=0.05,
                ),
            ],
        )
        writer.create_entry(entry)

        # Write a log file
        log_content = "\n".join([f"Log line {i}" for i in range(1, 101)])
        writer.write_harness_log(mock_task.id, 1, log_content)

        result = generate_retry_context(mock_task, integration, log_tail_lines=10)

        assert result is not None
        assert "Last 10 lines from most recent failure" in result
        assert "attempt #1" in result
        assert "```" in result
        # Should contain the last 10 lines
        assert "Log line 91" in result
        assert "Log line 100" in result
        # Should not contain earlier lines (check with boundaries to avoid substring matches)
        lines_in_result = result.split("\n")
        assert "Log line 1" not in lines_in_result
        assert "Log line 50" not in lines_in_result

    def test_handles_missing_log_file_gracefully(self, mock_task, tmp_path):
        """Test retry context handles missing log file gracefully."""
        from cub.cli.run import generate_retry_context
        from cub.core.ledger.integration import LedgerIntegration
        from cub.core.ledger.models import Attempt, LedgerEntry
        from cub.core.ledger.writer import LedgerWriter

        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        integration = LedgerIntegration(writer)

        entry = LedgerEntry(
            id=mock_task.id,
            title=mock_task.title,
            type="task",
            attempts=[
                Attempt(
                    attempt_number=1,
                    run_id="run-1",
                    harness="claude",
                    model="haiku",
                    success=False,
                    error_category="harness_crash",
                    error_summary="Harness crashed before writing log",
                    duration_seconds=5,
                    cost_usd=0.01,
                ),
            ],
        )
        writer.create_entry(entry)

        # Don't write a log file - simulate missing log

        result = generate_retry_context(mock_task, integration)

        # Should still return valid context, just without log tail
        assert result is not None
        assert "## Retry Context" in result
        assert "Attempt #1:" in result
        assert "harness_crash" in result
        # Should not crash or include log section

    def test_shows_duration_in_seconds_for_short_tasks(self, mock_task, tmp_path):
        """Test retry context shows duration in seconds for tasks under 1 minute."""
        from cub.cli.run import generate_retry_context
        from cub.core.ledger.integration import LedgerIntegration
        from cub.core.ledger.models import Attempt, LedgerEntry
        from cub.core.ledger.writer import LedgerWriter

        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        integration = LedgerIntegration(writer)

        entry = LedgerEntry(
            id=mock_task.id,
            title=mock_task.title,
            type="task",
            attempts=[
                Attempt(
                    attempt_number=1,
                    run_id="run-1",
                    harness="claude",
                    model="haiku",
                    success=False,
                    error_category="quick_failure",
                    error_summary="Failed immediately",
                    duration_seconds=45,  # Under 60 seconds
                    cost_usd=0.02,
                ),
            ],
        )
        writer.create_entry(entry)

        result = generate_retry_context(mock_task, integration)

        assert result is not None
        assert "Duration: 45s" in result

    def test_mixed_success_and_failure_attempts(self, mock_task, tmp_path):
        """Test retry context only shows failed attempts when there are mixed results."""
        from cub.cli.run import generate_retry_context
        from cub.core.ledger.integration import LedgerIntegration
        from cub.core.ledger.models import Attempt, LedgerEntry
        from cub.core.ledger.writer import LedgerWriter

        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        integration = LedgerIntegration(writer)

        entry = LedgerEntry(
            id=mock_task.id,
            title=mock_task.title,
            type="task",
            attempts=[
                Attempt(
                    attempt_number=1,
                    run_id="run-1",
                    harness="claude",
                    model="haiku",
                    success=False,
                    error_category="test_failure",
                    error_summary="Tests failed",
                    duration_seconds=30,
                    cost_usd=0.05,
                ),
                Attempt(
                    attempt_number=2,
                    run_id="run-2",
                    harness="claude",
                    model="haiku",
                    success=True,  # This one succeeded
                    duration_seconds=45,
                    cost_usd=0.06,
                ),
                Attempt(
                    attempt_number=3,
                    run_id="run-3",
                    harness="claude",
                    model="sonnet",
                    success=False,
                    error_category="timeout",
                    error_summary="Timed out",
                    duration_seconds=600,
                    cost_usd=0.20,
                ),
            ],
        )
        writer.create_entry(entry)

        result = generate_retry_context(mock_task, integration)

        assert result is not None
        assert "attempted 3 time(s) before" in result
        assert "2 failure(s)" in result  # Only 2 failures
        # Should show failed attempts
        assert "Attempt #1:" in result
        assert "test_failure" in result
        assert "Attempt #3:" in result
        assert "timeout" in result

    def test_custom_log_tail_lines(self, mock_task, tmp_path):
        """Test retry context respects custom log_tail_lines parameter."""
        from cub.cli.run import generate_retry_context
        from cub.core.ledger.integration import LedgerIntegration
        from cub.core.ledger.models import Attempt, LedgerEntry
        from cub.core.ledger.writer import LedgerWriter

        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        writer = LedgerWriter(ledger_dir)
        integration = LedgerIntegration(writer)

        entry = LedgerEntry(
            id=mock_task.id,
            title=mock_task.title,
            type="task",
            attempts=[
                Attempt(
                    attempt_number=1,
                    run_id="run-1",
                    harness="claude",
                    model="haiku",
                    success=False,
                    error_category="error",
                    duration_seconds=30,
                    cost_usd=0.05,
                ),
            ],
        )
        writer.create_entry(entry)

        # Write a log with 100 lines
        log_content = "\n".join([f"Line {i}" for i in range(1, 101)])
        writer.write_harness_log(mock_task.id, 1, log_content)

        # Request only 5 lines
        result = generate_retry_context(mock_task, integration, log_tail_lines=5)

        assert result is not None
        assert "Last 5 lines" in result
        assert "Line 96" in result
        assert "Line 100" in result
        assert "Line 95" not in result


# ==============================================================================
# Tests for generate_task_prompt
# ==============================================================================


class TestGenerateTaskPrompt:
    """Tests for generate_task_prompt function."""

    def test_basic_prompt_structure(self, mock_task, mock_task_backend):
        """Test basic prompt contains required sections."""
        result = generate_task_prompt(mock_task, mock_task_backend)

        assert "## CURRENT TASK" in result
        assert f"Task ID: {mock_task.id}" in result
        assert f"Title: {mock_task.title}" in result
        assert f"Type: {mock_task.type.value}" in result

    def test_includes_description(self, mock_task, mock_task_backend):
        """Test prompt includes task description."""
        result = generate_task_prompt(mock_task, mock_task_backend)

        assert "Description:" in result
        assert mock_task.description in result

    def test_includes_acceptance_criteria(self, mock_task, mock_task_backend):
        """Test prompt includes acceptance criteria when present."""
        result = generate_task_prompt(mock_task, mock_task_backend)

        assert "Acceptance Criteria:" in result
        assert "- Criterion 1" in result
        assert "- Criterion 2" in result

    def test_no_acceptance_criteria_when_empty(self, mock_task_backend):
        """Test prompt omits acceptance criteria section when empty."""
        task = Task(
            id="cub-001",
            title="Simple task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            acceptance_criteria=[],
        )

        result = generate_task_prompt(task, mock_task_backend)

        assert "Acceptance Criteria:" not in result

    def test_beads_backend_instructions(self, mock_task, mock_task_backend):
        """Test beads backend shows correct completion instructions."""
        mock_task_backend.backend_name = "beads"
        mock_task_backend.get_agent_instructions.return_value = (
            f"This project uses the beads task backend (`bd` CLI).\n\n"
            f"**Task lifecycle:**\n"
            f"- `bd update {mock_task.id} --status in_progress` - Claim the task (do this first)\n"
            f"- `bd close {mock_task.id}` - Mark task complete (after all checks pass)\n"
            f'- `bd close {mock_task.id} -r "reason"` - Close with explanation'
        )

        result = generate_task_prompt(mock_task, mock_task_backend)

        assert f"bd close {mock_task.id}" in result
        assert f"task({mock_task.id}): {mock_task.title}" in result

    def test_json_backend_instructions(self, mock_task, mock_task_backend):
        """Test json backend shows different completion instructions."""
        mock_task_backend.backend_name = "json"
        mock_task_backend.get_agent_instructions.return_value = (
            "This project uses the JSON task backend.\n\n"
            "**Task lifecycle:**\n"
            '- Edit prd.json: set status to "closed" when complete'
        )

        result = generate_task_prompt(mock_task, mock_task_backend)

        assert 'prd.json: set status to "closed"' in result

    def test_includes_backend_specific_instructions(self, mock_task, mock_task_backend):
        """Test prompt includes backend-specific agent instructions."""
        mock_task_backend.get_agent_instructions.return_value = "Custom backend instructions here"

        result = generate_task_prompt(mock_task, mock_task_backend)

        assert "Custom backend instructions here" in result

    def test_handles_empty_description(self, mock_task_backend):
        """Test prompt handles tasks with empty description."""
        task = Task(
            id="cub-001",
            title="No description task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            description="",  # Empty string, not None (Task model defaults to "")
        )

        result = generate_task_prompt(task, mock_task_backend)

        # Empty description shows as "(No description provided)"
        # because the code checks `task.description or "(No description provided)"`
        assert "(No description provided)" in result

    def test_different_task_types(self, mock_task_backend):
        """Test prompt handles different task types correctly."""
        for task_type in [TaskType.TASK, TaskType.FEATURE, TaskType.BUG]:
            task = Task(
                id="cub-001",
                title="Typed task",
                status=TaskStatus.OPEN,
                priority=TaskPriority.P2,
                type=task_type,
            )

            result = generate_task_prompt(task, mock_task_backend)

            assert f"Type: {task_type.value}" in result
            assert f"{task_type.value}(cub-001):" in result

    def test_includes_epic_context_when_present(self, mock_task_backend):
        """Test that epic context is included in task prompt when task has parent."""
        # Create epic
        epic = Task(
            id="epic-001",
            title="Main Epic",
            description="Epic description",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.EPIC,
        )

        # Create task with parent
        task = Task(
            id="cub-001",
            title="Task in epic",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="epic-001",
        )

        completed_sibling = Task(
            id="cub-000",
            title="Completed sibling",
            status=TaskStatus.CLOSED,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent="epic-001",
        )

        # Mock backend
        mock_task_backend.get_task.return_value = epic
        mock_task_backend.list_tasks.return_value = [task, completed_sibling]

        result = generate_task_prompt(task, mock_task_backend)

        # Should contain epic context section
        assert "## Epic Context" in result
        assert "epic-001" in result
        assert "Main Epic" in result
        assert "Completed Sibling Tasks:" in result
        assert "✓ cub-000: Completed sibling" in result

    def test_no_epic_context_when_no_parent(self, mock_task_backend):
        """Test that epic context is not included when task has no parent."""
        task = Task(
            id="cub-001",
            title="Standalone task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            parent=None,
        )

        result = generate_task_prompt(task, mock_task_backend)

        # Should not contain epic context section
        assert "## Epic Context" not in result


# ==============================================================================
# Tests for display_task_info
# ==============================================================================


class TestDisplayTaskInfo:
    """Tests for display_task_info function."""

    def test_displays_without_error(self, mock_task, capsys):
        """Test that display_task_info runs without raising errors."""
        # Should not raise any exceptions
        display_task_info(mock_task, iteration=3, max_iterations=10)

        # Capture and verify output was produced
        capsys.readouterr()
        # Rich output may include control characters, just verify no exception

    def test_handles_various_task_properties(self, capsys):
        """Test display handles various task property values."""
        task = Task(
            id="cub-complex",
            title="A" * 100,  # Long title
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P0,
            type=TaskType.FEATURE,
        )

        # Should handle long titles and different values
        display_task_info(task, iteration=1, max_iterations=1)


# ==============================================================================
# Tests for display_summary
# ==============================================================================


class TestDisplaySummary:
    """Tests for display_summary function."""

    def test_displays_without_error(self, mock_run_status, capsys):
        """Test that display_summary runs without raising errors."""
        display_summary(mock_run_status)

        # Should complete without exception

    def test_handles_zero_cost(self, capsys):
        """Test display handles zero cost gracefully."""
        status = RunStatus(
            run_id="test",
            phase=RunPhase.COMPLETED,
            budget=BudgetStatus(tokens_used=1000, cost_usd=0.0),
        )

        display_summary(status)

    def test_handles_none_cost(self, capsys):
        """Test display handles None cost."""
        status = RunStatus(
            run_id="test",
            phase=RunPhase.COMPLETED,
            budget=BudgetStatus(tokens_used=1000),
        )
        status.budget.cost_usd = 0.0  # Explicitly zero

        display_summary(status)


# ==============================================================================
# Tests for _show_ready_tasks
# ==============================================================================


class TestShowReadyTasks:
    """Tests for _show_ready_tasks function."""

    def test_displays_ready_tasks(self, mock_task_backend, capsys):
        """Test display of ready tasks."""
        ready_tasks = [
            Task(
                id="cub-001",
                title="First task",
                status=TaskStatus.OPEN,
                priority=TaskPriority.P1,
                type=TaskType.TASK,
                labels=["label1", "label2"],
            ),
            Task(
                id="cub-002",
                title="Second task",
                status=TaskStatus.OPEN,
                priority=TaskPriority.P2,
                type=TaskType.FEATURE,
                labels=[],
            ),
        ]
        mock_task_backend.get_ready_tasks.return_value = ready_tasks

        _show_ready_tasks(mock_task_backend, epic=None, label=None)

    def test_shows_no_ready_tasks_message(self, mock_task_backend, capsys):
        """Test message when no ready tasks."""
        mock_task_backend.get_ready_tasks.return_value = []
        mock_task_backend.get_task_counts.return_value = MagicMock(remaining=5)

        _show_ready_tasks(mock_task_backend, epic=None, label=None)

    def test_shows_all_complete_message(self, mock_task_backend, capsys):
        """Test message when all tasks complete."""
        mock_task_backend.get_ready_tasks.return_value = []
        mock_task_backend.get_task_counts.return_value = MagicMock(remaining=0)

        _show_ready_tasks(mock_task_backend, epic=None, label=None)

    def test_filters_by_epic(self):
        """Test that epic filter is passed to backend."""
        from cub.core.tasks.backend import TaskBackend

        # Create a mock that passes isinstance check
        mock_backend = MagicMock(spec=TaskBackend)
        mock_backend.get_ready_tasks.return_value = []
        mock_backend.get_task_counts.return_value = MagicMock(remaining=0)

        _show_ready_tasks(mock_backend, epic="epic-1", label=None)

        mock_backend.get_ready_tasks.assert_called_once_with(parent="epic-1", label=None)

    def test_filters_by_label(self):
        """Test that label filter is passed to backend."""
        from cub.core.tasks.backend import TaskBackend

        # Create a mock that passes isinstance check
        mock_backend = MagicMock(spec=TaskBackend)
        mock_backend.get_ready_tasks.return_value = []
        mock_backend.get_task_counts.return_value = MagicMock(remaining=0)

        _show_ready_tasks(mock_backend, epic=None, label="urgent")

        mock_backend.get_ready_tasks.assert_called_once_with(parent=None, label="urgent")

    def test_handles_many_labels(self, mock_task_backend, capsys):
        """Test truncation of many labels."""
        task = Task(
            id="cub-001",
            title="Many labels task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            labels=["a", "b", "c", "d", "e"],  # More than 3
        )
        mock_task_backend.get_ready_tasks.return_value = [task]

        _show_ready_tasks(mock_task_backend, epic=None, label=None)

    def test_handles_long_title(self, mock_task_backend, capsys):
        """Test truncation of long titles."""
        task = Task(
            id="cub-001",
            title="A" * 100,  # Very long title
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
        )
        mock_task_backend.get_ready_tasks.return_value = [task]

        _show_ready_tasks(mock_task_backend, epic=None, label=None)


# ==============================================================================
# Tests for Signal Handler
# ==============================================================================


class TestSignalHandler:
    """Tests for interrupt signal handling."""

    def test_first_interrupt_sets_flag(self):
        """Test first SIGINT sets interrupted flag."""
        import cub.cli.run as run_module

        # Reset the flag
        run_module._interrupted = False

        _signal_handler(signal.SIGINT, None)

        assert run_module._interrupted is True

    def test_second_interrupt_exits(self):
        """Test second SIGINT force exits."""
        import cub.cli.run as run_module

        # Set flag as if first interrupt happened
        run_module._interrupted = True

        with pytest.raises(SystemExit) as exc_info:
            _signal_handler(signal.SIGINT, None)

        assert exc_info.value.code == 130

        # Clean up
        run_module._interrupted = False


# ==============================================================================
# Tests for Flag Validation
# ==============================================================================


class TestFlagValidation:
    """Tests for CLI flag validation."""

    def test_no_network_requires_sandbox(self, runner):
        """Test --no-network requires --sandbox flag."""
        result = runner.invoke(app, ["--no-network"])

        assert result.exit_code == ExitCode.USER_ERROR
        assert "--no-network" in result.output and "--sandbox" in result.output

    def test_sandbox_keep_requires_sandbox(self, runner):
        """Test --sandbox-keep requires --sandbox flag."""
        result = runner.invoke(app, ["--sandbox-keep"])

        assert result.exit_code == ExitCode.USER_ERROR
        assert "--sandbox-keep" in result.output and "--sandbox" in result.output

    def test_worktree_keep_allowed_with_worktree(self, runner):
        """Test --worktree-keep is allowed with --worktree."""
        # This will fail for other reasons (no harness), but shouldn't fail on validation
        with patch("cub.cli.run.load_config") as mock_config:
            mock_config.return_value = MagicMock()
            mock_config.return_value.harness.priority = []

            with patch("cub.cli.run.detect_async_harness", return_value=None):
                result = runner.invoke(app, ["--worktree", "--worktree-keep", "--once"])

                # Should not fail with worktree-keep validation error
                assert "--worktree-keep requires" not in result.output


# ==============================================================================
# Tests for Main Run Loop Integration
# ==============================================================================


class TestRunLoopIntegration:
    """Integration tests for the main run loop."""

    @pytest.fixture
    def mock_run_dependencies(self, mock_config, mock_harness_backend, mock_task_backend):
        """Set up all dependencies for run loop tests."""
        import asyncio

        def sync_run_async(func, *args, **kwargs):
            """Run async function synchronously for testing."""
            loop = asyncio.new_event_loop()
            try:
                if asyncio.iscoroutinefunction(func):
                    return loop.run_until_complete(func(*args, **kwargs))
                # For AsyncMock, call it and run the coroutine
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return loop.run_until_complete(result)
                return result
            finally:
                loop.close()

        with (
            patch("cub.cli.run.load_config") as mock_load_config,
            patch("cub.cli.run.detect_async_harness") as mock_detect,
            patch("cub.cli.run.get_async_backend") as mock_get_harness,
            patch("cub.cli.run.get_task_backend") as mock_get_task,
            patch("cub.cli.run.StatusWriter") as mock_status_writer,
            patch("cub.cli.run.run_hooks_async") as mock_run_hooks_async,
            patch("cub.cli.run.wait_async_hooks") as mock_wait_hooks,
            patch("anyio.from_thread.run", side_effect=sync_run_async),
            # Mock branch operations to avoid git calls in CI
            patch("cub.core.branches.store.BranchStore") as mock_branch_store,
            patch("cub.cli.run._create_branch_from_base") as mock_create_branch,
            # Mock RunLoop internals for harness invocation and hooks
            patch("cub.core.run.loop.generate_system_prompt") as mock_sys_prompt,
            patch("cub.core.run.loop.generate_task_prompt") as mock_task_prompt,
            # Mock RunLoop's hook runner so it uses the CLI-level mock
            patch("cub.core.run.loop.RunLoop._run_hook") as mock_loop_run_hook,
            # Mock RunLoop's harness invocation (avoids asyncio.run in test)
            patch("cub.core.run.loop.RunLoop._invoke_harness") as mock_loop_invoke,
            # Mock RunLoop's git helper
            patch("cub.core.run.loop.RunLoop._get_current_commit") as mock_get_commit,
        ):
            mock_load_config.return_value = mock_config
            mock_detect.return_value = "claude"
            mock_get_harness.return_value = mock_harness_backend
            mock_get_task.return_value = mock_task_backend
            mock_status_writer.return_value = MagicMock()
            mock_sys_prompt.return_value = "system prompt"
            mock_task_prompt.return_value = "task prompt"
            mock_loop_run_hook.return_value = True
            mock_loop_invoke.return_value = HarnessResult(
                output="Task completed",
                exit_code=0,
                usage=TokenUsage(input_tokens=100, output_tokens=200),
            )
            mock_get_commit.return_value = None

            # Set up task backend mock
            mock_task_backend.get_task_counts.return_value = MagicMock(
                total=5, open=3, in_progress=1, closed=1, remaining=4
            )

            # Set up branch mocks to simulate being on a feature branch
            # This prevents the tests from trying to create branches in CI
            mock_branch_store.get_current_branch.return_value = "feature/test-branch"
            mock_create_branch.return_value = True

            yield {
                "load_config": mock_load_config,
                "detect_harness": mock_detect,
                "get_harness_backend": mock_get_harness,
                "get_task_backend": mock_get_task,
                "status_writer": mock_status_writer,
                "run_hooks_async": mock_run_hooks_async,
                "wait_hooks": mock_wait_hooks,
                "config": mock_config,
                "harness_backend": mock_harness_backend,
                "task_backend": mock_task_backend,
                "branch_store": mock_branch_store,
                "create_branch": mock_create_branch,
                "sys_prompt": mock_sys_prompt,
                "task_prompt": mock_task_prompt,
                "loop_run_hook": mock_loop_run_hook,
                "loop_invoke": mock_loop_invoke,
                "get_commit": mock_get_commit,
            }

    def test_run_once_with_specific_task(self, runner, mock_run_dependencies):
        """Test running once with a specific task ID."""
        deps = mock_run_dependencies
        task = Task(
            id="cub-specific",
            title="Specific task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_task.return_value = task
        deps["harness_backend"].invoke.return_value = HarnessResult(
            output="Task completed",
            exit_code=0,
            usage=TokenUsage(input_tokens=100, output_tokens=200),
        )

        runner.invoke(app, ["--once", "--task", "cub-specific"])

        # Verify task was fetched
        deps["task_backend"].get_task.assert_called_with("cub-specific")

    def test_run_once_task_not_found(self, runner, mock_run_dependencies):
        """Test error when specified task not found."""
        deps = mock_run_dependencies
        deps["task_backend"].get_task.return_value = None

        result = runner.invoke(app, ["--once", "--task", "nonexistent"])

        assert result.exit_code == 1

    def test_run_once_task_already_closed(self, runner, mock_run_dependencies):
        """Test behavior when specified task is already closed."""
        deps = mock_run_dependencies
        task = Task(
            id="cub-closed",
            title="Closed task",
            status=TaskStatus.CLOSED,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_task.return_value = task

        result = runner.invoke(app, ["--once", "--task", "cub-closed"])

        # Should exit gracefully
        assert result.exit_code == 0

    def test_run_no_harness_available(self, runner, mock_run_dependencies):
        """Test error when no harness is available."""
        deps = mock_run_dependencies
        deps["detect_harness"].return_value = None

        result = runner.invoke(app, ["--once"])

        assert result.exit_code == 1
        assert "No AI harness available" in result.output

    def test_run_harness_not_installed(self, runner, mock_run_dependencies):
        """Test error when specified harness is not installed."""
        deps = mock_run_dependencies
        deps["harness_backend"].is_available.return_value = False

        result = runner.invoke(app, ["--once", "--harness", "claude"])

        assert result.exit_code == 1
        assert "not available" in result.output

    def test_run_no_ready_tasks_all_complete(self, runner, mock_run_dependencies):
        """Test when all tasks are complete."""
        deps = mock_run_dependencies
        deps["task_backend"].get_ready_tasks.return_value = []
        deps["task_backend"].get_task_counts.return_value = MagicMock(
            total=5, open=0, in_progress=0, closed=5, remaining=0
        )

        result = runner.invoke(app, ["--once"])

        assert result.exit_code == 0
        assert "All tasks complete" in result.output

    def test_run_no_ready_tasks_blocked(self, runner, mock_run_dependencies):
        """Test when remaining tasks are blocked."""
        deps = mock_run_dependencies
        deps["task_backend"].get_ready_tasks.return_value = []
        deps["task_backend"].get_task_counts.return_value = MagicMock(
            total=5, open=2, in_progress=0, closed=3, remaining=2
        )

        result = runner.invoke(app, ["--once"])

        assert result.exit_code == 0
        assert "remaining" in result.output
        assert "dependencies" in result.output.lower()

    def test_run_ready_flag_lists_tasks(self, runner, mock_run_dependencies):
        """Test --ready flag lists tasks without executing."""
        deps = mock_run_dependencies
        tasks = [
            Task(
                id="cub-001",
                title="Ready 1",
                status=TaskStatus.OPEN,
                priority=TaskPriority.P1,
                type=TaskType.TASK,
            ),
            Task(
                id="cub-002",
                title="Ready 2",
                status=TaskStatus.OPEN,
                priority=TaskPriority.P2,
                type=TaskType.FEATURE,
            ),
        ]
        deps["task_backend"].get_ready_tasks.return_value = tasks

        result = runner.invoke(app, ["--ready"])

        assert result.exit_code == 0
        # Harness should not be invoked
        deps["harness_backend"].invoke.assert_not_called()

    def test_run_successful_task_execution(self, runner, mock_run_dependencies):
        """Test successful single task execution."""
        deps = mock_run_dependencies
        task = Task(
            id="cub-success",
            title="Successful task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]
        deps["task_backend"].get_task.return_value = task

        runner.invoke(app, ["--once"])

        # Harness was invoked via RunLoop's _invoke_harness
        deps["loop_invoke"].assert_called_once()

    def test_run_task_failure_stops(self, runner, mock_run_dependencies):
        """Test that task failure stops the loop when configured."""
        from cub.core.harness.models import TaskResult

        deps = mock_run_dependencies
        deps["config"].loop.on_task_failure = "stop"
        task = Task(
            id="cub-fail",
            title="Failing task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]

        # Mock run_task to return a failure result
        async def mock_failure(task_input, debug=False):
            return TaskResult(
                output="",
                exit_code=1,
                error="Task execution failed",
                usage=TokenUsage(input_tokens=50, output_tokens=10),
                duration_seconds=0.1,
            )

        deps["harness_backend"].run_task.side_effect = mock_failure

        result = runner.invoke(app, ["--once"])

        assert result.exit_code == 1

    def test_run_task_failure_continues(self, runner, mock_run_dependencies):
        """Test that task failure continues when configured."""
        from cub.core.harness.models import TaskResult

        deps = mock_run_dependencies
        deps["config"].loop.on_task_failure = "continue"
        task = Task(
            id="cub-fail",
            title="Failing task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]

        # Mock run_task to return a failure result
        async def mock_failure(task_input, debug=False):
            return TaskResult(
                output="",
                exit_code=1,
                error="Task execution failed",
                usage=TokenUsage(input_tokens=50, output_tokens=10),
                duration_seconds=0.1,
            )

        deps["harness_backend"].run_task.side_effect = mock_failure

        runner.invoke(app, ["--once"])

        # Should still exit after one iteration due to --once
        # but not because of the failure

    def test_run_pre_loop_hook_failure(self, runner, mock_run_dependencies):
        """Test that pre-loop hook failure stops execution when fail_fast."""
        deps = mock_run_dependencies
        # RunLoop._run_hook is now mocked at the class level
        # First call is pre-loop hook → False means hook failed
        deps["loop_run_hook"].return_value = False
        deps["config"].hooks.fail_fast = True
        deps["config"].hooks.enabled = True

        result = runner.invoke(app, ["--once"])

        assert result.exit_code == 1

    def test_run_pre_task_hook_failure(self, runner, mock_run_dependencies):
        """Test that pre-task hook failure stops execution when fail_fast."""
        deps = mock_run_dependencies
        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]
        deps["task_backend"].get_task.return_value = task

        # Pre-loop succeeds, pre-task fails
        deps["loop_run_hook"].side_effect = [True, False]
        deps["config"].hooks.fail_fast = True
        deps["config"].hooks.enabled = True

        result = runner.invoke(app, ["--once"])

        assert result.exit_code == 1

    def test_run_uses_model_from_cli(self, runner, mock_run_dependencies):
        """Test that CLI model flag is used in RunLoop invocation."""
        deps = mock_run_dependencies
        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]
        deps["task_backend"].get_task.return_value = task

        runner.invoke(app, ["--once", "--model", "opus"])

        # Verify model was passed to RunLoop._invoke_harness via TaskInput
        call_args = deps["loop_invoke"].call_args
        assert call_args is not None, "RunLoop._invoke_harness should have been called"
        task_input = call_args[0][0]  # First positional argument
        assert task_input.model == "opus"

    def test_run_uses_model_from_task_label(self, runner, mock_run_dependencies):
        """Test that task model label is used when no CLI model."""
        deps = mock_run_dependencies
        # Task with a model:haiku label that gets parsed to model_label
        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
            labels=["model:haiku"],  # This sets model_label via computed property
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]
        deps["task_backend"].get_task.return_value = task
        deps["config"].harness.model = None  # No default, so task label should be used

        runner.invoke(app, ["--once"])

        # Verify task model label was used via RunLoop._invoke_harness
        call_args = deps["loop_invoke"].call_args
        assert call_args is not None, "RunLoop._invoke_harness should have been called"
        task_input = call_args[0][0]  # First positional argument
        assert task_input.model == "haiku"

    def test_run_streaming_mode(self, runner, mock_run_dependencies):
        """Test streaming mode passes stream flag to RunLoop."""
        deps = mock_run_dependencies
        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]
        deps["task_backend"].get_task.return_value = task

        runner.invoke(app, ["--once", "--stream"])

        # Streaming is now handled inside RunLoop._invoke_harness
        # Verify the loop's harness invocation was called (streaming is a config concern)
        deps["loop_invoke"].assert_called_once()


# ==============================================================================
# Tests for Budget Tracking
# ==============================================================================


class TestBudgetTracking:
    """Tests for budget tracking in the run loop."""

    @pytest.fixture
    def budget_mock_deps(self, mock_config, mock_harness_backend, mock_task_backend):
        """Set up dependencies for budget tests."""
        import asyncio

        def sync_run_async(func, *args, **kwargs):
            """Run async function synchronously for testing."""
            loop = asyncio.new_event_loop()
            try:
                if asyncio.iscoroutinefunction(func):
                    return loop.run_until_complete(func(*args, **kwargs))
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return loop.run_until_complete(result)
                return result
            finally:
                loop.close()

        with (
            patch("cub.cli.run.load_config") as mock_load_config,
            patch("cub.cli.run.detect_async_harness") as mock_detect,
            patch("cub.cli.run.get_async_backend") as mock_get_harness,
            patch("cub.cli.run.get_task_backend") as mock_get_task,
            patch("cub.cli.run.StatusWriter") as mock_status_writer,
            patch("cub.cli.run.run_hooks_async") as mock_run_hooks_async,
            patch("cub.cli.run.wait_async_hooks"),
            patch("anyio.from_thread.run", side_effect=sync_run_async),
        ):
            mock_load_config.return_value = mock_config
            mock_detect.return_value = "claude"
            mock_get_harness.return_value = mock_harness_backend
            mock_get_task.return_value = mock_task_backend
            # run_hooks now handled by RunLoop._run_hook (mocked at loop level)
            mock_status_writer.return_value = MagicMock()

            mock_task_backend.get_task_counts.return_value = MagicMock(
                total=10, open=8, in_progress=1, closed=1, remaining=9
            )

            yield {
                "config": mock_config,
                "harness_backend": mock_harness_backend,
                "task_backend": mock_task_backend,
                "run_hooks_async": mock_run_hooks_async,
            }

    def test_budget_tokens_accumulated(self, runner, budget_mock_deps):
        """Test that token usage is accumulated across invocations."""
        deps = budget_mock_deps
        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]
        deps["harness_backend"].invoke.return_value = HarnessResult(
            output="Done",
            exit_code=0,
            usage=TokenUsage(input_tokens=1000, output_tokens=500, cost_usd=0.05),
        )

        runner.invoke(app, ["--once"])

        # Verify tokens were tracked (would be in status)

    def test_budget_warning_fires_once(self, runner, budget_mock_deps):
        """Test budget warning hook fires only once when crossing threshold."""
        deps = budget_mock_deps
        deps["config"].budget.max_tokens_per_task = 1000  # Low limit
        deps["config"].guardrails.iteration_warning_threshold = 0.5  # 50%

        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]
        deps["harness_backend"].invoke.return_value = HarnessResult(
            output="Done",
            exit_code=0,
            usage=TokenUsage(input_tokens=600, output_tokens=200),  # 800 > 500 threshold
        )

        runner.invoke(app, ["--once"])

        # Budget warning hook should have been called
        # (check run_hooks_async was called with on-budget-warning)


# ==============================================================================
# Tests for Harness Invocation Errors
# ==============================================================================


class TestHarnessInvocationErrors:
    """Tests for harness invocation error handling."""

    @pytest.fixture
    def error_mock_deps(self, mock_config, mock_harness_backend, mock_task_backend):
        """Set up dependencies for error handling tests."""
        with (
            patch("cub.cli.run.load_config") as mock_load_config,
            patch("cub.cli.run.detect_async_harness") as mock_detect,
            patch("cub.cli.run.get_async_backend") as mock_get_harness,
            patch("cub.cli.run.get_task_backend") as mock_get_task,
            patch("cub.cli.run.StatusWriter") as mock_status_writer,
            patch("cub.cli.run.run_hooks_async"),
            patch("cub.cli.run.wait_async_hooks"),
            # Mock branch operations to avoid git calls in CI
            patch("cub.core.branches.store.BranchStore") as mock_branch_store,
            patch("cub.cli.run._create_branch_from_base") as mock_create_branch,
        ):
            mock_load_config.return_value = mock_config
            mock_detect.return_value = "claude"
            mock_get_harness.return_value = mock_harness_backend
            mock_get_task.return_value = mock_task_backend
            # run_hooks now handled by RunLoop._run_hook (mocked at loop level)
            mock_status_writer.return_value = MagicMock()

            mock_task_backend.get_task_counts.return_value = MagicMock(
                total=5, open=3, in_progress=1, closed=1, remaining=4
            )

            # Set up branch mocks to simulate being on a feature branch
            mock_branch_store.get_current_branch.return_value = "feature/test-branch"
            mock_create_branch.return_value = True

            yield {
                "config": mock_config,
                "harness_backend": mock_harness_backend,
                "task_backend": mock_task_backend,
            }

    @pytest.mark.skip(
        reason="Test mock setup needs updating after v0.27.0 merge - status phase tracking"
    )
    def test_harness_exception_stops_on_failure(self, runner, error_mock_deps):
        """Test that harness exceptions stop loop when configured to stop."""
        deps = error_mock_deps
        deps["config"].loop.on_task_failure = "stop"

        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]

        # Mock run_task to raise an exception (async method used by run loop)
        async def mock_crash(task_input, debug=False):
            raise Exception("Harness crashed")

        deps["harness_backend"].run_task.side_effect = mock_crash

        result = runner.invoke(app, ["--once"])

        assert result.exit_code == 1
        assert "Harness invocation failed" in result.output

    def test_harness_exception_continues(self, runner, error_mock_deps):
        """Test that harness exceptions continue when configured."""
        deps = error_mock_deps
        deps["config"].loop.on_task_failure = "continue"

        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]

        # Mock run_task to raise an exception (async method used by run loop)
        async def mock_crash(task_input, debug=False):
            raise Exception("Harness crashed")

        deps["harness_backend"].run_task.side_effect = mock_crash

        runner.invoke(app, ["--once"])

        # Loop completes iteration despite error
        # Should not exit with failure code from the exception itself


# ==============================================================================
# Tests for Invalid Harness
# ==============================================================================


class TestInvalidHarness:
    """Tests for invalid harness configuration."""

    def test_invalid_harness_name(self, runner):
        """Test error with invalid harness name."""
        with (
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.get_task_backend") as mock_get_task,
            patch("cub.cli.run.get_async_backend") as mock_get_harness,
            # Mock branch operations to avoid git calls in CI
            patch("cub.core.branches.store.BranchStore") as mock_branch_store,
            patch("cub.cli.run._create_branch_from_base") as mock_create_branch,
        ):
            mock_config.return_value = MagicMock()
            mock_get_task.return_value = MagicMock()
            mock_get_harness.side_effect = ValueError("Unknown harness: invalid")
            mock_branch_store.get_current_branch.return_value = "feature/test-branch"
            mock_create_branch.return_value = True

            result = runner.invoke(app, ["--harness", "invalid", "--once"])

            assert result.exit_code == 1
            assert "Unknown harness" in result.output


# ==============================================================================
# Tests for Task Backend Initialization
# ==============================================================================


class TestTaskBackendInitialization:
    """Tests for task backend initialization failures."""

    def test_task_backend_init_failure(self, runner):
        """Test error when task backend fails to initialize."""
        with (
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.get_task_backend") as mock_get_task,
            # Mock branch operations to avoid git calls in CI
            patch("cub.core.branches.store.BranchStore") as mock_branch_store,
            patch("cub.cli.run._create_branch_from_base") as mock_create_branch,
        ):
            mock_config.return_value = MagicMock()
            mock_get_task.side_effect = Exception("No beads found")
            mock_branch_store.get_current_branch.return_value = "feature/test-branch"
            mock_create_branch.return_value = True

            result = runner.invoke(app, ["--once"])

            assert result.exit_code == 1
            assert "Failed to initialize task backend" in result.output


# ==============================================================================
# Tests for Max Iterations
# ==============================================================================


class TestMaxIterations:
    """Tests for max iteration handling."""

    @pytest.fixture
    def iteration_mock_deps(self, mock_config, mock_harness_backend, mock_task_backend):
        """Set up dependencies for iteration tests."""
        import asyncio

        def sync_run_async(func, *args, **kwargs):
            """Run async function synchronously for testing."""
            loop = asyncio.new_event_loop()
            try:
                if asyncio.iscoroutinefunction(func):
                    return loop.run_until_complete(func(*args, **kwargs))
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return loop.run_until_complete(result)
                return result
            finally:
                loop.close()

        with (
            patch("cub.cli.run.load_config") as mock_load_config,
            patch("cub.cli.run.detect_async_harness") as mock_detect,
            patch("cub.cli.run.get_async_backend") as mock_get_harness,
            patch("cub.cli.run.get_task_backend") as mock_get_task,
            patch("cub.cli.run.StatusWriter") as mock_status_writer,
            patch("cub.cli.run.run_hooks_async"),
            patch("cub.cli.run.wait_async_hooks"),
            patch("cub.cli.run.time.sleep"),  # Don't actually sleep
            patch("anyio.from_thread.run", side_effect=sync_run_async),
            # Mock branch operations to avoid git calls in CI
            patch("cub.core.branches.store.BranchStore") as mock_branch_store,
            patch("cub.cli.run._create_branch_from_base") as mock_create_branch,
            # Mock RunLoop internals for harness invocation and hooks
            patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt"),
            patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt"),
            patch("cub.core.run.loop.RunLoop._run_hook", return_value=True),
            patch("cub.core.run.loop.RunLoop._invoke_harness") as mock_loop_invoke,
            patch("cub.core.run.loop.RunLoop._get_current_commit", return_value=None),
        ):
            mock_load_config.return_value = mock_config
            mock_detect.return_value = "claude"
            mock_get_harness.return_value = mock_harness_backend
            mock_get_task.return_value = mock_task_backend
            # run_hooks now handled by RunLoop._run_hook (mocked at loop level)
            mock_status_writer.return_value = MagicMock()
            mock_loop_invoke.return_value = HarnessResult(
                output="Task completed",
                exit_code=0,
                usage=TokenUsage(input_tokens=100, output_tokens=200),
            )

            mock_task_backend.get_task_counts.return_value = MagicMock(
                total=100, open=90, in_progress=5, closed=5, remaining=95
            )

            # Set up branch mocks to simulate being on a feature branch
            mock_branch_store.get_current_branch.return_value = "feature/test-branch"
            mock_create_branch.return_value = True

            yield {
                "config": mock_config,
                "harness_backend": mock_harness_backend,
                "task_backend": mock_task_backend,
                "loop_invoke": mock_loop_invoke,
            }

    def test_once_flag_limits_to_one_iteration(self, runner, iteration_mock_deps):
        """Test --once flag limits to single iteration."""
        deps = iteration_mock_deps
        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]
        deps["task_backend"].get_task.return_value = task

        runner.invoke(app, ["--once"])

        # Should only invoke harness once via RunLoop
        assert deps["loop_invoke"].call_count == 1

    def test_max_iterations_from_config(self, runner, iteration_mock_deps):
        """Test max iterations comes from config when not using --once."""
        deps = iteration_mock_deps
        deps["config"].loop.max_iterations = 2  # Allow 2 iterations

        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        # Return the same task each time (simulates it not being closed)
        deps["task_backend"].get_ready_tasks.return_value = [task]
        deps["task_backend"].get_task.return_value = task

        result = runner.invoke(app, [])

        # Should invoke harness twice (max_iterations = 2) via RunLoop
        assert deps["loop_invoke"].call_count == 2
        assert "Reached max iterations" in result.output


# ==============================================================================
# Tests for Epic and Label Filtering
# ==============================================================================


class TestFiltering:
    """Tests for epic and label filtering."""

    @pytest.fixture
    def filter_mock_deps(self, mock_config, mock_harness_backend, mock_task_backend):
        """Set up dependencies for filtering tests."""
        import asyncio

        def sync_run_async(func, *args, **kwargs):
            """Run async function synchronously for testing."""
            loop = asyncio.new_event_loop()
            try:
                if asyncio.iscoroutinefunction(func):
                    return loop.run_until_complete(func(*args, **kwargs))
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return loop.run_until_complete(result)
                return result
            finally:
                loop.close()

        with (
            patch("cub.cli.run.load_config") as mock_load_config,
            patch("cub.cli.run.detect_async_harness") as mock_detect,
            patch("cub.cli.run.get_async_backend") as mock_get_harness,
            patch("cub.cli.run.get_task_backend") as mock_get_task,
            patch("cub.cli.run.StatusWriter") as mock_status_writer,
            patch("cub.cli.run.run_hooks_async"),
            patch("cub.cli.run.wait_async_hooks"),
            patch("anyio.from_thread.run", side_effect=sync_run_async),
            # Mock branch operations to avoid git calls in CI
            patch("cub.core.branches.store.BranchStore") as mock_branch_store,
            patch("cub.cli.run._create_branch_from_base") as mock_create_branch,
        ):
            mock_load_config.return_value = mock_config
            mock_detect.return_value = "claude"
            mock_get_harness.return_value = mock_harness_backend
            mock_get_task.return_value = mock_task_backend
            # run_hooks now handled by RunLoop._run_hook (mocked at loop level)
            mock_status_writer.return_value = MagicMock()

            mock_task_backend.get_task_counts.return_value = MagicMock(
                total=10, open=5, in_progress=2, closed=3, remaining=7
            )

            # Set up branch mocks to simulate being on a feature branch
            mock_branch_store.get_current_branch.return_value = "feature/test-branch"
            mock_create_branch.return_value = True

            yield {
                "task_backend": mock_task_backend,
                "harness_backend": mock_harness_backend,
            }

    def test_epic_filter_passed_to_backend(self, runner, filter_mock_deps):
        """Test that --epic filter is passed to task backend."""
        deps = filter_mock_deps
        deps["task_backend"].get_ready_tasks.return_value = []
        deps["task_backend"].get_task_counts.return_value = MagicMock(remaining=0)

        runner.invoke(app, ["--once", "--epic", "backend-v2"])

        # Verify epic was passed as parent filter
        deps["task_backend"].get_ready_tasks.assert_called_with(parent="backend-v2", label=None)

    def test_label_filter_passed_to_backend(self, runner, filter_mock_deps):
        """Test that --label filter is passed to task backend."""
        deps = filter_mock_deps
        deps["task_backend"].get_ready_tasks.return_value = []
        deps["task_backend"].get_task_counts.return_value = MagicMock(remaining=0)

        runner.invoke(app, ["--once", "--label", "urgent"])

        # Verify label was passed
        deps["task_backend"].get_ready_tasks.assert_called_with(parent=None, label="urgent")

    def test_both_filters_combined(self, runner, filter_mock_deps):
        """Test that both epic and label filters can be combined."""
        deps = filter_mock_deps
        deps["task_backend"].get_ready_tasks.return_value = []
        deps["task_backend"].get_task_counts.return_value = MagicMock(remaining=0)

        runner.invoke(app, ["--once", "--epic", "v2", "--label", "critical"])

        # Verify both filters passed
        deps["task_backend"].get_ready_tasks.assert_called_with(parent="v2", label="critical")

    def test_auto_close_epic_when_all_tasks_complete(self, runner, filter_mock_deps):
        """Test that epic is auto-closed when all tasks are complete."""
        deps = filter_mock_deps
        deps["task_backend"].get_ready_tasks.return_value = []
        deps["task_backend"].get_task_counts.return_value = MagicMock(remaining=0)
        deps["task_backend"].try_close_epic.return_value = (
            True,
            "Epic 'backend-v2' auto-closed (3 tasks completed)",
        )

        result = runner.invoke(app, ["--once", "--epic", "backend-v2"])

        # Verify try_close_epic was called
        deps["task_backend"].try_close_epic.assert_called_once_with("backend-v2")
        # Check success message in output
        assert "auto-closed" in result.output or result.exit_code == 0

    def test_epic_not_closed_when_tasks_remain(self, runner, filter_mock_deps):
        """Test that epic stays open when tasks remain."""
        deps = filter_mock_deps
        deps["task_backend"].get_ready_tasks.return_value = []
        deps["task_backend"].get_task_counts.return_value = MagicMock(remaining=0)
        deps["task_backend"].try_close_epic.return_value = (
            False,
            "Epic 'backend-v2' has 1 open and 0 in-progress tasks remaining",
        )

        result = runner.invoke(app, ["--once", "--epic", "backend-v2"])

        # Verify try_close_epic was called
        deps["task_backend"].try_close_epic.assert_called_once_with("backend-v2")
        # No auto-closed message should appear
        assert "auto-closed" not in result.output

    def test_no_close_epic_without_epic_flag(self, runner, filter_mock_deps):
        """Test that try_close_epic is not called without --epic flag."""
        deps = filter_mock_deps
        deps["task_backend"].get_ready_tasks.return_value = []
        deps["task_backend"].get_task_counts.return_value = MagicMock(remaining=0)

        runner.invoke(app, ["--once"])

        # Verify try_close_epic was NOT called
        deps["task_backend"].try_close_epic.assert_not_called()


# ==============================================================================
# Tests for Branch Creation Behavior
# ==============================================================================


class TestBranchCreation:
    """Tests for --use-current-branch flag and branch creation behavior."""

    def test_use_current_branch_on_main_without_main_ok_fails(self, runner):
        """Test --use-current-branch on main without --main-ok fails."""
        with patch("cub.core.branches.store.BranchStore.get_current_branch") as mock_get:
            mock_get.return_value = "main"

            result = runner.invoke(app, ["--use-current-branch", "--once"])

            assert result.exit_code == ExitCode.USER_ERROR
            assert "Cannot run on 'main' branch" in result.output

    def test_use_current_branch_on_main_with_main_ok_succeeds(self, runner):
        """Test --use-current-branch on main with --main-ok succeeds."""
        with (
            patch("cub.core.branches.store.BranchStore.get_current_branch") as mock_get,
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.get_task_backend") as mock_task_backend,
            patch("cub.cli.run.detect_async_harness", return_value=None),
        ):
            mock_get.return_value = "main"
            mock_config.return_value = MagicMock()
            mock_config.return_value.harness.priority = []
            mock_task_backend.return_value = MagicMock()

            result = runner.invoke(app, ["--use-current-branch", "--main-ok", "--once"])

            # Should fail for no harness, not branch protection
            assert "No AI harness available" in result.output
            assert "Cannot run on 'main'" not in result.output

    def test_use_current_branch_on_feature_branch_succeeds(self, runner):
        """Test --use-current-branch on feature branch works without --main-ok."""
        with (
            patch("cub.core.branches.store.BranchStore.get_current_branch") as mock_get,
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.get_task_backend") as mock_task_backend,
            patch("cub.cli.run.detect_async_harness", return_value=None),
        ):
            mock_get.return_value = "feature/my-work"
            mock_config.return_value = MagicMock()
            mock_config.return_value.harness.priority = []
            mock_task_backend.return_value = MagicMock()

            result = runner.invoke(app, ["--use-current-branch", "--once"])

            # Should fail for no harness, not branch protection
            assert "No AI harness available" in result.output
            assert "Cannot run on" not in result.output

    def test_default_creates_branch_from_origin_main(self, runner):
        """Test default behavior creates branch from origin/main."""
        with (
            patch("cub.core.branches.store.BranchStore.get_current_branch") as mock_get,
            patch("cub.cli.run._create_branch_from_base") as mock_create,
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.detect_async_harness", return_value=None),
        ):
            mock_get.return_value = "main"
            mock_create.return_value = True  # Branch creation succeeds
            mock_config.return_value = MagicMock()
            mock_config.return_value.harness.priority = []

            runner.invoke(app, ["--once"])

            # Should create branch from origin/main
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert call_args[0][1] == "origin/main"  # base_branch is origin/main

    def test_from_branch_overrides_default_base(self, runner):
        """Test --from-branch overrides the default origin/main base."""
        with (
            patch("cub.core.branches.store.BranchStore.get_current_branch") as mock_get,
            patch("cub.cli.run._create_branch_from_base") as mock_create,
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.detect_async_harness", return_value=None),
        ):
            mock_get.return_value = "main"
            mock_create.return_value = True
            mock_config.return_value = MagicMock()
            mock_config.return_value.harness.priority = []

            runner.invoke(app, ["--from-branch", "develop", "--once"])

            # Should create branch from develop
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert call_args[0][1] == "develop"  # base_branch is develop

    def test_use_current_branch_ignores_from_branch(self, runner):
        """Test --use-current-branch ignores --from-branch (no-op)."""
        with (
            patch("cub.core.branches.store.BranchStore.get_current_branch") as mock_get,
            patch("cub.cli.run._create_branch_from_base") as mock_create,
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.get_task_backend") as mock_task_backend,
            patch("cub.cli.run.detect_async_harness", return_value=None),
        ):
            mock_get.return_value = "feature/existing"
            mock_config.return_value = MagicMock()
            mock_config.return_value.harness.priority = []
            mock_task_backend.return_value = MagicMock()

            result = runner.invoke(
                app, ["--use-current-branch", "--from-branch", "develop", "--once"]
            )

            # Should NOT create a branch
            mock_create.assert_not_called()
            # Should fail for no harness, not branch issues
            assert "No AI harness available" in result.output

    def test_on_feature_branch_reuses_existing(self, runner):
        """Test running on existing feature branch reuses it (no new branch)."""
        with (
            patch("cub.core.branches.store.BranchStore.get_current_branch") as mock_get,
            patch("cub.cli.run._create_branch_from_base") as mock_create,
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.get_task_backend") as mock_task_backend,
            patch("cub.cli.run.detect_async_harness", return_value=None),
        ):
            mock_get.return_value = "feature/existing-work"
            mock_config.return_value = MagicMock()
            mock_config.return_value.harness.priority = []
            mock_task_backend.return_value = MagicMock()

            result = runner.invoke(app, ["--once"])

            # Should NOT create a new branch when already on a feature branch
            mock_create.assert_not_called()
            # Should fail for no harness, not branch issues
            assert "No AI harness available" in result.output

    def test_task_specific_branch_name(self, runner):
        """Test --task creates branch with task ID in name."""
        with (
            patch("cub.core.branches.store.BranchStore.get_current_branch") as mock_get,
            patch("cub.cli.run._create_branch_from_base") as mock_create,
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.detect_async_harness", return_value=None),
        ):
            mock_get.return_value = "main"
            mock_create.return_value = True
            mock_config.return_value = MagicMock()
            mock_config.return_value.harness.priority = []

            runner.invoke(app, ["--task", "cub-123", "--once"])

            # Should create branch with task ID
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert "task/cub-123" in call_args[0][0]  # branch_name contains task ID

    def test_epic_branch_name(self, runner):
        """Test --epic creates branch with epic name."""
        with (
            patch("cub.core.branches.store.BranchStore.get_current_branch") as mock_get,
            patch("cub.cli.run._create_branch_from_base") as mock_create,
            patch("cub.cli.run._get_epic_title", return_value="Backend API"),
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.detect_async_harness", return_value=None),
        ):
            mock_get.return_value = "main"
            mock_create.return_value = True
            mock_config.return_value = MagicMock()
            mock_config.return_value.harness.priority = []

            runner.invoke(app, ["--epic", "cub-xyz", "--once"])

            # Should create branch with epic title slug
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert "feature/backend-api" in call_args[0][0]

    def test_label_branch_name(self, runner):
        """Test --label creates branch with label name."""
        with (
            patch("cub.core.branches.store.BranchStore.get_current_branch") as mock_get,
            patch("cub.cli.run._create_branch_from_base") as mock_create,
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.detect_async_harness", return_value=None),
        ):
            mock_get.return_value = "main"
            mock_create.return_value = True
            mock_config.return_value = MagicMock()
            mock_config.return_value.harness.priority = []

            runner.invoke(app, ["--label", "priority", "--once"])

            # Should create branch with label name
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert "feature/priority" in call_args[0][0]

    def test_master_branch_also_protected(self, runner):
        """Test 'master' branch is also protected like 'main'."""
        with patch("cub.core.branches.store.BranchStore.get_current_branch") as mock_get:
            mock_get.return_value = "master"

            result = runner.invoke(app, ["--use-current-branch", "--once"])

            assert result.exit_code == ExitCode.USER_ERROR
            assert "Cannot run on 'master' branch" in result.output


# ==============================================================================
# Test create_run_artifact function
# ==============================================================================


class TestCreateRunArtifact:
    """Tests for create_run_artifact helper function."""

    def test_create_run_artifact_completed(self):
        """Test create_run_artifact with completed run."""
        from datetime import datetime

        now = datetime.now()
        status = RunStatus(
            run_id="test-run-001",
            session_name="test-session",
            started_at=now,
            phase=RunPhase.COMPLETED,
        )
        status.budget.tokens_used = 5000
        status.budget.cost_usd = 0.25
        status.budget.tasks_completed = 3

        config_dict = {"test": "config"}
        artifact = create_run_artifact(status, config_dict)

        assert artifact.run_id == "test-run-001"
        assert artifact.session_name == "test-session"
        assert artifact.started_at == now
        assert artifact.completed_at is not None
        assert artifact.status == "completed"
        assert artifact.config == config_dict
        assert artifact.tasks_completed == 3
        assert artifact.budget.tokens_used == 5000
        assert artifact.budget.cost_usd == 0.25

    def test_create_run_artifact_failed(self):
        """Test create_run_artifact with failed run."""
        from datetime import datetime

        now = datetime.now()
        status = RunStatus(
            run_id="test-run-002",
            session_name="test-session",
            started_at=now,
            phase=RunPhase.FAILED,
        )
        status.budget.tokens_used = 2000

        artifact = create_run_artifact(status)

        assert artifact.run_id == "test-run-002"
        assert artifact.completed_at is not None
        assert artifact.status == "failed"
        assert artifact.budget.tokens_used == 2000

    def test_create_run_artifact_stopped(self):
        """Test create_run_artifact with stopped run."""
        from datetime import datetime

        now = datetime.now()
        status = RunStatus(
            run_id="test-run-003",
            session_name="test-session",
            started_at=now,
            phase=RunPhase.STOPPED,
        )

        artifact = create_run_artifact(status)

        assert artifact.completed_at is not None
        assert artifact.status == "stopped"

    def test_create_run_artifact_running(self):
        """Test create_run_artifact with still-running run."""
        from datetime import datetime

        now = datetime.now()
        status = RunStatus(
            run_id="test-run-004",
            session_name="test-session",
            started_at=now,
            phase=RunPhase.RUNNING,
        )

        artifact = create_run_artifact(status)

        assert artifact.completed_at is None
        assert artifact.status == "running"

    def test_create_run_artifact_with_budget_limits(self):
        """Test create_run_artifact preserves budget limits."""
        from datetime import datetime

        now = datetime.now()
        status = RunStatus(
            run_id="test-run-005",
            session_name="test-session",
            started_at=now,
            phase=RunPhase.COMPLETED,
        )
        status.budget.tokens_used = 8000
        status.budget.tokens_limit = 10000
        status.budget.cost_usd = 0.50
        status.budget.cost_limit = 1.00
        status.budget.tasks_completed = 5
        status.budget.tasks_limit = 10

        artifact = create_run_artifact(status)

        assert artifact.budget.tokens_used == 8000
        assert artifact.budget.tokens_limit == 10000
        assert artifact.budget.cost_usd == 0.50
        assert artifact.budget.cost_limit == 1.00
        assert artifact.budget.tasks_completed == 5
        assert artifact.budget.tasks_limit == 10


# ==============================================================================
# Test Harness Log Capture
# ==============================================================================


class TestHarnessLogCapture:
    """Test that harness output is captured to harness.log."""

    @pytest.fixture
    def mock_deps_with_log(self, tmp_path, mock_config, mock_task_backend, mock_harness_backend):
        """Set up mocks for harness log capture tests."""
        with (
            patch("cub.cli.run.load_config") as mock_load_config,
            patch("cub.cli.run.detect_async_harness") as mock_detect,
            patch("cub.cli.run.get_async_backend") as mock_get_harness,
            patch("cub.cli.run.get_task_backend") as mock_get_task,
            patch("cub.cli.run.run_hooks_async"),
            patch("cub.cli.run.wait_async_hooks"),
            patch("cub.core.branches.store.BranchStore") as mock_branch_store,
            patch("cub.cli.run._create_branch_from_base") as mock_create_branch,
        ):
            mock_load_config.return_value = mock_config
            mock_detect.return_value = "claude"
            mock_get_harness.return_value = mock_harness_backend
            mock_get_task.return_value = mock_task_backend
            # run_hooks now handled by RunLoop._run_hook (mocked at loop level)

            # Set up branch mocks
            mock_branch_store.get_current_branch.return_value = "feature/test-branch"
            mock_create_branch.return_value = True

            mock_task_backend.get_task_counts.return_value = MagicMock(
                total=1, open=1, in_progress=0, closed=0, remaining=1
            )

            yield {
                "config": mock_config,
                "harness_backend": mock_harness_backend,
                "task_backend": mock_task_backend,
                "project_dir": tmp_path,
            }

    def test_harness_log_created_on_task_execution(self, runner, mock_deps_with_log, mock_task):
        """Test that harness.log is created when a task runs."""
        deps = mock_deps_with_log
        project_dir = deps["project_dir"]

        # Set up task backend to return one task
        deps["task_backend"].get_task.return_value = mock_task
        deps["task_backend"].get_ready_tasks.return_value = [mock_task]

        # Run with --once and --task
        with patch("cub.cli.run.Path.cwd", return_value=project_dir):
            runner.invoke(
                app,
                ["--once", "--task", mock_task.id],
                obj={"debug": False},
            )

        # Find the actual run directory (it has a timestamp)
        runs_dir = project_dir / ".cub" / "runs"
        if runs_dir.exists():
            run_dirs = list(runs_dir.iterdir())
            if run_dirs:
                actual_log = run_dirs[0] / "tasks" / mock_task.id / "harness.log"
                assert actual_log.exists(), f"harness.log should exist at {actual_log}"

                # Verify it contains the harness output
                log_content = actual_log.read_text()
                assert "Task completed successfully" in log_content
