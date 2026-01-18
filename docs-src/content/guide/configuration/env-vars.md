# Environment Variables

Environment variables provide a flexible way to configure Cub without modifying config files. They are particularly useful for:

- **CI/CD pipelines**: Set configuration in your build environment
- **Session overrides**: Temporarily change settings without editing files
- **Secrets**: Pass sensitive values without storing them in config

## Quick Reference

All environment variables at a glance:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CUB_PROJECT_DIR` | String | `$(pwd)` | Project directory |
| `CUB_MODEL` | String | - | Claude model: `haiku`, `sonnet`, `opus` |
| `CUB_BUDGET` | Number | `1000000` | Token budget limit |
| `CUB_MAX_ITERATIONS` | Number | `100` | Max loop iterations |
| `CUB_DEBUG` | Boolean | `false` | Enable debug logging |
| `CUB_STREAM` | Boolean | `false` | Stream harness output |
| `CUB_BACKEND` | String | `auto` | Task backend: `auto`, `beads`, `json` |
| `CUB_EPIC` | String | - | Filter to epic ID |
| `CUB_LABEL` | String | - | Filter to label name |
| `CUB_REQUIRE_CLEAN` | Boolean | `true` | Enforce clean git state |
| `CUB_AUTO_CLOSE` | Boolean | `true` | Auto-close tasks on success |
| `CUB_MAX_TASK_ITERATIONS` | Number | `3` | Max attempts per task |
| `CUB_MAX_RUN_ITERATIONS` | Number | `50` | Max iterations per run |
| `HARNESS` | String | `auto` | Harness selection |
| `CLAUDE_FLAGS` | String | - | Extra flags for Claude Code CLI |
| `CODEX_FLAGS` | String | - | Extra flags for OpenAI Codex CLI |
| `GEMINI_FLAGS` | String | - | Extra flags for Gemini CLI |
| `OPENCODE_FLAGS` | String | - | Extra flags for OpenCode CLI |

---

## Core Settings

### `CUB_PROJECT_DIR`

Override the project directory.

| Property | Value |
|----------|-------|
| **Type** | String (path) |
| **Default** | Current working directory |

```bash
CUB_PROJECT_DIR=/path/to/project cub run
```

### `CUB_DEBUG`

Enable verbose debug logging.

| Property | Value |
|----------|-------|
| **Type** | Boolean (`true`/`false`, `1`/`0`) |
| **Default** | `false` |

```bash
CUB_DEBUG=true cub run
```

!!! tip
    Debug mode outputs detailed information about configuration loading, task selection, and harness execution.

### `CUB_STREAM`

Stream harness output in real-time.

| Property | Value |
|----------|-------|
| **Type** | Boolean |
| **Default** | `false` |

```bash
CUB_STREAM=true cub run
```

When enabled, you see the AI's output as it generates, rather than waiting for task completion.

---

## Budget & Limits

### `CUB_BUDGET`

Set the token budget for the session.

| Property | Value |
|----------|-------|
| **Type** | Number (positive integer) |
| **Default** | `1000000` |

```bash
# Small budget for testing
CUB_BUDGET=50000 cub run --once

# Large budget for production
CUB_BUDGET=5000000 cub run
```

### `CUB_MAX_ITERATIONS`

Set maximum loop iterations.

| Property | Value |
|----------|-------|
| **Type** | Number (positive integer) |
| **Default** | `100` |

```bash
CUB_MAX_ITERATIONS=20 cub run
```

### `CUB_MAX_TASK_ITERATIONS`

Set maximum attempts per task.

| Property | Value |
|----------|-------|
| **Type** | Number (positive integer) |
| **Default** | `3` |

```bash
# Allow more retries for complex tasks
CUB_MAX_TASK_ITERATIONS=5 cub run
```

### `CUB_MAX_RUN_ITERATIONS`

Set maximum total iterations per run.

| Property | Value |
|----------|-------|
| **Type** | Number (positive integer) |
| **Default** | `50` |

```bash
# Extended run with more iterations
CUB_MAX_RUN_ITERATIONS=200 cub run
```

---

## Task Selection

### `CUB_BACKEND`

Force a specific task backend.

| Property | Value |
|----------|-------|
| **Type** | String |
| **Default** | `auto` |
| **Allowed Values** | `auto`, `beads`, `json` |

```bash
# Force beads backend
CUB_BACKEND=beads cub run

# Force JSON backend (legacy)
CUB_BACKEND=json cub run
```

### `CUB_EPIC`

Filter tasks to a specific epic.

| Property | Value |
|----------|-------|
| **Type** | String (epic ID) |
| **Default** | - (no filter) |

```bash
CUB_EPIC=phase-1 cub run
```

### `CUB_LABEL`

Filter tasks to a specific label.

| Property | Value |
|----------|-------|
| **Type** | String (label name) |
| **Default** | - (no filter) |

```bash
CUB_LABEL=high-priority cub run
```

---

## Clean State

### `CUB_REQUIRE_CLEAN`

Enforce clean git state between tasks.

| Property | Value |
|----------|-------|
| **Type** | Boolean |
| **Default** | `true` |

```bash
# Skip clean state checks for development
CUB_REQUIRE_CLEAN=false cub run
```

### `CUB_AUTO_CLOSE`

Automatically close tasks on successful completion.

| Property | Value |
|----------|-------|
| **Type** | Boolean |
| **Default** | `true` |

```bash
# Require explicit task closure
CUB_AUTO_CLOSE=false cub run
```

---

## Harness Configuration

### `HARNESS`

Select which AI harness to use.

| Property | Value |
|----------|-------|
| **Type** | String |
| **Default** | `auto` |
| **Allowed Values** | `auto`, `claude`, `codex`, `gemini`, `opencode` |

```bash
HARNESS=claude cub run
```

### `CUB_MODEL`

Select Claude model variant.

| Property | Value |
|----------|-------|
| **Type** | String |
| **Default** | - |
| **Allowed Values** | `haiku`, `sonnet`, `opus` |

```bash
# Fast model for simple tasks
CUB_MODEL=haiku cub run

# Best model for complex tasks
CUB_MODEL=opus cub run
```

!!! note
    This variable only affects the Claude harness. Other harnesses have their own model selection mechanisms.

---

## Harness-Specific Flags

Pass additional flags to the underlying AI CLI tools.

### `CLAUDE_FLAGS`

Extra flags for Claude Code CLI.

```bash
CLAUDE_FLAGS="--verbose --max-tokens 4000" cub run --harness claude
```

### `CODEX_FLAGS`

Extra flags for OpenAI Codex CLI.

```bash
CODEX_FLAGS="--model gpt-4" cub run --harness codex
```

### `GEMINI_FLAGS`

Extra flags for Google Gemini CLI.

```bash
GEMINI_FLAGS="--temperature 0.7" cub run --harness gemini
```

### `OPENCODE_FLAGS`

Extra flags for OpenCode CLI.

```bash
OPENCODE_FLAGS="--context-size large" cub run --harness opencode
```

---

## Usage Patterns

### Development Testing

Quick testing with reduced limits:

```bash
export CUB_MODEL=haiku
export CUB_BUDGET=50000
export CUB_MAX_ITERATIONS=5
export CUB_REQUIRE_CLEAN=false
cub run --once
```

### Debugging

Full debug output with streaming:

```bash
CUB_DEBUG=true CUB_STREAM=true cub run --once
```

### CI/CD Pipeline

Deterministic execution for continuous integration:

```bash
export CUB_BUDGET=2000000
export CUB_MAX_ITERATIONS=50
export CUB_BACKEND=beads
export CUB_REQUIRE_CLEAN=true
export HARNESS=claude

cub run
```

### Epic-Focused Work

Target a specific epic with custom limits:

```bash
CUB_EPIC=phase-1 CUB_MAX_TASK_ITERATIONS=5 cub run
```

---

## Boolean Values

For boolean environment variables, Cub accepts:

| True Values | False Values |
|-------------|--------------|
| `true`, `1`, `yes`, `on` | `false`, `0`, `no`, `off` |

```bash
# All equivalent to true
CUB_DEBUG=true cub run
CUB_DEBUG=1 cub run
CUB_DEBUG=yes cub run

# All equivalent to false
CUB_DEBUG=false cub run
CUB_DEBUG=0 cub run
CUB_DEBUG=no cub run
```

---

## Precedence

Environment variables override config files but are overridden by CLI flags:

```
Defaults < Global Config < Project Config < Environment Variables < CLI Flags
```

Example:

```bash
# Config file says budget=1000000
# Environment says budget=500000
# CLI says --budget 200000
# Result: budget=200000 (CLI wins)
export CUB_BUDGET=500000
cub run --budget 200000  # Uses 200000
```
