"""
Tests for the toolsmith execution module.

Tests cover:
- ToolRunResult dataclass instantiation and attributes
- ToolExecutionError exception raising
- run_tool() with supported and unsupported tools
- _run_brave_search() parameter validation and API interaction
- _write_artifact() file creation and path formatting
- _runs_dir() path construction
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from cub.core.toolsmith.execution import (
    ToolExecutionError,
    ToolRunResult,
    _run_brave_search,
    _runs_dir,
    _write_artifact,
    run_tool,
)

# ==============================================================================
# ToolRunResult Tests
# ==============================================================================


class TestToolRunResult:
    """Tests for ToolRunResult dataclass."""

    def test_instantiation(self, tmp_path: Path) -> None:
        """Test ToolRunResult can be instantiated with all fields."""
        created = datetime.now(timezone.utc)
        artifact = tmp_path / "test.json"

        result = ToolRunResult(
            tool_id="test:tool",
            created_at=created,
            artifact_path=artifact,
            summary="Test summary",
        )

        assert result.tool_id == "test:tool"
        assert result.created_at == created
        assert result.artifact_path == artifact
        assert result.summary == "Test summary"

    def test_immutable(self, tmp_path: Path) -> None:
        """Test ToolRunResult is frozen (immutable)."""
        result = ToolRunResult(
            tool_id="test:tool",
            created_at=datetime.now(timezone.utc),
            artifact_path=tmp_path / "test.json",
            summary="Test summary",
        )

        with pytest.raises(AttributeError):
            result.tool_id = "new:tool"

    def test_equality(self, tmp_path: Path) -> None:
        """Test ToolRunResult equality comparison."""
        created = datetime.now(timezone.utc)
        artifact = tmp_path / "test.json"

        result1 = ToolRunResult(
            tool_id="test:tool",
            created_at=created,
            artifact_path=artifact,
            summary="Test summary",
        )
        result2 = ToolRunResult(
            tool_id="test:tool",
            created_at=created,
            artifact_path=artifact,
            summary="Test summary",
        )

        assert result1 == result2


# ==============================================================================
# ToolExecutionError Tests
# ==============================================================================


class TestToolExecutionError:
    """Tests for ToolExecutionError exception."""

    def test_raises_with_message(self) -> None:
        """Test ToolExecutionError can be raised with a message."""
        with pytest.raises(ToolExecutionError, match="test error"):
            raise ToolExecutionError("test error")

    def test_inherits_from_runtime_error(self) -> None:
        """Test ToolExecutionError inherits from RuntimeError."""
        error = ToolExecutionError("test")
        assert isinstance(error, RuntimeError)

    def test_error_message_preserved(self) -> None:
        """Test error message is accessible."""
        error = ToolExecutionError("specific error message")
        assert str(error) == "specific error message"


# ==============================================================================
# _runs_dir() Tests
# ==============================================================================


class TestRunsDir:
    """Tests for _runs_dir() function."""

    def test_returns_path_under_cwd(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test _runs_dir returns path under current working directory."""
        monkeypatch.chdir(tmp_path)

        result = _runs_dir()

        assert result == tmp_path / ".cub" / "toolsmith" / "runs"

    def test_returns_path_type(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test _runs_dir returns a Path object."""
        monkeypatch.chdir(tmp_path)

        result = _runs_dir()

        assert isinstance(result, Path)


# ==============================================================================
# _write_artifact() Tests
# ==============================================================================


class TestWriteArtifact:
    """Tests for _write_artifact() function."""

    def test_creates_directory_if_not_exists(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test _write_artifact creates the runs directory if it doesn't exist."""
        monkeypatch.chdir(tmp_path)

        runs_dir = tmp_path / ".cub" / "toolsmith" / "runs"
        assert not runs_dir.exists()

        _write_artifact("test:tool", {"key": "value"})

        assert runs_dir.exists()

    def test_writes_json_content(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test _write_artifact writes JSON payload correctly."""
        monkeypatch.chdir(tmp_path)
        payload = {"tool_id": "test:tool", "data": [1, 2, 3]}

        artifact_path = _write_artifact("test:tool", payload)

        content = json.loads(artifact_path.read_text())
        assert content == payload

    def test_writes_indented_json(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test _write_artifact writes pretty-printed JSON."""
        monkeypatch.chdir(tmp_path)
        payload = {"key": "value"}

        artifact_path = _write_artifact("test:tool", payload)

        content = artifact_path.read_text()
        # Indented JSON has newlines and spaces
        assert "\n" in content
        assert "  " in content  # 2-space indent

    def test_returns_path_to_artifact(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test _write_artifact returns the path to the created file."""
        monkeypatch.chdir(tmp_path)

        result = _write_artifact("test:tool", {"key": "value"})

        assert isinstance(result, Path)
        assert result.exists()
        assert result.suffix == ".json"

    def test_path_format_includes_timestamp_and_tool_id(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test artifact path follows YYYYMMDD-HHMMSS-tool_id.json format."""
        monkeypatch.chdir(tmp_path)

        result = _write_artifact("test:tool", {"key": "value"})

        # Path should be like: YYYYMMDD-HHMMSS-test_tool.json
        filename = result.name
        parts = filename.rsplit("-", 1)  # Split from right to handle tool_id with dashes
        assert len(parts) == 2
        # First part is YYYYMMDD-HHMMSS (timestamp)
        # Second part is tool_id.json
        assert parts[1] == "test_tool.json"

    def test_sanitizes_tool_id_colons(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test colons in tool_id are replaced with underscores."""
        monkeypatch.chdir(tmp_path)

        result = _write_artifact("mcp-official:brave-search", {"key": "value"})

        assert "mcp-official_brave-search" in result.name

    def test_sanitizes_tool_id_slashes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test slashes in tool_id are replaced with underscores."""
        monkeypatch.chdir(tmp_path)

        result = _write_artifact("source/tool/name", {"key": "value"})

        assert "source_tool_name" in result.name


# ==============================================================================
# run_tool() Tests
# ==============================================================================


class TestRunTool:
    """Tests for run_tool() function."""

    def test_unsupported_tool_raises_error(self) -> None:
        """Test run_tool raises ToolExecutionError for unsupported tools."""
        with pytest.raises(ToolExecutionError) as exc_info:
            run_tool("unsupported:tool", params={})

        assert "unsupported:tool" in str(exc_info.value)
        assert "not implemented" in str(exc_info.value).lower()

    def test_unsupported_tool_error_mentions_supported_tools(self) -> None:
        """Test error message mentions supported tools."""
        with pytest.raises(ToolExecutionError) as exc_info:
            run_tool("random:tool", params={})

        assert "mcp-official:brave-search" in str(exc_info.value)

    def test_brave_search_tool_is_supported(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test brave-search tool ID is recognized and dispatched correctly."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        # Mock httpx.get to return a successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mocker.patch("httpx.get", return_value=mock_response)

        result = run_tool("mcp-official:brave-search", params={"query": "test"})

        assert isinstance(result, ToolRunResult)
        assert result.tool_id == "mcp-official:brave-search"


# ==============================================================================
# _run_brave_search() Tests
# ==============================================================================


class TestRunBraveSearch:
    """Tests for _run_brave_search() function."""

    # --------------------------------------------------------------------------
    # Parameter Validation Tests
    # --------------------------------------------------------------------------

    def test_missing_query_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test missing query parameter raises ToolExecutionError."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        with pytest.raises(ToolExecutionError, match="non-empty 'query'"):
            _run_brave_search("mcp-official:brave-search", params={})

    def test_empty_query_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test empty query parameter raises ToolExecutionError."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        with pytest.raises(ToolExecutionError, match="non-empty 'query'"):
            _run_brave_search("mcp-official:brave-search", params={"query": ""})

    def test_whitespace_only_query_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test whitespace-only query parameter raises ToolExecutionError."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        with pytest.raises(ToolExecutionError, match="non-empty 'query'"):
            _run_brave_search("mcp-official:brave-search", params={"query": "   "})

    def test_count_below_minimum_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test count less than 1 raises ToolExecutionError."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        with pytest.raises(ToolExecutionError, match="between 1 and 20"):
            _run_brave_search(
                "mcp-official:brave-search",
                params={"query": "test", "count": 0},
            )

    def test_count_above_maximum_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test count greater than 20 raises ToolExecutionError."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        with pytest.raises(ToolExecutionError, match="between 1 and 20"):
            _run_brave_search(
                "mcp-official:brave-search",
                params={"query": "test", "count": 21},
            )

    def test_count_exactly_1_is_valid(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test count of 1 is accepted."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mocker.patch("httpx.get", return_value=mock_response)

        # Should not raise
        result = _run_brave_search(
            "mcp-official:brave-search",
            params={"query": "test", "count": 1},
        )
        assert isinstance(result, ToolRunResult)

    def test_count_exactly_20_is_valid(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test count of 20 is accepted."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mocker.patch("httpx.get", return_value=mock_response)

        # Should not raise
        result = _run_brave_search(
            "mcp-official:brave-search",
            params={"query": "test", "count": 20},
        )
        assert isinstance(result, ToolRunResult)

    def test_default_count_is_5(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test default count is 5 when not specified."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_get = mocker.patch("httpx.get")
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        _run_brave_search("mcp-official:brave-search", params={"query": "test"})

        # Check the count parameter passed to httpx.get
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["count"] == "5"

    # --------------------------------------------------------------------------
    # API Key Tests
    # --------------------------------------------------------------------------

    def test_missing_api_key_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test missing BRAVE_API_KEY raises ToolExecutionError."""
        # Ensure BRAVE_API_KEY is not set
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)

        with pytest.raises(ToolExecutionError, match="BRAVE_API_KEY is not set"):
            _run_brave_search(
                "mcp-official:brave-search",
                params={"query": "test"},
            )

    def test_empty_api_key_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test empty BRAVE_API_KEY raises ToolExecutionError."""
        monkeypatch.setenv("BRAVE_API_KEY", "")

        with pytest.raises(ToolExecutionError, match="BRAVE_API_KEY is not set"):
            _run_brave_search(
                "mcp-official:brave-search",
                params={"query": "test"},
            )

    def test_error_message_includes_export_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test error message includes helpful export command."""
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)

        with pytest.raises(ToolExecutionError) as exc_info:
            _run_brave_search(
                "mcp-official:brave-search",
                params={"query": "test"},
            )

        assert "export BRAVE_API_KEY" in str(exc_info.value)

    # --------------------------------------------------------------------------
    # HTTP Request Tests
    # --------------------------------------------------------------------------

    def test_http_error_raises_tool_execution_error(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MagicMock
    ) -> None:
        """Test HTTP error is wrapped in ToolExecutionError."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        # Create a mock response with a status code error
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden",
            request=MagicMock(),
            response=mock_response,
        )
        mocker.patch("httpx.get", return_value=mock_response)

        with pytest.raises(ToolExecutionError, match="Brave API HTTP 403"):
            _run_brave_search(
                "mcp-official:brave-search",
                params={"query": "test"},
            )

    def test_network_error_raises_tool_execution_error(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MagicMock
    ) -> None:
        """Test network error is wrapped in ToolExecutionError."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mocker.patch("httpx.get", side_effect=httpx.ConnectError("Connection failed"))

        with pytest.raises(ToolExecutionError, match="Brave API request failed"):
            _run_brave_search(
                "mcp-official:brave-search",
                params={"query": "test"},
            )

    def test_timeout_error_raises_tool_execution_error(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MagicMock
    ) -> None:
        """Test timeout error is wrapped in ToolExecutionError."""
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mocker.patch("httpx.get", side_effect=httpx.TimeoutException("Request timed out"))

        with pytest.raises(ToolExecutionError, match="Brave API request failed"):
            _run_brave_search(
                "mcp-official:brave-search",
                params={"query": "test"},
            )

    def test_correct_api_url_used(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test correct Brave API URL is used."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_get = mocker.patch("httpx.get")
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        _run_brave_search("mcp-official:brave-search", params={"query": "test"})

        call_args = mock_get.call_args
        assert call_args[0][0] == "https://api.search.brave.com/res/v1/web/search"

    def test_correct_headers_sent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test correct headers are sent with request."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "my-api-key-123")

        mock_get = mocker.patch("httpx.get")
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        _run_brave_search("mcp-official:brave-search", params={"query": "test"})

        call_kwargs = mock_get.call_args[1]
        headers = call_kwargs["headers"]
        assert headers["Accept"] == "application/json"
        assert headers["X-Subscription-Token"] == "my-api-key-123"
        assert headers["User-Agent"] == "cub-toolsmith/0.1"

    def test_correct_query_params_sent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test correct query parameters are sent."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_get = mocker.patch("httpx.get")
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        _run_brave_search(
            "mcp-official:brave-search",
            params={"query": "python tutorial", "count": 10},
        )

        call_kwargs = mock_get.call_args[1]
        params = call_kwargs["params"]
        assert params["q"] == "python tutorial"
        assert params["count"] == "10"

    def test_timeout_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test request timeout is set."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_get = mocker.patch("httpx.get")
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        _run_brave_search("mcp-official:brave-search", params={"query": "test"})

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["timeout"] == 30.0

    # --------------------------------------------------------------------------
    # Success Path Tests
    # --------------------------------------------------------------------------

    def test_success_returns_tool_run_result(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test successful execution returns ToolRunResult."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Result 1", "url": "https://example.com/1"},
                    {"title": "Result 2", "url": "https://example.com/2"},
                ]
            }
        }
        mock_response.raise_for_status.return_value = None
        mocker.patch("httpx.get", return_value=mock_response)

        result = _run_brave_search(
            "mcp-official:brave-search",
            params={"query": "test query"},
        )

        assert isinstance(result, ToolRunResult)
        assert result.tool_id == "mcp-official:brave-search"
        assert isinstance(result.created_at, datetime)
        assert isinstance(result.artifact_path, Path)
        assert "2 result(s)" in result.summary
        assert "test query" in result.summary

    def test_success_writes_artifact(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test successful execution writes artifact file."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        api_response = {
            "web": {
                "results": [{"title": "Test Result"}]
            }
        }
        mock_response = MagicMock()
        mock_response.json.return_value = api_response
        mock_response.raise_for_status.return_value = None
        mocker.patch("httpx.get", return_value=mock_response)

        result = _run_brave_search(
            "mcp-official:brave-search",
            params={"query": "test", "count": 3},
        )

        # Verify artifact file exists and contains expected data
        assert result.artifact_path.exists()
        artifact_content = json.loads(result.artifact_path.read_text())
        assert artifact_content["tool_id"] == "mcp-official:brave-search"
        assert artifact_content["params"]["query"] == "test"
        assert artifact_content["params"]["count"] == 3
        assert artifact_content["result"] == api_response

    def test_success_summary_with_no_results(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test summary message when no results returned."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mocker.patch("httpx.get", return_value=mock_response)

        result = _run_brave_search(
            "mcp-official:brave-search",
            params={"query": "obscure query"},
        )

        assert "0 result(s)" in result.summary
        assert "obscure query" in result.summary

    def test_success_handles_missing_web_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test handles API response missing 'web' key gracefully."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {}  # No 'web' key
        mock_response.raise_for_status.return_value = None
        mocker.patch("httpx.get", return_value=mock_response)

        result = _run_brave_search(
            "mcp-official:brave-search",
            params={"query": "test"},
        )

        # Should not raise, summary should show 0 results
        assert "0 result(s)" in result.summary

    def test_success_handles_missing_results_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test handles API response missing 'results' key gracefully."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {}}  # No 'results' key
        mock_response.raise_for_status.return_value = None
        mocker.patch("httpx.get", return_value=mock_response)

        result = _run_brave_search(
            "mcp-official:brave-search",
            params={"query": "test"},
        )

        # Should not raise, summary should show 0 results
        assert "0 result(s)" in result.summary

    def test_created_at_is_utc(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test created_at timestamp is in UTC."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mocker.patch("httpx.get", return_value=mock_response)

        before = datetime.now(timezone.utc)
        result = _run_brave_search(
            "mcp-official:brave-search",
            params={"query": "test"},
        )
        after = datetime.now(timezone.utc)

        assert result.created_at.tzinfo is not None
        assert before <= result.created_at <= after

    def test_artifact_contains_iso_timestamp(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MagicMock
    ) -> None:
        """Test artifact file contains ISO-formatted timestamp."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mocker.patch("httpx.get", return_value=mock_response)

        result = _run_brave_search(
            "mcp-official:brave-search",
            params={"query": "test"},
        )

        artifact_content = json.loads(result.artifact_path.read_text())
        # ISO format should have 'T' separator and '+00:00' or 'Z' for UTC
        assert "T" in artifact_content["created_at"]
