# Hooks System

Cub provides a flexible hook system to extend functionality at key points in the task lifecycle. Hooks are executable scripts that run at specific moments, enabling integrations with external services, custom notifications, automated workflows, and more.

## What Are Hooks?

Hooks are scripts that execute at defined points during cub operation:

- **Scripts**: Any executable file (bash, Python, etc.)
- **Event-driven**: Triggered by lifecycle events
- **Context-aware**: Receive environment variables with relevant data
- **Composable**: Multiple hooks can run at each point

Common use cases:

- Send notifications to Slack when tasks complete
- Report metrics to monitoring systems
- Create git branches automatically at session start
- Trigger PagerDuty alerts on failures
- Generate reports at session end

## Hook Lifecycle

The following diagram shows when hooks execute during a typical cub session:

```
+-----------------------------------------------------+
|                   cub Start                         |
+---------------------------+-------------------------+
                            |
                            v
                     +--------------+
                     | pre-loop     |  (setup, initialization)
                     +--------------+
                            |
                            v
              +-------------------------+
              |   Main Loop Starts      |
              +------------+------------+
                           |
                    +------v--------+
                    | pre-task      |  (for each task)
                    +-------+-------+
                            |
                            v
                   +-----------------+
                   | Execute Task    |
                   |  (harness)      |
                   +--------+--------+
                            |
              +-------------+-------------+
              |                           |
              v                           v
         +----------+               +----------+
         | Success  |               | Failure  |
         +----+-----+               +----+-----+
              |                          |
              |                    +-----v------+
              |                    | on-error   |  (alert, logs)
              |                    +-----+------+
              |                          |
              +-------------+------------+
                            |
                            v
                    +---------------+
                    | post-task     |  (metrics, notify)
                    +-------+-------+
                            |
              +-------------+------------+
              |                          |
              v                          v
         +--------+              +-----------+
         | More   |              | All Done  |
         | Tasks? |              +-----+-----+
         +---+----+                    |
             | yes                     |
             v                         |
        (Loop Back)                    |
             |                         |
             +-------------------------+
                            |
                            v
                     +--------------+
                     | post-loop    |  (cleanup, reports)
                     +--------------+
                            |
                            v
                     +--------------+
                     |  Exit Loop   |
                     +--------------+
```

## Configuration

Hook behavior is controlled in your configuration file:

```json
{
  "hooks": {
    "enabled": true,
    "fail_fast": false
  }
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `true` | Enable or disable all hooks |
| `fail_fast` | `false` | Stop execution if a hook fails |

### Disabling Hooks

Temporarily disable hooks for testing:

```json
{
  "hooks": {
    "enabled": false
  }
}
```

Or via environment variable:

```bash
CUB_HOOKS_ENABLED=false cub run
```

### Fail Fast Mode

Enable strict mode where hook failures stop the loop:

```json
{
  "hooks": {
    "fail_fast": true
  }
}
```

By default, hook failures are logged but execution continues.

## Hook Locations

Hooks are discovered from two directories in order:

### 1. Global Hooks

Available to all projects on your system:

```
~/.config/cub/hooks/
+-- pre-loop.d/
+-- pre-task.d/
+-- post-task.d/
+-- on-error.d/
+-- post-loop.d/
```

### 2. Project Hooks

Specific to a single project:

```
.cub/hooks/
+-- pre-loop.d/
+-- pre-task.d/
+-- post-task.d/
+-- on-error.d/
+-- post-loop.d/
```

### Execution Order

1. All executable files in each `.d/` directory are discovered
2. Files are sorted alphabetically by name
3. Global hooks run first, then project hooks
4. Use numeric prefixes to control order: `01-first.sh`, `50-middle.sh`, `99-last.sh`

## Quick Start

### Installing an Example Hook

```bash
# Create hooks directory
mkdir -p .cub/hooks/post-task.d

# Copy example hook
cp examples/hooks/post-task/slack-notify.sh .cub/hooks/post-task.d/01-slack.sh

# Make executable
chmod +x .cub/hooks/post-task.d/01-slack.sh

# Set required environment variable
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Run cub - hook will execute after each task
cub run
```

### Writing a Simple Hook

Create `.cub/hooks/post-task.d/01-notify.sh`:

```bash
#!/usr/bin/env bash

# Access context via environment variables
echo "Task completed: $CUB_TASK_ID"
echo "Exit code: $CUB_EXIT_CODE"
echo "Project: $CUB_PROJECT_DIR"

# Exit 0 for success, non-zero for failure
exit 0
```

Make it executable:

```bash
chmod +x .cub/hooks/post-task.d/01-notify.sh
```

## Next Steps

<div class="grid cards" markdown>

-   :material-map-marker: **Hook Points**

    ---

    Detailed documentation of each hook point and when they execute.

    [:octicons-arrow-right-24: Hook Points](points.md)

-   :material-code-braces: **Context Variables**

    ---

    All environment variables available to hooks.

    [:octicons-arrow-right-24: Context Variables](context.md)

-   :material-file-document-edit: **Examples**

    ---

    Ready-to-use hook scripts for common integrations.

    [:octicons-arrow-right-24: Examples](examples.md)

</div>

## Built-in Example Hooks

Cub ships with example hooks for common integrations:

| Hook | Location | Description |
|------|----------|-------------|
| `10-auto-branch.sh` | `pre-loop.d/` | Automatically creates git branch at session start |
| `90-pr-prompt.sh` | `post-loop.d/` | Prompts to create GitHub PR at session end |
| `slack-notify.sh` | `post-task.d/` | Posts task completion to Slack |
| `datadog-metric.sh` | `post-loop.d/` | Reports metrics to Datadog |
| `pagerduty-alert.sh` | `on-error.d/` | Sends PagerDuty alerts on failure |

Find these in the `examples/hooks/` directory of your cub installation.
