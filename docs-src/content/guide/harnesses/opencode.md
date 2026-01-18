# OpenCode Harness

OpenCode is a harness that provides streaming and token tracking without separate system prompt support. It offers good observability for budget management.

## Capabilities

| Capability | Status |
|------------|:------:|
| streaming | :white_check_mark: Supported |
| token_reporting | :white_check_mark: Supported |
| system_prompt | :x: Not supported |
| auto_mode | :white_check_mark: Supported |
| json_output | :white_check_mark: Supported |
| model_selection | :x: Not supported (config only) |

## Installation

Install OpenCode from the official repository:

```bash
# Via npm
npm install -g opencode

# Or via your package manager
# See https://github.com/sst/opencode for options

# Verify installation
opencode --version
```

For detailed instructions, see the [OpenCode documentation](https://github.com/sst/opencode).

## Features

### Streaming Output

OpenCode supports real-time streaming via `--format json`, emitting JSON events with `step_finish` messages:

```bash
cub run --harness opencode --stream
```

### Token Tracking

OpenCode provides accurate token usage in its `step_finish` events:

```json
{
  "type": "step_finish",
  "part": {
    "tokens": {
      "input": 500,
      "output": 200
    }
  }
}
```

This enables precise budget tracking with cub's `--budget` flags.

### Auto Mode

OpenCode's `run` subcommand auto-approves all operations, enabling fully autonomous execution.

## Limitations

### No Separate System Prompt

OpenCode does not support a separate system prompt parameter. Cub combines prompts with a `---` separator:

```
<system prompt content>

---

<task prompt content>
```

### No Runtime Model Selection

Model selection is configured via project settings, not CLI flags. Task labels with `model:` are ignored for OpenCode.

To change models, update your OpenCode project configuration.

## Example Invocation

Here's how cub invokes OpenCode:

```bash
opencode run --format json "$combined_prompt"
```

### Flags Used

| Flag | Purpose |
|------|---------|
| `run` | Auto-approve subcommand |
| `--format json` | JSON output for streaming and parsing |

## Environment Variables

### OPENCODE_FLAGS

Pass additional flags to OpenCode:

```bash
export OPENCODE_FLAGS="--verbose"
cub run --harness opencode
```

## Token Usage

OpenCode reports token usage in streaming events:

```json
{
  "type": "step_finish",
  "part": {
    "tokens": {
      "input": 1500,
      "output": 800
    }
  }
}
```

Cub aggregates these across the session for:

- Budget tracking (`--budget`, `--iteration-budget`)
- Cost reporting in `cub status`
- Iteration summaries in logs

## Tips and Best Practices

### Good for Budget-Conscious Sessions

With accurate token reporting, OpenCode is a good choice when budget tracking is important:

```bash
cub run --harness opencode --budget 5.00
```

### Use Streaming for Monitoring

Enable streaming to see real-time progress:

```bash
cub run --harness opencode --stream
```

### Combine Prompts Carefully

Since system and task prompts are combined, structure your PROMPT.md to work well as a prefix to task descriptions.

### Configure Model in Project

Since model selection isn't available via CLI, configure your preferred model in OpenCode's project settings.

## Troubleshooting

### "opencode: command not found"

Ensure OpenCode is installed and in your PATH:

```bash
which opencode
npm install -g opencode
```

### No Token Data

If token usage shows zeros:

1. Ensure you're using `--format json` (cub does this automatically)
2. Check that the streaming output is being parsed correctly
3. Verify OpenCode version supports token reporting

### Combined Prompt Issues

If the AI seems confused by the combined system + task prompt:

1. Review PROMPT.md for content that might conflict with task descriptions
2. Consider simplifying system instructions
3. Add clear section markers in PROMPT.md

### Model Not Changing

Remember that OpenCode doesn't support CLI model selection. Task labels with `model:` are ignored. Update your OpenCode project configuration to change models.
