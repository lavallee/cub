"""
Unit tests for hook execution.

Tests hook discovery, execution order, context passing,
failure handling, and configuration.
"""

import stat
from pathlib import Path

import pytest

from cub.core.config import clear_cache
from cub.utils.hooks import (
    HookContext,
    clear_async_hooks,
    find_hook_scripts,
    run_hooks,
    run_hooks_async,
    wait_async_hooks,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def temp_project(tmp_path, monkeypatch):
    """Create a temporary project directory with XDG config."""
    # Set up XDG config home
    config_home = tmp_path / "config"
    config_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    # Create project directory
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    # Create hook directories
    global_hooks = config_home / "cub" / "hooks"
    project_hooks = project_dir / ".cub" / "hooks"
    global_hooks.mkdir(parents=True)
    project_hooks.mkdir(parents=True)

    # Clear config cache to ensure fresh config loading
    clear_cache()

    return {
        "project_dir": project_dir,
        "global_hooks": global_hooks,
        "project_hooks": project_hooks,
        "config_home": config_home,
    }


def create_hook_script(hook_dir: Path, hook_name: str, script_name: str, content: str) -> Path:
    """
    Create an executable hook script.

    Args:
        hook_dir: Base hook directory (global or project)
        hook_name: Hook name (e.g., "pre-task")
        script_name: Script filename (e.g., "01-test.sh")
        content: Script content (bash code)

    Returns:
        Path to created script
    """
    hook_subdir = hook_dir / f"{hook_name}.d"
    hook_subdir.mkdir(exist_ok=True)

    script_path = hook_subdir / script_name
    script_path.write_text(f"#!/bin/bash\n{content}\n")

    # Make executable
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return script_path


# ==============================================================================
# HookContext Tests
# ==============================================================================


class TestHookContext:
    """Test the HookContext dataclass."""

    def test_minimal_context(self):
        """Test context with only required fields."""
        context = HookContext(hook_name="pre-task")
        env_dict = context.to_env_dict()

        assert env_dict["CUB_HOOK_NAME"] == "pre-task"
        assert env_dict["CUB_PROJECT_DIR"]  # Should have default cwd
        assert env_dict["CUB_TASK_ID"] == ""
        assert env_dict["CUB_TASK_TITLE"] == ""
        assert env_dict["CUB_EXIT_CODE"] == ""
        assert env_dict["CUB_HARNESS"] == ""
        assert env_dict["CUB_SESSION_ID"] == ""

    def test_full_context(self, tmp_path):
        """Test context with all fields populated."""
        context = HookContext(
            hook_name="post-task",
            project_dir=tmp_path,
            task_id="cub-123",
            task_title="Fix bug",
            exit_code=0,
            harness="claude",
            session_id="session-456",
        )
        env_dict = context.to_env_dict()

        assert env_dict["CUB_HOOK_NAME"] == "post-task"
        assert env_dict["CUB_PROJECT_DIR"] == str(tmp_path)
        assert env_dict["CUB_TASK_ID"] == "cub-123"
        assert env_dict["CUB_TASK_TITLE"] == "Fix bug"
        assert env_dict["CUB_EXIT_CODE"] == "0"
        assert env_dict["CUB_HARNESS"] == "claude"
        assert env_dict["CUB_SESSION_ID"] == "session-456"

    def test_budget_context(self, tmp_path):
        """Test context with budget fields for on-budget-warning hook."""
        context = HookContext(
            hook_name="on-budget-warning",
            project_dir=tmp_path,
            budget_percentage=85.5,
            budget_used=855000,
            budget_limit=1000000,
        )
        env_dict = context.to_env_dict()

        assert env_dict["CUB_HOOK_NAME"] == "on-budget-warning"
        assert env_dict["CUB_BUDGET_PERCENTAGE"] == "85.5"
        assert env_dict["CUB_BUDGET_USED"] == "855000"
        assert env_dict["CUB_BUDGET_LIMIT"] == "1000000"

    def test_init_context(self, tmp_path):
        """Test context with init type for post-init hook."""
        context = HookContext(
            hook_name="post-init",
            project_dir=tmp_path,
            init_type="global",
        )
        env_dict = context.to_env_dict()

        assert env_dict["CUB_HOOK_NAME"] == "post-init"
        assert env_dict["CUB_INIT_TYPE"] == "global"

    def test_optional_fields_not_in_env_when_none(self, tmp_path):
        """Test that optional fields are not added when None."""
        context = HookContext(
            hook_name="pre-task",
            project_dir=tmp_path,
        )
        env_dict = context.to_env_dict()

        # Budget fields should not be present
        assert "CUB_BUDGET_PERCENTAGE" not in env_dict
        assert "CUB_BUDGET_USED" not in env_dict
        assert "CUB_BUDGET_LIMIT" not in env_dict
        assert "CUB_INIT_TYPE" not in env_dict


# ==============================================================================
# Hook Discovery Tests
# ==============================================================================


class TestFindHookScripts:
    """Test hook script discovery."""

    def test_find_no_hooks(self, temp_project):
        """Test finding hooks when none exist."""
        scripts = find_hook_scripts("pre-task", temp_project["project_dir"])
        assert scripts == []

    def test_find_global_hooks_only(self, temp_project):
        """Test finding only global hooks."""
        create_hook_script(
            temp_project["global_hooks"], "pre-task", "01-first.sh", "echo 'global 1'"
        )
        create_hook_script(
            temp_project["global_hooks"], "pre-task", "02-second.sh", "echo 'global 2'"
        )

        scripts = find_hook_scripts("pre-task", temp_project["project_dir"])
        assert len(scripts) == 2
        assert scripts[0].name == "01-first.sh"
        assert scripts[1].name == "02-second.sh"

    def test_find_project_hooks_only(self, temp_project):
        """Test finding only project hooks."""
        create_hook_script(
            temp_project["project_hooks"], "pre-task", "01-project.sh", "echo 'project'"
        )

        scripts = find_hook_scripts("pre-task", temp_project["project_dir"])
        assert len(scripts) == 1
        assert scripts[0].name == "01-project.sh"

    def test_find_both_global_and_project(self, temp_project):
        """Test finding both global and project hooks."""
        create_hook_script(
            temp_project["global_hooks"], "pre-task", "01-global.sh", "echo 'global'"
        )
        create_hook_script(
            temp_project["project_hooks"], "pre-task", "02-project.sh", "echo 'project'"
        )

        scripts = find_hook_scripts("pre-task", temp_project["project_dir"])
        assert len(scripts) == 2
        assert scripts[0].name == "01-global.sh"
        assert scripts[1].name == "02-project.sh"

    def test_ignore_non_executable(self, temp_project):
        """Test that non-executable files are ignored."""
        hook_dir = temp_project["global_hooks"] / "pre-task.d"
        hook_dir.mkdir(exist_ok=True)

        # Create executable script
        executable = hook_dir / "01-executable.sh"
        executable.write_text("#!/bin/bash\necho 'executable'")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

        # Create non-executable file
        non_executable = hook_dir / "02-not-executable.sh"
        non_executable.write_text("#!/bin/bash\necho 'not executable'")

        scripts = find_hook_scripts("pre-task", temp_project["project_dir"])
        assert len(scripts) == 1
        assert scripts[0].name == "01-executable.sh"

    def test_sorted_order(self, temp_project):
        """Test that scripts are returned in sorted order."""
        create_hook_script(temp_project["global_hooks"], "pre-task", "99-last.sh", "echo 'last'")
        create_hook_script(temp_project["global_hooks"], "pre-task", "01-first.sh", "echo 'first'")
        create_hook_script(
            temp_project["global_hooks"], "pre-task", "50-middle.sh", "echo 'middle'"
        )

        scripts = find_hook_scripts("pre-task", temp_project["project_dir"])
        assert len(scripts) == 3
        assert scripts[0].name == "01-first.sh"
        assert scripts[1].name == "50-middle.sh"
        assert scripts[2].name == "99-last.sh"

    def test_empty_hook_name_raises(self, temp_project):
        """Test that empty hook name raises ValueError."""
        with pytest.raises(ValueError, match="hook_name is required"):
            find_hook_scripts("", temp_project["project_dir"])


# ==============================================================================
# Hook Execution Tests
# ==============================================================================


class TestRunHooks:
    """Test hook execution."""

    def test_run_no_hooks(self, temp_project):
        """Test running when no hooks exist."""
        result = run_hooks("pre-task", project_dir=temp_project["project_dir"])
        assert result is True

    def test_run_successful_hook(self, temp_project, capsys):
        """Test running a successful hook."""
        create_hook_script(
            temp_project["project_hooks"], "pre-task", "01-test.sh", "echo 'Hook executed'"
        )

        result = run_hooks("pre-task", project_dir=temp_project["project_dir"])
        assert result is True

        captured = capsys.readouterr()
        assert "Hook executed" in captured.out

    def test_run_multiple_hooks_in_order(self, temp_project, capsys):
        """Test that multiple hooks run in sorted order."""
        create_hook_script(temp_project["project_hooks"], "pre-task", "01-first.sh", "echo 'First'")
        create_hook_script(
            temp_project["project_hooks"], "pre-task", "02-second.sh", "echo 'Second'"
        )

        result = run_hooks("pre-task", project_dir=temp_project["project_dir"])
        assert result is True

        captured = capsys.readouterr()
        # Check order by looking at string positions
        first_pos = captured.out.find("First")
        second_pos = captured.out.find("Second")
        assert first_pos >= 0 and second_pos >= 0
        assert first_pos < second_pos

    def test_context_passed_via_env(self, temp_project):
        """Test that context is passed via environment variables."""
        # Create script that writes env vars to a file
        output_file = temp_project["project_dir"] / "hook_output.txt"
        create_hook_script(
            temp_project["project_hooks"],
            "pre-task",
            "01-test.sh",
            f'echo "$CUB_TASK_ID|$CUB_TASK_TITLE|$CUB_HARNESS" > {output_file}',
        )

        context = HookContext(
            hook_name="pre-task",
            project_dir=temp_project["project_dir"],
            task_id="cub-123",
            task_title="Test task",
            harness="claude",
        )

        result = run_hooks("pre-task", context=context, project_dir=temp_project["project_dir"])
        assert result is True

        # Check that env vars were passed correctly
        output = output_file.read_text().strip()
        assert output == "cub-123|Test task|claude"

    def test_hook_failure_without_fail_fast(self, temp_project, capsys):
        """Test that hook failure doesn't stop execution when fail_fast=false."""
        # Create config with fail_fast=false (default)
        config = {"hooks": {"enabled": True, "fail_fast": False}}
        config_file = temp_project["project_dir"] / ".cub.json"
        import json

        config_file.write_text(json.dumps(config))
        clear_cache()

        create_hook_script(temp_project["project_hooks"], "pre-task", "01-fail.sh", "exit 1")

        result = run_hooks("pre-task", project_dir=temp_project["project_dir"])
        assert result is True  # Still returns True because fail_fast=false

        captured = capsys.readouterr()
        assert "failed with exit code 1" in captured.out

    def test_hook_failure_with_fail_fast(self, temp_project, capsys):
        """Test that hook failure stops execution when fail_fast=true."""
        # Create config with fail_fast=true
        config = {"hooks": {"enabled": True, "fail_fast": True}}
        config_file = temp_project["project_dir"] / ".cub.json"
        import json

        config_file.write_text(json.dumps(config))
        clear_cache()

        create_hook_script(temp_project["project_hooks"], "pre-task", "01-fail.sh", "exit 1")

        result = run_hooks("pre-task", project_dir=temp_project["project_dir"])
        assert result is False

        captured = capsys.readouterr()
        assert "failed with exit code 1" in captured.out

    def test_hooks_disabled(self, temp_project):
        """Test that hooks don't run when disabled in config."""
        # Create config with hooks disabled
        config = {"hooks": {"enabled": False}}
        config_file = temp_project["project_dir"] / ".cub.json"
        import json

        config_file.write_text(json.dumps(config))
        clear_cache()

        # Create a hook that would fail if executed
        create_hook_script(temp_project["project_hooks"], "pre-task", "01-fail.sh", "exit 1")

        result = run_hooks("pre-task", project_dir=temp_project["project_dir"])
        assert result is True  # Hooks disabled, so returns success

    def test_empty_hook_name_raises(self, temp_project):
        """Test that empty hook name raises ValueError."""
        with pytest.raises(ValueError, match="hook_name is required"):
            run_hooks("", project_dir=temp_project["project_dir"])

    def test_hook_with_stderr(self, temp_project, capsys):
        """Test that hook stderr is captured and logged."""
        create_hook_script(
            temp_project["project_hooks"],
            "pre-task",
            "01-test.sh",
            "echo 'Error message' >&2\nexit 1",
        )

        # Use default fail_fast=false
        result = run_hooks("pre-task", project_dir=temp_project["project_dir"])
        assert result is True

        captured = capsys.readouterr()
        assert "failed with exit code 1" in captured.out
        assert "Error message" in captured.out

    def test_multiple_failures_with_fail_fast_false(self, temp_project, capsys):
        """Test that all hooks run even if multiple fail (fail_fast=false)."""
        create_hook_script(temp_project["project_hooks"], "pre-task", "01-fail1.sh", "exit 1")
        create_hook_script(
            temp_project["project_hooks"], "pre-task", "02-success.sh", "echo 'Success'"
        )
        create_hook_script(temp_project["project_hooks"], "pre-task", "03-fail2.sh", "exit 2")

        result = run_hooks("pre-task", project_dir=temp_project["project_dir"])
        assert result is True  # fail_fast=false by default

        captured = capsys.readouterr()
        assert "01-fail1.sh failed with exit code 1" in captured.out
        assert "Success" in captured.out
        assert "03-fail2.sh failed with exit code 2" in captured.out

    def test_hook_timeout(self, temp_project, capsys):
        """Test that hooks timeout after 5 minutes."""
        # This test would take 5 minutes to run, so we skip it in normal test runs
        # It's here to document the behavior
        pytest.skip("Timeout test takes too long for normal test runs")

        create_hook_script(
            temp_project["project_hooks"],
            "pre-task",
            "01-hang.sh",
            "sleep 400",  # 400 seconds, more than 300s timeout
        )

        result = run_hooks("pre-task", project_dir=temp_project["project_dir"])
        assert result is True  # fail_fast=false by default

        captured = capsys.readouterr()
        assert "timed out after 300 seconds" in captured.out


# ==============================================================================
# Async Hook Tests
# ==============================================================================


class TestRunHooksAsync:
    """Test asynchronous hook execution."""

    def setup_method(self):
        """Clear async processes before each test."""
        clear_async_hooks()

    def teardown_method(self):
        """Clean up async processes after each test."""
        clear_async_hooks()

    def test_async_no_hooks(self, temp_project):
        """Test async execution when no hooks exist."""
        # Should not raise, just return
        run_hooks_async("post-task", project_dir=temp_project["project_dir"])
        wait_async_hooks()  # Should complete immediately

    def test_async_runs_hook(self, temp_project):
        """Test that async hooks actually run."""
        # Create a hook that writes to a file
        output_file = temp_project["project_dir"] / "async_output.txt"
        create_hook_script(
            temp_project["project_hooks"],
            "post-task",
            "01-test.sh",
            f'echo "async hook ran" > {output_file}',
        )

        run_hooks_async("post-task", project_dir=temp_project["project_dir"])

        # File shouldn't exist yet (or might, depending on timing)
        # Wait for completion
        wait_async_hooks()

        # Now file should definitely exist
        assert output_file.exists()
        assert "async hook ran" in output_file.read_text()

    def test_async_passes_context(self, temp_project):
        """Test that context is passed to async hooks."""
        output_file = temp_project["project_dir"] / "async_context.txt"
        create_hook_script(
            temp_project["project_hooks"],
            "post-task",
            "01-test.sh",
            f'echo "$CUB_TASK_ID|$CUB_EXIT_CODE" > {output_file}',
        )

        context = HookContext(
            hook_name="post-task",
            project_dir=temp_project["project_dir"],
            task_id="async-task-123",
            exit_code=0,
        )

        run_hooks_async("post-task", context, temp_project["project_dir"])
        wait_async_hooks()

        output = output_file.read_text().strip()
        assert output == "async-task-123|0"

    def test_async_multiple_hooks(self, temp_project):
        """Test running multiple hooks asynchronously."""
        output_file1 = temp_project["project_dir"] / "async1.txt"
        output_file2 = temp_project["project_dir"] / "async2.txt"

        create_hook_script(
            temp_project["project_hooks"],
            "post-task",
            "01-first.sh",
            f'echo "first" > {output_file1}',
        )
        create_hook_script(
            temp_project["project_hooks"],
            "post-task",
            "02-second.sh",
            f'echo "second" > {output_file2}',
        )

        run_hooks_async("post-task", project_dir=temp_project["project_dir"])
        wait_async_hooks()

        assert output_file1.exists()
        assert output_file2.exists()
        assert "first" in output_file1.read_text()
        assert "second" in output_file2.read_text()

    def test_async_with_disabled_hooks(self, temp_project):
        """Test that async hooks don't run when disabled."""
        import json

        config = {"hooks": {"enabled": False}}
        config_file = temp_project["project_dir"] / ".cub.json"
        config_file.write_text(json.dumps(config))
        clear_cache()

        # Create a hook that would create a file
        output_file = temp_project["project_dir"] / "should_not_exist.txt"
        create_hook_script(
            temp_project["project_hooks"],
            "post-task",
            "01-test.sh",
            f'touch {output_file}',
        )

        run_hooks_async("post-task", project_dir=temp_project["project_dir"])
        wait_async_hooks()

        # File should NOT exist since hooks are disabled
        assert not output_file.exists()

    def test_async_empty_hook_name_raises(self, temp_project):
        """Test that empty hook name raises ValueError."""
        with pytest.raises(ValueError, match="hook_name is required"):
            run_hooks_async("", project_dir=temp_project["project_dir"])


class TestWaitAsyncHooks:
    """Test waiting for async hooks."""

    def setup_method(self):
        """Clear async processes before each test."""
        clear_async_hooks()

    def teardown_method(self):
        """Clean up async processes after each test."""
        clear_async_hooks()

    def test_wait_with_no_processes(self):
        """Test waiting when no async hooks have been started."""
        # Should not raise
        wait_async_hooks()

    def test_wait_collects_output(self, temp_project, capsys):
        """Test that wait collects output from hooks."""
        create_hook_script(
            temp_project["project_hooks"],
            "post-task",
            "01-test.sh",
            'echo "Async hook output"',
        )

        run_hooks_async("post-task", project_dir=temp_project["project_dir"])
        wait_async_hooks()

        captured = capsys.readouterr()
        assert "Async hook output" in captured.out

    def test_wait_handles_failure(self, temp_project, capsys):
        """Test that wait handles failed hooks gracefully."""
        create_hook_script(
            temp_project["project_hooks"],
            "on-error",
            "01-fail.sh",
            "exit 1",
        )

        run_hooks_async("on-error", project_dir=temp_project["project_dir"])
        wait_async_hooks()  # Should not raise

        captured = capsys.readouterr()
        assert "exited with code 1" in captured.out


class TestClearAsyncHooks:
    """Test clearing async hook process list."""

    def test_clear_resets_state(self, temp_project):
        """Test that clear removes all tracked processes."""
        # Create a hook that takes a moment
        create_hook_script(
            temp_project["project_hooks"],
            "post-task",
            "01-slow.sh",
            "sleep 0.1",
        )

        run_hooks_async("post-task", project_dir=temp_project["project_dir"])

        # Clear without waiting
        clear_async_hooks()

        # Wait should now do nothing (list was cleared)
        wait_async_hooks()  # Should return immediately
