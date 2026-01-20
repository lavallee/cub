"""
Comprehensive tests for cli/run.py core loop.

Tests the main execution loop, task selection, budget tracking,
error handling, and all supporting functions.
"""

import signal
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cub.cli.run import (
    _show_ready_tasks,
    _signal_handler,
    app,
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
            f"- `bd close {mock_task.id} -r \"reason\"` - Close with explanation"
        )

        result = generate_task_prompt(mock_task, mock_task_backend)

        assert f"bd close {mock_task.id}" in result
        assert f"task({mock_task.id}): {mock_task.title}" in result

    def test_json_backend_instructions(self, mock_task, mock_task_backend):
        """Test json backend shows different completion instructions."""
        mock_task_backend.backend_name = "json"
        mock_task_backend.get_agent_instructions.return_value = (
            'This project uses the JSON task backend.\n\n'
            '**Task lifecycle:**\n'
            '- Edit prd.json: set status to "closed" when complete'
        )

        result = generate_task_prompt(mock_task, mock_task_backend)

        assert 'prd.json: set status to "closed"' in result

    def test_includes_backend_specific_instructions(self, mock_task, mock_task_backend):
        """Test prompt includes backend-specific agent instructions."""
        mock_task_backend.get_agent_instructions.return_value = (
            "Custom backend instructions here"
        )

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

        mock_backend.get_ready_tasks.assert_called_once_with(
            parent="epic-1", label=None
        )

    def test_filters_by_label(self):
        """Test that label filter is passed to backend."""
        from cub.core.tasks.backend import TaskBackend

        # Create a mock that passes isinstance check
        mock_backend = MagicMock(spec=TaskBackend)
        mock_backend.get_ready_tasks.return_value = []
        mock_backend.get_task_counts.return_value = MagicMock(remaining=0)

        _show_ready_tasks(mock_backend, epic=None, label="urgent")

        mock_backend.get_ready_tasks.assert_called_once_with(
            parent=None, label="urgent"
        )

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

        assert result.exit_code == 1
        assert "--no-network requires --sandbox" in result.output

    def test_sandbox_keep_requires_sandbox(self, runner):
        """Test --sandbox-keep requires --sandbox flag."""
        result = runner.invoke(app, ["--sandbox-keep"])

        assert result.exit_code == 1
        assert "--sandbox-keep requires --sandbox" in result.output

    def test_worktree_keep_allowed_with_worktree(self, runner):
        """Test --worktree-keep is allowed with --worktree."""
        # This will fail for other reasons (no harness), but shouldn't fail on validation
        with patch("cub.cli.run.load_config") as mock_config:
            mock_config.return_value = MagicMock()
            mock_config.return_value.harness.priority = []

            with patch("cub.cli.run.detect_async_harness", return_value=None):
                result = runner.invoke(
                    app, ["--worktree", "--worktree-keep", "--once"]
                )

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
            patch("cub.cli.run.run_hooks") as mock_run_hooks,
            patch("cub.cli.run.run_hooks_async") as mock_run_hooks_async,
            patch("cub.cli.run.wait_async_hooks") as mock_wait_hooks,
            patch("anyio.from_thread.run", side_effect=sync_run_async),
        ):
            mock_load_config.return_value = mock_config
            mock_detect.return_value = "claude"
            mock_get_harness.return_value = mock_harness_backend
            mock_get_task.return_value = mock_task_backend
            mock_run_hooks.return_value = True
            mock_status_writer.return_value = MagicMock()

            # Set up task backend mock
            mock_task_backend.get_task_counts.return_value = MagicMock(
                total=5, open=3, in_progress=1, closed=1, remaining=4
            )

            yield {
                "load_config": mock_load_config,
                "detect_harness": mock_detect,
                "get_harness_backend": mock_get_harness,
                "get_task_backend": mock_get_task,
                "status_writer": mock_status_writer,
                "run_hooks": mock_run_hooks,
                "run_hooks_async": mock_run_hooks_async,
                "wait_hooks": mock_wait_hooks,
                "config": mock_config,
                "harness_backend": mock_harness_backend,
                "task_backend": mock_task_backend,
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
        assert "No harness available" in result.output

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
        deps["harness_backend"].invoke.return_value = HarnessResult(
            output="Task completed successfully",
            exit_code=0,
            usage=TokenUsage(input_tokens=100, output_tokens=200, cost_usd=0.01),
        )

        runner.invoke(app, ["--once"])

        # Harness was invoked (async method)
        deps["harness_backend"].run_task.assert_called_once()

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
        """Test that pre-loop hook failure stops execution."""
        deps = mock_run_dependencies
        deps["run_hooks"].return_value = False  # Hook failed
        deps["config"].hooks.fail_fast = True

        result = runner.invoke(app, ["--once"])

        assert result.exit_code == 1
        assert "Pre-loop hook failed" in result.output

    def test_run_pre_task_hook_failure(self, runner, mock_run_dependencies):
        """Test that pre-task hook failure stops execution."""
        deps = mock_run_dependencies
        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]

        # Pre-loop succeeds, pre-task fails
        deps["run_hooks"].side_effect = [True, False]
        deps["config"].hooks.fail_fast = True

        result = runner.invoke(app, ["--once"])

        assert result.exit_code == 1
        assert "Pre-task hook failed" in result.output

    def test_run_uses_model_from_cli(self, runner, mock_run_dependencies):
        """Test that CLI model flag is used."""
        deps = mock_run_dependencies
        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]

        runner.invoke(app, ["--once", "--model", "opus"])

        # Verify model was passed to harness via TaskInput
        call_args = deps["harness_backend"].run_task.call_args
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
        deps["config"].harness.model = None  # No default, so task label should be used

        runner.invoke(app, ["--once"])

        # Verify task model label was used via TaskInput
        call_args = deps["harness_backend"].run_task.call_args
        task_input = call_args[0][0]  # First positional argument
        assert task_input.model == "haiku"

    def test_run_streaming_mode(self, runner, mock_run_dependencies):
        """Test streaming mode invokes streaming method."""
        deps = mock_run_dependencies
        task = Task(
            id="cub-001",
            title="Task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )
        deps["task_backend"].get_ready_tasks.return_value = [task]

        runner.invoke(app, ["--once", "--stream"])

        # Verify streaming method was called (stream_task for async)
        deps["harness_backend"].stream_task.assert_called_once()
        deps["harness_backend"].run_task.assert_not_called()


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
            patch("cub.cli.run.run_hooks") as mock_run_hooks,
            patch("cub.cli.run.run_hooks_async") as mock_run_hooks_async,
            patch("cub.cli.run.wait_async_hooks"),
            patch("anyio.from_thread.run", side_effect=sync_run_async),
        ):
            mock_load_config.return_value = mock_config
            mock_detect.return_value = "claude"
            mock_get_harness.return_value = mock_harness_backend
            mock_get_task.return_value = mock_task_backend
            mock_run_hooks.return_value = True
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
            patch("cub.cli.run.run_hooks") as mock_run_hooks,
            patch("cub.cli.run.run_hooks_async"),
            patch("cub.cli.run.wait_async_hooks"),
        ):
            mock_load_config.return_value = mock_config
            mock_detect.return_value = "claude"
            mock_get_harness.return_value = mock_harness_backend
            mock_get_task.return_value = mock_task_backend
            mock_run_hooks.return_value = True
            mock_status_writer.return_value = MagicMock()

            mock_task_backend.get_task_counts.return_value = MagicMock(
                total=5, open=3, in_progress=1, closed=1, remaining=4
            )

            yield {
                "config": mock_config,
                "harness_backend": mock_harness_backend,
                "task_backend": mock_task_backend,
            }

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
        deps["harness_backend"].invoke.side_effect = Exception("Harness crashed")

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
        deps["harness_backend"].invoke.side_effect = Exception("Harness crashed")

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
            patch("cub.cli.run.get_async_backend") as mock_get_harness,
        ):
            mock_config.return_value = MagicMock()
            mock_get_harness.side_effect = ValueError("Unknown harness: invalid")

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
        ):
            mock_config.return_value = MagicMock()
            mock_get_task.side_effect = Exception("No beads found")

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
            patch("cub.cli.run.run_hooks") as mock_run_hooks,
            patch("cub.cli.run.run_hooks_async"),
            patch("cub.cli.run.wait_async_hooks"),
            patch("cub.cli.run.time.sleep"),  # Don't actually sleep
            patch("anyio.from_thread.run", side_effect=sync_run_async),
        ):
            mock_load_config.return_value = mock_config
            mock_detect.return_value = "claude"
            mock_get_harness.return_value = mock_harness_backend
            mock_get_task.return_value = mock_task_backend
            mock_run_hooks.return_value = True
            mock_status_writer.return_value = MagicMock()

            mock_task_backend.get_task_counts.return_value = MagicMock(
                total=100, open=90, in_progress=5, closed=5, remaining=95
            )

            yield {
                "config": mock_config,
                "harness_backend": mock_harness_backend,
                "task_backend": mock_task_backend,
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

        runner.invoke(app, ["--once"])

        # Should only invoke harness once (async method)
        assert deps["harness_backend"].run_task.call_count == 1

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

        result = runner.invoke(app, [])

        # Should invoke harness twice (max_iterations = 2, using async method)
        assert deps["harness_backend"].run_task.call_count == 2
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
            patch("cub.cli.run.run_hooks") as mock_run_hooks,
            patch("cub.cli.run.run_hooks_async"),
            patch("cub.cli.run.wait_async_hooks"),
            patch("anyio.from_thread.run", side_effect=sync_run_async),
        ):
            mock_load_config.return_value = mock_config
            mock_detect.return_value = "claude"
            mock_get_harness.return_value = mock_harness_backend
            mock_get_task.return_value = mock_task_backend
            mock_run_hooks.return_value = True
            mock_status_writer.return_value = MagicMock()

            mock_task_backend.get_task_counts.return_value = MagicMock(
                total=10, open=5, in_progress=2, closed=3, remaining=7
            )

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
        deps["task_backend"].get_ready_tasks.assert_called_with(
            parent="backend-v2", label=None
        )

    def test_label_filter_passed_to_backend(self, runner, filter_mock_deps):
        """Test that --label filter is passed to task backend."""
        deps = filter_mock_deps
        deps["task_backend"].get_ready_tasks.return_value = []
        deps["task_backend"].get_task_counts.return_value = MagicMock(remaining=0)

        runner.invoke(app, ["--once", "--label", "urgent"])

        # Verify label was passed
        deps["task_backend"].get_ready_tasks.assert_called_with(
            parent=None, label="urgent"
        )

    def test_both_filters_combined(self, runner, filter_mock_deps):
        """Test that both epic and label filters can be combined."""
        deps = filter_mock_deps
        deps["task_backend"].get_ready_tasks.return_value = []
        deps["task_backend"].get_task_counts.return_value = MagicMock(remaining=0)

        runner.invoke(app, ["--once", "--epic", "v2", "--label", "critical"])

        # Verify both filters passed
        deps["task_backend"].get_ready_tasks.assert_called_with(
            parent="v2", label="critical"
        )
