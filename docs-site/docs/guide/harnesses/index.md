# AI Harnesses

Cub supports multiple AI coding CLI tools called **harnesses**. A harness is a wrapper around an AI coding assistant that provides a consistent interface for task execution, token tracking, and streaming output.

## What is a Harness?

A harness adapts an AI coding assistant's CLI to work with cub's autonomous loop. It handles:

- **Invocation**: Running the AI with system and task prompts
- **Streaming**: Real-time output as the AI generates responses
- **Token tracking**: Monitoring usage for budget management
- **Auto mode**: Enabling autonomous operation without user prompts

## Supported Harnesses

| Harness | CLI Binary | Documentation |
|---------|------------|---------------|
| [Claude Code](claude.md) | `claude` | [github.com/anthropics/claude-code](https://github.com/anthropics/claude-code) |
| [Codex](codex.md) | `codex` | [github.com/openai/codex](https://github.com/openai/codex) |
| [Gemini](gemini.md) | `gemini` | [github.com/google/gemini-cli](https://github.com/google/gemini-cli) |
| [OpenCode](opencode.md) | `opencode` | [github.com/sst/opencode](https://github.com/sst/opencode) |

## Capability Matrix

Different harnesses have different features. Cub adapts its behavior based on what each harness supports.

| Capability | Claude Code | Codex | Gemini | OpenCode |
|------------|:-----------:|:-----:|:------:|:--------:|
| **streaming** | :white_check_mark: | :white_check_mark: | :x: | :white_check_mark: |
| **token_reporting** | :white_check_mark: | :x: | :x:* | :white_check_mark: |
| **system_prompt** | :white_check_mark: | :x: | :x: | :x: |
| **auto_mode** | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| **json_output** | :white_check_mark: | :white_check_mark: | :x: | :white_check_mark: |
| **model_selection** | :white_check_mark: | :white_check_mark: | :white_check_mark: | :x: |

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

Configure harness behavior in `.cub.json` or your global config:

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

**Choose Claude Code if:**

- You need all features (streaming, tokens, system prompts)
- Budget tracking is important
- You want model selection per task

**Choose Codex if:**

- You prefer OpenAI models
- Streaming is important but token tracking is not critical

**Choose Gemini if:**

- You want to use Google's models
- Basic autonomous operation is sufficient

**Choose OpenCode if:**

- You need streaming and token tracking
- You don't need separate system prompts
