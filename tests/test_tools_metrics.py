"""Tests for ToolMetrics model."""

from datetime import datetime, timezone

import pytest

from cub.core.tools.models import AdapterType, ToolMetrics, ToolResult


class TestToolMetrics:
    """Tests for ToolMetrics model."""

    def test_create_empty_metrics(self) -> None:
        """Test creating empty metrics for a new tool."""
        metrics = ToolMetrics(tool_id="test-tool")

        assert metrics.tool_id == "test-tool"
        assert metrics.invocations == 0
        assert metrics.successes == 0
        assert metrics.failures == 0
        assert metrics.total_duration_ms == 0
        assert metrics.min_duration_ms is None
        assert metrics.max_duration_ms is None
        assert metrics.avg_duration_ms == 0.0
        assert metrics.error_types == {}
        assert metrics.last_used_at is None
        assert metrics.first_used_at is None

    def test_create_metrics_with_data(self) -> None:
        """Test creating metrics with initial data."""
        now = datetime.now(timezone.utc)
        metrics = ToolMetrics(
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

        assert metrics.tool_id == "test-tool"
        assert metrics.invocations == 10
        assert metrics.successes == 8
        assert metrics.failures == 2
        assert metrics.total_duration_ms == 5000
        assert metrics.min_duration_ms == 100
        assert metrics.max_duration_ms == 1000
        assert metrics.avg_duration_ms == 500.0
        assert metrics.error_types == {"timeout": 1, "auth": 1}
        assert metrics.last_used_at == now
        assert metrics.first_used_at == now

    def test_success_rate_with_no_invocations(self) -> None:
        """Test success_rate returns 0 when there are no invocations."""
        metrics = ToolMetrics(tool_id="test-tool")
        assert metrics.success_rate() == 0.0

    def test_success_rate_with_all_successes(self) -> None:
        """Test success_rate with 100% success."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=10,
            failures=0,
        )
        assert metrics.success_rate() == 100.0

    def test_success_rate_with_all_failures(self) -> None:
        """Test success_rate with 0% success."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=0,
            failures=10,
        )
        assert metrics.success_rate() == 0.0

    def test_success_rate_with_mixed_results(self) -> None:
        """Test success_rate with mixed success/failure."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=7,
            failures=3,
        )
        assert metrics.success_rate() == 70.0

    def test_failure_rate_with_no_invocations(self) -> None:
        """Test failure_rate returns 0 when there are no invocations."""
        metrics = ToolMetrics(tool_id="test-tool")
        assert metrics.failure_rate() == 0.0

    def test_failure_rate_with_all_failures(self) -> None:
        """Test failure_rate with 100% failure."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=0,
            failures=10,
        )
        assert metrics.failure_rate() == 100.0

    def test_failure_rate_with_all_successes(self) -> None:
        """Test failure_rate with 0% failure."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=10,
            failures=0,
        )
        assert metrics.failure_rate() == 0.0

    def test_failure_rate_with_mixed_results(self) -> None:
        """Test failure_rate with mixed success/failure."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=6,
            failures=4,
        )
        assert metrics.failure_rate() == 40.0

    def test_record_execution_first_success(self) -> None:
        """Test recording the first successful execution."""
        metrics = ToolMetrics(tool_id="test-tool")

        now = datetime.now(timezone.utc)
        result = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={"result": "success"},
            started_at=now,
            duration_ms=250,
            adapter_type=AdapterType.HTTP,
        )

        metrics.record_execution(result)

        assert metrics.invocations == 1
        assert metrics.successes == 1
        assert metrics.failures == 0
        assert metrics.total_duration_ms == 250
        assert metrics.min_duration_ms == 250
        assert metrics.max_duration_ms == 250
        assert metrics.avg_duration_ms == 250.0
        assert metrics.error_types == {}
        assert metrics.first_used_at == now
        assert metrics.last_used_at == now

    def test_record_execution_first_failure(self) -> None:
        """Test recording the first failed execution."""
        metrics = ToolMetrics(tool_id="test-tool")

        now = datetime.now(timezone.utc)
        result = ToolResult(
            tool_id="test-tool",
            action="test",
            success=False,
            output=None,
            error="Connection timeout",
            error_type="timeout",
            started_at=now,
            duration_ms=5000,
            adapter_type=AdapterType.HTTP,
        )

        metrics.record_execution(result)

        assert metrics.invocations == 1
        assert metrics.successes == 0
        assert metrics.failures == 1
        assert metrics.total_duration_ms == 5000
        assert metrics.min_duration_ms == 5000
        assert metrics.max_duration_ms == 5000
        assert metrics.avg_duration_ms == 5000.0
        assert metrics.error_types == {"timeout": 1}
        assert metrics.first_used_at == now
        assert metrics.last_used_at == now

    def test_record_multiple_executions(self) -> None:
        """Test recording multiple executions updates all metrics correctly."""
        metrics = ToolMetrics(tool_id="test-tool")

        base_time = datetime.now(timezone.utc)

        # First execution: success (100ms)
        result1 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={"result": "success"},
            started_at=base_time,
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result1)

        # Second execution: success (300ms)
        result2 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={"result": "success"},
            started_at=base_time,
            duration_ms=300,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result2)

        # Third execution: failure (200ms)
        result3 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=False,
            output=None,
            error="Auth error",
            error_type="auth",
            started_at=base_time,
            duration_ms=200,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result3)

        # Check final metrics
        assert metrics.invocations == 3
        assert metrics.successes == 2
        assert metrics.failures == 1
        assert metrics.total_duration_ms == 600
        assert metrics.min_duration_ms == 100
        assert metrics.max_duration_ms == 300
        assert metrics.avg_duration_ms == 200.0
        assert metrics.error_types == {"auth": 1}
        assert metrics.success_rate() == pytest.approx(66.666, rel=1e-2)
        assert metrics.failure_rate() == pytest.approx(33.333, rel=1e-2)

    def test_record_execution_multiple_error_types(self) -> None:
        """Test recording multiple error types."""
        metrics = ToolMetrics(tool_id="test-tool")

        base_time = datetime.now(timezone.utc)

        # Record different error types
        error_types = [
            "timeout",   # 1st timeout error
            "timeout",   # 2nd timeout error
            "auth",      # 1st auth error
            "network",   # 1st network error
        ]

        for error_type in error_types:
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=False,
                output=None,
                error=f"{error_type} error",
                error_type=error_type,
                started_at=base_time,
                duration_ms=100,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # Check error type counts
        assert metrics.error_types == {"timeout": 2, "auth": 1, "network": 1}
        assert metrics.failures == 4
        assert metrics.invocations == 4

    def test_record_execution_timing_updates(self) -> None:
        """Test that timing statistics are updated correctly."""
        metrics = ToolMetrics(tool_id="test-tool")

        base_time = datetime.now(timezone.utc)
        durations = [500, 100, 1000, 250, 750]

        for duration in durations:
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=True,
                output={"result": "success"},
                started_at=base_time,
                duration_ms=duration,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # Check timing statistics
        assert metrics.invocations == 5
        assert metrics.total_duration_ms == 2600
        assert metrics.min_duration_ms == 100
        assert metrics.max_duration_ms == 1000
        assert metrics.avg_duration_ms == 520.0

    def test_record_execution_preserves_first_timestamp(self) -> None:
        """Test that first_used_at is set once and never changes."""
        metrics = ToolMetrics(tool_id="test-tool")

        first_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        second_time = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

        # First execution
        result1 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={"result": "success"},
            started_at=first_time,
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result1)

        # Second execution
        result2 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={"result": "success"},
            started_at=second_time,
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result2)

        # first_used_at should remain the first timestamp
        assert metrics.first_used_at == first_time
        assert metrics.last_used_at == second_time

    def test_record_execution_updates_last_timestamp(self) -> None:
        """Test that last_used_at is updated with each execution."""
        metrics = ToolMetrics(tool_id="test-tool")

        timestamps = [
            datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
        ]

        for ts in timestamps:
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=True,
                output={"result": "success"},
                started_at=ts,
                duration_ms=100,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # last_used_at should be the most recent timestamp
        assert metrics.last_used_at == timestamps[-1]
        assert metrics.first_used_at == timestamps[0]

    def test_timestamp_normalization_with_naive_datetime(self) -> None:
        """Test that naive datetimes are normalized to UTC."""
        # Create metrics with naive datetime
        naive_dt = datetime(2024, 1, 1, 12, 0, 0)

        metrics = ToolMetrics(
            tool_id="test-tool",
            first_used_at=naive_dt,
            last_used_at=naive_dt,
        )

        # Should be normalized to UTC
        assert metrics.first_used_at is not None
        assert metrics.first_used_at.tzinfo == timezone.utc
        assert metrics.last_used_at is not None
        assert metrics.last_used_at.tzinfo == timezone.utc

    def test_timestamp_normalization_with_iso_string(self) -> None:
        """Test that ISO string timestamps are parsed correctly."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            first_used_at="2024-01-01T12:00:00Z",  # type: ignore[arg-type]
            last_used_at="2024-01-02T12:00:00+00:00",  # type: ignore[arg-type]
        )

        # Should be parsed and normalized
        assert metrics.first_used_at is not None
        assert isinstance(metrics.first_used_at, datetime)
        assert metrics.first_used_at.tzinfo == timezone.utc
        assert metrics.last_used_at is not None
        assert isinstance(metrics.last_used_at, datetime)
        assert metrics.last_used_at.tzinfo == timezone.utc

    def test_timestamp_normalization_with_none(self) -> None:
        """Test that None timestamps are preserved."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            first_used_at=None,
            last_used_at=None,
        )

        assert metrics.first_used_at is None
        assert metrics.last_used_at is None

    def test_validation_tool_id_required(self) -> None:
        """Test that tool_id is required."""
        with pytest.raises(ValueError, match="Field required"):
            ToolMetrics()  # type: ignore

    def test_validation_tool_id_non_empty(self) -> None:
        """Test that tool_id cannot be empty."""
        with pytest.raises(ValueError, match="at least 1 character"):
            ToolMetrics(tool_id="")

    def test_validation_invocations_non_negative(self) -> None:
        """Test that invocations cannot be negative."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            ToolMetrics(tool_id="test-tool", invocations=-1)

    def test_validation_successes_non_negative(self) -> None:
        """Test that successes cannot be negative."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            ToolMetrics(tool_id="test-tool", successes=-1)

    def test_validation_failures_non_negative(self) -> None:
        """Test that failures cannot be negative."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            ToolMetrics(tool_id="test-tool", failures=-1)

    def test_validation_total_duration_non_negative(self) -> None:
        """Test that total_duration_ms cannot be negative."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            ToolMetrics(tool_id="test-tool", total_duration_ms=-1)

    def test_validation_avg_duration_non_negative(self) -> None:
        """Test that avg_duration_ms cannot be negative."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            ToolMetrics(tool_id="test-tool", avg_duration_ms=-1.0)

    def test_serialization_to_dict(self) -> None:
        """Test serializing metrics to dictionary."""
        now = datetime.now(timezone.utc)
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=8,
            failures=2,
            first_used_at=now,
            last_used_at=now,
        )

        data = metrics.model_dump()

        assert data["tool_id"] == "test-tool"
        assert data["invocations"] == 10
        assert data["successes"] == 8
        assert data["failures"] == 2
        assert isinstance(data["first_used_at"], datetime)
        assert isinstance(data["last_used_at"], datetime)

    def test_serialization_to_json_dict(self) -> None:
        """Test serializing metrics to JSON-compatible dictionary."""
        now = datetime.now(timezone.utc)
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=8,
            failures=2,
            first_used_at=now,
            last_used_at=now,
        )

        data = metrics.model_dump(mode="json")

        assert data["tool_id"] == "test-tool"
        assert data["invocations"] == 10
        # Timestamps should be ISO strings in JSON mode
        assert isinstance(data["first_used_at"], str)
        assert isinstance(data["last_used_at"], str)


class TestDegradationDetection:
    """Tests for detecting tool performance degradation over time."""

    def test_detect_degradation_from_high_to_low_success_rate(self) -> None:
        """Test detecting degradation when success rate drops significantly."""
        metrics = ToolMetrics(tool_id="test-tool")

        base_time = datetime.now(timezone.utc)

        # Record 10 successful executions (100% success)
        for i in range(10):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=True,
                output={"result": "success"},
                started_at=base_time,
                duration_ms=100,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # At this point, success rate is 100%
        assert metrics.success_rate() == 100.0

        # Record 10 failed executions (degradation)
        for i in range(10):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=False,
                output=None,
                error="Service degraded",
                error_type="server_error",
                started_at=base_time,
                duration_ms=100,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # Success rate should now be 50%
        assert metrics.success_rate() == 50.0
        assert metrics.failures == 10
        assert metrics.error_types == {"server_error": 10}

    def test_detect_timing_degradation(self) -> None:
        """Test detecting performance degradation through slower execution times."""
        metrics = ToolMetrics(tool_id="test-tool")

        base_time = datetime.now(timezone.utc)

        # Record 5 fast executions (100-180ms)
        for i in range(5):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=True,
                output={"result": "success"},
                started_at=base_time,
                duration_ms=100 + (i * 20),
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # Average should be 140ms (100+120+140+160+180 = 700 / 5)
        assert metrics.avg_duration_ms == 140.0
        assert metrics.min_duration_ms == 100
        assert metrics.max_duration_ms == 180

        # Record 5 slow executions (1000-2000ms) - degradation
        for i in range(5):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=True,
                output={"result": "success"},
                started_at=base_time,
                duration_ms=1000 + (i * 250),
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # Average should now be significantly higher
        # Total: 700 (first 5) + 7500 (next 5) = 8200ms / 10 = 820ms
        assert metrics.avg_duration_ms == 820.0
        assert metrics.max_duration_ms == 2000
        # Degradation detected: avg duration increased from 140ms to 820ms

    def test_detect_error_pattern_emergence(self) -> None:
        """Test detecting when new error types start appearing."""
        metrics = ToolMetrics(tool_id="test-tool")

        base_time = datetime.now(timezone.utc)

        # Initial period: all successes
        for i in range(10):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=True,
                output={"result": "success"},
                started_at=base_time,
                duration_ms=100,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        assert len(metrics.error_types) == 0

        # Degradation: timeout errors start appearing
        for i in range(3):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=False,
                output=None,
                error="Request timeout",
                error_type="timeout",
                started_at=base_time,
                duration_ms=5000,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # New error pattern detected
        assert "timeout" in metrics.error_types
        assert metrics.error_types["timeout"] == 3
        assert metrics.success_rate() == pytest.approx(76.923, rel=1e-2)

    def test_detect_increasing_error_frequency(self) -> None:
        """Test detecting when error frequency increases over time."""
        metrics = ToolMetrics(tool_id="test-tool")

        base_time = datetime.now(timezone.utc)

        # Phase 1: Rare errors (1 failure in 10)
        for i in range(10):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=(i != 9),  # Only last one fails
                output={"result": "success"} if i != 9 else None,
                error="Error" if i == 9 else None,
                error_type="intermittent" if i == 9 else None,
                started_at=base_time,
                duration_ms=100,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        initial_success_rate = metrics.success_rate()
        assert initial_success_rate == 90.0

        # Phase 2: Frequent errors (5 failures in 10)
        for i in range(10):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=(i % 2 == 0),  # Every other one fails
                output={"result": "success"} if i % 2 == 0 else None,
                error="Error" if i % 2 != 0 else None,
                error_type="intermittent" if i % 2 != 0 else None,
                started_at=base_time,
                duration_ms=100,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # Overall success rate should drop
        final_success_rate = metrics.success_rate()
        assert final_success_rate == 70.0
        assert metrics.error_types["intermittent"] == 6
        # Degradation: error frequency increased from 10% to 30% overall

    def test_stable_performance_no_degradation(self) -> None:
        """Test that stable performance doesn't trigger degradation indicators."""
        metrics = ToolMetrics(tool_id="test-tool")

        base_time = datetime.now(timezone.utc)

        # Record 20 consistent successful executions
        for i in range(20):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=True,
                output={"result": "success"},
                started_at=base_time,
                duration_ms=100 + (i % 5),  # Slight variance (100-104ms)
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # Performance should be stable
        assert metrics.success_rate() == 100.0
        assert metrics.min_duration_ms == 100
        assert metrics.max_duration_ms == 104
        assert metrics.avg_duration_ms == 102.0
        assert len(metrics.error_types) == 0

    def test_recovery_after_degradation(self) -> None:
        """Test metrics after tool recovers from degradation."""
        metrics = ToolMetrics(tool_id="test-tool")

        base_time = datetime.now(timezone.utc)

        # Phase 1: Good performance (10 successes)
        for i in range(10):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=True,
                output={"result": "success"},
                started_at=base_time,
                duration_ms=100,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # Phase 2: Degradation (10 failures)
        for i in range(10):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=False,
                output=None,
                error="Service down",
                error_type="server_error",
                started_at=base_time,
                duration_ms=100,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        assert metrics.success_rate() == 50.0

        # Phase 3: Recovery (10 successes)
        for i in range(10):
            result = ToolResult(
                tool_id="test-tool",
                action="test",
                success=True,
                output={"result": "success"},
                started_at=base_time,
                duration_ms=100,
                adapter_type=AdapterType.HTTP,
            )
            metrics.record_execution(result)

        # Overall success rate should improve
        assert metrics.success_rate() == pytest.approx(66.666, rel=1e-2)
        assert metrics.invocations == 30
        assert metrics.successes == 20
        assert metrics.failures == 10
