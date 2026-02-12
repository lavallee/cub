"""
Circuit breaker for detecting and preventing harness stagnation.

This module provides the CircuitBreaker class that wraps harness execution
with timeout monitoring. Two timeout mechanisms are supported:

1. **Overall timeout** (existing): A hard wall-clock limit on total execution time.
2. **Activity timeout** (new): Trips when no heartbeat is received for a configured
   period. During streaming, each chunk calls ``heartbeat()``; a gap longer than
   the activity timeout almost certainly means a stuck subprocess (e.g., a deadlocked
   ``pytest`` run).

This prevents infinite hangs where the harness becomes unresponsive but the
process continues running indefinitely.

Example:
    >>> import asyncio
    >>> from cub.core.circuit_breaker import CircuitBreaker, CircuitBreakerTrippedError
    >>>
    >>> async def long_running_task():
    ...     await asyncio.sleep(60)  # Simulate work
    ...     return "completed"
    >>>
    >>> breaker = CircuitBreaker(timeout_minutes=1, enabled=True)
    >>> try:
    ...     result = await breaker.execute(long_running_task())
    ... except CircuitBreakerTrippedError as e:
    ...     print(f"Stagnation detected: {e}")
"""

import asyncio
import time
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")


class CircuitBreakerTrippedError(Exception):
    """
    Exception raised when circuit breaker detects stagnation.

    Raised when a coroutine exceeds the configured timeout period without
    completing. This indicates the harness has likely hung or become unresponsive.

    Attributes:
        timeout_minutes: The timeout period that was exceeded
        is_activity_timeout: True if tripped by activity (heartbeat) timeout,
            False if tripped by overall wall-clock timeout
        message: Human-readable error message
    """

    def __init__(
        self,
        timeout_minutes: int,
        *,
        is_activity_timeout: bool = False,
    ) -> None:
        """
        Initialize a circuit breaker tripped exception.

        Args:
            timeout_minutes: The timeout period that was exceeded
            is_activity_timeout: Whether this was an activity-based timeout
        """
        self.timeout_minutes = timeout_minutes
        self.is_activity_timeout = is_activity_timeout

        if is_activity_timeout:
            self.message = (
                f"Circuit breaker tripped: No streaming activity for "
                f"{timeout_minutes} minutes. A subprocess may be stuck."
            )
        else:
            self.message = (
                f"Circuit breaker tripped: No activity for {timeout_minutes} minutes. "
                f"The harness appears to be hung or unresponsive."
            )
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        return self.message


class CircuitBreaker:
    """
    Circuit breaker for monitoring harness execution and detecting stagnation.

    Wraps async coroutines with a timeout. If the coroutine doesn't complete
    within the configured timeout period, the circuit breaker trips and raises
    CircuitBreakerTrippedError.

    Supports two timeout modes:
    - **Overall timeout**: Hard wall-clock limit (``timeout_minutes``).
    - **Activity timeout**: Trips when ``heartbeat()`` hasn't been called for
      ``activity_timeout_minutes``. Callers (streaming loops) call ``heartbeat()``
      on each chunk. If heartbeat is never called (non-streaming), the activity
      watchdog is inactive and only the overall timeout applies.

    The circuit breaker can be disabled for testing or debugging purposes.

    Attributes:
        timeout_minutes: Maximum minutes of inactivity before tripping (overall)
        activity_timeout_minutes: Minutes without a heartbeat before tripping
        enabled: Whether the circuit breaker is active

    Example:
        >>> import asyncio
        >>> from cub.core.circuit_breaker import CircuitBreaker
        >>>
        >>> async def my_task():
        ...     await asyncio.sleep(2)
        ...     return "done"
        >>>
        >>> breaker = CircuitBreaker(timeout_minutes=1)
        >>> result = await breaker.execute(my_task())
        >>> print(result)
        done
    """

    def __init__(
        self,
        timeout_minutes: int,
        enabled: bool = True,
        activity_timeout_minutes: int | None = None,
        _timeout_seconds_override: float | None = None,
        _activity_timeout_seconds_override: float | None = None,
    ) -> None:
        """
        Initialize a circuit breaker.

        Args:
            timeout_minutes: Maximum minutes to wait before tripping (must be >= 1)
            enabled: Whether to enforce timeout (default: True)
            activity_timeout_minutes: Minutes without a heartbeat before tripping.
                None disables activity-based monitoring.
            _timeout_seconds_override: Override overall timeout in seconds (testing only)
            _activity_timeout_seconds_override: Override activity timeout in seconds
                (testing only)

        Raises:
            ValueError: If timeout_minutes < 1
            ValueError: If activity_timeout_minutes < 1 (when set)
        """
        if timeout_minutes < 1:
            raise ValueError(f"timeout_minutes must be >= 1, got {timeout_minutes}")

        if activity_timeout_minutes is not None and activity_timeout_minutes < 1:
            raise ValueError(
                f"activity_timeout_minutes must be >= 1, got {activity_timeout_minutes}"
            )

        self.timeout_minutes = timeout_minutes
        self.enabled = enabled
        self.activity_timeout_minutes = activity_timeout_minutes
        self._timeout_seconds_override = _timeout_seconds_override
        self._activity_timeout_seconds_override = _activity_timeout_seconds_override

        # Heartbeat state (reset at start of each execute() call)
        self._last_heartbeat: float = 0.0
        self._heartbeat_received: bool = False

    def heartbeat(self) -> None:
        """
        Record a heartbeat from the streaming loop.

        Call this on every chunk received during streaming. The activity
        watchdog uses the time between heartbeats to detect stuck subprocesses.
        """
        self._last_heartbeat = time.monotonic()
        self._heartbeat_received = True

    async def execute(self, coro: Coroutine[None, None, T]) -> T:
        """
        Execute a coroutine with circuit breaker monitoring.

        Wraps the coroutine with a timeout. If the timeout is exceeded,
        raises CircuitBreakerTrippedError. If the circuit breaker is disabled,
        executes the coroutine without timeout.

        When ``activity_timeout_minutes`` is set, a watchdog task runs concurrently.
        It checks every 30 seconds whether ``heartbeat()`` has been called recently.
        If not, and the staleness exceeds the activity timeout, the watchdog cancels
        the main task and raises CircuitBreakerTrippedError with
        ``is_activity_timeout=True``.

        If ``heartbeat()`` is never called (non-streaming mode), the watchdog
        remains passive and only the overall timeout applies.

        Args:
            coro: The coroutine to execute

        Returns:
            The result from the coroutine

        Raises:
            CircuitBreakerTrippedError: If timeout is exceeded and breaker is enabled
            asyncio.CancelledError: If the task is cancelled externally
            Exception: Any exception raised by the coroutine

        Example:
            >>> breaker = CircuitBreaker(timeout_minutes=5)
            >>> async def task():
            ...     return "success"
            >>> result = await breaker.execute(task())
        """
        if not self.enabled:
            # Circuit breaker disabled - execute without timeout
            return await coro

        # Reset heartbeat state for this execution
        self._last_heartbeat = time.monotonic()
        self._heartbeat_received = False

        overall_timeout = (
            self._timeout_seconds_override
            if self._timeout_seconds_override is not None
            else self.timeout_minutes * 60
        )

        # If no activity timeout configured, use simple wait_for
        if self.activity_timeout_minutes is None:
            try:
                return await asyncio.wait_for(coro, timeout=overall_timeout)
            except asyncio.TimeoutError:
                raise CircuitBreakerTrippedError(self.timeout_minutes) from None
            except asyncio.CancelledError:
                raise

        # Activity timeout is configured — use watchdog pattern
        activity_timeout = (
            self._activity_timeout_seconds_override
            if self._activity_timeout_seconds_override is not None
            else self.activity_timeout_minutes * 60
        )

        activity_tripped = False

        async def watchdog() -> None:
            """Periodically check heartbeat staleness."""
            nonlocal activity_tripped
            check_interval = min(30.0, activity_timeout / 2)
            while True:
                await asyncio.sleep(check_interval)
                if not self._heartbeat_received:
                    # Heartbeat never called — non-streaming mode.
                    # Let overall timeout govern.
                    continue
                staleness = time.monotonic() - self._last_heartbeat
                if staleness >= activity_timeout:
                    activity_tripped = True
                    return

        main_task = asyncio.ensure_future(coro)
        watchdog_task = asyncio.ensure_future(watchdog())

        try:
            done, pending = await asyncio.wait(
                {main_task, watchdog_task},
                timeout=overall_timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Case 1: Overall timeout expired (nothing in done)
            if not done:
                main_task.cancel()
                watchdog_task.cancel()
                # Suppress CancelledError from cancelled tasks
                for t in (main_task, watchdog_task):
                    try:
                        await t
                    except (asyncio.CancelledError, Exception):
                        pass
                raise CircuitBreakerTrippedError(self.timeout_minutes) from None

            # Case 2: Watchdog completed first (activity timeout)
            if watchdog_task in done:
                # Check watchdog for exceptions (shouldn't happen, but be safe)
                if watchdog_task.done() and not watchdog_task.cancelled():
                    exc = watchdog_task.exception()
                    if exc is not None:
                        # Unexpected watchdog error — let main task continue
                        # by falling through
                        pass

                if activity_tripped:
                    main_task.cancel()
                    try:
                        await main_task
                    except (asyncio.CancelledError, Exception):
                        pass
                    timeout_mins = self.activity_timeout_minutes or 0
                    raise CircuitBreakerTrippedError(
                        timeout_mins, is_activity_timeout=True
                    ) from None

            # Case 3: Main task completed first
            if main_task in done:
                watchdog_task.cancel()
                try:
                    await watchdog_task
                except (asyncio.CancelledError, Exception):
                    pass
                return main_task.result()

            # Fallback: shouldn't reach here, but handle gracefully
            # Cancel remaining tasks
            for p in pending:
                p.cancel()
                try:
                    await p
                except (asyncio.CancelledError, Exception):
                    pass

            if main_task.done():
                return main_task.result()

            raise CircuitBreakerTrippedError(self.timeout_minutes) from None

        except asyncio.CancelledError:
            main_task.cancel()
            watchdog_task.cancel()
            for t in (main_task, watchdog_task):
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
            raise


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerTrippedError",
]
