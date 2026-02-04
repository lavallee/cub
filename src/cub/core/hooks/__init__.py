"""
Hook configuration and installation for Claude Code integration.

This module provides functionality for installing, validating, and managing
Claude Code hooks configuration in .claude/settings.json. The installer handles
creating/merging hook configuration without clobbering existing user settings.

It also defines the context models that carry data to lifecycle hook scripts
at key execution points: pre-session, end-of-task, end-of-epic, end-of-plan.

Key Functions:
    install_hooks: Install or update hook configuration
    validate_hooks: Check hook configuration integrity
    uninstall_hooks: Remove hook configuration

Key Models:
    SessionContext: Context for pre-session hook
    TaskContext: Context for end-of-task hook
    EpicContext: Context for end-of-epic hook
    PlanContext: Context for end-of-plan hook
    HookResult: Result from hook execution
    HookConfig: Hook configuration settings

Architecture:
    - Non-destructive: Preserves existing settings while adding hooks
    - Idempotent: Re-running installation is safe
    - Validated: Checks for common configuration issues

Usage:
    from cub.core.hooks import install_hooks, validate_hooks

    # Install hooks
    result = install_hooks(project_dir)
    if result.success:
        print(f"Installed {len(result.hooks_installed)} hooks")

    # Validate installation
    issues = validate_hooks(project_dir)
    if issues:
        for issue in issues:
            print(f"Warning: {issue.message}")

    # Use context models
    from cub.core.hooks import TaskContext, HookResult

    context = TaskContext(
        task_id="cub-123",
        task_title="Fix bug",
        status="closed",
        success=True,
        project_dir="/path/to/project"
    )
    json_str = context.to_json()  # Serialize for env var
"""

from cub.core.hooks.installer import (
    HookInstallResult,
    HookIssue,
    install_hooks,
    uninstall_hooks,
    validate_hooks,
)
from cub.core.hooks.models import (
    EpicContext,
    HookConfig,
    HookResult,
    PlanContext,
    SessionContext,
    TaskContext,
)

__all__ = [
    # Installer functions
    "install_hooks",
    "validate_hooks",
    "uninstall_hooks",
    "HookInstallResult",
    "HookIssue",
    # Context models
    "SessionContext",
    "TaskContext",
    "EpicContext",
    "PlanContext",
    # Result and config models
    "HookResult",
    "HookConfig",
]
