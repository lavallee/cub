"""
Metrics storage layer for reading/writing tool execution metrics.

Manages tool metrics at project-level (.cub/tools/metrics.json). Provides
load, save, and query operations with atomic writes for safety.

Tool metrics track execution statistics (success rates, timing, errors)
to enable the learning loop to evaluate tool reliability and performance.

Storage location:
- Project: .cub/tools/metrics.json

Example:
    # Project-level metrics store
    store = MetricsStore.project()

    # Get metrics for a tool
    metrics = store.get("brave-search")

    # Update metrics after execution
    store.record_execution(result)

    # Get all metrics
    all_metrics = store.list_all()

    # Get metrics for tools with low success rate
    unreliable = store.filter(lambda m: m.success_rate() < 80.0)
"""

import json
import tempfile
from collections.abc import Callable
from pathlib import Path

from cub.core.tools.models import ToolMetrics, ToolResult


class MetricsStore:
    """
    Storage layer for tool execution metrics.

    Manages reading/writing tool metrics from disk with atomic writes
    to prevent corruption during saves. Metrics are stored per-tool in
    a single JSON file at the project level.

    Attributes:
        metrics_file: Path to the metrics JSON file

    Example:
        # Project-level store
        store = MetricsStore.project()

        # Record an execution
        result = ToolResult(...)
        store.record_execution(result)

        # Query metrics
        metrics = store.get("brave-search")
        print(f"Success rate: {metrics.success_rate():.1f}%")
    """

    def __init__(self, metrics_file: Path) -> None:
        """
        Initialize store with a metrics file path.

        Args:
            metrics_file: Path to metrics.json file
        """
        self.metrics_file = Path(metrics_file)

    def load(self) -> dict[str, ToolMetrics]:
        """
        Load all tool metrics from disk.

        Returns an empty dict if the file doesn't exist yet.

        Returns:
            Dictionary mapping tool IDs to ToolMetrics objects

        Raises:
            ValueError: If metrics file is malformed
            json.JSONDecodeError: If metrics file contains invalid JSON
        """
        if not self.metrics_file.exists():
            # Return empty metrics dict
            return {}

        with open(self.metrics_file, encoding="utf-8") as f:
            data = json.load(f)
            # Convert each tool's metrics dict to ToolMetrics object
            return {
                tool_id: ToolMetrics.model_validate(metrics_data)
                for tool_id, metrics_data in data.items()
            }

    def save(self, metrics: dict[str, ToolMetrics]) -> Path:
        """
        Write metrics to disk with atomic write.

        Creates parent directories if they don't exist.
        Uses atomic write (write to temp file, then rename) to prevent corruption.

        Args:
            metrics: Dictionary mapping tool IDs to ToolMetrics objects

        Returns:
            Path to the saved metrics file

        Raises:
            OSError: If file cannot be written
        """
        # Ensure parent directory exists
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

        # Serialize metrics to JSON with nice formatting
        # Use mode='json' to convert datetime objects to ISO strings
        metrics_dict = {
            tool_id: tool_metrics.model_dump(mode="json")
            for tool_id, tool_metrics in metrics.items()
        }
        json_str = json.dumps(metrics_dict, indent=2)

        # Atomic write: write to temp file in same directory, then rename
        # This ensures we don't corrupt the metrics if write fails mid-way
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.metrics_file.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            tmp.write(json_str)
            tmp.flush()
            tmp_path = Path(tmp.name)

        # Atomic rename (replaces existing file)
        tmp_path.replace(self.metrics_file)

        return self.metrics_file

    def get(self, tool_id: str) -> ToolMetrics | None:
        """
        Get metrics for a specific tool.

        Args:
            tool_id: The tool identifier

        Returns:
            ToolMetrics for the tool, or None if not found
        """
        metrics = self.load()
        return metrics.get(tool_id)

    def get_or_create(self, tool_id: str) -> ToolMetrics:
        """
        Get metrics for a tool, creating empty metrics if not found.

        Args:
            tool_id: The tool identifier

        Returns:
            ToolMetrics for the tool (existing or newly created)
        """
        metrics = self.load()
        if tool_id not in metrics:
            metrics[tool_id] = ToolMetrics(tool_id=tool_id)
        return metrics[tool_id]

    def record_execution(self, result: ToolResult) -> ToolMetrics:
        """
        Record a tool execution and update metrics.

        Loads current metrics, updates them with the execution result,
        and saves back to disk atomically.

        Args:
            result: ToolResult from tool execution

        Returns:
            Updated ToolMetrics for the tool

        Raises:
            OSError: If metrics cannot be saved
        """
        # Load current metrics
        metrics = self.load()

        # Get or create metrics for this tool
        if result.tool_id not in metrics:
            metrics[result.tool_id] = ToolMetrics(tool_id=result.tool_id)

        # Update metrics with this execution
        tool_metrics = metrics[result.tool_id]
        tool_metrics.record_execution(result)

        # Save updated metrics
        self.save(metrics)

        return tool_metrics

    def list_all(self) -> list[ToolMetrics]:
        """
        Get metrics for all tools.

        Returns:
            List of ToolMetrics objects for all tools (may be empty)
        """
        metrics = self.load()
        return list(metrics.values())

    def filter(
        self, predicate: Callable[[ToolMetrics], bool]
    ) -> list[ToolMetrics]:
        """
        Filter metrics by a predicate function.

        Args:
            predicate: Function that takes ToolMetrics and returns bool

        Returns:
            List of ToolMetrics that match the predicate

        Example:
            # Get tools with success rate below 80%
            >>> unreliable = store.filter(lambda m: m.success_rate() < 80.0)

            # Get tools with more than 10 invocations
            >>> popular = store.filter(lambda m: m.invocations > 10)

            # Get tools with recent errors
            >>> errored = store.filter(lambda m: len(m.error_types) > 0)
        """
        metrics = self.load()
        return [m for m in metrics.values() if predicate(m)]

    def remove(self, tool_id: str) -> bool:
        """
        Remove metrics for a specific tool.

        Args:
            tool_id: The tool identifier

        Returns:
            True if metrics were removed, False if not found
        """
        metrics = self.load()
        if tool_id in metrics:
            del metrics[tool_id]
            self.save(metrics)
            return True
        return False

    def clear_all(self) -> None:
        """
        Clear all metrics from the store.

        Saves an empty metrics file to disk.
        """
        self.save({})

    @classmethod
    def project(cls, project_dir: Path | None = None) -> "MetricsStore":
        """
        Create a store for the project-level metrics.

        The project-level metrics are stored at:
        - .cub/tools/metrics.json (relative to project root)

        Args:
            project_dir: Project directory (defaults to current directory)

        Returns:
            MetricsStore for project-level metrics
        """
        if project_dir is None:
            project_dir = Path.cwd()
        metrics_file = project_dir / ".cub" / "tools" / "metrics.json"
        return cls(metrics_file)
