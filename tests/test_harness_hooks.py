"""
Tests for harness hook system.

Tests hook registration, execution, and blocking behavior for:
- ClaudeSDKHarness (full hook support)
- ClaudeLegacyBackend (no-op hooks)
- CodexBackend (no-op hooks)
"""

import warnings
from typing import Any
from unittest.mock import patch

import pytest

from cub.core.harness import (
    HookContext,
    HookEvent,
    HookResult,
    TaskInput,
)

# Skip SDK tests if claude-agent-sdk is not installed
pytest.importorskip("claude_agent_sdk")

from cub.core.harness.claude_sdk import ClaudeSDKHarness


class TestHookTypes:
    """Tests for hook type definitions."""

    def test_hook_event_values(self) -> None:
        """Test HookEvent enum values."""
        assert HookEvent.PRE_TASK.value == "pre_task"
        assert HookEvent.POST_TASK.value == "post_task"
        assert HookEvent.PRE_TOOL_USE.value == "pre_tool_use"
        assert HookEvent.POST_TOOL_USE.value == "post_tool_use"
        assert HookEvent.ON_ERROR.value == "on_error"
        assert HookEvent.ON_MESSAGE.value == "on_message"

    def test_hook_context_creation(self) -> None:
        """Test HookContext dataclass creation."""
        context = HookContext(
            event=HookEvent.PRE_TASK,
            task_id="test-123",
            tool_name="Read",
            tool_input={"file_path": "/test.py"},
        )

        assert context.event == HookEvent.PRE_TASK
        assert context.task_id == "test-123"
        assert context.tool_name == "Read"
        assert context.tool_input == {"file_path": "/test.py"}
        assert context.error is None
        assert context.metadata == {}

    def test_hook_context_with_metadata(self) -> None:
        """Test HookContext with custom metadata."""
        context = HookContext(
            event=HookEvent.ON_ERROR,
            error=ValueError("test error"),
            metadata={"retry_count": 3},
        )

        assert context.event == HookEvent.ON_ERROR
        assert isinstance(context.error, ValueError)
        assert context.metadata["retry_count"] == 3

    def test_hook_result_defaults(self) -> None:
        """Test HookResult default values."""
        result = HookResult()

        assert result.block is False
        assert result.reason is None
        assert result.modified_input is None

    def test_hook_result_blocking(self) -> None:
        """Test HookResult with blocking."""
        result = HookResult(
            block=True,
            reason="Budget exceeded",
        )

        assert result.block is True
        assert result.reason == "Budget exceeded"


class TestClaudeSDKHarnessHooks:
    """Tests for ClaudeSDKHarness hook system."""

    def test_harness_initializes_empty_hooks(self) -> None:
        """Test harness initializes with empty hook registry."""
        harness = ClaudeSDKHarness()

        for event in HookEvent:
            assert event in harness._hooks
            assert len(harness._hooks[event]) == 0

    def test_register_hook(self) -> None:
        """Test registering a hook handler."""
        harness = ClaudeSDKHarness()

        async def my_hook(ctx: HookContext) -> HookResult | None:
            return None

        harness.register_hook(HookEvent.PRE_TASK, my_hook)

        assert len(harness._hooks[HookEvent.PRE_TASK]) == 1
        assert harness._hooks[HookEvent.PRE_TASK][0] is my_hook

    def test_register_multiple_hooks(self) -> None:
        """Test registering multiple hooks for same event."""
        harness = ClaudeSDKHarness()

        async def hook1(ctx: HookContext) -> HookResult | None:
            return None

        async def hook2(ctx: HookContext) -> HookResult | None:
            return None

        harness.register_hook(HookEvent.PRE_TASK, hook1)
        harness.register_hook(HookEvent.PRE_TASK, hook2)

        assert len(harness._hooks[HookEvent.PRE_TASK]) == 2
        assert harness._hooks[HookEvent.PRE_TASK][0] is hook1
        assert harness._hooks[HookEvent.PRE_TASK][1] is hook2

    def test_unregister_hook(self) -> None:
        """Test unregistering a hook handler."""
        harness = ClaudeSDKHarness()

        async def my_hook(ctx: HookContext) -> HookResult | None:
            return None

        harness.register_hook(HookEvent.PRE_TASK, my_hook)
        assert len(harness._hooks[HookEvent.PRE_TASK]) == 1

        result = harness.unregister_hook(HookEvent.PRE_TASK, my_hook)

        assert result is True
        assert len(harness._hooks[HookEvent.PRE_TASK]) == 0

    def test_unregister_nonexistent_hook(self) -> None:
        """Test unregistering a hook that doesn't exist."""
        harness = ClaudeSDKHarness()

        async def my_hook(ctx: HookContext) -> HookResult | None:
            return None

        result = harness.unregister_hook(HookEvent.PRE_TASK, my_hook)

        assert result is False

    def test_clear_hooks_for_event(self) -> None:
        """Test clearing hooks for a specific event."""
        harness = ClaudeSDKHarness()

        async def hook1(ctx: HookContext) -> HookResult | None:
            return None

        async def hook2(ctx: HookContext) -> HookResult | None:
            return None

        harness.register_hook(HookEvent.PRE_TASK, hook1)
        harness.register_hook(HookEvent.POST_TASK, hook2)

        harness.clear_hooks(HookEvent.PRE_TASK)

        assert len(harness._hooks[HookEvent.PRE_TASK]) == 0
        assert len(harness._hooks[HookEvent.POST_TASK]) == 1

    def test_clear_all_hooks(self) -> None:
        """Test clearing all hooks."""
        harness = ClaudeSDKHarness()

        async def hook1(ctx: HookContext) -> HookResult | None:
            return None

        harness.register_hook(HookEvent.PRE_TASK, hook1)
        harness.register_hook(HookEvent.POST_TASK, hook1)
        harness.register_hook(HookEvent.ON_ERROR, hook1)

        harness.clear_hooks()

        for event in HookEvent:
            assert len(harness._hooks[event]) == 0

    @pytest.mark.asyncio
    async def test_execute_hooks_no_handlers(self) -> None:
        """Test executing hooks when no handlers registered."""
        harness = ClaudeSDKHarness()
        context = HookContext(event=HookEvent.PRE_TASK)

        result = await harness._execute_hooks(HookEvent.PRE_TASK, context)

        assert result.block is False

    @pytest.mark.asyncio
    async def test_execute_hooks_allow(self) -> None:
        """Test executing hooks that allow the action."""
        harness = ClaudeSDKHarness()
        called = []

        async def allowing_hook(ctx: HookContext) -> HookResult | None:
            called.append("hook")
            return None  # Allow action

        harness.register_hook(HookEvent.PRE_TASK, allowing_hook)
        context = HookContext(event=HookEvent.PRE_TASK)

        result = await harness._execute_hooks(HookEvent.PRE_TASK, context)

        assert result.block is False
        assert called == ["hook"]

    @pytest.mark.asyncio
    async def test_execute_hooks_block(self) -> None:
        """Test executing hooks that block the action."""
        harness = ClaudeSDKHarness()

        async def blocking_hook(ctx: HookContext) -> HookResult:
            return HookResult(block=True, reason="Test block")

        harness.register_hook(HookEvent.PRE_TASK, blocking_hook)
        context = HookContext(event=HookEvent.PRE_TASK)

        result = await harness._execute_hooks(HookEvent.PRE_TASK, context)

        assert result.block is True
        assert result.reason == "Test block"

    @pytest.mark.asyncio
    async def test_execute_hooks_stops_on_block(self) -> None:
        """Test that hook execution stops when a hook blocks."""
        harness = ClaudeSDKHarness()
        called = []

        async def first_hook(ctx: HookContext) -> HookResult:
            called.append("first")
            return HookResult(block=True, reason="Blocked")

        async def second_hook(ctx: HookContext) -> HookResult | None:
            called.append("second")
            return None

        harness.register_hook(HookEvent.PRE_TASK, first_hook)
        harness.register_hook(HookEvent.PRE_TASK, second_hook)
        context = HookContext(event=HookEvent.PRE_TASK)

        await harness._execute_hooks(HookEvent.PRE_TASK, context)

        assert called == ["first"]  # Second hook not called

    @pytest.mark.asyncio
    async def test_execute_hooks_continues_on_exception(self) -> None:
        """Test that hook execution continues if a hook raises exception."""
        harness = ClaudeSDKHarness()
        called = []

        async def failing_hook(ctx: HookContext) -> HookResult | None:
            called.append("failing")
            raise ValueError("Hook error")

        async def success_hook(ctx: HookContext) -> HookResult | None:
            called.append("success")
            return None

        harness.register_hook(HookEvent.PRE_TASK, failing_hook)
        harness.register_hook(HookEvent.PRE_TASK, success_hook)
        context = HookContext(event=HookEvent.PRE_TASK)

        result = await harness._execute_hooks(HookEvent.PRE_TASK, context)

        assert called == ["failing", "success"]
        assert result.block is False


class TestClaudeSDKHarnessRunTaskHooks:
    """Tests for hook execution in run_task."""

    @pytest.mark.asyncio
    async def test_run_task_pre_task_hook_blocks(self) -> None:
        """Test that PRE_TASK hook can block task execution."""
        harness = ClaudeSDKHarness()

        async def blocking_hook(ctx: HookContext) -> HookResult:
            return HookResult(block=True, reason="Budget exceeded")

        harness.register_hook(HookEvent.PRE_TASK, blocking_hook)

        with patch.object(harness, "is_available", return_value=True):
            task_input = TaskInput(prompt="Hello")
            result = await harness.run_task(task_input)

            assert result.failed is True
            assert "Budget exceeded" in (result.error or "")

    @pytest.mark.asyncio
    async def test_run_task_pre_task_hook_allows(self) -> None:
        """Test that PRE_TASK hook allows task to proceed."""
        from claude_agent_sdk import AssistantMessage, ResultMessage
        from claude_agent_sdk.types import TextBlock

        harness = ClaudeSDKHarness()
        pre_task_called = []

        async def allowing_hook(ctx: HookContext) -> HookResult | None:
            pre_task_called.append(ctx.event)
            return None

        harness.register_hook(HookEvent.PRE_TASK, allowing_hook)

        messages = [
            AssistantMessage(
                content=[TextBlock(text="Hello back")],
                model="claude-sonnet-4-20250514",
            ),
            ResultMessage(
                subtype="success",
                duration_ms=1000,
                duration_api_ms=800,
                is_error=False,
                num_turns=1,
                session_id="test-session",
            ),
        ]

        async def mock_query(*args: Any, **kwargs: Any) -> Any:
            for msg in messages:
                yield msg

        with (
            patch.object(harness, "is_available", return_value=True),
            patch("claude_agent_sdk.query", mock_query),
        ):
            task_input = TaskInput(prompt="Hello")
            result = await harness.run_task(task_input)

            assert result.success is True
            assert pre_task_called == [HookEvent.PRE_TASK]

    @pytest.mark.asyncio
    async def test_run_task_post_task_hook_executes(self) -> None:
        """Test that POST_TASK hook executes after task."""
        from claude_agent_sdk import AssistantMessage, ResultMessage
        from claude_agent_sdk.types import TextBlock

        harness = ClaudeSDKHarness()
        post_task_called = []

        async def post_hook(ctx: HookContext) -> HookResult | None:
            post_task_called.append(ctx.event)
            post_task_called.append(ctx.metadata.get("output"))
            return None

        harness.register_hook(HookEvent.POST_TASK, post_hook)

        messages = [
            AssistantMessage(
                content=[TextBlock(text="Task output")],
                model="claude-sonnet-4-20250514",
            ),
            ResultMessage(
                subtype="success",
                duration_ms=1000,
                duration_api_ms=800,
                is_error=False,
                num_turns=1,
                session_id="test-session",
            ),
        ]

        async def mock_query(*args: Any, **kwargs: Any) -> Any:
            for msg in messages:
                yield msg

        with (
            patch.object(harness, "is_available", return_value=True),
            patch("claude_agent_sdk.query", mock_query),
        ):
            task_input = TaskInput(prompt="Hello")
            await harness.run_task(task_input)

            assert HookEvent.POST_TASK in post_task_called
            assert "Task output" in post_task_called

    @pytest.mark.asyncio
    async def test_run_task_on_error_hook_executes(self) -> None:
        """Test that ON_ERROR hook executes on error."""
        from claude_agent_sdk import CLINotFoundError

        harness = ClaudeSDKHarness()
        error_contexts = []

        async def error_hook(ctx: HookContext) -> HookResult | None:
            error_contexts.append(ctx)
            return None

        harness.register_hook(HookEvent.ON_ERROR, error_hook)

        async def mock_query(*args: Any, **kwargs: Any) -> Any:
            raise CLINotFoundError("Claude not found")
            yield  # Make it a generator

        with (
            patch.object(harness, "is_available", return_value=True),
            patch("claude_agent_sdk.query", mock_query),
        ):
            task_input = TaskInput(prompt="Hello")
            result = await harness.run_task(task_input)

            assert result.failed is True
            assert len(error_contexts) == 1
            assert error_contexts[0].event == HookEvent.ON_ERROR
            assert error_contexts[0].error is not None


class TestClaudeSDKHarnessStreamTaskHooks:
    """Tests for hook execution in stream_task."""

    @pytest.mark.asyncio
    async def test_stream_task_pre_task_hook_blocks(self) -> None:
        """Test that PRE_TASK hook can block stream_task."""
        harness = ClaudeSDKHarness()

        async def blocking_hook(ctx: HookContext) -> HookResult:
            return HookResult(block=True, reason="Rate limited")

        harness.register_hook(HookEvent.PRE_TASK, blocking_hook)

        with patch.object(harness, "is_available", return_value=True):
            task_input = TaskInput(prompt="Hello")

            with pytest.raises(RuntimeError, match="Rate limited"):
                async for _ in harness.stream_task(task_input):
                    pass


class TestLegacyHarnessNoOpHooks:
    """Tests for no-op hook support in legacy harnesses."""

    def test_claude_legacy_register_hook_logs_warning(self) -> None:
        """Test that ClaudeLegacyBackend logs warning on hook registration."""
        # Suppress deprecation warning for this test
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from cub.core.harness.claude import ClaudeLegacyBackend

            harness = ClaudeLegacyBackend()

        async def my_hook(ctx: HookContext) -> HookResult | None:
            return None

        with patch("cub.core.harness.claude.logger") as mock_logger:
            harness.register_hook(HookEvent.PRE_TASK, my_hook)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            assert "does not support hooks" in call_args[0]

    def test_codex_register_hook_logs_warning(self) -> None:
        """Test that CodexBackend logs warning on hook registration."""
        from cub.core.harness.codex import CodexBackend

        harness = CodexBackend()

        async def my_hook(ctx: HookContext) -> HookResult | None:
            return None

        with patch("cub.core.harness.codex.logger") as mock_logger:
            harness.register_hook(HookEvent.PRE_TASK, my_hook)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            assert "does not support hooks" in call_args[0]


class TestToolLevelHooksWarning:
    """Tests for warnings about unimplemented tool-level hooks."""

    def test_register_pre_tool_use_warns(self) -> None:
        """Test that registering PRE_TOOL_USE logs a warning."""
        harness = ClaudeSDKHarness()

        async def tool_hook(ctx: HookContext) -> HookResult | None:
            return None

        with patch("cub.core.harness.claude_sdk.logger") as mock_logger:
            harness.register_hook(HookEvent.PRE_TOOL_USE, tool_hook)

            # Should warn about tool-level hooks not being active yet
            warning_calls = [c for c in mock_logger.warning.call_args_list]
            assert len(warning_calls) == 1
            assert "not yet active" in warning_calls[0][0][0]

    def test_register_post_tool_use_warns(self) -> None:
        """Test that registering POST_TOOL_USE logs a warning."""
        harness = ClaudeSDKHarness()

        async def tool_hook(ctx: HookContext) -> HookResult | None:
            return None

        with patch("cub.core.harness.claude_sdk.logger") as mock_logger:
            harness.register_hook(HookEvent.POST_TOOL_USE, tool_hook)

            warning_calls = [c for c in mock_logger.warning.call_args_list]
            assert len(warning_calls) == 1
            assert "not yet active" in warning_calls[0][0][0]
