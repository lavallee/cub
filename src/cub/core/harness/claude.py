"""
Claude Code harness backend implementation.

This backend wraps the `claude` CLI tool for AI coding assistance with full
streaming support, token reporting, and model selection.
"""

import json
import os
import shutil
import subprocess
import time
from typing import Callable, Optional

from .backend import HarnessBackend, register_backend
from .models import HarnessCapabilities, HarnessResult, TokenUsage


@register_backend("claude")
class ClaudeBackend:
    """
    Claude Code harness backend.

    Wraps the `claude` CLI tool with:
    - Full streaming support via --output-format stream-json
    - Token usage reporting from JSON output
    - System prompt support via --append-system-prompt
    - Auto mode via --dangerously-skip-permissions
    - Model selection via --model flag
    """

    @property
    def name(self) -> str:
        """Return 'claude' as the harness name."""
        return "claude"

    @property
    def capabilities(self) -> HarnessCapabilities:
        """
        Claude supports all major capabilities.

        Returns:
            HarnessCapabilities with all features enabled
        """
        return HarnessCapabilities(
            streaming=True,
            token_reporting=True,
            system_prompt=True,
            auto_mode=True,
            json_output=True,
            model_selection=True,
        )

    def is_available(self) -> bool:
        """
        Check if claude CLI is available.

        Returns:
            True if 'claude' command exists in PATH
        """
        return shutil.which("claude") is not None

    def invoke(
        self,
        system_prompt: str,
        task_prompt: str,
        model: Optional[str] = None,
        debug: bool = False,
    ) -> HarnessResult:
        """
        Invoke Claude with blocking execution.

        Uses --output-format json to get structured output with token usage.

        Args:
            system_prompt: System prompt (prepended instructions)
            task_prompt: User/task prompt (specific request)
            model: Optional model name (e.g., 'sonnet', 'opus')
            debug: Enable debug logging

        Returns:
            HarnessResult with output, usage, and timing
        """
        start_time = time.time()

        # Build command flags
        flags = [
            "-p",  # Pipe mode (read from stdin)
            "--append-system-prompt",
            system_prompt,
            "--dangerously-skip-permissions",
            "--output-format",
            "json",
        ]

        # Add model if specified
        if model is None:
            model = os.environ.get("CUB_MODEL")
        if model:
            flags.extend(["--model", model])

        # Add debug flag if requested
        if debug:
            flags.append("--debug")

        # Add extra flags from environment
        extra_flags = os.environ.get("CLAUDE_FLAGS", "").strip()
        if extra_flags:
            flags.extend(extra_flags.split())

        # Run command
        try:
            result = subprocess.run(
                ["claude"] + flags,
                input=task_prompt,
                text=True,
                capture_output=True,
                check=False,
            )

            duration = time.time() - start_time

            # Parse JSON output
            output_text = ""
            usage = TokenUsage()
            error = None

            try:
                output_json = json.loads(result.stdout)

                # Extract result text
                output_text = output_json.get("result") or output_json.get("content", "")

                # Extract usage
                if "usage" in output_json:
                    usage_data = output_json["usage"]
                    usage = TokenUsage(
                        input_tokens=usage_data.get("input_tokens", 0),
                        output_tokens=usage_data.get("output_tokens", 0),
                        cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
                        cache_creation_tokens=usage_data.get("cache_creation_input_tokens", 0),
                        cost_usd=output_json.get("cost_usd"),
                        estimated=False,
                    )

            except (json.JSONDecodeError, KeyError):
                # If JSON parsing fails, output as-is (likely error message)
                output_text = result.stdout or result.stderr
                if result.returncode != 0:
                    error = f"Claude command failed: {result.stderr}"

            return HarnessResult(
                output=output_text,
                usage=usage,
                duration_seconds=duration,
                exit_code=result.returncode,
                error=error,
            )

        except Exception as e:
            duration = time.time() - start_time
            return HarnessResult(
                output="",
                usage=TokenUsage(),
                duration_seconds=duration,
                exit_code=1,
                error=f"Failed to invoke claude: {e}",
            )

    def invoke_streaming(
        self,
        system_prompt: str,
        task_prompt: str,
        model: Optional[str] = None,
        debug: bool = False,
        callback: Optional[Callable[[str], None]] = None,
    ) -> HarnessResult:
        """
        Invoke Claude with streaming output.

        Uses --output-format stream-json to get real-time output events.
        Parses events to extract text and token usage.

        Args:
            system_prompt: System prompt (prepended instructions)
            task_prompt: User/task prompt (specific request)
            model: Optional model name
            debug: Enable debug logging
            callback: Optional callback for each text chunk

        Returns:
            HarnessResult with complete output and usage
        """
        start_time = time.time()

        # Build command flags
        flags = [
            "-p",
            "--append-system-prompt",
            system_prompt,
            "--dangerously-skip-permissions",
            "--verbose",
            "--output-format",
            "stream-json",
        ]

        # Add model if specified
        if model is None:
            model = os.environ.get("CUB_MODEL")
        if model:
            flags.extend(["--model", model])

        # Add debug flag if requested
        if debug:
            flags.append("--debug")

        # Add extra flags from environment
        extra_flags = os.environ.get("CLAUDE_FLAGS", "").strip()
        if extra_flags:
            flags.extend(extra_flags.split())

        # Run command with streaming
        try:
            process = subprocess.Popen(
                ["claude"] + flags,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Send task prompt
            if process.stdin is not None:
                process.stdin.write(task_prompt)
                process.stdin.close()

            # Parse streaming output
            output_chunks = []
            total_input = 0
            total_output = 0
            total_cache_read = 0
            total_cache_creation = 0
            final_cost = None

            if process.stdout is None:
                raise RuntimeError("Failed to capture stdout from claude process")

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                    event_type = event.get("type", "")

                    # Handle different event types
                    if event_type in ("assistant", "message"):
                        # Extract usage from message events
                        if "usage" in event:
                            usage_data = event["usage"]
                            total_input += usage_data.get("input_tokens", 0)
                            total_output += usage_data.get("output_tokens", 0)
                            total_cache_read += usage_data.get("cache_read_input_tokens", 0)
                            total_cache_creation += usage_data.get("cache_creation_input_tokens", 0)

                        # Extract text content from assistant messages
                        if "message" in event and "content" in event["message"]:
                            for content_block in event["message"]["content"]:
                                if content_block.get("type") == "text":
                                    text = content_block.get("text", "")
                                    if text:
                                        output_chunks.append(text)
                                        if callback:
                                            callback(text)

                    elif event_type == "content_block_delta":
                        # Extract text deltas
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                output_chunks.append(text)
                                if callback:
                                    callback(text)

                    elif event_type == "result":
                        # Extract cost from result event
                        cost = event.get("cost_usd")
                        if cost is not None:
                            final_cost = cost

                except json.JSONDecodeError:
                    # Skip malformed JSON lines
                    continue

            # Wait for process completion
            process.wait()
            duration = time.time() - start_time

            # Build result
            output_text = "".join(output_chunks)
            usage = TokenUsage(
                input_tokens=total_input,
                output_tokens=total_output,
                cache_read_tokens=total_cache_read,
                cache_creation_tokens=total_cache_creation,
                cost_usd=final_cost,
                estimated=False,
            )

            error = None
            if process.returncode != 0:
                stderr = process.stderr.read() if process.stderr is not None else ""
                error = f"Claude command failed: {stderr}"

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
                usage=TokenUsage(),
                duration_seconds=duration,
                exit_code=1,
                error=f"Failed to invoke claude streaming: {e}",
            )

    def get_version(self) -> str:
        """
        Get Claude CLI version.

        Returns:
            Version string or 'unknown' if unavailable
        """
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout.strip() or "unknown"
        except Exception:
            return "unknown"
