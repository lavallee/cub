# Worktree Support

Git worktrees allow you to have multiple working directories for the same repository. Cub leverages worktrees to enable parallel task execution, where different epics can run simultaneously in isolated environments.

## What Are Worktrees?

A git worktree is an additional working directory linked to your repository. Each worktree:

- Has its own checked-out branch
- Shares the same git history and objects
- Operates independently (commits, changes, etc.)
- Uses minimal additional disk space

```
my-project/                          # Main worktree
+-- .git/                            # Shared git data
+-- .cub/worktrees/
    +-- cub-001/                     # Task worktree
    |   +-- src/
    |   +-- tests/
    +-- cub-002/                     # Another task worktree
        +-- src/
        +-- tests/
```

## The `cub worktree` Command

Cub provides the `cub worktree` command for managing worktrees.

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

### Verbose Output

```bash
cub worktree list --verbose
```

Adds columns for lock status and associated task ID.

### Create Worktree

```bash
cub worktree create <branch>
```

Examples:

```bash
# Create worktree with new branch
cub worktree create feature/new-feature

# Create worktree and associate with task
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
cub worktree remove <path>
```

Examples:

```bash
# Remove a worktree
cub worktree remove .cub/worktrees/cub-042

# Force remove (even with uncommitted changes)
cub worktree remove .cub/worktrees/cub-042 --force
```

### Clean Merged Worktrees

Remove worktrees whose branches have been merged:

```bash
cub worktree clean
```

Options:

```bash
# Check against different base branch
cub worktree clean --base develop

# Show which worktrees were removed
cub worktree clean --verbose
```

## Parallel Epic Work

Worktrees enable running multiple epics simultaneously:

### Setup

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

Or use `cub run --worktree`:

```bash
# Automatically creates/uses worktree for task
cub run --worktree --epic cub-001
```

### Worktree Flag

The `--worktree` flag on `cub run`:

```bash
cub run --worktree
```

This:
1. Creates a worktree for the current task (if needed)
2. Runs the task in that isolated environment
3. Returns to main worktree when done

Additional options:

```bash
# Keep worktree after completion (don't auto-cleanup)
cub run --worktree --worktree-keep
```

## Directory Structure

Worktrees are created under `.cub/worktrees/`:

```
.cub/
+-- worktrees/
    +-- cub-001/
    |   +-- .git                     # Pointer to main .git
    |   +-- src/
    |   +-- tests/
    |   +-- .cub.json
    +-- cub-002/
        +-- .git
        +-- src/
        +-- tests/
        +-- .cub.json
```

Each worktree is a complete working copy with its own checked-out files.

## Best Practices

### 1. Use Worktrees for Independent Work

Worktrees are ideal when tasks don't depend on each other:

```bash
# Epic A: Frontend work
cub worktree create frontend-feature

# Epic B: Backend work (independent)
cub worktree create backend-feature
```

### 2. Clean Up After Merging

Remove merged worktrees to save disk space:

```bash
cub worktree clean
```

### 3. Don't Share Worktrees

Each worktree should have a single user/session. Avoid:

```bash
# Bad: Two sessions in same worktree
cd .cub/worktrees/cub-001
cub run &
cub run  # Conflict!
```

### 4. Use Descriptive Branch Names

```bash
cub worktree create feature/user-auth --task-id cub-auth
```

### 5. Check Status Before Cleanup

```bash
# See what's in each worktree
cub worktree list --verbose

# Check for uncommitted work
cd .cub/worktrees/cub-001 && git status
```

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

## Comparison: Worktrees vs. Clones

| Feature | Worktrees | Multiple Clones |
|---------|-----------|-----------------|
| Disk space | Shared objects | Duplicated |
| Git history | Single source | Separate |
| Branch visibility | Immediate | Requires fetch |
| Setup time | Fast | Slower |
| Cleanup | `worktree remove` | Delete directory |

Worktrees are preferred for parallel work in the same repository.
