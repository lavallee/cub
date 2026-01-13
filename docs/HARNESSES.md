# Harness Reference

Cub supports multiple AI coding CLI tools ("harnesses"). This document describes the capabilities of each harness and how cub adapts its behavior accordingly.

## Capability Matrix

| Capability | Claude Code | OpenCode | Codex | Gemini |
|------------|:-----------:|:--------:|:-----:|:------:|
| **streaming** | Yes | Yes | No | No |
| **token_reporting** | Yes | Yes | No | No* |
| **system_prompt** | Yes | No | No | No |
| **auto_mode** | Yes | Yes | Yes | Yes |
| **json_output** | Yes | Yes | No | No |
| **model_selection** | Yes | No | No | Yes |

\* Gemini uses character-based estimation (~4 chars/token)

## Capabilities Explained

### streaming
Real-time output streaming as the AI generates responses.

| Harness | Implementation |
|---------|----------------|
| Claude Code | `--output-format stream-json` - JSON event stream with deltas |
| OpenCode | `--format json` - JSON events with `step_finish` messages |
| Codex | Not supported - output appears after completion |
| Gemini | Not supported - output appears after completion |

**How cub adapts:** When streaming is available, cub can show live progress with `--stream` flag. Without streaming, output appears only after task completion.

### token_reporting
Accurate token usage reporting for budget tracking.

| Harness | Implementation |
|---------|----------------|
| Claude Code | `.usage` object in JSON output with `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens` |
| OpenCode | `.part.tokens` in `step_finish` events |
| Codex | Not available |
| Gemini | Estimated from character count (~4 chars/token) |

**How cub adapts:** Budget tracking uses actual tokens when available, falls back to estimation otherwise. Estimated usage is marked in logs.

### system_prompt
Separate system prompt support (keeps system instructions distinct from task).

| Harness | Implementation |
|---------|----------------|
| Claude Code | `--append-system-prompt` flag |
| OpenCode | Combined into task prompt |
| Codex | Combined into task prompt |
| Gemini | Combined into task prompt |

**How cub adapts:** When `system_prompt` capability is missing, cub concatenates the system prompt (from PROMPT.md) with the task prompt, separated by `---`.

### auto_mode
Autonomous operation without user confirmation prompts.

| Harness | Implementation |
|---------|----------------|
| Claude Code | `--dangerously-skip-permissions` |
| OpenCode | `run` subcommand (auto-approves all) |
| Codex | `--full-auto` |
| Gemini | `-y` (YOLO mode) |

**How cub adapts:** All harnesses must support auto_mode for autonomous loop operation. This is the minimum required capability.

### json_output
Structured JSON response format for programmatic parsing.

| Harness | Implementation |
|---------|----------------|
| Claude Code | `--output-format json` or `--output-format stream-json` |
| OpenCode | `--format json` |
| Codex | Not available (plain text only) |
| Gemini | Not available (plain text only) |

**How cub adapts:** JSON output enables reliable token extraction and result parsing. Without it, cub uses the raw text output.

### model_selection
Runtime model selection via CLI flag.

| Harness | Implementation |
|---------|----------------|
| Claude Code | `--model <model>` (haiku, sonnet, opus, etc.) |
| OpenCode | Project configuration only |
| Codex | Not configurable via CLI |
| Gemini | `-m <model>` (gemini-2.5-pro, etc.) |

**How cub adapts:** Task labels like `model:haiku` only work with harnesses that support model_selection. For other harnesses, the label is ignored.

## Harness Details

### Claude Code

**Binary:** `claude`
**Documentation:** https://github.com/anthropics/claude-code

The most full-featured harness with all capabilities. Recommended for complex tasks.

```bash
# Example invocation
echo "$task" | claude -p \
    --append-system-prompt "$system" \
    --dangerously-skip-permissions \
    --output-format stream-json \
    --model sonnet
```

**Environment variables:**
- `CLAUDE_FLAGS` - Additional flags passed to claude

**Cub-specific:**
- `CUB_MODEL` - Model override (set via `model:X` task labels)

### OpenCode

**Binary:** `opencode`
**Documentation:** https://github.com/sst/opencode

Good streaming and token support, but no separate system prompt.

```bash
# Example invocation
opencode run --format json "$combined_prompt"
```

**Environment variables:**
- `OPENCODE_FLAGS` - Additional flags passed to opencode

**Notes:**
- Model configured via project settings, not CLI
- System prompt must be combined with task prompt

### Codex

**Binary:** `codex`
**Documentation:** https://github.com/openai/codex

Basic harness with auto mode only. Limited observability.

```bash
# Example invocation
echo "$combined_prompt" | codex exec --full-auto -
```

**Environment variables:**
- `CODEX_FLAGS` - Additional flags passed to codex

**Notes:**
- No token reporting - budget tracking unavailable
- No streaming - output appears only after completion
- System prompt must be combined with task prompt

### Gemini

**Binary:** `gemini`
**Documentation:** https://github.com/google/gemini-cli

Basic harness with auto mode and model selection.

```bash
# Example invocation
echo "" | gemini -p "$combined_prompt" -y -m gemini-2.5-pro
```

**Environment variables:**
- `GEMINI_FLAGS` - Additional flags passed to gemini

**Notes:**
- Token usage is estimated (~4 characters per token)
- Streaming not supported in v0.1.9 (homebrew version)
- System prompt must be combined with task prompt

## Querying Capabilities

### In Shell Scripts

```bash
source lib/harness.sh

# Check if current harness supports a capability
if harness_supports "streaming"; then
    echo "Streaming available"
fi

# Check for a specific harness
if harness_supports "token_reporting" "claude"; then
    echo "Claude reports tokens"
fi
```

### Get All Capabilities as JSON

```bash
source lib/harness.sh

# Current harness
harness_get_capabilities_json
# {"harness":"claude","streaming":true,"token_reporting":true,...}

# Specific harness
harness_get_capabilities_json "codex"
# {"harness":"codex","streaming":false,"token_reporting":false,...}
```

### Available Constants

```bash
HARNESS_CAP_STREAMING="streaming"
HARNESS_CAP_TOKEN_REPORTING="token_reporting"
HARNESS_CAP_SYSTEM_PROMPT="system_prompt"
HARNESS_CAP_AUTO_MODE="auto_mode"
HARNESS_CAP_JSON_OUTPUT="json_output"
HARNESS_CAP_MODEL_SELECTION="model_selection"
```

## Harness Selection

### Priority Order

Cub selects a harness using this priority:

1. **CLI flag:** `--harness claude`
2. **Environment variable:** `HARNESS=claude`
3. **Config priority array:** `harness.priority` in config
4. **Default order:** claude > opencode > codex > gemini

### Configuration

Set harness priority in `.cub.json` or global config:

```json
{
  "harness": {
    "priority": ["gemini", "claude", "codex", "opencode"]
  }
}
```

Cub tries each harness in order until one is found installed.

## Adding New Harnesses

To add support for a new AI coding CLI:

1. Add capability definition in `_harness_get_capabilities()`:
```bash
new_harness)
    echo "auto_mode streaming"  # List supported capabilities
    ;;
```

2. Implement invoke functions:
```bash
new_harness_invoke() { ... }
new_harness_invoke_streaming() { ... }
```

3. Add case to dispatcher functions:
```bash
harness_invoke() {
    case "$harness" in
        new_harness)
            new_harness_invoke "$system_prompt" "$task_prompt" "$debug"
            ;;
    esac
}
```

4. Update `harness_detect()` to find the new binary

5. Add to default priority in `_harness_detect_default_order()`

6. Update documentation and tests
