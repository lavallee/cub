"""
Tests for hook configuration installer.

Tests cover:
- Installation: fresh install, idempotent re-install, force overwrite
- Validation: missing files, invalid JSON, configuration checks
- Uninstallation: clean removal, preserving other hooks
- Edge cases: missing hook script, permissions, existing settings
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cub.core.hooks import (
    HookInstallResult,
    HookIssue,
    install_hooks,
    uninstall_hooks,
    validate_hooks,
)


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with .cub structure."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create .cub directory structure
    cub_dir = project_dir / ".cub"
    cub_dir.mkdir()

    # Create hook script directory
    hooks_dir = cub_dir / "scripts" / "hooks"
    hooks_dir.mkdir(parents=True)

    # Create dummy hook script
    hook_script = hooks_dir / "cub-hook.sh"
    hook_script.write_text("#!/bin/bash\necho 'hook'\n")
    hook_script.chmod(0o755)

    return project_dir


@pytest.fixture
def temp_project_no_script(tmp_path: Path) -> Path:
    """Create a temporary project directory without hook script."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    cub_dir = project_dir / ".cub"
    cub_dir.mkdir()

    return project_dir


class TestInstallHooks:
    """Tests for install_hooks function."""

    def test_fresh_install(self, temp_project: Path) -> None:
        """Test installing hooks on a fresh project."""
        result = install_hooks(temp_project)

        assert result.success
        assert len(result.hooks_installed) == 6
        assert "PostToolUse" in result.hooks_installed
        assert "SessionStart" in result.hooks_installed
        assert result.settings_file == str(temp_project / ".claude" / "settings.json")

        # Check settings file was created
        settings_file = temp_project / ".claude" / "settings.json"
        assert settings_file.exists()

        # Check settings content
        with settings_file.open("r") as f:
            settings = json.load(f)

        assert "hooks" in settings
        assert "PostToolUse" in settings["hooks"]
        assert len(settings["hooks"]) == 6

    def test_idempotent_install(self, temp_project: Path) -> None:
        """Test that re-installing hooks is safe (idempotent)."""
        # First install
        result1 = install_hooks(temp_project)
        assert result1.success
        assert len(result1.hooks_installed) == 6

        # Second install
        result2 = install_hooks(temp_project)
        assert result2.success
        assert len(result2.hooks_installed) == 0  # Nothing new to install
        assert "already configured" in result2.message.lower()

    def test_force_install(self, temp_project: Path) -> None:
        """Test force overwrite of existing hooks."""
        # First install
        install_hooks(temp_project)

        # Modify settings
        settings_file = temp_project / ".claude" / "settings.json"
        with settings_file.open("r") as f:
            settings = json.load(f)
        settings["hooks"]["PostToolUse"][0]["hooks"][0]["timeout"] = 999

        with settings_file.open("w") as f:
            json.dump(settings, f)

        # Force install
        result = install_hooks(temp_project, force=True)
        assert result.success
        assert len(result.hooks_installed) == 6

        # Check timeout was reset
        with settings_file.open("r") as f:
            settings = json.load(f)
        assert settings["hooks"]["PostToolUse"][0]["hooks"][0]["timeout"] == 10

    def test_preserves_existing_settings(self, temp_project: Path) -> None:
        """Test that existing non-hook settings are preserved."""
        # Create existing settings
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir(exist_ok=True)
        settings_file = claude_dir / "settings.json"

        existing_settings = {
            "statusLine": {"type": "command", "command": "date"},
            "someOtherSetting": "value",
        }
        with settings_file.open("w") as f:
            json.dump(existing_settings, f)

        # Install hooks
        result = install_hooks(temp_project)
        assert result.success

        # Check existing settings preserved
        with settings_file.open("r") as f:
            settings = json.load(f)

        assert settings["statusLine"] == existing_settings["statusLine"]
        assert settings["someOtherSetting"] == existing_settings["someOtherSetting"]
        assert "hooks" in settings

    def test_appends_to_existing_hooks(self, temp_project: Path) -> None:
        """Test that cub hooks are appended to existing hook configuration."""
        # Create existing hook configuration
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir(exist_ok=True)
        settings_file = claude_dir / "settings.json"

        existing_settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write",
                        "hooks": [{"type": "command", "command": "echo 'other hook'"}],
                    }
                ]
            }
        }
        with settings_file.open("w") as f:
            json.dump(existing_settings, f)

        # Install hooks
        result = install_hooks(temp_project)
        assert result.success

        # Check both hooks present
        with settings_file.open("r") as f:
            settings = json.load(f)

        post_tool_hooks = settings["hooks"]["PostToolUse"]
        assert len(post_tool_hooks) == 2
        assert "other hook" in str(post_tool_hooks[0])
        assert "cub-hook.sh" in str(post_tool_hooks[1])

    def test_missing_hook_script_copies_from_template(self, temp_project_no_script: Path) -> None:
        """Test that missing hook script is copied from template."""
        # Mock template file
        template_script = Path(__file__).parent.parent / "templates" / "scripts" / "cub-hook.sh"

        if template_script.exists():
            # Template exists, test copy
            result = install_hooks(temp_project_no_script)
            assert result.success

            hook_script = temp_project_no_script / ".cub" / "scripts" / "hooks" / "cub-hook.sh"
            assert hook_script.exists()
            assert hook_script.stat().st_mode & 0o111  # Executable
        else:
            # Template doesn't exist, expect error
            result = install_hooks(temp_project_no_script)
            assert not result.success
            assert any(issue.severity == "error" for issue in result.issues)
            assert "Hook script not found" in result.issues[0].message

    def test_makes_hook_script_executable(self, temp_project: Path) -> None:
        """Test that non-executable hook script is made executable."""
        hook_script = temp_project / ".cub" / "scripts" / "hooks" / "cub-hook.sh"
        hook_script.chmod(0o644)  # Remove execute bit

        result = install_hooks(temp_project)
        assert result.success

        # Check executable bit set
        assert hook_script.stat().st_mode & 0o111

    def test_invalid_existing_settings_json(self, temp_project: Path) -> None:
        """Test handling of invalid JSON in existing settings file."""
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir(exist_ok=True)
        settings_file = claude_dir / "settings.json"

        # Write invalid JSON
        settings_file.write_text("{invalid json")

        result = install_hooks(temp_project)
        # Should succeed but warn about invalid JSON
        assert result.success
        assert any(
            issue.severity == "warning" and "parse" in issue.message.lower()
            for issue in result.issues
        )


class TestValidateHooks:
    """Tests for validate_hooks function."""

    def test_validates_successful_install(self, temp_project: Path) -> None:
        """Test validation of successfully installed hooks."""
        install_hooks(temp_project)
        issues = validate_hooks(temp_project)

        # Should have no errors (might have info messages)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_detects_missing_settings_file(self, temp_project: Path) -> None:
        """Test detection of missing settings file."""
        issues = validate_hooks(temp_project)

        assert len(issues) > 0
        assert issues[0].severity == "error"
        assert "not found" in issues[0].message.lower()

    def test_detects_invalid_json(self, temp_project: Path) -> None:
        """Test detection of invalid JSON in settings file."""
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir(exist_ok=True)
        settings_file = claude_dir / "settings.json"
        settings_file.write_text("{invalid json")

        issues = validate_hooks(temp_project)

        assert len(issues) > 0
        assert issues[0].severity == "error"
        assert "invalid json" in issues[0].message.lower()

    def test_detects_missing_hook_script(self, temp_project: Path) -> None:
        """Test detection of missing hook script."""
        # Install first (creates settings)
        install_hooks(temp_project)

        # Remove hook script
        hook_script = temp_project / ".cub" / "scripts" / "hooks" / "cub-hook.sh"
        hook_script.unlink()

        issues = validate_hooks(temp_project)

        errors = [i for i in issues if i.severity == "error"]
        assert any("not found" in issue.message.lower() for issue in errors)

    def test_detects_non_executable_hook_script(self, temp_project: Path) -> None:
        """Test detection of non-executable hook script."""
        install_hooks(temp_project)

        # Remove execute bit
        hook_script = temp_project / ".cub" / "scripts" / "hooks" / "cub-hook.sh"
        hook_script.chmod(0o644)

        issues = validate_hooks(temp_project)

        errors = [i for i in issues if i.severity == "error"]
        assert any("not executable" in issue.message.lower() for issue in errors)

    def test_detects_missing_hook_events(self, temp_project: Path) -> None:
        """Test detection of missing hook event configuration."""
        # Create minimal settings without all hooks
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir(exist_ok=True)
        settings_file = claude_dir / "settings.json"

        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "../.cub/scripts/hooks/cub-hook.sh PostToolUse",
                            }
                        ],
                    }
                ]
            }
        }
        with settings_file.open("w") as f:
            json.dump(settings, f)

        issues = validate_hooks(temp_project)

        # Should have info messages about missing hooks
        info_issues = [i for i in issues if i.severity == "info"]
        assert len(info_issues) >= 5  # 5 missing events

    def test_detects_hooks_without_cub_script(self, temp_project: Path) -> None:
        """Test detection of hook events not configured with cub script."""
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir(exist_ok=True)
        settings_file = claude_dir / "settings.json"

        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [{"type": "command", "command": "echo 'other hook'"}],
                    }
                ]
            }
        }
        with settings_file.open("w") as f:
            json.dump(settings, f)

        issues = validate_hooks(temp_project)

        warnings = [i for i in issues if i.severity == "warning"]
        assert any(
            "does not reference" in issue.message.lower() and issue.hook_name == "PostToolUse"
            for issue in warnings
        )

    def test_checks_python_handler_importable(self, temp_project: Path) -> None:
        """Test validation checks Python handler is importable."""
        install_hooks(temp_project)

        # Mock import failure
        with patch("builtins.__import__", side_effect=ImportError("Module not found")):
            issues = validate_hooks(temp_project)

            errors = [i for i in issues if i.severity == "error"]
            assert any("not importable" in issue.message.lower() for issue in errors)


class TestUninstallHooks:
    """Tests for uninstall_hooks function."""

    def test_removes_cub_hooks(self, temp_project: Path) -> None:
        """Test removal of cub hooks from settings."""
        # Install first
        install_hooks(temp_project)

        # Verify installed
        settings_file = temp_project / ".claude" / "settings.json"
        with settings_file.open("r") as f:
            settings = json.load(f)
        assert "PostToolUse" in settings["hooks"]

        # Uninstall
        uninstall_hooks(temp_project)

        # Check removed
        with settings_file.open("r") as f:
            settings = json.load(f)
        assert "hooks" in settings
        assert len(settings["hooks"]) == 0 or "PostToolUse" not in settings["hooks"]

    def test_preserves_other_hooks(self, temp_project: Path) -> None:
        """Test that non-cub hooks are preserved during uninstall."""
        # Create settings with both cub and other hooks
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir(exist_ok=True)
        settings_file = claude_dir / "settings.json"

        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write",
                        "hooks": [{"type": "command", "command": "echo 'keep this'"}],
                    },
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "../.cub/scripts/hooks/cub-hook.sh PostToolUse",
                            }
                        ],
                    },
                ]
            }
        }
        with settings_file.open("w") as f:
            json.dump(settings, f)

        # Uninstall
        uninstall_hooks(temp_project)

        # Check other hook preserved
        with settings_file.open("r") as f:
            settings = json.load(f)

        assert "PostToolUse" in settings["hooks"]
        post_hooks = settings["hooks"]["PostToolUse"]
        assert len(post_hooks) == 1
        assert "keep this" in str(post_hooks[0])
        assert "cub-hook.sh" not in str(post_hooks[0])

    def test_preserves_other_settings(self, temp_project: Path) -> None:
        """Test that non-hook settings are preserved during uninstall."""
        # Install with other settings
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir(exist_ok=True)
        settings_file = claude_dir / "settings.json"

        settings = {"statusLine": {"type": "command", "command": "date"}}
        with settings_file.open("w") as f:
            json.dump(settings, f)

        install_hooks(temp_project)
        uninstall_hooks(temp_project)

        # Check statusLine preserved
        with settings_file.open("r") as f:
            settings = json.load(f)

        assert "statusLine" in settings
        assert settings["statusLine"]["command"] == "date"

    def test_handles_missing_settings_file(self, temp_project: Path) -> None:
        """Test uninstall handles missing settings file gracefully."""
        # Should not raise exception
        uninstall_hooks(temp_project)

    def test_handles_invalid_json(self, temp_project: Path) -> None:
        """Test uninstall handles invalid JSON gracefully."""
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir(exist_ok=True)
        settings_file = claude_dir / "settings.json"
        settings_file.write_text("{invalid json")

        # Should not raise exception
        uninstall_hooks(temp_project)


class TestHookIssue:
    """Tests for HookIssue model."""

    def test_creates_issue_with_all_fields(self) -> None:
        """Test creating issue with all fields."""
        issue = HookIssue(
            severity="error",
            message="Something went wrong",
            hook_name="PostToolUse",
            file_path="/path/to/file",
        )

        assert issue.severity == "error"
        assert issue.message == "Something went wrong"
        assert issue.hook_name == "PostToolUse"
        assert issue.file_path == "/path/to/file"

    def test_creates_issue_with_minimal_fields(self) -> None:
        """Test creating issue with only required fields."""
        issue = HookIssue(severity="warning", message="Warning message")

        assert issue.severity == "warning"
        assert issue.message == "Warning message"
        assert issue.hook_name is None
        assert issue.file_path is None


class TestHookInstallResult:
    """Tests for HookInstallResult model."""

    def test_creates_result_success(self) -> None:
        """Test creating successful result."""
        result = HookInstallResult(
            success=True,
            hooks_installed=["PostToolUse", "Stop"],
            message="Installed successfully",
        )

        assert result.success
        assert len(result.hooks_installed) == 2
        assert result.message == "Installed successfully"
        assert len(result.issues) == 0

    def test_creates_result_with_issues(self) -> None:
        """Test creating result with validation issues."""
        issue = HookIssue(severity="warning", message="Minor issue")
        result = HookInstallResult(success=True, hooks_installed=["PostToolUse"], issues=[issue])

        assert result.success
        assert len(result.issues) == 1
        assert result.issues[0].severity == "warning"
