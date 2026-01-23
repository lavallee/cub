"""
Tests for ledger insight extraction.

Tests the LLM-based insight extraction from harness logs,
including model validation, parsing, fallback behavior, and
error handling.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from cub.core.ledger.extractor import (
    InsightExtraction,
    _build_extraction_prompt,
    _extract_basic_approach,
    _fallback_extraction,
    _parse_bullet_list,
    _parse_extraction_response,
    _truncate_log,
    extract_insights,
)
from cub.core.tasks.models import Task


class TestInsightExtraction:
    """Tests for InsightExtraction model."""

    def test_create_with_defaults(self) -> None:
        """Test creating InsightExtraction with default values."""
        extraction = InsightExtraction()
        assert extraction.approach == ""
        assert extraction.decisions == []
        assert extraction.lessons_learned == []
        assert extraction.success is True
        assert extraction.error is None
        assert extraction.model_used == "haiku"
        assert extraction.tokens_used == 0

    def test_create_with_values(self) -> None:
        """Test creating InsightExtraction with specific values."""
        extraction = InsightExtraction(
            approach="Used JWT with bcrypt for password hashing",
            decisions=["JWT over session cookies", "24h token expiry"],
            lessons_learned=["bcrypt.compare is async in Node.js"],
            success=True,
            model_used="haiku",
            tokens_used=1500,
        )
        assert extraction.approach == "Used JWT with bcrypt for password hashing"
        assert len(extraction.decisions) == 2
        assert len(extraction.lessons_learned) == 1
        assert extraction.success is True
        assert extraction.tokens_used == 1500

    def test_create_failed_extraction(self) -> None:
        """Test creating InsightExtraction for failed extraction."""
        extraction = InsightExtraction(
            success=False,
            error="Claude CLI timed out",
            model_used="fallback",
        )
        assert extraction.success is False
        assert extraction.error == "Claude CLI timed out"
        assert extraction.model_used == "fallback"

    def test_negative_tokens_rejected(self) -> None:
        """Test that negative token values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            InsightExtraction(tokens_used=-100)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_serialization_roundtrip(self) -> None:
        """Test serialization and deserialization roundtrip."""
        original = InsightExtraction(
            approach="Test approach",
            decisions=["Decision 1", "Decision 2"],
            lessons_learned=["Lesson 1"],
            success=True,
            tokens_used=500,
        )

        data = original.model_dump()
        restored = InsightExtraction.model_validate(data)

        assert restored.approach == original.approach
        assert restored.decisions == original.decisions
        assert restored.lessons_learned == original.lessons_learned
        assert restored.success == original.success
        assert restored.tokens_used == original.tokens_used


class TestParseBulletList:
    """Tests for _parse_bullet_list helper."""

    def test_parse_dash_bullets(self) -> None:
        """Test parsing dash-prefixed bullet list."""
        text = """- First item
- Second item
- Third item"""
        result = _parse_bullet_list(text)
        assert result == ["First item", "Second item", "Third item"]

    def test_parse_asterisk_bullets(self) -> None:
        """Test parsing asterisk-prefixed bullet list."""
        text = """* First item
* Second item"""
        result = _parse_bullet_list(text)
        assert result == ["First item", "Second item"]

    def test_parse_numbered_list(self) -> None:
        """Test parsing numbered list."""
        text = """1. First item
2. Second item
3) Third item"""
        result = _parse_bullet_list(text)
        assert result == ["First item", "Second item", "Third item"]

    def test_parse_mixed_formatting(self) -> None:
        """Test parsing list with mixed formatting."""
        text = """- First item
  * Second with indent
1. Third numbered"""
        result = _parse_bullet_list(text)
        assert result == ["First item", "Second with indent", "Third numbered"]

    def test_parse_none_keyword(self) -> None:
        """Test that 'None' keyword returns empty list."""
        assert _parse_bullet_list("None") == []
        assert _parse_bullet_list("none") == []
        assert _parse_bullet_list("  None  ") == []

    def test_parse_empty_text(self) -> None:
        """Test that empty text returns empty list."""
        assert _parse_bullet_list("") == []
        assert _parse_bullet_list("   ") == []

    def test_parse_none_value(self) -> None:
        """Test handling None value edge case via empty string behavior."""
        # The function expects a string, but should handle empty gracefully
        assert _parse_bullet_list("") == []

    def test_filters_empty_lines(self) -> None:
        """Test that empty lines are filtered out."""
        text = """- First item

- Second item

- Third item"""
        result = _parse_bullet_list(text)
        assert result == ["First item", "Second item", "Third item"]

    def test_filters_none_items(self) -> None:
        """Test that 'None' items in list are filtered."""
        text = """- First item
- None
- Third item"""
        result = _parse_bullet_list(text)
        assert result == ["First item", "Third item"]


class TestTruncateLog:
    """Tests for _truncate_log helper."""

    def test_short_log_unchanged(self) -> None:
        """Test that short logs are returned unchanged."""
        log = "Short log content"
        result = _truncate_log(log, max_chars=1000)
        assert result == log

    def test_long_log_truncated(self) -> None:
        """Test that long logs are truncated with indicator."""
        log = "x" * 100000
        result = _truncate_log(log, max_chars=50000)
        assert len(result) <= 50000
        assert "[LOG TRUNCATED - middle portion removed]" in result

    def test_preserves_beginning_and_end(self) -> None:
        """Test that truncation preserves log beginning and end."""
        beginning = "START_MARKER " + "a" * 10000
        middle = "b" * 80000
        ending = "c" * 10000 + " END_MARKER"
        log = beginning + middle + ending

        result = _truncate_log(log, max_chars=50000)

        assert "START_MARKER" in result
        assert "END_MARKER" in result
        assert "[LOG TRUNCATED" in result

    def test_exact_limit_unchanged(self) -> None:
        """Test that log at exact limit is unchanged."""
        log = "x" * 50000
        result = _truncate_log(log, max_chars=50000)
        assert result == log


class TestParseExtractionResponse:
    """Tests for _parse_extraction_response helper."""

    def test_parse_complete_response(self) -> None:
        """Test parsing a complete, well-formatted response."""
        response = """APPROACH:
Implemented JWT authentication with bcrypt for secure password hashing.
The solution follows industry best practices.

DECISIONS:
- Used JWT over session cookies for stateless auth
- Set 24-hour token expiry for security
- Stored refresh tokens in httpOnly cookies

LESSONS:
- bcrypt.compare is async in Node.js
- JWT tokens should include minimal claims
- Always validate token on server side"""

        result = _parse_extraction_response(response)

        assert "JWT authentication" in result.approach
        assert len(result.decisions) == 3
        assert len(result.lessons_learned) == 3
        assert result.success is True

    def test_parse_with_none_sections(self) -> None:
        """Test parsing response with 'None' in sections."""
        response = """APPROACH:
Simple bug fix in configuration file.

DECISIONS:
None

LESSONS:
- Always check config file syntax before deploying"""

        result = _parse_extraction_response(response)

        assert "bug fix" in result.approach
        assert result.decisions == []
        assert len(result.lessons_learned) == 1

    def test_parse_minimal_response(self) -> None:
        """Test parsing a minimal response."""
        response = """APPROACH:
Fixed the issue.

DECISIONS:
None

LESSONS:
None"""

        result = _parse_extraction_response(response)

        assert result.approach == "Fixed the issue."
        assert result.decisions == []
        assert result.lessons_learned == []

    def test_parse_empty_response(self) -> None:
        """Test parsing an empty response."""
        result = _parse_extraction_response("")
        assert result.approach == ""
        assert result.decisions == []
        assert result.lessons_learned == []
        assert result.success is True

    def test_parse_malformed_response(self) -> None:
        """Test parsing a response missing expected sections."""
        response = "Some random text without proper formatting"
        result = _parse_extraction_response(response)
        # Should gracefully handle missing sections
        assert result.approach == ""
        assert result.decisions == []
        assert result.lessons_learned == []


class TestBuildExtractionPrompt:
    """Tests for _build_extraction_prompt helper."""

    def test_includes_task_details(self) -> None:
        """Test that prompt includes task ID, title, and description."""
        task = Task(
            id="cub-001",
            title="Add authentication",
            description="Implement JWT-based authentication for the API",
        )
        log = "Sample execution log"

        prompt = _build_extraction_prompt(log, task)

        assert "cub-001" in prompt
        assert "Add authentication" in prompt
        assert "JWT-based authentication" in prompt
        assert "Sample execution log" in prompt

    def test_includes_format_instructions(self) -> None:
        """Test that prompt includes expected format instructions."""
        task = Task(id="test", title="Test")
        log = "Log content"

        prompt = _build_extraction_prompt(log, task)

        assert "APPROACH:" in prompt
        assert "DECISIONS:" in prompt
        assert "LESSONS:" in prompt

    def test_truncates_long_description(self) -> None:
        """Test that very long descriptions are truncated."""
        long_desc = "x" * 1000
        task = Task(id="test", title="Test", description=long_desc)
        log = "Log"

        prompt = _build_extraction_prompt(log, task)

        # Description should be truncated to 500 chars
        assert len(prompt) < len(long_desc) + 1000

    def test_handles_empty_description(self) -> None:
        """Test handling task with no description."""
        task = Task(id="test", title="Test", description="")
        log = "Log"

        prompt = _build_extraction_prompt(log, task)

        assert "(no description)" in prompt


class TestExtractBasicApproach:
    """Tests for _extract_basic_approach fallback helper."""

    def test_detects_file_creation(self) -> None:
        """Test detection of file creation patterns."""
        log = "Created file `src/auth/jwt.ts` with JWT implementation"
        task = Task(id="test", title="Add auth")

        result = _extract_basic_approach(log, task)

        assert "Created files" in result or "Add auth" in result

    def test_detects_test_runs(self) -> None:
        """Test detection of test execution patterns."""
        log = "Running tests with pytest... All tests passed"
        task = Task(id="test", title="Fix bug")

        result = _extract_basic_approach(log, task)

        assert "Ran tests" in result or "Fix bug" in result

    def test_detects_bug_fixes(self) -> None:
        """Test detection of bug fix patterns."""
        log = "Fixed bug in authentication module"
        task = Task(id="test", title="Fix login")

        result = _extract_basic_approach(log, task)

        assert "Fixed bugs" in result or "Fix login" in result

    def test_fallback_to_task_title(self) -> None:
        """Test fallback to task title when no patterns match."""
        log = "Some generic execution output"
        task = Task(id="test", title="Update dependencies")

        result = _extract_basic_approach(log, task)

        assert "Update dependencies" in result


class TestFallbackExtraction:
    """Tests for _fallback_extraction helper."""

    def test_returns_failed_extraction(self) -> None:
        """Test that fallback returns extraction with success=False."""
        task = Task(id="test", title="Test task")

        result = _fallback_extraction("Log content", task, "Test error")

        assert result.success is False
        assert result.error == "Test error"
        assert result.model_used == "fallback"
        assert result.tokens_used == 0

    def test_includes_basic_approach(self) -> None:
        """Test that fallback includes a basic approach description."""
        task = Task(id="test", title="Add feature")

        result = _fallback_extraction("Created new files", task, "Error")

        assert result.approach != ""
        assert "Add feature" in result.approach or "Created files" in result.approach


class TestExtractInsights:
    """Tests for the main extract_insights function."""

    @patch("cub.core.ledger.extractor.subprocess.run")
    def test_successful_extraction(self, mock_run: MagicMock) -> None:
        """Test successful insight extraction."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""APPROACH:
Implemented the feature using test-driven development.

DECISIONS:
- Used dependency injection for testability

LESSONS:
- TDD helps catch edge cases early""",
        )

        task = Task(id="cub-001", title="Add feature")
        result = extract_insights("Sample log", task)

        assert result.success is True
        assert "test-driven development" in result.approach
        assert len(result.decisions) == 1
        assert len(result.lessons_learned) == 1

    @patch("cub.core.ledger.extractor.subprocess.run")
    def test_cli_nonzero_exit(self, mock_run: MagicMock) -> None:
        """Test fallback on non-zero CLI exit code."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")

        task = Task(id="test", title="Test")
        result = extract_insights("Log", task)

        assert result.success is False
        assert "exit code" in (result.error or "")

    @patch("cub.core.ledger.extractor.subprocess.run")
    def test_cli_timeout(self, mock_run: MagicMock) -> None:
        """Test fallback on CLI timeout."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=60)

        task = Task(id="test", title="Test")
        result = extract_insights("Log", task)

        assert result.success is False
        assert "timed out" in (result.error or "")

    @patch("cub.core.ledger.extractor.subprocess.run")
    def test_cli_not_found(self, mock_run: MagicMock) -> None:
        """Test fallback when Claude CLI not installed."""
        mock_run.side_effect = FileNotFoundError()

        task = Task(id="test", title="Test")
        result = extract_insights("Log", task)

        assert result.success is False
        assert "not installed" in (result.error or "")

    @patch("cub.core.ledger.extractor.subprocess.run")
    def test_os_error(self, mock_run: MagicMock) -> None:
        """Test fallback on OS error."""
        mock_run.side_effect = OSError("Permission denied")

        task = Task(id="test", title="Test")
        result = extract_insights("Log", task)

        assert result.success is False
        assert "OS error" in (result.error or "")

    @patch("cub.core.ledger.extractor.subprocess.run")
    def test_calls_haiku_model(self, mock_run: MagicMock) -> None:
        """Test that extraction uses haiku model for cost efficiency."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="APPROACH:\nTest\n\nDECISIONS:\nNone\n\nLESSONS:\nNone",
        )

        task = Task(id="test", title="Test")
        extract_insights("Log", task)

        # Verify haiku model was specified
        call_args = mock_run.call_args
        assert "--model" in call_args[0][0]
        assert "haiku" in call_args[0][0]

    @patch("cub.core.ledger.extractor.subprocess.run")
    def test_truncates_long_logs(self, mock_run: MagicMock) -> None:
        """Test that very long logs are truncated before sending."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="APPROACH:\nHandled\n\nDECISIONS:\nNone\n\nLESSONS:\nNone",
        )

        # Create a very long log
        long_log = "x" * 100000
        task = Task(id="test", title="Test")

        extract_insights(long_log, task)

        # The prompt sent to Claude should be truncated
        call_args = mock_run.call_args
        prompt = call_args[0][0][-1]  # Last argument is the prompt
        # The full prompt should be reasonable size (not 100k+ chars)
        assert len(prompt) < 60000

    @patch("cub.core.ledger.extractor.subprocess.run")
    def test_custom_timeout(self, mock_run: MagicMock) -> None:
        """Test that custom timeout is passed to subprocess."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="APPROACH:\nTest\n\nDECISIONS:\nNone\n\nLESSONS:\nNone",
        )

        task = Task(id="test", title="Test")
        extract_insights("Log", task, timeout=120)

        # Verify custom timeout was used
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 120
