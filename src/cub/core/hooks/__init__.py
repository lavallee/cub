"""
Hook configuration and installation for Claude Code integration.

This module provides functionality for installing, validating, and managing
Claude Code hooks configuration in .claude/settings.json. The installer handles
creating/merging hook configuration without clobbering existing user settings.

Key Functions:
    install_hooks: Install or update hook configuration
    validate_hooks: Check hook configuration integrity
    uninstall_hooks: Remove hook configuration

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
"""

from cub.core.hooks.installer import (
    HookInstallResult,
    HookIssue,
    install_hooks,
    uninstall_hooks,
    validate_hooks,
)

__all__ = [
    "install_hooks",
    "validate_hooks",
    "uninstall_hooks",
    "HookInstallResult",
    "HookIssue",
]
