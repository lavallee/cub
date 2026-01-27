#!/usr/bin/env python3
"""
Claude Code statusline for cub projects.

Reads Claude's session JSON from stdin and augments it with cub project
state: task counts by status, active run info, and workflow stage summary.

Configured in .claude/settings.json:
    { "statusLine": { "type": "command", "command": "python3 scripts/statusline.py" } }
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

# Type alias for the JSON dicts we pass around
JsonDict = dict[str, Any]


def read_claude_input() -> JsonDict:
    """Read Claude Code's JSON payload from stdin."""
    try:
        result: JsonDict = json.load(sys.stdin)
        return result
    except (json.JSONDecodeError, ValueError):
        return {}


def find_project_dir(data: JsonDict) -> Path:
    """Determine the project directory from Claude's input or cwd."""
    workspace = data.get("workspace", {})
    project_dir = workspace.get("project_dir") or workspace.get("current_dir") or os.getcwd()
    return Path(project_dir)


def get_task_counts(project_dir: Path) -> dict[str, int]:
    """Parse .beads/issues.jsonl for task counts by status."""
    counts: dict[str, int] = {"open": 0, "in_progress": 0, "closed": 0}
    issues_file = project_dir / ".beads" / "issues.jsonl"

    if not issues_file.exists():
        return counts

    try:
        with open(issues_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    issue = json.loads(line)
                    status = issue.get("status", "").lower()
                    if status in counts:
                        counts[status] += 1
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass

    return counts


def get_active_run(project_dir: Path) -> JsonDict | None:
    """Find the most recent active run's status.json."""
    runs_dir = project_dir / ".cub" / "runs"
    if not runs_dir.exists():
        return None

    # Find status.json files, sorted by mtime descending
    status_files: list[tuple[float, Path]] = []
    try:
        for run_dir in runs_dir.iterdir():
            status_file = run_dir / "status.json"
            if status_file.exists() and status_file.stat().st_size > 0:
                status_files.append((status_file.stat().st_mtime, status_file))
    except OSError:
        return None

    if not status_files:
        return None

    # Read most recent
    status_files.sort(reverse=True)
    try:
        with open(status_files[0][1]) as f:
            run_data: JsonDict = json.load(f)
            phase = run_data.get("phase", "").lower()
            if phase in ("running", "initializing"):
                return run_data
    except (json.JSONDecodeError, OSError):
        pass

    return None


def format_statusline(data: JsonDict) -> str:
    """Build the statusline string."""
    parts: list[str] = []

    # Model name
    model = data.get("model", {}).get("display_name", "")
    if model:
        parts.append(f"\033[1;34m{model}\033[0m")

    # Project dir (short name)
    project_dir = find_project_dir(data)
    project_name = project_dir.name
    if project_name:
        parts.append(f"\033[0;36m{project_name}\033[0m")

    # Task counts from beads
    counts = get_task_counts(project_dir)
    total = sum(counts.values())
    if total > 0:
        open_n = counts["open"]
        doing_n = counts["in_progress"]
        done_n = counts["closed"]
        # Color: open=yellow, doing=blue, done=green
        task_str = (
            f"\033[1;33m{open_n}\033[0m/"
            f"\033[1;34m{doing_n}\033[0m/"
            f"\033[1;32m{done_n}\033[0m"
        )
        parts.append(task_str)

    # Active run info
    run = get_active_run(project_dir)
    if run:
        task_title = run.get("current_task_title", "")
        task_id = run.get("current_task_id", "")
        phase = run.get("phase", "")
        iteration = run.get("iteration", {})
        current_iter = iteration.get("current", 0)
        max_iter = iteration.get("max", 0)

        if task_id:
            run_str = f"\033[1;35m{task_id}\033[0m"
            if current_iter and max_iter:
                run_str += f" ({current_iter}/{max_iter})"
            parts.append(run_str)
        elif phase:
            parts.append(f"\033[1;35m{phase}\033[0m")

        # Budget
        budget = run.get("budget", {})
        cost = budget.get("cost_usd", 0)
        if cost and cost > 0:
            cost_color = "\033[1;31m" if budget.get("is_over_budget") else "\033[0;33m"
            parts.append(f"{cost_color}${cost:.2f}\033[0m")

    # Context window from Claude's data
    ctx = data.get("context_window", {})
    used_pct = ctx.get("used_percentage", 0)
    if used_pct > 0:
        if used_pct >= 80:
            ctx_color = "\033[1;31m"
        elif used_pct >= 60:
            ctx_color = "\033[1;33m"
        else:
            ctx_color = "\033[0;32m"
        parts.append(f"ctx:{ctx_color}{used_pct:.0f}%\033[0m")

    # Session cost from Claude's data
    claude_cost = data.get("cost", {}).get("total_cost_usd", 0)
    if claude_cost > 0 and not run:
        parts.append(f"\033[0;33m${claude_cost:.2f}\033[0m")

    return " | ".join(parts) if parts else "cub"


def main() -> None:
    data = read_claude_input()
    print(format_statusline(data))


if __name__ == "__main__":
    main()
