"""
Process management utilities for safe subprocess spawning and cleanup.

This module provides utilities for:
- Safe process spawning with timeout support
- Process group management for clean termination
- Platform-specific handling (Windows vs Unix)
- Graceful shutdown with escalating termination
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_UNIX = not IS_WINDOWS


class ProcessResult(BaseModel):
    """Structured result from process execution."""

    success: bool
    """Whether the process completed successfully (exit code 0)."""

    exit_code: int | None
    """Process exit code, or None if killed/timed out."""

    stdout: str
    """Standard output from the process."""

    stderr: str
    """Standard error from the process."""

    duration_ms: int
    """Execution duration in milliseconds."""

    timed_out: bool = False
    """Whether the process was terminated due to timeout."""

    error: str | None = None
    """Error message if execution failed."""


async def run_process(
    command: list[str],
    *,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    input_data: str | None = None,
) -> ProcessResult:
    """
    Run a subprocess with timeout and automatic cleanup.

    This function provides safe subprocess execution with:
    - Automatic process group creation for clean termination
    - Timeout handling with graceful shutdown
    - Platform-specific process management (Windows vs Unix)
    - Comprehensive error handling

    Args:
        command: Command and arguments as a list (e.g., ["git", "status"])
        timeout: Optional timeout in seconds. None means no timeout.
        env: Optional environment variables. Merged with os.environ if provided.
        cwd: Optional working directory for the process.
        input_data: Optional string to send to stdin.

    Returns:
        ProcessResult with output, exit code, and timing information.

    Example:
        >>> result = await run_process(
        ...     ["git", "status"],
        ...     timeout=30.0,
        ...     cwd="/path/to/repo"
        ... )
        >>> if result.success:
        ...     print(result.stdout)
    """
    started_at = datetime.now(timezone.utc)
    process: asyncio.subprocess.Process | None = None

    # Build environment variables
    process_env = None
    if env is not None:
        process_env = os.environ.copy()
        process_env.update(env)

    try:
        # Create subprocess with platform-specific options
        kwargs: dict[str, Any] = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "cwd": cwd,
            "env": process_env,
        }

        if input_data is not None:
            kwargs["stdin"] = asyncio.subprocess.PIPE

        # Use start_new_session on Unix to create process group
        # On Windows, this parameter is ignored (not supported)
        if IS_UNIX:
            kwargs["start_new_session"] = True

        logger.debug(f"Running process: {' '.join(command)}")
        process = await asyncio.create_subprocess_exec(*command, **kwargs)

        # Communicate with timeout
        try:
            input_bytes = input_data.encode("utf-8") if input_data else None

            if timeout is not None:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(input_bytes),
                    timeout=timeout,
                )
            else:
                stdout_bytes, stderr_bytes = await process.communicate(input_bytes)

            # Calculate duration
            duration_ms = int(
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
            )

            # Decode output
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

            # Check success
            success = process.returncode == 0

            return ProcessResult(
                success=success,
                exit_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
                timed_out=False,
            )

        except asyncio.TimeoutError:
            # Kill the process group on timeout
            await kill_process_group(process)

            duration_ms = int(
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
            )

            return ProcessResult(
                success=False,
                exit_code=None,
                stdout="",
                stderr="",
                duration_ms=duration_ms,
                timed_out=True,
                error=f"Process timed out after {timeout}s",
            )

    except FileNotFoundError:
        duration_ms = int(
            (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
        )
        return ProcessResult(
            success=False,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=duration_ms,
            error=f"Command not found: {command[0]}. Ensure it is installed and in PATH.",
        )

    except Exception as e:
        duration_ms = int(
            (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
        )
        logger.exception(f"Unexpected error running process: {command}")
        return ProcessResult(
            success=False,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=duration_ms,
            error=f"Unexpected error: {e}",
        )

    finally:
        # Ensure process is terminated
        if process is not None:
            await ensure_process_terminated(process)


async def kill_process_group(process: asyncio.subprocess.Process) -> None:
    """
    Kill the process group to ensure all child processes are terminated.

    This function handles platform differences:
    - Unix: Uses process groups with os.killpg()
    - Windows: Falls back to direct process.kill()

    Args:
        process: The subprocess to kill along with its children.
    """
    if process.returncode is not None:
        return  # Already terminated

    try:
        if IS_UNIX:
            # Unix: Kill the entire process group
            try:
                # Get the process group ID (same as PID due to start_new_session=True)
                pgid = os.getpgid(process.pid)
                # Kill the entire process group
                os.killpg(pgid, signal.SIGKILL)
                logger.debug(f"Killed process group {pgid}")
            except (ProcessLookupError, OSError) as e:
                # Process may have already terminated
                logger.debug(f"Process group kill failed (process may be dead): {e}")
                pass

        else:
            # Windows: Direct process kill
            # Note: On Windows, subprocess termination doesn't kill child processes
            # automatically. For proper child cleanup on Windows, consider using
            # job objects via the `win32job` module or `psutil` library.
            try:
                process.kill()
                logger.debug(f"Killed process {process.pid} on Windows")
            except (ProcessLookupError, OSError) as e:
                logger.debug(f"Process kill failed (process may be dead): {e}")
                pass

        # Wait for process to terminate
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            # Last resort - force kill the process directly if not already tried
            if IS_UNIX:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except (asyncio.TimeoutError, ProcessLookupError, OSError):
                    pass

    except Exception as e:
        logger.warning(f"Error during process group kill: {e}")


async def ensure_process_terminated(process: asyncio.subprocess.Process) -> None:
    """
    Ensure the process is fully terminated using graceful shutdown.

    This function implements an escalating termination strategy:
    1. Try graceful termination with SIGTERM (process.terminate())
    2. Wait up to 2 seconds for graceful shutdown
    3. Force kill with SIGKILL if still running (via kill_process_group)

    Should be called in finally blocks to guarantee cleanup.

    Args:
        process: The subprocess to terminate.
    """
    if process.returncode is not None:
        return  # Already terminated

    try:
        # Step 1: Try graceful termination first
        logger.debug(f"Terminating process {process.pid} gracefully")
        process.terminate()

        try:
            # Step 2: Wait for graceful shutdown
            await asyncio.wait_for(process.wait(), timeout=2.0)
            logger.debug(f"Process {process.pid} terminated gracefully")
        except asyncio.TimeoutError:
            # Step 3: Force kill if graceful termination didn't work
            logger.debug(f"Process {process.pid} did not terminate gracefully, force killing")
            await kill_process_group(process)

    except (ProcessLookupError, OSError) as e:
        # Process already terminated
        logger.debug(f"Process termination skipped (already dead): {e}")
        pass
    except Exception as e:
        logger.warning(f"Error during process termination: {e}")


def is_process_running(process: asyncio.subprocess.Process) -> bool:
    """
    Check if a process is still running.

    Args:
        process: The subprocess to check.

    Returns:
        True if the process is still running, False otherwise.
    """
    return process.returncode is None


async def wait_for_process(
    process: asyncio.subprocess.Process,
    timeout: float | None = None,
) -> int | None:
    """
    Wait for a process to complete with optional timeout.

    Args:
        process: The subprocess to wait for.
        timeout: Optional timeout in seconds. None means wait indefinitely.

    Returns:
        The process exit code, or None if timed out.

    Raises:
        asyncio.TimeoutError: If timeout is exceeded.
    """
    if timeout is not None:
        await asyncio.wait_for(process.wait(), timeout=timeout)
    else:
        await process.wait()

    return process.returncode
