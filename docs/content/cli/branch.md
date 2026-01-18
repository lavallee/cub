# cub branch

Create and bind a git branch to an epic.

## Synopsis

```bash
cub branch <epic-id> [OPTIONS]
```

## Description

The `cub branch` command creates a new git branch and binds it to an epic. This binding enables organized, trackable development where branches map to logical units of work.

When you create a branch binding:

1. A new git branch is created (unless using `--bind-only`)
2. The binding is recorded in `.beads/branches.yaml`
3. Metadata is stored for later PR creation
4. The epic becomes associated with this branch for `cub run` and `cub pr`

## Options

| Option | Description |
|--------|-------------|
| `<epic-id>` | Epic identifier to bind (required) |
| `--name <branch>` | Custom branch name (default: `feature/<epic-id>`) |
| `--bind-only` | Bind current branch without creating new one |
| `--base <branch>` | Base branch to create from (default: current branch) |

## Examples

### Create Branch for Epic

```bash
# Create default-named branch
cub branch cub-vd6

# Output:
# Created branch: feature/cub-vd6
# Bound to epic: cub-vd6
```

### Custom Branch Name

```bash
# Use descriptive branch name
cub branch cub-vd6 --name feature/v19-git-workflow
```

### Bind Existing Branch

```bash
# Already on a branch, just bind it
git checkout -b my-feature
cub branch cub-vd6 --bind-only
```

### Create from Specific Base

```bash
# Branch from develop instead of current
cub branch cub-vd6 --base develop
```

## Branch Naming Conventions

### Default Naming

Without `--name`, branches are named:

```
feature/<epic-id>
```

Examples:
- `feature/cub-vd6`
- `feature/cub-abc123`

### Custom Naming

Use `--name` for descriptive names:

```bash
cub branch cub-vd6 --name release/v2.0
cub branch cub-auth --name feature/oauth-integration
```

### Session Branches

When using the auto-branch hook, session branches follow:

```
cub/{session_name}/{timestamp}
```

Examples:
- `cub/porcupine/20260111-114543`
- `cub/narwhal/20260111-120000`

## Binding Storage

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

## Workflow Integration

### With `cub run`

The bound branch is used automatically:

```bash
# Runs on feature/cub-vd6 branch
cub run --epic cub-vd6
```

### With `cub pr`

PR creation uses binding information:

```bash
# Creates PR from feature/cub-vd6 to main
cub pr cub-vd6
```

The binding provides:
- Source branch
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

# Approve to unblock further work
cub checkpoints approve <checkpoint-id>
```

## Best Practices

### One Epic per Branch

Each epic should have exactly one branch:

```bash
# Good: Each epic has its own branch
cub branch cub-001
cub branch cub-002

# Avoid: Multiple epics sharing a branch
```

### Use Descriptive Names for Large Features

```bash
cub branch cub-vd6 --name feature/git-workflow-v19
```

### Keep Base Branch Updated

Before creating a new branch:

```bash
git checkout main
git pull origin main
cub branch cub-vd6
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

Check and rebind if needed:

```bash
cub branches | grep cub-vd6
cub branches --unbind cub-vd6
cub branch cub-vd6 --name new-branch-name
```

## Related Commands

- [`cub branches`](branches.md) - List and manage branch bindings
- [`cub pr`](pr.md) - Create pull requests
- [`cub worktree`](worktree.md) - Parallel work with worktrees
- [`cub merge`](merge.md) - Merge completed work
