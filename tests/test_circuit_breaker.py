"""Tests for CircuitBreaker."""

import asyncio
import time

import pytest

from cub.core.circuit_breaker import CircuitBreaker, CircuitBreakerTrippedError


class TestCircuitBreakerTrippedError:
    """Tests for CircuitBreakerTrippedError exception."""

    def test_exception_message(self) -> None:
        """Test that exception has correct message format."""
        exc = CircuitBreakerTrippedError(timeout_minutes=30)
        assert exc.timeout_minutes == 30
        assert "30 minutes" in str(exc)
        assert "Circuit breaker tripped" in str(exc)
        assert "hung or unresponsive" in str(exc)
        assert exc.is_activity_timeout is False

    def test_exception_attributes(self) -> None:
        """Test exception attributes are set correctly."""
        exc = CircuitBreakerTrippedError(timeout_minutes=15)
        assert exc.timeout_minutes == 15
        assert exc.message == str(exc)

    def test_activity_timeout_message(self) -> None:
        """Test activity timeout has distinct message."""
        exc = CircuitBreakerTrippedError(timeout_minutes=15, is_activity_timeout=True)
        assert exc.timeout_minutes == 15
        assert exc.is_activity_timeout is True
        assert "streaming activity" in str(exc)
        assert "subprocess may be stuck" in str(exc)
        assert "hung or unresponsive" not in str(exc)

    def test_overall_timeout_message(self) -> None:
        """Test overall timeout message is unchanged."""
        exc = CircuitBreakerTrippedError(timeout_minutes=30, is_activity_timeout=False)
        assert exc.is_activity_timeout is False
        assert "hung or unresponsive" in str(exc)
        assert "streaming activity" not in str(exc)


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_init_default_enabled(self) -> None:
        """Test circuit breaker is enabled by default."""
        breaker = CircuitBreaker(timeout_minutes=10)
        assert breaker.timeout_minutes == 10
        assert breaker.enabled is True

    def test_init_explicit_enabled(self) -> None:
        """Test circuit breaker can be explicitly enabled."""
        breaker = CircuitBreaker(timeout_minutes=5, enabled=True)
        assert breaker.enabled is True

    def test_init_disabled(self) -> None:
        """Test circuit breaker can be disabled."""
        breaker = CircuitBreaker(timeout_minutes=5, enabled=False)
        assert breaker.enabled is False

    def test_init_invalid_timeout(self) -> None:
        """Test that timeout < 1 raises ValueError."""
        with pytest.raises(ValueError, match="timeout_minutes must be >= 1"):
            CircuitBreaker(timeout_minutes=0)

        with pytest.raises(ValueError, match="timeout_minutes must be >= 1"):
            CircuitBreaker(timeout_minutes=-5)


class TestCircuitBreakerActivityInit:
    """Tests for CircuitBreaker activity timeout initialization."""

    def test_init_with_activity_timeout(self) -> None:
        """Test activity timeout is stored correctly."""
        breaker = CircuitBreaker(timeout_minutes=30, activity_timeout_minutes=15)
        assert breaker.activity_timeout_minutes == 15

    def test_init_without_activity_timeout(self) -> None:
        """Test activity timeout defaults to None."""
        breaker = CircuitBreaker(timeout_minutes=30)
        assert breaker.activity_timeout_minutes is None

    def test_init_activity_timeout_invalid(self) -> None:
        """Test that activity_timeout_minutes < 1 raises ValueError."""
        with pytest.raises(ValueError, match="activity_timeout_minutes must be >= 1"):
            CircuitBreaker(timeout_minutes=30, activity_timeout_minutes=0)

        with pytest.raises(ValueError, match="activity_timeout_minutes must be >= 1"):
            CircuitBreaker(timeout_minutes=30, activity_timeout_minutes=-1)

    def test_init_activity_timeout_one(self) -> None:
        """Test minimum valid activity timeout."""
        breaker = CircuitBreaker(timeout_minutes=30, activity_timeout_minutes=1)
        assert breaker.activity_timeout_minutes == 1

    def test_init_activity_timeout_none_explicit(self) -> None:
        """Test explicitly setting activity timeout to None."""
        breaker = CircuitBreaker(timeout_minutes=30, activity_timeout_minutes=None)
        assert breaker.activity_timeout_minutes is None


class TestCircuitBreakerHeartbeat:
    """Tests for CircuitBreaker.heartbeat() method."""

    def test_heartbeat_records_timestamp(self) -> None:
        """Test that heartbeat updates _last_heartbeat."""
        breaker = CircuitBreaker(timeout_minutes=30, activity_timeout_minutes=15)
        before = time.monotonic()
        breaker.heartbeat()
        after = time.monotonic()
        assert before <= breaker._last_heartbeat <= after
        assert breaker._heartbeat_received is True

    def test_heartbeat_updates_on_subsequent_calls(self) -> None:
        """Test that subsequent heartbeats update the timestamp."""
        breaker = CircuitBreaker(timeout_minutes=30, activity_timeout_minutes=15)
        breaker.heartbeat()
        first = breaker._last_heartbeat
        time.sleep(0.01)
        breaker.heartbeat()
        assert breaker._last_heartbeat > first

    def test_heartbeat_received_flag(self) -> None:
        """Test that heartbeat sets the received flag."""
        breaker = CircuitBreaker(timeout_minutes=30, activity_timeout_minutes=15)
        assert breaker._heartbeat_received is False
        breaker.heartbeat()
        assert breaker._heartbeat_received is True


class TestCircuitBreakerExecute:
    """Tests for CircuitBreaker.execute()."""

    @pytest.mark.asyncio
    async def test_execute_success_fast(self) -> None:
        """Test successful execution that completes quickly."""
        breaker = CircuitBreaker(timeout_minutes=1)

        async def quick_task() -> str:
            await asyncio.sleep(0.01)
            return "success"

        result = await breaker.execute(quick_task())
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_success_with_value(self) -> None:
        """Test successful execution returns correct value."""
        breaker = CircuitBreaker(timeout_minutes=1)

        async def return_value() -> int:
            return 42

        result = await breaker.execute(return_value())
        assert result == 42

    @pytest.mark.asyncio
    async def test_execute_timeout_trips_breaker(self) -> None:
        """Test that timeout causes CircuitBreakerTrippedError."""
        breaker = CircuitBreaker(
            timeout_minutes=1,
            _timeout_seconds_override=0.1,
        )

        async def slow_task() -> str:
            await asyncio.sleep(5)
            return "should not reach here"

        with pytest.raises(CircuitBreakerTrippedError) as exc_info:
            await breaker.execute(slow_task())

        assert exc_info.value.timeout_minutes == 1
        assert "Circuit breaker tripped" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_disabled_no_timeout(self) -> None:
        """Test that disabled breaker doesn't enforce timeout."""
        breaker = CircuitBreaker(timeout_minutes=1, enabled=False)

        async def task() -> str:
            await asyncio.sleep(0.01)
            return "completed"

        # Should complete without timeout
        result = await breaker.execute(task())
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_execute_propagates_exceptions(self) -> None:
        """Test that exceptions from coroutine are propagated."""
        breaker = CircuitBreaker(timeout_minutes=1)

        async def failing_task() -> None:
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await breaker.execute(failing_task())

    @pytest.mark.asyncio
    async def test_execute_propagates_cancellation(self) -> None:
        """Test that CancelledError is propagated."""
        breaker = CircuitBreaker(timeout_minutes=1)

        async def cancellable_task() -> None:
            await asyncio.sleep(10)

        # Create task and cancel it
        task = asyncio.create_task(breaker.execute(cancellable_task()))
        await asyncio.sleep(0.01)  # Let it start
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_execute_short_timeout(self) -> None:
        """Test with minimum timeout (1 minute)."""
        breaker = CircuitBreaker(timeout_minutes=1)

        async def instant_task() -> str:
            return "done"

        result = await breaker.execute(instant_task())
        assert result == "done"

    @pytest.mark.asyncio
    async def test_execute_long_timeout(self) -> None:
        """Test with long timeout value."""
        breaker = CircuitBreaker(timeout_minutes=120)

        async def quick_task() -> str:
            await asyncio.sleep(0.01)
            return "finished"

        result = await breaker.execute(quick_task())
        assert result == "finished"


class TestCircuitBreakerRealTimeout:
    """
    Tests that actually wait for timeout to occur.

    Uses _timeout_seconds_override to keep tests fast while still
    exercising the real timeout path.
    """

    @pytest.mark.asyncio
    async def test_actual_timeout_behavior(self) -> None:
        """Test that timeout actually occurs after expected time."""
        breaker = CircuitBreaker(
            timeout_minutes=1,
            _timeout_seconds_override=0.5,
        )

        async def very_slow_task() -> str:
            await asyncio.sleep(10)
            return "should not complete"

        start_time = asyncio.get_event_loop().time()

        with pytest.raises(CircuitBreakerTrippedError):
            await breaker.execute(very_slow_task())

        elapsed = asyncio.get_event_loop().time() - start_time

        # Should have timed out around 0.5 seconds (allow some margin)
        assert 0.3 < elapsed < 2.0, f"Expected ~0.5s timeout, got {elapsed}s"


class TestCircuitBreakerActivityMonitoring:
    """Tests for activity-based (heartbeat) timeout monitoring."""

    @pytest.mark.asyncio
    async def test_regular_heartbeats_completes_normally(self) -> None:
        """Task with regular heartbeats should complete without tripping."""
        breaker = CircuitBreaker(
            timeout_minutes=30,
            activity_timeout_minutes=15,
            _timeout_seconds_override=5.0,
            _activity_timeout_seconds_override=0.5,
        )

        async def task_with_heartbeats() -> str:
            for _ in range(5):
                await asyncio.sleep(0.05)
                breaker.heartbeat()
            return "completed"

        result = await breaker.execute(task_with_heartbeats())
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_heartbeats_stop_trips_activity_timeout(self) -> None:
        """Task that sends heartbeats then stops should trip activity timeout."""
        breaker = CircuitBreaker(
            timeout_minutes=30,
            activity_timeout_minutes=15,
            _timeout_seconds_override=10.0,
            _activity_timeout_seconds_override=0.3,
        )

        async def task_heartbeats_then_stuck() -> str:
            # Send a few heartbeats
            for _ in range(3):
                await asyncio.sleep(0.02)
                breaker.heartbeat()
            # Then go silent (simulate stuck subprocess)
            await asyncio.sleep(10)
            return "should not reach here"

        with pytest.raises(CircuitBreakerTrippedError) as exc_info:
            await breaker.execute(task_heartbeats_then_stuck())

        assert exc_info.value.is_activity_timeout is True
        assert "streaming activity" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_heartbeats_falls_through_to_overall_timeout(self) -> None:
        """Non-streaming task (no heartbeats) should use overall timeout."""
        breaker = CircuitBreaker(
            timeout_minutes=30,
            activity_timeout_minutes=15,
            _timeout_seconds_override=0.3,
            _activity_timeout_seconds_override=0.1,
        )

        async def task_no_heartbeats() -> str:
            await asyncio.sleep(10)
            return "should not reach here"

        with pytest.raises(CircuitBreakerTrippedError) as exc_info:
            await breaker.execute(task_no_heartbeats())

        # Should be overall timeout, NOT activity timeout
        assert exc_info.value.is_activity_timeout is False
        assert exc_info.value.timeout_minutes == 30

    @pytest.mark.asyncio
    async def test_single_heartbeat_then_stuck(self) -> None:
        """Single heartbeat then nothing should trip activity timeout."""
        breaker = CircuitBreaker(
            timeout_minutes=30,
            activity_timeout_minutes=15,
            _timeout_seconds_override=10.0,
            _activity_timeout_seconds_override=0.3,
        )

        async def task_one_heartbeat_then_stuck() -> str:
            breaker.heartbeat()
            await asyncio.sleep(10)
            return "should not reach here"

        with pytest.raises(CircuitBreakerTrippedError) as exc_info:
            await breaker.execute(task_one_heartbeat_then_stuck())

        assert exc_info.value.is_activity_timeout is True

    @pytest.mark.asyncio
    async def test_no_activity_timeout_backward_compat(self) -> None:
        """Without activity_timeout_minutes, behavior is identical to original."""
        breaker = CircuitBreaker(
            timeout_minutes=1,
            _timeout_seconds_override=0.2,
        )
        assert breaker.activity_timeout_minutes is None

        async def slow_task() -> str:
            await asyncio.sleep(5)
            return "should not reach here"

        with pytest.raises(CircuitBreakerTrippedError) as exc_info:
            await breaker.execute(slow_task())

        assert exc_info.value.timeout_minutes == 1
        assert exc_info.value.is_activity_timeout is False

    @pytest.mark.asyncio
    async def test_heartbeat_state_resets_between_executions(self) -> None:
        """Heartbeat state should reset at the start of each execute() call."""
        breaker = CircuitBreaker(
            timeout_minutes=30,
            activity_timeout_minutes=15,
            _timeout_seconds_override=5.0,
            _activity_timeout_seconds_override=0.5,
        )

        # First execution: send heartbeats
        async def task1() -> str:
            breaker.heartbeat()
            return "first"

        result = await breaker.execute(task1())
        assert result == "first"

        # After first execution, heartbeat_received should be reset
        # by the second execute() call
        async def task2() -> str:
            # No heartbeats — should fall through to overall timeout
            # not be affected by first execution's heartbeats
            return "second"

        result = await breaker.execute(task2())
        assert result == "second"

    @pytest.mark.asyncio
    async def test_activity_timeout_timing(self) -> None:
        """Test that activity timeout fires approximately at the right time."""
        breaker = CircuitBreaker(
            timeout_minutes=30,
            activity_timeout_minutes=15,
            _timeout_seconds_override=10.0,
            _activity_timeout_seconds_override=0.4,
        )

        async def task() -> str:
            breaker.heartbeat()
            # Go silent — should trip after ~0.4s
            await asyncio.sleep(10)
            return "should not reach"

        start = asyncio.get_event_loop().time()

        with pytest.raises(CircuitBreakerTrippedError) as exc_info:
            await breaker.execute(task())

        elapsed = asyncio.get_event_loop().time() - start
        assert exc_info.value.is_activity_timeout is True
        # Activity timeout should fire roughly after 0.4s
        # Allow generous margin for CI environments
        assert 0.2 < elapsed < 3.0, f"Expected ~0.4s activity timeout, got {elapsed}s"


class TestCircuitBreakerEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_execute_with_zero_delay_task(self) -> None:
        """Test execution of task with no delay."""
        breaker = CircuitBreaker(timeout_minutes=1)

        async def no_delay_task() -> str:
            return "instant"

        result = await breaker.execute(no_delay_task())
        assert result == "instant"

    @pytest.mark.asyncio
    async def test_execute_multiple_times(self) -> None:
        """Test circuit breaker can be reused for multiple executions."""
        breaker = CircuitBreaker(timeout_minutes=1)

        async def task(value: int) -> int:
            await asyncio.sleep(0.01)
            return value

        result1 = await breaker.execute(task(1))
        result2 = await breaker.execute(task(2))
        result3 = await breaker.execute(task(3))

        assert result1 == 1
        assert result2 == 2
        assert result3 == 3

    @pytest.mark.asyncio
    async def test_execute_with_complex_return_type(self) -> None:
        """Test execution with complex return types."""
        breaker = CircuitBreaker(timeout_minutes=1)

        async def complex_task() -> dict[str, object]:
            return {"status": "ok", "data": [1, 2, 3], "nested": {"key": "value"}}

        result = await breaker.execute(complex_task())
        assert result["status"] == "ok"
        assert result["data"] == [1, 2, 3]
        assert result["nested"]["key"] == "value"  # type: ignore

    @pytest.mark.asyncio
    async def test_disabled_breaker_with_long_task(self) -> None:
        """Test disabled breaker allows long-running tasks."""
        breaker = CircuitBreaker(timeout_minutes=1, enabled=False)

        async def somewhat_long_task() -> str:
            # This would timeout if breaker was enabled
            await asyncio.sleep(0.1)
            return "completed anyway"

        result = await breaker.execute(somewhat_long_task())
        assert result == "completed anyway"

    @pytest.mark.asyncio
    async def test_activity_with_disabled_breaker(self) -> None:
        """Test disabled breaker ignores activity timeout settings."""
        breaker = CircuitBreaker(
            timeout_minutes=1,
            enabled=False,
            activity_timeout_minutes=1,
        )

        async def task() -> str:
            await asyncio.sleep(0.01)
            return "done"

        result = await breaker.execute(task())
        assert result == "done"

    @pytest.mark.asyncio
    async def test_exception_propagation_with_activity_timeout(self) -> None:
        """Test that exceptions from main task propagate with activity timeout."""
        breaker = CircuitBreaker(
            timeout_minutes=30,
            activity_timeout_minutes=15,
            _timeout_seconds_override=5.0,
            _activity_timeout_seconds_override=1.0,
        )

        async def failing_task() -> None:
            breaker.heartbeat()
            raise ValueError("expected error")

        with pytest.raises(ValueError, match="expected error"):
            await breaker.execute(failing_task())
