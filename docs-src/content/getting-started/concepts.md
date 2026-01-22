---
title: Core Concepts
description: Understand Cub's architecture - the prep and run workflow, task backends, AI harnesses, the autonomous loop, and configuration hierarchy.
---

# Core Concepts

This page explains how Cub works and how all the pieces fit together.

## The Two Main Events

Cub's workflow is built around two distinct phases:

<div class="workflow-grid" markdown>

<div class="workflow-card prep" markdown>

### Prep: Vision to Tasks

**When:** Starting new work, refining requirements

**Purpose:** Transform ideas into structured, agent-ready tasks

**Commands:** `cub prep`, `cub triage`, `cub architect`, `cub plan`, `cub bootstrap`

</div>

<div class="workflow-card run" markdown>

### Run: Tasks to Code

**When:** Executing prepared work

**Purpose:** Autonomously complete tasks using AI

**Commands:** `cub run`, `cub run --once`, `cub status`

</div>

</div>

### Why Two Phases?

The separation exists because different work benefits from different approaches:

| Phase | You Provide | Cub Does | Result |
|-------|-------------|----------|--------|
| **Prep** | Ideas, requirements, context | Guided refinement, structured decomposition | Clear, agent-sized tasks |
| **Run** | Ready tasks | Autonomous execution, monitoring | Working code |

This lets you invest time *before* code starts flying, making the autonomous execution more reliable.

---

## Task Backends

Cub supports two ways to manage tasks:

### Beads Backend (Recommended)

Uses the [beads](https://github.com/steveyegge/beads) CLI for advanced task management:

```bash
# Initialize
bd init

# Create tasks
bd create "Implement feature" --type feature --priority 2

# View tasks
bd list
bd show cub-abc

# Close tasks
bd close cub-abc -r "Completed with tests"
```

**Advantages:**

- Rich CLI for task management
- Built-in epic and dependency support
- Labels for filtering and model selection
- Branch-epic bindings

**When to use:** Production projects, team workflows, complex dependency chains

### JSON Backend

Simple file-based storage in `prd.json`:

```json
{
  "projectName": "my-project",
  "prefix": "myproj",
  "tasks": [
    {
      "id": "myproj-001",
      "type": "task",
      "title": "Add feature",
      "description": "Description here",
      "acceptanceCriteria": ["Tests pass"],
      "priority": "P2",
      "status": "open",
      "dependsOn": []
    }
  ]
}
```

**Advantages:**

- No additional tools needed
- Easy to version control
- Simple to understand

**When to use:** Quick experiments, small projects, learning Cub

### Backend Auto-Detection

Cub automatically selects the backend:

1. If `.beads/` directory exists -> Beads backend
2. Otherwise -> JSON backend

Override with the `CUB_BACKEND` environment variable:

```bash
CUB_BACKEND=json cub run
CUB_BACKEND=beads cub run
```

---

## AI Harnesses

A "harness" is Cub's abstraction over AI coding CLIs. Each harness wraps a different tool:

| Harness | Tool | Best For |
|---------|------|----------|
| `claude` | Claude Code | General coding, complex refactoring, multi-file changes |
| `codex` | OpenAI Codex CLI | Quick fixes, OpenAI ecosystem |
| `gemini` | Google Gemini CLI | Alternative perspective |
| `opencode` | OpenCode CLI | Open-source option |

### Harness Selection

Cub selects a harness using this priority:

1. **CLI flag:** `cub run --harness claude`
2. **Environment variable:** `HARNESS=codex cub run`
3. **Config priority:** `harness.priority` in config file
4. **Default order:** claude > opencode > codex > gemini

### Per-Task Model Selection

You can route tasks to specific models using labels:

```bash
# Fast model for simple tasks
bd label add cub-abc model:haiku

# Balanced model for most tasks
bd label add cub-xyz model:sonnet

# Most capable model for complex work
bd label add cub-123 model:opus
```

This helps manage token costs by using the right model for each task's complexity.

---

## The Autonomous Loop

When you run `cub run`, here's what happens:

```
┌──────────────────────────────────────────┐
│               cub run                     │
│                                           │
│  ┌─────────────────────────────────┐     │
│  │      1. Find Ready Task          │     │
│  │  - status == "open"              │     │
│  │  - dependencies satisfied        │     │
│  │  - highest priority first        │     │
│  └───────────────┬─────────────────┘     │
│                  │                        │
│                  ▼                        │
│  ┌─────────────────────────────────┐     │
│  │      2. Generate Prompt          │     │
│  │  - System prompt (PROMPT.md)     │     │
│  │  - Task details + criteria       │     │
│  │  - Agent instructions (AGENT.md) │     │
│  └───────────────┬─────────────────┘     │
│                  │                        │
│                  ▼                        │
│  ┌─────────────────────────────────┐     │
│  │      3. Execute Harness          │     │
│  │  - Invoke claude/codex/gemini    │     │
│  │  - Stream or capture output      │     │
│  │  - Track tokens                  │     │
│  └───────────────┬─────────────────┘     │
│                  │                        │
│                  ▼                        │
│  ┌─────────────────────────────────┐     │
│  │      4. Detect Completion        │     │
│  │  - Check task status             │     │
│  │  - Verify acceptance criteria    │     │
│  │  - Handle success/failure        │     │
│  └───────────────┬─────────────────┘     │
│                  │                        │
│            ┌─────┴─────┐                  │
│            ▼           ▼                  │
│        Success      Failure              │
│            │           │                  │
│            ▼           ▼                  │
│     More tasks?   Retry/Skip             │
│            │           │                  │
│       ┌────┴────┐      │                  │
│       ▼         ▼      │                  │
│      Yes       No ◄────┘                  │
│       │         │                         │
│       ▼         ▼                         │
│     Loop      Done                        │
└──────────────────────────────────────────┘
```

### Task Selection Algorithm

1. Find tasks where `status == "open"`
2. Filter to tasks where all `dependsOn` items are `closed`
3. Sort by priority (P0 first, then P1, P2, P3, P4)
4. Pick the first one

### Completion Detection

The harness signals completion by:

1. Closing the task (via `bd close` or updating `prd.json`)
2. Outputting `<promise>COMPLETE</promise>` when all work is done

---

## Project Structure

After `cub init`, your project contains:

```
my-project/
├── prd.json        # Task backlog (JSON backend)
├── .beads/         # Task data (Beads backend)
├── PROMPT.md       # System prompt template
├── AGENT.md        # Build/run instructions
├── AGENTS.md       # Symlink to AGENT.md (Codex compatibility)
├── progress.txt    # Session learnings (agent appends)
├── fix_plan.md     # Discovered issues
├── specs/          # Detailed specifications
└── .cub/           # Runtime data
    ├── hooks/      # Project-specific hooks
    └── runs/       # Run artifacts
```

### Key Files

| File | Purpose |
|------|---------|
| `prd.json` | Task backlog (JSON backend) |
| `PROMPT.md` | System prompt sent to the AI |
| `AGENT.md` | Instructions on running tests, building, etc. |
| `progress.txt` | Memory across iterations - patterns, gotchas |
| `specs/` | Detailed specifications for complex tasks |

### Artifacts Directory

Each run creates artifacts in `.cub/runs/{session}/`:

```
.cub/runs/porcupine-20260111-114543/
├── run.json                    # Run metadata
└── tasks/
    └── cub-abc/
        ├── task.json           # Execution details
        ├── summary.md          # AI-generated summary
        └── changes.patch       # Git diff
```

---

## Configuration Hierarchy

Cub uses layered configuration with clear precedence:

```
Priority (highest to lowest):
┌─────────────────────────────────────────┐
│  1. CLI flags                            │
│     cub run --harness claude             │
├─────────────────────────────────────────┤
│  2. Environment variables                │
│     HARNESS=codex CUB_BUDGET=500000      │
├─────────────────────────────────────────┤
│  3. Project config                       │
│     ./.cub.json                          │
├─────────────────────────────────────────┤
│  4. Global config                        │
│     ~/.config/cub/config.json            │
├─────────────────────────────────────────┤
│  5. Hardcoded defaults                   │
│     (built into Cub)                     │
└─────────────────────────────────────────┘
```

### Example Configuration

**Global** (`~/.config/cub/config.json`):

```json
{
  "harness": {
    "default": "auto",
    "priority": ["claude", "codex"]
  },
  "budget": {
    "default": 1000000,
    "warn_at": 0.8
  }
}
```

**Project** (`.cub.json`):

```json
{
  "budget": {
    "default": 500000
  },
  "loop": {
    "max_iterations": 50
  }
}
```

The project config overrides global for `budget.default` and `loop.max_iterations`, but inherits `harness` settings.

---

## Hooks System

Hooks let you run custom scripts at lifecycle points:

```
Loop Start ──▶ pre-loop
                  │
              ┌───┴───┐
              │ Tasks │
              └───┬───┘
                  │
         ┌───────┴───────┐
         ▼               ▼
     pre-task        (for each)
         │
         ▼
    Execute Task
         │
    ┌────┴────┐
    ▼         ▼
 Success   Failure ──▶ on-error
    │         │
    └────┬────┘
         ▼
    post-task
         │
    └────┴────┘
              │
              ▼
         post-loop
              │
              ▼
         Loop End
```

### Hook Locations

| Priority | Location | Scope |
|----------|----------|-------|
| 1 | `~/.config/cub/hooks/{hook}.d/` | All projects |
| 2 | `./.cub/hooks/{hook}.d/` | Current project |

All executable scripts in these directories run in sorted order.

### Context Variables

Hooks receive context via environment variables:

| Variable | Available In | Description |
|----------|--------------|-------------|
| `CUB_HOOK_NAME` | All | Hook being executed |
| `CUB_PROJECT_DIR` | All | Project directory |
| `CUB_SESSION_ID` | pre/post-loop | Unique session ID |
| `CUB_TASK_ID` | task hooks | Current task ID |
| `CUB_EXIT_CODE` | post-task, on-error | Task exit code |

---

## Budget and Guardrails

Cub provides safety mechanisms to prevent runaway execution:

### Token Budget

Track and limit token usage:

```json
{
  "budget": {
    "default": 1000000,
    "warn_at": 0.8
  }
}
```

### Iteration Limits

Prevent infinite loops:

```json
{
  "guardrails": {
    "max_task_iterations": 3,
    "max_run_iterations": 50
  }
}
```

### Failure Handling

Configure behavior on task failure:

| Mode | Behavior |
|------|----------|
| `stop` | Stop immediately |
| `move-on` | Mark failed, continue |
| `retry` | Retry with context |
| `triage` | Human intervention |

---

## Next Steps

Now that you understand the concepts:

- **[Configuration Guide](../guide/configuration/index.md)** - Customize Cub
- **[Prep Pipeline](../guide/prep-pipeline/index.md)** - Master vision-to-tasks
- **[Run Loop](../guide/run-loop/index.md)** - Deep dive on execution
- **[AI Harnesses](../guide/harnesses/index.md)** - Harness details
