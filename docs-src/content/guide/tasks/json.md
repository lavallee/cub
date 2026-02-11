# JSON Backend

The **JSON backend** stores tasks in a single `prd.json` file. It requires no external tools and is ideal for quick experiments, small projects, or learning Cub.

## Overview

The JSON backend reads and writes tasks from `prd.json` in your project root. All operations are atomic (using temp files and rename) to prevent corruption.

## File Structure

A minimal `prd.json`:

```json
{
  "prefix": "myproj",
  "tasks": []
}
```

A complete example:

```json
{
  "projectName": "My Project",
  "prefix": "myproj",
  "tasks": [
    {
      "id": "myproj-001",
      "title": "Implement user authentication",
      "description": "Add JWT-based authentication with login and logout endpoints.",
      "status": "open",
      "priority": "P2",
      "type": "feature",
      "labels": ["backend", "auth"],
      "dependsOn": [],
      "acceptanceCriteria": [
        "Login endpoint returns JWT token",
        "Logout endpoint invalidates token",
        "All auth tests pass"
      ]
    },
    {
      "id": "myproj-002",
      "title": "Add login page UI",
      "description": "Create React login form component.",
      "status": "open",
      "priority": "P2",
      "type": "feature",
      "labels": ["frontend"],
      "dependsOn": ["myproj-001"]
    }
  ]
}
```

## Required Fields

Each task must have:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (format: `{prefix}-{number}`) |
| `title` | string | Brief task summary |

## Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | `""` | Detailed task description |
| `status` | string | `"open"` | `open`, `in_progress`, or `closed` |
| `priority` | string | `"P2"` | `P0` through `P4` |
| `type` | string | `"task"` | `task`, `feature`, `bug`, `epic`, `gate` |
| `labels` | array | `[]` | Tags for filtering |
| `dependsOn` | array | `[]` | Task IDs that must complete first |
| `parent` | string | `null` | Parent epic ID |
| `assignee` | string | `null` | Assigned session or user |
| `acceptanceCriteria` | array | `[]` | Completion conditions |
| `notes` | string | `""` | Additional comments |

## File Location

Cub looks for `prd.json` in the current directory. The file is created automatically with an empty tasks array if it doesn't exist when cub runs.

```
your-project/
+-- prd.json         # Task database
+-- .cub.json        # Cub configuration
+-- PROMPT.md        # System prompt
+-- ...
```

## Creating Tasks

### Manually

Edit `prd.json` directly:

```json
{
  "prefix": "myproj",
  "tasks": [
    {
      "id": "myproj-001",
      "title": "Add new feature",
      "status": "open",
      "priority": "P2",
      "type": "feature"
    }
  ]
}
```

### Via Cub Plan

The plan flow generates tasks:

```bash
cub plan run
# After orient, architect, itemize, stage...
# Tasks are written to prd.json
```

### Task ID Format

IDs follow the pattern `{prefix}-{number}`:

- `myproj-001`, `myproj-002`, `myproj-003`
- Numbers are zero-padded to 3 digits

Cub auto-generates the next available ID when creating tasks.

## Managing Tasks

### Closing Tasks

When the AI completes work, it updates `prd.json`:

```json
{
  "id": "myproj-001",
  "title": "Add new feature",
  "status": "closed",  // Changed from "open"
  "notes": "[Closed: 2026-01-17T10:30:00] Implemented with tests"
}
```

### Checking Status

View task status with any JSON tool:

```bash
# List all tasks
jq '.tasks[] | {id, title, status}' prd.json

# Find open tasks
jq '.tasks[] | select(.status == "open")' prd.json

# Find ready tasks (open with no unfulfilled dependencies)
jq --slurpfile prd prd.json '
  ($prd[0].tasks | map(select(.status == "closed")) | map(.id)) as $closed |
  $prd[0].tasks[] |
  select(.status == "open") |
  select((.dependsOn // []) | all(. as $dep | $closed | contains([$dep])))
' prd.json
```

### Filtering by Label

```bash
# Tasks with 'frontend' label
jq '.tasks[] | select(.labels | contains(["frontend"]))' prd.json
```

## Agent Instructions

When cub runs a task with the JSON backend, it includes these instructions:

```
This project uses the JSON task backend (prd.json). To manage tasks:
- Update prd.json: set status to "closed" for myproj-001
- Read prd.json to check task status
- View all tasks in the "tasks" array
```

The AI reads and writes `prd.json` directly.

## Auto-Detection

Cub selects the JSON backend when:

1. `CUB_BACKEND=json` environment variable is set, OR
2. No `.beads/` directory exists

Force JSON backend:

```bash
CUB_BACKEND=json cub run
```

## When to Use JSON vs Beads

### Use JSON Backend When:

- Starting a new project quickly
- Learning Cub's concepts
- Working on small projects (< 50 tasks)
- You prefer minimal tooling
- You want version-controlled tasks in a single file

### Use Beads Backend When:

- Managing complex projects with many tasks
- You need rich CLI querying
- Working with epics and deep hierarchies
- You want branch-epic git integration
- Team workflows with concurrent access

## Migrating to Beads

To migrate from JSON to beads:

1. Install beads:
   ```bash
   npm install -g @beads/bd
   ```

2. Initialize beads:
   ```bash
   bd init
   ```

3. Import tasks from prd.json:
   ```bash
   # For each task in prd.json
   jq -r '.tasks[] | "\(.title)\t\(.type // "task")\t\(.priority // "P2" | sub("P";""))"' prd.json | \
   while IFS=$'\t' read -r title type priority; do
     bd create "$title" --type "$type" --priority "$priority"
   done
   ```

4. Verify migration:
   ```bash
   bd list
   ```

5. Optionally archive prd.json:
   ```bash
   mv prd.json prd.json.bak
   ```

!!! note "Manual Migration"
    For complex tasks with dependencies and descriptions, consider migrating manually or writing a migration script that preserves all fields.

## Validation

Ensure your JSON is valid:

```bash
# Check for syntax errors
jq empty prd.json && echo "Valid JSON"

# Validate required fields
jq '.tasks[] | select(.id == null or .title == null)' prd.json
# (Should return nothing if all tasks have required fields)
```

## Troubleshooting

??? question "prd.json not found"
    Create it manually or let cub create it:
    ```json
    {
      "prefix": "myproj",
      "tasks": []
    }
    ```

??? question "JSON parse error"
    Validate your JSON:
    ```bash
    jq empty prd.json
    ```
    Common issues: trailing commas, unquoted strings, missing braces.

??? question "Tasks not showing as ready"
    Check dependencies:
    ```bash
    jq '.tasks[] | select(.status == "open") | {id, dependsOn}' prd.json
    ```
    Ensure all `dependsOn` task IDs are closed.

??? question "AI not closing tasks"
    Verify AI has write access and check the task prompt includes JSON backend instructions. Enable `task.auto_close` in config as a fallback.

## Next Steps

<div class="grid cards" markdown>

-   :material-database: **[Beads Backend](beads.md)**

    ---

    Full-featured CLI for advanced task management.

-   :material-link-variant: **[Dependencies](dependencies.md)**

    ---

    Chain tasks and control execution order.

</div>
