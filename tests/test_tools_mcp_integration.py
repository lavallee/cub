"""
Integration tests for MCP adapter with real subprocess.

These tests use the mock MCP server fixture to test actual process communication,
complementing the unit tests that use mocking.
"""

import os
import sys

import pytest

from cub.core.tools.adapters.mcp_stdio import MCPStdioAdapter
from cub.core.tools.models import AdapterType, MCPConfig

# Path to the mock server
MOCK_SERVER_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "mock_mcp_server.py")


@pytest.mark.asyncio
class TestMCPStdioAdapterRealSubprocess:
    """Test MCP adapter with real subprocess communication."""

    async def test_execute_with_real_subprocess_tools_list(self) -> None:
        """Test tools/list with real subprocess."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command=sys.executable,  # Use current Python interpreter
            args=[MOCK_SERVER_PATH],
        )

        result = await adapter.execute(
            tool_id="mock-server",
            action="tools/list",
            params={"_mcp_config": config},
            timeout=5.0,
        )

        assert result.success is True
        assert result.tool_id == "mock-server"
        assert result.action == "tools/list"
        assert result.adapter_type == AdapterType.MCP_STDIO
        assert "tools" in result.output
        assert len(result.output["tools"]) == 2
        assert result.output["tools"][0]["name"] == "read_file"
        assert result.output["tools"][1]["name"] == "write_file"

    async def test_execute_with_real_subprocess_read_file(self) -> None:
        """Test tools/call (read_file) with real subprocess."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command=sys.executable,
            args=[MOCK_SERVER_PATH],
        )

        result = await adapter.execute(
            tool_id="mock-server",
            action="tools/call",
            params={
                "_mcp_config": config,
                "name": "read_file",
                "arguments": {"path": "/test/file.txt"},
            },
            timeout=5.0,
        )

        assert result.success is True
        assert "content" in result.output
        assert len(result.output["content"]) == 1
        assert result.output["content"][0]["type"] == "text"
        assert "Mock content of /test/file.txt" in result.output["content"][0]["text"]

    async def test_execute_with_real_subprocess_write_file(self) -> None:
        """Test tools/call (write_file) with real subprocess."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command=sys.executable,
            args=[MOCK_SERVER_PATH],
        )

        result = await adapter.execute(
            tool_id="mock-server",
            action="tools/call",
            params={
                "_mcp_config": config,
                "name": "write_file",
                "arguments": {
                    "path": "/test/output.txt",
                    "content": "Hello, world!",
                },
            },
            timeout=5.0,
        )

        assert result.success is True
        assert "content" in result.output
        assert result.output["content"][0]["type"] == "text"
        assert "Successfully wrote" in result.output["content"][0]["text"]

    async def test_execute_with_real_subprocess_missing_params(self) -> None:
        """Test tools/call with missing params - server returns error."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command=sys.executable,
            args=[MOCK_SERVER_PATH],
        )

        result = await adapter.execute(
            tool_id="mock-server",
            action="tools/call",
            params={
                "_mcp_config": config,
                "name": "read_file",
                "arguments": {},  # Missing 'path' parameter
            },
            timeout=5.0,
        )

        assert result.success is False
        assert result.error_type == "validation"
        assert result.error is not None
        assert "Invalid params" in result.error
        assert result.metadata is not None
        assert result.metadata["error_code"] == -32602

    async def test_execute_with_real_subprocess_method_not_found(self) -> None:
        """Test tools/call with unknown tool - server returns error."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command=sys.executable,
            args=[MOCK_SERVER_PATH],
        )

        result = await adapter.execute(
            tool_id="mock-server",
            action="tools/call",
            params={
                "_mcp_config": config,
                "name": "nonexistent_tool",
                "arguments": {},
            },
            timeout=5.0,
        )

        assert result.success is False
        assert result.error_type == "validation"
        assert result.error is not None
        assert "Method not found" in result.error
        assert result.metadata is not None
        assert result.metadata["error_code"] == -32601

    async def test_execute_with_real_subprocess_server_error(self) -> None:
        """Test tools/call with server error response."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command=sys.executable,
            args=[MOCK_SERVER_PATH],
        )

        result = await adapter.execute(
            tool_id="mock-server",
            action="tools/call",
            params={
                "_mcp_config": config,
                "name": "error_test",
                "arguments": {},
            },
            timeout=5.0,
        )

        assert result.success is False
        assert result.error_type == "execution"
        assert result.error is not None
        assert "Server error" in result.error
        assert result.metadata is not None
        assert result.metadata["error_code"] == -32000

    async def test_execute_with_real_subprocess_initialize(self) -> None:
        """Test initialize method with real subprocess."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command=sys.executable,
            args=[MOCK_SERVER_PATH],
        )

        result = await adapter.execute(
            tool_id="mock-server",
            action="initialize",
            params={
                "_mcp_config": config,
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "cub-test",
                    "version": "1.0.0",
                },
            },
            timeout=5.0,
        )

        assert result.success is True
        assert "protocolVersion" in result.output
        assert "capabilities" in result.output
        assert "serverInfo" in result.output
        assert result.output["serverInfo"]["name"] == "mock-mcp-server"

    async def test_execute_with_real_subprocess_timeout(self) -> None:
        """Test timeout with a command that takes too long."""
        adapter = MCPStdioAdapter()

        # Use sleep command to simulate timeout
        config = MCPConfig(
            command="sleep",
            args=["10"],  # Sleep for 10 seconds
        )

        result = await adapter.execute(
            tool_id="slow-server",
            action="test",
            params={"_mcp_config": config},
            timeout=0.1,  # Very short timeout
        )

        assert result.success is False
        assert result.error is not None
        assert "timed out" in result.error.lower()
        assert result.error_type == "timeout"

    async def test_execute_with_real_subprocess_command_not_found(self) -> None:
        """Test with a command that doesn't exist."""
        adapter = MCPStdioAdapter()

        config = MCPConfig(
            command="nonexistent_command_12345",
            args=[],
        )

        result = await adapter.execute(
            tool_id="missing-server",
            action="test",
            params={"_mcp_config": config},
            timeout=5.0,
        )

        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error.lower()
        assert result.error_type == "validation"
