# Claude Code Harness

Claude Code is the most full-featured harness, supporting all capabilities including hooks, custom tools, and stateful sessions. It is the recommended choice for complex autonomous coding tasks.

!!! note "SDK vs Legacy (v0.24+)"
    Cub now offers two Claude backends:

    - **`claude`** (default): Uses Claude Agent SDK for full hook support
    - **`claude-cli`**: Uses shell-out mode for compatibility

    The SDK backend is recommended for new projects.

## Capabilities

| Capability | SDK (`claude`) | CLI (`claude-cli`) |
|------------|:--------------:|:------------------------:|
| streaming | :white_check_mark: | :white_check_mark: |
| token_reporting | :white_check_mark: | :white_check_mark: |
| system_prompt | :white_check_mark: | :white_check_mark: |
| auto_mode | :white_check_mark: | :white_check_mark: |
| json_output | :white_check_mark: | :white_check_mark: |
| model_selection | :white_check_mark: | :white_check_mark: |
| **hooks** | :white_check_mark: | :x: |
| **custom_tools** | :white_check_mark: | :x: |
| **sessions** | :white_check_mark: | :x: |

## Installation

Install Claude Code from the official repository:

```bash
# Via npm (recommended)
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version
```

For detailed installation instructions, see the [Claude Code documentation](https://github.com/anthropics/claude-code).

### SDK Dependencies (Optional)

For SDK features (hooks, custom tools), install the Python SDK:

```bash
pip install claude-agent-sdk
```

If the SDK is not installed, cub automatically falls back to legacy mode.

## Features

### Streaming Output

Claude Code supports real-time streaming via `--output-format stream-json`. When running with streaming enabled, you see output as it's generated:

```bash
cub run --stream
```

### Token Reporting

Claude provides accurate token usage including:

- Input tokens
- Output tokens
- Cache read tokens (for prompt caching)
- Cache creation tokens
- Cost in USD

This enables precise budget tracking with `--budget` flags.

### System Prompt Support

Claude Code supports separate system prompts via `--append-system-prompt`. This keeps your task instructions distinct from system-level guidance in PROMPT.md.

### Model Selection

Select models at runtime with the `--model` flag:

- `haiku` - Fast, cost-effective for simple tasks
- `sonnet` - Balanced performance and cost
- `opus` - Most capable for complex tasks

Use task labels to select models per task:

```bash
bd label <task-id> model:haiku
```

## Example Invocation

Here's how cub invokes Claude Code:

```bash
echo "$task" | claude -p \
    --append-system-prompt "$system" \
    --dangerously-skip-permissions \
    --output-format stream-json \
    --model sonnet
```

### Flags Used

| Flag | Purpose |
|------|---------|
| `-p` | Pipe mode (read task from stdin) |
| `--append-system-prompt` | Add system instructions |
| `--dangerously-skip-permissions` | Enable auto mode |
| `--output-format` | JSON or stream-json output |
| `--model` | Select model (haiku, sonnet, opus) |

## Environment Variables

### CLAUDE_FLAGS

Pass additional flags to the Claude CLI:

```bash
export CLAUDE_FLAGS="--verbose --max-tokens 4000"
cub run
```

### CUB_MODEL

Override the model for all tasks:

```bash
export CUB_MODEL=opus
cub run
```

This is equivalent to adding `--model opus` to every invocation. Task labels with `model:` take precedence.

## Token Usage

Claude reports detailed token usage in its JSON output:

```json
{
  "result": "Task completed successfully...",
  "usage": {
    "input_tokens": 1500,
    "output_tokens": 800,
    "cache_read_input_tokens": 500,
    "cache_creation_input_tokens": 200
  },
  "cost_usd": 0.0045
}
```

Cub uses this data for:

- Budget tracking (`--budget`, `--iteration-budget`)
- Cost reporting in `cub status`
- Iteration summaries in logs

## Tips and Best Practices

### Use Sonnet for Most Tasks

Sonnet offers the best balance of capability and cost. Reserve opus for complex architectural decisions.

```bash
# Default to sonnet
export CUB_MODEL=sonnet

# Use opus for specific tasks
bd label cub-abc123 model:opus
```

### Enable Streaming for Visibility

Streaming provides real-time feedback on what the AI is doing:

```bash
cub run --stream
```

### Leverage Prompt Caching

Claude's prompt caching reduces costs for repeated similar prompts. Structure your PROMPT.md to maximize cache hits by putting stable content first.

### Set Reasonable Budgets

Use budget flags to prevent runaway costs:

```bash
# Limit total session cost
cub run --budget 5.00

# Limit per-iteration cost
cub run --iteration-budget 0.50
```

## Troubleshooting

### "claude: command not found"

Ensure Claude Code is installed and in your PATH:

```bash
which claude
# Should return: /usr/local/bin/claude or similar
```

If not found, reinstall or add to PATH:

```bash
npm install -g @anthropic-ai/claude-code
```

### Rate Limit Errors

Claude may hit rate limits during intensive sessions. Cub automatically retries with backoff. To reduce rate limit issues:

- Use `--delay` to add pauses between iterations
- Consider sonnet instead of opus for routine tasks

### High Token Usage

If token usage seems high:

1. Check PROMPT.md - large system prompts increase every invocation
2. Review task descriptions - overly verbose tasks consume more tokens
3. Use streaming to monitor what the AI is doing

---

## Hooks System (SDK Only)

The SDK backend (`claude`) supports hooks for intercepting and controlling AI behavior. Hooks enable:

- **Guardrails**: Block dangerous commands before execution
- **Logging**: Track tool usage and decisions
- **Circuit breakers**: Stop runaway loops
- **Custom behavior**: Modify prompts or inject context

### Hook Events

| Event | When Fired | Use Case |
|-------|------------|----------|
| `PRE_TASK` | Before task starts | Validate inputs, inject context |
| `POST_TASK` | After task completes | Log results, cleanup |
| `PRE_TOOL_USE` | Before tool execution | Block dangerous commands |
| `POST_TOOL_USE` | After tool execution | Log tool results |
| `ON_ERROR` | When error occurs | Custom error handling |
| `ON_MESSAGE` | On each AI message | Real-time monitoring |

### Example: Blocking Dangerous Commands

```python
from cub.core.harness import HookEvent, HookContext, HookResult

def block_dangerous_commands(context: HookContext) -> HookResult:
    """Block rm -rf and other dangerous commands."""
    if context.event == HookEvent.PRE_TOOL_USE:
        if context.tool_name == "bash":
            command = context.tool_input.get("command", "")
            if "rm -rf" in command or "sudo" in command:
                return HookResult(
                    block=True,
                    message="Blocked dangerous command"
                )
    return HookResult(block=False)

# Register the hook
backend.register_hook(HookEvent.PRE_TOOL_USE, block_dangerous_commands)
```

### Configuring Hooks

Hooks can be configured in `.cub.json`:

```json
{
  "harness": {
    "hooks": {
      "block_patterns": ["rm -rf", "sudo", "curl | sh"],
      "log_tool_usage": true,
      "max_iterations": 50
    }
  }
}
```

For more details, see the [Hooks System](../hooks/index.md) guide.

---

## CLI Backend

The CLI backend (`claude-cli`) uses shell-out mode, invoking Claude Code as a subprocess. Use this for:

- Compatibility with older environments
- Troubleshooting SDK integration issues
- Simpler deployments without SDK dependencies

### Selecting CLI Mode

```bash
# Via CLI flag
cub run --harness claude-cli

# Via environment variable
HARNESS=claude-cli cub run

# Via config
# .cub.json
{
  "harness": {
    "default": "claude-cli"
  }
}
```

### Differences from SDK

| Feature | SDK | Legacy |
|---------|-----|--------|
| Hooks | Full support | No-op (silent) |
| Custom tools | Supported | Not available |
| Sessions | Supported | Not available |
| Execution | In-process async | Subprocess |
| Streaming | Async generator | Line-buffered |

!!! note "When to use CLI backend"
    The CLI backend is maintained for compatibility and simpler deployments. Use it when you don't need hooks, custom tools, or session support.
