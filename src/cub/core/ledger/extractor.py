"""
LLM-based insight extraction for the ledger.

Uses Claude Haiku to extract structured insights (approach, decisions,
lessons learned) from harness execution logs. This provides rich metadata
for the completed work ledger without manual input.
"""

import re
import subprocess

from pydantic import BaseModel, Field

from cub.core.tasks.models import Task

# Default timeout for Claude CLI calls (seconds)
CLAUDE_TIMEOUT = 60


class InsightExtraction(BaseModel):
    """Result of LLM insight extraction from a harness log.

    Contains the extracted approach, decisions, and lessons learned,
    along with metadata about the extraction process itself.

    Example:
        >>> extraction = InsightExtraction(
        ...     approach="Implemented using JWT with bcrypt for password hashing",
        ...     decisions=["JWT over session cookies", "24h token expiry"],
        ...     lessons_learned=["bcrypt.compare is async in Node.js"],
        ...     success=True
        ... )
    """

    approach: str = Field(
        default="",
        description="High-level approach taken to complete the task (markdown)",
    )
    decisions: list[str] = Field(
        default_factory=list,
        description="Key technical or implementation decisions made",
    )
    lessons_learned: list[str] = Field(
        default_factory=list,
        description="Insights and learnings from the implementation",
    )
    success: bool = Field(
        default=True,
        description="Whether extraction was successful",
    )
    error: str | None = Field(
        default=None,
        description="Error message if extraction failed",
    )
    model_used: str = Field(
        default="haiku",
        description="Model used for extraction",
    )
    tokens_used: int = Field(
        default=0,
        ge=0,
        description="Approximate token count for extraction (if available)",
    )


def extract_insights(
    harness_log: str,
    task: Task,
    timeout: int = CLAUDE_TIMEOUT,
) -> InsightExtraction:
    """
    Extract structured insights from a harness execution log using LLM.

    Uses Claude Haiku to analyze the execution log and extract:
    - The approach taken to complete the task
    - Key decisions made during implementation
    - Lessons learned or insights gained

    Args:
        harness_log: The raw output/log from harness execution.
        task: The task that was executed (provides context).
        timeout: Timeout in seconds for the Claude CLI call.

    Returns:
        InsightExtraction with extracted data, or fallback on failure.

    Example:
        >>> from cub.core.tasks.models import Task
        >>> task = Task(id="cub-001", title="Add authentication")
        >>> log = "Implemented JWT auth with bcrypt..."
        >>> insights = extract_insights(log, task)
        >>> insights.success
        True
    """
    # Truncate very long logs to stay within context limits
    truncated_log = _truncate_log(harness_log, max_chars=50000)

    prompt = _build_extraction_prompt(truncated_log, task)

    try:
        result = subprocess.run(
            ["claude", "--model", "haiku", "--print", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            return _fallback_extraction(
                harness_log, task, error=f"Claude CLI returned exit code {result.returncode}"
            )

        return _parse_extraction_response(result.stdout)

    except subprocess.TimeoutExpired:
        return _fallback_extraction(harness_log, task, error="Claude CLI timed out")
    except FileNotFoundError:
        return _fallback_extraction(harness_log, task, error="Claude CLI not installed")
    except OSError as e:
        return _fallback_extraction(harness_log, task, error=f"OS error: {e}")


def _build_extraction_prompt(harness_log: str, task: Task) -> str:
    """Build the extraction prompt for Claude.

    Args:
        harness_log: Truncated harness execution log.
        task: Task being analyzed.

    Returns:
        Formatted prompt string.
    """
    return f"""Analyze this AI coding assistant execution log and extract insights about
how the task was completed.

TASK:
- ID: {task.id}
- Title: {task.title}
- Description: {task.description[:500] if task.description else "(no description)"}

EXECUTION LOG:
{harness_log}

Extract the following information and respond in this exact format:

APPROACH:
<A 1-3 sentence summary of the approach taken to complete the task.
Focus on the overall strategy, not implementation details.>

DECISIONS:
- <Key decision 1 made during implementation>
- <Key decision 2>
- <Add more as needed, or "None" if no notable decisions>

LESSONS:
- <Lesson or insight 1 learned from this work>
- <Lesson 2>
- <Add more as needed, or "None" if no notable lessons>

Guidelines:
- Be concise but informative
- Focus on decisions that would be useful for future similar tasks
- Lessons should be actionable insights, not just observations
- If the log is unclear or minimal, extract what you can and note uncertainty
- Use "None" for DECISIONS or LESSONS if nothing notable"""


def _parse_extraction_response(response: str) -> InsightExtraction:
    """Parse Claude's response into an InsightExtraction.

    Args:
        response: Raw output from Claude CLI.

    Returns:
        InsightExtraction parsed from the response.
    """
    # Extract APPROACH section
    approach_match = re.search(
        r"APPROACH:\s*\n?(.*?)(?=\nDECISIONS:|\Z)", response, re.IGNORECASE | re.DOTALL
    )
    approach = approach_match.group(1).strip() if approach_match else ""

    # Extract DECISIONS section
    decisions_match = re.search(
        r"DECISIONS:\s*\n?(.*?)(?=\nLESSONS:|\Z)", response, re.IGNORECASE | re.DOTALL
    )
    decisions_text = decisions_match.group(1).strip() if decisions_match else ""
    decisions = _parse_bullet_list(decisions_text)

    # Extract LESSONS section
    lessons_match = re.search(r"LESSONS:\s*\n?(.*?)(?=\Z)", response, re.IGNORECASE | re.DOTALL)
    lessons_text = lessons_match.group(1).strip() if lessons_match else ""
    lessons = _parse_bullet_list(lessons_text)

    return InsightExtraction(
        approach=approach,
        decisions=decisions,
        lessons_learned=lessons,
        success=True,
        model_used="haiku",
    )


def _parse_bullet_list(text: str) -> list[str]:
    """Parse a bullet-point list into individual items.

    Args:
        text: Text containing bullet points.

    Returns:
        List of bullet items (empty if none or "None").
    """
    if not text or text.strip().lower() == "none":
        return []

    items = []
    for line in text.split("\n"):
        # Strip bullet markers (-, *, •, numbers)
        cleaned = re.sub(r"^\s*[-*•]\s*", "", line)
        cleaned = re.sub(r"^\s*\d+[.)]\s*", "", cleaned)
        cleaned = cleaned.strip()

        if cleaned and cleaned.lower() != "none":
            items.append(cleaned)

    return items


def _truncate_log(log: str, max_chars: int = 50000) -> str:
    """Truncate a log to stay within context limits.

    Keeps the beginning and end of the log, which typically contain
    the most relevant information (setup and final results).

    Args:
        log: The full log text.
        max_chars: Maximum characters to keep.

    Returns:
        Truncated log with indicator if truncated.
    """
    if len(log) <= max_chars:
        return log

    # Keep first 60% and last 40%
    first_portion = int(max_chars * 0.6)
    last_portion = max_chars - first_portion - 100  # Reserve space for truncation notice

    return (
        log[:first_portion]
        + "\n\n... [LOG TRUNCATED - middle portion removed] ...\n\n"
        + log[-last_portion:]
    )


def _fallback_extraction(harness_log: str, task: Task, error: str) -> InsightExtraction:
    """Generate a fallback extraction when LLM is unavailable.

    Attempts basic heuristic extraction from the log.

    Args:
        harness_log: The harness execution log.
        task: The task that was executed.
        error: Error message describing why extraction failed.

    Returns:
        InsightExtraction with basic data and error flag.
    """
    # Try to extract a basic approach from the log
    approach = _extract_basic_approach(harness_log, task)

    return InsightExtraction(
        approach=approach,
        decisions=[],
        lessons_learned=[],
        success=False,
        error=error,
        model_used="fallback",
        tokens_used=0,
    )


def _extract_basic_approach(harness_log: str, task: Task) -> str:
    """Extract a basic approach description without LLM.

    Args:
        harness_log: The harness execution log.
        task: The task that was executed.

    Returns:
        Simple approach description.
    """
    # Look for common patterns in logs that indicate what was done
    patterns = [
        (r"(?:created|wrote|added)\s+(?:file|files?)\s+[`'\"]?(\S+)", "Created files"),
        (r"(?:modified|updated|changed)\s+(?:file|files?)", "Modified existing files"),
        (r"(?:ran|running)\s+(?:tests?|pytest|jest)", "Ran tests"),
        (r"(?:fixed|resolved)\s+(?:bug|issue|error)", "Fixed bugs"),
        (r"(?:refactored?|restructured?)", "Refactored code"),
        (r"(?:implemented|added)\s+(\w+)", "Implemented functionality"),
    ]

    actions = []
    log_lower = harness_log.lower()

    for pattern, description in patterns:
        if re.search(pattern, log_lower):
            if description not in actions:
                actions.append(description)

    if actions:
        return f"Task '{task.title}': {', '.join(actions[:3])}"

    return f"Completed task: {task.title}"
