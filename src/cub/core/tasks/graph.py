"""
Dependency graph for task impact analysis.

Provides a pure query object built from a task list snapshot. Immutable after
construction. Used by AgentFormatter and `cub task blocked --agent` for impact
analysis and recommendations.
"""

from __future__ import annotations

from collections import deque

from .models import Task, TaskStatus


class DependencyGraph:
    """Immutable dependency graph built from a snapshot of tasks.

    The graph models two kinds of edges:

    * **forward edge** (``depends_on``): task A depends on task B  →  A cannot
      start until B is closed.
    * **reverse edge** (``unblocks``): completing B *unblocks* A.

    All queries are computed from these two adjacency maps plus the set of
    closed task IDs captured at construction time.

    Example::

        graph = DependencyGraph(backend.list_tasks())
        # Which tasks become workable if we close "cub-003"?
        graph.would_become_ready("cub-003")
    """

    __slots__ = ("_tasks", "_forward", "_reverse", "_closed", "_all_ids")

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, tasks: list[Task]) -> None:
        self._tasks: dict[str, Task] = {t.id: t for t in tasks}
        self._all_ids: frozenset[str] = frozenset(self._tasks)

        # forward[A] = {B, C} means A depends on B and C
        self._forward: dict[str, set[str]] = {}
        # reverse[B] = {A} means completing B unblocks A
        self._reverse: dict[str, set[str]] = {}

        self._closed: frozenset[str] = frozenset(
            t.id for t in tasks if t.status == TaskStatus.CLOSED
        )

        for task in tasks:
            deps = set(task.depends_on) & self._all_ids  # ignore dangling refs
            self._forward[task.id] = deps
            for dep_id in deps:
                self._reverse.setdefault(dep_id, set()).add(task.id)

    # ------------------------------------------------------------------
    # Core queries
    # ------------------------------------------------------------------

    def direct_unblocks(self, task_id: str) -> list[str]:
        """Return task IDs that directly depend on *task_id* (reverse edge lookup)."""
        return sorted(self._reverse.get(task_id, set()))

    def transitive_unblocks(self, task_id: str) -> set[str]:
        """BFS through reverse edges to find all transitively unblocked tasks."""
        visited: set[str] = set()
        queue: deque[str] = deque()

        for neighbour in self._reverse.get(task_id, set()):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)

        while queue:
            current = queue.popleft()
            for neighbour in self._reverse.get(current, set()):
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(neighbour)

        return visited

    def root_blockers(self, limit: int = 5) -> list[tuple[str, int]]:
        """Open tasks sorted by the number of tasks they transitively unblock.

        Returns at most *limit* ``(task_id, unblock_count)`` tuples,
        highest count first.
        """
        scores: list[tuple[str, int]] = []
        for tid in self._all_ids - self._closed:
            count = len(self.transitive_unblocks(tid))
            if count > 0:
                scores.append((tid, count))
        scores.sort(key=lambda x: (-x[1], x[0]))
        return scores[:limit]

    def chains(self, limit: int = 5) -> list[list[str]]:
        """Find the longest dependency chains (paths) in the forward graph.

        Uses DFS from every node, returns the *limit* longest paths sorted
        by length descending.
        """
        memo: dict[str, list[str]] = {}

        def _longest_from(node: str, visiting: set[str]) -> list[str]:
            if node in memo:
                return memo[node]
            if node in visiting:
                # cycle – stop recursion
                return [node]

            visiting.add(node)
            best: list[str] = [node]
            for dep in self._forward.get(node, set()):
                candidate = [node] + _longest_from(dep, visiting)
                if len(candidate) > len(best):
                    best = candidate
            visiting.discard(node)
            memo[node] = best
            return best

        all_chains: list[list[str]] = []
        for tid in sorted(self._all_ids):
            chain = _longest_from(tid, set())
            if len(chain) > 1:
                all_chains.append(chain)

        # Deduplicate: keep only chains that are not strict suffixes of others
        all_chains.sort(key=len, reverse=True)
        unique: list[list[str]] = []
        seen_tails: set[tuple[str, ...]] = set()
        for chain in all_chains:
            key = tuple(chain)
            # skip if this chain is a suffix of one already kept
            if key in seen_tails:
                continue
            unique.append(chain)
            # register all suffixes
            for i in range(1, len(chain)):
                seen_tails.add(tuple(chain[i:]))
        return unique[:limit]

    def would_become_ready(self, task_id: str) -> list[str]:
        """Tasks that would become ready (all deps satisfied) if *task_id* were closed.

        Only considers tasks that are not already closed.
        """
        hypothetical_closed = self._closed | {task_id}
        ready: list[str] = []
        for dependent in self._reverse.get(task_id, set()):
            if dependent in self._closed:
                continue
            deps = self._forward.get(dependent, set())
            if deps <= hypothetical_closed:
                ready.append(dependent)
        return sorted(ready)

    def has_cycle(self) -> bool:
        """Detect cycles using three-color DFS (white / gray / black)."""
        WHITE, GRAY, BLACK = 0, 1, 2  # noqa: N806
        color: dict[str, int] = {tid: WHITE for tid in self._all_ids}

        def _visit(node: str) -> bool:
            color[node] = GRAY
            for dep in self._forward.get(node, set()):
                if color[dep] == GRAY:
                    return True
                if color[dep] == WHITE and _visit(dep):
                    return True
            color[node] = BLACK
            return False

        for tid in self._all_ids:
            if color[tid] == WHITE:
                if _visit(tid):
                    return True
        return False

    # ------------------------------------------------------------------
    # Aggregate stats
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, int]:
        """Summary statistics: node_count, edge_count, max_chain_depth."""
        edge_count = sum(len(deps) for deps in self._forward.values())

        # max chain depth: longest path in forward graph
        max_depth = 0
        if self._all_ids:
            for chain in self.chains(limit=1):
                max_depth = len(chain)

        return {
            "node_count": len(self._all_ids),
            "edge_count": edge_count,
            "max_chain_depth": max_depth,
        }
