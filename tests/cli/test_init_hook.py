"""
Tests for pre-push hook installation in cub init.

Verifies that `cub init` correctly installs the pre-push hook
for counter verification.
"""

from pathlib import Path

import pytest


class TestPrePushHookInstallation:
    """Test suite for pre-push hook installation."""

    def test_init_installs_pre_push_hook(self, tmp_path: Path, git_repo: Path) -> None:
        """cub init should install pre-push hook."""
        from cub.cli.init_cmd import _install_pre_push_hook

        # Install hook
        result = _install_pre_push_hook(git_repo, force=False)

        # Check hook was installed
        assert result is True

        hook_path = git_repo / ".git" / "hooks" / "pre-push"
        assert hook_path.exists()
        assert hook_path.stat().st_mode & 0o111  # Executable

        # Check hook content
        content = hook_path.read_text()
        assert "verify_counters_before_push" in content
        assert "pre-push hook" in content.lower()

    def test_skips_if_hook_exists(self, git_repo: Path) -> None:
        """Should skip if pre-push hook already exists (not force)."""
        from cub.cli.init_cmd import _install_pre_push_hook

        # Create existing hook
        hook_path = git_repo / ".git" / "hooks" / "pre-push"
        hook_path.write_text("#!/bin/bash\necho 'existing hook'\n")
        hook_path.chmod(0o755)

        # Try to install
        result = _install_pre_push_hook(git_repo, force=False)

        # Should skip
        assert result is False

        # Original hook should be preserved
        content = hook_path.read_text()
        assert "existing hook" in content
        assert "verify_counters_before_push" not in content

    def test_overwrites_with_force(self, git_repo: Path) -> None:
        """Should overwrite existing hook when force=True."""
        from cub.cli.init_cmd import _install_pre_push_hook

        # Create existing hook
        hook_path = git_repo / ".git" / "hooks" / "pre-push"
        hook_path.write_text("#!/bin/bash\necho 'existing hook'\n")
        hook_path.chmod(0o755)

        # Install with force
        result = _install_pre_push_hook(git_repo, force=True)

        # Should install
        assert result is True

        # Should have new hook
        content = hook_path.read_text()
        assert "verify_counters_before_push" in content
        assert "existing hook" not in content

    def test_skips_reinstall_of_cub_hook(self, git_repo: Path) -> None:
        """Should skip if cub hook is already installed."""
        from cub.cli.init_cmd import _install_pre_push_hook

        # Install hook first time
        _install_pre_push_hook(git_repo, force=False)

        # Try to install again
        result = _install_pre_push_hook(git_repo, force=False)

        # Should skip
        assert result is False

    def test_handles_no_git_directory(self, tmp_path: Path) -> None:
        """Should handle missing .git directory gracefully."""
        from cub.cli.init_cmd import _install_pre_push_hook

        # No .git directory
        result = _install_pre_push_hook(tmp_path, force=False)

        # Should return False (not installed)
        assert result is False

    def test_hook_is_executable(self, git_repo: Path) -> None:
        """Installed hook should be executable."""
        from cub.cli.init_cmd import _install_pre_push_hook

        _install_pre_push_hook(git_repo, force=False)

        hook_path = git_repo / ".git" / "hooks" / "pre-push"
        mode = hook_path.stat().st_mode

        # Check executable bits are set
        assert mode & 0o100  # Owner execute
        assert mode & 0o010  # Group execute
        assert mode & 0o001  # Other execute


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository for testing."""
    import subprocess

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    # Configure git user for testing
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    readme = tmp_path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    return tmp_path
