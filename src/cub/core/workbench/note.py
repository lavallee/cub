"""Workbench note generation.

Takes tool run artifacts (JSON) and synthesizes them into a durable markdown note.
This is the missing bridge between "tool executed" and "human-usable artifact".

Current scope: Brave Search web results and other search tools.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter

from cub.core.tools.models import ToolResult


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_tool_result(path: Path) -> ToolResult | None:
    """Load a ToolResult from an artifact JSON file."""
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return ToolResult.model_validate(data)
    except Exception:
        return None


def _extract_web_results(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Extract Brave web results into a stable [{title,url,description}] list.

    This is a fallback for legacy artifact formats or when output_markdown is not available.
    """
    # Handle new ToolResult format where output is the response data
    output = payload.get("output")
    if isinstance(output, dict):
        result: dict[str, Any] = output
    else:
        # Fallback to legacy format
        result_val = payload.get("result")
        result = result_val if isinstance(result_val, dict) else {}

    if not isinstance(result, dict):
        return []

    web = result.get("web")
    if not isinstance(web, dict):
        return []

    items = web.get("results")
    if not isinstance(items, list):
        return []

    out: list[dict[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or "").strip()
        url = str(it.get("url") or "").strip()
        desc = str(it.get("description") or "").strip()
        if not (title and url):
            continue
        out.append({"title": title, "url": url, "description": desc})
    return out


def write_research_note_from_session(
    *,
    session_path: Path,
    note_path: Path,
    max_results_per_query: int = 5,
) -> Path:
    """Write/append a research note based on a workbench session.

    The session must have next_move.run_results entries with artifact paths.

    We append a new section for each run so the note becomes a running log.
    """
    post = frontmatter.load(session_path)
    meta = post.metadata if isinstance(post.metadata, dict) else {}
    next_move = meta.get("next_move")
    if not isinstance(next_move, dict):
        raise ValueError("session missing next_move")

    run_results = next_move.get("run_results")
    if not isinstance(run_results, list):
        raise ValueError("session next_move has no run_results; run workbench run-next first")

    tool_id = str(next_move.get("tool_id") or "").strip()
    created_at = _utc_now().isoformat()

    lines: list[str] = []
    lines.append(f"## Research run ({created_at})")
    if tool_id:
        lines.append(f"Tool: `{tool_id}`")
    lines.append("")

    for rr in run_results:
        if not isinstance(rr, dict):
            continue
        q = str(rr.get("query") or "").strip()
        ok = rr.get("ok") is True
        artifact = str(rr.get("artifact") or "").strip()
        if not q:
            continue

        lines.append(f"### Query: {q}")

        if not ok:
            err = str(rr.get("error") or "").strip()
            lines.append("- Status: FAILED")
            if err:
                lines.append(f"- Error: {err}")
            lines.append("")
            continue

        lines.append("- Status: OK")
        if artifact:
            lines.append(f"- Artifact: `{artifact}`")

        # Try to load ToolResult and use output_markdown if available
        tool_result = None
        if artifact:
            tool_result = _load_tool_result(Path(artifact))

        # Prefer output_markdown from ToolResult
        if tool_result and tool_result.output_markdown:
            lines.append("")
            lines.append(tool_result.output_markdown)
            lines.append("")
        else:
            # Fallback: extract web results from artifact payload
            results: list[dict[str, str]] = []
            if artifact:
                try:
                    with Path(artifact).open(encoding="utf-8") as f:
                        payload = json.load(f)
                    if isinstance(payload, dict):
                        results = _extract_web_results(payload)[:max_results_per_query]
                except Exception:
                    pass

            if results:
                lines.append("")
                for item in results:
                    title = item.get("title", "").strip()
                    url = item.get("url", "").strip()
                    desc = item.get("description", "").strip()
                    lines.append(f"- {title}\n  - {url}")
                    if desc:
                        lines.append(f"  - {desc}")
            lines.append("")

    # Ensure parent dirs exist
    note_path.parent.mkdir(parents=True, exist_ok=True)

    if note_path.exists():
        existing = note_path.read_text(encoding="utf-8").rstrip() + "\n\n"
    else:
        existing = (
            "---\n"
            f"created: {created_at}\n"
            "source: cub workbench run-next\n"
            "---\n\n"
            "# Workbench Research Notes\n\n"
        )

    note_path.write_text(existing + "\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return note_path
