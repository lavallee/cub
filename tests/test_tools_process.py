"""Tests for process management utilities."""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest

from cub.core.tools.process import (
    IS_UNIX,
    IS_WINDOWS,
    ProcessResult,
    ensure_process_terminated,
    is_process_running,
    kill_process_group,
    run_process,
    wait_for_process,
)


class TestProcessResult:
    """Tests for ProcessResult model."""

    def test_success_result(self):
        """Test creating a successful process result."""
        result = ProcessResult(
            success=True,
            exit_code=0,
            stdout="output",
            stderr="",
            duration_ms=100,
        )
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.timed_out is False
        assert result.error is None

    def test_failure_result(self):
        """Test creating a failed process result."""
        result = ProcessResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="error output",
            duration_ms=50,
            error="Command failed",
        )
        assert result.success is False
        assert result.exit_code == 1
        assert result.stderr == "error output"
        assert result.error == "Command failed"

    def test_timeout_result(self):
        """Test creating a timeout result."""
        result = ProcessResult(
            success=False,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=5000,
            timed_out=True,
            error="Process timed out after 5s",
        )
        assert result.timed_out is True
        assert result.exit_code is None
        assert result.error == "Process timed out after 5s"


class TestRunProcess:
    """Tests for run_process function."""

    @pytest.mark.asyncio
    async def test_successful_command(self):
        """Test running a successful command."""
        result = await run_process(["echo", "hello"])

        assert result.success is True
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.stderr == ""
        assert result.duration_ms > 0
        assert result.timed_out is False
        assert result.error is None

    @pytest.mark.asyncio
    async def test_command_with_stderr(self):
        """Test command that writes to stderr."""
        # Python script that writes to stderr
        result = await run_process([
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('error message'); sys.exit(1)",
        ])

        assert result.success is False
        assert result.exit_code == 1
        assert "error message" in result.stderr

    @pytest.mark.asyncio
    async def test_command_with_input(self):
        """Test command with stdin input."""
        # Python script that echoes stdin
        result = await run_process(
            [sys.executable, "-c", "import sys; print(sys.stdin.read())"],
            input_data="test input",
        )

        assert result.success is True
        assert "test input" in result.stdout

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Test command timeout."""
        # Python script that sleeps longer than timeout
        result = await run_process(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=0.1,
        )

        assert result.success is False
        assert result.timed_out is True
        assert result.exit_code is None
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_command_not_found(self):
        """Test handling of non-existent command."""
        result = await run_process(["nonexistent_command_12345"])

        assert result.success is False
        assert result.exit_code is None
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_custom_env(self):
        """Test command with custom environment variables."""
        result = await run_process(
            [sys.executable, "-c", "import os; print(os.environ.get('TEST_VAR', ''))"],
            env={"TEST_VAR": "test_value"},
        )

        assert result.success is True
        assert "test_value" in result.stdout

    @pytest.mark.asyncio
    async def test_custom_cwd(self, tmp_path):
        """Test command with custom working directory."""
        result = await run_process(
            [sys.executable, "-c", "import os; print(os.getcwd())"],
            cwd=str(tmp_path),
        )

        assert result.success is True
        assert str(tmp_path) in result.stdout

    @pytest.mark.asyncio
    async def test_no_timeout(self):
        """Test command without timeout (should complete normally)."""
        result = await run_process(
            [sys.executable, "-c", "print('hello')"],
            timeout=None,
        )

        assert result.success is True
        assert "hello" in result.stdout


class TestKillProcessGroup:
    """Tests for kill_process_group function."""

    @pytest.mark.asyncio
    async def test_kill_already_terminated(self):
        """Test killing an already terminated process (no-op)."""
        mock_process = MagicMock()
        mock_process.returncode = 0  # Already terminated

        # Should return immediately without error
        await kill_process_group(mock_process)

    @pytest.mark.asyncio
    @pytest.mark.skipif(IS_WINDOWS, reason="Unix-specific test")
    async def test_kill_unix_process_group(self):
        """Test killing process group on Unix."""
        # Create a real subprocess that sleeps
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import time; time.sleep(60)",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )

        # Process should be running
        assert process.returncode is None

        # Kill the process group
        await kill_process_group(process)

        # Process should be terminated
        await asyncio.sleep(0.1)  # Give it a moment
        assert process.returncode is not None

    @pytest.mark.asyncio
    @pytest.mark.skipif(IS_UNIX, reason="Windows-specific test")
    async def test_kill_windows_process(self):
        """Test killing process on Windows."""
        # Create a real subprocess that sleeps
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import time; time.sleep(60)",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Process should be running
        assert process.returncode is None

        # Kill the process
        await kill_process_group(process)

        # Process should be terminated
        await asyncio.sleep(0.1)  # Give it a moment
        assert process.returncode is not None


class TestEnsureProcessTerminated:
    """Tests for ensure_process_terminated function."""

    @pytest.mark.asyncio
    async def test_terminate_already_dead(self):
        """Test terminating an already dead process (no-op)."""
        mock_process = MagicMock()
        mock_process.returncode = 0  # Already terminated

        # Should return immediately without error
        await ensure_process_terminated(mock_process)

    @pytest.mark.asyncio
    async def test_graceful_termination(self):
        """Test graceful process termination."""
        # Create a subprocess that handles SIGTERM gracefully
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import time; time.sleep(60)",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Process should be running
        assert process.returncode is None

        # Terminate gracefully
        await ensure_process_terminated(process)

        # Process should be terminated
        assert process.returncode is not None

    @pytest.mark.asyncio
    async def test_force_kill_after_timeout(self):
        """Test force kill when graceful termination times out."""
        # This test verifies that ensure_process_terminated will eventually
        # kill a process that doesn't respond to graceful termination.
        # We'll verify the behavior by checking that kill_process_group is called.

        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        mock_process.terminate = MagicMock()

        with patch("cub.core.tools.process.kill_process_group") as mock_kill:
            with patch("cub.core.tools.process.asyncio.wait_for") as mock_wait_for:
                # First wait_for (after terminate) raises TimeoutError
                mock_wait_for.side_effect = asyncio.TimeoutError()

                await ensure_process_terminated(mock_process)

            # Verify terminate was called
            mock_process.terminate.assert_called_once()
            # Verify kill_process_group was called after timeout
            mock_kill.assert_called_once_with(mock_process)


class TestIsProcessRunning:
    """Tests for is_process_running function."""

    def test_running_process(self):
        """Test checking if process is running."""
        mock_process = MagicMock()
        mock_process.returncode = None

        assert is_process_running(mock_process) is True

    def test_terminated_process(self):
        """Test checking terminated process."""
        mock_process = MagicMock()
        mock_process.returncode = 0

        assert is_process_running(mock_process) is False


class TestWaitForProcess:
    """Tests for wait_for_process function."""

    @pytest.mark.asyncio
    async def test_wait_without_timeout(self):
        """Test waiting for process without timeout."""
        # Create a quick process
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "print('done')",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        exit_code = await wait_for_process(process)

        assert exit_code == 0
        assert process.returncode == 0

    @pytest.mark.asyncio
    async def test_wait_with_timeout(self):
        """Test waiting for process with timeout."""
        # Create a quick process
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "print('done')",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        exit_code = await wait_for_process(process, timeout=5.0)

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_wait_timeout_exceeded(self):
        """Test timeout exceeded while waiting."""
        # Create a slow process
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import time; time.sleep(10)",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        with pytest.raises(asyncio.TimeoutError):
            await wait_for_process(process, timeout=0.1)

        # Clean up
        await ensure_process_terminated(process)


class TestPlatformDetection:
    """Tests for platform detection constants."""

    def test_platform_constants(self):
        """Test that platform constants are correctly set."""
        # Exactly one should be True
        assert IS_WINDOWS != IS_UNIX

        # Check against sys.platform
        if sys.platform == "win32":
            assert IS_WINDOWS is True
            assert IS_UNIX is False
        else:
            assert IS_WINDOWS is False
            assert IS_UNIX is True
