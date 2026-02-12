"""Plan Markdown parser and beads-JSONL emitter.

Non-interactive planning is more reliable when the LLM outputs a strict-but-human
Markdown plan, and Cub deterministically serializes it to the backend format
(beads JSONL today).

Format (strict):

# Plan

## Epic: <epic_id> - <title>
Priority: <int>
Labels: a, b, c
Description:
<freeform markdown until next heading>

### Task: <task_id> - <title>
Priority: <int>
Labels: a, b
Blocks: other-task-id, another-id   (optional)
Description:
<freeform markdown until next heading>

Notes:
- IDs may be provided without prefix; caller can apply a prefix.
- Tasks automatically get a parent-child dependency on their epic.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Pattern matches "## Epic: <id> - <title>" where <id> can contain hyphens
# The separator is " - " (space-hyphen-space) to distinguish from hyphens in IDs
_EPIC_RE = re.compile(r"^##\s+Epic:\s*(?P<id>.+?)\s+-\s+(?P<title>.+?)\s*$")
_TASK_RE = re.compile(r"^###\s+Task:\s*(?P<id>.+?)\s+-\s+(?P<title>.+?)\s*$")
_KEY_RE = re.compile(r"^(?P<key>Priority|Labels|Blocks):\s*(?P<value>.*)$")


@dataclass
class PlanTask:
    task_id: str
    title: str
    priority: int = 2
    labels: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class PlanEpic:
    epic_id: str
    title: str
    priority: int = 2
    labels: list[str] = field(default_factory=list)
    description: str = ""
    tasks: list[PlanTask] = field(default_factory=list)


def _split_csv(value: str) -> list[str]:
    items = [v.strip() for v in value.split(",")]
    return [v for v in items if v]


def _normalize_id(raw: str, prefix: str) -> str:
    trimmed = raw.strip()
    if not trimmed:
        return trimmed
    if trimmed.startswith(prefix + "-"):
        return trimmed
    return f"{prefix}-{trimmed}" if prefix else trimmed


def parse_plan_markdown(text: str) -> list[PlanEpic]:
    lines = text.splitlines()

    epics: list[PlanEpic] = []
    current_epic: PlanEpic | None = None
    current_task: PlanTask | None = None
    in_description = False
    buf: list[str] = []

    def flush_description() -> None:
        nonlocal buf
        if not buf:
            return
        content = "\n".join(buf).strip() + "\n"
        if current_task is not None:
            current_task.description = content
        elif current_epic is not None:
            current_epic.description = content
        buf = []

    for line in lines:
        epic_match = _EPIC_RE.match(line)
        if epic_match:
            flush_description()
            current_task = None
            current_epic = PlanEpic(
                epic_id=epic_match.group("id").strip(),
                title=epic_match.group("title").strip(),
            )
            epics.append(current_epic)
            in_description = False
            continue

        task_match = _TASK_RE.match(line)
        if task_match:
            flush_description()
            if current_epic is None:
                # Ignore stray task outside an epic.
                continue
            current_task = PlanTask(
                task_id=task_match.group("id").strip(),
                title=task_match.group("title").strip(),
            )
            current_epic.tasks.append(current_task)
            in_description = False
            continue

        key_match = _KEY_RE.match(line)
        if key_match:
            flush_description()
            key = key_match.group("key")
            value = key_match.group("value").strip()
            target = current_task if current_task is not None else current_epic
            if target is None:
                continue
            if key == "Priority":
                try:
                    target.priority = int(value)
                except ValueError:
                    pass
            elif key == "Labels":
                target.labels = _split_csv(value)
            elif key == "Blocks" and current_task is not None:
                current_task.blocks = _split_csv(value)
            in_description = False
            continue

        if line.strip() == "Description:" or line.strip() == "Description":
            flush_description()
            in_description = True
            continue

        if in_description:
            buf.append(line)

    flush_description()
    return epics


def iter_beads_jsonl(epics: Iterable[PlanEpic], *, prefix: str) -> Iterable[dict[str, Any]]:
    for epic in epics:
        epic_id = _normalize_id(epic.epic_id, prefix)
        yield {
            "id": epic_id,
            "title": epic.title,
            "description": epic.description or "",
            "status": "open",
            "priority": epic.priority,
            "issue_type": "epic",
            "labels": epic.labels,
            "dependencies": [],
        }
        for task in epic.tasks:
            task_id = _normalize_id(task.task_id, prefix)
            deps = [{"depends_on_id": epic_id, "type": "parent-child"}]
            for blocked in task.blocks:
                deps.append({"depends_on_id": _normalize_id(blocked, prefix), "type": "blocks"})
            yield {
                "id": task_id,
                "title": task.title,
                "description": task.description or "",
                "status": "open",
                "priority": task.priority,
                "issue_type": "task",
                "labels": task.labels,
                "dependencies": deps,
            }


def convert_plan_markdown_to_beads_jsonl(md_path: Path, jsonl_path: Path, *, prefix: str) -> None:
    text = md_path.read_text(encoding="utf-8")
    epics = parse_plan_markdown(text)
    lines = [json.dumps(obj, ensure_ascii=False) for obj in iter_beads_jsonl(epics, prefix=prefix)]
    jsonl_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Convert strict plan markdown to beads JSONL")
    parser.add_argument("--prefix", default="", help="ID prefix (e.g. project name)")
    parser.add_argument("md", help="Input markdown path")
    parser.add_argument("jsonl", help="Output JSONL path")
    args = parser.parse_args(argv)

    convert_plan_markdown_to_beads_jsonl(Path(args.md), Path(args.jsonl), prefix=str(args.prefix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
