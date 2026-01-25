"""
Tests for LLM-based deep analysis in the review system.

Tests the integration between the review assessor and harness backends
for deep implementation analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from cub.core.harness.models import HarnessFeature, TaskResult, TokenUsage
from cub.core.ledger.models import (
    DriftRecord,
    LedgerEntry,
    Outcome,
    TaskSnapshot,
)
from cub.core.review.models import IssueSeverity, IssueType
from cub.core.review.prompts import (
    _is_analyzable_file,
    build_analysis_context,
    parse_analysis_issues,
    read_implementation_files,
    read_spec_file,
)


class TestBuildAnalysisContext:
    """Tests for building analysis context from ledger entries."""

    def test_minimal_context(self) -> None:
        """Test context building with minimal entry data."""
        entry = LedgerEntry(
            id="test-123",
            title="Test Task",
            completed_at=datetime.now(timezone.utc),
        )

        context = build_analysis_context(entry)

        assert "test-123" in context
        assert "Test Task" in context
        assert "# Task Information" in context

    def test_context_with_task_snapshot(self) -> None:
        """Test context includes task snapshot details."""
        entry = LedgerEntry(
            id="test-123",
            title="Test Task",
            task=TaskSnapshot(
                title="Test Task",
                description="A detailed task description",
                type="feature",
            ),
            completed_at=datetime.now(timezone.utc),
        )

        context = build_analysis_context(entry)

        assert "A detailed task description" in context
        assert "feature" in context

    def test_context_with_outcome(self) -> None:
        """Test context includes outcome details."""
        entry = LedgerEntry(
            id="test-123",
            title="Test Task",
            outcome=Outcome(
                success=True,
                approach="Used TDD approach",
                decisions=["Decision 1", "Decision 2"],
                files_changed=["src/foo.py", "src/bar.py"],
            ),
            completed_at=datetime.now(timezone.utc),
        )

        context = build_analysis_context(entry)

        assert "Success" in context
        assert "TDD approach" in context
        assert "Decision 1" in context
        assert "src/foo.py" in context

    def test_context_with_spec_content(self) -> None:
        """Test context includes spec content."""
        entry = LedgerEntry(
            id="test-123",
            title="Test Task",
            completed_at=datetime.now(timezone.utc),
        )

        spec_content = "# Spec\n\nThis is the specification."
        context = build_analysis_context(entry, spec_content=spec_content)

        assert "# Specification" in context
        assert "This is the specification" in context

    def test_context_with_implementation_files(self) -> None:
        """Test context notes implementation files."""
        entry = LedgerEntry(
            id="test-123",
            title="Test Task",
            completed_at=datetime.now(timezone.utc),
        )

        files = {"src/main.py": "print('hello')"}
        context = build_analysis_context(entry, implementation_files=files)

        assert "# Implementation Files" in context
        assert "1 files" in context

    def test_context_with_drift(self) -> None:
        """Test context includes drift information."""
        entry = LedgerEntry(
            id="test-123",
            title="Test Task",
            drift=DriftRecord(
                severity="significant",
                additions=["Added feature X"],
                omissions=["Skipped feature Y"],
            ),
            completed_at=datetime.now(timezone.utc),
        )

        context = build_analysis_context(entry)

        assert "significant" in context
        assert "Added feature X" in context
        assert "Skipped feature Y" in context


class TestParseAnalysisIssues:
    """Tests for parsing LLM analysis output into issues."""

    def test_parse_critical_issue(self) -> None:
        """Test parsing a CRITICAL severity issue."""
        analysis = "[CRITICAL] Missing error handling - Add try/except blocks"

        issues = parse_analysis_issues(analysis)

        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.CRITICAL
        assert "Missing error handling" in issues[0].description
        assert "Add try/except blocks" in issues[0].recommendation

    def test_parse_warning_issue(self) -> None:
        """Test parsing a WARNING severity issue."""
        analysis = "[WARNING] No tests for edge cases"

        issues = parse_analysis_issues(analysis)

        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.WARNING
        assert "No tests for edge cases" in issues[0].description

    def test_parse_info_issue(self) -> None:
        """Test parsing an INFO severity issue."""
        analysis = "[INFO] Consider adding documentation"

        issues = parse_analysis_issues(analysis)

        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.INFO
        assert "documentation" in issues[0].description

    def test_parse_multiple_issues(self) -> None:
        """Test parsing multiple issues from analysis."""
        analysis = """## Issues Found

[CRITICAL] Security vulnerability - Use parameterized queries
[WARNING] Performance issue - Consider caching
[INFO] Could improve naming
"""

        issues = parse_analysis_issues(analysis)

        assert len(issues) == 3
        assert issues[0].severity == IssueSeverity.CRITICAL
        assert issues[1].severity == IssueSeverity.WARNING
        assert issues[2].severity == IssueSeverity.INFO

    def test_parse_no_issues(self) -> None:
        """Test parsing when no issues found."""
        analysis = "## Summary\n\nNo issues found."

        issues = parse_analysis_issues(analysis)

        assert len(issues) == 0

    def test_parse_bullet_formatted_issues(self) -> None:
        """Test parsing issues with bullet points."""
        analysis = "- [CRITICAL] Issue one\n* [WARNING] Issue two"

        issues = parse_analysis_issues(analysis)

        assert len(issues) == 2

    def test_issue_type_is_deep_analysis(self) -> None:
        """Test that parsed issues have DEEP_ANALYSIS_FINDING type."""
        analysis = "[CRITICAL] Something is wrong"

        issues = parse_analysis_issues(analysis)

        assert issues[0].type == IssueType.DEEP_ANALYSIS_FINDING


class TestReadSpecFile:
    """Tests for reading spec files."""

    def test_read_existing_spec(self, tmp_path: Path) -> None:
        """Test reading an existing spec file."""
        spec_path = tmp_path / "spec.md"
        spec_path.write_text("# Spec Content")

        content = read_spec_file(str(spec_path), tmp_path)

        assert content == "# Spec Content"

    def test_read_relative_spec(self, tmp_path: Path) -> None:
        """Test reading a spec file with relative path."""
        spec_path = tmp_path / "specs" / "feature.md"
        spec_path.parent.mkdir(parents=True)
        spec_path.write_text("# Feature Spec")

        content = read_spec_file("specs/feature.md", tmp_path)

        assert content == "# Feature Spec"

    def test_read_missing_spec(self, tmp_path: Path) -> None:
        """Test reading a non-existent spec file."""
        content = read_spec_file("nonexistent.md", tmp_path)

        assert content is None

    def test_read_none_spec_path(self, tmp_path: Path) -> None:
        """Test reading when spec path is None."""
        content = read_spec_file(None, tmp_path)

        assert content is None


class TestReadImplementationFiles:
    """Tests for reading implementation files."""

    def test_read_single_file(self, tmp_path: Path) -> None:
        """Test reading a single implementation file."""
        file_path = tmp_path / "src" / "main.py"
        file_path.parent.mkdir(parents=True)
        file_path.write_text("print('hello')")

        contents = read_implementation_files(["src/main.py"], tmp_path)

        assert "src/main.py" in contents
        assert contents["src/main.py"] == "print('hello')"

    def test_read_multiple_files(self, tmp_path: Path) -> None:
        """Test reading multiple files."""
        for name in ["a.py", "b.py"]:
            path = tmp_path / name
            path.write_text(f"# {name}")

        contents = read_implementation_files(["a.py", "b.py"], tmp_path)

        assert len(contents) == 2

    def test_skip_binary_files(self, tmp_path: Path) -> None:
        """Test that binary files are skipped."""
        png_path = tmp_path / "image.png"
        png_path.write_bytes(b"\x89PNG")

        contents = read_implementation_files(["image.png"], tmp_path)

        assert len(contents) == 0

    def test_skip_pycache(self, tmp_path: Path) -> None:
        """Test that __pycache__ files are skipped."""
        cache_path = tmp_path / "__pycache__" / "module.pyc"
        cache_path.parent.mkdir(parents=True)
        cache_path.write_text("bytecode")

        contents = read_implementation_files(["__pycache__/module.pyc"], tmp_path)

        assert len(contents) == 0

    def test_max_files_limit(self, tmp_path: Path) -> None:
        """Test that max_files limit is respected."""
        for i in range(5):
            (tmp_path / f"file{i}.py").write_text(f"# {i}")

        paths = [f"file{i}.py" for i in range(5)]
        contents = read_implementation_files(paths, tmp_path, max_files=2)

        assert len(contents) == 2


class TestIsAnalyzableFile:
    """Tests for file analyzability checks."""

    def test_python_files_analyzable(self) -> None:
        """Test that Python files are analyzable."""
        assert _is_analyzable_file("src/main.py") is True
        assert _is_analyzable_file("tests/test_main.py") is True

    def test_binary_files_not_analyzable(self) -> None:
        """Test that binary files are not analyzable."""
        assert _is_analyzable_file("image.png") is False
        assert _is_analyzable_file("font.woff") is False
        assert _is_analyzable_file("app.exe") is False

    def test_pycache_not_analyzable(self) -> None:
        """Test that __pycache__ files are not analyzable."""
        assert _is_analyzable_file("__pycache__/module.cpython-310.pyc") is False

    def test_node_modules_not_analyzable(self) -> None:
        """Test that node_modules files are not analyzable."""
        assert _is_analyzable_file("node_modules/pkg/index.js") is False


class TestHarnessAnalyzeMethod:
    """Tests for the analyze() method on harness backends."""

    @pytest.mark.asyncio
    async def test_claude_sdk_analyze(self) -> None:
        """Test that ClaudeSDKBackend.analyze() works."""
        from cub.core.harness.claude_sdk import ClaudeSDKBackend

        backend = ClaudeSDKBackend()

        # Mock run_task to avoid actual API calls
        mock_result = TaskResult(
            output="## Summary\nNo issues found.",
            usage=TokenUsage(input_tokens=100, output_tokens=50),
            duration_seconds=1.0,
            exit_code=0,
        )
        backend.run_task = AsyncMock(return_value=mock_result)

        result = await backend.analyze(
            context="Test context",
            files_content={"test.py": "print('hello')"},
            analysis_type="implementation_review",
        )

        assert result.output == "## Summary\nNo issues found."
        backend.run_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_claude_cli_analyze(self) -> None:
        """Test that ClaudeCLIBackend.analyze() works."""
        from cub.core.harness.claude_cli import ClaudeCLIBackend

        backend = ClaudeCLIBackend()

        # Mock run_task
        mock_result = TaskResult(
            output="[CRITICAL] Issue found - Fix it",
            usage=TokenUsage(input_tokens=100, output_tokens=50),
            duration_seconds=1.0,
            exit_code=0,
        )
        backend.run_task = AsyncMock(return_value=mock_result)

        result = await backend.analyze(
            context="Test context",
            analysis_type="code_quality",
        )

        assert "Issue found" in result.output

    @pytest.mark.asyncio
    async def test_codex_analyze(self) -> None:
        """Test that CodexBackend.analyze() works."""
        from cub.core.harness.codex import CodexBackend

        backend = CodexBackend()

        # Mock run_task
        mock_result = TaskResult(
            output="## Analysis complete",
            usage=TokenUsage(input_tokens=100, output_tokens=50, estimated=True),
            duration_seconds=1.0,
            exit_code=0,
        )
        backend.run_task = AsyncMock(return_value=mock_result)

        result = await backend.analyze(
            context="Test context",
            analysis_type="spec_gap",
        )

        assert "Analysis complete" in result.output


class TestSupportsAnalysisFeature:
    """Tests for ANALYSIS feature support."""

    def test_claude_sdk_supports_analysis(self) -> None:
        """Test that ClaudeSDKBackend supports ANALYSIS."""
        from cub.core.harness.claude_sdk import ClaudeSDKBackend

        backend = ClaudeSDKBackend()
        assert backend.supports_feature(HarnessFeature.ANALYSIS) is True

    def test_claude_cli_supports_analysis(self) -> None:
        """Test that ClaudeCLIBackend supports ANALYSIS."""
        from cub.core.harness.claude_cli import ClaudeCLIBackend

        backend = ClaudeCLIBackend()
        assert backend.supports_feature(HarnessFeature.ANALYSIS) is True

    def test_codex_supports_analysis(self) -> None:
        """Test that CodexBackend supports ANALYSIS."""
        from cub.core.harness.codex import CodexBackend

        backend = CodexBackend()
        assert backend.supports_feature(HarnessFeature.ANALYSIS) is True
