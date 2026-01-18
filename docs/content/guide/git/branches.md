# Branch Management

Cub provides commands for creating and managing git branches that are associated with epics. This enables organized, trackable development where branches map to logical units of work.

## The `cub branch` Command

Create a new branch and bind it to an epic:

```bash
cub branch <epic-id>
```

### Basic Usage

```bash
# Create new branch for an epic
cub branch cub-vd6

# Output:
# Created branch: feature/cub-vd6
# Bound to epic: cub-vd6
```

This command:

1. Creates a new git branch (if not already on one)
2. Records the binding in `.beads/branches.yaml`
3. Stores metadata for later PR creation

### Options

| Option | Description |
|--------|-------------|
| `--name <branch>` | Custom branch name (default: `feature/<epic-id>`) |
| `--bind-only` | Bind current branch without creating new one |
| `--base <branch>` | Base branch to create from (default: current) |

### Examples

```bash
# Create branch with custom name
cub branch cub-vd6 --name feature/v19-git-workflow

# Bind existing branch to epic
git checkout -b my-feature
cub branch cub-vd6 --bind-only

# Create from specific base branch
cub branch cub-vd6 --base develop
```

## Branch Naming Convention

Cub uses a consistent naming convention for branches:

### Session Branches (Auto-Branch Hook)

Created automatically when using the auto-branch hook:

```
cub/{session_name}/{timestamp}
```

Examples:
- `cub/porcupine/20260111-114543`
- `cub/narwhal/20260111-120000`

### Epic Branches (cub branch Command)

Created when binding a branch to an epic:

```
feature/{epic-id}
```

Examples:
- `feature/cub-vd6`
- `feature/cub-abc123`

You can customize the name with `--name`:

```bash
cub branch cub-vd6 --name release/v2.0
```

## Epic-Branch Bindings

Bindings are stored in `.beads/branches.yaml`:

```yaml
bindings:
  - epic_id: cub-vd6
    branch: feature/cub-vd6
    base_branch: main
    created_at: 2026-01-11T11:45:43Z
    status: active
    pr_number: null
```

### Binding Fields

| Field | Description |
|-------|-------------|
| `epic_id` | The epic this branch implements |
| `branch` | Git branch name |
| `base_branch` | Target branch for eventual PR |
| `created_at` | When the binding was created |
| `status` | `active`, `merged`, or `closed` |
| `pr_number` | Associated PR number (if created) |

## Managing Branches

### List Bindings

View all branch-epic bindings:

```bash
cub branches
```

Output:
```
Epic       Branch              Base   Status   PR
cub-vd6    feature/cub-vd6     main   active   -
cub-abc    feature/cub-abc     main   merged   #42
cub-xyz    feature/cub-xyz     main   active   #45
```

### Filter by Status

```bash
# Only active branches
cub branches --status active

# Only merged branches
cub branches --status merged
```

### JSON Output

For scripting:

```bash
cub branches --json
```

```json
{
  "bindings": [
    {
      "epic_id": "cub-vd6",
      "branch": "feature/cub-vd6",
      "base_branch": "main",
      "status": "active"
    }
  ]
}
```

### Remove Binding

Unbind a branch from its epic:

```bash
cub branches --unbind cub-vd6
```

This removes the binding but does not delete the branch.

### Cleanup Merged Branches

Remove branches that have been merged:

```bash
cub branches --cleanup
```

This:
1. Checks which bound branches are merged into their base
2. Deletes the merged branches
3. Updates binding status to `merged`

### Sync Status

Update binding status from git state:

```bash
cub branches --sync
```

This checks if branches have been merged and updates the binding records accordingly.

## Workflow Integration

### With `cub run`

When running tasks for a specific epic, cub uses the bound branch:

```bash
# Automatically uses feature/cub-vd6 branch
cub run --epic cub-vd6
```

### With `cub pr`

Pull request creation uses binding information:

```bash
# Creates PR from feature/cub-vd6 to main
cub pr cub-vd6
```

The binding provides:
- Source branch (from binding)
- Target branch (from `base_branch`)
- PR title (from epic title)
- PR body (from completed tasks)

### With Checkpoints

Branches can have associated checkpoints (review gates):

```bash
# Create a checkpoint for the branch
bd create "Review: feature complete" --type gate --parent cub-vd6

# List checkpoints
cub checkpoints --epic cub-vd6

# Approve checkpoint to unblock further work
cub checkpoints approve <checkpoint-id>
```

## Best Practices

### 1. One Epic per Branch

Each epic should have exactly one branch. This keeps the mapping clear:

```bash
# Good: Each epic has its own branch
cub branch cub-001
cub branch cub-002

# Avoid: Multiple epics on one branch
```

### 2. Use Descriptive Names for Large Features

For significant features, use custom branch names:

```bash
cub branch cub-vd6 --name feature/git-workflow-v19
```

### 3. Clean Up After Merging

Regularly clean up merged branches:

```bash
cub branches --cleanup
```

### 4. Sync Before Starting Work

Ensure bindings are current:

```bash
cub branches --sync
git fetch origin
```

## Troubleshooting

### Branch Already Exists

```
Error: Branch feature/cub-vd6 already exists
```

Solution: Bind to existing branch instead:

```bash
git checkout feature/cub-vd6
cub branch cub-vd6 --bind-only
```

### Epic Already Bound

```
Error: Epic cub-vd6 already has a branch binding
```

Solution: Check existing binding:

```bash
cub branches | grep cub-vd6
```

If you need to rebind, first unbind:

```bash
cub branches --unbind cub-vd6
cub branch cub-vd6 --name new-branch-name
```

### Binding Not Found

```
Error: No branch binding found for epic cub-vd6
```

Solution: Create the binding:

```bash
cub branch cub-vd6
```

Or if the branch exists:

```bash
git checkout your-branch
cub branch cub-vd6 --bind-only
```
