"""Tests for DependencyGraph — pure query object for dependency analysis."""

from __future__ import annotations

import pytest

from cub.core.tasks.graph import DependencyGraph
from cub.core.tasks.models import Task, TaskStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _task(
    tid: str,
    depends_on: list[str] | None = None,
    status: TaskStatus = TaskStatus.OPEN,
) -> Task:
    """Shorthand for creating a minimal Task."""
    return Task(
        id=tid,
        title=f"Task {tid}",
        status=status,
        depends_on=depends_on or [],
    )


# ---------------------------------------------------------------------------
# Topology: empty graph
# ---------------------------------------------------------------------------


class TestEmptyGraph:
    def test_direct_unblocks_empty(self) -> None:
        g = DependencyGraph([])
        assert g.direct_unblocks("x") == []

    def test_transitive_unblocks_empty(self) -> None:
        g = DependencyGraph([])
        assert g.transitive_unblocks("x") == set()

    def test_root_blockers_empty(self) -> None:
        g = DependencyGraph([])
        assert g.root_blockers() == []

    def test_chains_empty(self) -> None:
        g = DependencyGraph([])
        assert g.chains() == []

    def test_would_become_ready_empty(self) -> None:
        g = DependencyGraph([])
        assert g.would_become_ready("x") == []

    def test_has_cycle_empty(self) -> None:
        g = DependencyGraph([])
        assert g.has_cycle() is False

    def test_stats_empty(self) -> None:
        s = DependencyGraph([]).stats
        assert s == {"node_count": 0, "edge_count": 0, "max_chain_depth": 0}


# ---------------------------------------------------------------------------
# Topology: single task (no deps)
# ---------------------------------------------------------------------------


class TestSingleTask:
    def test_no_edges(self) -> None:
        g = DependencyGraph([_task("a")])
        assert g.direct_unblocks("a") == []
        assert g.transitive_unblocks("a") == set()
        assert g.root_blockers() == []
        assert g.chains() == []
        assert g.would_become_ready("a") == []
        assert g.has_cycle() is False

    def test_stats_single(self) -> None:
        s = DependencyGraph([_task("a")]).stats
        assert s == {"node_count": 1, "edge_count": 0, "max_chain_depth": 0}


# ---------------------------------------------------------------------------
# Topology: linear chain  A → B → C → D
# (D depends on C, C depends on B, B depends on A)
# ---------------------------------------------------------------------------


class TestLinearChain:
    @pytest.fixture()
    def graph(self) -> DependencyGraph:
        return DependencyGraph([
            _task("a"),
            _task("b", depends_on=["a"]),
            _task("c", depends_on=["b"]),
            _task("d", depends_on=["c"]),
        ])

    def test_direct_unblocks(self, graph: DependencyGraph) -> None:
        assert graph.direct_unblocks("a") == ["b"]
        assert graph.direct_unblocks("b") == ["c"]
        assert graph.direct_unblocks("c") == ["d"]
        assert graph.direct_unblocks("d") == []

    def test_transitive_unblocks(self, graph: DependencyGraph) -> None:
        assert graph.transitive_unblocks("a") == {"b", "c", "d"}
        assert graph.transitive_unblocks("b") == {"c", "d"}
        assert graph.transitive_unblocks("c") == {"d"}
        assert graph.transitive_unblocks("d") == set()

    def test_root_blockers(self, graph: DependencyGraph) -> None:
        blockers = graph.root_blockers()
        assert blockers[0] == ("a", 3)
        assert blockers[1] == ("b", 2)
        assert blockers[2] == ("c", 1)

    def test_chains(self, graph: DependencyGraph) -> None:
        chains = graph.chains()
        assert len(chains) >= 1
        # the longest chain should be length 4 (d → c → b → a)
        assert len(chains[0]) == 4

    def test_would_become_ready(self, graph: DependencyGraph) -> None:
        # closing a should make b ready (b's only dep is a)
        assert graph.would_become_ready("a") == ["b"]
        # closing b shouldn't make c ready (c depends on b, not closed yet)
        assert graph.would_become_ready("b") == ["c"]

    def test_has_cycle(self, graph: DependencyGraph) -> None:
        assert graph.has_cycle() is False

    def test_stats(self, graph: DependencyGraph) -> None:
        s = graph.stats
        assert s["node_count"] == 4
        assert s["edge_count"] == 3
        assert s["max_chain_depth"] == 4


# ---------------------------------------------------------------------------
# Topology: diamond   A → B, A → C, B → D, C → D
# (D depends on B and C; B and C both depend on A)
# ---------------------------------------------------------------------------


class TestDiamond:
    @pytest.fixture()
    def graph(self) -> DependencyGraph:
        return DependencyGraph([
            _task("a"),
            _task("b", depends_on=["a"]),
            _task("c", depends_on=["a"]),
            _task("d", depends_on=["b", "c"]),
        ])

    def test_direct_unblocks(self, graph: DependencyGraph) -> None:
        assert graph.direct_unblocks("a") == ["b", "c"]
        assert graph.direct_unblocks("b") == ["d"]
        assert graph.direct_unblocks("c") == ["d"]
        assert graph.direct_unblocks("d") == []

    def test_transitive_unblocks(self, graph: DependencyGraph) -> None:
        assert graph.transitive_unblocks("a") == {"b", "c", "d"}
        assert graph.transitive_unblocks("b") == {"d"}

    def test_root_blockers(self, graph: DependencyGraph) -> None:
        blockers = graph.root_blockers()
        assert blockers[0] == ("a", 3)

    def test_would_become_ready_diamond(self, graph: DependencyGraph) -> None:
        # closing a: both b and c become ready (only dep is a)
        assert graph.would_become_ready("a") == ["b", "c"]
        # closing b alone: d is NOT ready (still depends on c)
        assert graph.would_become_ready("b") == []

    def test_would_become_ready_with_partial_close(self) -> None:
        # b is already closed, closing c should make d ready
        g = DependencyGraph([
            _task("a", status=TaskStatus.CLOSED),
            _task("b", depends_on=["a"], status=TaskStatus.CLOSED),
            _task("c", depends_on=["a"]),
            _task("d", depends_on=["b", "c"]),
        ])
        assert g.would_become_ready("c") == ["d"]

    def test_has_cycle(self, graph: DependencyGraph) -> None:
        assert graph.has_cycle() is False

    def test_stats(self, graph: DependencyGraph) -> None:
        s = graph.stats
        assert s["node_count"] == 4
        assert s["edge_count"] == 4


# ---------------------------------------------------------------------------
# Topology: forest (two independent chains)
# ---------------------------------------------------------------------------


class TestForest:
    @pytest.fixture()
    def graph(self) -> DependencyGraph:
        return DependencyGraph([
            _task("x1"),
            _task("x2", depends_on=["x1"]),
            _task("y1"),
            _task("y2", depends_on=["y1"]),
            _task("y3", depends_on=["y2"]),
        ])

    def test_independent_chains(self, graph: DependencyGraph) -> None:
        assert graph.transitive_unblocks("x1") == {"x2"}
        assert graph.transitive_unblocks("y1") == {"y2", "y3"}

    def test_root_blockers(self, graph: DependencyGraph) -> None:
        blockers = graph.root_blockers()
        assert blockers[0] == ("y1", 2)
        assert blockers[1] == ("x1", 1)

    def test_chains(self, graph: DependencyGraph) -> None:
        chains = graph.chains()
        # longest chain should be y3 → y2 → y1 (length 3)
        assert len(chains[0]) == 3

    def test_has_cycle(self, graph: DependencyGraph) -> None:
        assert graph.has_cycle() is False


# ---------------------------------------------------------------------------
# Topology: cycle
# ---------------------------------------------------------------------------


class TestCycle:
    def test_simple_cycle(self) -> None:
        g = DependencyGraph([
            _task("a", depends_on=["c"]),
            _task("b", depends_on=["a"]),
            _task("c", depends_on=["b"]),
        ])
        assert g.has_cycle() is True

    def test_self_loop(self) -> None:
        g = DependencyGraph([
            _task("a", depends_on=["a"]),
        ])
        assert g.has_cycle() is True

    def test_cycle_with_tail(self) -> None:
        # d → c → b → a → c  (cycle in a,b,c; d hangs off c)
        g = DependencyGraph([
            _task("a", depends_on=["c"]),
            _task("b", depends_on=["a"]),
            _task("c", depends_on=["b"]),
            _task("d", depends_on=["c"]),
        ])
        assert g.has_cycle() is True

    def test_no_cycle_in_dag(self) -> None:
        g = DependencyGraph([
            _task("a"),
            _task("b", depends_on=["a"]),
            _task("c", depends_on=["a"]),
            _task("d", depends_on=["b", "c"]),
        ])
        assert g.has_cycle() is False


# ---------------------------------------------------------------------------
# Topology: mixed open / closed
# ---------------------------------------------------------------------------


class TestMixedOpenClosed:
    @pytest.fixture()
    def graph(self) -> DependencyGraph:
        """A → B → C, A is closed."""
        return DependencyGraph([
            _task("a", status=TaskStatus.CLOSED),
            _task("b", depends_on=["a"]),
            _task("c", depends_on=["b"]),
        ])

    def test_root_blockers_exclude_closed(self, graph: DependencyGraph) -> None:
        blockers = graph.root_blockers()
        # 'a' is closed so should not appear
        ids = [b[0] for b in blockers]
        assert "a" not in ids
        assert ("b", 1) in blockers

    def test_would_become_ready_respects_closed(self, graph: DependencyGraph) -> None:
        # b's only dep (a) is already closed, so b is effectively ready
        # closing 'a' again: b should still show (it checks hypothetical)
        assert graph.would_become_ready("a") == ["b"]

    def test_would_become_ready_skips_already_closed(self) -> None:
        g = DependencyGraph([
            _task("a"),
            _task("b", depends_on=["a"], status=TaskStatus.CLOSED),
        ])
        # b is already closed, so won't appear in would_become_ready
        assert g.would_become_ready("a") == []

    def test_all_closed(self) -> None:
        g = DependencyGraph([
            _task("a", status=TaskStatus.CLOSED),
            _task("b", depends_on=["a"], status=TaskStatus.CLOSED),
        ])
        assert g.root_blockers() == []
        assert g.would_become_ready("a") == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_dangling_dependency_ignored(self) -> None:
        """If depends_on references a task not in the snapshot, ignore it."""
        g = DependencyGraph([
            _task("a", depends_on=["nonexistent"]),
        ])
        assert g.direct_unblocks("a") == []
        assert g.stats["edge_count"] == 0
        assert g.has_cycle() is False

    def test_chains_limit(self) -> None:
        tasks = [_task("t0")]
        for i in range(1, 10):
            tasks.append(_task(f"t{i}", depends_on=[f"t{i-1}"]))
        g = DependencyGraph(tasks)
        chains = g.chains(limit=2)
        assert len(chains) <= 2

    def test_root_blockers_limit(self) -> None:
        # many independent blockers
        tasks = []
        for i in range(20):
            tasks.append(_task(f"root{i}"))
            tasks.append(_task(f"child{i}", depends_on=[f"root{i}"]))
        g = DependencyGraph(tasks)
        assert len(g.root_blockers(limit=3)) == 3

    def test_in_progress_counts_as_open(self) -> None:
        """IN_PROGRESS tasks are not closed — they block dependents."""
        g = DependencyGraph([
            _task("a", status=TaskStatus.IN_PROGRESS),
            _task("b", depends_on=["a"]),
        ])
        assert g.would_become_ready("a") == ["b"]
        blockers = g.root_blockers()
        assert ("a", 1) in blockers
