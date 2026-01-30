"""
Route compiler - Normalize and aggregate command usage patterns.

This module processes raw command logs from Claude Code hook events,
normalizes them to extract semantic patterns, aggregates by frequency,
and compiles them into a shareable markdown file for team learning.
"""

import json
import re
from collections import Counter
from pathlib import Path


def normalize_command(command: str) -> str:
    """
    Normalize a command by stripping task IDs, file paths, and other variable content.

    This extracts the semantic pattern of the command, making it suitable
    for frequency aggregation across different task contexts.

    Normalization rules:
    1. Strip task IDs (e.g., cub-a3r.2, TASK-123)
    2. Replace file paths with placeholders
    3. Strip quoted strings (commit messages, etc.)
    4. Strip numeric arguments
    5. Preserve command structure and flags

    Args:
        command: Raw command string

    Returns:
        Normalized command pattern

    Examples:
        >>> normalize_command("cub run --task cub-a3r.2")
        'cub run --task <TASK_ID>'
        >>> normalize_command("git commit -m 'Fix bug in auth.py'")
        'git commit -m <MESSAGE>'
        >>> normalize_command("bd close cub-123 -r 'Done'")
        'bd close <TASK_ID> -r <MESSAGE>'
    """
    # Strip leading/trailing whitespace
    cmd = command.strip()

    # Replace URLs first (before path replacement)
    cmd = re.sub(r'https?://\S+', '<URL>', cmd)

    # Replace quoted strings (single or double quotes)
    # This handles commit messages, reasons, etc.
    # Do this before task ID replacement so task IDs in quotes get normalized
    cmd = re.sub(r'"[^"]*"', '<MESSAGE>', cmd)
    cmd = re.sub(r"'[^']*'", '<MESSAGE>', cmd)

    # Replace task IDs (common patterns: cub-123, cub-a3r.2, TASK-123, etc.)
    # Match: word-alphanumeric(dot alphanumeric)*
    cmd = re.sub(r'\b[a-zA-Z]+-[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*\b', '<TASK_ID>', cmd)

    # Replace file paths (absolute or relative)
    # Match paths with / or \ separators
    cmd = re.sub(r'\S+/\S+', '<PATH>', cmd)
    cmd = re.sub(r'\S+\\\S+', '<PATH>', cmd)

    # Replace standalone numbers (but preserve flags like -1, --timeout=30)
    cmd = re.sub(r'\s+\d+\s+', ' <NUM> ', cmd)
    cmd = re.sub(r'\s+\d+$', ' <NUM>', cmd)

    # Clean up multiple spaces
    cmd = re.sub(r'\s+', ' ', cmd).strip()

    return cmd


def compile_routes(
    log_file: Path,
    min_frequency: int = 3,
) -> list[tuple[str, int]]:
    """
    Compile routes from raw command log.

    Reads the JSONL log file, normalizes each command, aggregates by frequency,
    and filters out commands with frequency below the threshold.

    Args:
        log_file: Path to route-log.jsonl
        min_frequency: Minimum occurrence count to include (default: 3)

    Returns:
        List of (normalized_command, count) tuples, sorted by frequency descending

    Raises:
        FileNotFoundError: If log file doesn't exist
    """
    if not log_file.exists():
        raise FileNotFoundError(f"Route log file not found: {log_file}")

    # Parse JSONL and extract commands
    commands: list[str] = []
    with open(log_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if 'command' in entry:
                    commands.append(entry['command'])
            except json.JSONDecodeError:
                # Skip malformed lines
                continue

    # Normalize and aggregate
    normalized = [normalize_command(cmd) for cmd in commands]
    counts = Counter(normalized)

    # Filter by frequency and sort
    filtered = [(cmd, count) for cmd, count in counts.items() if count >= min_frequency]
    filtered.sort(key=lambda x: x[1], reverse=True)

    return filtered


def render_learned_routes(routes: list[tuple[str, int]]) -> str:
    """
    Render learned routes as a markdown table.

    Args:
        routes: List of (normalized_command, count) tuples

    Returns:
        Markdown-formatted table string
    """
    if not routes:
        return "# Learned Routes\n\nNo routes found (all commands below frequency threshold).\n"

    lines = [
        "# Learned Routes",
        "",
        "This file contains frequently-used command patterns learned from team usage.",
        "Commands are normalized (task IDs, paths, and messages replaced with placeholders).",
        "",
        "| Command | Frequency |",
        "|---------|-----------|",
    ]

    for cmd, count in routes:
        # Escape pipe characters in commands for markdown table
        escaped_cmd = cmd.replace('|', '\\|')
        lines.append(f"| `{escaped_cmd}` | {count} |")

    lines.append("")
    return "\n".join(lines)


def compile_and_write_routes(
    log_file: Path,
    output_file: Path,
    min_frequency: int = 3,
) -> None:
    """
    Compile routes and write to markdown file.

    This is the main entry point called by the Stop hook.

    Args:
        log_file: Path to route-log.jsonl
        output_file: Path to .cub/learned-routes.md
        min_frequency: Minimum occurrence count to include
    """
    routes = compile_routes(log_file, min_frequency)
    markdown = render_learned_routes(routes)

    # Ensure parent directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write to file
    with open(output_file, 'w') as f:
        f.write(markdown)
