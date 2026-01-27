"""Tests for CircuitBreaker."""

import asyncio

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

    def test_exception_attributes(self) -> None:
        """Test exception attributes are set correctly."""
        exc = CircuitBreakerTrippedError(timeout_minutes=15)
        assert exc.timeout_minutes == 15
        assert exc.message == str(exc)


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
        # Use very short timeout for testing (1 minute = 60 seconds)
        # We'll simulate a task that takes longer
        breaker = CircuitBreaker(timeout_minutes=1)

        async def slow_task() -> str:
            # Sleep for 90 seconds (longer than 60 second timeout)
            await asyncio.sleep(90)
            return "should not reach here"

        # Should trip after 60 seconds
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

    These tests use very short timeouts to test actual timeout behavior
    without making tests too slow. We use fractional minutes (which get
    converted to seconds) to keep tests fast.
    """

    @pytest.mark.asyncio
    async def test_actual_timeout_behavior(self) -> None:
        """Test that timeout actually occurs after expected time."""
        # Use 1 minute = 60 seconds
        # We'll test with a task that takes slightly longer
        breaker = CircuitBreaker(timeout_minutes=1)

        # This would take 2 minutes, should timeout at 1 minute
        async def very_slow_task() -> str:
            await asyncio.sleep(120)
            return "should not complete"

        start_time = asyncio.get_event_loop().time()

        with pytest.raises(CircuitBreakerTrippedError):
            await breaker.execute(very_slow_task())

        elapsed = asyncio.get_event_loop().time() - start_time

        # Should have timed out around 60 seconds (allow some margin)
        # We don't assert exact time due to test execution overhead
        assert 55 < elapsed < 65, f"Expected ~60s timeout, got {elapsed}s"


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
