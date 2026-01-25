"""
Tests for MCPStdioAdapter.

Tests the MCP stdio adapter with JSON-RPC over stdio communication,
timeout handling, and error classification.
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cub.core.tools.adapters.mcp_stdio import MCPStdioAdapter
from cub.core.tools.models import AdapterType, MCPConfig


class TestMCPStdioAdapter:
    """Test MCPStdioAdapter initialization and basic properties."""

    def test_adapter_type(self):
        """Test adapter returns correct type."""
        adapter = MCPStdioAdapter()
        assert adapter.adapter_type == "mcp_stdio"

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check succeeds."""
        adapter = MCPStdioAdapter()
        # Health check should succeed (runs echo command)
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check handles failures gracefully."""
        adapter = MCPStdioAdapter()
        # Mock subprocess to raise an error
        with patch(
            "cub.core.tools.adapters.mcp_stdio.asyncio.create_subprocess_exec",
            side_effect=Exception("Subprocess error"),
        ):
            assert await adapter.health_check() is False

    @pytest.mark.asyncio
    async def test_is_available(self):
        """Test tool availability check."""
        adapter = MCPStdioAdapter()
        # For now, is_available returns True optimistically
        assert await adapter.is_available("test-tool") is True


class TestMCPStdioAdapterExecute:
    """Test MCPStdioAdapter execute method."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful MCP execution with JSON-RPC response."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="mcp-server-test",
            args=["--test"],
        )

        # Mock JSON-RPC response
        response = {
            "jsonrpc": "2.0",
            "id": None,  # Will be matched by request_id
            "result": {"content": [{"type": "text", "text": "Hello, world!"}]},
        }

        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.pid = 12345
        mock_process.stdin = AsyncMock()
        mock_process.stdin.write = Mock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdin.close = Mock()
        mock_process.stdin.wait_closed = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        # Capture the request to get the ID for the response
        captured_request = {}

        def capture_write(data):
            nonlocal response
            captured_request["data"] = data
            # Parse the request to get the ID
            request = json.loads(data.decode("utf-8").strip())
            # Update response with the correct ID
            response["id"] = request["id"]

        mock_process.stdin.write = Mock(side_effect=capture_write)
        mock_process.stdout.read = AsyncMock(
            return_value=json.dumps(response).encode("utf-8")
        )
        mock_process.stderr.read = AsyncMock(return_value=b"")

        with patch(
            "cub.core.tools.adapters.mcp_stdio.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            result = await adapter.execute(
                tool_id="test-server",
                action="read_file",
                params={"_mcp_config": config, "path": "/test/file.txt"},
                timeout=30.0,
            )

        assert result.success is True
        assert result.tool_id == "test-server"
        assert result.action == "read_file"
        assert result.output == {"content": [{"type": "text", "text": "Hello, world!"}]}
        assert result.adapter_type == AdapterType.MCP_STDIO
        assert result.duration_ms >= 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_execute_missing_config(self):
        """Test execution fails gracefully when config is missing."""
        adapter = MCPStdioAdapter()

        result = await adapter.execute(
            tool_id="test-server",
            action="test",
            params={"query": "test"},
            timeout=30.0,
        )

        assert result.success is False
        assert result.error == "MCP configuration not provided"
        assert result.error_type == "validation"

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """Test execution handles timeout gracefully."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="mcp-server-slow",
            args=[],
        )

        # Mock the subprocess to simulate timeout
        mock_process = AsyncMock()
        mock_process.returncode = None  # Still running
        mock_process.pid = 12345
        mock_process.stdin = AsyncMock()
        mock_process.stdin.write = Mock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdin.close = Mock()
        mock_process.stdin.wait_closed = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.terminate = Mock()
        mock_process.kill = Mock()
        mock_process.wait = AsyncMock()

        # Make communicate take too long
        async def slow_read():
            await asyncio.sleep(10)
            return b""

        mock_process.stdout.read = slow_read
        mock_process.stderr.read = AsyncMock(return_value=b"")

        with patch(
            "cub.core.tools.adapters.mcp_stdio.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ), patch(
            "cub.core.tools.adapters.mcp_stdio.os.getpgid",
            return_value=12345,
        ), patch(
            "cub.core.tools.adapters.mcp_stdio.os.killpg",
        ):
            result = await adapter.execute(
                tool_id="slow-server",
                action="slow_action",
                params={"_mcp_config": config},
                timeout=0.1,
            )

        assert result.success is False
        assert "timed out" in result.error.lower()
        assert result.error_type == "timeout"

    @pytest.mark.asyncio
    async def test_execute_command_not_found(self):
        """Test execution handles command not found."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="nonexistent-mcp-server",
            args=[],
        )

        with patch(
            "cub.core.tools.adapters.mcp_stdio.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("Command not found"),
        ):
            result = await adapter.execute(
                tool_id="missing-server",
                action="test",
                params={"_mcp_config": config},
                timeout=30.0,
            )

        assert result.success is False
        assert "not found" in result.error.lower()
        assert result.error_type == "validation"

    @pytest.mark.asyncio
    async def test_execute_jsonrpc_error(self):
        """Test execution handles JSON-RPC error response."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="mcp-server-error",
            args=[],
        )

        # Mock JSON-RPC error response
        response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32601,
                "message": "Method not found",
            },
        }

        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.pid = 12345
        mock_process.stdin = AsyncMock()
        mock_process.stdin.write = Mock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdin.close = Mock()
        mock_process.stdin.wait_closed = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()

        def capture_write(data):
            nonlocal response
            request = json.loads(data.decode("utf-8").strip())
            response["id"] = request["id"]

        mock_process.stdin.write = Mock(side_effect=capture_write)
        mock_process.stdout.read = AsyncMock(
            return_value=json.dumps(response).encode("utf-8")
        )
        mock_process.stderr.read = AsyncMock(return_value=b"")

        with patch(
            "cub.core.tools.adapters.mcp_stdio.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            result = await adapter.execute(
                tool_id="error-server",
                action="nonexistent_method",
                params={"_mcp_config": config},
                timeout=30.0,
            )

        assert result.success is False
        assert "Method not found" in result.error
        assert result.error_type == "validation"  # -32601 is method not found
        assert result.metadata["error_code"] == -32601

    @pytest.mark.asyncio
    async def test_execute_empty_response(self):
        """Test execution handles empty response."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="mcp-server-empty",
            args=[],
        )

        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.pid = 12345
        mock_process.stdin = AsyncMock()
        mock_process.stdin.write = Mock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdin.close = Mock()
        mock_process.stdin.wait_closed = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()

        mock_process.stdout.read = AsyncMock(return_value=b"")
        mock_process.stderr.read = AsyncMock(return_value=b"")

        with patch(
            "cub.core.tools.adapters.mcp_stdio.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            result = await adapter.execute(
                tool_id="empty-server",
                action="test",
                params={"_mcp_config": config},
                timeout=30.0,
            )

        assert result.success is False
        assert "empty response" in result.error.lower()
        assert result.error_type == "protocol"

    @pytest.mark.asyncio
    async def test_execute_invalid_json_response(self):
        """Test execution handles invalid JSON response."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="mcp-server-invalid",
            args=[],
        )

        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.pid = 12345
        mock_process.stdin = AsyncMock()
        mock_process.stdin.write = Mock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdin.close = Mock()
        mock_process.stdin.wait_closed = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()

        mock_process.stdout.read = AsyncMock(
            return_value=b"not valid json at all"
        )
        mock_process.stderr.read = AsyncMock(return_value=b"")

        with patch(
            "cub.core.tools.adapters.mcp_stdio.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            result = await adapter.execute(
                tool_id="invalid-server",
                action="test",
                params={"_mcp_config": config},
                timeout=30.0,
            )

        assert result.success is False
        assert "parse" in result.error.lower() or "json" in result.error.lower()
        assert result.error_type == "protocol"

    @pytest.mark.asyncio
    async def test_execute_with_env_vars(self):
        """Test execution with custom environment variables."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="mcp-server-test",
            args=[],
            env_vars={"MCP_API_KEY": "test_key", "MCP_DEBUG": "true"},
        )

        response = {
            "jsonrpc": "2.0",
            "id": None,
            "result": {"status": "ok"},
        }

        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.pid = 12345
        mock_process.stdin = AsyncMock()
        mock_process.stdin.write = Mock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdin.close = Mock()
        mock_process.stdin.wait_closed = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()

        def capture_write(data):
            nonlocal response
            request = json.loads(data.decode("utf-8").strip())
            response["id"] = request["id"]

        mock_process.stdin.write = Mock(side_effect=capture_write)
        mock_process.stdout.read = AsyncMock(
            return_value=json.dumps(response).encode("utf-8")
        )
        mock_process.stderr.read = AsyncMock(return_value=b"")

        with patch(
            "cub.core.tools.adapters.mcp_stdio.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ) as mock_exec:
            result = await adapter.execute(
                tool_id="env-server",
                action="test",
                params={"_mcp_config": config},
                timeout=30.0,
            )

        assert result.success is True
        # Verify env was passed to subprocess
        call_kwargs = mock_exec.call_args[1]
        assert "env" in call_kwargs
        assert call_kwargs["env"]["MCP_API_KEY"] == "test_key"
        assert call_kwargs["env"]["MCP_DEBUG"] == "true"

    @pytest.mark.asyncio
    async def test_execute_unexpected_error(self):
        """Test execution handles unexpected errors."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="mcp-server-test",
            args=[],
        )

        with patch(
            "cub.core.tools.adapters.mcp_stdio.asyncio.create_subprocess_exec",
            side_effect=RuntimeError("Unexpected error"),
        ):
            result = await adapter.execute(
                tool_id="test-server",
                action="test",
                params={"_mcp_config": config},
                timeout=30.0,
            )

        assert result.success is False
        assert "Unexpected error" in result.error
        assert result.error_type == "unknown"

    @pytest.mark.asyncio
    async def test_execute_multiline_response(self):
        """Test execution handles multiline JSON-RPC responses."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="mcp-server-test",
            args=[],
        )

        # Some MCP servers output multiple messages (e.g., initialization + result)
        init_message = {"jsonrpc": "2.0", "method": "initialize", "params": {}}
        response = {
            "jsonrpc": "2.0",
            "id": None,
            "result": {"data": "success"},
        }

        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.pid = 12345
        mock_process.stdin = AsyncMock()
        mock_process.stdin.write = Mock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdin.close = Mock()
        mock_process.stdin.wait_closed = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()

        def capture_write(data):
            nonlocal response
            request = json.loads(data.decode("utf-8").strip())
            response["id"] = request["id"]

        mock_process.stdin.write = Mock(side_effect=capture_write)

        # Return multiline response
        multiline_output = (
            json.dumps(init_message) + "\n" + json.dumps(response)
        ).encode("utf-8")
        mock_process.stdout.read = AsyncMock(return_value=multiline_output)
        mock_process.stderr.read = AsyncMock(return_value=b"")

        with patch(
            "cub.core.tools.adapters.mcp_stdio.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            result = await adapter.execute(
                tool_id="multiline-server",
                action="test",
                params={"_mcp_config": config},
                timeout=30.0,
            )

        assert result.success is True
        assert result.output == {"data": "success"}


class TestMCPStdioAdapterHelpers:
    """Test MCPStdioAdapter helper methods."""

    def test_build_env_no_vars(self):
        """Test environment building with no custom vars."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="test",
            args=[],
        )

        env = adapter._build_env(config)
        assert env is None

    def test_build_env_with_vars(self):
        """Test environment building with custom vars."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="test",
            args=[],
            env_vars={"MY_VAR": "value", "ANOTHER_VAR": "value2"},
        )

        env = adapter._build_env(config)
        assert env is not None
        assert env["MY_VAR"] == "value"
        assert env["ANOTHER_VAR"] == "value2"

    def test_build_jsonrpc_request(self):
        """Test JSON-RPC request building."""
        adapter = MCPStdioAdapter()

        request = adapter._build_jsonrpc_request(
            method="tools/call",
            params={
                "_mcp_config": None,
                "name": "read_file",
                "arguments": {"path": "/test.txt"},
            },
            request_id="test-123",
        )

        parsed = json.loads(request.strip())
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == "test-123"
        assert parsed["method"] == "tools/call"
        # Internal params should be filtered out
        assert "_mcp_config" not in parsed["params"]
        assert parsed["params"]["name"] == "read_file"
        assert parsed["params"]["arguments"] == {"path": "/test.txt"}

    def test_build_jsonrpc_request_filters_internal_params(self):
        """Test that internal params are filtered from request."""
        adapter = MCPStdioAdapter()

        request = adapter._build_jsonrpc_request(
            method="test",
            params={
                "_mcp_config": "should_be_filtered",
                "_internal": "also_filtered",
                "public_param": "included",
            },
            request_id="test-456",
        )

        parsed = json.loads(request.strip())
        assert "_mcp_config" not in parsed["params"]
        assert "_internal" not in parsed["params"]
        assert parsed["params"]["public_param"] == "included"

    def test_classify_jsonrpc_error_parse_error(self):
        """Test error classification for parse error."""
        adapter = MCPStdioAdapter()
        assert adapter._classify_jsonrpc_error(-32700) == "protocol"

    def test_classify_jsonrpc_error_invalid_request(self):
        """Test error classification for invalid request."""
        adapter = MCPStdioAdapter()
        assert adapter._classify_jsonrpc_error(-32600) == "validation"

    def test_classify_jsonrpc_error_method_not_found(self):
        """Test error classification for method not found."""
        adapter = MCPStdioAdapter()
        assert adapter._classify_jsonrpc_error(-32601) == "validation"

    def test_classify_jsonrpc_error_invalid_params(self):
        """Test error classification for invalid params."""
        adapter = MCPStdioAdapter()
        assert adapter._classify_jsonrpc_error(-32602) == "validation"

    def test_classify_jsonrpc_error_internal_error(self):
        """Test error classification for internal error."""
        adapter = MCPStdioAdapter()
        assert adapter._classify_jsonrpc_error(-32603) == "execution"

    def test_classify_jsonrpc_error_server_error(self):
        """Test error classification for server error range."""
        adapter = MCPStdioAdapter()
        assert adapter._classify_jsonrpc_error(-32000) == "execution"
        assert adapter._classify_jsonrpc_error(-32050) == "execution"
        assert adapter._classify_jsonrpc_error(-32099) == "execution"

    def test_classify_jsonrpc_error_unknown(self):
        """Test error classification for unknown error code."""
        adapter = MCPStdioAdapter()
        assert adapter._classify_jsonrpc_error(0) == "unknown"
        assert adapter._classify_jsonrpc_error(100) == "unknown"
        assert adapter._classify_jsonrpc_error("not_a_number") == "unknown"

    def test_generate_markdown_dict_with_content(self):
        """Test markdown generation for dict result with content."""
        adapter = MCPStdioAdapter()

        markdown = adapter._generate_markdown(
            "filesystem-server",
            "read_file",
            {"content": [{"type": "text", "text": "file content"}]},
        )

        assert "filesystem-server" in markdown
        assert "read_file" in markdown
        assert "MCP" in markdown
        assert "Content items: 1" in markdown

    def test_generate_markdown_dict_with_tools(self):
        """Test markdown generation for dict result with tools."""
        adapter = MCPStdioAdapter()

        markdown = adapter._generate_markdown(
            "tool-server",
            "list_tools",
            {"tools": [{"name": "tool1"}, {"name": "tool2"}]},
        )

        assert "tool-server" in markdown
        assert "Tools: 2" in markdown

    def test_generate_markdown_list_result(self):
        """Test markdown generation for list result."""
        adapter = MCPStdioAdapter()

        markdown = adapter._generate_markdown(
            "list-server",
            "list_items",
            [{"id": 1}, {"id": 2}, {"id": 3}],
        )

        assert "list-server" in markdown
        assert "Items: 3" in markdown

    def test_generate_markdown_string_content(self):
        """Test markdown generation for string content."""
        adapter = MCPStdioAdapter()

        markdown = adapter._generate_markdown(
            "text-server",
            "get_text",
            {"content": "This is some text content"},
        )

        assert "text-server" in markdown
        assert "Content length:" in markdown


class TestMCPStdioAdapterIntegration:
    """Integration-style tests for MCPStdioAdapter."""

    @pytest.mark.asyncio
    async def test_execute_full_workflow(self):
        """Test complete execution workflow with all lifecycle stages."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="mcp-server-test",
            args=["--config", "/path/to/config"],
            env_vars={"TEST_ENV": "value"},
        )

        response = {
            "jsonrpc": "2.0",
            "id": None,
            "result": {
                "tools": [
                    {"name": "read_file", "description": "Read a file"},
                    {"name": "write_file", "description": "Write a file"},
                ]
            },
        }

        # Create a complete mock process
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.pid = 12345
        mock_process.stdin = AsyncMock()
        mock_process.stdin.write = Mock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdin.close = Mock()
        mock_process.stdin.wait_closed = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()

        def capture_write(data):
            nonlocal response
            request = json.loads(data.decode("utf-8").strip())
            response["id"] = request["id"]
            # Verify request structure
            assert request["jsonrpc"] == "2.0"
            assert request["method"] == "tools/list"
            assert "_mcp_config" not in request["params"]

        mock_process.stdin.write = Mock(side_effect=capture_write)
        mock_process.stdout.read = AsyncMock(
            return_value=json.dumps(response).encode("utf-8")
        )
        mock_process.stderr.read = AsyncMock(return_value=b"debug output")

        with patch(
            "cub.core.tools.adapters.mcp_stdio.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ) as mock_exec:
            result = await adapter.execute(
                tool_id="complete-server",
                action="tools/list",
                params={"_mcp_config": config},
                timeout=30.0,
            )

        # Verify subprocess was called with correct arguments
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args
        # Command and args
        assert call_args[0][0] == "mcp-server-test"
        assert "--config" in call_args[0]
        # Environment
        assert call_args[1]["env"]["TEST_ENV"] == "value"
        # Process group
        assert call_args[1]["start_new_session"] is True

        # Verify result
        assert result.success is True
        assert result.tool_id == "complete-server"
        assert result.action == "tools/list"
        assert len(result.output["tools"]) == 2
        assert result.adapter_type == AdapterType.MCP_STDIO
        assert result.output_markdown is not None
        assert "Tools: 2" in result.output_markdown
