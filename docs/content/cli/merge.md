# cub merge

Merge pull requests with CI verification.

## Synopsis

```bash
cub merge <target> [OPTIONS]
cub merge wait <target> [OPTIONS]
```

## Description

The `cub merge` command merges pull requests after verifying CI status. It supports different merge methods (squash, merge, rebase) and can optionally delete the source branch after merging.

The command:

1. Verifies all CI checks have passed
2. Merges the PR using the specified method
3. Updates the branch binding status to `merged`
4. Optionally deletes the source branch

## Options

| Option | Description |
|--------|-------------|
| `<target>` | Epic ID, branch name, or PR number (required) |
| `-m, --method <method>` | Merge method: `squash`, `merge`, or `rebase` (default: `squash`) |
| `--no-delete` | Don't delete branch after merge |
| `-f, --force` | Merge even if checks are failing |
| `-n, --dry-run` | Show what would be done without making changes |

## Subcommands

### `cub merge wait`

Wait for CI checks to complete before proceeding.

| Option | Description |
|----------|-------------|
| `<target>` | Epic ID, branch name, or PR number (required) |
| `--timeout <seconds>` | Timeout in seconds (default: 600) |

## Examples

### Merge an Epic

```bash
# Merge PR for epic (squash by default)
cub merge cub-vd6
```

### Merge by PR Number

```bash
cub merge 123
```

### Merge by Branch Name

```bash
cub merge feature/my-branch
```

### Different Merge Methods

```bash
# Use merge commit instead of squash
cub merge cub-vd6 --method merge

# Use rebase
cub merge cub-vd6 --method rebase
```

### Keep Branch After Merge

```bash
cub merge cub-vd6 --no-delete
```

### Force Merge

```bash
# Merge even if CI checks are failing
cub merge cub-vd6 --force
```

### Dry Run

```bash
# Preview without making changes
cub merge cub-vd6 --dry-run
```

### Wait for CI

```bash
# Wait for checks to pass, then merge
cub merge wait cub-vd6
cub merge cub-vd6

# With custom timeout (20 minutes)
cub merge wait cub-vd6 --timeout 1200
```

## Merge Methods

| Method | Description |
|--------|-------------|
| `squash` | Combine all commits into one (default) |
| `merge` | Create a merge commit |
| `rebase` | Rebase commits onto base branch |

### When to Use Each

**Squash** (default):
- Clean history with one commit per feature
- Simplifies reverting features
- Good for most feature branches

**Merge**:
- Preserves full commit history
- Clear branch topology in history
- Good for long-running branches

**Rebase**:
- Linear history
- Individual commits preserved
- Good for small, incremental changes

## CI Verification

By default, `cub merge` checks CI status before merging:

```bash
cub merge cub-vd6
```

If checks are failing:
```
CI checks failed:
  - tests: failure
  - lint: cancelled

Use --force to merge anyway
```

If checks are still running:
```
CI checks still running:
  - deploy-preview: in_progress

Wait for checks to complete or use --force to merge anyway
```

### Force Merge

Use `--force` to bypass CI verification:

```bash
cub merge cub-vd6 --force
```

Use this cautiously - only when you understand why checks are failing and have manually verified the code is safe to merge.

## Workflow Examples

### Standard Workflow

```bash
# Create and push PR
cub pr cub-vd6 --push

# Wait for CI
cub merge wait cub-vd6

# Merge when ready
cub merge cub-vd6
```

### Automated Pipeline

```bash
# In a script or CI job
cub merge wait cub-vd6 --timeout 1800  # 30 min timeout
if [ $? -eq 0 ]; then
  cub merge cub-vd6
else
  echo "CI failed or timed out"
  exit 1
fi
```

### Keep Branch for Debugging

```bash
# Merge but keep the branch
cub merge cub-vd6 --no-delete

# Later, manually delete
git push origin --delete feature/cub-vd6
```

### Quick Merge for Hotfixes

```bash
# For verified hotfixes, skip waiting
cub merge hotfix-123 --force
```

## Output

### Successful Merge

```
PR #45 merged and branch deleted
```

Or with `--no-delete`:

```
PR #45 merged (branch kept)
```

### Dry Run

```
Dry run - no changes made
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Merge successful |
| 1 | Error (CI failed, PR not found, etc.) |
| 130 | Interrupted (Ctrl+C during wait) |

## Prerequisites

- GitHub CLI (`gh`) must be installed and authenticated
- PR must exist for the target
- You must have permission to merge

## Troubleshooting

### "CI checks failed"

Fix the failing checks or use `--force`:

```bash
# Check what's failing
cub pr status cub-vd6

# Fix issues, push, then merge
git push origin feature/cub-vd6
cub merge wait cub-vd6
cub merge cub-vd6
```

### "No PR found"

Create a PR first:

```bash
cub pr cub-vd6
cub merge cub-vd6
```

### "Cannot merge - conflicts"

Resolve conflicts locally:

```bash
git checkout feature/cub-vd6
git rebase main
# Resolve conflicts
git push --force-with-lease
cub merge cub-vd6
```

### Timeout During Wait

Increase timeout or check CI status:

```bash
# Longer timeout
cub merge wait cub-vd6 --timeout 1800

# Check what's taking long
cub pr status cub-vd6
```

## Related Commands

- [`cub pr`](pr.md) - Create pull requests
- [`cub branch`](branch.md) - Create and bind branches
- [`cub branches`](branches.md) - List branch bindings (includes merge status)
- [`cub worktree`](worktree.md) - Parallel work with worktrees
