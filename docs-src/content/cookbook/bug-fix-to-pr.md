---
title: "Recipe: Bug Fix to PR"
description: Complete workflow for fixing a bug from initial report through to a merged pull request.
---

# Fix a Bug from Issue to Merged PR

## What You'll Do

Start with a bug report, have Cub fix it autonomously, review the result, and land a merged pull request with a complete ledger entry. This is the bread-and-butter Cub workflow for small, well-defined fixes.

**Time estimate:** 10--30 minutes (mostly waiting for the harness).

---

## Prerequisites

- `cub init` completed in your project
- GitHub CLI (`gh`) installed and authenticated (`gh auth status`)
- At least one harness available (`claude --version`, `codex`, etc.)
- A clean git working tree (`git status` shows no uncommitted changes)

---

## Step 1: Create the Task

Create a task that describes the bug. Be specific about what is broken and what "fixed" looks like -- the harness will use this as its instructions.

```bash
cub task create "Fix login timeout on slow connections" \
  --type bug \
  --priority 1 \
  --description "Users on connections > 500ms RTT see a timeout error on the login page. The fetch call in auth.ts uses a hardcoded 2-second timeout. Increase to 10 seconds and add a retry with exponential backoff. Acceptance: login succeeds on simulated 1s RTT, existing tests still pass."
```

Cub assigns a task ID (for example, `myapp-042-1.3`). Note it for the next steps.

```bash
# Verify the task is ready
cub task show myapp-042-1.3
```

---

## Step 2: Create a Branch

Bind a feature branch to the task's epic so Cub tracks the relationship between code changes and the task.

```bash
# Option A: Let cub create and bind the branch
cub branch myapp-042

# Option B: Create a branch manually
git checkout -b fix/login-timeout
```

If you use Option B, Cub still tracks the work through the task ID, but you will not get automatic branch-epic bindings for `cub pr`.

---

## Step 3: Run Cub

Execute a single iteration targeting your task. The `--once` flag tells Cub to run exactly one task and stop.

```bash
cub run --once --task myapp-042-1.3
```

What happens behind the scenes:

1. Cub generates a prompt from the task title, description, and acceptance criteria.
2. The harness (Claude Code by default) receives the prompt and begins working.
3. It edits files, runs tests, and commits changes.
4. Cub records the result in the ledger.

!!! tip "Watch in real-time"
    Add `--stream` to see the harness output as it works:
    ```bash
    cub run --once --task myapp-042-1.3 --stream
    ```

---

## Step 4: Review the Work

Before merging, review what the harness produced.

```bash
# Cub's built-in review command
cub review myapp-042-1.3

# Check the actual diff
git diff main

# Run tests manually to confirm
pytest tests/ -v
```

If the fix is not right, you can re-run with additional context:

```bash
# Update the task description with feedback
cub task show myapp-042-1.3 --full
# Then re-run
cub run --once --task myapp-042-1.3
```

---

## Step 5: Create a PR

If you used `cub branch` in Step 2, create a PR through Cub:

```bash
cub pr myapp-042 --push
```

This pushes the branch, generates a PR body from the completed tasks, and opens the PR on GitHub.

If you created the branch manually, use `gh` directly:

```bash
git push -u origin fix/login-timeout
gh pr create --title "fix: increase login timeout for slow connections" \
  --body "Fixes login timeout on high-latency connections. Increases fetch timeout to 10s and adds retry with exponential backoff."
```

---

## Step 6: Close and Record

Once the PR is merged, close the task and verify the ledger entry.

```bash
# Close the task with a reason
cub task close myapp-042-1.3 -r "Fixed timeout by increasing to 10s with exponential backoff retry"

# Verify the ledger recorded the work
cub ledger show
```

The ledger entry captures what was done, which files changed, token usage, and cost -- giving you a permanent record of the fix.

---

## Tips

- **Use `--stream` to watch.** Seeing the harness work in real-time helps you catch issues early and builds confidence in the output.

- **Check `cub status` before starting.** Make sure no other tasks are in-progress and your working tree is clean.

- **Use `--model haiku` for simple fixes.** Small, well-scoped bugs often do not need the most powerful model. Haiku is faster and cheaper:
    ```bash
    cub run --once --task myapp-042-1.3 --model haiku
    ```

- **Set a budget for safety.** Prevent runaway costs on a single fix:
    ```bash
    cub run --once --task myapp-042-1.3 --budget 2
    ```

- **Review the diff, not just the tests.** AI-generated code can pass tests while introducing subtle issues. Always read the diff before merging.

---

## Next Steps

- [Feature from Spec](feature-from-spec.md) -- For larger work that needs planning before execution
- [Pull Request Workflow](../guide/git/pr.md) -- Detailed PR management options
- [The Run Loop](../guide/run-loop/index.md) -- How Cub selects and executes tasks
