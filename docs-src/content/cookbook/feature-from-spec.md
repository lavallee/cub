---
title: "Recipe: Feature from Spec"
description: Complete workflow for building a feature from initial idea through planning, execution, and delivery.
---

# Build a Feature from Spec to Ship

## What You'll Do

Start with a feature idea, run it through Cub's planning pipeline to produce well-scoped tasks, execute those tasks autonomously, and ship the result. This is the full Cub workflow for medium-to-large features.

**Time estimate:** 1--4 hours depending on feature complexity (mostly autonomous execution time).

---

## Prerequisites

- `cub init` completed in your project
- At least one harness available (`claude --version`, `codex`, etc.)
- A clean git working tree

---

## Step 1: Create a Spec

A spec captures your feature idea in enough detail for the planning pipeline to work with. You can create one interactively or write it by hand.

### Option A: Interactive interview

```bash
cub spec "user authentication with OAuth2"
```

Cub asks clarifying questions about scope, constraints, and success criteria, then writes a spec file to `specs/researching/`.

### Option B: Write manually

Create a markdown file in `specs/researching/`:

```bash
mkdir -p specs/researching
```

```markdown
<!-- specs/researching/oauth2-auth.md -->
---
id: spec-oauth2-auth
title: OAuth2 Authentication
status: researching
---

# OAuth2 Authentication

## Problem
Users must currently create accounts with email/password. We want to support
Google and GitHub OAuth2 login to reduce friction.

## Requirements
- Google OAuth2 login flow
- GitHub OAuth2 login flow
- Link OAuth accounts to existing email accounts
- Fallback to email/password remains available

## Constraints
- Must work with existing session middleware
- No additional database migrations beyond a provider column
- Must pass existing auth test suite
```

---

## Step 2: Orient

Research the problem space. The orient stage analyzes your spec against the existing codebase, surfaces constraints, and identifies open questions.

```bash
cub plan orient specs/researching/oauth2-auth.md
```

Cub produces `plans/oauth2-auth/orientation.md` containing:

- Summary of the problem and current state
- Codebase analysis (relevant files, patterns, dependencies)
- Open questions and risks
- Requirements clarification

Review the orientation and address any open questions before proceeding.

---

## Step 3: Architect

Design the technical approach. The architect stage proposes components, interfaces, and an implementation strategy.

```bash
cub plan architect
```

Cub produces `plans/oauth2-auth/architecture.md` containing:

- Component breakdown (what to build)
- Interface contracts (how pieces connect)
- Technology choices and rationale
- Implementation phases

!!! tip "Use `--model opus` for architecture"
    Complex design decisions benefit from the most capable model:
    ```bash
    cub plan architect --model opus
    ```

Review the architecture. This is the most important review point -- task execution quality depends on good architecture.

---

## Step 4: Itemize

Break the architecture into agent-sized tasks. Each task should be completable by an AI harness in a single session.

```bash
cub plan itemize
```

Cub produces `plans/oauth2-auth/itemized-plan.md` containing:

- Epics grouping related tasks
- Individual tasks with titles, descriptions, and acceptance criteria
- Dependency ordering between tasks
- Priority assignments and effort estimates

---

## Step 5: Stage

Import the tasks from the plan into the task backend so Cub can execute them.

```bash
# Preview what will be created
cub stage --dry-run

# Import tasks
cub stage
```

This creates tasks in the backend, generates runtime prompt context in `plans/oauth2-auth/prompt-context.md`, and moves the spec from `researching/` to `staged/`.

Verify the tasks were created:

```bash
cub task list
```

---

## Step 6: Review Tasks

Before running, review the generated tasks. Adjust priorities, clarify descriptions, or add acceptance criteria where needed.

```bash
# List all tasks in the epic
cub task list --status open

# Show details for a specific task
cub task show myapp-oauth-1.1

# Show full description including acceptance criteria
cub task show myapp-oauth-1.1 --full
```

This is your last chance to refine scope before execution begins.

---

## Step 7: Run

Execute all tasks in the epic. Cub picks tasks in dependency and priority order, generates prompts, and invokes the harness for each one.

```bash
cub run --epic myapp-oauth
```

Cub will:

1. Select the highest-priority ready task (no unmet dependencies).
2. Generate a prompt including task details, plan context, and epic context.
3. Invoke the harness, which edits files, runs tests, and commits.
4. Record the result in the ledger.
5. Repeat until all tasks in the epic are complete or the budget is exhausted.

!!! tip "Budget limits"
    Set a budget to prevent runaway costs:
    ```bash
    cub run --epic myapp-oauth --budget 20
    ```

!!! tip "Route simple tasks to cheaper models"
    Use `--model haiku` for straightforward implementation tasks and save opus for complex ones. You can also configure per-task model overrides in the task backend.

---

## Step 8: Monitor Progress

While Cub is running, check on progress from another terminal.

```bash
# Quick status overview
cub status

# Live dashboard with real-time updates
cub monitor

# Ledger statistics (cost, tokens, duration)
cub ledger stats

# Check a specific task's result
cub task show myapp-oauth-1.3
```

If a task fails, Cub will either retry it or move on depending on your `on_task_failure` configuration. Check the ledger for details:

```bash
cub ledger show --recent 5
```

---

## Step 9: Review and Ship

Once all tasks are complete, review the full body of work.

```bash
# Review the entire epic
cub review myapp-oauth --epic

# Check the diff against main
git diff main

# Run the full test suite
pytest tests/ -v

# Run type checking
mypy src/
```

Create a pull request for the epic:

```bash
# Bind a branch if you have not already
cub branch myapp-oauth

# Push and create PR
cub pr myapp-oauth --push
```

The PR body is auto-generated from the completed tasks, including what was done, which files changed, and acceptance criteria status.

---

## Step 10: Retrospective

After shipping, run a retrospective to extract lessons learned.

```bash
cub retro myapp-oauth --epic
```

The retro report includes:

- Executive summary and timeline
- Metrics: total cost, tokens used, duration per task
- Task outcomes (success, retry count, failure reasons)
- Key decisions made during execution
- Lessons learned and recommendations

Save it for future reference:

```bash
cub retro myapp-oauth --epic --output retro-oauth.md
```

You can also extract patterns across multiple features:

```bash
cub learn extract --since 30
```

---

## Tips

- **Review architecture thoroughly.** The architect stage is the highest-leverage review point. Weak architecture leads to rework across many tasks.

- **Use `--model opus` for orient and architect.** Planning benefits from the strongest reasoning. Switch to haiku or sonnet for routine implementation tasks to save cost:
    ```bash
    cub plan orient specs/researching/oauth2-auth.md --model opus
    cub plan architect --model opus
    cub run --epic myapp-oauth --model sonnet
    ```

- **Set budget limits.** For a 10-task epic, a $20 budget is a reasonable starting point. Adjust based on task complexity:
    ```bash
    cub run --epic myapp-oauth --budget 20
    ```

- **Stage with `--dry-run` first.** Always preview what `cub stage` will create before committing to it.

- **Monitor early.** Check `cub status` after the first task completes to make sure things are going in the right direction. It is cheaper to course-correct after one task than after ten.

- **Use the ledger.** `cub ledger stats` gives you cost and duration breakdowns. Use this data to estimate future features and set better budgets.

---

## Next Steps

- [Bug Fix to PR](bug-fix-to-pr.md) -- For quick, single-task fixes
- [Plan Pipeline](../guide/plan-pipeline/index.md) -- Detailed documentation for each planning stage
- [Budget and Guardrails](../guide/budget/index.md) -- Control costs and prevent runaway loops
- [The Run Loop](../guide/run-loop/index.md) -- How Cub selects and executes tasks
