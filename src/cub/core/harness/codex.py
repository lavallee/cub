"""
Codex CLI harness backend implementation (legacy shell-out).

This backend wraps the `codex` CLI tool for AI coding assistance with streaming
support, model selection, and autonomous execution.

Note: Since there is no SDK-based Codex harness yet, this is the primary
implementation. It has been migrated to support the async interface for
compatibility with the harness abstraction layer.
"""

import asyncio
import json
import logging
import shutil
import subprocess
import time
from collections.abc import AsyncIterator, Callable

from .async_backend import register_async_backend
from .backend import register_backend
from .models import (
    HarnessCapabilities,
    HarnessFeature,
    HarnessResult,
    HookEvent,
    HookHandler,
    TaskInput,
    TaskResult,
    TokenUsage,
)

logger = logging.getLogger(__name__)


@register_backend("codex")
@register_async_backend("codex")
class CodexBackend:
    """
    Codex CLI harness backend with async support.

    Wraps the `codex` CLI tool with:
    - Streaming support via --json JSONL output
    - Model selection via -m flag
    - Auto mode via --dangerously-bypass-approvals-and-sandbox
    - No separate system prompt (combined with task prompt)
    - Token usage estimation (CLI doesn't report actual usage)
    - Async wrapper around sync shell-out methods

    Note: This is the primary Codex implementation. No SDK-based
    harness exists yet, so no deprecation warning is shown.
    """

    @property
    def name(self) -> str:
        """Return 'codex' as the harness name."""
        return "codex"

    @property
    def capabilities(self) -> HarnessCapabilities:
        """
        Codex supports streaming, auto mode, JSON output, and model selection.

        Does NOT support:
        - system_prompt: Must combine system and task prompts
        - token_reporting: CLI doesn't report actual usage, only estimates

        Returns:
            HarnessCapabilities with supported features enabled
        """
        return HarnessCapabilities(
            streaming=True,
            token_reporting=False,
            system_prompt=False,
            auto_mode=True,
            json_output=True,
            model_selection=True,
        )

    def is_available(self) -> bool:
        """
        Check if codex CLI is available.

        Returns:
            True if 'codex' command exists in PATH
        """
        return shutil.which("codex") is not None

    def invoke(
        self,
        system_prompt: str,
        task_prompt: str,
        model: str | None = None,
        debug: bool = False,
    ) -> HarnessResult:
        """
        Invoke Codex with blocking execution.

        Codex doesn't support separate system prompts, so they are combined
        with a separator.

        Args:
            system_prompt: System prompt (prepended instructions)
            task_prompt: User/task prompt (specific request)
            model: Optional model name (e.g., 'gpt-5.2-codex')
            debug: Enable debug logging

        Returns:
            HarnessResult with output, estimated usage, and timing
        """
        start_time = time.time()

        # Combine prompts since Codex doesn't have --append-system-prompt
        combined_prompt = f"{system_prompt}\n\n---\n\n{task_prompt}"

        # Build command flags
        flags = ["--dangerously-bypass-approvals-and-sandbox"]

        # Add model if specified
        if model:
            flags.extend(["-m", model])

        # Add extra flags from environment
        import os

        extra_flags = os.environ.get("CODEX_FLAGS", "").strip()
        if extra_flags:
            flags.extend(extra_flags.split())

        # Run command
        try:
            result = subprocess.run(
                ["codex", "exec"] + flags + ["-"],
                input=combined_prompt,
                text=True,
                capture_output=True,
                check=False,
            )

            duration = time.time() - start_time

            # Codex CLI doesn't report actual token usage
            # Estimate based on character counts (rough: 4 chars per token)
            input_chars = len(combined_prompt)
            output_chars = len(result.stdout)
            estimated_input = input_chars // 4
            estimated_output = output_chars // 4

            usage = TokenUsage(
                input_tokens=estimated_input,
                output_tokens=estimated_output,
                estimated=True,
            )

            error = None
            if result.returncode != 0:
                error = f"Codex command failed: {result.stderr}"

            return HarnessResult(
                output=result.stdout,
                usage=usage,
                duration_seconds=duration,
                exit_code=result.returncode,
                error=error,
            )

        except Exception as e:
            duration = time.time() - start_time
            return HarnessResult(
                output="",
                usage=TokenUsage(estimated=True),
                duration_seconds=duration,
                exit_code=1,
                error=f"Failed to invoke codex: {e}",
            )

    def invoke_streaming(
        self,
        system_prompt: str,
        task_prompt: str,
        model: str | None = None,
        debug: bool = False,
        callback: Callable[[str], None] | None = None,
    ) -> HarnessResult:
        """
        Invoke Codex with streaming output.

        Uses --json flag to get JSONL events with item details.
        Parses events to extract text and commands in real-time.

        Args:
            system_prompt: System prompt (prepended instructions)
            task_prompt: User/task prompt (specific request)
            model: Optional model name
            debug: Enable debug logging
            callback: Optional callback for each text chunk

        Returns:
            HarnessResult with complete output and estimated usage
        """
        start_time = time.time()

        # Combine prompts
        combined_prompt = f"{system_prompt}\n\n---\n\n{task_prompt}"

        # Build command flags
        flags = ["--dangerously-bypass-approvals-and-sandbox", "--json"]

        # Add model if specified
        if model:
            flags.extend(["-m", model])

        # Add extra flags from environment
        import os

        extra_flags = os.environ.get("CODEX_FLAGS", "").strip()
        if extra_flags:
            flags.extend(extra_flags.split())

        # Run command with streaming
        try:
            process = subprocess.Popen(
                ["codex", "exec"] + flags + ["-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Send combined prompt
            if process.stdin is not None:
                process.stdin.write(combined_prompt)
                process.stdin.close()

            # Parse streaming JSONL output
            output_chunks = []
            total_input = 0
            total_output = 0

            if process.stdout is None:
                raise RuntimeError("Failed to capture stdout from codex process")

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                    event_type = event.get("type", "")

                    # Handle different event types
                    if event_type == "item.started":
                        # Show what's starting (commands, file edits, etc.)
                        item = event.get("item", {})
                        item_type = item.get("type", "")

                        if item_type == "command_execution":
                            cmd = item.get("command", "")
                            if cmd and callback:
                                callback(f"$ {cmd}\n")
                        elif item_type in ("file_edit", "file_write"):
                            file_path = item.get("file_path") or item.get("path", "")
                            if file_path and callback:
                                callback(f"▶ Editing: {file_path}\n")

                    elif event_type == "item.completed":
                        # Extract item details
                        item = event.get("item", {})
                        item_type = item.get("type", "")

                        if item_type == "reasoning":
                            text = item.get("text", "")
                            if text:
                                output_chunks.append(text)
                                if callback:
                                    callback(text)

                        elif item_type == "message":
                            content = item.get("content") or item.get("text", "")
                            if content:
                                output_chunks.append(content)
                                if callback:
                                    callback(content)

                        elif item_type == "command_execution":
                            output = item.get("aggregated_output", "")
                            if output:
                                # Truncate long output
                                if len(output) > 500:
                                    output = output[:500] + "..."
                                output_chunks.append(output + "\n")
                                if callback:
                                    callback(output + "\n")

                    elif event_type == "turn.completed":
                        # Extract usage if available
                        usage = event.get("usage", {})
                        if usage:
                            total_input += usage.get("input_tokens", 0)
                            total_output += usage.get("output_tokens", 0)

                except json.JSONDecodeError:
                    # Skip malformed JSON lines
                    continue

            # Wait for process completion
            process.wait()
            duration = time.time() - start_time

            # Build result
            output_text = "".join(output_chunks)

            # If no usage reported, estimate from character counts
            if total_input == 0 and total_output == 0:
                input_chars = len(combined_prompt)
                output_chars = len(output_text)
                total_input = input_chars // 4
                total_output = output_chars // 4

            usage = TokenUsage(
                input_tokens=total_input,
                output_tokens=total_output,
                estimated=True,
            )

            error = None
            if process.returncode != 0:
                stderr = process.stderr.read() if process.stderr is not None else ""
                error = f"Codex command failed: {stderr}"

            return HarnessResult(
                output=output_text,
                usage=usage,
                duration_seconds=duration,
                exit_code=process.returncode,
                error=error,
            )

        except Exception as e:
            duration = time.time() - start_time
            return HarnessResult(
                output="",
                usage=TokenUsage(estimated=True),
                duration_seconds=duration,
                exit_code=1,
                error=f"Failed to invoke codex streaming: {e}",
            )

    def get_version(self) -> str:
        """
        Get Codex CLI version.

        Returns:
            Version string or 'unknown' if unavailable
        """
        try:
            result = subprocess.run(
                ["codex", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout.strip() or "unknown"
        except Exception:
            return "unknown"

    def supports_feature(self, feature: HarnessFeature) -> bool:
        """
        Check if harness supports a specific feature.

        Args:
            feature: Feature to check (from HarnessFeature enum)

        Returns:
            True if feature is supported
        """
        # Codex supports these features
        supported = {
            HarnessFeature.STREAMING,
            HarnessFeature.AUTO_MODE,
            HarnessFeature.JSON_OUTPUT,
            HarnessFeature.MODEL_SELECTION,
        }
        return feature in supported

    # Async interface methods (AsyncHarnessBackend protocol)

    async def run_task(
        self,
        task_input: TaskInput,
        debug: bool = False,
    ) -> TaskResult:
        """
        Execute task with blocking execution (async wrapper).

        Wraps sync invoke() method with asyncio.to_thread() for
        compatibility with async interface.

        Args:
            task_input: Task parameters (prompt, model, permissions, etc.)
            debug: Enable debug logging

        Returns:
            TaskResult with output, usage, messages, and file changes

        Raises:
            RuntimeError: If harness invocation fails
        """
        # Build system prompt (Codex combines system and task prompts)
        system_prompt = task_input.system_prompt or ""

        # Run sync method in thread pool
        result = await asyncio.to_thread(
            self.invoke,
            system_prompt=system_prompt,
            task_prompt=task_input.prompt,
            model=task_input.model,
            debug=debug,
        )

        # Convert HarnessResult to TaskResult
        return TaskResult(
            output=result.output,
            usage=result.usage,
            duration_seconds=result.duration_seconds,
            exit_code=result.exit_code,
            error=result.error,
            timestamp=result.timestamp,
            messages=[],  # Legacy harness doesn't track messages
            files_changed=[],  # Legacy harness doesn't track file changes
            files_created=[],
        )

    async def stream_task(
        self,
        task_input: TaskInput,
        debug: bool = False,
    ) -> AsyncIterator[str]:
        """
        Execute task with streaming output (async generator).

        Wraps sync invoke_streaming() method with asyncio.to_thread().

        Args:
            task_input: Task parameters
            debug: Enable debug logging

        Yields:
            Output chunks as strings

        Raises:
            RuntimeError: If harness invocation fails
        """
        # Build system prompt
        system_prompt = task_input.system_prompt or ""

        # Run sync streaming in thread and collect output
        result = await asyncio.to_thread(
            self.invoke_streaming,
            system_prompt=system_prompt,
            task_prompt=task_input.prompt,
            model=task_input.model,
            debug=debug,
            callback=None,  # Don't use callback for now
        )

        # Yield the complete output
        # This is not true streaming, but compatible with async interface
        if result.output:
            yield result.output

        if result.error:
            raise RuntimeError(f"Harness invocation failed: {result.error}")

    def register_hook(
        self,
        event: HookEvent,
        handler: HookHandler,
    ) -> None:
        """
        Register a hook handler (no-op for Codex harness).

        The Codex shell-out harness does not support hooks. Hook registration
        is accepted but logged as a warning and the hooks will not be executed.

        Args:
            event: Event to hook (ignored)
            handler: Handler function (ignored)
        """
        logger.warning(
            "Hook registration ignored: harness '%s' does not support hooks.",
            self.name,
        )
