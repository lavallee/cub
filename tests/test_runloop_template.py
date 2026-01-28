"""
Tests for runloop.md template verification.
"""

from pathlib import Path

import pytest


class TestRunloopTemplate:
    """Tests for runloop.md template content."""

    @pytest.fixture
    def runloop_content(self) -> str:
        """Load the runloop.md template content."""
        template_path = Path(__file__).parent.parent / "templates" / "runloop.md"
        return template_path.read_text()

    def test_contains_escape_hatch(self, runloop_content: str) -> None:
        """Verify runloop.md contains the escape hatch mechanism."""
        assert "Escape Hatch: Signal When Stuck" in runloop_content
        assert "<stuck>" in runloop_content
        assert "REASON FOR BEING STUCK" in runloop_content

    def test_contains_complete_signal(self, runloop_content: str) -> None:
        """Verify runloop.md contains the COMPLETE signal instruction."""
        assert "<promise>COMPLETE</promise>" in runloop_content
        assert "This signals the loop should terminate" in runloop_content

    def test_does_not_contain_progress_txt_references(self, runloop_content: str) -> None:
        """Verify runloop.md does not reference progress.txt."""
        assert "progress.txt" not in runloop_content.lower()
        assert "@progress.txt" not in runloop_content

    def test_does_not_contain_agent_md_references(self, runloop_content: str) -> None:
        """Verify runloop.md does not reference @AGENT.md."""
        assert "@AGENT.md" not in runloop_content

    def test_does_not_contain_specs_references(self, runloop_content: str) -> None:
        """Verify runloop.md does not reference @specs/*."""
        assert "@specs" not in runloop_content

    def test_contains_workflow_section(self, runloop_content: str) -> None:
        """Verify runloop.md contains the core workflow."""
        assert "## Your Workflow" in runloop_content
        assert "Understand" in runloop_content
        assert "Implement" in runloop_content
        assert "Validate" in runloop_content
        assert "Complete" in runloop_content

    def test_contains_critical_rules(self, runloop_content: str) -> None:
        """Verify runloop.md contains critical rules."""
        assert "## Critical Rules" in runloop_content
        assert "ONE TASK" in runloop_content
        assert "FULL IMPLEMENTATION" in runloop_content
        assert "CLOSE THE TASK" in runloop_content

    def test_contains_feedback_loop_instructions(self, runloop_content: str) -> None:
        """Verify runloop.md contains feedback loop instructions."""
        assert "feedback loops" in runloop_content.lower()
        assert "Type checking" in runloop_content
        assert "Tests" in runloop_content
        assert "Linting" in runloop_content

    def test_does_not_contain_html_comment_header(self, runloop_content: str) -> None:
        """Verify runloop.md does not contain the lengthy HTML comment header."""
        assert "<!--" not in runloop_content
        assert "SYSTEM PROMPT FOR CUB AUTONOMOUS CODING" not in runloop_content

    def test_approximate_line_count(self, runloop_content: str) -> None:
        """Verify runloop.md is approximately 40-60 lines (target ~40)."""
        line_count = len(runloop_content.strip().split("\n"))
        # Allow some flexibility but should be much shorter than PROMPT.md
        assert 30 <= line_count <= 70, f"Expected ~40 lines, got {line_count}"
