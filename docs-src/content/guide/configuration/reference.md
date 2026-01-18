# Configuration Reference

This page provides complete documentation for all Cub configuration options.

## Harness Configuration

Controls which AI harness (Claude Code, Codex, etc.) is used to execute tasks.

### `harness.default`

The default harness to use for task execution.

| Property | Value |
|----------|-------|
| **Type** | `string` |
| **Default** | `"auto"` |
| **Allowed Values** | `auto`, `claude`, `codex`, `gemini`, `opencode` |
| **CLI Flag** | `--harness <name>` |
| **Environment Variable** | `HARNESS` |

When set to `auto`, Cub attempts harnesses in priority order and uses the first one that is available.

### `harness.priority`

Order to try harnesses when using `auto` mode.

| Property | Value |
|----------|-------|
| **Type** | `array` of `string` |
| **Default** | `["claude", "gemini", "codex", "opencode"]` |

The first available harness in the list is used. This allows you to prefer certain harnesses while having fallbacks.

!!! example "Configuration Examples"

    === "Force Claude"

        ```json
        {
          "harness": {
            "default": "claude"
          }
        }
        ```

    === "Prefer Gemini with Fallback"

        ```json
        {
          "harness": {
            "default": "auto",
            "priority": ["gemini", "claude", "codex"]
          }
        }
        ```

    === "CLI Override"

        ```bash
        cub run --harness claude
        ```

---

## Budget Configuration

Manage token budget to control AI API costs.

### `budget.default`

Token budget limit per session.

| Property | Value |
|----------|-------|
| **Type** | `number` |
| **Default** | `1000000` (1 million tokens) |
| **CLI Flag** | `--budget <tokens>` |
| **Environment Variable** | `CUB_BUDGET` |

The execution loop exits when the budget is exceeded. This prevents runaway costs.

### `budget.warn_at`

Warning threshold as a percentage of budget.

| Property | Value |
|----------|-------|
| **Type** | `number` (0.0-1.0) |
| **Default** | `0.8` (80%) |

When token usage reaches this percentage of the budget, a warning is logged. This gives you advance notice before hitting the limit.

!!! example "Configuration Examples"

    === "Low Budget for Testing"

        ```json
        {
          "budget": {
            "default": 100000,
            "warn_at": 0.9
          }
        }
        ```

    === "High Budget with Early Warning"

        ```json
        {
          "budget": {
            "default": 5000000,
            "warn_at": 0.7
          }
        }
        ```

    === "Environment Override"

        ```bash
        export CUB_BUDGET=200000
        cub run
        ```

!!! tip "Monitoring Budget Usage"

    Track token usage from logs:

    ```bash
    # View budget warnings
    jq 'select(.event_type=="budget_warning")' ~/.local/share/cub/logs/myproject/*.jsonl

    # Calculate total tokens used
    jq -s '[.[].data.tokens_used // 0] | add' ~/.local/share/cub/logs/myproject/*.jsonl
    ```

---

## Loop Configuration

Control the main execution loop behavior.

### `loop.max_iterations`

Maximum number of iterations before the loop exits.

| Property | Value |
|----------|-------|
| **Type** | `number` |
| **Default** | `100` |
| **CLI Flag** | `--max-iterations <num>` |
| **Environment Variable** | `CUB_MAX_ITERATIONS` |

This prevents infinite loops and provides a hard stop for long-running sessions. Each task attempt counts as one iteration.

!!! example "Configuration Examples"

    === "Quick Test"

        ```bash
        cub run --max-iterations 5 --once
        ```

    === "Extended Session"

        ```json
        {
          "loop": {
            "max_iterations": 200
          }
        }
        ```

---

## Clean State Configuration

Enforce code quality and consistency checks between task executions.

### `clean_state.require_commit`

Enforce git commits after harness completes a task.

| Property | Value |
|----------|-------|
| **Type** | `boolean` |
| **Default** | `true` |
| **CLI Flags** | `--require-clean`, `--no-require-clean` |
| **Environment Variable** | `CUB_REQUIRE_CLEAN` |

When enabled, Cub verifies that all changes are committed after each task. This ensures a clean state between tasks.

### `clean_state.require_tests`

Enforce test passage before allowing commits.

| Property | Value |
|----------|-------|
| **Type** | `boolean` |
| **Default** | `false` |

When enabled, tasks must pass all tests before the clean state check succeeds. This ensures code quality at each step.

### `clean_state.auto_commit`

Automatically commit remaining changes when the harness completes successfully.

| Property | Value |
|----------|-------|
| **Type** | `boolean` |
| **Default** | `true` |

When the harness exits with code 0 but forgets to commit, this setting allows Cub to commit the remaining changes automatically. This prevents task failures due to uncommitted changes when the work is actually complete.

!!! note
    Session files (`progress.txt`, `fix_plan.md`) are always auto-committed regardless of this setting.

!!! example "Configuration Examples"

    === "Development (Relaxed)"

        ```json
        {
          "clean_state": {
            "require_commit": false,
            "require_tests": false
          }
        }
        ```

    === "Production (Strict)"

        ```json
        {
          "clean_state": {
            "require_commit": true,
            "require_tests": true,
            "auto_commit": false
          }
        }
        ```

    === "CLI Override"

        ```bash
        cub run --no-require-clean
        ```

---

## Task Configuration

Control task lifecycle behavior.

### `task.auto_close`

Automatically close tasks when the harness completes successfully.

| Property | Value |
|----------|-------|
| **Type** | `boolean` |
| **Default** | `true` |
| **Environment Variable** | `CUB_AUTO_CLOSE` |

When the harness exits with code 0 but the agent forgets to close the task, this setting allows Cub to close it automatically. This prevents tasks from getting stuck in "in_progress" state.

!!! note "Backend Behavior"
    - **Beads backend**: Auto-close runs `bd close <task-id>`
    - **JSON backend**: Auto-close updates the task status to "closed" in `prd.json`

!!! example "Configuration Examples"

    === "Default (Auto-close Enabled)"

        ```json
        {
          "task": {
            "auto_close": true
          }
        }
        ```

    === "Require Explicit Close"

        ```json
        {
          "task": {
            "auto_close": false
          }
        }
        ```

---

## Hooks Configuration

Control the hook system for task lifecycle events.

### `hooks.enabled`

Enable or disable all hooks.

| Property | Value |
|----------|-------|
| **Type** | `boolean` |
| **Default** | `true` |

### `hooks.fail_fast`

Stop the loop if a hook fails.

| Property | Value |
|----------|-------|
| **Type** | `boolean` |
| **Default** | `false` |

When enabled, a hook failure (non-zero exit code) stops the entire run. When disabled, hook failures are logged but execution continues.

### `hooks.async_notifications`

Run `post-task` and `on-error` hooks asynchronously (non-blocking).

| Property | Value |
|----------|-------|
| **Type** | `boolean` |
| **Default** | `true` |

When enabled, notification hooks (`post-task`, `on-error`, `on-budget-warning`, `on-all-tasks-complete`) fire in the background so they don't slow down the main loop. All async hooks are collected before the session ends. Set to `false` to run all hooks synchronously.

!!! example "Configuration Examples"

    === "Disable Hooks for Testing"

        ```json
        {
          "hooks": {
            "enabled": false
          }
        }
        ```

    === "Strict Mode"

        ```json
        {
          "hooks": {
            "enabled": true,
            "fail_fast": true
          }
        }
        ```

    === "Synchronous Hooks"

        ```json
        {
          "hooks": {
            "enabled": true,
            "async_notifications": false
          }
        }
        ```

See the [Hooks System Guide](../hooks/index.md) for details on writing custom hooks.

---

## Guardrails Configuration

Prevent runaway loops and redact sensitive information from output.

### `guardrails.max_task_iterations`

Maximum attempts for a single task.

| Property | Value |
|----------|-------|
| **Type** | `number` |
| **Default** | `3` |
| **Environment Variable** | `CUB_MAX_TASK_ITERATIONS` |

When exceeded, the task is marked as failed and skipped. This prevents infinite retry loops on problematic tasks.

### `guardrails.max_run_iterations`

Maximum total iterations in a run.

| Property | Value |
|----------|-------|
| **Type** | `number` |
| **Default** | `50` |
| **Environment Variable** | `CUB_MAX_RUN_ITERATIONS` |

When exceeded, the run stops immediately. This prevents runaway loop behavior across all tasks.

### `guardrails.iteration_warning_threshold`

Warning threshold as a percentage of iteration limit.

| Property | Value |
|----------|-------|
| **Type** | `number` (0.0-1.0) |
| **Default** | `0.8` (80%) |

Logs a warning when approaching `max_task_iterations` or `max_run_iterations`.

### `guardrails.secret_patterns`

Regular expression patterns to detect and redact sensitive information.

| Property | Value |
|----------|-------|
| **Type** | `array` of `string` (regex patterns) |
| **Default** | `["api[_-]?key", "password", "token", "secret", "authorization", "credentials"]` |

Patterns are matched case-insensitively against log output. Matched values are redacted to prevent accidental exposure.

!!! example "Configuration Examples"

    === "Strict Limits for Testing"

        ```json
        {
          "guardrails": {
            "max_task_iterations": 2,
            "max_run_iterations": 10,
            "iteration_warning_threshold": 0.5
          }
        }
        ```

    === "Custom Secret Patterns"

        ```json
        {
          "guardrails": {
            "secret_patterns": [
              "api[_-]?key",
              "password",
              "token",
              "secret",
              "authorization",
              "credentials",
              "webhook_url",
              "private_key",
              "aws_secret"
            ]
          }
        }
        ```

    === "Relaxed Limits for Complex Tasks"

        ```bash
        export CUB_MAX_TASK_ITERATIONS=10
        export CUB_MAX_RUN_ITERATIONS=200
        cub run
        ```

---

## Complete Configuration Schema

Here is the complete JSON schema for `.cub.json`:

```json
{
  "harness": {
    "default": "auto",
    "priority": ["claude", "gemini", "codex", "opencode"]
  },
  "budget": {
    "default": 1000000,
    "warn_at": 0.8
  },
  "loop": {
    "max_iterations": 100
  },
  "clean_state": {
    "require_commit": true,
    "require_tests": false,
    "auto_commit": true
  },
  "task": {
    "auto_close": true
  },
  "hooks": {
    "enabled": true,
    "fail_fast": false
  },
  "guardrails": {
    "max_task_iterations": 3,
    "max_run_iterations": 50,
    "iteration_warning_threshold": 0.8,
    "secret_patterns": [
      "api[_-]?key",
      "password",
      "token",
      "secret",
      "authorization",
      "credentials"
    ]
  }
}
```

---

## Debugging Configuration

### View Merged Configuration

Check what configuration Cub is actually using:

```bash
# Show debug output including config
cub run --debug --once 2>&1 | grep -i config

# View global config
cat ~/.config/cub/config.json | jq .

# View project config
cat .cub.json | jq .
```

### Validate Configuration

Ensure your JSON is valid before using:

```bash
# Validate global config
jq empty ~/.config/cub/config.json && echo "Valid"

# Validate project config
jq empty .cub.json && echo "Valid"
```

### Common Issues

??? question "Config file not found"
    Run `cub init --global` to create global config, or create `.cub.json` in your project.

??? question "Budget exceeded but tasks remaining"
    - Increase `budget.default` in config or via `CUB_BUDGET`
    - Check token usage in logs
    - Reduce `budget.warn_at` for earlier warnings

??? question "Wrong harness selected"
    - Check `harness.priority` in config
    - Use `--harness <name>` to force specific harness
    - Verify harness is installed: `which claude`

??? question "Tasks not running"
    - Check `loop.max_iterations` - may have hit limit
    - Use `cub status --ready` to see available tasks
    - Check `--epic` and `--label` filters
