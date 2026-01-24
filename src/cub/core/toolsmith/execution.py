"""Tool execution helpers (experimental).

Toolsmith's long-term goal is to discover, evaluate, *install*, and *execute*
external tools (e.g., MCP servers, skills). The broader tool execution
architecture is still in flux.

This module provides a minimal, well-scoped execution layer so we can start
"adopt → use" experiments without blocking on full MCP runtime support.

Current scope:
- Provide a small set of *built-in adapters* that execute a known tool id.
- Record run artifacts under .cub/toolsmith/runs/.

As Toolsmith matures, these adapters should be replaced by a generic runtime
(MCP stdio/HTTP, skill runner, etc.) and richer Tool metadata.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class ToolRunResult:
    tool_id: str
    created_at: datetime
    artifact_path: Path
    summary: str


class ToolExecutionError(RuntimeError):
    pass


def _runs_dir() -> Path:
    return Path.cwd() / ".cub" / "toolsmith" / "runs"


def _write_artifact(tool_id: str, payload: dict[str, Any]) -> Path:
    runs_dir = _runs_dir()
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_id = tool_id.replace(":", "_").replace("/", "_")
    path = runs_dir / f"{ts}-{safe_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def run_tool(tool_id: str, *, params: dict[str, Any]) -> ToolRunResult:
    """Execute a tool by id (experimental).

    Args:
        tool_id: Tool catalog id
        params: Tool-specific parameters

    Returns:
        ToolRunResult

    Raises:
        ToolExecutionError on unsupported tool id or execution failure.
    """
    if tool_id == "mcp-official:brave-search":
        return _run_brave_search(tool_id, params=params)

    raise ToolExecutionError(
        f"Tool execution not implemented for '{tool_id}'. "
        "(Only mcp-official:brave-search is supported in this experiment.)"
    )


def _run_brave_search(tool_id: str, *, params: dict[str, Any]) -> ToolRunResult:
    query = str(params.get("query", "")).strip()
    count = int(params.get("count", 5))
    if not query:
        raise ToolExecutionError("brave-search requires non-empty 'query'")
    if count < 1 or count > 20:
        raise ToolExecutionError("brave-search 'count' must be between 1 and 20")

    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        raise ToolExecutionError(
            "BRAVE_API_KEY is not set. Set it in the environment, e.g.\n\n"
            "  export BRAVE_API_KEY=...\n\n"
            "Then re-run the command."
        )

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
        "User-Agent": "cub-toolsmith/0.1",
    }

    # Brave API uses 'q' query parameter.
    http_params = {"q": query, "count": str(count)}

    try:
        resp = httpx.get(url, params=http_params, headers=headers, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        raise ToolExecutionError(f"Brave API HTTP {e.response.status_code}: {e}") from e
    except Exception as e:
        raise ToolExecutionError(f"Brave API request failed: {e}") from e

    created_at = datetime.now(timezone.utc)
    payload = {
        "tool_id": tool_id,
        "created_at": created_at.isoformat(),
        "params": {"query": query, "count": count},
        "result": data,
    }
    artifact = _write_artifact(tool_id, payload)

    # Build a small human summary.
    web_results = ((data.get("web") or {}).get("results") or [])
    summary = f"Brave search returned {len(web_results)} result(s) for '{query}'."

    return ToolRunResult(
        tool_id=tool_id,
        created_at=created_at,
        artifact_path=artifact,
        summary=summary,
    )
