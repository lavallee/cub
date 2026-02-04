"""
Tests for agent.md managed section syncing.

Tests cover:
- Managed section parsing
- Section injection
- Conflict detection
- Pull from sync branch
- Push to sync branch
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cub.core.sync import SyncService


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)

    # Configure git user (required for commits)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    # Create initial commit
    (repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    return repo


class TestManagedSectionParsing:
    """Tests for parsing managed sections from agent.md."""

    def test_parse_single_section(self, git_repo: Path) -> None:
        """Parse a single managed section."""
        content = """
# Some header

<!-- BEGIN CUB MANAGED SECTION v1 -->
<!-- sha256:abc123 -->
Managed content here.
<!-- END CUB MANAGED SECTION -->

Regular content.
"""
        sync = SyncService(project_dir=git_repo)
        sections = sync._parse_managed_sections(content)

        assert len(sections) == 1
        assert "v1" in sections
        managed_content, _, _ = sections["v1"]
        assert "Managed content here." in managed_content

    def test_parse_multiple_sections(self, git_repo: Path) -> None:
        """Parse multiple managed sections with different versions."""
        content = """
<!-- BEGIN CUB MANAGED SECTION v1 -->
Section 1 content.
<!-- END CUB MANAGED SECTION -->

<!-- BEGIN CUB MANAGED SECTION v2 -->
Section 2 content.
<!-- END CUB MANAGED SECTION -->
"""
        sync = SyncService(project_dir=git_repo)
        sections = sync._parse_managed_sections(content)

        assert len(sections) == 2
        assert "v1" in sections
        assert "v2" in sections

    def test_parse_no_sections(self, git_repo: Path) -> None:
        """Parse content with no managed sections."""
        content = """
# Regular content
No managed sections here.
"""
        sync = SyncService(project_dir=git_repo)
        sections = sync._parse_managed_sections(content)

        assert len(sections) == 0

    def test_parse_section_positions(self, git_repo: Path) -> None:
        """Verify section positions are calculated correctly."""
        content = "abc\n<!-- BEGIN CUB MANAGED SECTION v1 -->\ntest\n<!-- END CUB MANAGED SECTION -->\ndef\n"  # noqa: E501
        sync = SyncService(project_dir=git_repo)
        sections = sync._parse_managed_sections(content)

        assert "v1" in sections
        _, start_pos, end_pos = sections["v1"]

        # Verify positions point to the right substring
        extracted = content[start_pos:end_pos]
        assert "BEGIN CUB MANAGED SECTION" in extracted
        assert "END CUB MANAGED SECTION" in extracted


class TestManagedSectionInjection:
    """Tests for injecting managed sections into content."""

    def test_inject_single_section(self, git_repo: Path) -> None:
        """Inject a managed section into content."""
        base_content = """
# Header

<!-- BEGIN CUB MANAGED SECTION v1 -->
Old content.
<!-- END CUB MANAGED SECTION -->

Footer.
"""
        sync = SyncService(project_dir=git_repo)
        new_sections = {"v1": ("New content.\n", 0, 0)}

        result = sync._inject_managed_sections(base_content, new_sections)

        assert "New content." in result
        assert "Old content." not in result
        assert "# Header" in result
        assert "Footer." in result

    def test_inject_preserves_non_managed(self, git_repo: Path) -> None:
        """Injecting sections preserves non-managed content."""
        base_content = """
Intro text.

<!-- BEGIN CUB MANAGED SECTION v1 -->
Old.
<!-- END CUB MANAGED SECTION -->

Outro text.
"""
        sync = SyncService(project_dir=git_repo)
        new_sections = {"v1": ("New.\n", 0, 0)}

        result = sync._inject_managed_sections(base_content, new_sections)

        assert "Intro text." in result
        assert "Outro text." in result
        assert "New." in result

    def test_inject_multiple_sections(self, git_repo: Path) -> None:
        """Inject multiple managed sections."""
        base_content = """
<!-- BEGIN CUB MANAGED SECTION v1 -->
Old v1.
<!-- END CUB MANAGED SECTION -->

<!-- BEGIN CUB MANAGED SECTION v2 -->
Old v2.
<!-- END CUB MANAGED SECTION -->
"""
        sync = SyncService(project_dir=git_repo)
        new_sections = {
            "v1": ("New v1.\n", 0, 0),
            "v2": ("New v2.\n", 0, 0),
        }

        result = sync._inject_managed_sections(base_content, new_sections)

        assert "New v1." in result
        assert "New v2." in result
        assert "Old v1." not in result
        assert "Old v2." not in result


class TestConflictDetection:
    """Tests for detecting conflicts in managed sections."""

    def test_no_conflict_same_content(self, git_repo: Path) -> None:
        """No conflict when content is identical."""
        local = """
<!-- BEGIN CUB MANAGED SECTION v1 -->
Same content.
<!-- END CUB MANAGED SECTION -->
"""
        remote = """
<!-- BEGIN CUB MANAGED SECTION v1 -->
Same content.
<!-- END CUB MANAGED SECTION -->
"""
        sync = SyncService(project_dir=git_repo)
        conflicts = sync._detect_agent_sync_conflicts(local, remote)

        assert len(conflicts) == 0

    def test_conflict_different_content(self, git_repo: Path) -> None:
        """Conflict detected when both sides have different hashes."""
        local = """
<!-- BEGIN CUB MANAGED SECTION v1 -->
<!-- sha256:localhash123 -->
Local content.
<!-- END CUB MANAGED SECTION -->
"""
        remote = """
<!-- BEGIN CUB MANAGED SECTION v1 -->
<!-- sha256:remotehash456 -->
Remote content.
<!-- END CUB MANAGED SECTION -->
"""
        sync = SyncService(project_dir=git_repo)
        conflicts = sync._detect_agent_sync_conflicts(local, remote)

        assert len(conflicts) == 1
        assert "v1" in conflicts

    def test_no_conflict_different_versions(self, git_repo: Path) -> None:
        """No conflict when sections have different versions."""
        local = """
<!-- BEGIN CUB MANAGED SECTION v1 -->
Content.
<!-- END CUB MANAGED SECTION -->
"""
        remote = """
<!-- BEGIN CUB MANAGED SECTION v2 -->
Content.
<!-- END CUB MANAGED SECTION -->
"""
        sync = SyncService(project_dir=git_repo)
        conflicts = sync._detect_agent_sync_conflicts(local, remote)

        assert len(conflicts) == 0


class TestAgentPull:
    """Tests for pulling managed sections from sync branch."""

    def test_pull_not_initialized(self, git_repo: Path) -> None:
        """Pull fails if sync branch not initialized."""
        sync = SyncService(project_dir=git_repo)
        result = sync.sync_agent_pull()

        assert not result.success
        assert "not initialized" in result.message.lower()

    def test_pull_no_local_agent_file(self, git_repo: Path) -> None:
        """Pull fails if no local agent.md exists."""
        sync = SyncService(project_dir=git_repo)
        sync.initialize()

        result = sync.sync_agent_pull()

        assert not result.success
        assert "no agent.md" in result.message.lower()

    def test_pull_updates_local_file(self, git_repo: Path) -> None:
        """Pull updates local agent.md with remote sections (no conflict case)."""
        # Setup: create local agent.md with placeholder content
        cub_dir = git_repo / ".cub"
        cub_dir.mkdir()
        agent_file = cub_dir / "agent.md"
        agent_file.write_text("""
# Agent Instructions

<!-- BEGIN CUB MANAGED SECTION v1 -->
Placeholder.
<!-- END CUB MANAGED SECTION -->
""")

        # Initialize sync
        sync = SyncService(project_dir=git_repo)
        sync.initialize()

        # Update remote with new content (simulating sync branch update)
        remote_content = """
# Agent Instructions

<!-- BEGIN CUB MANAGED SECTION v1 -->
<!-- sha256:dummy -->
Remote content from sync branch.
<!-- END CUB MANAGED SECTION -->
"""
        blob_sha = sync._run_git(["hash-object", "-w", "--stdin"], input_data=remote_content)
        tree_sha = sync._create_tree_for_path(blob_sha, ".cub/agent.md")
        parent_sha = sync._get_branch_sha(sync.branch_ref)
        commit_sha = sync._run_git(
            ["commit-tree", tree_sha, "-p", parent_sha, "-m", "Add remote content"]
        )
        sync._run_git(["update-ref", sync.branch_ref, commit_sha])

        # Reset local to same placeholder to avoid conflict
        agent_file.write_text("""
# Agent Instructions

<!-- BEGIN CUB MANAGED SECTION v1 -->
Placeholder.
<!-- END CUB MANAGED SECTION -->
""")

        # Pull and verify
        result = sync.sync_agent_pull()

        assert result.success
        assert result.tasks_updated == 1

        # Verify local file was updated
        updated_content = agent_file.read_text()
        assert "Remote content from sync branch." in updated_content
        assert "Placeholder." not in updated_content

    def test_pull_with_conflicts(self, git_repo: Path) -> None:
        """Pull detects conflicts when both sides have different hashes."""
        # Setup local agent.md with hash
        cub_dir = git_repo / ".cub"
        cub_dir.mkdir()
        agent_file = cub_dir / "agent.md"
        agent_file.write_text("""
<!-- BEGIN CUB MANAGED SECTION v1 -->
<!-- sha256:localhash999 -->
Local modified.
<!-- END CUB MANAGED SECTION -->
""")

        # Setup sync branch with different content and different hash
        sync = SyncService(project_dir=git_repo)
        sync.initialize()

        remote_content = """
<!-- BEGIN CUB MANAGED SECTION v1 -->
<!-- sha256:remotehash888 -->
Remote modified.
<!-- END CUB MANAGED SECTION -->
"""
        blob_sha = sync._run_git(["hash-object", "-w", "--stdin"], input_data=remote_content)
        tree_sha = sync._create_tree_for_path(blob_sha, ".cub/agent.md")
        parent_sha = sync._get_branch_sha(sync.branch_ref)
        commit_sha = sync._run_git(
            ["commit-tree", tree_sha, "-p", parent_sha, "-m", "Remote change"]
        )
        sync._run_git(["update-ref", sync.branch_ref, commit_sha])

        # Pull should detect conflict
        result = sync.sync_agent_pull()

        assert not result.success
        assert len(result.conflicts) > 0
        assert "conflict" in result.message.lower()


class TestAgentPush:
    """Tests for pushing managed sections to sync branch."""

    def test_push_not_initialized(self, git_repo: Path) -> None:
        """Push fails if sync branch not initialized."""
        sync = SyncService(project_dir=git_repo)
        result = sync.sync_agent_push()

        assert not result.success
        assert "not initialized" in result.message.lower()

    def test_push_no_local_agent_file(self, git_repo: Path) -> None:
        """Push fails if no local agent.md exists."""
        sync = SyncService(project_dir=git_repo)
        sync.initialize()

        result = sync.sync_agent_push()

        assert not result.success
        assert "no agent.md" in result.message.lower()

    def test_push_creates_commit(self, git_repo: Path) -> None:
        """Push creates a commit on sync branch."""
        # Setup local agent.md
        cub_dir = git_repo / ".cub"
        cub_dir.mkdir()
        agent_file = cub_dir / "agent.md"
        agent_file.write_text("""
# Agent Instructions

<!-- BEGIN CUB MANAGED SECTION v1 -->
<!-- sha256:abc -->
Local content to push.
<!-- END CUB MANAGED SECTION -->
""")

        sync = SyncService(project_dir=git_repo)
        sync.initialize()

        # Push
        result = sync.sync_agent_push()

        assert result.success
        assert result.commit_sha is not None
        assert result.tasks_updated == 1

        # Verify content on sync branch
        remote_content = sync._get_file_from_ref(sync.branch_ref, ".cub/agent.md")
        assert remote_content is not None
        assert "Local content to push." in remote_content

    def test_push_no_sections(self, git_repo: Path) -> None:
        """Push with no managed sections returns success but no changes."""
        # Setup local agent.md without managed sections
        cub_dir = git_repo / ".cub"
        cub_dir.mkdir()
        agent_file = cub_dir / "agent.md"
        agent_file.write_text("# Agent Instructions\n\nNo managed sections.\n")

        sync = SyncService(project_dir=git_repo)
        sync.initialize()

        result = sync.sync_agent_push()

        assert result.success
        assert "no managed sections" in result.message.lower()

    def test_push_multiple_sections(self, git_repo: Path) -> None:
        """Push multiple managed sections."""
        cub_dir = git_repo / ".cub"
        cub_dir.mkdir()
        agent_file = cub_dir / "agent.md"
        agent_file.write_text("""
<!-- BEGIN CUB MANAGED SECTION v1 -->
Section 1.
<!-- END CUB MANAGED SECTION -->

<!-- BEGIN CUB MANAGED SECTION v2 -->
Section 2.
<!-- END CUB MANAGED SECTION -->
""")

        sync = SyncService(project_dir=git_repo)
        sync.initialize()

        result = sync.sync_agent_push()

        assert result.success
        assert result.tasks_updated == 2

        # Verify both sections on sync branch
        remote_content = sync._get_file_from_ref(sync.branch_ref, ".cub/agent.md")
        assert remote_content is not None
        assert "Section 1." in remote_content
        assert "Section 2." in remote_content


class TestAgentFileDiscovery:
    """Tests for finding agent.md variants."""

    def test_find_agent_md(self, git_repo: Path) -> None:
        """Find agent.md in .cub directory."""
        cub_dir = git_repo / ".cub"
        cub_dir.mkdir()
        (cub_dir / "agent.md").write_text("content")

        sync = SyncService(project_dir=git_repo)
        found = sync._find_agent_file(ref=None)

        assert found is not None
        assert "agent.md" in found

    def test_find_claude_md(self, git_repo: Path) -> None:
        """Find CLAUDE.md variant."""
        cub_dir = git_repo / ".cub"
        cub_dir.mkdir()
        (cub_dir / "CLAUDE.md").write_text("content")

        sync = SyncService(project_dir=git_repo)
        found = sync._find_agent_file(ref=None)

        assert found is not None
        assert "CLAUDE.md" in found

    def test_find_prefers_agent_md(self, git_repo: Path) -> None:
        """Prefer agent.md when multiple variants exist."""
        cub_dir = git_repo / ".cub"
        cub_dir.mkdir()
        (cub_dir / "agent.md").write_text("agent")
        (cub_dir / "CLAUDE.md").write_text("claude")

        sync = SyncService(project_dir=git_repo)
        found = sync._find_agent_file(ref=None)

        assert found is not None
        assert found.endswith("agent.md")

    def test_find_none_when_missing(self, git_repo: Path) -> None:
        """Return None when no agent file exists."""
        cub_dir = git_repo / ".cub"
        cub_dir.mkdir()

        sync = SyncService(project_dir=git_repo)
        found = sync._find_agent_file(ref=None)

        assert found is None
