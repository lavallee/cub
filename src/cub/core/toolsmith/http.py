"""
HTTP utilities with retry logic and exponential backoff.

This module provides retry decorators and utilities for HTTP requests
to handle transient failures gracefully. Uses exponential backoff with
jitter to prevent thundering herd problems.

Example:
    >>> import httpx
    >>> from cub.core.toolsmith.http import with_retry
    >>>
    >>> @with_retry()
    >>> def fetch_data(url: str) -> httpx.Response:
    ...     return httpx.get(url, timeout=30.0)
    >>>
    >>> # Will retry on transient errors (5xx, timeout, connection error)
    >>> response = fetch_data("https://api.example.com/data")

Configuration:
    - Default timeout: 30.0 seconds
    - Default retries: 3 attempts
    - Default base delay: 1.0 seconds
    - Default multiplier: 2.0x per retry
    - Jitter: Random variance of ±20% added to delay
"""

import functools
import logging
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

import httpx

logger = logging.getLogger(__name__)

# Type variable for decorated function return type
T = TypeVar("T")


class RetryConfig:
    """
    Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds before first retry (default: 1.0)
        multiplier: Exponential backoff multiplier (default: 2.0)
        jitter: Whether to add jitter to delays (default: True)
        jitter_ratio: Random variance ratio for jitter (default: 0.2 = ±20%)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        multiplier: float = 2.0,
        jitter: bool = True,
        jitter_ratio: float = 0.2,
    ) -> None:
        """
        Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds before first retry
            multiplier: Exponential backoff multiplier
            jitter: Whether to add jitter to delays
            jitter_ratio: Random variance ratio for jitter (0.0-1.0)

        Raises:
            ValueError: If parameters are invalid
        """
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if base_delay <= 0:
            raise ValueError("base_delay must be positive")
        if multiplier < 1.0:
            raise ValueError("multiplier must be >= 1.0")
        if not 0.0 <= jitter_ratio <= 1.0:
            raise ValueError("jitter_ratio must be between 0.0 and 1.0")

        self.max_retries = max_retries
        self.base_delay = base_delay
        self.multiplier = multiplier
        self.jitter = jitter
        self.jitter_ratio = jitter_ratio

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given retry attempt.

        Uses exponential backoff: delay = base_delay * (multiplier ^ attempt)
        Optionally adds jitter to prevent thundering herd.

        Args:
            attempt: Retry attempt number (0-indexed)

        Returns:
            Delay in seconds before next retry
        """
        # Calculate exponential backoff
        delay = self.base_delay * (self.multiplier**attempt)

        # Add jitter if enabled
        if self.jitter:
            # Apply random variance of ±jitter_ratio
            variance = delay * self.jitter_ratio
            jitter_amount = random.uniform(-variance, variance)
            delay = delay + jitter_amount

        return max(0.0, delay)  # Ensure non-negative


def is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an exception represents a transient, retryable error.

    Retryable errors include:
    - 5xx server errors (server-side issues)
    - Timeout errors (temporary network issues)
    - Connection errors (temporary network issues)
    - Network errors (temporary network issues)
    - General request errors (network/connection issues)

    Non-retryable errors include:
    - 4xx client errors (permanent failures like 404, 401, 400)
    - Other exceptions (programming errors, validation errors, etc.)

    Args:
        exception: Exception to check

    Returns:
        True if the error is retryable, False otherwise
    """
    # HTTP status errors: only retry on 5xx (server errors)
    # Check this first because HTTPStatusError is also a RequestError/HTTPError
    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        # 5xx errors are retryable (server-side issues)
        # 4xx errors are NOT retryable (client errors like 404, 401, 400)
        return 500 <= status_code < 600

    # Timeout errors are retryable
    if isinstance(exception, httpx.TimeoutException):
        return True

    # Connection/network/request errors are retryable
    # This includes ConnectError, NetworkError, and other transient request errors
    # Note: HTTPStatusError is also a RequestError but we handle it above
    if isinstance(exception, httpx.RequestError):
        return True

    # Generic HTTPError (base class) - treat as retryable since it's an HTTP/network issue
    # This catches generic httpx errors that don't fall into more specific categories
    # Note: HTTPStatusError and RequestError are both subclasses, so they're handled above
    if isinstance(exception, httpx.HTTPError):
        return True

    # All other errors are not retryable
    return False


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    multiplier: float = 2.0,
    jitter: bool = True,
    jitter_ratio: float = 0.2,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to add retry logic with exponential backoff to a function.

    Automatically retries the decorated function on transient errors
    (5xx server errors, timeouts, connection errors). Uses exponential
    backoff with optional jitter to prevent thundering herd.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        multiplier: Exponential backoff multiplier (default: 2.0)
        jitter: Whether to add jitter to delays (default: True)
        jitter_ratio: Random variance ratio for jitter (default: 0.2)

    Returns:
        Decorator function that wraps the target function with retry logic

    Example:
        >>> @with_retry(max_retries=3, base_delay=1.0, multiplier=2.0)
        ... def fetch_api_data(url: str) -> dict:
        ...     response = httpx.get(url, timeout=30.0)
        ...     response.raise_for_status()
        ...     return response.json()
        >>>
        >>> # Will retry up to 3 times on transient errors
        >>> # Delays: 1s, 2s, 4s (with jitter)
        >>> data = fetch_api_data("https://api.example.com/data")
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        multiplier=multiplier,
        jitter=jitter,
        jitter_ratio=jitter_ratio,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            func_name = getattr(func, "__name__", repr(func))

            for attempt in range(config.max_retries + 1):
                try:
                    # Attempt the function call
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if we should retry
                    if not is_retryable_error(e):
                        # Non-retryable error, raise immediately
                        logger.debug(
                            f"{func_name}: Non-retryable error on attempt {attempt + 1}: {e}"
                        )
                        raise

                    # Check if we have retries left
                    if attempt >= config.max_retries:
                        # No more retries, raise the last exception
                        logger.warning(
                            f"{func_name}: Max retries ({config.max_retries}) " f"exceeded: {e}"
                        )
                        raise

                    # Calculate delay and log retry attempt
                    delay = config.calculate_delay(attempt)
                    logger.info(
                        f"{func_name}: Retry attempt {attempt + 1}/{config.max_retries} "
                        f"after {delay:.2f}s due to: {e}"
                    )

                    # Wait before retrying
                    time.sleep(delay)

            # This should never be reached, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry loop completed without success or exception")

        return wrapper

    return decorator


def retry_request(
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    multiplier: float = 2.0,
    timeout: float = 30.0,
    **kwargs: Any,
) -> httpx.Response:
    """
    Make an HTTP request with automatic retry logic.

    Convenience function that combines httpx request with retry logic.
    Handles transient errors (5xx, timeouts, connection errors) with
    exponential backoff and jitter.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: URL to request
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        multiplier: Exponential backoff multiplier (default: 2.0)
        timeout: Request timeout in seconds (default: 30.0)
        **kwargs: Additional arguments to pass to httpx.request()

    Returns:
        HTTP response object

    Raises:
        httpx.HTTPStatusError: On 4xx errors or after max retries on 5xx
        httpx.TimeoutException: After max retries on timeout
        httpx.RequestError: After max retries on network errors

    Example:
        >>> response = retry_request(
        ...     "GET",
        ...     "https://api.example.com/data",
        ...     max_retries=3,
        ...     timeout=30.0,
        ...     headers={"Authorization": "Bearer token"}
        ... )
        >>> data = response.json()
    """

    @with_retry(max_retries=max_retries, base_delay=base_delay, multiplier=multiplier)
    def _make_request() -> httpx.Response:
        response = httpx.request(method, url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response

    return _make_request()


__all__ = [
    "RetryConfig",
    "with_retry",
    "retry_request",
    "is_retryable_error",
]
