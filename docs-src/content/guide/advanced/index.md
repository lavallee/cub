# Advanced Features

Cub includes powerful features for scaling autonomous coding sessions, ensuring safety through isolation, and maintaining detailed audit trails.

## Feature Overview

| Feature | Purpose | Use Case |
|---------|---------|----------|
| [Sandbox Mode](sandbox.md) | Docker-based isolation | Untrusted code, safe experimentation |
| [Parallel Execution](parallel.md) | Run multiple tasks simultaneously | Speed up independent tasks |
| [Captures](captures.md) | Quick idea capture | Notes, observations, future tasks |
| [Audit Logging](audit.md) | Detailed JSONL logs | Debugging, analytics, compliance |

## Quick Start

### Sandbox Mode

Run tasks in Docker containers for complete isolation:

```bash
# Basic sandbox execution
cub run --sandbox

# Sandbox without network access
cub run --sandbox --no-network

# Keep sandbox for inspection
cub run --sandbox --sandbox-keep
```

### Parallel Execution

Run multiple independent tasks at once:

```bash
# Run 3 tasks in parallel
cub run --parallel 3

# Each task runs in its own git worktree
```

### Captures

Quickly capture ideas without interrupting workflow:

```bash
# Capture an idea
cub capture "Add caching to user lookup"

# Capture with tags
cub capture "Refactor auth flow" --tag feature --tag auth

# Interactive capture with Claude
cub capture -i "New API endpoint needed"
```

### Audit Logging

Query detailed logs for debugging:

```bash
# Find slow tasks
cat ~/.local/share/cub/logs/myproject/*.jsonl | \
  jq 'select(.event_type == "task_end" and .data.duration_sec > 60)'

# Calculate total tokens
cat ~/.local/share/cub/logs/myproject/*.jsonl | \
  jq -s '[.[] | select(.event_type == "task_end") | .data.tokens_used] | add'
```

## When to Use Each Feature

### Use Sandbox Mode When

- Running untrusted or experimental code
- Testing destructive operations (file deletion, DB changes)
- Ensuring reproducible builds
- Preventing network side effects
- Isolating from production systems

### Use Parallel Execution When

- You have multiple independent tasks
- Tasks don't share dependencies
- You want to maximize throughput
- Working on different parts of the codebase

### Use Captures When

- You notice something that needs attention later
- Ideas come up during other work
- You want to log observations without context switching
- Building up a backlog of improvements

### Use Audit Logs When

- Debugging failed tasks
- Analyzing performance patterns
- Tracking costs over time
- Compliance requirements
- Building dashboards or reports

## Feature Comparison

```
                    Isolation   Speed   Persistence   Complexity
                    ---------   -----   -----------   ----------
Sandbox Mode        ****        **      ***           ***
Parallel Exec       **          ****    **            **
Captures            *           ****    ****          *
Audit Logging       *           ****    ****          **
```

## Combining Features

Features can be combined for powerful workflows:

### Parallel + Sandbox

```bash
# Run 3 sandboxed tasks in parallel
cub run --parallel 3 --sandbox
```

Each worker gets its own isolated container.

### Captures + Audit Logs

Use captures to note issues, then correlate with logs:

```bash
# Capture an observation
cub capture "Task cub-054 seems slow"

# Later, analyze logs
cat ~/.local/share/cub/logs/myproject/*.jsonl | \
  jq 'select(.data.task_id == "cub-054")'
```

## System Requirements

| Feature | Requirements |
|---------|--------------|
| Sandbox Mode | Docker Desktop or Docker Engine |
| Parallel Execution | Git, sufficient disk space for worktrees |
| Captures | None (uses filesystem) |
| Audit Logging | None (uses filesystem) |

## Next Steps

<div class="grid cards" markdown>

-   :material-docker: **Sandbox Mode**

    ---

    Complete isolation with Docker containers.

    [:octicons-arrow-right-24: Sandbox](sandbox.md)

-   :material-run-fast: **Parallel Execution**

    ---

    Run multiple tasks simultaneously.

    [:octicons-arrow-right-24: Parallel](parallel.md)

-   :material-lightbulb-outline: **Captures**

    ---

    Quick idea capture for future reference.

    [:octicons-arrow-right-24: Captures](captures.md)

-   :material-file-document-outline: **Audit Logging**

    ---

    Detailed JSONL logs for debugging.

    [:octicons-arrow-right-24: Audit Logging](audit.md)

</div>
