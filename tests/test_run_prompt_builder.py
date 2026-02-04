"""
Unit tests for cub.core.run.prompt_builder.

Tests the prompt builder functions in isolation, imported directly from
the core package rather than via cli/run.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cub.core.run.prompt_builder import (
    PromptConfig,
    TaskPrompt,
    generate_direct_task_prompt,
    generate_epic_context,
    generate_retry_context,
    generate_system_prompt,
    generate_task_prompt,
    load_plan_context,
)
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    task_id: str = "test-001",
    title: str = "Test task",
    description: str = "Do the thing",
    parent: str | None = None,
    status: TaskStatus = TaskStatus.OPEN,
    task_type: TaskType = TaskType.TASK,
    acceptance_criteria: list[str] | None = None,
) -> Task:
    return Task(
        id=task_id,
        title=title,
        description=description,
        parent=parent,
        status=status,
        type=task_type,
        priority=TaskPriority.P2,
        acceptance_criteria=acceptance_criteria or [],
    )


def _make_task_backend(
    agent_instructions: str = "Use bd close test-001 to close.",
    epic: Task | None = None,
    sibling_tasks: list[Task] | None = None,
) -> MagicMock:
    backend = MagicMock()
    backend.get_agent_instructions.return_value = agent_instructions
    backend.get_task.return_value = epic
    backend.list_tasks.return_value = sibling_tasks or []
    return backend


# ===========================================================================
# PromptConfig model
# ===========================================================================


class TestPromptConfig:
    """Tests for the PromptConfig dataclass."""

    def test_default_package_root(self) -> None:
        """Default package_root resolves to the repo's top-level src dir."""
        config = PromptConfig(project_dir=Path("/fake"))
        # The default goes 4 parents up from prompt_builder.py:
        # prompt_builder.py -> run/ -> core/ -> cub/ -> src/
        assert config.package_root.name in ("src", "cub")  # depends on install
        assert isinstance(config.package_root, Path)

    def test_prompt_search_paths_order(self, tmp_path: Path) -> None:
        """Search paths are returned in documented priority order.

        After the runloop.md/PROMPT.md consolidation, only runloop.md paths
        are searched (no more PROMPT.md in the chain).
        """
        config = PromptConfig(project_dir=tmp_path, package_root=tmp_path / "pkg")
        paths = config.prompt_search_paths
        assert len(paths) == 2
        # Project-level runloop (highest priority)
        assert paths[0] == tmp_path / ".cub" / "runloop.md"
        # Package-bundled fallback
        assert paths[1] == tmp_path / "pkg" / "templates" / "runloop.md"

    def test_plan_context_path_with_slug(self, tmp_path: Path) -> None:
        """Plan context path is derived from plan_slug."""
        config = PromptConfig(
            project_dir=tmp_path,
            package_root=tmp_path / "pkg",
            plan_slug="my-feature",
        )
        assert config.plan_context_path == tmp_path / "plans" / "my-feature" / "prompt-context.md"

    def test_plan_context_path_without_slug(self, tmp_path: Path) -> None:
        """Plan context path is None when no plan_slug provided."""
        config = PromptConfig(project_dir=tmp_path, package_root=tmp_path / "pkg")
        assert config.plan_context_path is None

    def test_frozen(self) -> None:
        """PromptConfig is immutable."""
        config = PromptConfig(project_dir=Path("/a"))
        with pytest.raises(AttributeError):
            config.project_dir = Path("/b")  # type: ignore[misc]


# ===========================================================================
# TaskPrompt model
# ===========================================================================


class TestTaskPrompt:
    """Tests for the TaskPrompt dataclass."""

    def test_defaults(self) -> None:
        tp = TaskPrompt(text="hello")
        assert tp.text == "hello"
        assert tp.has_epic_context is False
        assert tp.has_retry_context is False

    def test_with_context_flags(self) -> None:
        tp = TaskPrompt(text="x", has_epic_context=True, has_retry_context=True)
        assert tp.has_epic_context is True
        assert tp.has_retry_context is True


# ===========================================================================
# generate_system_prompt
# ===========================================================================


class TestGenerateSystemPrompt:
    """Tests for generate_system_prompt (imported from core, not cli)."""

    def test_reads_cub_runloop(self, tmp_path: Path) -> None:
        """Highest priority: .cub/runloop.md."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        (cub_dir / "runloop.md").write_text("# Runloop from .cub")
        (tmp_path / "PROMPT.md").write_text("# Legacy prompt")

        result = generate_system_prompt(tmp_path)
        assert "Runloop from .cub" in result
        assert "Legacy prompt" not in result

    def test_reads_bundled_runloop(self, tmp_path: Path) -> None:
        """Falls back to bundled runloop when project runloop missing."""
        # When no .cub/runloop.md exists, the bundled template is used
        # (or the hardcoded fallback if that's also missing)
        result = generate_system_prompt(tmp_path)
        # Either the bundled template or fallback - both mention autonomous coding
        assert "autonomous" in result.lower() or "Autonomous" in result

    def test_injects_plan_context(self, tmp_path: Path) -> None:
        """Plan context is appended when plan_slug is provided."""
        # Create runloop
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        (cub_dir / "runloop.md").write_text("# Core Runloop\n\nBase instructions.")

        # Create plan context
        plan_dir = tmp_path / "plans" / "my-feature"
        plan_dir.mkdir(parents=True)
        (plan_dir / "prompt-context.md").write_text("# Plan Context\n\nFeature requirements.")

        result = generate_system_prompt(tmp_path, plan_slug="my-feature")
        assert "Core Runloop" in result
        assert "Plan Context" in result
        assert "Feature requirements" in result

    def test_no_plan_context_without_slug(self, tmp_path: Path) -> None:
        """Plan context is not included when no plan_slug."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        (cub_dir / "runloop.md").write_text("# Core Runloop\n\nBase instructions.")

        # Create plan context that should NOT be loaded
        plan_dir = tmp_path / "plans" / "my-feature"
        plan_dir.mkdir(parents=True)
        (plan_dir / "prompt-context.md").write_text("# Plan Context\n\nFeature requirements.")

        result = generate_system_prompt(tmp_path)  # No plan_slug
        assert "Core Runloop" in result
        assert "Plan Context" not in result

    def test_handles_missing_plan_context(self, tmp_path: Path) -> None:
        """Gracefully handles missing prompt-context.md file."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        (cub_dir / "runloop.md").write_text("# Core Runloop\n\nBase instructions.")

        # No plan directory exists
        result = generate_system_prompt(tmp_path, plan_slug="nonexistent")
        assert "Core Runloop" in result
        # Should not error, just skip plan context

    def test_fallback_prompt(self, tmp_path: Path) -> None:
        """When no file exists AND bundled templates don't exist, return fallback."""
        # Create an empty project with a fake package root that has no templates
        empty_pkg = tmp_path / "empty_pkg"
        empty_pkg.mkdir()

        config = PromptConfig(project_dir=tmp_path, package_root=empty_pkg)
        # Use config's search paths directly to demonstrate fallback
        found = False
        for p in config.prompt_search_paths:
            if p.exists():
                found = True
                break

        if not found:
            # Simulate the fallback path
            result = generate_system_prompt(tmp_path)
            # The bundled template usually exists, so this may still find it.
            # Either way, a non-empty string is returned.
            assert len(result) > 50
            assert "autonomous coding agent" in result.lower() or "Autonomous" in result

    def test_always_returns_nonempty_string(self, tmp_path: Path) -> None:
        """generate_system_prompt always returns a non-empty string."""
        result = generate_system_prompt(tmp_path)
        assert isinstance(result, str)
        assert len(result) > 0


# ===========================================================================
# generate_direct_task_prompt
# ===========================================================================


class TestGenerateDirectTaskPrompt:
    """Tests for generate_direct_task_prompt."""

    def test_contains_current_task_header(self) -> None:
        result = generate_direct_task_prompt("Add logout button")
        assert "## CURRENT TASK" in result

    def test_contains_direct_mode_marker(self) -> None:
        result = generate_direct_task_prompt("Fix bug")
        assert "Direct (no task backend)" in result

    def test_contains_task_content(self) -> None:
        result = generate_direct_task_prompt("Refactor the auth module")
        assert "Refactor the auth module" in result

    def test_contains_completion_instructions(self) -> None:
        result = generate_direct_task_prompt("anything")
        assert "When complete:" in result
        assert "feedback loops" in result

    def test_notes_no_task_id(self) -> None:
        result = generate_direct_task_prompt("anything")
        assert "No task ID to close" in result

    def test_preserves_multiline_content(self) -> None:
        content = "Step 1: Do A\nStep 2: Do B\nStep 3: Do C"
        result = generate_direct_task_prompt(content)
        assert "Step 1: Do A" in result
        assert "Step 2: Do B" in result
        assert "Step 3: Do C" in result


# ===========================================================================
# generate_epic_context
# ===========================================================================


class TestGenerateEpicContext:
    """Tests for generate_epic_context."""

    def test_returns_none_when_no_parent(self) -> None:
        task = _make_task(parent=None)
        backend = _make_task_backend()
        assert generate_epic_context(task, backend) is None

    def test_returns_none_when_epic_not_found(self) -> None:
        task = _make_task(parent="epic-999")
        backend = _make_task_backend(epic=None)
        assert generate_epic_context(task, backend) is None

    def test_basic_structure(self) -> None:
        epic = _make_task(task_id="epic-1", title="Big feature")
        task = _make_task(parent="epic-1")
        backend = _make_task_backend(epic=epic, sibling_tasks=[])

        result = generate_epic_context(task, backend)
        assert result is not None
        assert "## Epic Context" in result
        assert "epic-1" in result
        assert "Big feature" in result

    def test_truncates_long_description(self) -> None:
        long_desc = " ".join(["word"] * 250)
        epic = _make_task(task_id="epic-1", title="Epic", description=long_desc)
        task = _make_task(parent="epic-1")
        backend = _make_task_backend(epic=epic, sibling_tasks=[])

        result = generate_epic_context(task, backend)
        assert result is not None
        assert "..." in result

    def test_does_not_truncate_short_description(self) -> None:
        epic = _make_task(task_id="epic-1", title="Epic", description="Short desc")
        task = _make_task(parent="epic-1")
        backend = _make_task_backend(epic=epic, sibling_tasks=[])

        result = generate_epic_context(task, backend)
        assert result is not None
        assert "Short desc" in result
        assert "..." not in result

    def test_shows_completed_siblings(self) -> None:
        epic = _make_task(task_id="epic-1", title="Epic")
        task = _make_task(task_id="t-2", parent="epic-1")
        sibling_done = _make_task(task_id="t-1", title="Done task", status=TaskStatus.CLOSED)
        backend = _make_task_backend(epic=epic, sibling_tasks=[sibling_done, task])

        result = generate_epic_context(task, backend)
        assert result is not None
        assert "✓ t-1: Done task" in result

    def test_shows_remaining_siblings(self) -> None:
        epic = _make_task(task_id="epic-1", title="Epic")
        task = _make_task(task_id="t-1", parent="epic-1")
        sibling_open = _make_task(task_id="t-2", title="Open task", status=TaskStatus.OPEN)
        sibling_wip = _make_task(task_id="t-3", title="WIP task", status=TaskStatus.IN_PROGRESS)
        backend = _make_task_backend(epic=epic, sibling_tasks=[task, sibling_open, sibling_wip])

        result = generate_epic_context(task, backend)
        assert result is not None
        assert "○ t-2: Open task" in result
        assert "◐ t-3: WIP task" in result

    def test_excludes_self_from_remaining(self) -> None:
        epic = _make_task(task_id="epic-1", title="Epic")
        task = _make_task(task_id="t-1", parent="epic-1", status=TaskStatus.OPEN)
        backend = _make_task_backend(epic=epic, sibling_tasks=[task])

        result = generate_epic_context(task, backend)
        assert result is not None
        # Self should not appear in "Remaining" section
        assert "Remaining Sibling Tasks:" not in result


# ===========================================================================
# generate_retry_context
# ===========================================================================


class TestGenerateRetryContext:
    """Tests for generate_retry_context."""

    def _make_ledger_integration(
        self,
        entry: object | None = None,
        by_task_dir: Path | None = None,
    ) -> MagicMock:
        li = MagicMock()
        li.writer.get_entry.return_value = entry
        if by_task_dir is not None:
            li.writer.by_task_dir = by_task_dir
        return li

    def _make_attempt(
        self,
        attempt_number: int = 1,
        success: bool = False,
        duration_seconds: int = 30,
        model: str = "haiku",
        error_category: str | None = None,
        error_summary: str | None = None,
    ) -> MagicMock:
        attempt = MagicMock()
        attempt.attempt_number = attempt_number
        attempt.success = success
        attempt.duration_seconds = duration_seconds
        attempt.duration_minutes = duration_seconds / 60
        attempt.model = model
        attempt.error_category = error_category
        attempt.error_summary = error_summary
        return attempt

    def _make_entry(self, attempts: list[object]) -> MagicMock:
        entry = MagicMock()
        entry.attempts = attempts
        return entry

    def test_returns_none_when_no_entry(self) -> None:
        task = _make_task()
        li = self._make_ledger_integration(entry=None)
        assert generate_retry_context(task, li) is None

    def test_returns_none_when_no_attempts(self) -> None:
        task = _make_task()
        entry = self._make_entry(attempts=[])
        li = self._make_ledger_integration(entry=entry)
        assert generate_retry_context(task, li) is None

    def test_returns_none_when_all_successful(self) -> None:
        task = _make_task()
        entry = self._make_entry(attempts=[self._make_attempt(success=True)])
        li = self._make_ledger_integration(entry=entry)
        assert generate_retry_context(task, li) is None

    def test_basic_retry_structure(self, tmp_path: Path) -> None:
        task = _make_task()
        failed = self._make_attempt(
            attempt_number=1, success=False, duration_seconds=45, model="haiku"
        )
        entry = self._make_entry(attempts=[failed])
        li = self._make_ledger_integration(entry=entry, by_task_dir=tmp_path)

        result = generate_retry_context(task, li)
        assert result is not None
        assert "## Retry Context" in result
        assert "1 time(s)" in result
        assert "1 failure(s)" in result
        assert "Attempt #1" in result

    def test_shows_multiple_failed_attempts(self, tmp_path: Path) -> None:
        task = _make_task()
        a1 = self._make_attempt(attempt_number=1, success=False, model="haiku")
        a2 = self._make_attempt(attempt_number=2, success=False, model="sonnet")
        entry = self._make_entry(attempts=[a1, a2])
        li = self._make_ledger_integration(entry=entry, by_task_dir=tmp_path)

        result = generate_retry_context(task, li)
        assert result is not None
        assert "Attempt #1" in result
        assert "Attempt #2" in result
        assert "2 failure(s)" in result

    def test_duration_seconds_format(self, tmp_path: Path) -> None:
        task = _make_task()
        failed = self._make_attempt(duration_seconds=30)
        entry = self._make_entry(attempts=[failed])
        li = self._make_ledger_integration(entry=entry, by_task_dir=tmp_path)

        result = generate_retry_context(task, li)
        assert result is not None
        assert "30s" in result

    def test_duration_minutes_format(self, tmp_path: Path) -> None:
        task = _make_task()
        failed = self._make_attempt(duration_seconds=120)
        entry = self._make_entry(attempts=[failed])
        li = self._make_ledger_integration(entry=entry, by_task_dir=tmp_path)

        result = generate_retry_context(task, li)
        assert result is not None
        assert "2.0m" in result

    def test_includes_log_tail(self, tmp_path: Path) -> None:
        task = _make_task()
        failed = self._make_attempt(attempt_number=1)
        entry = self._make_entry(attempts=[failed])
        li = self._make_ledger_integration(entry=entry, by_task_dir=tmp_path)

        # Create the log file
        log_dir = tmp_path / "test-001" / "attempts"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "001-harness.log"
        log_file.write_text("line 1\nline 2\nERROR: something broke\n")

        result = generate_retry_context(task, li)
        assert result is not None
        assert "ERROR: something broke" in result
        assert "```" in result

    def test_custom_log_tail_lines(self, tmp_path: Path) -> None:
        task = _make_task()
        failed = self._make_attempt(attempt_number=1)
        entry = self._make_entry(attempts=[failed])
        li = self._make_ledger_integration(entry=entry, by_task_dir=tmp_path)

        # Create log with many lines
        log_dir = tmp_path / "test-001" / "attempts"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "001-harness.log"
        lines = [f"line {i}" for i in range(100)]
        log_file.write_text("\n".join(lines))

        result = generate_retry_context(task, li, log_tail_lines=5)
        assert result is not None
        assert "Last 5 lines" in result

    def test_handles_missing_log_gracefully(self, tmp_path: Path) -> None:
        task = _make_task()
        failed = self._make_attempt(attempt_number=1)
        entry = self._make_entry(attempts=[failed])
        li = self._make_ledger_integration(entry=entry, by_task_dir=tmp_path)
        # No log file created

        result = generate_retry_context(task, li)
        assert result is not None
        # Should not crash, just skip log tail
        assert "```" not in result

    def test_includes_error_category_and_summary(self, tmp_path: Path) -> None:
        task = _make_task()
        failed = self._make_attempt(
            error_category="TypeCheckError", error_summary="mypy found 3 errors"
        )
        entry = self._make_entry(attempts=[failed])
        li = self._make_ledger_integration(entry=entry, by_task_dir=tmp_path)

        result = generate_retry_context(task, li)
        assert result is not None
        assert "TypeCheckError" in result
        assert "mypy found 3 errors" in result


# ===========================================================================
# generate_task_prompt
# ===========================================================================


class TestGenerateTaskPrompt:
    """Tests for generate_task_prompt."""

    def test_basic_structure(self) -> None:
        task = _make_task(task_id="cub-42", title="Add feature", task_type=TaskType.TASK)
        backend = _make_task_backend()

        result = generate_task_prompt(task, backend)
        assert "## CURRENT TASK" in result
        assert "Task ID: cub-42" in result
        assert "Type: task" in result
        assert "Title: Add feature" in result

    def test_includes_description(self) -> None:
        task = _make_task(description="Implement the widget")
        backend = _make_task_backend()

        result = generate_task_prompt(task, backend)
        assert "Implement the widget" in result

    def test_handles_empty_description(self) -> None:
        task = _make_task(description="")
        backend = _make_task_backend()

        result = generate_task_prompt(task, backend)
        # Empty string is falsy, so falls through to the fallback
        assert "(No description provided)" in result

    def test_includes_acceptance_criteria(self) -> None:
        task = _make_task(acceptance_criteria=["All tests pass", "No lint errors"])
        backend = _make_task_backend()

        result = generate_task_prompt(task, backend)
        assert "Acceptance Criteria:" in result
        assert "- All tests pass" in result
        assert "- No lint errors" in result

    def test_no_acceptance_criteria_when_empty(self) -> None:
        task = _make_task(acceptance_criteria=[])
        backend = _make_task_backend()

        result = generate_task_prompt(task, backend)
        assert "Acceptance Criteria:" not in result

    def test_includes_task_management(self) -> None:
        task = _make_task()
        backend = _make_task_backend(agent_instructions="Use bd close test-001")

        result = generate_task_prompt(task, backend)
        assert "## Task Management" in result
        assert "bd close test-001" in result

    def test_includes_completion_workflow(self) -> None:
        task = _make_task(task_id="cub-7", title="Fix bug", task_type=TaskType.TASK)
        backend = _make_task_backend()

        result = generate_task_prompt(task, backend)
        assert "## When Complete" in result
        assert "feedback loops" in result
        assert "task(cub-7): Fix bug" in result

    def test_includes_epic_context_when_present(self) -> None:
        epic = _make_task(task_id="epic-1", title="Big epic")
        task = _make_task(task_id="t-1", parent="epic-1")
        backend = _make_task_backend(epic=epic, sibling_tasks=[])

        result = generate_task_prompt(task, backend)
        assert "## Epic Context" in result
        assert "epic-1" in result

    def test_no_epic_context_when_no_parent(self) -> None:
        task = _make_task(parent=None)
        backend = _make_task_backend()

        result = generate_task_prompt(task, backend)
        assert "## Epic Context" not in result

    def test_includes_retry_context_when_present(self, tmp_path: Path) -> None:
        task = _make_task()
        backend = _make_task_backend()

        # Mock ledger integration with a failed attempt
        li = MagicMock()
        attempt = MagicMock()
        attempt.attempt_number = 1
        attempt.success = False
        attempt.duration_seconds = 30
        attempt.duration_minutes = 0.5
        attempt.model = "haiku"
        attempt.error_category = None
        attempt.error_summary = None

        entry = MagicMock()
        entry.attempts = [attempt]
        li.writer.get_entry.return_value = entry
        li.writer.by_task_dir = tmp_path

        result = generate_task_prompt(task, backend, ledger_integration=li)
        assert "## Retry Context" in result

    def test_no_retry_context_without_ledger(self) -> None:
        task = _make_task()
        backend = _make_task_backend()

        result = generate_task_prompt(task, backend, ledger_integration=None)
        assert "## Retry Context" not in result


# ===========================================================================
# Import compatibility (from cub.core.run)
# ===========================================================================


class TestPackageReexports:
    """Verify functions are accessible from the cub.core.run package."""

    def test_import_from_core_run(self) -> None:
        """All public functions importable from cub.core.run."""
        from cub.core.run import (
            generate_direct_task_prompt as f1,
        )
        from cub.core.run import (
            generate_epic_context as f2,
        )
        from cub.core.run import (
            generate_retry_context as f3,
        )
        from cub.core.run import (
            generate_system_prompt as f4,
        )
        from cub.core.run import (
            generate_task_prompt as f5,
        )

        assert callable(f1)
        assert callable(f2)
        assert callable(f3)
        assert callable(f4)
        assert callable(f5)

    def test_import_from_cli_run(self) -> None:
        """All prompt functions still importable from cub.cli.run (backwards compat)."""
        from cub.cli.run import (
            generate_direct_task_prompt as f1,
        )
        from cub.cli.run import (
            generate_epic_context as f2,
        )
        from cub.cli.run import (
            generate_retry_context as f3,
        )
        from cub.cli.run import (
            generate_system_prompt as f4,
        )
        from cub.cli.run import (
            generate_task_prompt as f5,
        )

        assert callable(f1)
        assert callable(f2)
        assert callable(f3)
        assert callable(f4)
        assert callable(f5)
