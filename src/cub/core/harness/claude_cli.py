"""
Claude Code harness backend implementation (CLI shell-out).

This backend wraps the `claude` CLI tool for AI coding assistance with full
streaming support, token reporting, and model selection.

Use 'claude-cli' to explicitly select this backend, or 'claude-sdk' for the
SDK-based harness. The alias 'claude' defaults to 'claude-sdk'.
"""

import asyncio
import json
import logging
import os
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


@register_backend("claude-cli")
@register_async_backend("claude-cli")
class ClaudeCLIBackend:
    """
    Claude Code CLI harness backend (shell-out).

    Wraps the `claude` CLI tool with async compatibility via asyncio.to_thread().
    For SDK features like hooks, custom tools, and stateful sessions, use
    ClaudeSDKBackend (harness='claude-sdk' or 'claude').

    Features:
    - Full streaming support via --output-format stream-json
    - Token usage reporting from JSON output
    - System prompt support via --append-system-prompt
    - Auto mode via --dangerously-skip-permissions
    - Model selection via --model flag
    - Async wrapper around sync shell-out methods
    """

    def __init__(self) -> None:
        """Initialize the CLI backend."""
        pass

    @property
    def name(self) -> str:
        """Return 'claude-cli' as the harness name."""
        return "claude-cli"

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
        model: str | None = None,
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

        # Set up subprocess environment with CUB_RUN_ACTIVE to prevent hook double-tracking
        subprocess_env = os.environ.copy()
        subprocess_env["CUB_RUN_ACTIVE"] = "1"

        # Run command
        try:
            result = subprocess.run(
                ["claude"] + flags,
                input=task_prompt,
                text=True,
                capture_output=True,
                check=False,
                env=subprocess_env,
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
                        cost_usd=output_json.get("total_cost_usd"),
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
        model: str | None = None,
        debug: bool = False,
        callback: Callable[[str], None] | None = None,
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

        # Set up subprocess environment with CUB_RUN_ACTIVE to prevent hook double-tracking
        subprocess_env = os.environ.copy()
        subprocess_env["CUB_RUN_ACTIVE"] = "1"

        # Run command with streaming
        try:
            process = subprocess.Popen(
                ["claude"] + flags,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                env=subprocess_env,
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
                        # Claude outputs total_cost_usd, not cost_usd
                        cost = event.get("total_cost_usd")
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

    def supports_feature(self, feature: HarnessFeature) -> bool:
        """
        Check if harness supports a specific feature.

        Args:
            feature: Feature to check (from HarnessFeature enum)

        Returns:
            True if feature is supported
        """
        # Legacy harness supports basic shell-out features + analysis
        supported = {
            HarnessFeature.STREAMING,
            HarnessFeature.TOKEN_REPORTING,
            HarnessFeature.SYSTEM_PROMPT,
            HarnessFeature.AUTO_MODE,
            HarnessFeature.JSON_OUTPUT,
            HarnessFeature.MODEL_SELECTION,
            HarnessFeature.ANALYSIS,  # Read-only analysis via prompts
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
        # Build system prompt
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
    ) -> AsyncIterator[str | TokenUsage]:
        """
        Execute task with streaming output (async generator).

        Wraps sync invoke_streaming() method with asyncio.to_thread()
        and yields chunks via queue. The final yielded value is a
        TokenUsage object with usage data for the session.

        Args:
            task_input: Task parameters
            debug: Enable debug logging

        Yields:
            Output chunks as strings, and a final TokenUsage sentinel

        Raises:
            RuntimeError: If harness invocation fails
        """
        # Build system prompt
        system_prompt = task_input.system_prompt or ""

        # For now, run sync streaming in thread and collect output
        # TODO: Implement true async streaming with queue
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

        # Yield usage data as final sentinel
        if result.usage:
            yield result.usage

    def register_hook(
        self,
        event: HookEvent,
        handler: HookHandler,
    ) -> None:
        """
        Register a hook handler (no-op for legacy harness).

        The legacy shell-out harness does not support hooks. Hook registration
        is accepted but logged as a warning and the hooks will not be executed.

        For hook support, use the SDK-based harness (harness='claude').

        Args:
            event: Event to hook (ignored)
            handler: Handler function (ignored)
        """
        logger.warning(
            "Hook registration ignored: legacy harness '%s' does not support hooks. "
            "Use harness='claude' for SDK-based hook support.",
            self.name,
        )

    async def analyze(
        self,
        context: str,
        files_content: dict[str, str] | None = None,
        analysis_type: str = "implementation_review",
        model: str | None = None,
    ) -> TaskResult:
        """
        Run LLM-based analysis without modifying files.

        Uses run_task() internally with a specialized system prompt
        that instructs the LLM to analyze without making changes.

        Args:
            context: Context about what to analyze
            files_content: Dict mapping file paths to contents
            analysis_type: Type of analysis to perform
            model: Optional model override (defaults to 'sonnet')

        Returns:
            TaskResult with analysis text in output field
        """
        # Build analysis prompt
        system_prompt = self._build_analysis_system_prompt(analysis_type)
        user_prompt = self._build_analysis_user_prompt(context, files_content, analysis_type)

        # Create task input with read-only settings
        task_input = TaskInput(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=model or "sonnet",
            auto_approve=True,
        )

        return await self.run_task(task_input)

    def _build_analysis_system_prompt(self, analysis_type: str) -> str:
        """Build system prompt for analysis based on type."""
        base_prompt = """You are a code review assistant providing actionable feedback for follow-up work.

IMPORTANT RULES:
1. This is a READ-ONLY analysis. Do NOT suggest using any tools to modify files.
2. Do NOT attempt to run commands, create files, or make changes.
3. Focus on providing ACTIONABLE guidance for whoever will fix these issues.
4. Distinguish between issues with CLEAR FIXES vs issues that NEED DECISIONS.
"""

        type_prompts = {
            "implementation_review": """
Your goal is to compare implementation against the spec/plan/task and provide actionable follow-up guidance.

For each issue you find, determine:
1. Is the fix CLEAR from the spec/plan/task? → Provide specific fix instructions
2. Does this raise a QUESTION that needs human decision? → Flag for clarification

FORMAT YOUR RESPONSE WITH THESE SECTIONS:

## Summary
Brief overview: what percentage complete, major gaps, overall quality.

## Fix Now (Clear Remedies)
Issues where the correct fix is obvious from the spec/plan/task.
Format each as:
[SEVERITY] **Issue**: Description of what's wrong
**Expected**: What the spec/plan/task specified
**Fix**: Specific steps to resolve (be concrete - file names, function names, what to add/change)

## Needs Decision (Questions to Resolve)
Issues where implementation differs from spec in ways that might be intentional, or where the spec is ambiguous.
Format each as:
[WARNING] **Drift**: Description of the deviation
**Question**: What needs to be decided
**Options**: Possible resolutions and their trade-offs

## Verification Checklist
Concrete checks the follow-up work should pass:
- [ ] Specific test or validation to perform
- [ ] File/function that should exist
- [ ] Behavior that should be observable
""",
            "code_quality": """
Your goal is to analyze code quality and provide actionable improvement guidance.

FORMAT YOUR RESPONSE:

## Summary
Brief quality assessment with specific metrics if observable.

## Fix Now (Clear Issues)
Issues with obvious fixes. Format:
[SEVERITY] **Issue**: What's wrong
**Fix**: Specific remediation steps

## Consider (Trade-off Decisions)
Issues that involve trade-offs or architectural choices. Format:
[INFO] **Observation**: What you noticed
**Trade-off**: Why this might be intentional vs problematic
**Recommendation**: Suggested approach if they decide to address it

## Verification Checklist
- [ ] Specific quality checks to run
- [ ] Tests to add or verify
""",
            "spec_gap": """
Your goal is to find gaps between spec and implementation, categorizing each by actionability.

FORMAT YOUR RESPONSE:

## Summary
Alignment score (0-100%) and key findings.

## Missing from Implementation (Fix Required)
Features in spec but not in code. Format:
[SEVERITY] **Gap**: What's missing
**Spec Reference**: Where this was specified
**Implementation Path**: Suggested approach to add it

## Implementation Drift (Decision Required)
Features in code but not in spec, or behavioral differences. Format:
[WARNING] **Drift**: What differs
**Question**: Keep, remove, or update spec?
**Impact**: What changes if each option is chosen

## Alignment Checklist
- [ ] Specific spec requirements to verify
- [ ] Behaviors to test
""",
        }

        return base_prompt + type_prompts.get(
            analysis_type, type_prompts["implementation_review"]
        )

    def _build_analysis_user_prompt(
        self,
        context: str,
        files_content: dict[str, str] | None,
        analysis_type: str,
    ) -> str:
        """Build user prompt with context and file contents."""
        parts = [f"# Analysis Request\n\n{context}"]

        if files_content:
            parts.append("\n\n# Files to Analyze\n")
            for path, content in files_content.items():
                # Truncate very large files
                if len(content) > 50000:
                    content = content[:50000] + "\n... [truncated]"
                parts.append(f"\n## {path}\n```\n{content}\n```\n")

        parts.append(f"\n\nPlease perform a {analysis_type.replace('_', ' ')} analysis.")

        return "".join(parts)
