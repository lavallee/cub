"""
Unit tests for lifecycle hook discovery and execution.

Tests the new lifecycle hooks system (pre-session, end-of-task, end-of-epic,
end-of-plan) including discovery, execution, context passing, and failure handling.
"""

import json
import stat
from pathlib import Path

import pytest

from cub.core.hooks import HookConfig, HookExecutor, TaskContext, discover_hooks
from cub.core.hooks.discovery import get_default_global_hooks_dir

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def temp_project(tmp_path, monkeypatch):
    """Create a temporary project directory with hook directories."""
    # Set up XDG config home
    config_home = tmp_path / "config"
    config_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    # Create project directory
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create hook directories
    global_hooks = config_home / "cub" / "hooks"
    project_hooks = project_dir / ".cub" / "hooks"
    global_hooks.mkdir(parents=True)
    project_hooks.mkdir(parents=True)

    return {
        "project_dir": project_dir,
        "global_hooks": global_hooks,
        "project_hooks": project_hooks,
        "config_home": config_home,
    }


def create_hook_script(
    hook_dir: Path, hook_name: str, script_name: str, content: str, executable: bool = True
) -> Path:
    """
    Create a hook script.

    Args:
        hook_dir: Base hook directory (global or project)
        hook_name: Hook name (e.g., "pre-session", "end-of-task")
        script_name: Script filename (e.g., "01-test.sh")
        content: Script content (bash code)
        executable: Whether to mark script as executable

    Returns:
        Path to created script
    """
    hook_subdir = hook_dir / hook_name
    hook_subdir.mkdir(exist_ok=True)

    script_path = hook_subdir / script_name
    script_path.write_text(f"#!/bin/bash\n{content}\n")

    # Make executable if requested
    if executable:
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return script_path


# ==============================================================================
# Discovery Tests
# ==============================================================================


class TestDiscoverHooks:
    """Test hook discovery functionality."""

    def test_discover_no_hooks(self, temp_project):
        """Test discovery when no hooks exist."""
        scripts = discover_hooks("pre-session", temp_project["project_dir"])
        assert scripts == []

    def test_discover_global_hooks_only(self, temp_project):
        """Test discovery of global hooks only."""
        create_hook_script(
            temp_project["global_hooks"], "pre-session", "01-setup.sh", "echo 'setup'"
        )

        scripts = discover_hooks("pre-session", temp_project["project_dir"])
        assert len(scripts) == 1
        assert scripts[0].name == "01-setup.sh"

    def test_discover_project_hooks_only(self, temp_project):
        """Test discovery of project hooks only."""
        create_hook_script(
            temp_project["project_hooks"], "end-of-task", "notify.sh", "echo 'done'"
        )

        scripts = discover_hooks("end-of-task", temp_project["project_dir"])
        assert len(scripts) == 1
        assert scripts[0].name == "notify.sh"

    def test_discover_both_global_and_project(self, temp_project):
        """Test discovery finds both global and project hooks in correct order."""
        create_hook_script(
            temp_project["global_hooks"], "pre-session", "01-global.sh", "echo 'global'"
        )
        create_hook_script(
            temp_project["project_hooks"], "pre-session", "02-project.sh", "echo 'project'"
        )

        scripts = discover_hooks("pre-session", temp_project["project_dir"])
        assert len(scripts) == 2
        # Global hooks come first
        assert scripts[0].name == "01-global.sh"
        assert scripts[1].name == "02-project.sh"

    def test_ignore_non_executable(self, temp_project):
        """Test that non-executable files are ignored."""
        create_hook_script(
            temp_project["project_hooks"],
            "end-of-task",
            "executable.sh",
            "echo 'executable'",
            executable=True,
        )
        create_hook_script(
            temp_project["project_hooks"],
            "end-of-task",
            "not-executable.sh",
            "echo 'not executable'",
            executable=False,
        )

        scripts = discover_hooks("end-of-task", temp_project["project_dir"])
        assert len(scripts) == 1
        assert scripts[0].name == "executable.sh"

    def test_ignore_hidden_files(self, temp_project):
        """Test that hidden files (starting with .) are ignored."""
        create_hook_script(
            temp_project["project_hooks"], "pre-session", "01-visible.sh", "echo 'visible'"
        )
        create_hook_script(
            temp_project["project_hooks"], "pre-session", ".hidden.sh", "echo 'hidden'"
        )

        scripts = discover_hooks("pre-session", temp_project["project_dir"])
        assert len(scripts) == 1
        assert scripts[0].name == "01-visible.sh"

    def test_sorted_order(self, temp_project):
        """Test that hooks are returned in sorted order."""
        create_hook_script(
            temp_project["project_hooks"], "end-of-epic", "03-third.sh", "echo '3'"
        )
        create_hook_script(
            temp_project["project_hooks"], "end-of-epic", "01-first.sh", "echo '1'"
        )
        create_hook_script(
            temp_project["project_hooks"], "end-of-epic", "02-second.sh", "echo '2'"
        )

        scripts = discover_hooks("end-of-epic", temp_project["project_dir"])
        assert len(scripts) == 3
        assert scripts[0].name == "01-first.sh"
        assert scripts[1].name == "02-second.sh"
        assert scripts[2].name == "03-third.sh"

    def test_empty_hook_name_raises(self, temp_project):
        """Test that empty hook name raises ValueError."""
        with pytest.raises(ValueError, match="hook_name is required"):
            discover_hooks("", temp_project["project_dir"])

    def test_with_hook_config(self, temp_project):
        """Test discovery with custom HookConfig."""
        # Create a custom global hooks directory
        custom_global = temp_project["config_home"] / "custom_hooks"
        custom_global.mkdir()

        create_hook_script(custom_global, "pre-session", "custom.sh", "echo 'custom'")

        config = HookConfig(
            global_hooks_dir=str(custom_global),
        )

        scripts = discover_hooks("pre-session", temp_project["project_dir"], config)
        assert len(scripts) == 1
        assert scripts[0].name == "custom.sh"


class TestGetDefaultGlobalHooksDir:
    """Test getting default global hooks directory."""

    def test_returns_path(self, tmp_path, monkeypatch):
        """Test that it returns a valid Path object."""
        config_home = tmp_path / "config"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

        hooks_dir = get_default_global_hooks_dir()
        assert isinstance(hooks_dir, Path)
        assert "cub" in str(hooks_dir)
        assert "hooks" in str(hooks_dir)


# ==============================================================================
# Executor Tests
# ==============================================================================


class TestHookExecutor:
    """Test hook execution functionality."""

    def test_execute_no_hooks(self, temp_project):
        """Test execution when no hooks exist."""
        executor = HookExecutor(temp_project["project_dir"])
        context = TaskContext(
            task_id="test-1",
            task_title="Test task",
            status="closed",
            success=True,
            project_dir=str(temp_project["project_dir"]),
        )

        results = executor.run("end-of-task", context)
        assert results == []

    def test_execute_successful_hook(self, temp_project):
        """Test execution of a successful hook."""
        create_hook_script(
            temp_project["project_hooks"], "pre-session", "test.sh", "echo 'success'\nexit 0"
        )

        executor = HookExecutor(temp_project["project_dir"])
        context = TaskContext(
            task_id="test-1",
            task_title="Test",
            status="closed",
            success=True,
            project_dir=str(temp_project["project_dir"]),
        )

        results = executor.run("pre-session", context)
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].exit_code == 0
        assert "success" in results[0].stdout

    def test_context_passed_via_env(self, temp_project):
        """Test that context is passed via CUB_HOOK_CONTEXT environment variable."""
        # Script that reads context and outputs task_id
        create_hook_script(
            temp_project["project_hooks"],
            "end-of-task",
            "check-context.sh",
            """
echo "$CUB_HOOK_CONTEXT" > /tmp/hook_context.json
echo "Hook name: $CUB_HOOK_NAME"
echo "Project dir: $CUB_PROJECT_DIR"
exit 0
""",
        )

        executor = HookExecutor(temp_project["project_dir"])
        context = TaskContext(
            task_id="test-123",
            task_title="Test Task",
            status="closed",
            success=True,
            project_dir=str(temp_project["project_dir"]),
        )

        results = executor.run("end-of-task", context)
        assert len(results) == 1
        assert results[0].success is True

        # Check that environment variables were set
        stdout = results[0].stdout
        assert "Hook name: end-of-task" in stdout
        assert f"Project dir: {temp_project['project_dir']}" in stdout

        # Check that context JSON was written
        context_file = Path("/tmp/hook_context.json")
        if context_file.exists():
            context_data = json.loads(context_file.read_text())
            assert context_data["task_id"] == "test-123"
            assert context_data["task_title"] == "Test Task"

    def test_hook_failure_without_fail_on_error(self, temp_project):
        """Test that failed hooks don't raise when fail_on_error is False."""
        create_hook_script(
            temp_project["project_hooks"], "end-of-task", "fail.sh", "echo 'error' >&2\nexit 1"
        )

        config = HookConfig(fail_on_error=False)
        executor = HookExecutor(temp_project["project_dir"], config)
        context = TaskContext(
            task_id="test-1",
            task_title="Test",
            status="closed",
            success=True,
            project_dir=str(temp_project["project_dir"]),
        )

        # Should not raise
        results = executor.run("end-of-task", context)
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].exit_code == 1
        assert "error" in results[0].stderr

    def test_hook_failure_with_fail_on_error(self, temp_project):
        """Test that failed hooks raise when fail_on_error is True."""
        create_hook_script(
            temp_project["project_hooks"], "pre-session", "fail.sh", "exit 1"
        )

        config = HookConfig(fail_on_error=True)
        executor = HookExecutor(temp_project["project_dir"], config)
        context = TaskContext(
            task_id="test-1",
            task_title="Test",
            status="closed",
            success=True,
            project_dir=str(temp_project["project_dir"]),
        )

        with pytest.raises(RuntimeError, match="failed with exit code 1"):
            executor.run("pre-session", context)

    def test_multiple_hooks_in_order(self, temp_project):
        """Test that multiple hooks execute in sorted order."""
        create_hook_script(
            temp_project["project_hooks"],
            "end-of-epic",
            "01-first.sh",
            "echo 'first'\nexit 0",
        )
        create_hook_script(
            temp_project["project_hooks"],
            "end-of-epic",
            "02-second.sh",
            "echo 'second'\nexit 0",
        )

        executor = HookExecutor(temp_project["project_dir"])
        context = TaskContext(
            task_id="test-1",
            task_title="Test",
            status="closed",
            success=True,
            project_dir=str(temp_project["project_dir"]),
        )

        results = executor.run("end-of-epic", context)
        assert len(results) == 2
        assert results[0].success is True
        assert "first" in results[0].stdout
        assert results[1].success is True
        assert "second" in results[1].stdout

    def test_hook_timeout(self, temp_project):
        """Test that hooks timeout after configured duration."""
        # Script that sleeps longer than timeout
        create_hook_script(
            temp_project["project_hooks"], "end-of-plan", "slow.sh", "sleep 10\nexit 0"
        )

        config = HookConfig(timeout_seconds=1)
        executor = HookExecutor(temp_project["project_dir"], config)
        context = TaskContext(
            task_id="test-1",
            task_title="Test",
            status="closed",
            success=True,
            project_dir=str(temp_project["project_dir"]),
        )

        results = executor.run("end-of-plan", context)
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].exit_code == -1
        assert "timed out" in results[0].error_message

    def test_disabled_hook(self, temp_project):
        """Test that disabled hooks don't run."""
        create_hook_script(
            temp_project["project_hooks"], "pre-session", "test.sh", "echo 'should not run'"
        )

        config = HookConfig(enabled_hooks=["end-of-task"])  # pre-session not enabled
        executor = HookExecutor(temp_project["project_dir"], config)
        context = TaskContext(
            task_id="test-1",
            task_title="Test",
            status="closed",
            success=True,
            project_dir=str(temp_project["project_dir"]),
        )

        results = executor.run("pre-session", context)
        assert results == []

    def test_hooks_globally_disabled(self, temp_project):
        """Test that no hooks run when globally disabled."""
        create_hook_script(
            temp_project["project_hooks"], "end-of-task", "test.sh", "echo 'should not run'"
        )

        config = HookConfig(enabled=False)
        executor = HookExecutor(temp_project["project_dir"], config)
        context = TaskContext(
            task_id="test-1",
            task_title="Test",
            status="closed",
            success=True,
            project_dir=str(temp_project["project_dir"]),
        )

        results = executor.run("end-of-task", context)
        assert results == []

    def test_hook_captures_stderr(self, temp_project):
        """Test that stderr is captured from hooks."""
        create_hook_script(
            temp_project["project_hooks"],
            "end-of-task",
            "stderr.sh",
            "echo 'error message' >&2\nexit 0",
        )

        executor = HookExecutor(temp_project["project_dir"])
        context = TaskContext(
            task_id="test-1",
            task_title="Test",
            status="closed",
            success=True,
            project_dir=str(temp_project["project_dir"]),
        )

        results = executor.run("end-of-task", context)
        assert len(results) == 1
        assert results[0].success is True
        assert "error message" in results[0].stderr

    def test_hook_execution_duration(self, temp_project):
        """Test that execution duration is measured."""
        create_hook_script(
            temp_project["project_hooks"], "pre-session", "test.sh", "sleep 0.1\nexit 0"
        )

        executor = HookExecutor(temp_project["project_dir"])
        context = TaskContext(
            task_id="test-1",
            task_title="Test",
            status="closed",
            success=True,
            project_dir=str(temp_project["project_dir"]),
        )

        results = executor.run("pre-session", context)
        assert len(results) == 1
        assert results[0].duration_seconds >= 0.1
        assert results[0].duration_seconds < 1.0  # Should be quick
