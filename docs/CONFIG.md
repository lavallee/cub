# Cub Configuration Guide

This guide covers all cub configuration options, how to set them, and what they control.

## Configuration Precedence

Cub loads configuration from multiple sources with the following precedence (highest to lowest):

1. **Environment variables** - Runtime overrides (e.g., `CUB_BUDGET=100`)
2. **Project config** - `.cub.json` in project root
3. **User config** - `~/.config/cub/config.json` (or `$XDG_CONFIG_HOME/cub/config.json`)
4. **Hardcoded defaults** - Built-in values for all settings

This allows you to set global defaults in your user config and override them per-project or per-run.

## Configuration Files

### Project Configuration (.cub.json)

Located in your project root:

```json
{
  "circuit_breaker": {
    "enabled": true,
    "timeout_minutes": 30
  },
  "budget": {
    "max_total_cost": 50.0
  },
  "guardrails": {
    "max_task_iterations": 3,
    "max_run_iterations": 50
  }
}
```

### User Configuration (~/.config/cub/config.json)

Located in your XDG config directory (default: `~/.config/cub/config.json`):

```json
{
  "harness": {
    "name": "claude",
    "model": "sonnet"
  },
  "circuit_breaker": {
    "enabled": true,
    "timeout_minutes": 30
  }
}
```

## Configuration Sections

### Circuit Breaker Configuration

Controls automatic termination when the harness becomes unresponsive for extended periods.

**Configuration:**

```json
{
  "circuit_breaker": {
    "enabled": true,
    "timeout_minutes": 30
  }
}
```

**Fields:**

- `enabled` (boolean, default: `true`)
  - Enable/disable circuit breaker stagnation detection
  - When enabled, cub will stop if no harness activity is detected for `timeout_minutes`
  - Set to `false` to disable (useful for testing or long-running tasks)

- `timeout_minutes` (integer, default: `30`, min: `1`)
  - Minutes of inactivity before circuit breaker trips
  - Reasonable values: 15 (tight monitoring) to 60+ (for slow tasks)
  - Must be >= 1 (validation enforced)

**Environment Variables:**

- `CUB_CIRCUIT_BREAKER_ENABLED` - Set to `true`/`false` to override config
- `CUB_CIRCUIT_BREAKER_TIMEOUT` - Set to number of minutes

**Examples:**

```bash
# Disable circuit breaker for this run
export CUB_CIRCUIT_BREAKER_ENABLED=false
cub run

# Set 60-minute timeout
export CUB_CIRCUIT_BREAKER_TIMEOUT=60
cub run

# Both together
export CUB_CIRCUIT_BREAKER_ENABLED=true
export CUB_CIRCUIT_BREAKER_TIMEOUT=45
cub run --harness claude
```

### Budget Configuration

Controls token and cost limits for autonomous sessions.

**Configuration:**

```json
{
  "budget": {
    "max_tokens_per_task": 500000,
    "max_tasks_per_session": 20,
    "max_total_cost": 100.0,
    "default": 5000
  }
}
```

**Fields:**

- `max_tokens_per_task` (integer, optional)
  - Stop if a single task uses more than this many tokens
  - Useful for detecting runaway tasks

- `max_tasks_per_session` (integer, optional)
  - Stop after completing this many tasks in one session
  - Useful for limiting batch runs

- `max_total_cost` (float, optional)
  - Stop if total spend exceeds this amount (in USD)
  - Prevents runaway costs

- `default` (integer, optional)
  - Default budget if not specified (for backward compatibility)

**Environment Variables:**

- `CUB_BUDGET` - Set total budget for session

### Guardrails Configuration

Safety limits that prevent runaway costs and infinite loops.

**Configuration:**

```json
{
  "guardrails": {
    "max_task_iterations": 3,
    "max_run_iterations": 50,
    "iteration_warning_threshold": 0.8,
    "secret_patterns": ["api_key", "password", "token"]
  }
}
```

**Fields:**

- `max_task_iterations` (integer, default: `3`)
  - Maximum iterations per task before failing

- `max_run_iterations` (integer, default: `50`)
  - Maximum total iterations before stopping the run

- `iteration_warning_threshold` (float, default: `0.8`, range: 0.0-1.0)
  - Warn when iterations reach this fraction of max (0.0-1.0)
  - 0.8 means warn at 80% of max_run_iterations

- `secret_patterns` (list of strings)
  - Regex patterns for detecting secrets in code
  - Default patterns: api_key, password, token, secret, authorization, credentials

### State Configuration

Pre-flight checks before running tasks.

**Configuration:**

```json
{
  "state": {
    "require_clean": true,
    "run_tests": false,
    "run_typecheck": false,
    "run_lint": false
  }
}
```

**Fields:**

- `require_clean` (boolean, default: `true`)
  - Fail if git has uncommitted changes

- `run_tests` (boolean, default: `false`)
  - Run tests and fail if they don't pass

- `run_typecheck` (boolean, default: `false`)
  - Run type checker and fail if there are errors

- `run_lint` (boolean, default: `false`)
  - Run linter and fail if there are issues

### Loop Configuration

Controls autonomous loop behavior.

**Configuration:**

```json
{
  "loop": {
    "max_iterations": 100,
    "on_task_failure": "stop"
  }
}
```

**Fields:**

- `max_iterations` (integer, default: `100`)
  - Stop after N iterations (prevents infinite loops)

- `on_task_failure` (string, default: `"stop"`)
  - What to do when a task fails: `"stop"` or `"continue"`

### Harness Configuration

Specifies which AI assistant to use.

**Configuration:**

```json
{
  "harness": {
    "name": "claude",
    "priority": ["claude", "codex"],
    "model": "sonnet"
  }
}
```

**Fields:**

- `name` (string, optional)
  - Harness name: `"claude"`, `"codex"`, `"gemini"`, `"opencode"`, etc.
  - If not specified, auto-detects based on availability

- `priority` (list of strings, default: `["claude", "codex"]`)
  - Auto-detection priority order

- `model` (string, optional)
  - Specific model to use (e.g., `"sonnet"`, `"haiku"`, `"opus"`)

### Other Configuration Sections

- **Hooks** - Lifecycle hooks configuration
- **Interview** - Task interview questions
- **Review** - Task and plan review settings
- **Cleanup** - Post-run cleanup settings
- **Ledger** - Task completion tracking
- **Sync** - Task state synchronization
- **Backend** - Task backend selection

See `.cub/agent.md` in the cub repository for comprehensive documentation on all settings.

## Setting Configuration

### Method 1: Project Config File

Create `.cub.json` in your project root:

```bash
cat > .cub.json << 'EOF'
{
  "circuit_breaker": {
    "enabled": true,
    "timeout_minutes": 30
  },
  "budget": {
    "max_total_cost": 100.0
  }
}
EOF
```

### Method 2: Environment Variables

Set environment variables before running cub:

```bash
export CUB_CIRCUIT_BREAKER_ENABLED=true
export CUB_CIRCUIT_BREAKER_TIMEOUT=45
export CUB_BUDGET=200
cub run
```

### Method 3: User Global Config

Set defaults for all projects:

```bash
mkdir -p ~/.config/cub
cat > ~/.config/cub/config.json << 'EOF'
{
  "harness": {
    "name": "claude",
    "model": "sonnet"
  },
  "circuit_breaker": {
    "enabled": true,
    "timeout_minutes": 30
  }
}
EOF
```

### Method 4: CLI Flags

Some commands support CLI flags that override config:

```bash
cub run --budget 500 --no-clean-check
```

## Configuration Examples

### Tight Monitoring (Development)

For development and testing, use tight monitoring with frequent checks:

```json
{
  "circuit_breaker": {
    "enabled": true,
    "timeout_minutes": 15
  },
  "guardrails": {
    "max_run_iterations": 10,
    "max_task_iterations": 2
  }
}
```

### Cost-Controlled Batch (Production)

For production batch runs with cost controls:

```json
{
  "circuit_breaker": {
    "enabled": true,
    "timeout_minutes": 60
  },
  "budget": {
    "max_total_cost": 50.0,
    "max_tasks_per_session": 100
  },
  "guardrails": {
    "max_run_iterations": 100,
    "max_task_iterations": 3
  }
}
```

### Overnight Run (High Availability)

For long-running overnight sessions:

```json
{
  "circuit_breaker": {
    "enabled": true,
    "timeout_minutes": 120
  },
  "state": {
    "require_clean": true,
    "run_tests": true
  },
  "loop": {
    "max_iterations": 500
  }
}
```

## Environment Variable Reference

### Circuit Breaker

- `CUB_CIRCUIT_BREAKER_ENABLED` - `true` or `false`
- `CUB_CIRCUIT_BREAKER_TIMEOUT` - number (minutes, >= 1)

### Budget

- `CUB_BUDGET` - number (integer, token budget or cost limit)

### Review

- `CUB_REVIEW_STRICT` - `true` or `false`

### XDG Directories

- `XDG_CONFIG_HOME` - override config directory (default: `~/.config`)

## Troubleshooting

### "Warning: Invalid CUB_CIRCUIT_BREAKER_TIMEOUT value"

The circuit breaker timeout must be a valid integer >= 1:

```bash
# Bad: Not a number
export CUB_CIRCUIT_BREAKER_TIMEOUT=very-long
cub run  # Warning printed

# Bad: Zero not allowed
export CUB_CIRCUIT_BREAKER_TIMEOUT=0
cub run  # Warning printed

# Good: Valid integer
export CUB_CIRCUIT_BREAKER_TIMEOUT=30
cub run
```

### "Warning: Failed to parse config at"

Check your JSON syntax:

```bash
# Validate JSON
python3 -m json.tool .cub.json

# Or with jq
jq . .cub.json
```

### Circuit Breaker Keeps Triggering

If the circuit breaker trips too frequently:

1. Increase `timeout_minutes` in config
2. Or disable with `CUB_CIRCUIT_BREAKER_ENABLED=false`
3. Check if the harness is actually responsive

### Configuration Not Applied

Remember the precedence chain:

1. Check environment variables first: `echo $CUB_*`
2. Check project config: `cat .cub.json`
3. Check user config: `cat ~/.config/cub/config.json`
4. Use `cub doctor` to diagnose config loading
