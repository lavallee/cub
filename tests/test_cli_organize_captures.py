"""
Tests for cub organize-captures CLI command.
"""

from datetime import datetime, timezone
from pathlib import Path

import frontmatter  # type: ignore[import-untyped]
import pytest
from typer.testing import CliRunner

from cub.cli import app
from cub.core.captures.models import Capture, CaptureSource

runner = CliRunner()


@pytest.fixture
def temp_captures_dir(tmp_path: Path) -> Path:
    """Create a temporary captures directory."""
    captures_dir = tmp_path / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)
    return captures_dir


def test_organize_captures_no_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test organize-captures when captures directory doesn't exist."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["organize-captures"])

    assert result.exit_code == 0
    assert "Captures directory not found" in result.stdout
    assert "Nothing to organize" in result.stdout


def test_organize_captures_empty_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test organize-captures with empty captures directory."""
    captures_dir = tmp_path / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["organize-captures"])

    assert result.exit_code == 0
    assert "No markdown files found" in result.stdout


def test_organize_captures_all_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test organize-captures when all files are already valid."""
    captures_dir = tmp_path / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)

    # Create a valid capture file
    capture = Capture(
        id="cap-001",
        created=datetime(2026, 1, 16, 14, 30, 0, tzinfo=timezone.utc),
        title="Test Capture",
        tags=["test"],
        source=CaptureSource.CLI,
    )

    post = frontmatter.Post("This is a test capture")
    post.metadata = capture.to_frontmatter_dict()

    capture_file = captures_dir / "cap-001.md"
    with open(capture_file, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["organize-captures"])

    assert result.exit_code == 0
    assert "All capture files are properly organized" in result.stdout


def test_organize_captures_missing_frontmatter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test organize-captures with file missing frontmatter."""
    captures_dir = tmp_path / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)

    # Create a file without frontmatter
    plain_file = captures_dir / "plain-note.md"
    plain_file.write_text("Just a plain markdown file\n\nWith some content.", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    # Run with dry-run first
    result = runner.invoke(app, ["organize-captures", "--dry-run"])

    assert result.exit_code == 0
    assert "plain-note.md" in result.stdout
    assert "Missing frontmatter" in result.stdout
    assert "Dry run mode - no changes made" in result.stdout

    # Verify file wasn't changed
    assert plain_file.exists()
    assert not plain_file.read_text().startswith("---")


def test_organize_captures_invalid_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test organize-captures with file with invalid ID."""
    captures_dir = tmp_path / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)

    # Create a file with invalid ID
    post = frontmatter.Post("Test content")
    post.metadata = {
        "id": "invalid-id",
        "created": datetime(2026, 1, 16, 14, 30, 0, tzinfo=timezone.utc).isoformat(),
        "title": "Test",
    }

    invalid_file = captures_dir / "invalid-id.md"
    with open(invalid_file, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))

    monkeypatch.chdir(tmp_path)

    # Run with dry-run
    result = runner.invoke(app, ["organize-captures", "--dry-run"])

    assert result.exit_code == 0
    assert "invalid-id.md" in result.stdout
    assert "Invalid or missing ID" in result.stdout


def test_organize_captures_non_standard_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test organize-captures with non-standard filename."""
    captures_dir = tmp_path / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)

    # Create a valid capture with non-standard filename (not cap-NNN or YYYY-MM-DD format)
    capture = Capture(
        id="cap-001",
        created=datetime(2026, 1, 16, 14, 30, 0, tzinfo=timezone.utc),
        title="Test Capture",
        tags=["test"],
        source=CaptureSource.CLI,
    )

    post = frontmatter.Post("This is a test capture")
    post.metadata = capture.to_frontmatter_dict()

    # Save with non-standard filename (neither cap-NNN.md nor date-based)
    capture_file = captures_dir / "mynote.md"
    with open(capture_file, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))

    monkeypatch.chdir(tmp_path)

    # Run with dry-run
    result = runner.invoke(app, ["organize-captures", "--dry-run"])

    assert result.exit_code == 0
    assert "mynote.md" in result.stdout
    assert "Non-standard filename" in result.stdout
    assert "2026-01-16-test-capture.md" in result.stdout


def test_organize_captures_apply_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test organize-captures actually applies changes with --yes flag."""
    captures_dir = tmp_path / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)

    # Create a file without frontmatter
    plain_file = captures_dir / "plain-note.md"
    plain_file.write_text("Just a plain markdown file", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    # Run with --yes to skip confirmation
    result = runner.invoke(app, ["organize-captures", "--yes"])

    assert result.exit_code == 0
    assert "Successfully organized 1 files" in result.stdout

    # Verify that a cap-*.md file was created (random ID format)
    cap_files = list(captures_dir.glob("cap-*.md"))
    assert len(cap_files) == 1
    cap_file = cap_files[0]

    # Verify it has frontmatter
    post = frontmatter.load(cap_file)
    assert "id" in post.metadata
    assert post.metadata["id"].startswith("cap-")
    assert "created" in post.metadata
    assert "title" in post.metadata

    # Verify old file was removed
    assert not plain_file.exists()


def test_organize_captures_global_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test organize-captures with --global flag."""
    from unittest.mock import patch

    # Mock the XDG_DATA_HOME to point to our temp dir
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    # Create the expected directory structure (with project ID)
    # Global store now expects: ~/.local/share/cub/captures/{project_id}/
    cub_captures = tmp_path / "cub" / "captures" / "test-project"
    cub_captures.mkdir(parents=True, exist_ok=True)

    # Create a file without frontmatter in global captures
    plain_file = cub_captures / "global-note.md"
    plain_file.write_text("Global capture content", encoding="utf-8")

    # Create a different working directory
    work_dir = tmp_path / "somewhere_else"
    work_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(work_dir)

    # Mock get_project_id to return a consistent value
    with patch("cub.core.captures.store.get_project_id", return_value="test-project"):
        # Run with --global and --dry-run
        result = runner.invoke(app, ["organize-captures", "--global", "--dry-run"])

    assert result.exit_code == 0
    assert "global-note.md" in result.stdout
