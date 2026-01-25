"""
Tests for tool adapter protocol and registry.

Tests the adapter registry, adapter management functions, and ToolResult structure.
"""

from datetime import datetime, timezone

import pytest

from cub.core.tools import adapter as tools_adapter
from cub.core.tools.adapter import (
    ToolAdapter,
    get_adapter,
    is_adapter_available,
    list_adapters,
    register_adapter,
)
from cub.core.tools.models import AdapterType, ToolResult


class TestAdapterRegistry:
    """Test adapter registration and retrieval."""

    def test_register_adapter(self):
        """Test registering an adapter."""

        @register_adapter("test-adapter")
        class TestAdapter:
            @property
            def adapter_type(self) -> str:
                return "test-adapter"

            async def execute(self, tool_id, action, params, timeout=30.0):
                return ToolResult(
                    tool_id=tool_id,
                    action=action,
                    success=True,
                    output={"result": "test"},
                    started_at=datetime.now(timezone.utc),
                    adapter_type=AdapterType.HTTP,
                )

            async def is_available(self, tool_id: str) -> bool:
                return True

            async def health_check(self) -> bool:
                return True

        # Verify adapter is registered
        assert "test-adapter" in list_adapters()

        # Clean up
        tools_adapter._adapters.pop("test-adapter", None)

    def test_get_adapter_by_type(self):
        """Test getting an adapter by type."""

        @register_adapter("test-get")
        class TestAdapter:
            @property
            def adapter_type(self) -> str:
                return "test-get"

            async def execute(self, tool_id, action, params, timeout=30.0):
                return ToolResult(
                    tool_id=tool_id,
                    action=action,
                    success=True,
                    output={"result": "test"},
                    started_at=datetime.now(timezone.utc),
                    adapter_type=AdapterType.HTTP,
                )

            async def is_available(self, tool_id: str) -> bool:
                return True

            async def health_check(self) -> bool:
                return True

        adapter = get_adapter("test-get")
        assert isinstance(adapter, TestAdapter)
        assert adapter.adapter_type == "test-get"

        # Clean up
        tools_adapter._adapters.pop("test-get", None)

    def test_get_adapter_invalid_type(self):
        """Test getting an invalid adapter raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            get_adapter("nonexistent-adapter")

    def test_list_adapters(self):
        """Test listing all registered adapters."""
        # Clear any existing test adapters
        test_adapters = [k for k in list_adapters() if k.startswith("test-")]
        for name in test_adapters:
            tools_adapter._adapters.pop(name, None)

        @register_adapter("test-list-1")
        class TestAdapter1:
            @property
            def adapter_type(self) -> str:
                return "test-list-1"

            async def execute(self, tool_id, action, params, timeout=30.0):
                return ToolResult(
                    tool_id=tool_id,
                    action=action,
                    success=True,
                    output={},
                    started_at=datetime.now(timezone.utc),
                    adapter_type=AdapterType.HTTP,
                )

            async def is_available(self, tool_id: str) -> bool:
                return True

            async def health_check(self) -> bool:
                return True

        @register_adapter("test-list-2")
        class TestAdapter2:
            @property
            def adapter_type(self) -> str:
                return "test-list-2"

            async def execute(self, tool_id, action, params, timeout=30.0):
                return ToolResult(
                    tool_id=tool_id,
                    action=action,
                    success=True,
                    output={},
                    started_at=datetime.now(timezone.utc),
                    adapter_type=AdapterType.HTTP,
                )

            async def is_available(self, tool_id: str) -> bool:
                return True

            async def health_check(self) -> bool:
                return True

        adapters = list_adapters()
        assert "test-list-1" in adapters
        assert "test-list-2" in adapters

        # Clean up
        tools_adapter._adapters.pop("test-list-1", None)
        tools_adapter._adapters.pop("test-list-2", None)


class TestAdapterAvailability:
    """Test adapter availability detection."""

    def test_is_adapter_available_true(self):
        """Test is_adapter_available returns True for registered adapter."""

        @register_adapter("test-available")
        class TestAdapter:
            @property
            def adapter_type(self) -> str:
                return "test-available"

            async def execute(self, tool_id, action, params, timeout=30.0):
                return ToolResult(
                    tool_id=tool_id,
                    action=action,
                    success=True,
                    output={},
                    started_at=datetime.now(timezone.utc),
                    adapter_type=AdapterType.HTTP,
                )

            async def is_available(self, tool_id: str) -> bool:
                return True

            async def health_check(self) -> bool:
                return True

        assert is_adapter_available("test-available") is True

        # Clean up
        tools_adapter._adapters.pop("test-available", None)

    def test_is_adapter_available_false(self):
        """Test is_adapter_available returns False for nonexistent adapter."""
        assert is_adapter_available("does-not-exist") is False


class TestToolResult:
    """Test ToolResult structure."""

    def test_tool_result_success(self):
        """Test creating a successful ToolResult."""
        started_at = datetime.now(timezone.utc)
        result = ToolResult(
            tool_id="test-tool",
            action="test-action",
            success=True,
            output={"data": "test"},
            output_markdown="# Test Result",
            started_at=started_at,
            duration_ms=150,
            tokens_used=100,
            adapter_type=AdapterType.HTTP,
            metadata={"status": 200},
        )

        assert result.tool_id == "test-tool"
        assert result.action == "test-action"
        assert result.success is True
        assert result.output == {"data": "test"}
        assert result.output_markdown == "# Test Result"
        assert result.started_at == started_at
        assert result.duration_ms == 150
        assert result.tokens_used == 100
        assert result.adapter_type == AdapterType.HTTP
        assert result.error is None
        assert result.metadata == {"status": 200}

    def test_tool_result_failure(self):
        """Test creating a failed ToolResult."""
        started_at = datetime.now(timezone.utc)
        result = ToolResult(
            tool_id="test-tool",
            action="test-action",
            success=False,
            output=None,
            started_at=started_at,
            error="Connection timeout",
            error_type="timeout",
            duration_ms=30000,
            adapter_type=AdapterType.CLI,
        )

        assert result.tool_id == "test-tool"
        assert result.action == "test-action"
        assert result.success is False
        assert result.output is None
        assert result.error == "Connection timeout"
        assert result.error_type == "timeout"
        assert result.duration_ms == 30000
        assert result.adapter_type == AdapterType.CLI
        assert result.tokens_used is None

    def test_tool_result_minimal(self):
        """Test creating a ToolResult with minimal fields."""
        started_at = datetime.now(timezone.utc)
        result = ToolResult(
            tool_id="test-tool",
            action="test-action",
            success=True,
            output="simple output",
            started_at=started_at,
            adapter_type=AdapterType.MCP_STDIO,
        )

        assert result.tool_id == "test-tool"
        assert result.action == "test-action"
        assert result.success is True
        assert result.output == "simple output"
        assert result.started_at == started_at
        assert result.adapter_type == AdapterType.MCP_STDIO
        assert result.output_markdown is None
        assert result.duration_ms == 0
        assert result.tokens_used is None
        assert result.error is None
        assert result.error_type is None
        assert result.artifact_path is None
        assert result.metadata is None


class TestProtocolConformance:
    """Test that Protocol runtime checking works correctly."""

    def test_protocol_isinstance_check(self):
        """Test runtime Protocol checking with isinstance."""

        @register_adapter("test-protocol")
        class TestAdapter:
            @property
            def adapter_type(self) -> str:
                return "test-protocol"

            async def execute(self, tool_id, action, params, timeout=30.0):
                return ToolResult(
                    tool_id=tool_id,
                    action=action,
                    success=True,
                    output={},
                    started_at=datetime.now(timezone.utc),
                    adapter_type=AdapterType.HTTP,
                )

            async def is_available(self, tool_id: str) -> bool:
                return True

            async def health_check(self) -> bool:
                return True

        adapter = get_adapter("test-protocol")
        assert isinstance(adapter, ToolAdapter)

        # Clean up
        tools_adapter._adapters.pop("test-protocol", None)

    def test_protocol_missing_methods(self):
        """Test that class missing protocol methods is not a ToolAdapter."""

        class IncompleteAdapter:
            @property
            def adapter_type(self) -> str:
                return "incomplete"

        incomplete = IncompleteAdapter()
        # This should be False because execute, is_available, health_check are missing
        assert not isinstance(incomplete, ToolAdapter)
