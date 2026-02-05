"""
Hook executor for lifecycle hooks.

This module executes hook scripts with context passed via environment variables.
It's part of the new lifecycle hooks system that provides rich context at key
execution points:
- pre-session: Before harness session starts
- end-of-task: After a task completes
- end-of-epic: After all tasks in an epic complete
- end-of-plan: After all epics in a plan complete

Context is passed to hooks via the CUB_HOOK_CONTEXT environment variable
as a JSON-serialized string. Hooks can parse this to get structured data
about the current execution state.

Execution features:
- Configurable timeout (default 30s)
- Captures stdout and stderr
- Handles hook failures gracefully (configurable)
- Measures execution duration
- Returns structured results

Example hook script:
    #!/bin/bash
    # Parse context
    CONTEXT=$(echo "$CUB_HOOK_CONTEXT" | jq .)
    TASK_ID=$(echo "$CONTEXT" | jq -r '.task_id')
    echo "Processing task: $TASK_ID"

Usage:
    from cub.core.hooks.executor import HookExecutor
    from cub.core.hooks.models import TaskContext

    # Create executor with custom config
    executor = HookExecutor(project_dir, hook_config)

    # Run hooks with context
    context = TaskContext(
        task_id="cub-123",
        task_title="Fix bug",
        status="closed",
        success=True,
        project_dir="/path/to/project"
    )
    results = executor.run("end-of-task", context)

    # Check results
    for result in results:
        if result.failed:
            print(f"Hook failed: {result.error_message}")
"""

import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from cub.core.hooks.discovery import discover_hooks
from cub.core.hooks.models import HookConfig, HookResult

logger = logging.getLogger(__name__)


class HookExecutor:
    """
    Executor for lifecycle hook scripts.

    The executor discovers and runs hook scripts with context passed via
    environment variables. It handles timeouts, captures output, and provides
    structured results.

    Attributes:
        project_dir: Project root directory
        config: Hook configuration (timeout, fail_on_error, etc.)

    Example:
        >>> from pathlib import Path
        >>> executor = HookExecutor(Path.cwd())
        >>> context = TaskContext(
        ...     task_id="cub-123",
        ...     task_title="Test",
        ...     status="closed",
        ...     success=True,
        ...     project_dir="/path/to/project"
        ... )
        >>> results = executor.run("end-of-task", context)
        >>> print(f"Ran {len(results)} hooks")
    """

    def __init__(
        self,
        project_dir: Path,
        config: HookConfig | None = None,
    ):
        """
        Initialize hook executor.

        Args:
            project_dir: Project root directory
            config: Hook configuration (uses defaults if not provided)
        """
        self.project_dir = project_dir
        self.config = config or HookConfig()

    def run(
        self,
        hook_name: str,
        context: BaseModel,
    ) -> list[HookResult]:
        """
        Run all hooks for a given lifecycle event.

        Discovers and executes all hook scripts for the specified hook name.
        Context is passed to each script via the CUB_HOOK_CONTEXT environment
        variable as a JSON string.

        Args:
            hook_name: Lifecycle hook name (pre-session, end-of-task, etc.)
            context: Context model with hook data (must have to_json() method)

        Returns:
            List of HookResult objects, one per executed script

        Raises:
            RuntimeError: If a hook fails and config.fail_on_error is True

        Example:
            >>> results = executor.run("end-of-task", task_context)
            >>> for result in results:
            ...     print(f"Hook exit code: {result.exit_code}")
        """
        # Check if hook is enabled
        if not self.config.is_hook_enabled(hook_name):
            logger.debug(f"Hook {hook_name} is disabled, skipping")
            return []

        # Discover hook scripts
        scripts = discover_hooks(hook_name, self.project_dir, self.config)

        if not scripts:
            logger.debug(f"No hook scripts found for {hook_name}")
            return []

        logger.info(f"Running {len(scripts)} hook(s) for {hook_name}")

        # Execute each script
        results: list[HookResult] = []
        for script in scripts:
            result = self._execute_script(script, hook_name, context)
            results.append(result)

            # Log result
            if result.success:
                logger.info(
                    f"Hook {script.name} completed successfully in {result.duration_seconds:.2f}s"
                )
            else:
                logger.error(
                    f"Hook {script.name} failed with exit code {result.exit_code}: "
                    f"{result.error_message}"
                )

            # Handle failure based on configuration
            if result.failed and self.config.fail_on_error:
                raise RuntimeError(
                    f"Hook {script.name} failed with exit code {result.exit_code}: "
                    f"{result.error_message}"
                )

        return results

    def _execute_script(
        self,
        script_path: Path,
        hook_name: str,
        context: BaseModel,
    ) -> HookResult:
        """
        Execute a single hook script with context.

        Args:
            script_path: Path to hook script
            hook_name: Hook name for logging
            context: Context model to pass via environment

        Returns:
            HookResult with execution details
        """
        # Serialize context to JSON
        context_json = context.model_dump_json()

        # Build environment with context
        env = self._build_environment(hook_name, context_json)

        # Execute script with timeout
        start_time = time.time()
        try:
            result = subprocess.run(
                [str(script_path)],
                cwd=str(self.project_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )

            duration = time.time() - start_time

            return HookResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=duration,
                timestamp=datetime.now(),
                error_message=None if result.returncode == 0 else result.stderr.strip(),
            )

        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            return HookResult(
                success=False,
                exit_code=-1,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr=e.stderr.decode() if e.stderr else "",
                duration_seconds=duration,
                timestamp=datetime.now(),
                error_message=f"Hook timed out after {self.config.timeout_seconds}s",
            )

        except Exception as e:
            duration = time.time() - start_time
            return HookResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                duration_seconds=duration,
                timestamp=datetime.now(),
                error_message=f"Failed to execute hook: {str(e)}",
            )

    def _build_environment(
        self,
        hook_name: str,
        context_json: str,
    ) -> dict[str, str]:
        """
        Build environment dictionary for hook execution.

        Includes the current process environment plus hook-specific variables.

        Args:
            hook_name: Hook name
            context_json: JSON-serialized context

        Returns:
            Environment dictionary for subprocess
        """
        import os

        # Start with current environment
        env = os.environ.copy()

        # Add hook-specific variables
        env["CUB_HOOK_NAME"] = hook_name
        env["CUB_HOOK_CONTEXT"] = context_json
        env["CUB_PROJECT_DIR"] = str(self.project_dir)

        return env
