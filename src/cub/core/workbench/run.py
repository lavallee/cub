"""Execute a workbench session's Next Move.

MVP implementation:
- Loads a session markdown file (frontmatter)
- Executes Next Move if it specifies an adopted tool
- Writes Toolsmith run artifacts (handled by tool execution layer)
- Updates the session file with links to produced artifacts

This is intentionally narrow to support experimentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter

from cub.core.toolsmith.execution import ToolExecutionError, run_tool


@dataclass(frozen=True)
class RunNextResult:
    session_path: Path
    tool_id: str
    artifact_paths: list[Path]


def _load_session(path: Path) -> frontmatter.Post:
    return frontmatter.load(path)


def _save_session(path: Path, post: frontmatter.Post) -> None:
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def run_next_move(*, session_path: Path) -> RunNextResult:
    """Run the session's configured next_move.

    Currently supports only next_move.kind == 'research' with tool_id
    mcp-official:brave-search.
    """
    post = _load_session(session_path)
    meta: dict[str, Any] = post.metadata if isinstance(post.metadata, dict) else {}

    next_move = meta.get("next_move") or {}
    if not isinstance(next_move, dict):
        raise ValueError("session next_move must be a dict")

    tool_id = next_move.get("tool_id")
    if not tool_id or not isinstance(tool_id, str):
        # Fallback: if the session didn't have a tool selected yet, try to use an
        # adopted tool matching the expected default.
        from cub.core.toolsmith.adoption import AdoptionStore

        adopted_ids = {a.tool_id for a in AdoptionStore.default().list_all()}
        if "mcp-official:brave-search" in adopted_ids:
            tool_id = "mcp-official:brave-search"
            next_move["tool_id"] = tool_id
        else:
            raise ValueError(
                "next_move.tool_id is missing; adopt a tool (e.g., mcp-official:brave-search) "
                "or edit the session"
            )

    kind = next_move.get("kind")
    if kind != "research":
        raise ValueError(f"Unsupported next_move.kind: {kind!r} (only 'research' supported)")

    queries = next_move.get("queries") or []
    if not isinstance(queries, list) or not queries:
        raise ValueError("next_move.queries must be a non-empty list")

    count = int(next_move.get("count", 5))

    artifact_paths: list[Path] = []
    results: list[dict[str, Any]] = []

    import time

    for q in queries:
        q = str(q).strip()
        if not q:
            continue
        try:
            r = run_tool(tool_id, params={"query": q, "count": count})
            artifact_paths.append(r.artifact_path)
            results.append(
                {
                    "query": q,
                    "artifact": str(r.artifact_path),
                    "summary": r.summary,
                    "ok": True,
                }
            )
        except ToolExecutionError as e:
            # Record the failure and stop further queries to avoid hammering
            # rate-limited APIs.
            results.append({"query": q, "ok": False, "error": str(e)})
            break

        # Small delay to reduce risk of rate limiting.
        time.sleep(0.8)

    # Update session links
    links = meta.get("links")
    if not isinstance(links, list):
        links = []

    for p in artifact_paths:
        links.append({"kind": "tool_run", "tool_id": tool_id, "path": str(p)})

    meta["links"] = links
    next_move["last_run"] = datetime.now(timezone.utc).isoformat()
    next_move["run_results"] = results
    meta["next_move"] = next_move

    post.metadata = meta
    _save_session(session_path, post)

    return RunNextResult(session_path=session_path, tool_id=tool_id, artifact_paths=artifact_paths)
