"""
Hook configuration installer for Claude Code.

Manages the installation, validation, and removal of Claude Code hooks configuration
in .claude/settings.json. The installer performs non-destructive updates by merging
new hook configuration with existing settings.

Implementation:
    - Reads existing .claude/settings.json (if present)
    - Merges hook configuration with existing content
    - Writes updated configuration back to file
    - Validates hook script existence and permissions
    - Provides detailed results and issue reporting
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HookIssue(BaseModel):
    """Represents a validation issue with hook configuration."""

    severity: str = Field(description="Issue severity: error, warning, info")
    message: str = Field(description="Human-readable issue description")
    hook_name: str | None = Field(default=None, description="Hook name if applicable")
    file_path: str | None = Field(default=None, description="Related file path if applicable")


class HookInstallResult(BaseModel):
    """Result of hook installation operation."""

    success: bool = Field(description="Whether installation succeeded")
    hooks_installed: list[str] = Field(
        default_factory=list, description="List of hooks successfully installed"
    )
    issues: list[HookIssue] = Field(default_factory=list, description="Issues encountered")
    settings_file: str | None = Field(
        default=None, description="Path to settings file that was modified"
    )
    message: str | None = Field(default=None, description="Summary message")


def install_hooks(project_dir: Path | str, force: bool = False) -> HookInstallResult:
    """
    Install Claude Code hooks configuration.

    Creates or updates .claude/settings.json with hook configuration that
    integrates cub artifact capture. Existing settings are preserved.

    Args:
        project_dir: Project root directory
        force: If True, overwrite existing hook configuration

    Returns:
        HookInstallResult with installation details and any issues

    Example:
        >>> result = install_hooks(Path("/path/to/project"))
        >>> if result.success:
        ...     print(f"Installed {len(result.hooks_installed)} hooks")
    """
    project_path = Path(project_dir)
    claude_dir = project_path / ".claude"
    settings_file = claude_dir / "settings.json"
    hook_script = project_path / ".cub" / "scripts" / "hooks" / "cub-hook.sh"

    issues: list[HookIssue] = []
    hooks_installed: list[str] = []

    # Validate hook script exists
    if not hook_script.exists():
        # Try to copy from templates
        template_path = Path(__file__).parent.parent.parent.parent.parent
        template_hook = template_path / "templates" / "scripts" / "cub-hook.sh"
        if template_hook.exists():
            # Create target directory
            hook_script.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(template_hook, hook_script)
            hook_script.chmod(0o755)  # Make executable
            logger.info(f"Copied hook script from template to {hook_script}")
        else:
            issues.append(
                HookIssue(
                    severity="error",
                    message=f"Hook script not found at {hook_script}",
                    file_path=str(hook_script),
                )
            )
            return HookInstallResult(
                success=False,
                issues=issues,
                message="Hook script missing and template not found",
            )

    # Ensure hook script is executable
    if not hook_script.stat().st_mode & 0o111:
        try:
            hook_script.chmod(0o755)
        except OSError as e:
            issues.append(
                HookIssue(
                    severity="warning",
                    message=f"Could not make hook script executable: {e}",
                    file_path=str(hook_script),
                )
            )

    # Load existing settings
    existing_settings: dict[str, Any] = {}
    if settings_file.exists():
        try:
            with settings_file.open("r", encoding="utf-8") as f:
                existing_settings = json.load(f)
            logger.info(f"Loaded existing settings from {settings_file}")
        except (json.JSONDecodeError, OSError) as e:
            issues.append(
                HookIssue(
                    severity="warning",
                    message=f"Could not parse existing settings.json: {e}",
                    file_path=str(settings_file),
                )
            )

    # Build hook configuration
    hook_events = [
        "PostToolUse",
        "SessionStart",
        "Stop",
        "SessionEnd",
        "PreCompact",
        "UserPromptSubmit",
    ]

    # Relative path from .claude/ to .cub/scripts/hooks/
    hook_script_relative = "../.cub/scripts/hooks/cub-hook.sh"

    # Create hook configuration for each event
    hooks_config: dict[str, Any] = existing_settings.get("hooks", {})

    for event in hook_events:
        # Build hook entry
        hook_entry = {
            "matcher": "*",  # Match all tools (for PostToolUse)
            "hooks": [
                {
                    "type": "command",
                    "command": f"{hook_script_relative} {event}",
                    "timeout": 10,  # Fast timeout for quick filter script
                }
            ],
        }

        if force or event not in hooks_config:
            # Install or overwrite
            hooks_config[event] = [hook_entry]
            hooks_installed.append(event)
        else:
            # Check if our hook is already present
            existing_entries = hooks_config.get(event, [])
            has_cub_hook = any(
                hook_script_relative in str(hook.get("hooks", []))
                for hook in existing_entries
                if isinstance(hook, dict)
            )

            if has_cub_hook:
                logger.info(f"Hook {event} already configured, skipping")
            else:
                # Append to existing hooks
                existing_entries.append(hook_entry)
                hooks_config[event] = existing_entries
                hooks_installed.append(event)

    # Merge hooks back into settings
    updated_settings = existing_settings.copy()
    updated_settings["hooks"] = hooks_config

    # Write updated settings
    try:
        claude_dir.mkdir(parents=True, exist_ok=True)
        with settings_file.open("w", encoding="utf-8") as f:
            json.dump(updated_settings, f, indent=2)
            f.write("\n")  # Trailing newline
        logger.info(f"Wrote updated settings to {settings_file}")
    except OSError as e:
        issues.append(
            HookIssue(
                severity="error",
                message=f"Failed to write settings.json: {e}",
                file_path=str(settings_file),
            )
        )
        return HookInstallResult(
            success=False,
            issues=issues,
            settings_file=str(settings_file),
            message="Failed to write settings file",
        )

    # Success
    message = (
        f"Installed {len(hooks_installed)} hooks"
        if hooks_installed
        else "All hooks already configured"
    )
    return HookInstallResult(
        success=True,
        hooks_installed=hooks_installed,
        issues=issues,
        settings_file=str(settings_file),
        message=message,
    )


def validate_hooks(project_dir: Path | str) -> list[HookIssue]:
    """
    Validate hook configuration.

    Checks that:
    - .claude/settings.json exists and is valid JSON
    - Hook script exists and is executable
    - Hook configuration references correct paths
    - Python handler module is importable

    Args:
        project_dir: Project root directory

    Returns:
        List of validation issues (empty if all checks pass)

    Example:
        >>> issues = validate_hooks(Path("/path/to/project"))
        >>> for issue in issues:
        ...     print(f"{issue.severity}: {issue.message}")
    """
    project_path = Path(project_dir)
    claude_dir = project_path / ".claude"
    settings_file = claude_dir / "settings.json"
    hook_script = project_path / ".cub" / "scripts" / "hooks" / "cub-hook.sh"

    issues: list[HookIssue] = []

    # Check settings file exists
    if not settings_file.exists():
        issues.append(
            HookIssue(
                severity="error",
                message=".claude/settings.json not found (hooks not installed)",
                file_path=str(settings_file),
            )
        )
        return issues

    # Check settings file is valid JSON
    try:
        with settings_file.open("r", encoding="utf-8") as f:
            settings = json.load(f)
    except json.JSONDecodeError as e:
        issues.append(
            HookIssue(
                severity="error",
                message=f"Invalid JSON in settings.json: {e}",
                file_path=str(settings_file),
            )
        )
        return issues
    except OSError as e:
        issues.append(
            HookIssue(
                severity="error",
                message=f"Could not read settings.json: {e}",
                file_path=str(settings_file),
            )
        )
        return issues

    # Check hook configuration exists
    hooks_config = settings.get("hooks", {})
    if not hooks_config:
        issues.append(
            HookIssue(
                severity="warning",
                message="No hooks configured in settings.json",
                file_path=str(settings_file),
            )
        )
        return issues

    # Check hook script exists
    if not hook_script.exists():
        issues.append(
            HookIssue(
                severity="error",
                message=f"Hook script not found at {hook_script}",
                file_path=str(hook_script),
            )
        )
    else:
        # Check hook script is executable
        if not hook_script.stat().st_mode & 0o111:
            issues.append(
                HookIssue(
                    severity="error",
                    message=f"Hook script is not executable: {hook_script}",
                    file_path=str(hook_script),
                )
            )

    # Check each configured hook references the correct script
    hook_script_name = "cub-hook.sh"
    expected_events = [
        "PostToolUse",
        "SessionStart",
        "Stop",
        "SessionEnd",
        "PreCompact",
        "UserPromptSubmit",
    ]

    for event in expected_events:
        if event not in hooks_config:
            issues.append(
                HookIssue(
                    severity="info",
                    message=f"Hook {event} not configured",
                    hook_name=event,
                )
            )
            continue

        # Check if hook references our script
        event_hooks = hooks_config[event]
        has_cub_hook = False
        for hook_entry in event_hooks:
            if not isinstance(hook_entry, dict):
                continue
            for hook_def in hook_entry.get("hooks", []):
                if not isinstance(hook_def, dict):
                    continue
                command = hook_def.get("command", "")
                if hook_script_name in command:
                    has_cub_hook = True
                    break
            if has_cub_hook:
                break

        if not has_cub_hook:
            issues.append(
                HookIssue(
                    severity="warning",
                    message=f"Hook {event} does not reference {hook_script_name}",
                    hook_name=event,
                )
            )

    # Check Python handler is importable
    try:
        import cub.core.harness.hooks  # noqa: F401
    except ImportError as e:
        issues.append(
            HookIssue(
                severity="error",
                message=f"Python hook handler not importable: {e}",
            )
        )

    return issues


def uninstall_hooks(project_dir: Path | str) -> None:
    """
    Remove Claude Code hooks configuration.

    Removes cub hook entries from .claude/settings.json. Preserves other
    settings and non-cub hooks.

    Args:
        project_dir: Project root directory

    Example:
        >>> uninstall_hooks(Path("/path/to/project"))
    """
    project_path = Path(project_dir)
    settings_file = project_path / ".claude" / "settings.json"

    if not settings_file.exists():
        logger.info("No settings file found, nothing to uninstall")
        return

    # Load existing settings
    try:
        with settings_file.open("r", encoding="utf-8") as f:
            settings = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not read settings.json: {e}")
        return

    # Remove cub hooks
    hooks_config = settings.get("hooks", {})
    hook_script_name = "cub-hook.sh"
    modified = False

    for event, event_hooks in list(hooks_config.items()):
        if not isinstance(event_hooks, list):
            continue

        # Filter out cub hooks
        filtered_hooks = []
        for hook_entry in event_hooks:
            if not isinstance(hook_entry, dict):
                filtered_hooks.append(hook_entry)
                continue

            # Filter out cub hook definitions
            hook_defs = hook_entry.get("hooks", [])
            filtered_defs = [
                h
                for h in hook_defs
                if not (isinstance(h, dict) and hook_script_name in h.get("command", ""))
            ]

            if filtered_defs:
                hook_entry["hooks"] = filtered_defs
                filtered_hooks.append(hook_entry)
            else:
                modified = True

        if filtered_hooks:
            hooks_config[event] = filtered_hooks
        else:
            del hooks_config[event]
            modified = True

    # Write back if modified
    if modified:
        settings["hooks"] = hooks_config
        try:
            with settings_file.open("w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
                f.write("\n")
            logger.info(f"Removed cub hooks from {settings_file}")
        except OSError as e:
            logger.error(f"Failed to write settings.json: {e}")
    else:
        logger.info("No cub hooks found in settings.json")
