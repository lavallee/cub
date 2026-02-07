"""
Claude Code invocation for cub plan stages.

This module provides utilities for invoking Claude Code with command templates
to perform the actual planning work (orient, architect, itemize).

The stages use Claude Code's slash command system with templates from
templates/commands/cub:*.md to conduct interactive interviews and generate
high-quality planning artifacts.

Example:
    >>> from cub.core.plan.claude import invoke_claude_command
    >>> result = invoke_claude_command(
    ...     command="cub:orient",
    ...     args="specs/researching/my-feature.md",
    ...     output_path=Path("plans/my-feature/orientation.md"),
    ... )
    >>> result.success
    True
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class ClaudeResult:
    """Result of a Claude Code invocation."""

    success: bool
    output_path: Path | None
    output_content: str | None
    error: str | None
    needs_human_input: bool = False
    human_input_questions: list[str] | None = None


class ClaudeNotFoundError(Exception):
    """Raised when Claude Code CLI is not found."""

    pass


class ClaudeInvocationError(Exception):
    """Raised when Claude Code invocation fails."""

    pass


def find_claude() -> str:
    """
    Find the Claude Code CLI executable.

    Returns:
        Path to the claude executable.

    Raises:
        ClaudeNotFoundError: If claude is not found.
    """
    claude_path = shutil.which("claude")
    if claude_path is None:
        raise ClaudeNotFoundError(
            "Claude Code CLI not found. "
            "Install from: https://docs.anthropic.com/en/docs/claude-code"
        )
    return claude_path


def invoke_claude_command(
    command: str,
    args: str = "",
    working_dir: Path | None = None,
    output_path: Path | None = None,
    timeout: int | None = None,
    non_interactive: bool = False,
    non_interactive_prompt: str | None = None,
) -> ClaudeResult:
    """
    Invoke a Claude Code slash command.

    This function invokes Claude Code with a slash command (e.g., /cub:orient)
    and waits for the session to complete.

    Args:
        command: The slash command to invoke (e.g., "cub:orient").
        args: Arguments to pass to the command.
        working_dir: Working directory for the command.
        output_path: Expected output file path (for verification).
        timeout: Timeout in seconds (None for no timeout).
        non_interactive: If True, use claude -p for non-interactive mode.
        non_interactive_prompt: Custom prompt for non-interactive mode.

    Returns:
        ClaudeResult with success status and output information.

    Raises:
        ClaudeNotFoundError: If claude CLI is not found.
        ClaudeInvocationError: If invocation fails unexpectedly.
    """
    claude_path = find_claude()
    working_dir = working_dir or Path.cwd()

    if non_interactive:
        return _invoke_non_interactive(
            claude_path=claude_path,
            command=command,
            args=args,
            working_dir=working_dir,
            output_path=output_path,
            timeout=timeout,
            custom_prompt=non_interactive_prompt,
        )
    else:
        return _invoke_interactive(
            claude_path=claude_path,
            command=command,
            args=args,
            working_dir=working_dir,
            output_path=output_path,
            timeout=timeout,
        )


def _invoke_interactive(
    claude_path: str,
    command: str,
    args: str,
    working_dir: Path,
    output_path: Path | None,
    timeout: int | None,
) -> ClaudeResult:
    """
    Invoke Claude Code in interactive mode.

    This launches an interactive Claude session with the slash command.
    The user interacts with Claude until the session ends.
    """
    # Build the command string
    full_command = f"/{command}"
    if args:
        full_command = f"{full_command} {args}"

    # Build subprocess command
    cmd = [
        claude_path,
        "--dangerously-skip-permissions",
        full_command,
    ]

    try:
        # Run interactively - inherit stdio for user interaction
        subprocess.run(
            cmd,
            cwd=working_dir,
            timeout=timeout,
            # Let the user interact with Claude
            stdin=None,
            stdout=None,
            stderr=None,
        )

        # Check if output file was created
        if output_path and output_path.exists():
            content = output_path.read_text(encoding="utf-8")

            # Check for "Needs Human Input" section
            needs_human = "## Needs Human Input" in content
            questions = None
            if needs_human:
                questions = _extract_human_input_questions(content)

            return ClaudeResult(
                success=not needs_human,
                output_path=output_path,
                output_content=content,
                error=None,
                needs_human_input=needs_human,
                human_input_questions=questions,
            )
        else:
            # Output file not created - session may have been interrupted
            return ClaudeResult(
                success=False,
                output_path=None,
                output_content=None,
                error="Output file not created. Session may have been interrupted.",
            )

    except subprocess.TimeoutExpired:
        return ClaudeResult(
            success=False,
            output_path=None,
            output_content=None,
            error=f"Claude session timed out after {timeout} seconds.",
        )
    except Exception as e:
        return ClaudeResult(
            success=False,
            output_path=None,
            output_content=None,
            error=f"Claude invocation failed: {e}",
        )


def _invoke_non_interactive(
    claude_path: str,
    command: str,
    args: str,
    working_dir: Path,
    output_path: Path | None,
    timeout: int | None,
    custom_prompt: str | None,
) -> ClaudeResult:
    """
    Invoke Claude Code in non-interactive mode using claude -p.

    This uses claude's prompt mode to generate output without user interaction.
    Best-effort mode that makes assumptions when details are missing.
    """
    # Build the prompt
    if custom_prompt:
        prompt = custom_prompt
    else:
        prompt = _build_non_interactive_prompt(command, args, output_path)

    cmd = [
        claude_path,
        "-p",
        prompt,
    ]

    try:
        # Capture output
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            timeout=timeout,
            capture_output=True,
            text=True,
            env={**os.environ, "NO_COLOR": "1"},
        )

        # Strip ANSI escape codes from output
        output = _strip_ansi(result.stdout)

        # For non-interactive mode, we need to write the output to the file
        # since claude -p just prints to stdout
        if output_path and output:
            # Try to extract markdown content from the output
            content = _extract_markdown_content(output)
            if content:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(content, encoding="utf-8")

                # Check for "Needs Human Input" section
                needs_human = "## Needs Human Input" in content
                questions = None
                if needs_human:
                    questions = _extract_human_input_questions(content)

                return ClaudeResult(
                    success=not needs_human,
                    output_path=output_path,
                    output_content=content,
                    error=None,
                    needs_human_input=needs_human,
                    human_input_questions=questions,
                )

        return ClaudeResult(
            success=False,
            output_path=None,
            output_content=output,
            error="Failed to extract valid output from Claude response.",
        )

    except subprocess.TimeoutExpired:
        return ClaudeResult(
            success=False,
            output_path=None,
            output_content=None,
            error=f"Claude session timed out after {timeout} seconds.",
        )
    except Exception as e:
        return ClaudeResult(
            success=False,
            output_path=None,
            output_content=None,
            error=f"Claude invocation failed: {e}",
        )


def _build_non_interactive_prompt(
    command: str,
    args: str,
    output_path: Path | None,
) -> str:
    """Build a non-interactive prompt based on the command type."""
    if command == "cub:orient":
        return _build_orient_prompt(args, output_path)
    elif command == "cub:architect":
        return _build_architect_prompt(args, output_path)
    elif command == "cub:itemize":
        return _build_itemize_prompt(args, output_path)
    else:
        return f"Run the /{command} command with args: {args}"


def _build_orient_prompt(args: str, output_path: Path | None) -> str:
    """Build non-interactive orient prompt."""
    spec_path = args.strip() if args else None
    spec_content = ""
    if spec_path:
        try:
            spec_content = Path(spec_path).read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            pass

    return f"""You are Cub's Orient Agent conducting requirements refinement.

You will produce an ORIENTATION document from the input spec.

Rules:
- Make best-effort assumptions when details are missing.
- If blocked on critical missing info, add a section '## Needs Human Input' with 1-5 specific questions.
- Output MUST be valid Markdown. Do not wrap in code fences.
- Output ONLY the document content (no preamble, no explanations).

Output an orientation document with these sections:
- ## Executive Summary
- ## Problem Statement
- ## Refined Vision
- ## Requirements (### P0 - Must Have, ### P1 - Should Have, ### P2 - Nice to Have)
- ## Constraints
- ## Assumptions
- ## Open Questions / Experiments
- ## Out of Scope
- ## Risks (table: Risk | Impact | Mitigation)
- ## MVP Definition
- ## Needs Human Input (only if blocked)

INPUT SPEC:
---
{spec_content or 'No spec content provided. Make best-effort assumptions.'}
---
"""


def _build_architect_prompt(args: str, output_path: Path | None) -> str:
    """Build non-interactive architect prompt."""
    # Try to find and read orientation.md
    plan_slug = args.strip() if args else None
    orientation_content = ""
    if plan_slug:
        orient_path = Path("plans") / plan_slug / "orientation.md"
        if orient_path.exists():
            orientation_content = orient_path.read_text(encoding="utf-8")

    return f"""You are Cub's Architect Agent designing technical architecture.

You will produce a TECHNICAL ARCHITECTURE document based on the orientation.

Rules:
- Make best-effort assumptions when details are missing.
- Use MVP mindset and team scale by default.
- If blocked on a critical decision, add a section '## Needs Human Input' with 1-5 specific questions.
- Output MUST be valid Markdown. Do not wrap in code fences.
- Output ONLY the document content (no preamble, no explanations).

Output an architecture document with these sections:
- ## Technical Summary
- ## Technology Stack (table: Layer | Choice | Rationale)
- ## System Architecture (with ASCII diagram)
- ## Components (### Component Name with Purpose, Responsibilities, Dependencies, Interface)
- ## Data Model
- ## APIs / Interfaces
- ## Implementation Phases (### Phase N: Name with Goal and high-level tasks)
- ## Technical Risks (table: Risk | Impact | Likelihood | Mitigation)
- ## Dependencies (### External, ### Internal)
- ## Security Considerations
- ## Future Considerations
- ## Needs Human Input (only if blocked)

ORIENTATION INPUT:
---
{orientation_content or 'No orientation content found. Make best-effort assumptions.'}
---
"""


def _build_itemize_prompt(args: str, output_path: Path | None) -> str:
    """Build non-interactive itemize prompt."""
    plan_slug = args.strip() if args else None
    orientation_content = ""
    architecture_content = ""

    if plan_slug:
        orient_path = Path("plans") / plan_slug / "orientation.md"
        arch_path = Path("plans") / plan_slug / "architecture.md"
        if orient_path.exists():
            orientation_content = orient_path.read_text(encoding="utf-8")
        if arch_path.exists():
            architecture_content = arch_path.read_text(encoding="utf-8")

    return f"""You are Cub's Itemizer Agent breaking architecture into executable tasks.

You will produce an ITEMIZED PLAN document.

Rules:
- Use Micro granularity (15-30 minute tasks, optimal for AI agents).
- Make best-effort assumptions when details are missing.
- Output MUST be valid Markdown following the exact format below.
- Output ONLY the document content (no preamble, no explanations).

Format requirements:
- Start with '# Itemized Plan: {{title}}'
- Epic sections: '## Epic: {{id}} - {{title}}'
- Task sections: '### Task: {{id}} - {{title}}'
- Each epic and task MUST include these metadata lines:
  Priority: {{integer 0-3}}
  Labels: comma,separated,labels
  Description:
  {{freeform markdown}}
- Tasks may include: Blocks: comma,separated,task_ids

Required labels for each task:
- Phase label: phase-1, phase-2, etc.
- Model label: model:opus, model:sonnet, or model:haiku
- Complexity label: complexity:high, complexity:medium, or complexity:low

Epic IDs: E01, E02, etc.
Task IDs: 001, 002, etc. (sequential)

ORIENTATION:
---
{orientation_content or 'No orientation found.'}
---

ARCHITECTURE:
---
{architecture_content or 'No architecture found.'}
---
"""


def _strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
    return ansi_pattern.sub("", text).replace("\r", "")


def _extract_markdown_content(output: str) -> str | None:
    """
    Extract markdown content from Claude's output.

    Claude may include preamble or explanatory text. This tries to
    extract just the markdown document content.
    """
    # If output starts with # heading, it's probably the document
    lines = output.strip().split("\n")
    if lines and lines[0].startswith("#"):
        return output.strip()

    # Look for content between markdown code fences
    fence_match = re.search(r"```markdown\s*([\s\S]*?)\s*```", output)
    if fence_match:
        return fence_match.group(1).strip()

    # Look for first heading and take everything from there
    heading_match = re.search(r"(^|\n)(# .+[\s\S]*)", output)
    if heading_match:
        return heading_match.group(2).strip()

    # Return original if no patterns matched
    return output.strip() if output.strip() else None


def _extract_human_input_questions(content: str) -> list[str]:
    """Extract questions from the Needs Human Input section."""
    questions = []

    # Find the Needs Human Input section
    match = re.search(
        r"## Needs Human Input\s*([\s\S]*?)(?=\n## |\Z)",
        content,
        re.IGNORECASE,
    )
    if match:
        section = match.group(1)
        # Extract numbered or bulleted questions
        question_matches = re.findall(r"^[\d\-\*]+\.?\s*(.+)$", section, re.MULTILINE)
        questions = [q.strip() for q in question_matches if q.strip()]

    return questions


def check_command_installed(command: str) -> bool:
    """
    Check if a Claude Code command template is installed.

    Args:
        command: Command name (e.g., "cub:orient").

    Returns:
        True if the command template exists.
    """
    command_file = Path(".claude/commands") / f"{command}.md"
    return command_file.exists()


def ensure_commands_installed(project_root: Path) -> list[str]:
    """
    Ensure Claude Code command templates are installed.

    Checks for required command templates and returns a list of missing ones.

    Args:
        project_root: Project root directory.

    Returns:
        List of missing command names.
    """
    required_commands = ["cub:orient", "cub:architect", "cub:itemize"]
    missing = []

    commands_dir = project_root / ".claude" / "commands"
    for cmd in required_commands:
        if not (commands_dir / f"{cmd}.md").exists():
            missing.append(cmd)

    return missing
