# cub worktree

Manage git worktrees for parallel task execution.

## Synopsis

```bash
cub worktree [SUBCOMMAND]
cub worktree list [OPTIONS]
cub worktree create <branch> [OPTIONS]
cub worktree remove <path> [OPTIONS]
cub worktree clean [OPTIONS]
```

## Description

The `cub worktree` command manages git worktrees to enable parallel task execution. Each worktree is an additional working directory linked to your repository, allowing you to work on multiple epics simultaneously in isolated environments.

Worktrees:

- Have their own checked-out branch
- Share the same git history and objects
- Operate independently (commits, changes, etc.)
- Use minimal additional disk space

## Subcommands

### `cub worktree` (default: list)

Running `cub worktree` without a subcommand shows all worktrees.

### `cub worktree list`

Show all worktrees in the repository.

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Show additional details (lock status, task ID) |

### `cub worktree create`

Create a new worktree.

| Option | Description |
|--------|-------------|
| `<branch>` | Branch name or task ID (required) |
| `-t, --task-id <id>` | Task ID for organizing (defaults to branch name) |

### `cub worktree remove`

Remove a worktree.

| Option | Description |
|--------|-------------|
| `<path>` | Path to the worktree (required) |
| `-f, --force` | Force removal even with uncommitted changes |

### `cub worktree clean`

Remove worktrees for merged branches.

| Option | Description |
|--------|-------------|
| `-b, --base <branch>` | Base branch to check against (default: `main`) |
| `-v, --verbose` | Show removed worktrees |

## Examples

### List Worktrees

```bash
cub worktree
# or
cub worktree list
```

Output:
```
+------------------------+-------------------+----------+
| Path                   | Branch            | Commit   |
+------------------------+-------------------+----------+
| /home/user/my-project  | main              | abc1234  |
| .cub/worktrees/cub-001 | feature/cub-001   | def5678  |
| .cub/worktrees/cub-002 | feature/cub-002   | ghi9012  |
+------------------------+-------------------+----------+
```

### Verbose Listing

```bash
cub worktree list --verbose
```

Adds columns for lock status and associated task ID.

### Create Worktree

```bash
# Create with new branch
cub worktree create feature/new-feature

# Create and associate with task
cub worktree create cub-042 --task-id cub-042

# Create with custom branch name
cub worktree create my-branch --task-id cub-043
```

Output:
```
Created worktree at: .cub/worktrees/cub-042
  Branch: feature/cub-042
  Commit: abc1234
  Task ID: cub-042
```

### Remove Worktree

```bash
# Remove a worktree
cub worktree remove .cub/worktrees/cub-042

# Force remove (even with uncommitted changes)
cub worktree remove .cub/worktrees/cub-042 --force
```

### Clean Merged Worktrees

```bash
# Clean up after merging
cub worktree clean

# Check against different base branch
cub worktree clean --base develop

# Show what was removed
cub worktree clean --verbose
```

## Directory Structure

Worktrees are created under `.cub/worktrees/`:

```
my-project/                          # Main worktree
+-- .git/                            # Shared git data
+-- .cub/worktrees/
    +-- cub-001/                     # Task worktree
    |   +-- .git                     # Pointer to main .git
    |   +-- src/
    |   +-- tests/
    +-- cub-002/                     # Another task worktree
        +-- .git
        +-- src/
        +-- tests/
```

## Parallel Work

### Setup for Multiple Epics

```bash
# Create worktrees for two epics
cub worktree create cub-001 --task-id cub-001
cub worktree create cub-002 --task-id cub-002
```

### Running in Parallel

Open multiple terminals:

```bash
# Terminal 1: Run epic 001
cd .cub/worktrees/cub-001
cub run --epic cub-001

# Terminal 2: Run epic 002
cd .cub/worktrees/cub-002
cub run --epic cub-002
```

### Using `--worktree` Flag

Alternatively, use the `--worktree` flag on `cub run`:

```bash
# Automatically creates/uses worktree for task
cub run --worktree --epic cub-001
```

This:
1. Creates a worktree for the task (if needed)
2. Runs the task in that isolated environment
3. Returns to main worktree when done

Additional options:

```bash
# Keep worktree after completion (don't auto-cleanup)
cub run --worktree --worktree-keep
```

## Integration with `cub run`

### Automatic Worktree Mode

```bash
cub run --worktree --epic cub-001
```

Workflow:
1. Check if worktree exists for task
2. Create if missing
3. Change to worktree directory
4. Execute task
5. Return to main worktree
6. Optionally cleanup (unless `--worktree-keep`)

### Manual Worktree Mode

```bash
# Create worktree manually
cub worktree create cub-001 --task-id cub-001

# Run in that worktree
cd .cub/worktrees/cub-001
cub run --epic cub-001

# Clean up when done
cd ../..
cub worktree remove .cub/worktrees/cub-001
```

## Best Practices

### Use Worktrees for Independent Work

Worktrees are ideal when tasks don't depend on each other:

```bash
# Epic A: Frontend work
cub worktree create frontend-feature

# Epic B: Backend work (independent)
cub worktree create backend-feature
```

### Clean Up After Merging

Remove merged worktrees to save disk space:

```bash
cub worktree clean
```

### Don't Share Worktrees

Each worktree should have a single user/session:

```bash
# Bad: Two sessions in same worktree
cd .cub/worktrees/cub-001
cub run &
cub run  # Conflict!
```

### Check Status Before Cleanup

```bash
# See what's in each worktree
cub worktree list --verbose

# Check for uncommitted work
cd .cub/worktrees/cub-001 && git status
```

## Performance Considerations

### Disk Space

Worktrees share git objects, so they use minimal additional space:

- Git objects: Shared (no duplication)
- Working files: Full copy per worktree

For a 100MB repository with 3 worktrees:
- Without worktrees: ~100MB
- With worktrees: ~120MB (not 400MB)

### I/O Performance

Each worktree has independent file I/O. Parallel execution does not create conflicts.

### Memory

Multiple `cub run` sessions use separate memory spaces. Monitor total memory if running many parallel sessions.

## Troubleshooting

### Worktree Already Exists

```
Error: Worktree already exists at: .cub/worktrees/cub-001
```

Solutions:
1. Use existing worktree: `cd .cub/worktrees/cub-001`
2. Remove and recreate: `cub worktree remove .cub/worktrees/cub-001`

### Branch Is Checked Out Elsewhere

```
Error: Branch feature/cub-001 is already checked out at /path/to/worktree
```

Git prevents the same branch from being checked out in multiple worktrees.

Solutions:
1. Use different branch names per worktree
2. Remove the other worktree first

### Worktree Has Uncommitted Changes

```
Error: Worktree has uncommitted changes, use --force to remove
```

Options:
1. Commit or stash changes in the worktree
2. Force remove: `cub worktree remove .cub/worktrees/cub-001 --force`

### Pruning Stale Worktrees

If worktrees were manually deleted:

```bash
# Clean up git's worktree metadata
git worktree prune
```

## Related Commands

- [`cub run`](../guide/run-loop/index.md) - Execute tasks (supports `--worktree`)
- [`cub branch`](branch.md) - Create and bind branches
- [`cub branches`](branches.md) - List branch bindings
- [`cub sandbox`](../guide/advanced/sandbox.md) - Docker-based isolation
