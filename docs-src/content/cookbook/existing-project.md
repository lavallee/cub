---
title: "Recipe: Add to Existing Project"
description: Set up Cub in an existing codebase and run your first autonomous task.
---

# Add Cub to an Existing Project

Take any existing codebase -- Python, JavaScript, Go, Rust, or anything else -- and set up Cub to run autonomous coding tasks against it. By the end of this recipe you will have initialized Cub, created your first task, and watched an AI agent complete it.

## What You'll Do

1. Initialize Cub in your project
2. Configure harness and budget defaults
3. Document your project for the AI agent
4. Install symbiotic hooks
5. Create your first task with acceptance criteria
6. Run a single autonomous iteration
7. Review the results
8. Scale up to more tasks

**Time:** ~15 minutes to first completed task.

---

## Prerequisites

- Cub installed and on your PATH:
  ```bash
  cub --version
  ```
- Your project is in a git repository (Cub uses git for state tracking and worktrees)
- At least one AI harness installed:
  ```bash
  claude --version   # Claude Code
  # or: codex --version, gemini --version, opencode --version
  ```

!!! tip "Install Cub if you haven't"
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv tool install cub
    ```

---

## Step 1: Initialize

Navigate to your project and run init:

```bash
cd /path/to/your-project
cub init
```

This creates the following structure:

```
your-project/
├── .cub/
│   ├── config.json        # Project configuration
│   ├── runloop.md         # System prompt for autonomous sessions
│   ├── agent.md           # Project instructions (you edit this)
│   ├── scripts/
│   │   └── hooks/
│   │       └── cub-hook.sh  # Hook fast-path filter
│   └── ledger/            # Completed work records
├── .claude/
│   └── settings.json      # Claude Code hook configuration
└── CLAUDE.md              # Symlink to .cub/agent.md
```

!!! note "First time using Cub?"
    If you have not set up global configuration yet, run `cub init --global` first. This creates `~/.config/cub/config.json` with your default harness, model, and budget preferences.

---

## Step 2: Configure

Open `.cub/config.json` and adjust the defaults for your project:

```json
{
  "harness": "claude",
  "budget": {
    "max_tokens_per_task": 500000,
    "max_total_cost": 25.00
  },
  "state": {
    "require_clean": true,
    "run_tests": true,
    "run_typecheck": false,
    "run_lint": false
  },
  "loop": {
    "max_iterations": 50,
    "on_task_failure": "stop"
  }
}
```

| Setting | Recommendation | Why |
|---------|---------------|-----|
| `harness` | Your preferred AI tool | `"claude"`, `"codex"`, `"gemini"`, or `"opencode"` |
| `require_clean` | `true` | Ensures git state is clean before each task |
| `run_tests` | `true` | Runs your test suite after each task to verify correctness |
| `max_total_cost` | Start low ($10-25) | Safety net while you learn the system |

---

## Step 3: Document Your Project

This is the most important step. The `CLAUDE.md` file (symlinked to `.cub/agent.md`) tells the AI agent how to work in your codebase. Open it and add:

```markdown
# Agent Instructions

## Build & Test

```bash
# Install dependencies
npm install              # or: pip install -e ".[dev]", go mod download, etc.

# Run tests
npm test                 # or: pytest, go test ./..., cargo test

# Type checking (if applicable)
npx tsc --noEmit         # or: mypy src/, etc.

# Linting
npm run lint             # or: ruff check src/, golangci-lint run
```

## Architecture

- `src/api/` -- Express REST API handlers
- `src/services/` -- Business logic layer
- `src/models/` -- Database models (Prisma)
- `tests/` -- Jest test suite

## Conventions

- All API endpoints return JSON
- Use TypeScript strict mode
- Tests required for all new features
- Commits should be atomic and well-described
```

!!! warning "Invest time in CLAUDE.md"
    The quality of your `CLAUDE.md` directly determines the quality of autonomous task output. An agent that knows how to build, test, and navigate your codebase will produce much better results than one working blind. Spend 10 minutes getting this right.

---

## Step 4: Verify Hooks

The `cub init` command installs hooks automatically. Verify they are working:

```bash
cub doctor
```

You should see all hook checks passing. Hooks enable the [symbiotic workflow](direct-session-tracking.md) -- automatic tracking of work done in interactive Claude Code sessions.

---

## Step 5: Create Your First Task

Start with something small and well-defined:

```bash
cub task create "Add input validation to login form" \
  --type task \
  --priority 1 \
  --description "Add client-side and server-side validation to the login form. \
Email field should validate format. Password field should require minimum 8 characters. \
Show inline error messages below each field."
```

!!! tip "Good first tasks"
    Pick a task that is:

    - **Small** -- One file or module, completable in a single iteration
    - **Well-defined** -- Clear success criteria
    - **Testable** -- Has an obvious way to verify correctness
    - **Low-risk** -- Not touching critical infrastructure

    Examples: add a new utility function, write tests for an existing module, fix a straightforward bug, add input validation, update documentation.

### Adding Acceptance Criteria

For JSONL backend tasks, include acceptance criteria in the description:

```bash
cub task create "Add input validation to login form" \
  --type task \
  --priority 1 \
  --description "Add validation to the login form.

Acceptance Criteria:
- Email field validates format using regex
- Password field requires minimum 8 characters
- Invalid fields show red border and error message
- Form cannot submit with invalid fields
- Unit tests cover all validation rules
- All existing tests still pass"
```

---

## Step 6: Test Run

Run a single iteration with streaming output so you can watch what happens:

```bash
cub run --once --stream
```

Here is what Cub does:

1. **Selects** the highest-priority ready task (your new task)
2. **Generates** a prompt from the task description, acceptance criteria, and CLAUDE.md context
3. **Invokes** your AI harness (Claude Code by default)
4. **Monitors** the harness as it reads files, writes code, runs tests, and commits
5. **Detects** completion and records the result in the ledger
6. **Stops** (because you used `--once`)

!!! note "First run may take a few minutes"
    The AI agent needs to read your codebase, understand the architecture, and then implement the changes. A simple task typically takes 2-5 minutes.

---

## Step 7: Review Results

After the run completes, check what happened:

```bash
# See the overall status
cub status

# Check what files changed
git diff HEAD~1 --stat

# View the full diff
git diff HEAD~1

# Check the ledger entry
cub ledger show --limit 1

# Run your test suite manually to double-check
npm test  # or: pytest, go test ./..., etc.
```

If the task succeeded, you should see:

- A new git commit with the changes
- Tests passing
- A ledger entry recording the completion

If it failed, check:

```bash
# Review the task's work
cub review <task-id>

# Check debug logs
cub run --once --task <task-id> --debug
```

---

## Step 8: Scale Up

Once your first task completes successfully, you are ready to expand.

### Create More Tasks

```bash
cub task create "Write unit tests for auth module" --type task --priority 2
cub task create "Add request logging middleware" --type task --priority 2
cub task create "Refactor database connection pooling" --type task --priority 3
```

### Organize with Epics

Group related tasks into epics for better tracking:

```bash
cub task create "API improvements" --type epic --priority 1
# Then set the parent on child tasks
```

### Use the Planning Pipeline for Larger Features

For features that need design before implementation:

```bash
# Run the full planning pipeline
cub plan run

# This walks through:
# 1. Orient   -- Research the problem space
# 2. Architect -- Design the solution
# 3. Itemize  -- Break into agent-sized tasks

# Stage the plan into your task backend
cub stage
```

### Let It Run

```bash
# Run all ready tasks
cub run --stream

# Or with a budget ceiling
cub run --budget 20 --stream
```

---

## Tips

!!! tip "Start with `--model haiku` to save tokens"
    While you are calibrating task descriptions and testing your setup, use the cheapest model:

    ```bash
    cub run --once --model haiku --stream
    ```

    Once you are confident tasks are well-defined, switch to sonnet or opus for better results.

!!! tip "Add build commands first"
    The single most impactful thing in `CLAUDE.md` is accurate build and test commands. If the agent can run your tests, it can verify its own work.

!!! tip "Use `cub suggest` when unsure what to do next"
    ```bash
    cub suggest
    ```

    Cub analyzes your project state and recommends the best next action.

!!! tip "Check in `.cub/` to version control"
    The `.cub/` directory (minus logs and temporary state) should be committed to git. This way your configuration and agent instructions are shared with the team.

    ```bash
    git add .cub/config.json .cub/agent.md .cub/runloop.md
    git commit -m "chore: add cub configuration"
    ```

---

## Next Steps

- [Direct Session Tracking](direct-session-tracking.md) -- Track interactive Claude Code work with hooks
- [Overnight Batch](overnight-batch.md) -- Run large task queues unattended
- [Configuration Reference](../guide/configuration/reference.md) -- Full list of configuration options
- [Core Concepts](../getting-started/concepts.md) -- Understand the architecture
