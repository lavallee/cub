"""
Tests for CLIAdapter.

Tests the CLI tool adapter with subprocess execution, timeout handling,
and output parsing.
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cub.core.tools.adapters.cli import CLIAdapter
from cub.core.tools.models import AdapterType, CLIConfig


class TestCLIAdapter:
    """Test CLIAdapter initialization and basic properties."""

    def test_adapter_type(self):
        """Test adapter returns correct type."""
        adapter = CLIAdapter()
        assert adapter.adapter_type == "cli"

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check succeeds."""
        adapter = CLIAdapter()
        # Health check should succeed (runs echo command)
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check handles failures gracefully."""
        adapter = CLIAdapter()
        # Mock subprocess to raise an error
        with patch(
            "cub.core.tools.adapters.cli.asyncio.create_subprocess_exec",
            side_effect=Exception("Subprocess error"),
        ):
            assert await adapter.health_check() is False

    @pytest.mark.asyncio
    async def test_is_available(self):
        """Test tool availability check."""
        adapter = CLIAdapter()
        # For now, is_available returns True optimistically
        assert await adapter.is_available("test-tool") is True


class TestCLIAdapterExecute:
    """Test CLIAdapter execute method."""

    @pytest.mark.asyncio
    async def test_execute_success_json(self):
        """Test successful CLI execution with JSON output."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="gh",
            args_template="issue list --repo {repo} --json number,title",
            output_format="json",
        )

        json_output = [{"number": 1, "title": "Test Issue"}]

        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(
                json.dumps(json_output).encode("utf-8"),
                b"",
            )
        )

        with patch(
            "cub.core.tools.adapters.cli.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            result = await adapter.execute(
                tool_id="github-cli",
                action="list_issues",
                params={"_cli_config": config, "repo": "owner/repo"},
                timeout=30.0,
            )

        assert result.success is True
        assert result.tool_id == "github-cli"
        assert result.action == "list_issues"
        assert result.output == json_output
        assert result.adapter_type == AdapterType.CLI
        assert result.duration_ms >= 0
        assert result.metadata["exit_code"] == 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_execute_success_text(self):
        """Test successful CLI execution with text output."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="echo",
            args_template="Hello {name}",
            output_format="text",
        )

        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(
                b"Hello World\n",
                b"",
            )
        )

        with patch(
            "cub.core.tools.adapters.cli.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            result = await adapter.execute(
                tool_id="echo-tool",
                action="echo",
                params={"_cli_config": config, "name": "World"},
                timeout=30.0,
            )

        assert result.success is True
        assert result.output == {"text": "Hello World"}
        assert result.adapter_type == AdapterType.CLI

    @pytest.mark.asyncio
    async def test_execute_success_lines(self):
        """Test successful CLI execution with lines output."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="ls",
            output_format="lines",
        )

        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(
                b"file1.txt\nfile2.txt\nfile3.txt\n",
                b"",
            )
        )

        with patch(
            "cub.core.tools.adapters.cli.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            result = await adapter.execute(
                tool_id="ls-tool",
                action="list",
                params={"_cli_config": config},
                timeout=30.0,
            )

        assert result.success is True
        assert result.output == ["file1.txt", "file2.txt", "file3.txt"]
        assert result.adapter_type == AdapterType.CLI

    @pytest.mark.asyncio
    async def test_execute_missing_config(self):
        """Test execution fails gracefully when config is missing."""
        adapter = CLIAdapter()

        result = await adapter.execute(
            tool_id="test-tool",
            action="test",
            params={"query": "test"},
            timeout=30.0,
        )

        assert result.success is False
        assert result.error == "CLI configuration not provided"
        assert result.error_type == "validation"

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """Test execution handles timeout gracefully."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="sleep",
            args_template="10",
            output_format="text",
        )

        # Mock the subprocess to simulate timeout
        mock_process = AsyncMock()
        # kill() is synchronous in real asyncio subprocess
        mock_process.kill = Mock()
        mock_process.wait = AsyncMock()
        mock_process.communicate = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        with patch(
            "cub.core.tools.adapters.cli.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            result = await adapter.execute(
                tool_id="sleep-tool",
                action="sleep",
                params={"_cli_config": config},
                timeout=1.0,
            )

        assert result.success is False
        assert "timed out" in result.error.lower()
        assert result.error_type == "timeout"
        # Verify process was killed
        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_command_not_found(self):
        """Test execution handles command not found."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="nonexistent-command",
            output_format="text",
        )

        with patch(
            "cub.core.tools.adapters.cli.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("Command not found"),
        ):
            result = await adapter.execute(
                tool_id="missing-tool",
                action="test",
                params={"_cli_config": config},
                timeout=30.0,
            )

        assert result.success is False
        assert "not found" in result.error.lower()
        assert result.error_type == "validation"

    @pytest.mark.asyncio
    async def test_execute_non_zero_exit_code(self):
        """Test execution handles non-zero exit codes."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="grep",
            args_template="nonexistent-pattern file.txt",
            output_format="text",
        )

        # Mock the subprocess with non-zero exit code
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(
                b"",
                b"grep: file.txt: No such file or directory\n",
            )
        )

        with patch(
            "cub.core.tools.adapters.cli.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            result = await adapter.execute(
                tool_id="grep-tool",
                action="search",
                params={"_cli_config": config},
                timeout=30.0,
            )

        assert result.success is False
        assert "No such file" in result.error
        assert result.error_type == "execution"
        assert result.metadata["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_execute_json_parse_error(self):
        """Test execution handles JSON parse errors gracefully."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="echo",
            args_template="invalid json",
            output_format="json",
        )

        # Mock the subprocess with invalid JSON
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(
                b"not valid json\n",
                b"",
            )
        )

        with patch(
            "cub.core.tools.adapters.cli.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            result = await adapter.execute(
                tool_id="echo-tool",
                action="echo",
                params={"_cli_config": config},
                timeout=30.0,
            )

        # Should still succeed but with parse_error in output
        assert result.success is True
        assert "text" in result.output
        assert "parse_error" in result.output

    @pytest.mark.asyncio
    async def test_execute_with_env_vars(self):
        """Test execution with custom environment variables."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="printenv",
            args_template="MY_VAR",
            output_format="text",
            env_vars={"MY_VAR": "test_value"},
        )

        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(
                b"test_value\n",
                b"",
            )
        )

        with patch(
            "cub.core.tools.adapters.cli.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ) as mock_exec:
            result = await adapter.execute(
                tool_id="env-tool",
                action="printenv",
                params={"_cli_config": config},
                timeout=30.0,
            )

        assert result.success is True
        # Verify env was passed to subprocess
        call_kwargs = mock_exec.call_args[1]
        assert "env" in call_kwargs
        assert call_kwargs["env"]["MY_VAR"] == "test_value"

    @pytest.mark.asyncio
    async def test_execute_unexpected_error(self):
        """Test execution handles unexpected errors."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="test",
            output_format="text",
        )

        with patch(
            "cub.core.tools.adapters.cli.asyncio.create_subprocess_exec",
            side_effect=RuntimeError("Unexpected error"),
        ):
            result = await adapter.execute(
                tool_id="test-tool",
                action="test",
                params={"_cli_config": config},
                timeout=30.0,
            )

        assert result.success is False
        assert "Unexpected error" in result.error
        assert result.error_type == "unknown"


class TestCLIAdapterHelpers:
    """Test CLIAdapter helper methods."""

    def test_build_command_with_template(self):
        """Test command building with args template."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="gh",
            args_template="issue list --repo {repo} --state {state}",
            output_format="json",
        )

        command = adapter._build_command(
            config,
            action="list_issues",
            params={
                "_cli_config": config,
                "repo": "owner/repo",
                "state": "open",
            },
        )

        assert command == [
            "gh",
            "issue",
            "list",
            "--repo",
            "owner/repo",
            "--state",
            "open",
        ]

    def test_build_command_without_template(self):
        """Test command building without args template."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="ls",
            output_format="lines",
        )

        command = adapter._build_command(
            config,
            action="list",
            params={"_cli_config": config},
        )

        assert command == ["ls"]

    def test_build_command_with_quoted_args(self):
        """Test command building with quoted arguments."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="grep",
            args_template="-r '{pattern}' {path}",
            output_format="text",
        )

        command = adapter._build_command(
            config,
            action="search",
            params={
                "_cli_config": config,
                "pattern": "test pattern",
                "path": "/tmp",
            },
        )

        assert command == ["grep", "-r", "test pattern", "/tmp"]

    def test_build_command_missing_param(self):
        """Test command building fails with missing parameter."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="gh",
            args_template="issue list --repo {repo}",
            output_format="json",
        )

        with pytest.raises(ValueError, match="Missing parameter"):
            adapter._build_command(
                config,
                action="list_issues",
                params={"_cli_config": config},
            )

    def test_build_env_no_vars(self):
        """Test environment building with no custom vars."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="test",
            output_format="text",
        )

        env = adapter._build_env(config)
        assert env is None

    def test_build_env_with_vars(self):
        """Test environment building with custom vars."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="test",
            output_format="text",
            env_vars={"MY_VAR": "value", "ANOTHER_VAR": "value2"},
        )

        env = adapter._build_env(config)
        assert env is not None
        assert env["MY_VAR"] == "value"
        assert env["ANOTHER_VAR"] == "value2"

    def test_parse_output_json(self):
        """Test JSON output parsing."""
        adapter = CLIAdapter()

        config = CLIConfig(command="test", output_format="json")

        output = adapter._parse_output(
            config,
            json.dumps({"key": "value"}),
        )

        assert output == {"key": "value"}

    def test_parse_output_text(self):
        """Test text output parsing."""
        adapter = CLIAdapter()

        config = CLIConfig(command="test", output_format="text")

        output = adapter._parse_output(config, "Hello World")

        assert output == {"text": "Hello World"}

    def test_parse_output_lines(self):
        """Test lines output parsing."""
        adapter = CLIAdapter()

        config = CLIConfig(command="test", output_format="lines")

        output = adapter._parse_output(
            config,
            "line1\nline2\nline3\n",
        )

        assert output == ["line1", "line2", "line3"]

    def test_parse_output_lines_with_empty_lines(self):
        """Test lines output parsing filters empty lines."""
        adapter = CLIAdapter()

        config = CLIConfig(command="test", output_format="lines")

        output = adapter._parse_output(
            config,
            "line1\n\nline2\n  \nline3\n",
        )

        assert output == ["line1", "line2", "line3"]

    def test_generate_markdown_json(self):
        """Test markdown generation for JSON output."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="gh",
            output_format="json",
        )

        markdown = adapter._generate_markdown(
            "github-cli",
            "list_issues",
            {"items": [{"id": 1}, {"id": 2}]},
            config,
        )

        assert "github-cli" in markdown
        assert "list_issues" in markdown
        assert "gh" in markdown

    def test_generate_markdown_lines(self):
        """Test markdown generation for lines output."""
        adapter = CLIAdapter()

        config = CLIConfig(
            command="ls",
            output_format="lines",
        )

        markdown = adapter._generate_markdown(
            "ls-tool",
            "list",
            ["file1.txt", "file2.txt"],
            config,
        )

        assert "ls-tool" in markdown
        assert "Lines: 2" in markdown
