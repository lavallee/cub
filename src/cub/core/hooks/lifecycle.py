"""
Lifecycle hook integration for the run loop.

This module provides functions to invoke lifecycle hooks at key points during
autonomous execution. It bridges the run loop state machine with the hook
execution system, building rich context objects from run loop state.

Lifecycle hook points:
- pre-session: Before harness session starts (before any tasks)
- end-of-task: After a task completes (success or failure)
- end-of-epic: After all tasks in an epic complete
- end-of-plan: After all epics in a plan complete

Each hook receives a context object with execution state via environment variables.
Hooks are optional and can be disabled via configuration.

Usage:
    from cub.core.hooks.lifecycle import invoke_pre_session_hook, invoke_end_of_task_hook

    # In run loop initialization
    invoke_pre_session_hook(config, task_backend, run_id)

    # After task completion
    invoke_end_of_task_hook(config, task, success, duration, run_id, error=error_msg)
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from cub.core.hooks.executor import HookExecutor
from cub.core.hooks.models import (
    EpicContext,
    HookConfig,
    PlanContext,
    SessionContext,
    TaskContext,
)

if TYPE_CHECKING:
    from cub.core.run.models import RunConfig
    from cub.core.tasks.backend import TaskBackend
    from cub.core.tasks.models import Task

logger = logging.getLogger(__name__)


def _get_hook_config(run_config: "RunConfig") -> HookConfig:
    """
    Build HookConfig from RunConfig.

    Args:
        run_config: Run loop configuration

    Returns:
        HookConfig for hook executor
    """
    return HookConfig(
        enabled=run_config.hooks_enabled,
        fail_on_error=run_config.hooks_fail_fast,
    )


def invoke_pre_session_hook(
    run_config: "RunConfig",
    task_backend: "TaskBackend",
    run_id: str,
) -> bool:
    """
    Invoke pre-session hook before harness session starts.

    Builds context with session information and task/epic counts from the
    task backend.

    Args:
        run_config: Run loop configuration
        task_backend: Task backend for counting tasks/epics
        run_id: Session identifier

    Returns:
        True if hook succeeded or hooks disabled, False if failed
    """
    if not run_config.hooks_enabled:
        return True

    try:
        # Count tasks and epics
        task_counts = task_backend.get_task_counts()

        # Count epics (tasks with type="epic")
        all_tasks = task_backend.list_tasks()
        epic_count = sum(1 for t in all_tasks if t.type.value == "epic")

        # Build context
        context = SessionContext(
            session_id=run_id,
            project_dir=str(Path(run_config.project_dir).resolve()),
            harness_name=run_config.harness_name,
            model=run_config.model,
            task_count=task_counts.total,
            epic_count=epic_count,
        )

        # Execute hook
        hook_config = _get_hook_config(run_config)
        executor = HookExecutor(Path(run_config.project_dir), hook_config)
        results = executor.run("pre-session", context)

        # Check for failures
        if run_config.hooks_fail_fast:
            for result in results:
                if result.failed:
                    logger.error(f"Pre-session hook failed: {result.error_message}")
                    return False

        return True

    except Exception as e:
        logger.error(f"Failed to invoke pre-session hook: {e}")
        if run_config.hooks_fail_fast:
            return False
        return True


def invoke_end_of_task_hook(
    run_config: "RunConfig",
    task: "Task",
    success: bool,
    duration_seconds: float,
    run_id: str,
    iterations: int = 1,
    error: str | None = None,
) -> bool:
    """
    Invoke end-of-task hook after task completion.

    Args:
        run_config: Run loop configuration
        task: Completed task
        success: Whether task completed successfully
        duration_seconds: Task execution duration
        run_id: Session identifier
        iterations: Number of iterations taken
        error: Error message if task failed

    Returns:
        True if hook succeeded or hooks disabled, False if failed
    """
    if not run_config.hooks_enabled:
        return True

    try:
        # Build context
        context = TaskContext(
            task_id=task.id,
            task_title=task.title,
            status="closed" if success else "failed",
            success=success,
            project_dir=str(Path(run_config.project_dir).resolve()),
            session_id=run_id,
            parent_epic=task.parent,
            duration_seconds=duration_seconds,
            iterations=iterations,
            error_message=error,
        )

        # Execute hook
        hook_config = _get_hook_config(run_config)
        executor = HookExecutor(Path(run_config.project_dir), hook_config)
        results = executor.run("end-of-task", context)

        # Check for failures
        if run_config.hooks_fail_fast:
            for result in results:
                if result.failed:
                    logger.error(f"End-of-task hook failed: {result.error_message}")
                    return False

        return True

    except Exception as e:
        logger.error(f"Failed to invoke end-of-task hook: {e}")
        if run_config.hooks_fail_fast:
            return False
        return True


def invoke_end_of_epic_hook(
    run_config: "RunConfig",
    task_backend: "TaskBackend",
    epic_id: str,
    run_id: str,
) -> bool:
    """
    Invoke end-of-epic hook after all tasks in epic complete.

    Builds context by aggregating stats from all tasks in the epic.

    Args:
        run_config: Run loop configuration
        task_backend: Task backend for querying epic tasks
        epic_id: Epic identifier
        run_id: Session identifier

    Returns:
        True if hook succeeded or hooks disabled, False if failed
    """
    if not run_config.hooks_enabled:
        return True

    try:
        # Get epic task
        epic = task_backend.get_task(epic_id)
        if not epic:
            logger.warning(f"Epic {epic_id} not found, skipping hook")
            return True

        # Get all tasks in epic
        epic_tasks = task_backend.list_tasks(parent=epic_id)

        # Count task statuses
        total_tasks = len(epic_tasks)
        completed_tasks = sum(1 for t in epic_tasks if t.status.value == "closed")
        failed_tasks = 0  # We don't track failed separately in status
        skipped_tasks = 0  # No skipped status currently

        # Try to calculate epic duration from task timestamps
        duration_seconds: float | None = None
        if epic_tasks:
            start_times = [t.created_at for t in epic_tasks if t.created_at]
            end_times = [t.closed_at for t in epic_tasks if t.closed_at]
            if start_times and end_times:
                earliest = min(start_times)
                latest = max(end_times)
                duration_seconds = (latest - earliest).total_seconds()

        # Determine parent plan
        parent_plan = epic.parent if epic.parent else None

        # Build context
        context = EpicContext(
            epic_id=epic_id,
            epic_title=epic.title,
            project_dir=str(Path(run_config.project_dir).resolve()),
            session_id=run_id,
            parent_plan=parent_plan,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            skipped_tasks=skipped_tasks,
            duration_seconds=duration_seconds,
        )

        # Execute hook
        hook_config = _get_hook_config(run_config)
        executor = HookExecutor(Path(run_config.project_dir), hook_config)
        results = executor.run("end-of-epic", context)

        # Check for failures
        if run_config.hooks_fail_fast:
            for result in results:
                if result.failed:
                    logger.error(f"End-of-epic hook failed: {result.error_message}")
                    return False

        return True

    except Exception as e:
        logger.error(f"Failed to invoke end-of-epic hook: {e}")
        if run_config.hooks_fail_fast:
            return False
        return True


def invoke_end_of_plan_hook(
    run_config: "RunConfig",
    task_backend: "TaskBackend",
    plan_id: str,
    run_id: str,
) -> bool:
    """
    Invoke end-of-plan hook after all epics in plan complete.

    Builds context by aggregating stats from all epics and tasks in the plan.

    Args:
        run_config: Run loop configuration
        task_backend: Task backend for querying plan data
        plan_id: Plan identifier
        run_id: Session identifier

    Returns:
        True if hook succeeded or hooks disabled, False if failed
    """
    if not run_config.hooks_enabled:
        return True

    try:
        # Get plan task
        plan = task_backend.get_task(plan_id)
        if not plan:
            logger.warning(f"Plan {plan_id} not found, skipping hook")
            return True

        # Get all epics in plan
        plan_epics = task_backend.list_tasks(parent=plan_id)
        epic_ids = [e.id for e in plan_epics if e.type.value == "epic"]

        # Get all tasks across all epics
        all_tasks = []
        for epic_id in epic_ids:
            epic_tasks = task_backend.list_tasks(parent=epic_id)
            all_tasks.extend(epic_tasks)

        # Count epics
        total_epics = len(epic_ids)
        completed_epics = sum(
            1 for e in plan_epics
            if e.type.value == "epic" and e.status.value == "closed"
        )

        # Count tasks
        total_tasks = len(all_tasks)
        completed_tasks = sum(1 for t in all_tasks if t.status.value == "closed")
        failed_tasks = 0  # No failed status tracking currently

        # Try to calculate plan duration
        duration_seconds: float | None = None
        if all_tasks:
            start_times = [t.created_at for t in all_tasks if t.created_at]
            end_times = [t.closed_at for t in all_tasks if t.closed_at]
            if start_times and end_times:
                earliest = min(start_times)
                latest = max(end_times)
                duration_seconds = (latest - earliest).total_seconds()

        # Build context
        context = PlanContext(
            plan_id=plan_id,
            plan_title=plan.title,
            project_dir=str(Path(run_config.project_dir).resolve()),
            session_id=run_id,
            total_epics=total_epics,
            completed_epics=completed_epics,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            duration_seconds=duration_seconds,
        )

        # Execute hook
        hook_config = _get_hook_config(run_config)
        executor = HookExecutor(Path(run_config.project_dir), hook_config)
        results = executor.run("end-of-plan", context)

        # Check for failures
        if run_config.hooks_fail_fast:
            for result in results:
                if result.failed:
                    logger.error(f"End-of-plan hook failed: {result.error_message}")
                    return False

        return True

    except Exception as e:
        logger.error(f"Failed to invoke end-of-plan hook: {e}")
        if run_config.hooks_fail_fast:
            return False
        return True
