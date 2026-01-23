"""
Tests for the cleanup service.

Tests the working directory cleanup functionality that runs after cub run completes.
"""

import subprocess

import pytest

from cub.core.cleanup.service import CleanupResult, CleanupService
from cub.core.config.models import CleanupConfig


class TestCleanupConfig:
    """Tests for CleanupConfig model."""

    def test_default_config(self):
        """Default config should have sensible values."""
        config = CleanupConfig()

        assert config.enabled is True
        assert config.commit_artifacts is True
        assert config.remove_temp_files is True
        assert "progress.txt" in config.artifact_patterns
        assert "*.bak" in config.temp_patterns
        assert ".git/**" in config.ignore_patterns

    def test_custom_patterns(self):
        """Custom patterns should be accepted."""
        config = CleanupConfig(
            artifact_patterns=["custom.log", "*.report"],
            temp_patterns=["*.cache"],
            ignore_patterns=[".secret/**"],
        )

        assert config.artifact_patterns == ["custom.log", "*.report"]
        assert config.temp_patterns == ["*.cache"]
        assert config.ignore_patterns == [".secret/**"]

    def test_disabled_config(self):
        """Cleanup can be disabled."""
        config = CleanupConfig(enabled=False)
        assert config.enabled is False


class TestCleanupResult:
    """Tests for CleanupResult dataclass."""

    def test_empty_result(self):
        """Empty result should report no actions."""
        result = CleanupResult()

        assert result.committed_files == []
        assert result.removed_files == []
        assert result.is_clean is False
        assert result.summary() == "No cleanup actions needed"

    def test_summary_with_commits(self):
        """Summary should report committed files."""
        result = CleanupResult(
            committed_files=["progress.txt", "AGENT.md", "fix_plan.md"],
            is_clean=True,
        )

        summary = result.summary()
        assert "Committed 3 file(s)" in summary
        assert "Working directory is clean" in summary

    def test_summary_with_removals(self):
        """Summary should report removed files."""
        result = CleanupResult(
            removed_files=["foo.bak", "bar.tmp", "test.pyc"],
            is_clean=True,
        )

        summary = result.summary()
        assert "Removed 3 temporary file(s)" in summary

    def test_summary_with_errors(self):
        """Summary should report errors."""
        result = CleanupResult(
            commit_errors=["failed.txt"],
            removal_errors=["locked.bak"],
            remaining_files=["untracked.txt"],
        )

        summary = result.summary()
        assert "Failed to commit 1 file(s)" in summary
        assert "Failed to remove 1 file(s)" in summary
        assert "1 file(s) remain uncommitted" in summary


class TestCleanupService:
    """Tests for CleanupService."""

    @pytest.fixture
    def git_project(self, tmp_path):
        """Create a git repository for testing."""
        project = tmp_path / "project"
        project.mkdir()

        # Initialize git repo
        subprocess.run(
            ["git", "init"],
            cwd=project,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=project,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=project,
            capture_output=True,
            check=True,
        )

        # Create initial commit
        (project / "README.md").write_text("# Test Project")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=project,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=project,
            capture_output=True,
            check=True,
        )

        return project

    def test_cleanup_disabled(self, git_project):
        """Cleanup should do nothing when disabled."""
        config = CleanupConfig(enabled=False)
        service = CleanupService(config, git_project)

        # Create some files
        (git_project / "test.bak").write_text("backup")

        result = service.cleanup()

        # File should still exist
        assert (git_project / "test.bak").exists()
        assert result.committed_files == []
        assert result.removed_files == []

    def test_remove_temp_files(self, git_project):
        """Should remove files matching temp patterns."""
        config = CleanupConfig(
            commit_artifacts=False,  # Don't try to commit
            temp_patterns=["*.bak", "*.tmp"],
        )
        service = CleanupService(config, git_project)

        # Create temp files
        (git_project / "test.bak").write_text("backup")
        (git_project / "cache.tmp").write_text("temp")
        (git_project / "keep.txt").write_text("keep this")

        result = service.cleanup()

        # Temp files should be removed
        assert not (git_project / "test.bak").exists()
        assert not (git_project / "cache.tmp").exists()
        # Other files should remain
        assert (git_project / "keep.txt").exists()

        assert "test.bak" in result.removed_files
        assert "cache.tmp" in result.removed_files

    def test_commit_artifact_files(self, git_project):
        """Should commit files matching artifact patterns."""
        config = CleanupConfig(
            remove_temp_files=False,  # Don't remove
            artifact_patterns=["progress.txt", "*.log"],
        )
        service = CleanupService(config, git_project)

        # Create artifact files
        (git_project / "progress.txt").write_text("Task 1: done")
        (git_project / "build.log").write_text("Build successful")

        result = service.cleanup()

        # Files should be committed
        assert "progress.txt" in result.committed_files or "build.log" in result.committed_files
        assert result.is_clean

        # Verify git status is clean
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_project,
            capture_output=True,
            text=True,
        )
        assert status.stdout.strip() == ""

    def test_ignore_patterns(self, git_project):
        """Should not touch ignored files."""
        config = CleanupConfig(
            artifact_patterns=["*"],  # Match everything
            temp_patterns=["*"],  # Match everything
            ignore_patterns=[".env*", "secrets/**"],
        )
        service = CleanupService(config, git_project)

        # Create files that should be ignored
        (git_project / ".env").write_text("SECRET=value")
        (git_project / ".env.local").write_text("LOCAL=value")
        secrets_dir = git_project / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "api.key").write_text("secret-key")

        service.cleanup()

        # Ignored files should remain
        assert (git_project / ".env").exists()
        assert (git_project / ".env.local").exists()
        assert (secrets_dir / "api.key").exists()

    def test_get_cleanup_preview(self, git_project):
        """Preview should categorize files correctly."""
        config = CleanupConfig(
            artifact_patterns=["progress.txt"],
            temp_patterns=["*.bak"],
            ignore_patterns=[".env"],
        )
        service = CleanupService(config, git_project)

        # Create various files
        (git_project / "progress.txt").write_text("progress")
        (git_project / "backup.bak").write_text("backup")
        (git_project / ".env").write_text("secret")
        (git_project / "random.xyz").write_text("unknown")

        preview = service.get_cleanup_preview()

        assert "progress.txt" in preview["to_commit"]
        assert "backup.bak" in preview["to_remove"]
        assert ".env" in preview["ignored"]
        assert "random.xyz" in preview["unmatched"]

    def test_pattern_matching_with_directories(self, git_project):
        """Should handle directory patterns correctly."""
        config = CleanupConfig(
            temp_patterns=["__pycache__/**", ".pytest_cache/**"],
        )
        service = CleanupService(config, git_project)

        # Create cache directories
        pycache = git_project / "__pycache__"
        pycache.mkdir()
        (pycache / "module.pyc").write_text("compiled")

        pytest_cache = git_project / ".pytest_cache"
        pytest_cache.mkdir()
        (pytest_cache / "v" / "cache").mkdir(parents=True)

        # Check that pattern matching works
        assert service._matches_pattern("__pycache__/module.pyc", config.temp_patterns)
        assert service._matches_pattern(".pytest_cache/v/cache", config.temp_patterns)

    def test_full_cleanup_workflow(self, git_project):
        """Test complete cleanup workflow."""
        config = CleanupConfig(
            artifact_patterns=["progress.txt", "AGENT.md"],
            temp_patterns=["*.bak", "*.tmp"],
            ignore_patterns=[".git/**"],
        )
        service = CleanupService(config, git_project)

        # Create a mix of files
        (git_project / "progress.txt").write_text("Task 1: Complete")
        (git_project / "AGENT.md").write_text("# Agent Instructions")
        (git_project / "backup.bak").write_text("old backup")
        (git_project / "temp.tmp").write_text("temp data")
        (git_project / "other.txt").write_text("unmatched file")

        result = service.cleanup()

        # Check results
        assert len(result.removed_files) >= 2  # backup.bak and temp.tmp
        assert not (git_project / "backup.bak").exists()
        assert not (git_project / "temp.tmp").exists()

        # Artifacts should be committed
        assert len(result.committed_files) >= 1

        # other.txt should remain uncommitted
        assert "other.txt" in result.remaining_files or not result.is_clean


class TestCleanupIntegration:
    """Integration tests for cleanup with CubConfig."""

    def test_cleanup_config_in_cub_config(self):
        """CleanupConfig should be included in CubConfig."""
        from cub.core.config.models import CubConfig

        config = CubConfig()
        assert hasattr(config, "cleanup")
        assert isinstance(config.cleanup, CleanupConfig)
        assert config.cleanup.enabled is True

    def test_cleanup_config_from_dict(self):
        """CleanupConfig should load from dict (JSON)."""
        from cub.core.config.models import CubConfig

        config_dict = {
            "cleanup": {
                "enabled": True,
                "commit_artifacts": True,
                "remove_temp_files": False,
                "artifact_patterns": ["custom.log"],
                "temp_patterns": [],
            }
        }

        config = CubConfig.model_validate(config_dict)
        assert config.cleanup.enabled is True
        assert config.cleanup.remove_temp_files is False
        assert config.cleanup.artifact_patterns == ["custom.log"]

    def test_cleanup_disabled_via_config(self):
        """Cleanup should respect disabled setting from config."""
        from cub.core.config.models import CubConfig

        config = CubConfig(cleanup=CleanupConfig(enabled=False))
        assert config.cleanup.enabled is False


class TestPatternMatching:
    """Tests for pattern matching edge cases."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a cleanup service with test config."""
        config = CleanupConfig(
            artifact_patterns=["progress.txt", "*.log", "reports/**"],
            temp_patterns=["*.bak", "__pycache__/**", ".mypy_cache/**"],
            ignore_patterns=[".git/**", ".env*"],
        )
        return CleanupService(config, tmp_path)

    def test_simple_filename_match(self, service):
        """Should match exact filenames."""
        assert service._matches_pattern("progress.txt", service.config.artifact_patterns)
        assert not service._matches_pattern("progress.txt.bak", service.config.artifact_patterns)

    def test_extension_wildcard_match(self, service):
        """Should match extension wildcards."""
        assert service._matches_pattern("build.log", service.config.artifact_patterns)
        assert service._matches_pattern("test.log", service.config.artifact_patterns)
        assert not service._matches_pattern("test.txt", service.config.artifact_patterns)

    def test_directory_wildcard_match(self, service):
        """Should match directory wildcards."""
        assert service._matches_pattern("__pycache__/foo.pyc", service.config.temp_patterns)
        assert service._matches_pattern(".mypy_cache/cache.json", service.config.temp_patterns)

    def test_basename_matching(self, service):
        """Should match basename for simple patterns."""
        # *.bak should match foo.bak even in subdirectories
        assert service._matches_pattern("subdir/foo.bak", service.config.temp_patterns)

    def test_ignore_pattern_match(self, service):
        """Should detect ignored files."""
        assert service._is_ignored(".git/config")
        assert service._is_ignored(".env")
        assert service._is_ignored(".env.local")
        assert not service._is_ignored("src/config.py")
