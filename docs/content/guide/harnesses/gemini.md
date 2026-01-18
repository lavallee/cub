# Gemini Harness

Google Gemini is a basic harness that supports auto mode and model selection. It lacks streaming, JSON output, and accurate token reporting.

## Capabilities

| Capability | Status |
|------------|:------:|
| streaming | :x: Not supported |
| token_reporting | :x: Estimated only* |
| system_prompt | :x: Not supported |
| auto_mode | :white_check_mark: Supported |
| json_output | :x: Not supported |
| model_selection | :white_check_mark: Supported |

*Token usage is estimated from character count (~4 characters per token)

## Installation

Install the Gemini CLI:

```bash
# Via homebrew
brew install google/gemini-cli/gemini

# Verify installation
gemini --version
```

Ensure you have a Google API key configured:

```bash
export GOOGLE_API_KEY="your-key-here"
```

For detailed instructions, see the [Gemini CLI documentation](https://github.com/google/gemini-cli).

## Features

### Model Selection

Gemini supports model selection via the `-m` flag:

- `gemini-2.5-pro` - Most capable model
- `gemini-2.5-flash` - Faster, more cost-effective

Use task labels for per-task model selection:

```bash
bd label <task-id> model:gemini-2.5-flash
```

### Auto Mode (YOLO)

Gemini's `-y` flag enables YOLO mode for autonomous operation without confirmation prompts.

## Limitations

### No Streaming

Gemini CLI (homebrew version) does not support streaming output. All output appears after the task completes.

### No JSON Output

Output is plain text only. Cub parses the raw output as-is without structured data extraction.

### Token Estimation

Gemini CLI does not report actual token usage. Cub estimates tokens using a character-based formula:

```
estimated_tokens = character_count / 4
```

This estimation is marked in logs and budget tracking. Actual costs may vary.

### No Separate System Prompt

Gemini does not support a separate system prompt. Cub combines prompts with a `---` separator:

```
<system prompt content>

---

<task prompt content>
```

## Example Invocation

Here's how cub invokes Gemini:

```bash
echo "" | gemini -p "$combined_prompt" \
    -y \
    -m gemini-2.5-pro
```

### Flags Used

| Flag | Purpose |
|------|---------|
| `-p` | Prompt to execute |
| `-y` | YOLO mode (auto-approve) |
| `-m` | Model selection |

Note: The empty echo provides stdin input that Gemini requires.

## Environment Variables

### GEMINI_FLAGS

Pass additional flags to the Gemini CLI:

```bash
export GEMINI_FLAGS="--verbose"
cub run --harness gemini
```

### GOOGLE_API_KEY

Required for Gemini authentication:

```bash
export GOOGLE_API_KEY="AIza..."
```

## Tips and Best Practices

### Use for Simple Tasks

Gemini works well for straightforward tasks where streaming visibility isn't critical:

```bash
# Good for quick fixes
cub run --harness gemini --once
```

### Expect Batch Output

Since streaming isn't available, output appears all at once. For long-running tasks, consider a harness with streaming support.

### Budget Conservatively

Token estimates are approximate. Set conservative budgets:

```bash
cub run --harness gemini --budget 2.00
```

### Prefer Flash for Speed

For simple tasks, `gemini-2.5-flash` is faster and cheaper:

```bash
bd label <task-id> model:gemini-2.5-flash
```

## Troubleshooting

### "gemini: command not found"

Ensure Gemini CLI is installed:

```bash
brew install google/gemini-cli/gemini
```

Or check if it's in your PATH:

```bash
which gemini
```

### Authentication Errors

Verify your Google API key:

```bash
echo $GOOGLE_API_KEY
# Should show your key

# Test directly
gemini -p "Hello, world!" -y
```

### Slow Response Times

Gemini without streaming appears to "hang" during processing. This is normal - output appears after completion. For visibility, consider using Claude Code or Codex instead.

### Inaccurate Token Counts

Token estimates are approximations based on character count. For accurate budget tracking, use a harness with native token reporting (Claude Code or OpenCode).
