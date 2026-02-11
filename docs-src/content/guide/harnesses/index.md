# AI Harnesses

Cub supports multiple AI coding CLI tools called **harnesses**. A harness is a wrapper around an AI coding assistant that provides a consistent interface for task execution, token tracking, and streaming output.

## What is a Harness?

A harness adapts an AI coding assistant's CLI to work with cub's autonomous loop. It handles:

- **Invocation**: Running the AI with system and task prompts
- **Streaming**: Real-time output as the AI generates responses
- **Token tracking**: Monitoring usage for budget management
- **Auto mode**: Enabling autonomous operation without user prompts
- **Hooks**: Event interception for guardrails and custom behavior (v0.24+)

## Supported Harnesses

| Harness | Name | CLI Binary | Documentation |
|---------|------|------------|---------------|
| [Claude Code (SDK)](claude.md) | `claude` | `claude` | [github.com/anthropics/claude-code](https://github.com/anthropics/claude-code) |
| [Claude Code (CLI)](claude.md#cli-backend) | `claude-cli` | `claude` | Shell-out mode for compatibility |
| [Codex](codex.md) | `codex` | `codex` | [github.com/openai/codex](https://github.com/openai/codex) |
| [Gemini](gemini.md) | `gemini` | `gemini` | [github.com/google/gemini-cli](https://github.com/google/gemini-cli) |
| [OpenCode](opencode.md) | `opencode` | `opencode` | [github.com/sst/opencode](https://github.com/sst/opencode) |

!!! note "Claude Code SDK vs CLI"
    The default `claude` harness uses the Claude Agent SDK for full hook support and better integration. Use `claude-cli` explicitly for the shell-out approach (simpler deployment, no SDK dependencies).

## Capability Matrix

Different harnesses have different features. Cub adapts its behavior based on what each harness supports.

| Capability | Claude (SDK) | Claude (CLI) | Codex | Gemini | OpenCode |
|------------|:------------:|:---------------:|:-----:|:------:|:--------:|
| **streaming** | :white_check_mark: | :white_check_mark: | :white_check_mark: | :x: | :white_check_mark: |
| **token_reporting** | :white_check_mark: | :white_check_mark: | :x: | :x:* | :white_check_mark: |
| **system_prompt** | :white_check_mark: | :white_check_mark: | :x: | :x: | :x: |
| **auto_mode** | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| **json_output** | :white_check_mark: | :white_check_mark: | :white_check_mark: | :x: | :white_check_mark: |
| **model_selection** | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :x: |
| **hooks** | :white_check_mark: | :x: | :x: | :x: | :x: |
| **custom_tools** | :white_check_mark: | :x: | :x: | :x: | :x: |
| **sessions** | :white_check_mark: | :x: | :x: | :x: | :x: |

*Gemini uses character-based estimation (~4 chars/token)

### Capability Descriptions

**streaming**
:   Real-time output streaming as the AI generates responses. When available, cub shows live progress with the `--stream` flag.

**token_reporting**
:   Accurate token usage reporting for budget tracking. When unavailable, cub estimates usage or skips budget tracking.

**system_prompt**
:   Support for a separate system prompt (keeps instructions distinct from the task). When unavailable, cub concatenates system and task prompts with a `---` separator.

**auto_mode**
:   Autonomous operation without user confirmation prompts. All harnesses must support this for unattended execution.

**json_output**
:   Structured JSON response format for programmatic parsing. Enables reliable token extraction and result parsing.

**model_selection**
:   Runtime model selection via CLI flag. Enables task labels like `model:haiku` to select specific models.

**hooks** (v0.24+)
:   Event interception for guardrails and custom behavior. Enables blocking dangerous commands, logging tool usage, and implementing circuit breakers. See [Hooks System](../hooks/index.md).

**custom_tools** (v0.24+)
:   Register custom tools that the AI can invoke. Enables extending the AI's capabilities with project-specific functionality.

**sessions** (v0.24+)
:   Stateful conversation sessions. Enables multi-turn interactions and context preservation across tool calls.

## Harness Selection

Cub selects a harness using this priority order:

1. **CLI flag**: `--harness claude`
2. **Environment variable**: `HARNESS=claude`
3. **Config priority array**: `harness.priority` in config file
4. **Default order**: claude > opencode > codex > gemini

### Auto-Detection

When no harness is specified, cub auto-detects by checking which CLI binaries are available on your system:

```bash
# Cub will use the first available harness
cub run --once
```

### Explicit Selection

Specify a harness explicitly for consistent behavior:

```bash
# Via CLI flag
cub run --harness claude

# Via environment variable
HARNESS=claude cub run
```

## Configuration

Configure harness behavior in `.cub/config.json` or your global config:

```json
{
  "harness": {
    "priority": ["claude", "opencode", "codex", "gemini"]
  }
}
```

Cub tries each harness in order until one is found installed.

### Per-Task Model Selection

Use task labels to select models for specific tasks:

```bash
# Add model label to a task
bd label <task-id> model:haiku
```

When cub runs a task with a `model:` label, it passes the model to the harness (if supported).

## How Cub Adapts

Cub adjusts its behavior based on harness capabilities:

| Scenario | Adaptation |
|----------|------------|
| No streaming | Output appears after completion instead of real-time |
| No token_reporting | Budget tracking uses estimates or is disabled |
| No system_prompt | System prompt concatenated with task prompt |
| No json_output | Raw text output parsed as-is |
| No model_selection | `model:` task labels are ignored |

## Querying Capabilities

### Python API

```python
from cub.core.harness import get_backend, get_capabilities

# Get current harness capabilities
backend = get_backend()
caps = backend.capabilities

if caps.streaming:
    print("Streaming available")

if caps.token_reporting:
    print("Accurate token tracking enabled")
```

### Shell (Bash Backend)

```bash
source lib/harness.sh

# Check if current harness supports a capability
if harness_supports "streaming"; then
    echo "Streaming available"
fi

# Get all capabilities as JSON
harness_get_capabilities_json
# {"harness":"claude","streaming":true,"token_reporting":true,...}
```

## Choosing a Harness

**Choose Claude Code (SDK) if:** (default, recommended)

- You need hooks for guardrails and circuit breakers
- You want custom tools and stateful sessions
- Budget tracking and streaming are important
- You want the most full-featured experience

**Choose Claude Code (Legacy) if:**

- You need the previous shell-out behavior
- You're troubleshooting SDK integration issues
- Your environment doesn't support the Claude Agent SDK

**Choose Codex if:**

- You prefer OpenAI models
- Streaming is important but token tracking is not critical

**Choose Gemini if:**

- You want to use Google's models
- Basic autonomous operation is sufficient

**Choose OpenCode if:**

- You need streaming and token tracking
- You don't need separate system prompts

---

## Symbiotic Workflow

When you work directly in a harness (e.g., opening Claude Code without `cub run`), Cub can still track your work through its **symbiotic workflow**. Lightweight hooks installed by `cub init` observe file writes, task commands, and git commits during direct sessions and feed them back into the ledger. This means the ledger stays complete whether you use `cub run` or work interactively.

When `cub run` invokes a harness, hooks are automatically disabled (via `CUB_RUN_ACTIVE`) to prevent double-tracking.

:material-arrow-right: [Hooks Guide](../hooks/index.md) for installation and configuration details.

---

## Async Harness Interface (v0.24+)

Starting in v0.24, all harnesses use an async interface internally. This enables:

- **Non-blocking execution**: Other tasks can run while waiting for AI responses
- **Better streaming**: True async generators for real-time output
- **Hook integration**: Hooks can intercept and modify behavior asynchronously

The async interface is transparent to users - `cub run` handles the async execution automatically.

### Python API

```python
from cub.core.harness import get_async_backend, detect_async_harness

# Auto-detect best available harness
harness_name = detect_async_harness()

# Get the async backend
backend = get_async_backend(harness_name)

# Check capabilities
if backend.supports_feature("hooks"):
    print("Hooks available for guardrails")

# Run a task (async)
async def run():
    result = await backend.run_task(task_input)
    print(f"Completed with {result.usage.total_tokens} tokens")
```
