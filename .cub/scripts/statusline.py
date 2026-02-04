#!/usr/bin/env python3
# cub-script-version: 1
"""Claude Code statusline for cub projects (managed by cub init/update)."""

import json
import os
import sys
from pathlib import Path

def main():
    # Read Claude Code JSON from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}

    workspace = data.get("workspace", {})
    project_dir = Path(
        workspace.get("project_dir")
        or workspace.get("current_dir")
        or os.getcwd()
    )

    parts = []

    # Model name (blue)
    model = data.get("model", {}).get("display_name", "")
    if model:
        parts.append(f"\033[1;34m{model}\033[0m")

    # Project name (cyan)
    parts.append(f"\033[0;36m{project_dir.name}\033[0m")

    # Task counts (open/doing/done) - detect backend
    # Detection order: .beads/ directory (beads), then .cub/tasks.jsonl (jsonl)
    beads_file = project_dir / ".beads" / "issues.jsonl"
    jsonl_file = project_dir / ".cub" / "tasks.jsonl"

    tasks_file = None
    if beads_file.exists():
        tasks_file = beads_file
    elif jsonl_file.exists():
        tasks_file = jsonl_file

    counts = {"open": 0, "in_progress": 0, "closed": 0}
    if tasks_file:
        try:
            for line in open(tasks_file):
                line = line.strip()
                if not line:
                    continue
                try:
                    status = json.loads(line).get("status", "").lower()
                    if status in counts:
                        counts[status] += 1
                except json.JSONDecodeError:
                    pass
        except OSError:
            pass

    if sum(counts.values()) > 0:
        parts.append(
            f"\033[1;33m{counts['open']}\033[0m/"
            f"\033[1;34m{counts['in_progress']}\033[0m/"
            f"\033[1;32m{counts['closed']}\033[0m"
        )

    # Active run info
    runs_dir = project_dir / ".cub" / "runs"
    if runs_dir.exists():
        status_files = []
        try:
            for rd in runs_dir.iterdir():
                sf = rd / "status.json"
                if sf.exists() and sf.stat().st_size > 0:
                    status_files.append((sf.stat().st_mtime, sf))
        except OSError:
            pass

        if status_files:
            status_files.sort(reverse=True)
            try:
                with open(status_files[0][1]) as f:
                    run = json.load(f)
                    phase = run.get("phase", "").lower()
                    if phase in ("running", "initializing"):
                        tid = run.get("current_task_id", "")
                        it = run.get("iteration", {})
                        cur, mx = it.get("current", 0), it.get("max", 0)
                        if tid:
                            s = f"\033[1;35m{tid}\033[0m"
                            if cur and mx:
                                s += f" ({cur}/{mx})"
                            parts.append(s)
                        elif phase:
                            parts.append(f"\033[1;35m{phase}\033[0m")

                        budget = run.get("budget", {})
                        cost = budget.get("cost_usd", 0)
                        if cost and cost > 0:
                            c = "\033[1;31m" if budget.get("is_over_budget") else "\033[0;33m"
                            parts.append(f"{c}${cost:.2f}\033[0m")
            except (json.JSONDecodeError, OSError):
                pass

    # Context window (green/yellow/red)
    used_pct = data.get("context_window", {}).get("used_percentage", 0)
    if used_pct > 0:
        c = "\033[1;31m" if used_pct >= 80 else "\033[1;33m" if used_pct >= 60 else "\033[0;32m"
        parts.append(f"ctx:{c}{used_pct:.0f}%\033[0m")

    # Session cost (when no active run)
    claude_cost = data.get("cost", {}).get("total_cost_usd", 0)
    if claude_cost > 0 and not runs_dir.exists():
        parts.append(f"\033[0;33m${claude_cost:.2f}\033[0m")

    print(" | ".join(parts) if parts else "cub")


if __name__ == "__main__":
    main()
