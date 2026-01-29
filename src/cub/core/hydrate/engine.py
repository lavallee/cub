"""
Core hydration engine.

Calls Claude to expand unstructured text into structured output with
title, context, implementation steps, and acceptance criteria.

Supports streaming, debug output, and per-item progress callbacks.
"""

import re
import subprocess
from collections.abc import Callable

from cub.core.hydrate.models import HydrationResult, HydrationStatus

# Default timeout for Claude CLI calls (seconds)
CLAUDE_TIMEOUT = 60

# Type aliases for callbacks
OnStartCallback = Callable[[int, int, str], None]
OnCompleteCallback = Callable[[int, int, HydrationResult], None]
StreamCallback = Callable[[str], None]
DebugCallback = Callable[[str], None]


def hydrate(
    text: str,
    prompt_template: str | None = None,
    timeout: int = CLAUDE_TIMEOUT,
    stream: bool = False,
    debug: bool = False,
    stream_callback: StreamCallback | None = None,
    debug_callback: DebugCallback | None = None,
) -> HydrationResult:
    """
    Hydrate a single text item using Claude.

    Args:
        text: The raw text to hydrate.
        prompt_template: Custom prompt template. If provided, {text} is replaced
            with the input text. If None, uses the default prompt.
        timeout: Timeout in seconds for the Claude CLI call.
        stream: If True, stream stdout line-by-line via stream_callback.
        debug: If True, emit debug info via debug_callback.
        stream_callback: Called with each line when streaming.
        debug_callback: Called with debug messages.

    Returns:
        HydrationResult with structured output.
    """
    prompt = _build_prompt(text, prompt_template)

    if debug and debug_callback:
        debug_callback(f"[hydrate] prompt:\n{prompt}")

    try:
        if stream and stream_callback:
            output = _run_streaming(prompt, timeout, stream_callback, debug_callback)
        else:
            output = _run_captured(prompt, timeout)

        if output is None:
            return _fallback(text)

        if debug and debug_callback:
            debug_callback(f"[hydrate] raw response:\n{output}")

        result = _parse_response(output, text)

        if debug and debug_callback:
            debug_callback(f"[hydrate] parsed: status={result.status.value} title={result.title!r}")

        return result

    except subprocess.TimeoutExpired:
        return _fallback(text)
    except FileNotFoundError:
        return _fallback(text)
    except OSError:
        return _fallback(text)


def hydrate_batch(
    texts: list[str],
    prompt_template: str | None = None,
    timeout: int = CLAUDE_TIMEOUT,
    stream: bool = False,
    debug: bool = False,
    stream_callback: StreamCallback | None = None,
    debug_callback: DebugCallback | None = None,
    on_start: OnStartCallback | None = None,
    on_complete: OnCompleteCallback | None = None,
) -> list[HydrationResult]:
    """
    Hydrate multiple text items with per-item callbacks.

    Args:
        texts: List of raw text items to hydrate.
        prompt_template: Custom prompt template (see hydrate()).
        timeout: Timeout per item.
        stream: If True, stream each item's output.
        debug: If True, emit debug info.
        stream_callback: Called with each line when streaming.
        debug_callback: Called with debug messages.
        on_start: Called before each item with (index, total, source_text).
        on_complete: Called after each item with (index, total, result).

    Returns:
        List of HydrationResult objects.
    """
    total = len(texts)
    results: list[HydrationResult] = []

    for i, text in enumerate(texts):
        if on_start:
            on_start(i, total, text)

        result = hydrate(
            text,
            prompt_template=prompt_template,
            timeout=timeout,
            stream=stream,
            debug=debug,
            stream_callback=stream_callback,
            debug_callback=debug_callback,
        )
        results.append(result)

        if on_complete:
            on_complete(i, total, result)

    return results


def _build_prompt(text: str, template: str | None) -> str:
    """Build the prompt for Claude."""
    if template:
        return template.replace("{text}", text)

    return f"""Given this bug/feature request, generate a structured task description.

Request:
{text}

Respond in this exact format (preserve these exact labels):
TITLE: <concise title, 50 chars max, imperative mood like "Fix X" or "Add Y">
CONTEXT: <one paragraph explaining the problem/feature and why it matters>
STEPS:
1. <implementation step>
2. <implementation step>
CRITERIA:
- [ ] <acceptance criterion>
- [ ] <acceptance criterion>"""


def _run_captured(prompt: str, timeout: int) -> str | None:
    """Run Claude with captured output."""
    result = subprocess.run(
        ["claude", "--model", "haiku", "--print", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _run_streaming(
    prompt: str,
    timeout: int,
    stream_callback: StreamCallback,
    debug_callback: DebugCallback | None,
) -> str | None:
    """Run Claude with line-by-line streaming."""
    cmd = ["claude", "--model", "haiku", "--print", "-p", prompt]

    if debug_callback:
        debug_callback(f"[hydrate] command: {' '.join(cmd)}")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    lines: list[str] = []
    try:
        assert proc.stdout is not None  # for mypy
        for line in proc.stdout:
            lines.append(line)
            stream_callback(line)

        proc.wait(timeout=timeout)

        if proc.returncode != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            if debug_callback:
                debug_callback(f"[hydrate] claude exited {proc.returncode}: {stderr}")
            return None

        return "".join(lines)

    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return None


def _parse_response(response: str, source_text: str) -> HydrationResult:
    """Parse Claude's structured response into a HydrationResult."""
    # Extract TITLE
    title_match = re.search(r"TITLE:\s*(.+?)(?:\n|$)", response, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else ""

    # Extract CONTEXT (single paragraph, up to STEPS or end)
    context_match = re.search(
        r"CONTEXT:\s*(.+?)(?=\nSTEPS:|\nCRITERIA:|\Z)",
        response,
        re.IGNORECASE | re.DOTALL,
    )
    context = context_match.group(1).strip() if context_match else ""

    # Extract STEPS (numbered list)
    steps: list[str] = []
    steps_match = re.search(
        r"STEPS:\s*\n((?:\d+\..+\n?)+)",
        response,
        re.IGNORECASE,
    )
    if steps_match:
        for line in steps_match.group(1).strip().split("\n"):
            step = re.sub(r"^\d+\.\s*", "", line.strip())
            if step:
                steps.append(step)

    # Extract CRITERIA (checklist)
    criteria: list[str] = []
    criteria_match = re.search(
        r"CRITERIA:\s*\n((?:[-*]\s*\[.\].+\n?)+)",
        response,
        re.IGNORECASE,
    )
    if criteria_match:
        for line in criteria_match.group(1).strip().split("\n"):
            criterion = re.sub(r"^[-*]\s*\[.\]\s*", "", line.strip())
            if criterion:
                criteria.append(criterion)

    # Validate minimum: title is required
    if not title:
        return _fallback(source_text)

    # If no context, try legacy DESCRIPTION field
    if not context:
        desc_match = re.search(
            r"DESCRIPTION:\s*(.+)",
            response,
            re.IGNORECASE | re.DOTALL,
        )
        context = desc_match.group(1).strip() if desc_match else ""

    # If still no context, fallback
    if not context:
        return _fallback(source_text)

    return HydrationResult(
        title=title[:100],
        description=context.split("\n")[0] if context else "",
        context=context,
        implementation_steps=steps,
        acceptance_criteria=criteria,
        status=HydrationStatus.SUCCESS,
        source_text=source_text,
    )


def _fallback(text: str) -> HydrationResult:
    """Generate a basic hydration without AI."""
    lines = text.strip().split("\n")
    first_line = lines[0].strip()

    # Create title from first line
    if len(first_line) <= 50:
        title = first_line
    else:
        title = first_line[:47]
        if " " in title:
            title = title.rsplit(" ", 1)[0]
        title += "..."

    return HydrationResult(
        title=title,
        description=text.strip(),
        context=text.strip(),
        implementation_steps=[],
        acceptance_criteria=[],
        status=HydrationStatus.FALLBACK,
        source_text=text,
    )
