# cub branches

List and manage epic-branch bindings.

## Synopsis

```bash
cub branches [OPTIONS]
```

## Description

The `cub branches` command displays and manages the bindings between epics and git branches. These bindings are created with `cub branch` and stored in `.beads/branches.yaml`.

Use this command to:

- View all branch-epic bindings
- Filter by status (active, merged, closed)
- Remove bindings
- Cleanup merged branches
- Sync binding status with git

## Options

| Option | Description |
|--------|-------------|
| `--status <status>` | Filter by status: `active`, `merged`, `closed` |
| `--json` | Output in JSON format for scripting |
| `--unbind <epic-id>` | Remove binding for specified epic |
| `--cleanup` | Remove branches that have been merged |
| `--sync` | Update binding status from git state |

## Examples

### List All Bindings

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

For scripting and automation:

```bash
cub branches --json
```

Output:
```json
{
  "bindings": [
    {
      "epic_id": "cub-vd6",
      "branch": "feature/cub-vd6",
      "base_branch": "main",
      "status": "active",
      "pr_number": null
    }
  ]
}
```

### Remove a Binding

```bash
cub branches --unbind cub-vd6
```

This removes the binding but **does not delete the git branch**.

### Cleanup Merged Branches

```bash
cub branches --cleanup
```

This:
1. Checks which bound branches are merged into their base
2. Deletes the merged git branches
3. Updates binding status to `merged`

### Sync Status from Git

```bash
cub branches --sync
```

Updates binding records based on actual git state:
- Marks branches as merged if they've been merged
- Detects if branches have been deleted

## Binding Status

| Status | Description |
|--------|-------------|
| `active` | Branch exists and work is ongoing |
| `merged` | Branch has been merged to base |
| `closed` | Binding removed without merge |

## Workflow Examples

### Review Before PR

```bash
# Check current bindings before creating PRs
cub branches --status active

# Create PR for ready epic
cub pr cub-vd6
```

### Post-Release Cleanup

```bash
# After releasing, clean up merged branches
cub branches --cleanup

# Verify cleanup
cub branches --status merged
```

### Rebind After Branch Rename

```bash
# Remove old binding
cub branches --unbind cub-vd6

# Create new branch with different name
git checkout -b feature/v19-complete
cub branch cub-vd6 --bind-only
```

### Scripting with JSON

```bash
# Get all active branch names
cub branches --json | jq -r '.bindings[] | select(.status == "active") | .branch'

# Count active bindings
cub branches --json | jq '.bindings | map(select(.status == "active")) | length'
```

## Storage Format

Bindings are stored in `.beads/branches.yaml`:

```yaml
bindings:
  - epic_id: cub-vd6
    branch: feature/cub-vd6
    base_branch: main
    created_at: 2026-01-11T11:45:43Z
    status: active
    pr_number: null

  - epic_id: cub-abc
    branch: feature/cub-abc
    base_branch: main
    created_at: 2026-01-10T09:30:00Z
    status: merged
    pr_number: 42
```

## Best Practices

### Regular Cleanup

After merging PRs, clean up branches:

```bash
cub branches --cleanup
```

### Sync Before Starting Work

Ensure bindings are current:

```bash
cub branches --sync
git fetch origin
```

### Use JSON for CI/CD

In CI scripts:

```bash
# Check if epic has a PR
pr_num=$(cub branches --json | jq -r --arg epic "$EPIC_ID" \
  '.bindings[] | select(.epic_id == $epic) | .pr_number')
```

## Troubleshooting

### Stale Bindings

If bindings are out of sync with git:

```bash
cub branches --sync
```

### Orphaned Bindings

If a branch was deleted outside of cub:

```bash
# Sync will detect missing branches
cub branches --sync

# Or manually unbind
cub branches --unbind cub-old-epic
```

### Duplicate Bindings

If an epic somehow has multiple bindings:

```bash
# Check current state
cub branches --json | jq '.bindings[] | select(.epic_id == "cub-vd6")'

# Unbind and rebind
cub branches --unbind cub-vd6
cub branch cub-vd6 --bind-only
```

## Related Commands

- [`cub branch`](branch.md) - Create and bind branches
- [`cub pr`](pr.md) - Create pull requests
- [`cub merge`](merge.md) - Merge completed work
- [`cub worktree`](worktree.md) - Parallel work with worktrees
