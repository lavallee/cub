# Codex Harness

OpenAI Codex is a harness that wraps the OpenAI Codex CLI for autonomous coding. It provides streaming and model selection but lacks token reporting and system prompt support.

## Capabilities

| Capability | Status |
|------------|:------:|
| streaming | :white_check_mark: Supported |
| token_reporting | :x: Not supported (estimates only) |
| system_prompt | :x: Not supported |
| auto_mode | :white_check_mark: Supported |
| json_output | :white_check_mark: Supported |
| model_selection | :white_check_mark: Supported |

## Installation

Install the Codex CLI:

```bash
# Via npm
npm install -g @openai/codex

# Verify installation
codex --version
```

Ensure you have an OpenAI API key configured:

```bash
export OPENAI_API_KEY="your-key-here"
```

For detailed instructions, see the [Codex documentation](https://github.com/openai/codex).

## Features

### Streaming Output

Codex supports JSONL streaming output with `--json` flag, providing real-time visibility into:

- Commands being executed
- Files being edited
- Reasoning steps

### Model Selection

Select OpenAI models at runtime:

```bash
# Via task label
bd label <task-id> model:gpt-5.2-codex
```

### Auto Mode

Codex's `--dangerously-bypass-approvals-and-sandbox` flag enables fully autonomous operation without user prompts.

## Limitations

### No Separate System Prompt

Codex does not support a separate system prompt parameter. Cub combines the system prompt (from PROMPT.md) with the task prompt using a `---` separator:

```
<system prompt content>

---

<task prompt content>
```

### Token Estimation Only

Codex CLI does not report actual token usage. Cub estimates tokens based on character count (~4 characters per token). This means:

- Budget tracking is approximate
- `--budget` flags work but with estimated values
- Cost reporting is estimated

## Example Invocation

Here's how cub invokes Codex:

```bash
echo "$combined_prompt" | codex exec \
    --dangerously-bypass-approvals-and-sandbox \
    --json \
    -m gpt-5.2-codex \
    -
```

### Flags Used

| Flag | Purpose |
|------|---------|
| `exec` | Execute subcommand |
| `--dangerously-bypass-approvals-and-sandbox` | Enable auto mode |
| `--json` | JSONL output for streaming |
| `-m` | Model selection |
| `-` | Read prompt from stdin |

## Environment Variables

### CODEX_FLAGS

Pass additional flags to the Codex CLI:

```bash
export CODEX_FLAGS="--max-tokens 4000"
cub run --harness codex
```

### OPENAI_API_KEY

Required for Codex to authenticate with OpenAI:

```bash
export OPENAI_API_KEY="sk-..."
```

## Streaming Events

When streaming is enabled, Codex emits JSONL events:

```json
{"type": "item.started", "item": {"type": "command_execution", "command": "npm test"}}
{"type": "item.completed", "item": {"type": "reasoning", "text": "Running tests..."}}
{"type": "turn.completed", "usage": {"input_tokens": 500, "output_tokens": 200}}
```

Cub parses these events to display:

- Commands being run (prefixed with `$`)
- Files being edited (prefixed with `>`)
- Reasoning text

## Tips and Best Practices

### Use Streaming for Visibility

Since token reporting is estimated, streaming provides the best insight into what Codex is doing:

```bash
cub run --harness codex --stream
```

### Be Conservative with Budgets

Because token counts are estimated, set conservative budgets to avoid unexpected costs:

```bash
cub run --harness codex --budget 3.00
```

### Combine Prompts Carefully

Since system and task prompts are combined, ensure your PROMPT.md doesn't duplicate information that will be in task descriptions.

## Troubleshooting

### "codex: command not found"

Ensure Codex is installed and in your PATH:

```bash
which codex
npm install -g @openai/codex
```

### Authentication Errors

Verify your OpenAI API key is set:

```bash
echo $OPENAI_API_KEY
# Should show your key
```

### Unexpected Output

If Codex output seems garbled:

1. Ensure you're using `--json` flag (cub does this automatically)
2. Check for conflicting flags in `CODEX_FLAGS`
