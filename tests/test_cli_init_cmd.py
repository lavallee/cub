"""
Tests for CLI init_cmd module.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from cub.cli.init_cmd import (
    _ensure_prompt_md,
    _ensure_prompt_symlink,
    _file_hash,
    _init_global,
    _update_gitignore,
    detect_backend,
    detect_project_type,
    generate_instruction_files,
    init_project,
)


class TestGenerateInstructionFiles:
    """Tests for generate_instruction_files function."""

    def test_creates_claude_and_symlink(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md is created and AGENTS.md is a symlink to it."""
        generate_instruction_files(tmp_path, force=False)

        agents_file = tmp_path / "AGENTS.md"
        claude_file = tmp_path / "CLAUDE.md"
        constitution_file = tmp_path / ".cub" / "constitution.md"
        runloop_file = tmp_path / ".cub" / "runloop.md"

        assert claude_file.exists()
        assert agents_file.exists()
        assert agents_file.is_symlink()  # AGENTS.md should be a symlink
        assert constitution_file.exists()
        assert runloop_file.exists()
        assert len(claude_file.read_text()) > 0

        # Content accessible through symlink should match CLAUDE.md
        assert agents_file.read_text() == claude_file.read_text()

        # Check for managed section markers in CLAUDE.md
        claude_content = claude_file.read_text()
        assert "<!-- BEGIN CUB MANAGED SECTION" in claude_content
        assert "<!-- END CUB MANAGED SECTION" in claude_content

    def test_appends_to_claude_and_backs_up_agents(self, tmp_path: Path) -> None:
        """Test managed section appends to CLAUDE.md and AGENTS.md is backed up then symlinked."""
        # Create initial files with user content
        agents_file = tmp_path / "AGENTS.md"
        claude_file = tmp_path / "CLAUDE.md"

        agents_file.write_text("Original AGENTS content\n")
        claude_file.write_text("Original CLAUDE content\n")

        # Generate without force - should APPEND managed section to CLAUDE.md
        # and backup+convert AGENTS.md to symlink
        generate_instruction_files(tmp_path, force=False)

        # CLAUDE.md should have both original content AND managed section
        claude_content = claude_file.read_text()
        assert "Original CLAUDE content" in claude_content
        assert "<!-- BEGIN CUB MANAGED SECTION" in claude_content

        # AGENTS.md should now be a symlink to CLAUDE.md
        assert agents_file.is_symlink()
        assert agents_file.read_text() == claude_content

        # Original AGENTS.md should be backed up
        backup_file = tmp_path / "AGENTS.md.backup"
        assert backup_file.exists()
        assert backup_file.read_text() == "Original AGENTS content\n"

    def test_overwrites_with_force_flag(self, tmp_path: Path) -> None:
        """Test that constitution and runloop are overwritten with force=True."""
        # Create initial constitution and runloop
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        constitution_file = cub_dir / "constitution.md"
        runloop_file = cub_dir / "runloop.md"

        constitution_file.write_text("Original constitution")
        runloop_file.write_text("Original runloop")

        # Generate with force
        generate_instruction_files(tmp_path, force=True)

        # Constitution and runloop should be overwritten
        assert constitution_file.read_text() != "Original constitution"
        assert runloop_file.read_text() != "Original runloop"
        assert len(constitution_file.read_text()) > 100
        assert len(runloop_file.read_text()) > 100

    def test_handles_missing_config_gracefully(self, tmp_path: Path) -> None:
        """Test that generation works even without existing config."""
        # Should not raise exception
        generate_instruction_files(tmp_path, force=False)

        # Files should still be created
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / "CLAUDE.md").exists()

    def test_creates_valid_markdown_files(self, tmp_path: Path) -> None:
        """Test that generated CLAUDE.md contains valid markdown with managed sections."""
        generate_instruction_files(tmp_path, force=False)

        claude_content = (tmp_path / "CLAUDE.md").read_text()

        # Check for managed section markers in CLAUDE.md
        assert "<!-- BEGIN CUB MANAGED SECTION" in claude_content
        assert "<!-- END CUB MANAGED SECTION" in claude_content

        # Check for key content (using actual content from managed sections)
        assert "**Context:**" in claude_content or "context" in claude_content.lower()
        assert "workflow" in claude_content.lower()

        # AGENTS.md should be a symlink with identical content
        agents_path = tmp_path / "AGENTS.md"
        assert agents_path.is_symlink()
        assert agents_path.read_text() == claude_content

    def test_includes_project_specific_info(self, tmp_path: Path) -> None:
        """Test that generated files include project-specific information."""
        project_dir = tmp_path / "my-test-project"
        project_dir.mkdir()

        generate_instruction_files(project_dir, force=False)

        claude_content = (project_dir / "CLAUDE.md").read_text()

        # Should include project name in CLAUDE.md
        assert "my-test-project" in claude_content

        # AGENTS.md is a symlink, so content is identical
        agents_path = project_dir / "AGENTS.md"
        assert agents_path.is_symlink()
        assert agents_path.read_text() == claude_content

    def test_installs_hooks_when_flag_set(self, tmp_path: Path) -> None:
        """Test that hooks are installed when install_hooks_flag=True."""
        # Mock install_hooks to avoid actual installation
        with patch("cub.cli.init_cmd.install_hooks") as mock_install:
            from cub.core.hooks.installer import HookInstallResult

            mock_install.return_value = HookInstallResult(
                success=True,
                hooks_installed=["PostToolUse", "SessionStart"],
                message="Installed 2 hooks",
                settings_file=str(tmp_path / ".claude" / "settings.json"),
            )

            generate_instruction_files(tmp_path, force=False, install_hooks_flag=True)

            # Verify install_hooks was called
            mock_install.assert_called_once_with(tmp_path, force=False)

    def test_skips_hooks_when_flag_not_set(self, tmp_path: Path) -> None:
        """Test that hooks are not installed when install_hooks_flag=False."""
        with patch("cub.cli.init_cmd.install_hooks") as mock_install:
            generate_instruction_files(tmp_path, force=False, install_hooks_flag=False)

            # Verify install_hooks was not called
            mock_install.assert_not_called()

    def test_handles_hook_installation_failure(self, tmp_path: Path) -> None:
        """Test that init continues when hook installation fails."""
        with patch("cub.cli.init_cmd.install_hooks") as mock_install:
            from cub.core.hooks.installer import HookInstallResult, HookIssue

            mock_install.return_value = HookInstallResult(
                success=False,
                message="Hook script not found",
                issues=[
                    HookIssue(
                        severity="error",
                        message="Hook script not found",
                        file_path=str(tmp_path / ".cub" / "scripts" / "hooks" / "cub-hook.sh"),
                    )
                ],
            )

            # Should not raise exception
            generate_instruction_files(tmp_path, force=False, install_hooks_flag=True)

            # Main files should still be created (CLAUDE.md and AGENTS.md symlink)
            assert (tmp_path / "CLAUDE.md").exists()
            assert (tmp_path / "AGENTS.md").exists()
            assert (tmp_path / "AGENTS.md").is_symlink()

    def test_reports_hook_installation_warnings(self, tmp_path: Path) -> None:
        """Test that hook installation warnings are displayed."""
        with patch("cub.cli.init_cmd.install_hooks") as mock_install:
            from cub.core.hooks.installer import HookInstallResult, HookIssue

            mock_install.return_value = HookInstallResult(
                success=True,
                hooks_installed=["PostToolUse"],
                issues=[
                    HookIssue(
                        severity="warning",
                        message="Hook script not executable",
                        file_path=str(tmp_path / ".cub" / "scripts" / "hooks" / "cub-hook.sh"),
                    )
                ],
                message="Installed 1 hook with warnings",
            )

            # Should not raise exception
            generate_instruction_files(tmp_path, force=False, install_hooks_flag=True)

            # Main files should still be created (CLAUDE.md and AGENTS.md symlink)
            assert (tmp_path / "CLAUDE.md").exists()
            assert (tmp_path / "AGENTS.md").exists()
            assert (tmp_path / "AGENTS.md").is_symlink()


class TestDetectProjectType:
    """Tests for detect_project_type function."""

    def test_detects_nextjs(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"next": "^14.0.0", "react": "^18.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_project_type(tmp_path) == "nextjs"

    def test_detects_react(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"react": "^18.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_project_type(tmp_path) == "react"

    def test_detects_node(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"express": "^4.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_project_type(tmp_path) == "node"

    def test_detects_python_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
        assert detect_project_type(tmp_path) == "python"

    def test_detects_python_requirements(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("flask==2.0\n")
        assert detect_project_type(tmp_path) == "python"

    def test_detects_go(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("module example.com/myapp\n")
        assert detect_project_type(tmp_path) == "go"

    def test_detects_rust(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "myapp"\n')
        assert detect_project_type(tmp_path) == "rust"

    def test_falls_back_to_generic(self, tmp_path: Path) -> None:
        assert detect_project_type(tmp_path) == "generic"

    def test_handles_invalid_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("not valid json")
        assert detect_project_type(tmp_path) == "node"


class TestDetectBackend:
    """Tests for detect_backend function."""

    def test_explicit_overrides_all(self) -> None:
        assert detect_backend(explicit="jsonl") == "jsonl"

    def test_env_var_overrides_auto(self) -> None:
        with patch.dict(os.environ, {"CUB_BACKEND": "jsonl"}):
            assert detect_backend() == "jsonl"

    def test_auto_detects_beads(self) -> None:
        with patch("cub.cli.init_cmd.shutil.which", return_value="/usr/bin/bd"):
            with patch.dict(os.environ, {}, clear=True):
                # Ensure CUB_BACKEND is not set
                os.environ.pop("CUB_BACKEND", None)
                assert detect_backend() == "beads"

    def test_falls_back_to_jsonl(self) -> None:
        with patch("cub.cli.init_cmd.shutil.which", return_value=None):
            with patch.dict(os.environ, {}, clear=True):
                os.environ.pop("CUB_BACKEND", None)
                assert detect_backend() == "jsonl"


class TestInitGlobal:
    """Tests for _init_global function."""

    def test_creates_global_config(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path)}):
            _init_global(force=False)

        config_file = tmp_path / "cub" / "config.json"
        assert config_file.exists()

        config = json.loads(config_file.read_text())
        assert config["harness"] == "auto"
        assert config["budget"]["max_tokens_per_task"] == 500000
        assert config["state"]["require_clean"] is True

    def test_creates_hooks_directory(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path)}):
            _init_global(force=False)

        hooks_dir = tmp_path / "cub" / "hooks"
        assert hooks_dir.is_dir()

    def test_does_not_overwrite_without_force(self, tmp_path: Path) -> None:
        global_dir = tmp_path / "cub"
        global_dir.mkdir(parents=True)
        config_file = global_dir / "config.json"
        config_file.write_text('{"custom": true}\n')

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path)}):
            _init_global(force=False)

        # Should not be overwritten
        config = json.loads(config_file.read_text())
        assert config.get("custom") is True

    def test_overwrites_with_force(self, tmp_path: Path) -> None:
        global_dir = tmp_path / "cub"
        global_dir.mkdir(parents=True)
        config_file = global_dir / "config.json"
        config_file.write_text('{"custom": true}\n')

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path)}):
            _init_global(force=True)

        config = json.loads(config_file.read_text())
        assert "custom" not in config
        assert config["harness"] == "auto"


class TestUpdateGitignore:
    """Tests for _update_gitignore function."""

    def test_creates_gitignore_if_missing(self, tmp_path: Path) -> None:
        _update_gitignore(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert "# cub" in content
        assert ".cub/ledger/forensics/" in content

    def test_appends_missing_patterns(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n")

        _update_gitignore(tmp_path)

        content = gitignore.read_text()
        assert "node_modules/" in content
        assert "# cub" in content

    def test_skips_existing_patterns(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("# cub\n.cub/ledger/forensics/\n.cub/dashboard.db\n.cub/map.md\n")

        _update_gitignore(tmp_path)

        content = gitignore.read_text()
        # Should not duplicate
        assert content.count("# cub") == 1


class TestInitProject:
    """Tests for init_project orchestrator."""

    def test_full_init_creates_expected_files(self, tmp_path: Path) -> None:
        """Test that init_project creates the expected directory structure."""
        with (
            patch("cub.cli.init_cmd.install_hooks") as mock_hooks,
            patch("cub.cli.statusline.install_statusline", return_value=True),
        ):
            from cub.core.hooks.installer import HookInstallResult

            mock_hooks.return_value = HookInstallResult(
                success=True,
                hooks_installed=["PostToolUse"],
                message="ok",
            )

            init_project(
                tmp_path,
                force=False,
                backend="jsonl",
                install_hooks_flag=True,
            )

        # Core files should exist
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / "AGENTS.md").is_symlink()  # AGENTS.md should be symlink
        assert (tmp_path / ".cub" / "constitution.md").exists()
        assert (tmp_path / ".cub" / "runloop.md").exists()
        assert (tmp_path / "specs").is_dir()

    def test_init_project_detects_python(self, tmp_path: Path) -> None:
        """Test that Python project type is detected."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        with (
            patch("cub.cli.init_cmd.install_hooks") as mock_hooks,
            patch("cub.cli.statusline.install_statusline", return_value=False),
        ):
            from cub.core.hooks.installer import HookInstallResult

            mock_hooks.return_value = HookInstallResult(success=True, message="ok")

            # Should not raise
            init_project(tmp_path, backend="jsonl", install_hooks_flag=False)

    @pytest.mark.parametrize("backend_name", ["beads", "jsonl"])
    def test_init_project_backends(self, tmp_path: Path, backend_name: str) -> None:
        """Test that both backends can be initialized."""
        with (
            patch("cub.cli.init_cmd.install_hooks") as mock_hooks,
            patch("cub.cli.statusline.install_statusline", return_value=False),
            patch("cub.cli.init_cmd.shutil.which", return_value="/usr/bin/bd"),
            patch("cub.cli.init_cmd.subprocess.run"),
        ):
            from cub.core.hooks.installer import HookInstallResult

            mock_hooks.return_value = HookInstallResult(success=True, message="ok")

            init_project(
                tmp_path,
                backend=backend_name,
                install_hooks_flag=False,
            )

    def test_init_project_nonexistent_dir_exits(self, tmp_path: Path) -> None:
        """Test that init_project exits for nonexistent directory."""
        from click.exceptions import Exit

        with pytest.raises(Exit):
            init_project(tmp_path / "does-not-exist")

    def test_init_project_writes_explicit_backend_to_config(self, tmp_path: Path) -> None:
        """Test that cub init writes explicit backend.mode to config."""
        with (
            patch("cub.cli.init_cmd.install_hooks") as mock_hooks,
            patch("cub.cli.statusline.install_statusline", return_value=False),
        ):
            from cub.core.hooks.installer import HookInstallResult

            mock_hooks.return_value = HookInstallResult(success=True, message="ok")

            init_project(
                tmp_path,
                backend="jsonl",
                install_hooks_flag=False,
            )

        # Verify config has backend.mode set
        config_file = tmp_path / ".cub" / "config.json"
        assert config_file.exists()

        config = json.loads(config_file.read_text())
        assert "backend" in config
        assert config["backend"]["mode"] == "jsonl"

    def test_init_project_backend_config_used_by_detect_backend(
        self, tmp_path: Path
    ) -> None:
        """Test that backend loading respects explicit config setting over auto-detection."""
        from cub.core.config.loader import clear_cache
        from cub.core.tasks.backend import detect_backend as detect_backend_runtime

        with (
            patch("cub.cli.init_cmd.install_hooks") as mock_hooks,
            patch("cub.cli.statusline.install_statusline", return_value=False),
        ):
            from cub.core.hooks.installer import HookInstallResult

            mock_hooks.return_value = HookInstallResult(success=True, message="ok")

            init_project(
                tmp_path,
                backend="jsonl",
                install_hooks_flag=False,
            )

        # Clear config cache so it re-reads
        clear_cache()

        # Detect backend should return the configured value
        detected = detect_backend_runtime(project_dir=tmp_path)
        assert detected == "jsonl"

    def test_init_project_jsonl_backend_followed_by_task_list(
        self, tmp_path: Path
    ) -> None:
        """Test that cub init followed by task list uses the configured backend."""
        from cub.core.config.loader import clear_cache
        from cub.core.tasks.backend import get_backend

        with (
            patch("cub.cli.init_cmd.install_hooks") as mock_hooks,
            patch("cub.cli.statusline.install_statusline", return_value=False),
        ):
            from cub.core.hooks.installer import HookInstallResult

            mock_hooks.return_value = HookInstallResult(success=True, message="ok")

            init_project(
                tmp_path,
                backend="jsonl",
                install_hooks_flag=False,
            )

        # Clear config cache
        clear_cache()

        # Get backend and verify it's the JSONL backend
        backend = get_backend(project_dir=tmp_path)
        assert backend.backend_name == "jsonl"

        # Verify we can list tasks (should return empty list for new project)
        tasks = backend.list_tasks()
        assert tasks == []


class TestEnsurePromptMd:
    """Tests for _ensure_prompt_md function and prompt.md preservation."""

    def test_creates_prompt_md_if_missing(self, tmp_path: Path) -> None:
        """Test that prompt.md is created from template if it doesn't exist."""
        result = _ensure_prompt_md(tmp_path)

        prompt_file = tmp_path / ".cub" / "prompt.md"
        assert prompt_file.exists()
        assert result == "created"
        # Should contain template content
        assert len(prompt_file.read_text()) > 100

    def test_creates_prompt_symlink(self, tmp_path: Path) -> None:
        """Test that PROMPT.md symlink is created pointing to .cub/prompt.md."""
        _ensure_prompt_md(tmp_path)

        symlink_path = tmp_path / "PROMPT.md"
        prompt_file = tmp_path / ".cub" / "prompt.md"

        # Symlink should exist
        assert symlink_path.exists() or symlink_path.is_symlink()

        # If it's a symlink, verify it points to the right place
        if symlink_path.is_symlink():
            assert symlink_path.read_text() == prompt_file.read_text()

    def test_preserves_user_modified_prompt_md(self, tmp_path: Path) -> None:
        """Test that user modifications to prompt.md are preserved without --force."""
        # Create .cub directory and user-modified prompt.md
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        prompt_file = cub_dir / "prompt.md"
        user_content = "# My Custom Prompt\n\nUser customizations here.\n"
        prompt_file.write_text(user_content)

        # Run without force
        result = _ensure_prompt_md(tmp_path, force=False)

        # Should be skipped (modified)
        assert result == "skipped_modified"
        # Content should be unchanged
        assert prompt_file.read_text() == user_content

    def test_overwrites_with_force_flag(self, tmp_path: Path) -> None:
        """Test that prompt.md is overwritten when --force is used."""
        # Create .cub directory and user-modified prompt.md
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        prompt_file = cub_dir / "prompt.md"
        user_content = "# My Custom Prompt\n\nUser customizations here.\n"
        prompt_file.write_text(user_content)

        # Run with force
        result = _ensure_prompt_md(tmp_path, force=True)

        # Should be overwritten
        assert result == "overwritten"
        # Content should be template content (different from user content)
        new_content = prompt_file.read_text()
        assert new_content != user_content
        assert len(new_content) > 100  # Template is much longer

    def test_skips_unchanged_prompt_md(self, tmp_path: Path) -> None:
        """Test that prompt.md is skipped if it matches the template."""
        # First create the prompt.md from template
        result1 = _ensure_prompt_md(tmp_path, force=False)
        assert result1 == "created"

        # Run again - should skip since it matches template
        result2 = _ensure_prompt_md(tmp_path, force=False)
        assert result2 == "skipped_unchanged"

    def test_file_hash_function(self, tmp_path: Path) -> None:
        """Test that _file_hash produces consistent hashes."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        hash1 = _file_hash(test_file)
        hash2 = _file_hash(test_file)

        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hash length

        # Different content should produce different hash
        test_file.write_text("different content")
        hash3 = _file_hash(test_file)
        assert hash3 != hash1


class TestEnsurePromptSymlink:
    """Tests for _ensure_prompt_symlink function."""

    def test_creates_symlink_when_missing(self, tmp_path: Path) -> None:
        """Test that symlink is created when it doesn't exist."""
        # Create .cub/prompt.md first
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        (cub_dir / "prompt.md").write_text("content")

        _ensure_prompt_symlink(tmp_path)

        symlink_path = tmp_path / "PROMPT.md"
        # Should be a symlink (or not exist on systems without symlink support)
        if symlink_path.exists():
            assert symlink_path.is_symlink() or symlink_path.is_file()

    def test_preserves_regular_file(self, tmp_path: Path) -> None:
        """Test that a regular PROMPT.md file is not converted to symlink."""
        # Create regular file at PROMPT.md
        prompt_file = tmp_path / "PROMPT.md"
        user_content = "User's custom PROMPT.md content"
        prompt_file.write_text(user_content)

        _ensure_prompt_symlink(tmp_path)

        # Should still be a regular file with original content
        assert prompt_file.exists()
        assert not prompt_file.is_symlink()
        assert prompt_file.read_text() == user_content


class TestGenerateInstructionFilesPromptMd:
    """Tests for prompt.md handling in generate_instruction_files."""

    def test_creates_prompt_md_on_init(self, tmp_path: Path) -> None:
        """Test that generate_instruction_files creates prompt.md."""
        generate_instruction_files(tmp_path, force=False)

        prompt_file = tmp_path / ".cub" / "prompt.md"
        assert prompt_file.exists()
        assert len(prompt_file.read_text()) > 100

    def test_preserves_prompt_md_on_reinit(self, tmp_path: Path) -> None:
        """Test that prompt.md is preserved on re-initialization."""
        # First init
        generate_instruction_files(tmp_path, force=False)

        # Modify prompt.md
        prompt_file = tmp_path / ".cub" / "prompt.md"
        user_content = "# My Custom Prompt\n\nUser customizations.\n"
        prompt_file.write_text(user_content)

        # Re-init without force
        generate_instruction_files(tmp_path, force=False)

        # User content should be preserved
        assert prompt_file.read_text() == user_content

    def test_force_overwrites_prompt_md_on_reinit(self, tmp_path: Path) -> None:
        """Test that force=True overwrites prompt.md on re-initialization."""
        # First init
        generate_instruction_files(tmp_path, force=False)

        # Modify prompt.md
        prompt_file = tmp_path / ".cub" / "prompt.md"
        user_content = "# My Custom Prompt\n\nUser customizations.\n"
        prompt_file.write_text(user_content)

        # Re-init with force
        generate_instruction_files(tmp_path, force=True)

        # User content should be overwritten
        new_content = prompt_file.read_text()
        assert new_content != user_content
        assert len(new_content) > 100


class TestInitProjectPromptMd:
    """Tests for prompt.md handling in init_project."""

    def test_init_project_creates_prompt_md(self, tmp_path: Path) -> None:
        """Test that init_project creates prompt.md."""
        with (
            patch("cub.cli.init_cmd.install_hooks") as mock_hooks,
            patch("cub.cli.statusline.install_statusline", return_value=False),
        ):
            from cub.core.hooks.installer import HookInstallResult

            mock_hooks.return_value = HookInstallResult(success=True, message="ok")

            init_project(
                tmp_path,
                backend="jsonl",
                install_hooks_flag=False,
            )

        prompt_file = tmp_path / ".cub" / "prompt.md"
        assert prompt_file.exists()
        assert len(prompt_file.read_text()) > 100

    def test_init_project_preserves_modified_prompt_md(self, tmp_path: Path) -> None:
        """Test that init_project preserves user-modified prompt.md."""
        # Create initial structure with modified prompt.md
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        prompt_file = cub_dir / "prompt.md"
        user_content = "# My Custom Prompt\n\nCustomizations.\n"
        prompt_file.write_text(user_content)

        with (
            patch("cub.cli.init_cmd.install_hooks") as mock_hooks,
            patch("cub.cli.statusline.install_statusline", return_value=False),
        ):
            from cub.core.hooks.installer import HookInstallResult

            mock_hooks.return_value = HookInstallResult(success=True, message="ok")

            init_project(
                tmp_path,
                backend="jsonl",
                install_hooks_flag=False,
                force=False,
            )

        # User content should be preserved
        assert prompt_file.read_text() == user_content
