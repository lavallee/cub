"""
Tests for Claude harness backend.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import subprocess
import json

from cub.core.harness import get_backend, is_backend_available
from cub.core.harness.claude import ClaudeBackend


class TestClaudeBackend:
    """Tests for ClaudeBackend."""

    def test_name(self):
        """Test backend name is 'claude'."""
        backend = ClaudeBackend()
        assert backend.name == "claude"

    def test_capabilities(self):
        """Test Claude supports all major capabilities."""
        backend = ClaudeBackend()
        caps = backend.capabilities

        assert caps.streaming is True
        assert caps.token_reporting is True
        assert caps.system_prompt is True
        assert caps.auto_mode is True
        assert caps.json_output is True
        assert caps.model_selection is True

    @patch('cub.core.harness.claude.shutil.which')
    def test_is_available_when_installed(self, mock_which):
        """Test is_available returns True when claude is in PATH."""
        mock_which.return_value = "/usr/local/bin/claude"

        backend = ClaudeBackend()
        assert backend.is_available() is True
        mock_which.assert_called_once_with("claude")

    @patch('cub.core.harness.claude.shutil.which')
    def test_is_available_when_not_installed(self, mock_which):
        """Test is_available returns False when claude not in PATH."""
        mock_which.return_value = None

        backend = ClaudeBackend()
        assert backend.is_available() is False

    @patch('subprocess.run')
    def test_invoke_basic(self, mock_run):
        """Test basic invoke returns HarnessResult."""
        # Mock successful claude invocation
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "result": "Here is a prime checking function...",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 200,
                "cache_read_input_tokens": 50,
                "cache_creation_input_tokens": 10,
            },
            "cost_usd": 0.005,
        })
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        backend = ClaudeBackend()
        result = backend.invoke(
            system_prompt="You are a helpful assistant.",
            task_prompt="Write a prime checking function.",
        )

        assert result.success is True
        assert result.exit_code == 0
        assert "prime checking function" in result.output
        assert result.usage.input_tokens == 100
        assert result.usage.output_tokens == 200
        assert result.usage.cache_read_tokens == 50
        assert result.usage.cache_creation_tokens == 10
        assert result.usage.cost_usd == 0.005
        assert result.usage.estimated is False

    @patch('subprocess.run')
    def test_invoke_with_model(self, mock_run):
        """Test invoke passes model flag correctly."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"result": "output", "usage": {}})
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        backend = ClaudeBackend()
        backend.invoke(
            system_prompt="System",
            task_prompt="Task",
            model="opus",
        )

        # Verify model flag was passed
        call_args = mock_run.call_args[0][0]
        assert "--model" in call_args
        assert "opus" in call_args

    @patch('subprocess.run')
    def test_invoke_error_handling(self, mock_run):
        """Test invoke handles errors gracefully."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Invalid syntax"
        mock_result.stderr = "Error: failed to parse"
        mock_run.return_value = mock_result

        backend = ClaudeBackend()
        result = backend.invoke(
            system_prompt="System",
            task_prompt="Task",
        )

        assert result.failed is True
        assert result.exit_code == 1
        assert result.error is not None
        assert "failed" in result.error.lower()

    @patch('subprocess.Popen')
    def test_invoke_streaming_basic(self, mock_popen):
        """Test streaming invoke parses events correctly."""
        # Mock streaming output with events
        stream_events = [
            '{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello "}}',
            '{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "world"}}',
            '{"type": "message", "usage": {"input_tokens": 50, "output_tokens": 100}}',
        ]

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdin = MagicMock()
        mock_process.stdout = iter(stream_events)
        mock_process.stderr = MagicMock()
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        backend = ClaudeBackend()
        result = backend.invoke_streaming(
            system_prompt="System",
            task_prompt="Task",
        )

        assert result.success is True
        assert result.output == "Hello world"
        assert result.usage.input_tokens == 50
        assert result.usage.output_tokens == 100

    @patch('subprocess.Popen')
    def test_invoke_streaming_with_callback(self, mock_popen):
        """Test streaming invoke calls callback for each chunk."""
        stream_events = [
            '{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "chunk1"}}',
            '{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "chunk2"}}',
        ]

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdin = MagicMock()
        mock_process.stdout = iter(stream_events)
        mock_process.stderr = MagicMock()
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        callback_chunks = []
        def callback(chunk):
            callback_chunks.append(chunk)

        backend = ClaudeBackend()
        result = backend.invoke_streaming(
            system_prompt="System",
            task_prompt="Task",
            callback=callback,
        )

        assert callback_chunks == ["chunk1", "chunk2"]
        assert result.output == "chunk1chunk2"

    @patch('subprocess.run')
    def test_get_version(self, mock_run):
        """Test get_version returns version string."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "claude version 1.2.3\n"
        mock_run.return_value = mock_result

        backend = ClaudeBackend()
        version = backend.get_version()

        assert version == "claude version 1.2.3"

    @patch('subprocess.run')
    def test_get_version_error_handling(self, mock_run):
        """Test get_version returns 'unknown' on error."""
        mock_run.side_effect = FileNotFoundError("claude not found")

        backend = ClaudeBackend()
        version = backend.get_version()

        assert version == "unknown"


class TestClaudeBackendRegistry:
    """Test Claude backend is registered correctly."""

    @patch('cub.core.harness.claude.shutil.which')
    def test_backend_registered(self, mock_which):
        """Test Claude backend can be retrieved from registry."""
        mock_which.return_value = "/usr/local/bin/claude"

        backend = get_backend("claude")
        assert backend.name == "claude"

    @patch('cub.core.harness.claude.shutil.which')
    def test_backend_available_when_claude_installed(self, mock_which):
        """Test backend is reported as available when claude CLI exists."""
        mock_which.return_value = "/usr/local/bin/claude"
        assert is_backend_available("claude") is True
