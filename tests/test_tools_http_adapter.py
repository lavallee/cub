"""
Tests for HTTPAdapter.

Tests the HTTP tool adapter with retry logic, error handling, and response parsing.
"""

import os
from unittest.mock import Mock, patch

import httpx
import pytest

from cub.core.tools.adapters.http import HTTPAdapter
from cub.core.tools.models import AdapterType, HTTPConfig


class TestHTTPAdapter:
    """Test HTTPAdapter initialization and basic properties."""

    def test_adapter_type(self):
        """Test adapter returns correct type."""
        adapter = HTTPAdapter()
        assert adapter.adapter_type == "http"

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check succeeds."""
        adapter = HTTPAdapter()
        # Health check should always succeed (no actual request made)
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check handles failures gracefully."""
        adapter = HTTPAdapter()
        # Even if httpx has issues, health check should handle it
        with patch(
            "cub.core.tools.adapters.http.httpx.AsyncClient",
            side_effect=Exception("Network error"),
        ):
            assert await adapter.health_check() is False

    @pytest.mark.asyncio
    async def test_is_available(self):
        """Test tool availability check."""
        adapter = HTTPAdapter()
        # For now, is_available returns True optimistically
        assert await adapter.is_available("test-tool") is True


class TestHTTPAdapterExecute:
    """Test HTTPAdapter execute method."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful HTTP request execution."""
        adapter = HTTPAdapter()

        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
            headers={"Accept": "application/json"},
        )

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"results": [{"id": 1, "title": "Test"}]}

        with patch("cub.core.tools.adapters.http.retry_request", return_value=mock_response):
            result = await adapter.execute(
                tool_id="test-tool",
                action="search",
                params={"_http_config": config, "query": "test"},
                timeout=30.0,
            )

        assert result.success is True
        assert result.tool_id == "test-tool"
        assert result.action == "search"
        assert result.output == {"results": [{"id": 1, "title": "Test"}]}
        assert result.adapter_type == AdapterType.HTTP
        assert result.duration_ms >= 0
        assert result.metadata["status_code"] == 200
        assert result.error is None

    @pytest.mark.asyncio
    async def test_execute_missing_config(self):
        """Test execution fails gracefully when config is missing."""
        adapter = HTTPAdapter()

        result = await adapter.execute(
            tool_id="test-tool",
            action="search",
            params={"query": "test"},
            timeout=30.0,
        )

        assert result.success is False
        assert result.error == "HTTP configuration not provided"
        assert result.error_type == "validation"

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """Test timeout handling."""
        adapter = HTTPAdapter()

        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
        )

        with patch(
            "cub.core.tools.adapters.http.retry_request",
            side_effect=httpx.TimeoutException("Request timed out"),
        ):
            result = await adapter.execute(
                tool_id="test-tool",
                action="search",
                params={"_http_config": config, "query": "test"},
                timeout=30.0,
            )

        assert result.success is False
        assert result.error_type == "timeout"
        assert "timed out" in result.error.lower()
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_http_401_auth_error(self):
        """Test 401 authentication error handling."""
        adapter = HTTPAdapter()

        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
        )

        mock_response = Mock()
        mock_response.status_code = 401
        error = httpx.HTTPStatusError("Unauthorized", request=Mock(), response=mock_response)

        with patch("cub.core.tools.adapters.http.retry_request", side_effect=error):
            result = await adapter.execute(
                tool_id="test-tool",
                action="search",
                params={"_http_config": config, "query": "test"},
                timeout=30.0,
            )

        assert result.success is False
        assert result.error_type == "auth"
        assert "401" in result.error
        assert result.metadata["status_code"] == 401

    @pytest.mark.asyncio
    async def test_execute_http_429_rate_limit(self):
        """Test 429 rate limit error handling."""
        adapter = HTTPAdapter()

        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
        )

        mock_response = Mock()
        mock_response.status_code = 429
        error = httpx.HTTPStatusError("Too Many Requests", request=Mock(), response=mock_response)

        with patch("cub.core.tools.adapters.http.retry_request", side_effect=error):
            result = await adapter.execute(
                tool_id="test-tool",
                action="search",
                params={"_http_config": config, "query": "test"},
                timeout=30.0,
            )

        assert result.success is False
        assert result.error_type == "rate_limit"
        assert "429" in result.error

    @pytest.mark.asyncio
    async def test_execute_http_403_auth_error(self):
        """Test 403 forbidden error handling."""
        adapter = HTTPAdapter()

        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
        )

        mock_response = Mock()
        mock_response.status_code = 403
        error = httpx.HTTPStatusError("Forbidden", request=Mock(), response=mock_response)

        with patch("cub.core.tools.adapters.http.retry_request", side_effect=error):
            result = await adapter.execute(
                tool_id="test-tool",
                action="search",
                params={"_http_config": config, "query": "test"},
                timeout=30.0,
            )

        assert result.success is False
        assert result.error_type == "auth"
        assert "403" in result.error

    @pytest.mark.asyncio
    async def test_execute_http_400_validation_error(self):
        """Test 400 bad request error handling."""
        adapter = HTTPAdapter()

        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
        )

        mock_response = Mock()
        mock_response.status_code = 400
        error = httpx.HTTPStatusError("Bad Request", request=Mock(), response=mock_response)

        with patch("cub.core.tools.adapters.http.retry_request", side_effect=error):
            result = await adapter.execute(
                tool_id="test-tool",
                action="search",
                params={"_http_config": config, "query": "test"},
                timeout=30.0,
            )

        assert result.success is False
        assert result.error_type == "validation"
        assert "400" in result.error

    @pytest.mark.asyncio
    async def test_execute_http_500_network_error(self):
        """Test 500 server error handling."""
        adapter = HTTPAdapter()

        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
        )

        mock_response = Mock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError(
            "Internal Server Error", request=Mock(), response=mock_response
        )

        with patch("cub.core.tools.adapters.http.retry_request", side_effect=error):
            result = await adapter.execute(
                tool_id="test-tool",
                action="search",
                params={"_http_config": config, "query": "test"},
                timeout=30.0,
            )

        assert result.success is False
        assert result.error_type == "network"
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_execute_network_error(self):
        """Test network/connection error handling."""
        adapter = HTTPAdapter()

        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
        )

        with patch(
            "cub.core.tools.adapters.http.retry_request",
            side_effect=httpx.RequestError("Connection failed"),
        ):
            result = await adapter.execute(
                tool_id="test-tool",
                action="search",
                params={"_http_config": config, "query": "test"},
                timeout=30.0,
            )

        assert result.success is False
        assert result.error_type == "network"
        assert "network error" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_unexpected_error(self):
        """Test unexpected error handling."""
        adapter = HTTPAdapter()

        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
        )

        with patch(
            "cub.core.tools.adapters.http.retry_request",
            side_effect=RuntimeError("Unexpected error"),
        ):
            result = await adapter.execute(
                tool_id="test-tool",
                action="search",
                params={"_http_config": config, "query": "test"},
                timeout=30.0,
            )

        assert result.success is False
        assert result.error_type == "unknown"
        assert "unexpected error" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_non_json_response(self):
        """Test handling of non-JSON responses."""
        adapter = HTTPAdapter()

        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
        )

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.json.side_effect = Exception("Not JSON")
        mock_response.text = "Plain text response"

        with patch("cub.core.tools.adapters.http.retry_request", return_value=mock_response):
            result = await adapter.execute(
                tool_id="test-tool",
                action="search",
                params={"_http_config": config, "query": "test"},
                timeout=30.0,
            )

        assert result.success is True
        assert result.output == {"text": "Plain text response"}


class TestHTTPAdapterHelpers:
    """Test HTTPAdapter helper methods."""

    def test_build_url(self):
        """Test URL construction from config."""
        adapter = HTTPAdapter()
        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search", "get": "/v1/items"},
        )

        url = adapter._build_url(config, "search")
        assert url == "https://api.example.com/v1/search"

        url = adapter._build_url(config, "get")
        assert url == "https://api.example.com/v1/items"

    def test_build_url_trailing_slash(self):
        """Test URL construction handles trailing slashes."""
        adapter = HTTPAdapter()
        config = HTTPConfig(
            base_url="https://api.example.com/",
            endpoints={"search": "/v1/search"},
        )

        url = adapter._build_url(config, "search")
        assert url == "https://api.example.com/v1/search"

    def test_build_url_invalid_action(self):
        """Test URL construction fails for unknown action."""
        adapter = HTTPAdapter()
        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
        )

        with pytest.raises(ValueError, match="Action 'unknown' not found"):
            adapter._build_url(config, "unknown")

    def test_build_headers_no_auth(self):
        """Test header construction without authentication."""
        adapter = HTTPAdapter()
        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
            headers={"Accept": "application/json", "User-Agent": "test"},
        )

        headers = adapter._build_headers(config)
        assert headers == {"Accept": "application/json", "User-Agent": "test"}

    def test_build_headers_with_auth(self):
        """Test header construction with authentication."""
        adapter = HTTPAdapter()
        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
            headers={"Accept": "application/json"},
            auth_header="X-API-Key",
            auth_env_var="TEST_API_KEY",
        )

        with patch.dict(os.environ, {"TEST_API_KEY": "secret123"}):
            headers = adapter._build_headers(config)
            assert headers == {
                "Accept": "application/json",
                "X-API-Key": "secret123",
            }

    def test_build_headers_missing_auth(self):
        """Test header construction fails when auth is required but missing."""
        adapter = HTTPAdapter()
        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
            auth_header="X-API-Key",
            auth_env_var="MISSING_API_KEY",
        )

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="MISSING_API_KEY is not set"):
                adapter._build_headers(config)

    def test_build_params(self):
        """Test request parameter construction."""
        adapter = HTTPAdapter()

        params = {
            "query": "test",
            "count": 10,
            "filter": "active",
            "_http_config": "should be filtered",
            "_internal": "should be filtered",
        }

        http_params = adapter._build_params(params)
        assert http_params == {
            "query": "test",
            "count": "10",
            "filter": "active",
        }

    def test_classify_http_error_401(self):
        """Test error classification for 401."""
        adapter = HTTPAdapter()
        assert adapter._classify_http_error(401) == "auth"

    def test_classify_http_error_403(self):
        """Test error classification for 403."""
        adapter = HTTPAdapter()
        assert adapter._classify_http_error(403) == "auth"

    def test_classify_http_error_429(self):
        """Test error classification for 429."""
        adapter = HTTPAdapter()
        assert adapter._classify_http_error(429) == "rate_limit"

    def test_classify_http_error_400(self):
        """Test error classification for 400."""
        adapter = HTTPAdapter()
        assert adapter._classify_http_error(400) == "validation"

    def test_classify_http_error_404(self):
        """Test error classification for 404."""
        adapter = HTTPAdapter()
        assert adapter._classify_http_error(404) == "validation"

    def test_classify_http_error_500(self):
        """Test error classification for 500."""
        adapter = HTTPAdapter()
        assert adapter._classify_http_error(500) == "network"

    def test_classify_http_error_503(self):
        """Test error classification for 503."""
        adapter = HTTPAdapter()
        assert adapter._classify_http_error(503) == "network"

    def test_classify_http_error_unknown(self):
        """Test error classification for unknown status."""
        adapter = HTTPAdapter()
        assert adapter._classify_http_error(999) == "unknown"

    def test_generate_markdown_basic(self):
        """Test markdown generation for basic response."""
        adapter = HTTPAdapter()

        mock_response = Mock()
        mock_response.status_code = 200

        output = {"data": "test"}

        markdown = adapter._generate_markdown(
            "test-tool",
            "search",
            output,
            mock_response,
        )

        assert "test-tool" in markdown
        assert "search" in markdown
        assert "200" in markdown

    def test_generate_markdown_with_results(self):
        """Test markdown generation with results array."""
        adapter = HTTPAdapter()

        mock_response = Mock()
        mock_response.status_code = 200

        output = {"results": [{"id": 1}, {"id": 2}, {"id": 3}]}

        markdown = adapter._generate_markdown(
            "test-tool",
            "search",
            output,
            mock_response,
        )

        assert "Results: 3" in markdown

    def test_generate_markdown_with_data_array(self):
        """Test markdown generation with data array."""
        adapter = HTTPAdapter()

        mock_response = Mock()
        mock_response.status_code = 200

        output = {"data": [{"id": 1}, {"id": 2}]}

        markdown = adapter._generate_markdown(
            "test-tool",
            "list",
            output,
            mock_response,
        )

        assert "Items: 2" in markdown


class TestHTTPAdapterRegistration:
    """Test HTTPAdapter registration with adapter registry."""

    def test_adapter_registered(self):
        """Test that HTTPAdapter is registered with the adapter registry."""
        from cub.core.tools.adapter import get_adapter, is_adapter_available

        # HTTPAdapter should be registered via @register_adapter decorator
        assert is_adapter_available("http")

        adapter = get_adapter("http")
        assert isinstance(adapter, HTTPAdapter)
        assert adapter.adapter_type == "http"
