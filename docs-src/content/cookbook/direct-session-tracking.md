---
title: "Recipe: Direct Session Tracking"
description: Use hooks to automatically track work done in interactive Claude Code sessions.
---

# Track Work in Direct Claude Code Sessions

Work interactively in Claude Code while hooks automatically record your progress. Every file write, git commit, and task command is captured, producing ledger entries that match the quality of a `cub run` session -- without giving up the interactive experience.

## What You'll Do

1. Verify that hooks are installed and working
2. Open Claude Code and let SessionStart inject context
3. Claim a task to associate your session with specific work
4. Work normally -- hooks track everything in the background
5. Close the task when done
6. Verify the ledger entry was recorded

**Time to set up:** 2 minutes (one-time). **Per-session overhead:** zero.

---

## Prerequisites

- Cub initialized in the project (`cub init` completed)
- Claude Code installed and available
- Hooks installed (done automatically by `cub init`)

---

## Step 1: Verify Hooks

Run the diagnostic command to confirm hooks are properly installed:

```bash
cub doctor
```

Look for these checks in the output:

```
Hooks installed:                 Yes
Shell script present:            Yes
Shell script executable:         Yes
Python module importable:        Yes
All hook events configured:      Yes
```

If any check fails, re-run initialization:

```bash
cub init
```

!!! note "What `cub init` installs"
    The init command creates `.cub/scripts/hooks/cub-hook.sh` (the fast-path shell filter) and configures `.claude/settings.json` with hook entries for `PostToolUse` and `Stop` events.

---

## Step 2: Start Claude Code

Open Claude Code in your project directory:

```bash
claude
```

When the session starts, the **SessionStart** hook fires automatically. It injects context into your session including:

- A list of tasks that are ready to work on
- The current epic and its progress
- Any relevant project context from `.cub/config.json`

You should see something like this in the session context:

```
Ready tasks:
  myproj-042: Add input validation to login form
  myproj-043: Write unit tests for auth module
  myproj-044: Update API documentation
```

---

## Step 3: Claim a Task

Pick a task from the injected context and claim it:

```bash
cub task claim myproj-042
```

This does two things:

1. Marks the task as **in-progress** in the task backend
2. Associates the current session with this task ID for forensics tracking

!!! tip "Claim early"
    Claim as soon as you know what you are working on. The earlier you claim, the more complete your forensics log will be. If you forget to claim, `cub reconcile` can help after the fact.

You can also view task details before claiming:

```bash
# Quick summary
cub task show myproj-042

# Full description with acceptance criteria
cub task show myproj-042 --full
```

---

## Step 4: Work Normally

Now just work as you normally would in Claude Code. Write code, run tests, make commits. The hooks operate entirely in the background.

**What hooks track automatically:**

| Activity | Hook Event | What Gets Recorded |
|----------|-----------|-------------------|
| Writing or editing files | PostToolUse (Write/Edit) | File path, tool used, timestamp |
| Running bash commands | PostToolUse (Bash) | Command executed, exit code |
| Running `cub task` commands | PostToolUse (Bash) | Task ID, operation (claim/close) |
| Making git commits | PostToolUse (Bash) | Commit hash, message |
| Session ending | Stop | Session duration, final state |

All events are written to a forensics log at `.cub/ledger/forensics/{session_id}.jsonl`.

!!! note "No performance impact"
    The shell fast-path filter (`.cub/scripts/hooks/cub-hook.sh`) runs first and filters out 90% of irrelevant tool uses in under 10ms. The Python handler only runs for events that matter. You will not notice any latency.

---

## Step 5: Close the Task

When your work is done and tests pass, close the task with a reason:

```bash
cub task close myproj-042 -r "Added input validation with regex patterns, error messages, and unit tests"
```

The reason becomes part of the ledger entry and helps with future retrospectives.

!!! warning "Always close with a reason"
    The `-r` flag is required. A good reason describes *what you accomplished*, not just "done". This text shows up in `cub ledger show` and `cub retro` reports.

---

## Step 6: Verify Recording

After closing the task, confirm the ledger entry was created:

```bash
# View the ledger entry for this task
cub ledger show --task myproj-042

# Check overall data integrity
cub verify
```

The ledger entry should contain:

- Task ID and title
- Session ID
- Files modified
- Git commits made
- Duration
- Closure reason

---

## How It Works

The symbiotic hook pipeline has three stages:

```
Claude Code tool use
        |
        v
+---------------------------+
| Shell Fast-Path Filter    |  .cub/scripts/hooks/cub-hook.sh
| - Checks CUB_RUN_ACTIVE  |  (skips if inside cub run)
| - Filters irrelevant ops  |  (passes ~10% of events through)
+---------------------------+
        |
        v
+---------------------------+
| Python Event Handlers     |  cub.core.harness.hooks
| - Classifies file writes  |  (plans, specs, source code)
| - Detects task commands   |  (cub task claim/close)
| - Detects git commits     |
+---------------------------+
        |
        v
+---------------------------+
| Session Forensics         |  .cub/ledger/forensics/{id}.jsonl
| - Accumulates events      |
| - Synthesizes ledger      |
|   entry on session end    |
+---------------------------+
```

### Double-Tracking Prevention

When you use `cub run`, it sets the `CUB_RUN_ACTIVE` environment variable. The shell fast-path filter checks for this variable and skips all hook processing when it is set. This means:

- **Direct Claude Code session**: Hooks fire, forensics are recorded.
- **Inside `cub run`**: Hooks are silent, the run loop handles tracking.

No duplicate ledger entries, regardless of how you work.

---

## Tips

!!! tip "Mid-session notes"
    Add context to your session while it is in progress:

    ```bash
    cub session log --notes "Discovered the auth module also needs rate limiting. Filing follow-up task."
    ```

!!! tip "Reconcile after the fact"
    If something went wrong with hook tracking (hooks were not installed, session ended abruptly), you can reconstruct the ledger entry from forensics:

    ```bash
    # Reconcile a specific session
    cub reconcile <session-id>

    # Reconcile all unprocessed sessions
    cub reconcile --all

    # Preview without writing
    cub reconcile <session-id> --dry-run
    ```

!!! tip "Enrich with transcript data"
    If you have a Claude Code transcript (exported via the API), you can enrich the ledger entry with token counts and cost:

    ```bash
    cub reconcile <session-id> --transcript /path/to/transcript.jsonl
    ```

!!! tip "Check forensics directly"
    To see the raw event stream for debugging:

    ```bash
    cat .cub/ledger/forensics/<session-id>.jsonl | python3 -m json.tool --json-lines
    ```

---

## Next Steps

- [Hooks System](../guide/hooks/index.md) -- Understand the full hook lifecycle
- [Overnight Batch](overnight-batch.md) -- Automate large task queues with `cub run`
- [Add to Existing Project](existing-project.md) -- Set up hooks in a new project
