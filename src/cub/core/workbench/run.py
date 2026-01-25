"""Execute a workbench session's Next Move.

MVP implementation:
- Loads a session markdown file (frontmatter)
- Executes Next Move if it specifies an adopted tool
- Writes Toolsmith run artifacts (handled by tool execution layer)
- Updates the session file with links to produced artifacts

This is intentionally narrow to support experimentation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter

from cub.core.tools.exceptions import ExecutionError, ToolNotAdoptedError
from cub.core.tools.execution import ExecutionService
from cub.core.tools.registry import RegistryService


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

    Uses the new unified tool execution system with ExecutionService
    and RegistryService. Supports any adopted tool with search capability.
    """
    # Run async execution in a synchronous context
    return asyncio.run(_run_next_move_async(session_path=session_path))


async def _run_next_move_async(*, session_path: Path) -> RunNextResult:
    """Async implementation of run_next_move."""
    post = _load_session(session_path)
    meta: dict[str, Any] = post.metadata if isinstance(post.metadata, dict) else {}

    next_move = meta.get("next_move") or {}
    if not isinstance(next_move, dict):
        raise ValueError("session next_move must be a dict")

    tool_id = next_move.get("tool_id")

    # Initialize registry and execution services
    registry_service = RegistryService()
    execution_service = ExecutionService(registry_service=registry_service)

    if not tool_id or not isinstance(tool_id, str):
        # Fallback: if the session didn't have a tool selected yet, try to use an
        # adopted tool with search capability.
        search_tools = registry_service.find_by_capability("web_search")
        if search_tools:
            tool_id = search_tools[0].id
            next_move["tool_id"] = tool_id
        else:
            raise ValueError(
                "next_move.tool_id is missing and no tools with 'web_search' capability "
                "are adopted. Adopt a search tool first (e.g., brave-search)."
            )

    # Verify tool is adopted
    tool_config = registry_service.load().get(tool_id)
    if tool_config is None:
        raise ToolNotAdoptedError(
            tool_id,
            f"Tool '{tool_id}' must be adopted before use. "
            f"Use 'cub tools adopt {tool_id}' to adopt this tool.",
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
            # Build params with config from registry
            params = {"query": q, "count": count}

            # Add adapter-specific config to params
            if tool_config.http_config:
                params["_http_config"] = tool_config.http_config
            elif tool_config.cli_config:
                params["_cli_config"] = tool_config.cli_config
            elif tool_config.mcp_config:
                params["_mcp_config"] = tool_config.mcp_config

            # Execute the tool using the new system
            r = await execution_service.execute(
                tool_id=tool_id,
                action="search",
                adapter_type=tool_config.adapter_type.value,
                params=params,
                timeout=30.0,
                save_artifact=True,
            )

            if r.success and r.artifact_path:
                artifact_paths.append(Path(r.artifact_path))
                results.append(
                    {
                        "query": q,
                        "artifact": r.artifact_path,
                        "summary": r.output_markdown or "Tool executed successfully",
                        "ok": True,
                    }
                )
            else:
                # Tool execution failed
                results.append(
                    {
                        "query": q,
                        "ok": False,
                        "error": r.error or "Tool execution failed",
                    }
                )
                break

        except (ExecutionError, ToolNotAdoptedError) as e:
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
