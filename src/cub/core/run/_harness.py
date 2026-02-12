"""
Harness invocation helpers for the run loop.

Provides the async harness invocation logic extracted from cli/run.py,
without any Rich/CLI dependencies. Streaming output is written directly
to stdout (the CLI layer can set up tee behavior separately).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from cub.core.harness.models import HarnessResult, TaskInput, TokenUsage

if TYPE_CHECKING:
    from cub.core.circuit_breaker import CircuitBreaker
    from cub.core.harness.async_backend import AsyncHarnessBackend


async def invoke_harness_async(
    harness_backend: AsyncHarnessBackend,
    task_input: TaskInput,
    *,
    stream: bool = False,
    debug: bool = False,
    harness_log_path: Path | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> HarnessResult:
    """
    Async harness invocation (used for circuit breaker wrapping).

    This is the core harness execution logic, extracted from cli/run.py
    to be usable from the RunLoop without Rich/Typer dependencies.

    Args:
        harness_backend: The harness backend to use.
        task_input: Task parameters (prompt, system_prompt, model, etc.).
        stream: Whether to stream output.
        debug: Enable debug logging.
        harness_log_path: Optional path to write raw harness output.
        circuit_breaker: Optional circuit breaker for heartbeat signaling.

    Returns:
        HarnessResult with output, usage, and timing.
    """
    start_time = time.time()

    if stream and harness_backend.capabilities.streaming:
        # Stream execution with tee-like behavior
        sys.stdout.flush()

        collected = ""
        usage = TokenUsage()
        message_count = 0
        stream_it = harness_backend.stream_task(task_input, debug=debug)
        async for chunk in stream_it:  # type: ignore[attr-defined]
            if isinstance(chunk, TokenUsage):
                usage = chunk
            else:
                if message_count > 0:
                    sys.stdout.write("\n")
                sys.stdout.write(chunk)
                sys.stdout.flush()
                collected += chunk
                message_count += 1

            # Signal activity to circuit breaker on every chunk
            if circuit_breaker is not None:
                circuit_breaker.heartbeat()

        sys.stdout.write("\n")
        sys.stdout.flush()

        # Write collected output to harness.log if path provided
        if harness_log_path is not None:
            try:
                harness_log_path.write_text(collected, encoding="utf-8")
            except Exception:
                pass  # Non-fatal

        return HarnessResult(
            output=collected,
            usage=usage,
            duration_seconds=time.time() - start_time,
            exit_code=0,
        )
    else:
        # Blocking execution with async backend
        task_result = await harness_backend.run_task(task_input, debug)

        # Write output to harness.log if path provided
        if harness_log_path is not None:
            try:
                harness_log_path.write_text(task_result.output, encoding="utf-8")
            except Exception:
                pass  # Non-fatal

        return HarnessResult(
            output=task_result.output,
            usage=task_result.usage,
            duration_seconds=task_result.duration_seconds,
            exit_code=task_result.exit_code,
            error=task_result.error,
            timestamp=task_result.timestamp,
        )
