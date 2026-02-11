---
title: "Recipe: Parallel Epics"
description: Execute multiple independent epics in parallel using worktrees and branch bindings.
---

# Parallel Execution Across Epics

Run tasks from multiple independent epics simultaneously, each in its own git worktree on its own feature branch. When done, each epic produces a separate pull request that can be reviewed and merged independently.

## What You'll Do

1. Verify your epics are truly independent (no cross-epic dependencies)
2. Bind each epic to a feature branch
3. Launch parallel execution across epics
4. Monitor progress from a live dashboard
5. Review each epic's changes
6. Create separate PRs and merge

**Time to set up:** ~5 minutes. **Throughput gain:** 2-4x depending on task count and API limits.

---

## Prerequisites

- Multiple epics with tasks that do not depend on each other across epics
- All tasks planned and staged
- Sufficient system resources (disk space for worktrees, API rate limit headroom)
- `cub init` completed in the project

!!! warning "Independence is critical"
    Parallel epics must not share file dependencies. If epic A modifies `src/auth.py` and epic B also modifies `src/auth.py`, you will have merge conflicts. Verify independence before launching.

---

## Step 1: Plan Your Epics

Suppose you have three independent streams of work:

```
Epic: backend-api    (5 tasks)  -- New REST endpoints
Epic: frontend-ui    (4 tasks)  -- Dashboard components
Epic: infra-setup    (3 tasks)  -- CI/CD and monitoring
```

Verify that no tasks cross epic boundaries:

```bash
# Check for blocked tasks and cross-dependencies
cub task blocked --agent

# View each epic's tasks
cub task list --epic backend-api --agent
cub task list --epic frontend-ui --agent
cub task list --epic infra-setup --agent
```

Look for `dependsOn` fields that reference task IDs from a different epic. If you find any, either resolve the dependency first or move the dependent task to a later phase.

!!! tip "Design for independence"
    When planning epics, aim for work that touches different parts of the codebase. Backend API work, frontend UI work, and infrastructure work are natural candidates for parallel execution because they rarely share files.

---

## Step 2: Bind Branches

Each epic needs its own feature branch. Cub tracks the binding between epics and branches:

```bash
# Create and bind a branch for each epic
cub branch backend-api
cub branch frontend-ui
cub branch infra-setup
```

This creates branches named after the epic IDs (e.g., `backend-api`, `frontend-ui`, `infra-setup`). To use custom branch names:

```bash
cub branch backend-api --name feature/api-v2
cub branch frontend-ui --name feature/dashboard
cub branch infra-setup --name feature/cicd
```

Verify your bindings:

```bash
cub branches
```

Expected output:

```
Branch Bindings
+-----------------+---------------------+--------+
| Epic            | Branch              | Status |
+-----------------+---------------------+--------+
| backend-api     | feature/api-v2      | active |
| frontend-ui     | feature/dashboard   | active |
| infra-setup     | feature/cicd        | active |
+-----------------+---------------------+--------+
```

---

## Step 3: Launch Parallel Run

### Option A: Automatic Parallel Mode

Run all three epics simultaneously with a single command:

```bash
cub run --parallel 3 --budget 50
```

Cub selects independent tasks across epics, creates a worktree for each, and runs them simultaneously.

### Option B: Per-Epic in Separate Terminals

For more control, run each epic in its own terminal or tmux pane:

```bash
# Terminal 1
cub run --epic backend-api --worktree --budget 20 --stream

# Terminal 2
cub run --epic frontend-ui --worktree --budget 15 --stream

# Terminal 3
cub run --epic infra-setup --worktree --budget 15 --stream
```

### Option C: tmux Script

Automate the multi-pane setup:

```bash
# Create a tmux session with 3 panes
tmux new-session -d -s parallel-epics

# First pane: backend-api
tmux send-keys 'cub run --epic backend-api --worktree --budget 20 --stream' Enter

# Split and run frontend-ui
tmux split-window -h
tmux send-keys 'cub run --epic frontend-ui --worktree --budget 15 --stream' Enter

# Split and run infra-setup
tmux split-window -v
tmux send-keys 'cub run --epic infra-setup --worktree --budget 15 --stream' Enter

# Attach
tmux attach -t parallel-epics
```

!!! note "Worktree disk usage"
    Each worktree is a full copy of your repository (excluding `.git`). For a 200MB project with 3 parallel epics, expect ~600MB of additional disk usage. Worktrees are cleaned up automatically after the run completes.

---

## Step 4: Monitor Progress

### Live Dashboard

```bash
cub monitor
```

The dashboard shows all active tasks, their status, and token usage across all parallel workers.

### Status Check

```bash
# Overall project progress
cub status

# Branch status for all epics
cub branches

# Per-epic status
cub task list --epic backend-api --agent
cub task list --epic frontend-ui --agent
cub task list --epic infra-setup --agent
```

### Ledger Activity

```bash
# Recent completions across all epics
cub ledger show --limit 10
```

---

## Step 5: Review Per-Epic

Once parallel execution completes, review each epic's changes independently.

### Review Changes

```bash
# Review the backend-api epic
cub review backend-api --epic

# Check git diff on the branch
git diff main...feature/api-v2 --stat

# Run tests on the branch
git checkout feature/api-v2
npm test  # or your test command
git checkout main
```

Repeat for each epic:

```bash
cub review frontend-ui --epic
cub review infra-setup --epic
```

### Check for Issues

```bash
# Verify data integrity
cub verify

# Check ledger stats for the session
cub ledger stats
```

---

## Step 6: Create PRs

Each epic gets its own pull request:

```bash
# Push branches and create PRs
cub pr backend-api --push
cub pr frontend-ui --push
cub pr infra-setup --push
```

Cub auto-generates PR descriptions from the epic's completed tasks, including:

- Summary of changes
- List of tasks completed
- Files modified
- Test results

!!! tip "Draft PRs for review"
    Use `--draft` to create draft PRs that signal "ready for review but not ready to merge":

    ```bash
    cub pr backend-api --push --draft
    ```

---

## Step 7: Merge and Clean Up

After PRs are reviewed and approved:

```bash
# Merge each PR
cub merge <pr-number-1>
cub merge <pr-number-2>
cub merge <pr-number-3>
```

Clean up merged branches:

```bash
# Remove branch bindings for merged branches
cub branches --cleanup

# Prune remote tracking branches
git fetch --prune
```

Verify everything is clean:

```bash
cub status
cub branches
git branch --merged main
```

---

## Tips

!!! tip "Set per-epic budgets via labels"
    For fine-grained cost control, label tasks within each epic with budget hints:

    ```bash
    # Cheap tasks
    cub task label backend-api-001 model:haiku
    cub task label backend-api-002 model:haiku

    # Expensive tasks
    cub task label backend-api-003 model:opus
    ```

!!! tip "Use `--sandbox` for extra isolation"
    If you are concerned about parallel tasks interfering with each other (e.g., tasks that start servers on specific ports), use sandbox mode:

    ```bash
    cub run --parallel 3 --sandbox
    ```

    Each worker runs in its own Docker container with full filesystem and network isolation.

!!! tip "Verify independence with a dry run"
    Before committing to a long parallel execution, do a quick sanity check:

    ```bash
    # Check that tasks in different epics don't touch the same files
    cub task show backend-api-001 --full
    cub task show frontend-ui-001 --full
    ```

    If task descriptions mention the same files or modules, reconsider parallel execution.

!!! warning "Watch API rate limits"
    Running 3 parallel workers means 3x the API calls. If you hit rate limits:

    - Reduce parallelism: `--parallel 2`
    - Use cheaper models for simpler tasks (`model:haiku` labels)
    - Stagger launch times (start epics 5 minutes apart)

!!! tip "Retry failed epics independently"
    If one epic fails while others succeed, re-run just that epic:

    ```bash
    cub run --epic infra-setup --worktree --budget 10 --stream
    ```

    The other epics' completed work is unaffected.

---

## Next Steps

- [Parallel Execution](../guide/advanced/parallel.md) -- Deep dive on worktrees and parallel task selection
- [Git Integration](../guide/git/index.md) -- Branch bindings, PRs, and worktree management
- [Overnight Batch](overnight-batch.md) -- Run a large sequential queue unattended
- [Budget & Guardrails](../guide/budget/index.md) -- Control costs across parallel workers
