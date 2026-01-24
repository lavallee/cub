"""Tests for HTTP retry utilities."""

import time
from unittest.mock import Mock, patch

import httpx
import pytest

from cub.core.toolsmith.http import (
    RetryConfig,
    is_retryable_error,
    retry_request,
    with_retry,
)


class TestRetryConfig:
    """Test suite for RetryConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.multiplier == 2.0
        assert config.jitter is True
        assert config.jitter_ratio == 0.2

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            multiplier=3.0,
            jitter=False,
            jitter_ratio=0.1,
        )
        assert config.max_retries == 5
        assert config.base_delay == 2.0
        assert config.multiplier == 3.0
        assert config.jitter is False
        assert config.jitter_ratio == 0.1

    def test_invalid_max_retries(self) -> None:
        """Test that negative max_retries raises error."""
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            RetryConfig(max_retries=-1)

    def test_invalid_base_delay(self) -> None:
        """Test that non-positive base_delay raises error."""
        with pytest.raises(ValueError, match="base_delay must be positive"):
            RetryConfig(base_delay=0)

    def test_invalid_multiplier(self) -> None:
        """Test that multiplier < 1.0 raises error."""
        with pytest.raises(ValueError, match="multiplier must be >= 1.0"):
            RetryConfig(multiplier=0.5)

    def test_invalid_jitter_ratio(self) -> None:
        """Test that jitter_ratio outside [0.0, 1.0] raises error."""
        with pytest.raises(ValueError, match="jitter_ratio must be between"):
            RetryConfig(jitter_ratio=1.5)

    def test_calculate_delay_no_jitter(self) -> None:
        """Test delay calculation without jitter."""
        config = RetryConfig(base_delay=1.0, multiplier=2.0, jitter=False)

        # Attempt 0: 1.0 * (2.0 ^ 0) = 1.0
        assert config.calculate_delay(0) == 1.0

        # Attempt 1: 1.0 * (2.0 ^ 1) = 2.0
        assert config.calculate_delay(1) == 2.0

        # Attempt 2: 1.0 * (2.0 ^ 2) = 4.0
        assert config.calculate_delay(2) == 4.0

    def test_calculate_delay_with_jitter(self) -> None:
        """Test delay calculation with jitter."""
        config = RetryConfig(base_delay=1.0, multiplier=2.0, jitter=True, jitter_ratio=0.2)

        # With jitter, delay should be within ±20% of expected value
        # Attempt 0: expected 1.0, range [0.8, 1.2]
        delay = config.calculate_delay(0)
        assert 0.8 <= delay <= 1.2

        # Attempt 1: expected 2.0, range [1.6, 2.4]
        delay = config.calculate_delay(1)
        assert 1.6 <= delay <= 2.4

        # Attempt 2: expected 4.0, range [3.2, 4.8]
        delay = config.calculate_delay(2)
        assert 3.2 <= delay <= 4.8


class TestIsRetryableError:
    """Test suite for is_retryable_error."""

    def test_timeout_is_retryable(self) -> None:
        """Test that timeout exceptions are retryable."""
        error = httpx.TimeoutException("Request timed out")
        assert is_retryable_error(error) is True

    def test_connect_error_is_retryable(self) -> None:
        """Test that connection errors are retryable."""
        error = httpx.ConnectError("Connection refused")
        assert is_retryable_error(error) is True

    def test_network_error_is_retryable(self) -> None:
        """Test that network errors are retryable."""
        error = httpx.NetworkError("Network unreachable")
        assert is_retryable_error(error) is True

    def test_5xx_is_retryable(self) -> None:
        """Test that 5xx errors are retryable."""
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(500, request=request)
        error = httpx.HTTPStatusError("Server error", request=request, response=response)
        assert is_retryable_error(error) is True

    def test_503_is_retryable(self) -> None:
        """Test that 503 Service Unavailable is retryable."""
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(503, request=request)
        error = httpx.HTTPStatusError(
            "Service Unavailable", request=request, response=response
        )
        assert is_retryable_error(error) is True

    def test_4xx_is_not_retryable(self) -> None:
        """Test that 4xx errors are not retryable."""
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(404, request=request)
        error = httpx.HTTPStatusError("Not Found", request=request, response=response)
        assert is_retryable_error(error) is False

    def test_401_is_not_retryable(self) -> None:
        """Test that 401 Unauthorized is not retryable."""
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(401, request=request)
        error = httpx.HTTPStatusError("Unauthorized", request=request, response=response)
        assert is_retryable_error(error) is False

    def test_400_is_not_retryable(self) -> None:
        """Test that 400 Bad Request is not retryable."""
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(400, request=request)
        error = httpx.HTTPStatusError("Bad Request", request=request, response=response)
        assert is_retryable_error(error) is False

    def test_other_exception_is_not_retryable(self) -> None:
        """Test that non-HTTP exceptions are not retryable."""
        error = ValueError("Invalid value")
        assert is_retryable_error(error) is False

    def test_generic_http_error_is_retryable(self) -> None:
        """Test that generic HTTPError (base class) is retryable."""
        error = httpx.HTTPError("Generic HTTP error")
        assert is_retryable_error(error) is True


class TestWithRetryDecorator:
    """Test suite for with_retry decorator."""

    def test_success_on_first_attempt(self) -> None:
        """Test successful execution on first attempt."""
        mock_func = Mock(return_value="success")
        decorated = with_retry()(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_success_after_retries(self) -> None:
        """Test successful execution after retries."""
        # Fail twice, then succeed
        request = httpx.Request("GET", "https://example.com")
        response_500 = httpx.Response(500, request=request)
        error = httpx.HTTPStatusError("Server error", request=request, response=response_500)

        mock_func = Mock(side_effect=[error, error, "success"])
        decorated = with_retry(max_retries=3, base_delay=0.01)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_max_retries_exceeded(self) -> None:
        """Test that max retries is respected."""
        request = httpx.Request("GET", "https://example.com")
        response_500 = httpx.Response(500, request=request)
        error = httpx.HTTPStatusError("Server error", request=request, response=response_500)

        mock_func = Mock(side_effect=error)
        decorated = with_retry(max_retries=2, base_delay=0.01)(mock_func)

        with pytest.raises(httpx.HTTPStatusError):
            decorated()

        # Should try initial attempt + 2 retries = 3 times
        assert mock_func.call_count == 3

    def test_non_retryable_error_not_retried(self) -> None:
        """Test that non-retryable errors are not retried."""
        request = httpx.Request("GET", "https://example.com")
        response_404 = httpx.Response(404, request=request)
        error = httpx.HTTPStatusError("Not Found", request=request, response=response_404)

        mock_func = Mock(side_effect=error)
        decorated = with_retry(max_retries=3, base_delay=0.01)(mock_func)

        with pytest.raises(httpx.HTTPStatusError):
            decorated()

        # Should only try once (no retries)
        assert mock_func.call_count == 1

    def test_exponential_backoff_timing(self) -> None:
        """Test that exponential backoff timing is correct."""
        request = httpx.Request("GET", "https://example.com")
        response_500 = httpx.Response(500, request=request)
        error = httpx.HTTPStatusError("Server error", request=request, response=response_500)

        mock_func = Mock(side_effect=error)
        # Use very short delays and no jitter for timing test
        decorated = with_retry(max_retries=2, base_delay=0.01, multiplier=2.0, jitter=False)(
            mock_func
        )

        start_time = time.time()
        with pytest.raises(httpx.HTTPStatusError):
            decorated()
        elapsed_time = time.time() - start_time

        # Expected delays: 0.01s (after 1st attempt), 0.02s (after 2nd attempt)
        # Total expected delay: ~0.03s
        # Allow generous tolerance for CI variability (especially macOS)
        assert 0.02 <= elapsed_time <= 0.5

    def test_preserves_function_metadata(self) -> None:
        """Test that decorator preserves function metadata."""

        @with_retry()
        def example_func() -> str:
            """Example function docstring."""
            return "test"

        assert example_func.__name__ == "example_func"
        assert example_func.__doc__ == "Example function docstring."

    def test_passes_arguments(self) -> None:
        """Test that decorator passes arguments correctly."""
        mock_func = Mock(return_value="success")
        decorated = with_retry()(mock_func)

        result = decorated("arg1", "arg2", kwarg1="value1", kwarg2="value2")

        assert result == "success"
        mock_func.assert_called_once_with("arg1", "arg2", kwarg1="value1", kwarg2="value2")


class TestRetryRequest:
    """Test suite for retry_request convenience function."""

    @patch("httpx.request")
    def test_successful_request(self, mock_request: Mock) -> None:
        """Test successful HTTP request."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        response = retry_request("GET", "https://example.com/api")

        assert response == mock_response
        mock_request.assert_called_once_with(
            "GET", "https://example.com/api", timeout=30.0
        )

    @patch("httpx.request")
    def test_retry_on_500(self, mock_request: Mock) -> None:
        """Test retry on 500 error."""
        request = httpx.Request("GET", "https://example.com")
        response_500 = httpx.Response(500, request=request)
        error = httpx.HTTPStatusError("Server error", request=request, response=response_500)

        mock_success = Mock(spec=httpx.Response)
        mock_success.raise_for_status = Mock()

        # First call raises error, second succeeds
        mock_request.side_effect = [error, mock_success]

        response = retry_request(
            "GET", "https://example.com/api", max_retries=3, base_delay=0.01
        )

        assert response == mock_success
        assert mock_request.call_count == 2

    @patch("httpx.request")
    def test_no_retry_on_404(self, mock_request: Mock) -> None:
        """Test no retry on 404 error."""
        request = httpx.Request("GET", "https://example.com")
        response_404 = httpx.Response(404, request=request)
        error = httpx.HTTPStatusError("Not Found", request=request, response=response_404)
        mock_request.side_effect = error

        with pytest.raises(httpx.HTTPStatusError):
            retry_request("GET", "https://example.com/api", max_retries=3, base_delay=0.01)

        # Should only try once (no retries for 4xx)
        assert mock_request.call_count == 1

    @patch("httpx.request")
    def test_custom_timeout(self, mock_request: Mock) -> None:
        """Test custom timeout parameter."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        retry_request("GET", "https://example.com/api", timeout=60.0)

        mock_request.assert_called_once_with("GET", "https://example.com/api", timeout=60.0)

    @patch("httpx.request")
    def test_additional_kwargs(self, mock_request: Mock) -> None:
        """Test passing additional kwargs to httpx.request."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        headers = {"Authorization": "Bearer token"}
        retry_request(
            "POST",
            "https://example.com/api",
            headers=headers,
            json={"key": "value"},
        )

        mock_request.assert_called_once_with(
            "POST",
            "https://example.com/api",
            timeout=30.0,
            headers=headers,
            json={"key": "value"},
        )
