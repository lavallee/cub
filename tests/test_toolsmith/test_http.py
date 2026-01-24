"""Tests for HTTP retry utilities."""

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
    """Tests for RetryConfig class."""

    def test_valid_config(self) -> None:
        """Test creating a valid RetryConfig."""
        config = RetryConfig(max_retries=3, base_delay=1.0, multiplier=2.0)
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.multiplier == 2.0

    def test_negative_max_retries(self) -> None:
        """Test that negative max_retries raises ValueError."""
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            RetryConfig(max_retries=-1)

    def test_non_positive_base_delay(self) -> None:
        """Test that non-positive base_delay raises ValueError."""
        with pytest.raises(ValueError, match="base_delay must be positive"):
            RetryConfig(base_delay=0)

        with pytest.raises(ValueError, match="base_delay must be positive"):
            RetryConfig(base_delay=-1.0)

    def test_invalid_multiplier(self) -> None:
        """Test that multiplier < 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="multiplier must be >= 1.0"):
            RetryConfig(multiplier=0.5)

    def test_invalid_jitter_ratio_too_low(self) -> None:
        """Test that jitter_ratio < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="jitter_ratio must be between 0.0 and 1.0"):
            RetryConfig(jitter_ratio=-0.1)

    def test_invalid_jitter_ratio_too_high(self) -> None:
        """Test that jitter_ratio > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="jitter_ratio must be between 0.0 and 1.0"):
            RetryConfig(jitter_ratio=1.1)

    def test_calculate_delay_without_jitter(self) -> None:
        """Test delay calculation without jitter."""
        config = RetryConfig(base_delay=1.0, multiplier=2.0, jitter=False)

        # First retry: 1.0 * 2^0 = 1.0
        assert config.calculate_delay(0) == 1.0
        # Second retry: 1.0 * 2^1 = 2.0
        assert config.calculate_delay(1) == 2.0
        # Third retry: 1.0 * 2^2 = 4.0
        assert config.calculate_delay(2) == 4.0

    def test_calculate_delay_with_jitter(self) -> None:
        """Test delay calculation with jitter."""
        config = RetryConfig(base_delay=1.0, multiplier=2.0, jitter=True, jitter_ratio=0.2)

        # With jitter, delay should be within ±20% of base
        delay = config.calculate_delay(0)
        # Base is 1.0, with 20% jitter: 0.8 to 1.2
        assert 0.8 <= delay <= 1.2

        # Delay should be non-negative
        assert delay >= 0

    def test_calculate_delay_ensures_non_negative(self) -> None:
        """Test that calculate_delay never returns negative values."""
        # Even with extreme jitter, delay should be >= 0
        config = RetryConfig(base_delay=0.01, multiplier=1.0, jitter=True, jitter_ratio=1.0)
        delay = config.calculate_delay(0)
        assert delay >= 0.0


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_http_status_error_5xx_is_retryable(self) -> None:
        """Test that 5xx HTTP status errors are retryable."""
        response = Mock()
        response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=Mock(), response=response)
        assert is_retryable_error(error) is True

        response.status_code = 503
        error = httpx.HTTPStatusError("Service unavailable", request=Mock(), response=response)
        assert is_retryable_error(error) is True

    def test_http_status_error_4xx_not_retryable(self) -> None:
        """Test that 4xx HTTP status errors are not retryable."""
        response = Mock()
        response.status_code = 404
        error = httpx.HTTPStatusError("Not found", request=Mock(), response=response)
        assert is_retryable_error(error) is False

        response.status_code = 401
        error = httpx.HTTPStatusError("Unauthorized", request=Mock(), response=response)
        assert is_retryable_error(error) is False

    def test_timeout_error_is_retryable(self) -> None:
        """Test that timeout errors are retryable."""
        error = httpx.TimeoutException("Timeout")
        assert is_retryable_error(error) is True

    def test_request_error_is_retryable(self) -> None:
        """Test that request errors are retryable."""
        error = httpx.RequestError("Connection failed")
        assert is_retryable_error(error) is True

    def test_generic_http_error_is_retryable(self) -> None:
        """Test that generic HTTPError is retryable."""
        error = httpx.HTTPError("Generic HTTP error")
        assert is_retryable_error(error) is True

    def test_non_http_error_not_retryable(self) -> None:
        """Test that non-HTTP errors are not retryable."""
        error = ValueError("Not an HTTP error")
        assert is_retryable_error(error) is False


class TestWithRetry:
    """Tests for with_retry decorator."""

    @patch("time.sleep")  # Mock sleep to make tests instant
    def test_success_on_first_try(self, mock_sleep: Mock) -> None:
        """Test that decorator doesn't retry on success."""
        call_count = 0

        @with_retry(max_retries=3)
        def successful_function() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_function()
        assert result == "success"
        assert call_count == 1
        mock_sleep.assert_not_called()

    @patch("time.sleep")  # Mock sleep to make tests instant
    def test_retry_on_retryable_error(self, mock_sleep: Mock) -> None:
        """Test that decorator retries on retryable errors."""
        call_count = 0

        @with_retry(max_retries=2)
        def failing_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            return "success"

        result = failing_function()
        assert result == "success"
        assert call_count == 3  # 1 initial + 2 retries
        assert mock_sleep.call_count == 2  # Slept between retries

    @patch("time.sleep")  # Mock sleep to make tests instant
    def test_no_retry_on_non_retryable_error(self, mock_sleep: Mock) -> None:
        """Test that decorator doesn't retry on non-retryable errors."""
        call_count = 0

        @with_retry(max_retries=3)
        def failing_function() -> str:
            nonlocal call_count
            call_count += 1
            response = Mock()
            response.status_code = 404
            raise httpx.HTTPStatusError("Not found", request=Mock(), response=response)

        with pytest.raises(httpx.HTTPStatusError):
            failing_function()

        assert call_count == 1  # No retries for 4xx errors
        mock_sleep.assert_not_called()

    @patch("time.sleep")  # Mock sleep to make tests instant
    def test_exhaust_retries(self, mock_sleep: Mock) -> None:
        """Test that decorator raises after exhausting retries."""
        call_count = 0

        @with_retry(max_retries=2)
        def always_failing_function() -> str:
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("Timeout")

        with pytest.raises(httpx.TimeoutException):
            always_failing_function()

        assert call_count == 3  # 1 initial + 2 retries
        assert mock_sleep.call_count == 2


class TestRetryRequest:
    """Tests for retry_request function."""

    @patch("time.sleep")  # Mock sleep to make tests instant
    @patch("httpx.request")
    def test_successful_request(self, mock_request: Mock, mock_sleep: Mock) -> None:
        """Test that retry_request works for successful requests."""
        # Mock response
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        result = retry_request("GET", "https://example.com")

        assert result == mock_response
        mock_request.assert_called_once_with("GET", "https://example.com", timeout=30.0)
        mock_sleep.assert_not_called()

    @patch("time.sleep")  # Mock sleep to make tests instant
    @patch("httpx.request")
    def test_request_with_retries(self, mock_request: Mock, mock_sleep: Mock) -> None:
        """Test that retry_request retries on failures."""
        # First 2 calls fail, third succeeds
        mock_response_fail = Mock()
        mock_response_fail.raise_for_status = Mock(side_effect=httpx.TimeoutException("Timeout"))

        mock_response_success = Mock()
        mock_response_success.raise_for_status = Mock()

        mock_request.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success,
        ]

        result = retry_request("GET", "https://example.com", max_retries=2)

        assert result == mock_response_success
        assert mock_request.call_count == 3
        assert mock_sleep.call_count == 2
