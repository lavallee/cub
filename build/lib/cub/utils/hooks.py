"""
Hook execution framework for Cub.

This module provides functions for running hook scripts at various points in the
cub lifecycle. Hooks are executable Bash scripts stored in directories like:
  - ~/.config/cub/hooks/{hook_name}.d/  (global hooks)
  - ./.cub/hooks/{hook_name}.d/         (project-specific hooks)

Scripts are executed in sorted order (01-first.sh before 02-second.sh).

Available hook points:
  - pre-loop: Before starting the main loop
  - pre-task: Before each task execution
  - post-task: After each task execution (success or failure)
  - on-error: When a task fails
  - post-loop: After the main loop completes

Environment Variables Exported to Hooks:
  CUB_HOOK_NAME     - Name of the hook being run
  CUB_PROJECT_DIR   - Project directory
  CUB_TASK_ID       - Current task ID (if applicable)
  CUB_TASK_TITLE    - Current task title (if applicable)
  CUB_EXIT_CODE     - Task exit code (for post-task/on-error hooks)
  CUB_HARNESS       - Harness being used (claude, codex, etc.)
  CUB_SESSION_ID    - Current session ID
"""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from cub.core.config import load_config
from cub.core.config.loader import get_xdg_config_home


@dataclass
class HookContext:
    """
    Context information passed to hooks via environment variables.

    This provides all the information a hook script might need to make
    decisions or perform side effects.
    """

    hook_name: str
    project_dir: Path = field(default_factory=Path.cwd)
    task_id: str | None = None
    task_title: str | None = None
    exit_code: int | None = None
    harness: str | None = None
    session_id: str | None = None

    def to_env_dict(self) -> dict[str, str]:
        """
        Convert context to environment variable dictionary.

        Returns:
            Dict mapping env var names to string values (empty strings for None)
        """
        return {
            "CUB_HOOK_NAME": self.hook_name,
            "CUB_PROJECT_DIR": str(self.project_dir),
            "CUB_TASK_ID": self.task_id or "",
            "CUB_TASK_TITLE": self.task_title or "",
            "CUB_EXIT_CODE": str(self.exit_code) if self.exit_code is not None else "",
            "CUB_HARNESS": self.harness or "",
            "CUB_SESSION_ID": self.session_id or "",
        }


def find_hook_scripts(hook_name: str, project_dir: Path | None = None) -> list[Path]:
    """
    Find all executable hook scripts for a given hook name.

    Scans both global and project hook directories for executable scripts.
    Returns paths sorted by filename (global hooks first, then project).

    Args:
        hook_name: Name of the hook (e.g., "pre-task", "post-task")
        project_dir: Project directory (defaults to current directory)

    Returns:
        List of Path objects to executable hook scripts, sorted by name

    Example:
        >>> scripts = find_hook_scripts("pre-task")
        >>> # Returns:
        >>> # [
        >>> #   Path("~/.config/cub/hooks/pre-task.d/01-global.sh"),
        >>> #   Path("./.cub/hooks/pre-task.d/02-project.sh")
        >>> # ]
    """
    if not hook_name:
        raise ValueError("hook_name is required")

    if project_dir is None:
        project_dir = Path.cwd()

    # Build list of hook directories to check
    global_hook_dir = get_xdg_config_home() / "cub" / "hooks" / f"{hook_name}.d"
    project_hook_dir = project_dir / ".cub" / "hooks" / f"{hook_name}.d"

    all_scripts: list[Path] = []

    # Collect scripts from global directory
    if global_hook_dir.exists() and global_hook_dir.is_dir():
        for script in sorted(global_hook_dir.iterdir()):
            if script.is_file() and os.access(script, os.X_OK):
                all_scripts.append(script)

    # Collect scripts from project directory
    if project_hook_dir.exists() and project_hook_dir.is_dir():
        for script in sorted(project_hook_dir.iterdir()):
            if script.is_file() and os.access(script, os.X_OK):
                all_scripts.append(script)

    return all_scripts


def run_hooks(
    hook_name: str,
    context: HookContext | None = None,
    project_dir: Path | None = None,
) -> bool:
    """
    Run all scripts in a hook directory.

    Executes scripts in sorted order from both global and project hook directories.
    Scripts receive context via exported environment variables.
    Hook failures are logged but don't stop execution by default (configurable).

    Args:
        hook_name: Name of the hook (e.g., "pre-task", "post-task")
        context: Hook context with task/session information
        project_dir: Project directory (defaults to current directory)

    Returns:
        True if all hooks passed (or hooks.fail_fast is false)
        False if any hook failed and hooks.fail_fast is true

    Example:
        >>> context = HookContext(
        ...     hook_name="pre-task",
        ...     task_id="cub-123",
        ...     task_title="Fix bug"
        ... )
        >>> run_hooks("pre-task", context)
        True
    """
    if not hook_name:
        raise ValueError("hook_name is required")

    if project_dir is None:
        project_dir = Path.cwd()

    # Load config to check if hooks are enabled
    config = load_config(project_dir=project_dir)

    if not config.hooks.enabled:
        return True

    # Create context if not provided
    if context is None:
        context = HookContext(hook_name=hook_name, project_dir=project_dir)

    # Find all hook scripts
    all_scripts = find_hook_scripts(hook_name, project_dir)

    # If no scripts found, return success
    if not all_scripts:
        return True

    # Get fail_fast config (default: false, meaning hooks don't stop loop)
    fail_fast = config.hooks.fail_fast

    # Prepare environment variables
    env = os.environ.copy()
    env.update(context.to_env_dict())

    # Run each script in sorted order
    failed_count = 0
    for script in all_scripts:
        try:
            # Run the script and capture output
            result = subprocess.run(
                [str(script)],
                capture_output=True,
                text=True,
                env=env,
                timeout=300,  # 5 minute timeout for hooks
                check=False,
            )

            # Log execution result
            if result.returncode == 0:
                # Success - log if there was output
                if result.stdout.strip():
                    print(f"[hook:{hook_name}] {script.name}: {result.stdout.strip()}")
            else:
                # Failure - always log
                failed_count += 1
                print(
                    f"[hook:{hook_name}] {script.name} failed with exit code {result.returncode}",
                    flush=True,
                )
                if result.stderr.strip():
                    print(result.stderr.strip(), flush=True)
                elif result.stdout.strip():
                    print(result.stdout.strip(), flush=True)

                # If fail_fast is enabled, return immediately
                if fail_fast:
                    return False

        except subprocess.TimeoutExpired:
            failed_count += 1
            print(
                f"[hook:{hook_name}] {script.name} timed out after 300 seconds",
                flush=True,
            )
            if fail_fast:
                return False

        except Exception as e:
            failed_count += 1
            print(
                f"[hook:{hook_name}] {script.name} failed with error: {e}",
                flush=True,
            )
            if fail_fast:
                return False

    # Return success if all hooks passed, or if fail_fast is disabled
    return failed_count == 0 or not fail_fast
