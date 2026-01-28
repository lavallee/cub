"""
Circuit breaker for detecting and preventing harness stagnation.

This module provides the CircuitBreaker class that wraps harness execution
with timeout monitoring. If no activity is detected for the configured timeout
period, the circuit breaker trips and stops execution with a clear error message.

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
        message: Human-readable error message
    """

    def __init__(self, timeout_minutes: int) -> None:
        """
        Initialize a circuit breaker tripped exception.

        Args:
            timeout_minutes: The timeout period that was exceeded
        """
        self.timeout_minutes = timeout_minutes
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

    The circuit breaker can be disabled for testing or debugging purposes.

    Attributes:
        timeout_minutes: Maximum minutes of inactivity before tripping
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
        _timeout_seconds_override: float | None = None,
    ) -> None:
        """
        Initialize a circuit breaker.

        Args:
            timeout_minutes: Maximum minutes to wait before tripping (must be >= 1)
            enabled: Whether to enforce timeout (default: True)
            _timeout_seconds_override: Override timeout in seconds (for testing only)

        Raises:
            ValueError: If timeout_minutes < 1
        """
        if timeout_minutes < 1:
            raise ValueError(f"timeout_minutes must be >= 1, got {timeout_minutes}")

        self.timeout_minutes = timeout_minutes
        self.enabled = enabled
        self._timeout_seconds_override = _timeout_seconds_override

    async def execute(self, coro: Coroutine[None, None, T]) -> T:
        """
        Execute a coroutine with circuit breaker monitoring.

        Wraps the coroutine with a timeout. If the timeout is exceeded,
        raises CircuitBreakerTrippedError. If the circuit breaker is disabled,
        executes the coroutine without timeout.

        The coroutine is gracefully cancelled if the timeout is exceeded,
        allowing cleanup operations to complete.

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

        timeout_seconds = (
            self._timeout_seconds_override
            if self._timeout_seconds_override is not None
            else self.timeout_minutes * 60
        )

        try:
            # Use asyncio.wait_for to enforce timeout
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            # Timeout exceeded - trip the circuit breaker
            raise CircuitBreakerTrippedError(self.timeout_minutes) from None
        except asyncio.CancelledError:
            # Propagate cancellation (e.g., from Ctrl+C)
            raise


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerTrippedError",
]
