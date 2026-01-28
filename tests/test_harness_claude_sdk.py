"""
Tests for Claude SDK harness backend.

Tests both unit tests (with mocks) and integration tests (with real SDK).
Integration tests require ANTHROPIC_API_KEY and are skipped without it.
"""

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cub.core.harness import (
    get_async_backend,
    list_async_backends,
)
from cub.core.harness.models import (
    HarnessFeature,
    TaskInput,
)

# Skip all tests if claude-agent-sdk is not installed
pytest.importorskip("claude_agent_sdk")


from cub.core.harness.claude_sdk import (
    ClaudeSDKBackend,
    _build_options,
    _cli_available,
    _extract_text_from_message,
    _extract_usage,
    _parse_sdk_message,
    _sdk_available,
)


class TestClaudeSDKBackend:
    """Tests for ClaudeSDKBackend class."""

    def test_name(self) -> None:
        """Test backend name is 'claude'."""
        harness = ClaudeSDKBackend()
        assert harness.name == "claude-sdk"

    def test_capabilities(self) -> None:
        """Test Claude SDK supports all capabilities."""
        harness = ClaudeSDKBackend()
        caps = harness.capabilities

        assert caps.streaming is True
        assert caps.token_reporting is True
        assert caps.system_prompt is True
        assert caps.auto_mode is True
        assert caps.json_output is True
        assert caps.model_selection is True
        assert caps.hooks is True
        assert caps.custom_tools is True
        assert caps.sessions is True
        assert caps.session_forking is True
        assert caps.subagents is True

    def test_supports_feature_all(self) -> None:
        """Test supports_feature returns True for all features."""
        harness = ClaudeSDKBackend()

        for feature in HarnessFeature:
            assert harness.supports_feature(feature) is True

    @patch("cub.core.harness.claude_sdk._sdk_available")
    @patch("cub.core.harness.claude_sdk._cli_available")
    def test_is_available_both_present(self, mock_cli: MagicMock, mock_sdk: MagicMock) -> None:
        """Test is_available returns True when both SDK and CLI are present."""
        mock_sdk.return_value = True
        mock_cli.return_value = True

        harness = ClaudeSDKBackend()
        assert harness.is_available() is True

    @patch("cub.core.harness.claude_sdk._sdk_available")
    @patch("cub.core.harness.claude_sdk._cli_available")
    def test_is_available_sdk_missing(self, mock_cli: MagicMock, mock_sdk: MagicMock) -> None:
        """Test is_available returns False when SDK is missing."""
        mock_sdk.return_value = False
        mock_cli.return_value = True

        harness = ClaudeSDKBackend()
        assert harness.is_available() is False

    @patch("cub.core.harness.claude_sdk._sdk_available")
    @patch("cub.core.harness.claude_sdk._cli_available")
    def test_is_available_cli_missing(self, mock_cli: MagicMock, mock_sdk: MagicMock) -> None:
        """Test is_available returns False when CLI is missing."""
        mock_sdk.return_value = True
        mock_cli.return_value = False

        harness = ClaudeSDKBackend()
        assert harness.is_available() is False

    @patch("subprocess.run")
    def test_get_version(self, mock_run: MagicMock) -> None:
        """Test get_version returns version string."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Claude Code 1.2.3\n"
        mock_run.return_value = mock_result

        harness = ClaudeSDKBackend()
        version = harness.get_version()

        assert version == "Claude Code 1.2.3"

    @patch("subprocess.run")
    def test_get_version_error(self, mock_run: MagicMock) -> None:
        """Test get_version returns 'unknown' on error."""
        mock_run.side_effect = FileNotFoundError("claude not found")

        harness = ClaudeSDKBackend()
        version = harness.get_version()

        assert version == "unknown"


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_sdk_available(self) -> None:
        """Test _sdk_available returns True when SDK is installed."""
        # SDK should be installed since we skip if not
        assert _sdk_available() is True

    @patch("shutil.which")
    def test_cli_available_true(self, mock_which: MagicMock) -> None:
        """Test _cli_available returns True when CLI exists."""
        mock_which.return_value = "/usr/local/bin/claude"
        assert _cli_available() is True

    @patch("shutil.which")
    def test_cli_available_false(self, mock_which: MagicMock) -> None:
        """Test _cli_available returns False when CLI missing."""
        mock_which.return_value = None
        assert _cli_available() is False


class TestBuildOptions:
    """Tests for _build_options function."""

    def test_build_options_minimal(self) -> None:
        """Test building options with minimal input."""
        task_input = TaskInput(prompt="Hello")
        options = _build_options(task_input)

        assert options.system_prompt is None
        assert options.cwd is None
        assert options.permission_mode is None
        assert options.model is None

    def test_build_options_with_system_prompt(self) -> None:
        """Test building options with system prompt."""
        task_input = TaskInput(
            prompt="Hello",
            system_prompt="You are a helpful assistant",
        )
        options = _build_options(task_input)

        assert options.system_prompt == "You are a helpful assistant"

    def test_build_options_with_working_dir(self) -> None:
        """Test building options with working directory."""
        task_input = TaskInput(
            prompt="Hello",
            working_dir="/home/user/project",
        )
        options = _build_options(task_input)

        assert options.cwd == "/home/user/project"

    def test_build_options_auto_approve(self) -> None:
        """Test building options with auto_approve enables bypassPermissions."""
        task_input = TaskInput(
            prompt="Hello",
            auto_approve=True,
        )
        options = _build_options(task_input)

        assert options.permission_mode == "bypassPermissions"

    def test_build_options_with_model(self) -> None:
        """Test building options with model."""
        task_input = TaskInput(
            prompt="Hello",
            model="opus",
        )
        options = _build_options(task_input)

        assert options.model == "opus"

    def test_build_options_all_fields(self) -> None:
        """Test building options with all fields."""
        task_input = TaskInput(
            prompt="Hello",
            system_prompt="System",
            working_dir="/tmp",
            model="sonnet",
            auto_approve=True,
        )
        options = _build_options(task_input)

        assert options.system_prompt == "System"
        assert options.cwd == "/tmp"
        assert options.model == "sonnet"
        assert options.permission_mode == "bypassPermissions"


class TestParseSDKMessage:
    """Tests for _parse_sdk_message function."""

    def test_parse_user_message_string(self) -> None:
        """Test parsing UserMessage with string content."""
        from claude_agent_sdk import UserMessage

        sdk_msg = UserMessage(content="Hello, Claude!")
        parsed = _parse_sdk_message(sdk_msg)

        assert parsed is not None
        assert parsed.role == "user"
        assert parsed.content == "Hello, Claude!"
        assert len(parsed.tool_uses) == 0

    def test_parse_assistant_message_text(self) -> None:
        """Test parsing AssistantMessage with text content."""
        from claude_agent_sdk import AssistantMessage
        from claude_agent_sdk.types import TextBlock

        sdk_msg = AssistantMessage(
            content=[TextBlock(text="Here is your answer")],
            model="claude-sonnet-4-20250514",
        )
        parsed = _parse_sdk_message(sdk_msg)

        assert parsed is not None
        assert parsed.role == "assistant"
        assert parsed.content == "Here is your answer"
        assert len(parsed.tool_uses) == 0

    def test_parse_assistant_message_with_tool_use(self) -> None:
        """Test parsing AssistantMessage with tool use."""
        from claude_agent_sdk import AssistantMessage
        from claude_agent_sdk.types import TextBlock, ToolUseBlock

        sdk_msg = AssistantMessage(
            content=[
                TextBlock(text="Let me read that file"),
                ToolUseBlock(
                    id="tool_123",
                    name="Read",
                    input={"file_path": "/test.py"},
                ),
            ],
            model="claude-sonnet-4-20250514",
        )
        parsed = _parse_sdk_message(sdk_msg)

        assert parsed is not None
        assert parsed.role == "assistant"
        assert "Let me read that file" in parsed.content
        assert len(parsed.tool_uses) == 1
        assert parsed.tool_uses[0].tool_name == "Read"
        assert parsed.tool_uses[0].tool_input == {"file_path": "/test.py"}

    def test_parse_result_message_returns_none(self) -> None:
        """Test parsing ResultMessage returns None."""
        from claude_agent_sdk import ResultMessage

        sdk_msg = ResultMessage(
            subtype="success",
            duration_ms=1000,
            duration_api_ms=800,
            is_error=False,
            num_turns=1,
            session_id="test-123",
        )
        parsed = _parse_sdk_message(sdk_msg)

        assert parsed is None


class TestExtractUsage:
    """Tests for _extract_usage function."""

    def test_extract_usage_from_result_message(self) -> None:
        """Test extracting usage from ResultMessage."""
        from claude_agent_sdk import ResultMessage

        sdk_msg = ResultMessage(
            subtype="success",
            duration_ms=1000,
            duration_api_ms=800,
            is_error=False,
            num_turns=1,
            session_id="test-123",
            total_cost_usd=0.01,
            usage={
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 25,
                "cache_creation_input_tokens": 10,
            },
        )
        usage = _extract_usage(sdk_msg)

        assert usage is not None
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_read_tokens == 25
        assert usage.cache_creation_tokens == 10
        assert usage.cost_usd == 0.01
        assert usage.estimated is False

    def test_extract_usage_from_non_result(self) -> None:
        """Test extracting usage from non-ResultMessage returns None."""
        from claude_agent_sdk import UserMessage

        sdk_msg = UserMessage(content="Hello")
        usage = _extract_usage(sdk_msg)

        assert usage is None


class TestExtractText:
    """Tests for _extract_text_from_message function."""

    def test_extract_text_from_assistant(self) -> None:
        """Test extracting text from AssistantMessage."""
        from claude_agent_sdk import AssistantMessage
        from claude_agent_sdk.types import TextBlock

        sdk_msg = AssistantMessage(
            content=[
                TextBlock(text="First part. "),
                TextBlock(text="Second part."),
            ],
            model="claude-sonnet-4-20250514",
        )
        text = _extract_text_from_message(sdk_msg)

        assert text == "First part. Second part."

    def test_extract_text_from_non_assistant(self) -> None:
        """Test extracting text from non-AssistantMessage returns empty."""
        from claude_agent_sdk import UserMessage

        sdk_msg = UserMessage(content="Hello")
        text = _extract_text_from_message(sdk_msg)

        assert text == ""


class TestBackendRegistry:
    """Test Claude SDK backend is registered correctly."""

    def test_backend_registered(self) -> None:
        """Test Claude SDK backend is in registry."""
        backends = list_async_backends()
        assert "claude" in backends

    def test_get_backend_by_name(self) -> None:
        """Test getting Claude backend by name."""
        # This may fail if SDK or CLI not available, which is fine
        try:
            backend = get_async_backend("claude")
            assert backend.name == "claude-sdk"
        except ValueError:
            # Expected if harness not available
            pass


class TestRunTask:
    """Tests for run_task method."""

    @pytest.mark.asyncio
    async def test_run_task_not_available(self) -> None:
        """Test run_task raises when harness not available."""
        harness = ClaudeSDKBackend()

        with patch.object(harness, "is_available", return_value=False):
            task_input = TaskInput(prompt="Hello")

            with pytest.raises(RuntimeError, match="Claude SDK not available"):
                await harness.run_task(task_input)

    @pytest.mark.asyncio
    async def test_run_task_cli_not_found(self) -> None:
        """Test run_task handles CLINotFoundError."""
        from claude_agent_sdk import CLINotFoundError

        harness = ClaudeSDKBackend()

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
            assert "CLI not found" in (result.error or "")

    @pytest.mark.asyncio
    async def test_run_task_success(self) -> None:
        """Test run_task with successful execution."""
        from claude_agent_sdk import AssistantMessage, ResultMessage
        from claude_agent_sdk.types import TextBlock

        harness = ClaudeSDKBackend()

        # Create mock messages
        messages = [
            AssistantMessage(
                content=[TextBlock(text="Here is the answer")],
                model="claude-sonnet-4-20250514",
            ),
            ResultMessage(
                subtype="success",
                duration_ms=1000,
                duration_api_ms=800,
                is_error=False,
                num_turns=1,
                session_id="test-session",
                total_cost_usd=0.01,
                usage={"input_tokens": 100, "output_tokens": 50},
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
            assert result.output == "Here is the answer"
            assert result.usage.input_tokens == 100
            assert result.usage.output_tokens == 50
            assert result.session_id == "test-session"

    @pytest.mark.asyncio
    async def test_run_task_sets_cub_run_active_env_var(self) -> None:
        """Test run_task sets CUB_RUN_ACTIVE=1 during execution."""
        from claude_agent_sdk import AssistantMessage, ResultMessage
        from claude_agent_sdk.types import TextBlock

        harness = ClaudeSDKBackend()

        # Track whether CUB_RUN_ACTIVE was set during mock execution
        cub_run_active_during_execution = False

        async def mock_query(*args: Any, **kwargs: Any) -> Any:
            nonlocal cub_run_active_during_execution
            # Check if CUB_RUN_ACTIVE is set during query execution
            cub_run_active_during_execution = os.environ.get("CUB_RUN_ACTIVE") == "1"

            messages = [
                AssistantMessage(
                    content=[TextBlock(text="Answer")],
                    model="claude-sonnet-4-20250514",
                ),
                ResultMessage(
                    subtype="success",
                    duration_ms=1000,
                    duration_api_ms=800,
                    is_error=False,
                    num_turns=1,
                    session_id="test-session",
                    total_cost_usd=0.01,
                    usage={"input_tokens": 100, "output_tokens": 50},
                ),
            ]
            for msg in messages:
                yield msg

        with (
            patch.object(harness, "is_available", return_value=True),
            patch("claude_agent_sdk.query", mock_query),
        ):
            task_input = TaskInput(prompt="Hello")
            result = await harness.run_task(task_input)

            # Verify CUB_RUN_ACTIVE was set during execution
            assert cub_run_active_during_execution is True
            assert result.success is True
            # Verify it's restored after execution
            assert os.environ.get("CUB_RUN_ACTIVE") != "1"


class TestStreamTask:
    """Tests for stream_task method."""

    @pytest.mark.asyncio
    async def test_stream_task_not_available(self) -> None:
        """Test stream_task raises when harness not available."""
        harness = ClaudeSDKBackend()

        with patch.object(harness, "is_available", return_value=False):
            task_input = TaskInput(prompt="Hello")

            with pytest.raises(RuntimeError, match="Claude SDK not available"):
                async for _ in harness.stream_task(task_input):
                    pass

    @pytest.mark.asyncio
    async def test_stream_task_yields_chunks(self) -> None:
        """Test stream_task yields text chunks."""
        from claude_agent_sdk import AssistantMessage
        from claude_agent_sdk.types import TextBlock

        harness = ClaudeSDKBackend()

        messages = [
            AssistantMessage(
                content=[TextBlock(text="First ")],
                model="claude-sonnet-4-20250514",
            ),
            AssistantMessage(
                content=[TextBlock(text="second ")],
                model="claude-sonnet-4-20250514",
            ),
            AssistantMessage(
                content=[TextBlock(text="third")],
                model="claude-sonnet-4-20250514",
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
            chunks: list[str] = []

            async for chunk in harness.stream_task(task_input):
                chunks.append(chunk)

            assert chunks == ["First ", "second ", "third"]

    @pytest.mark.asyncio
    async def test_stream_task_sets_cub_run_active_env_var(self) -> None:
        """Test stream_task sets CUB_RUN_ACTIVE=1 during execution."""
        from claude_agent_sdk import AssistantMessage
        from claude_agent_sdk.types import TextBlock

        harness = ClaudeSDKBackend()

        # Track whether CUB_RUN_ACTIVE was set during mock execution
        cub_run_active_during_execution = False

        async def mock_query(*args: Any, **kwargs: Any) -> Any:
            nonlocal cub_run_active_during_execution
            # Check if CUB_RUN_ACTIVE is set during query execution
            cub_run_active_during_execution = os.environ.get("CUB_RUN_ACTIVE") == "1"

            messages = [
                AssistantMessage(
                    content=[TextBlock(text="Chunk1")],
                    model="claude-sonnet-4-20250514",
                ),
                AssistantMessage(
                    content=[TextBlock(text="Chunk2")],
                    model="claude-sonnet-4-20250514",
                ),
            ]
            for msg in messages:
                yield msg

        with (
            patch.object(harness, "is_available", return_value=True),
            patch("claude_agent_sdk.query", mock_query),
        ):
            task_input = TaskInput(prompt="Hello")
            chunks: list[str] = []

            async for chunk in harness.stream_task(task_input):
                chunks.append(chunk)

            # Verify CUB_RUN_ACTIVE was set during execution
            assert cub_run_active_during_execution is True
            assert len(chunks) == 2
            # Verify it's restored after execution
            assert os.environ.get("CUB_RUN_ACTIVE") != "1"


# Integration tests - require ANTHROPIC_API_KEY
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
class TestIntegration:
    """Integration tests that use the real Claude SDK."""

    @pytest.mark.asyncio
    async def test_run_task_real(self) -> None:
        """Test run_task with real SDK execution."""
        harness = ClaudeSDKBackend()

        if not harness.is_available():
            pytest.skip("Claude SDK or CLI not available")

        task_input = TaskInput(
            prompt="Say 'Hello from integration test' and nothing else.",
            auto_approve=True,
        )

        result = await harness.run_task(task_input)

        assert result.success is True
        assert "Hello from integration test" in result.output
        assert result.usage.total_tokens > 0

    @pytest.mark.asyncio
    async def test_stream_task_real(self) -> None:
        """Test stream_task with real SDK execution."""
        harness = ClaudeSDKBackend()

        if not harness.is_available():
            pytest.skip("Claude SDK or CLI not available")

        task_input = TaskInput(
            prompt="Say 'Streaming test' and nothing else.",
            auto_approve=True,
        )

        chunks: list[str] = []
        async for chunk in harness.stream_task(task_input):
            chunks.append(chunk)

        full_output = "".join(chunks)
        assert len(chunks) > 0
        assert "Streaming test" in full_output
