# Beads Backend

The **beads** backend is Cub's recommended task management system. It provides a full-featured CLI (`bd`) for creating, managing, and tracking tasks with support for dependencies, epics, labels, and git integration.

## What is Beads?

[Beads](https://github.com/steveyegge/beads) is a standalone task management CLI designed for AI-assisted development workflows. It stores tasks in a local `.beads/` directory using JSONL format for efficient querying and git-friendly diffs.

## Installation

=== "npm"

    ```bash
    npm install -g @beads/bd
    ```

=== "Homebrew"

    ```bash
    brew install steveyegge/beads/bd
    ```

=== "From Source"

    ```bash
    git clone https://github.com/steveyegge/beads.git
    cd beads
    npm install -g .
    ```

Verify installation:

```bash
bd --version
```

## Initialization

Initialize beads in your project:

```bash
cd your-project
bd init
```

This creates:

```
.beads/
+-- issues.jsonl    # Task database
+-- branches.yaml   # Branch-epic bindings
+-- config.yaml     # Beads configuration
```

!!! tip "Auto-Detection"
    Cub automatically detects and uses the beads backend when `.beads/` exists in your project.

## Common Commands

### Listing Tasks

```bash
# List all tasks
bd list

# Filter by status
bd list --status open
bd list --status in_progress
bd list --status closed

# Filter by parent epic
bd list --parent cub-epic-001

# Filter by label
bd list --label frontend

# JSON output for scripting
bd list --json
```

### Viewing Task Details

```bash
# Show full task details
bd show cub-042

# JSON output
bd show cub-042 --json
```

### Creating Tasks

```bash
# Basic task
bd create "Implement user authentication"

# With type and priority
bd create "Fix login timeout" --type bug --priority 1

# Short priority flag
bd create "Add dark mode" --type feature -p 2

# With parent epic
bd create "Add toggle component" --parent cub-epic-001

# With labels
bd create "Optimize queries" --labels "performance,database"
```

### Updating Tasks

```bash
# Change status
bd update cub-042 --status in_progress

# Change priority
bd update cub-042 --priority 1

# Add description
bd update cub-042 --description "Detailed requirements here..."

# Update assignee
bd update cub-042 --assignee "cub-session-001"
```

### Closing Tasks

```bash
# Close with reason
bd close cub-042 -r "Implemented with tests passing"

# Close without reason
bd close cub-042
```

!!! warning "Closing Tasks"
    When using cub, let the AI agent close tasks. The agent is instructed to run `bd close <task-id>` when work is complete.

### Managing Labels

```bash
# Add a label
bd label add cub-042 model:sonnet

# Remove a label
bd label remove cub-042 model:sonnet

# List labels on a task
bd show cub-042 --json | jq '.labels'
```

### Finding Ready Tasks

```bash
# List tasks ready to work on
bd ready

# Filter ready tasks by parent
bd ready --parent cub-epic-001

# Filter ready tasks by label
bd ready --label frontend

# JSON output
bd ready --json
```

A task is "ready" when:

- Status is `open`
- All dependencies (tasks in `blocks` field) are `closed`

## Dependencies

Beads uses a `blocks` field to express dependencies (the inverse of `dependsOn`).

```bash
# Task B depends on Task A
# (A must complete before B can start)
bd dep add cub-B cub-A --type blocks

# View dependencies
bd show cub-B --json | jq '.blocks'

# Remove dependency
bd dep remove cub-B cub-A
```

The relationship means: "Task B is blocked by Task A" or equivalently "Task A must be done before Task B can start."

See the [Dependencies guide](dependencies.md) for detailed examples.

## Epics and Hierarchy

Group related tasks under epics:

```bash
# Create an epic
bd create "User Management System" --type epic

# Create tasks under the epic
bd create "Add user model" --parent cub-epic-001
bd create "Add user API endpoints" --parent cub-epic-001
bd create "Add user UI components" --parent cub-epic-001

# List tasks in an epic
bd list --parent cub-epic-001
```

Run cub on a specific epic:

```bash
cub run --epic cub-epic-001
```

## Task Types

Beads supports these task types:

| Type | Purpose |
|------|---------|
| `task` | General work item (default) |
| `feature` | New functionality |
| `bug` | Defect to fix |
| `epic` | Container for related tasks |
| `gate` | Checkpoint requiring approval |

```bash
# Create with specific type
bd create "Add login page" --type feature
bd create "Fix timeout bug" --type bug
bd create "Q1 Features" --type epic
bd create "Security Review" --type gate
```

## Comments and Notes

Add notes to track progress:

```bash
# Add a comment
bd comment cub-042 "Started implementation, found edge case to handle"

# View comments
bd show cub-042 --json | jq '.comments'
```

## JSON Output

All commands support `--json` for machine-readable output:

```bash
# Parse with jq
bd list --json | jq '.[] | select(.priority <= 1)'

# Count open tasks
bd list --status open --json | jq 'length'

# Get task IDs only
bd list --json | jq '.[].id'
```

## Storage Format

Beads stores tasks in `.beads/issues.jsonl` (JSON Lines format):

```json
{"id":"cub-001","title":"Add authentication","status":"open","priority":2,"issue_type":"feature","labels":[],"blocks":[]}
{"id":"cub-002","title":"Fix login bug","status":"closed","priority":1,"issue_type":"bug","labels":["urgent"],"blocks":["cub-001"]}
```

Each line is a valid JSON object. This format:

- Is easy to version control (line-based diffs)
- Supports efficient append operations
- Can be processed with standard Unix tools

## Integration with Cub

### Agent Instructions

When cub runs a task with the beads backend, it includes these instructions for the AI:

```
This project uses the beads task backend. Use 'bd' commands for task management:
- bd close cub-042  - Mark this task complete
- bd show cub-042   - Check task status
- bd list           - See all tasks
```

### Environment Variable

Force beads backend regardless of auto-detection:

```bash
CUB_BACKEND=beads cub run
```

### Syncing with Git

Beads integrates with git for branch-epic bindings:

```bash
# Bind current branch to an epic
cub branch cub-epic-001

# List branch bindings
cub branches

# Sync status
bd sync
```

## Common Workflows

### Daily Development

```bash
# See what's ready
bd ready

# Check specific task
bd show cub-042

# Run cub on ready tasks
cub run --once
```

### Sprint Planning

```bash
# Create epic for sprint
bd create "Sprint 42: Authentication" --type epic

# Add tasks to epic
bd create "Design auth flow" --parent cub-sprint-42 -p 1
bd create "Implement JWT" --parent cub-sprint-42 -p 2
bd create "Add login UI" --parent cub-sprint-42 -p 2

# Set up dependencies
bd dep add cub-003 cub-002 --type blocks  # UI depends on JWT
bd dep add cub-002 cub-001 --type blocks  # JWT depends on design

# Run the sprint
cub run --epic cub-sprint-42
```

### Triaging Bugs

```bash
# Create bug
bd create "Users can't logout" --type bug -p 0 --labels "urgent,auth"

# Run high-priority bugs first
cub run --label urgent
```

## Troubleshooting

??? question "bd command not found"
    Ensure beads is installed and in your PATH:
    ```bash
    npm install -g @beads/bd
    which bd
    ```

??? question "No .beads directory"
    Initialize beads in your project:
    ```bash
    bd init
    ```

??? question "Cub not using beads backend"
    Check that `.beads/` exists and try forcing the backend:
    ```bash
    CUB_BACKEND=beads cub run
    ```

??? question "bd ready returns empty but tasks exist"
    Check for blocking dependencies:
    ```bash
    bd list --status open --json | jq '.[].blocks'
    ```
    Ensure blocking tasks are closed.

## Next Steps

<div class="grid cards" markdown>

-   :material-code-json: **[JSON Backend](json.md)**

    ---

    Alternative file-based storage without external tools.

-   :material-link-variant: **[Dependencies](dependencies.md)**

    ---

    Learn to chain tasks and manage execution order.

</div>
