# Audit Logging

Cub maintains detailed JSONL (JSON Lines) logs for every session, enabling debugging, performance analysis, cost tracking, and compliance reporting.

## JSONL Log Format

Each log file contains one JSON object per line:

```json
{"timestamp": "2026-01-17T10:30:00.123Z", "event_type": "task_start", "data": {"task_id": "cub-054", "task_title": "Add user caching"}}
{"timestamp": "2026-01-17T10:31:45.456Z", "event_type": "task_end", "data": {"task_id": "cub-054", "exit_code": 0, "duration_sec": 105.3, "tokens_used": 156892}}
```

### Why JSONL?

| Benefit | Description |
|---------|-------------|
| **Appendable** | New events append without rewriting |
| **Streamable** | Process line-by-line, no loading entire file |
| **Queryable** | Use jq for powerful queries |
| **Portable** | Standard format, works with many tools |

## Log Location

Logs are stored following XDG conventions:

```
~/.local/share/cub/logs/
    {project}/
        {session}.jsonl
```

Example paths:

```
~/.local/share/cub/logs/myproject/cub-20260117-103000.jsonl
~/.local/share/cub/logs/backend-api/cub-20260116-143022.jsonl
```

### Custom Log Location

Set via environment variable:

```bash
export XDG_DATA_HOME=/custom/path
# Logs at: /custom/path/cub/logs/
```

## Event Types

### task_start

Logged when a task begins execution:

```json
{
  "timestamp": "2026-01-17T10:30:00Z",
  "event_type": "task_start",
  "data": {
    "task_id": "cub-054",
    "task_title": "Add user caching",
    "harness": "claude"
  }
}
```

### task_end

Logged when a task completes:

```json
{
  "timestamp": "2026-01-17T10:31:45Z",
  "event_type": "task_end",
  "data": {
    "task_id": "cub-054",
    "exit_code": 0,
    "duration_sec": 105.3,
    "tokens_used": 156892,
    "budget_remaining": 343108,
    "budget_total": 500000
  }
}
```

### loop_start

Logged at the start of each iteration:

```json
{
  "timestamp": "2026-01-17T10:30:00Z",
  "event_type": "loop_start",
  "data": {
    "iteration": 1
  }
}
```

### loop_end

Logged at the end of each iteration:

```json
{
  "timestamp": "2026-01-17T10:32:00Z",
  "event_type": "loop_end",
  "data": {
    "iteration": 1,
    "tasks_processed": 1,
    "duration_sec": 120.5
  }
}
```

### budget_warning

Logged when approaching budget limits:

```json
{
  "timestamp": "2026-01-17T11:30:00Z",
  "event_type": "budget_warning",
  "data": {
    "remaining": 100000,
    "threshold": 400000,
    "total": 500000,
    "percentage_remaining": 20.0
  }
}
```

### error

Logged on errors:

```json
{
  "timestamp": "2026-01-17T10:35:00Z",
  "event_type": "error",
  "data": {
    "message": "Task execution failed: tests not passing",
    "context": {
      "task_id": "cub-055",
      "exit_code": 1
    }
  }
}
```

## Querying Logs with jq

### Basic Queries

```bash
# Pretty print all events
cat session.jsonl | jq .

# Filter by event type
cat session.jsonl | jq 'select(.event_type == "task_end")'

# Get specific fields
cat session.jsonl | jq '{time: .timestamp, task: .data.task_id}'
```

### Task Analysis

```bash
# List all completed tasks
cat session.jsonl | jq -r 'select(.event_type == "task_end") | .data.task_id'

# Find failed tasks
cat session.jsonl | jq 'select(.event_type == "task_end" and .data.exit_code != 0)'

# Task durations
cat session.jsonl | jq 'select(.event_type == "task_end") | {task: .data.task_id, duration: .data.duration_sec}'
```

### Token Analysis

```bash
# Total tokens used
cat session.jsonl | jq -s '[.[] | select(.event_type == "task_end") | .data.tokens_used] | add'

# Tokens per task
cat session.jsonl | jq 'select(.event_type == "task_end") | {task: .data.task_id, tokens: .data.tokens_used}'

# Most expensive task
cat session.jsonl | jq -s '[.[] | select(.event_type == "task_end")] | sort_by(-.data.tokens_used) | .[0]'
```

### Duration Analysis

```bash
# Average task duration
cat session.jsonl | jq -s '[.[] | select(.event_type == "task_end") | .data.duration_sec] | add / length'

# Slow tasks (>60 seconds)
cat session.jsonl | jq 'select(.event_type == "task_end" and .data.duration_sec > 60)'

# Total session time
cat session.jsonl | jq -s '[.[] | select(.event_type == "loop_end") | .data.duration_sec] | add'
```

### Error Analysis

```bash
# All errors
cat session.jsonl | jq 'select(.event_type == "error")'

# Error messages only
cat session.jsonl | jq -r 'select(.event_type == "error") | .data.message'

# Errors with context
cat session.jsonl | jq 'select(.event_type == "error") | {message: .data.message, context: .data.context}'
```

## Cross-Session Analysis

Query multiple sessions:

```bash
# All sessions for a project
cat ~/.local/share/cub/logs/myproject/*.jsonl | jq ...

# Recent sessions (last 7 days)
find ~/.local/share/cub/logs/myproject/ -mtime -7 -name "*.jsonl" -exec cat {} \; | jq ...

# Total tokens across all sessions
cat ~/.local/share/cub/logs/myproject/*.jsonl | \
  jq -s '[.[] | select(.event_type == "task_end") | .data.tokens_used // 0] | add'
```

## Log Retention

Cub does not automatically delete logs. Manage retention manually:

### Delete Old Logs

```bash
# Delete logs older than 30 days
find ~/.local/share/cub/logs/ -name "*.jsonl" -mtime +30 -delete
```

### Compress Old Logs

```bash
# Compress logs older than 7 days
find ~/.local/share/cub/logs/ -name "*.jsonl" -mtime +7 -exec gzip {} \;
```

### Archive to Cloud

```bash
# Sync to S3 (example)
aws s3 sync ~/.local/share/cub/logs/ s3://my-bucket/cub-logs/
```

## Status Files

In addition to JSONL logs, Cub writes status files for real-time monitoring:

```
.cub/runs/{session}/status.json
```

### Status File Contents

```json
{
  "run_id": "cub-20260117-103000",
  "session_name": "default",
  "phase": "running",
  "started_at": "2026-01-17T10:30:00Z",
  "current_task_id": "cub-054",
  "current_task_title": "Add user caching",
  "iteration": {
    "current": 3,
    "max": 50,
    "percentage": 6.0
  },
  "budget": {
    "tokens_used": 456892,
    "tokens_limit": 1000000,
    "cost_usd": 2.34,
    "tasks_completed": 2
  },
  "events": [
    {"timestamp": "2026-01-17T10:30:00Z", "level": "info", "message": "Run started"}
  ]
}
```

### Querying Status

```bash
# Current status
cat .cub/runs/*/status.json | jq .

# Most recent run
ls -t .cub/runs/*/status.json | head -1 | xargs cat | jq .
```

## Building Dashboards

Use logs to build monitoring dashboards:

### Simple Stats Script

```bash
#!/bin/bash
# cub-stats.sh - Generate session statistics

LOG_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/cub/logs"
PROJECT=${1:-$(basename $(pwd))}

echo "=== Cub Statistics for $PROJECT ==="
echo

# Total sessions
sessions=$(ls -1 "$LOG_DIR/$PROJECT"/*.jsonl 2>/dev/null | wc -l)
echo "Total sessions: $sessions"

# Total tasks completed
tasks=$(cat "$LOG_DIR/$PROJECT"/*.jsonl 2>/dev/null | \
  jq -s '[.[] | select(.event_type == "task_end" and .data.exit_code == 0)] | length')
echo "Tasks completed: $tasks"

# Total tokens
tokens=$(cat "$LOG_DIR/$PROJECT"/*.jsonl 2>/dev/null | \
  jq -s '[.[] | select(.event_type == "task_end") | .data.tokens_used // 0] | add')
echo "Total tokens: $tokens"

# Success rate
total_tasks=$(cat "$LOG_DIR/$PROJECT"/*.jsonl 2>/dev/null | \
  jq -s '[.[] | select(.event_type == "task_end")] | length')
if [ "$total_tasks" -gt 0 ]; then
  rate=$(echo "scale=1; $tasks * 100 / $total_tasks" | bc)
  echo "Success rate: ${rate}%"
fi
```

### Export to CSV

```bash
# Export task data to CSV
cat session.jsonl | \
  jq -r 'select(.event_type == "task_end") | [.timestamp, .data.task_id, .data.duration_sec, .data.tokens_used, .data.exit_code] | @csv' \
  > tasks.csv
```

## Compliance and Auditing

For compliance requirements:

### Immutable Logs

Write logs to append-only storage:

```bash
# Make logs append-only (Linux)
chattr +a ~/.local/share/cub/logs/myproject/*.jsonl
```

### Log Integrity

Hash logs for integrity verification:

```bash
# Generate checksums
sha256sum ~/.local/share/cub/logs/myproject/*.jsonl > checksums.txt

# Verify later
sha256sum -c checksums.txt
```

### Audit Trail

Logs provide complete audit trail:

- When tasks ran
- What harness was used
- How long tasks took
- Token consumption
- Errors encountered

## Troubleshooting with Logs

### Task Keeps Failing

```bash
# Find the task's attempts
cat *.jsonl | jq 'select(.data.task_id == "cub-054")'

# Check error messages
cat *.jsonl | jq 'select(.event_type == "error" and .data.context.task_id == "cub-054")'
```

### High Token Usage

```bash
# Find token-heavy tasks
cat *.jsonl | jq -s '[.[] | select(.event_type == "task_end")] | sort_by(-.data.tokens_used) | .[0:5]'
```

### Session Interrupted

```bash
# Check last events before interruption
cat session.jsonl | tail -20 | jq .
```
