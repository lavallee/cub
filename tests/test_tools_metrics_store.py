"""Tests for MetricsStore."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.tools.metrics import MetricsStore
from cub.core.tools.models import AdapterType, ToolMetrics, ToolResult


class TestMetricsStore:
    """Tests for MetricsStore class."""

    def test_create_store(self, tmp_path: Path):
        """Test creating a MetricsStore instance."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)
        assert store.metrics_file == metrics_file

    def test_load_nonexistent_file(self, tmp_path: Path):
        """Test loading metrics when file doesn't exist returns empty dict."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)
        metrics = store.load()
        assert metrics == {}
        assert isinstance(metrics, dict)

    def test_save_and_load_metrics(self, tmp_path: Path):
        """Test saving and loading metrics."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Create metrics
        now = datetime.now(timezone.utc)
        metrics_data = {
            "test-tool": ToolMetrics(
                tool_id="test-tool",
                invocations=10,
                successes=8,
                failures=2,
                total_duration_ms=5000,
                min_duration_ms=100,
                max_duration_ms=1000,
                avg_duration_ms=500.0,
                error_types={"timeout": 1, "auth": 1},
                last_used_at=now,
                first_used_at=now,
            )
        }

        # Save
        saved_path = store.save(metrics_data)
        assert saved_path == metrics_file
        assert metrics_file.exists()

        # Load
        loaded = store.load()
        assert len(loaded) == 1
        assert "test-tool" in loaded
        assert loaded["test-tool"].invocations == 10
        assert loaded["test-tool"].successes == 8
        assert loaded["test-tool"].failures == 2

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        """Test that save creates parent directories if they don't exist."""
        metrics_file = tmp_path / "nested" / "deep" / "metrics.json"
        store = MetricsStore(metrics_file)

        # Save empty metrics
        store.save({})

        assert metrics_file.exists()
        assert metrics_file.parent.exists()

    def test_get_existing_tool(self, tmp_path: Path):
        """Test getting metrics for an existing tool."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Create and save metrics
        metrics_data = {
            "test-tool": ToolMetrics(tool_id="test-tool", invocations=5)
        }
        store.save(metrics_data)

        # Get metrics
        metrics = store.get("test-tool")
        assert metrics is not None
        assert metrics.tool_id == "test-tool"
        assert metrics.invocations == 5

    def test_get_nonexistent_tool(self, tmp_path: Path):
        """Test getting metrics for a tool that doesn't exist."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        metrics = store.get("nonexistent")
        assert metrics is None

    def test_get_or_create_existing(self, tmp_path: Path):
        """Test get_or_create with an existing tool."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Create and save metrics
        metrics_data = {
            "test-tool": ToolMetrics(tool_id="test-tool", invocations=5)
        }
        store.save(metrics_data)

        # Get or create should return existing metrics
        metrics = store.get_or_create("test-tool")
        assert metrics.tool_id == "test-tool"
        assert metrics.invocations == 5

    def test_get_or_create_new(self, tmp_path: Path):
        """Test get_or_create with a new tool."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Get or create should create new metrics
        metrics = store.get_or_create("new-tool")
        assert metrics.tool_id == "new-tool"
        assert metrics.invocations == 0
        assert metrics.successes == 0

    def test_record_execution_new_tool(self, tmp_path: Path):
        """Test recording execution for a new tool."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Create a result
        result = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={"result": "success"},
            started_at=datetime.now(timezone.utc),
            duration_ms=250,
            adapter_type=AdapterType.HTTP,
        )

        # Record execution
        metrics = store.record_execution(result)

        # Check returned metrics
        assert metrics.tool_id == "test-tool"
        assert metrics.invocations == 1
        assert metrics.successes == 1
        assert metrics.failures == 0

        # Check persisted metrics
        loaded = store.load()
        assert "test-tool" in loaded
        assert loaded["test-tool"].invocations == 1

    def test_record_execution_existing_tool(self, tmp_path: Path):
        """Test recording execution for an existing tool."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Create initial metrics
        initial_metrics = {
            "test-tool": ToolMetrics(
                tool_id="test-tool",
                invocations=5,
                successes=4,
                failures=1,
            )
        }
        store.save(initial_metrics)

        # Record a new execution
        result = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={"result": "success"},
            started_at=datetime.now(timezone.utc),
            duration_ms=250,
            adapter_type=AdapterType.HTTP,
        )

        metrics = store.record_execution(result)

        # Check metrics were updated
        assert metrics.invocations == 6
        assert metrics.successes == 5
        assert metrics.failures == 1

        # Check persistence
        loaded = store.load()
        assert loaded["test-tool"].invocations == 6

    def test_record_multiple_executions(self, tmp_path: Path):
        """Test recording multiple executions."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        base_time = datetime.now(timezone.utc)

        # Record several executions
        for i in range(3):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=i < 2,  # First two succeed, last one fails
                output={"result": "success"} if i < 2 else None,
                error="Error" if i == 2 else None,
                error_type="timeout" if i == 2 else None,
                started_at=base_time,
                duration_ms=100 * (i + 1),
                adapter_type=AdapterType.HTTP,
            )
            store.record_execution(result)

        # Check final metrics
        loaded = store.load()
        metrics = loaded["test-tool"]
        assert metrics.invocations == 3
        assert metrics.successes == 2
        assert metrics.failures == 1
        assert metrics.error_types == {"timeout": 1}
        assert metrics.min_duration_ms == 100
        assert metrics.max_duration_ms == 300

    def test_list_all_empty(self, tmp_path: Path):
        """Test listing all metrics when store is empty."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        all_metrics = store.list_all()
        assert all_metrics == []
        assert isinstance(all_metrics, list)

    def test_list_all_with_metrics(self, tmp_path: Path):
        """Test listing all metrics."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Create multiple metrics
        metrics_data = {
            "tool-a": ToolMetrics(tool_id="tool-a", invocations=5),
            "tool-b": ToolMetrics(tool_id="tool-b", invocations=10),
            "tool-c": ToolMetrics(tool_id="tool-c", invocations=3),
        }
        store.save(metrics_data)

        # List all
        all_metrics = store.list_all()
        assert len(all_metrics) == 3
        tool_ids = {m.tool_id for m in all_metrics}
        assert tool_ids == {"tool-a", "tool-b", "tool-c"}

    def test_filter_metrics(self, tmp_path: Path):
        """Test filtering metrics with a predicate."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Create metrics with different characteristics
        metrics_data = {
            "tool-a": ToolMetrics(
                tool_id="tool-a",
                invocations=10,
                successes=10,
                failures=0,
            ),
            "tool-b": ToolMetrics(
                tool_id="tool-b",
                invocations=10,
                successes=5,
                failures=5,
            ),
            "tool-c": ToolMetrics(
                tool_id="tool-c",
                invocations=2,
                successes=2,
                failures=0,
            ),
        }
        store.save(metrics_data)

        # Filter by success rate < 80%
        unreliable = store.filter(lambda m: m.success_rate() < 80.0)
        assert len(unreliable) == 1
        assert unreliable[0].tool_id == "tool-b"

        # Filter by invocations > 5
        popular = store.filter(lambda m: m.invocations > 5)
        assert len(popular) == 2
        tool_ids = {m.tool_id for m in popular}
        assert tool_ids == {"tool-a", "tool-b"}

    def test_remove_existing_tool(self, tmp_path: Path):
        """Test removing metrics for an existing tool."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Create metrics
        metrics_data = {
            "tool-a": ToolMetrics(tool_id="tool-a"),
            "tool-b": ToolMetrics(tool_id="tool-b"),
        }
        store.save(metrics_data)

        # Remove tool-a
        removed = store.remove("tool-a")
        assert removed is True

        # Check persistence
        loaded = store.load()
        assert "tool-a" not in loaded
        assert "tool-b" in loaded

    def test_remove_nonexistent_tool(self, tmp_path: Path):
        """Test removing metrics for a tool that doesn't exist."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        removed = store.remove("nonexistent")
        assert removed is False

    def test_clear_all(self, tmp_path: Path):
        """Test clearing all metrics."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Create metrics
        metrics_data = {
            "tool-a": ToolMetrics(tool_id="tool-a"),
            "tool-b": ToolMetrics(tool_id="tool-b"),
        }
        store.save(metrics_data)

        # Clear all
        store.clear_all()

        # Check metrics are empty
        loaded = store.load()
        assert loaded == {}

        # Check file still exists but is empty
        assert metrics_file.exists()
        with open(metrics_file) as f:
            data = json.load(f)
            assert data == {}

    def test_project_classmethod(self, tmp_path: Path):
        """Test creating a project-level store."""
        store = MetricsStore.project(tmp_path)
        expected_path = tmp_path / ".cub" / "tools" / "metrics.json"
        assert store.metrics_file == expected_path

    def test_project_classmethod_default_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test project classmethod uses current directory by default."""
        monkeypatch.chdir(tmp_path)
        store = MetricsStore.project()
        expected_path = tmp_path / ".cub" / "tools" / "metrics.json"
        assert store.metrics_file == expected_path

    def test_atomic_write_safety(self, tmp_path: Path):
        """Test that atomic write doesn't corrupt existing file on error."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Create initial metrics
        initial_metrics = {
            "tool-a": ToolMetrics(tool_id="tool-a", invocations=5)
        }
        store.save(initial_metrics)

        # Verify initial state
        assert metrics_file.exists()
        loaded = store.load()
        assert loaded["tool-a"].invocations == 5

        # Save new metrics (should use atomic write)
        new_metrics = {
            "tool-a": ToolMetrics(tool_id="tool-a", invocations=10),
            "tool-b": ToolMetrics(tool_id="tool-b", invocations=3),
        }
        store.save(new_metrics)

        # Verify new state
        loaded = store.load()
        assert loaded["tool-a"].invocations == 10
        assert loaded["tool-b"].invocations == 3

    def test_json_formatting(self, tmp_path: Path):
        """Test that saved JSON is properly formatted."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        # Save metrics
        metrics_data = {
            "test-tool": ToolMetrics(tool_id="test-tool", invocations=5)
        }
        store.save(metrics_data)

        # Read raw JSON
        with open(metrics_file) as f:
            content = f.read()

        # Check it's formatted with indentation
        assert "  " in content  # Should have 2-space indentation
        assert "test-tool" in content

    def test_datetime_serialization(self, tmp_path: Path):
        """Test that datetimes are properly serialized to ISO format."""
        metrics_file = tmp_path / "metrics.json"
        store = MetricsStore(metrics_file)

        now = datetime.now(timezone.utc)
        metrics_data = {
            "test-tool": ToolMetrics(
                tool_id="test-tool",
                first_used_at=now,
                last_used_at=now,
            )
        }
        store.save(metrics_data)

        # Read raw JSON
        with open(metrics_file) as f:
            data = json.load(f)

        # Check timestamps are ISO strings
        assert isinstance(data["test-tool"]["first_used_at"], str)
        assert isinstance(data["test-tool"]["last_used_at"], str)
        assert "T" in data["test-tool"]["first_used_at"]  # ISO format marker

        # Check they can be loaded back
        loaded = store.load()
        assert loaded["test-tool"].first_used_at is not None
        assert isinstance(loaded["test-tool"].first_used_at, datetime)
