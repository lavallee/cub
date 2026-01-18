---
title: Quick Start
description: Get Cub running in 5 minutes. Initialize a project, create tasks, and run your first autonomous coding session.
---

# Quick Start

Get Cub running in 5 minutes. This guide assumes you've already [installed Cub](install.md).

## Prerequisites Check

Before starting, verify you have:

```bash
# Cub installed and configured
cub --version

# At least one harness available
claude --version   # or codex, gemini, opencode
```

!!! tip "Don't have Claude Code?"
    Install it with: `npm install -g @anthropic-ai/claude-code`

---

## Step 1: Initialize Your Project

Navigate to your project and run the initialization:

```bash
cd my-project
cub init
```

This creates the project structure:

```
my-project/
├── prd.json        # Task backlog
├── PROMPT.md       # System prompt template
├── AGENT.md        # Agent instructions
├── progress.txt    # Session learnings
└── specs/          # Detailed specifications
```

!!! info "First Time?"
    If you haven't run `cub init --global` yet, do that first to set up your global configuration.

---

## Step 2: Create Tasks

You have two options for creating tasks:

### Option A: Use Prep (Recommended)

Let Cub help you turn your ideas into structured tasks:

```bash
cub prep
```

The prep pipeline walks you through:

1. **Triage** - What are you trying to accomplish?
2. **Architect** - What's the technical approach?
3. **Plan** - Break it into agent-sized chunks
4. **Bootstrap** - Write tasks to your backend

!!! tip "Prep Requires Claude Code"
    The `cub prep` pipeline uses Claude Code for the interactive refinement process.

### Option B: Create Tasks Directly

If you already know what needs doing:

=== "Using Beads (Recommended)"

    ```bash
    # Initialize beads in your project
    bd init

    # Create tasks
    bd create "Add user authentication" --type feature --priority 2
    bd create "Create login form component" --type task --priority 2
    bd create "Add JWT token handling" --type task --priority 2

    # View your tasks
    bd list
    ```

=== "Using JSON"

    Edit `prd.json` directly:

    ```json
    {
      "projectName": "my-project",
      "prefix": "myproj",
      "tasks": [
        {
          "id": "myproj-001",
          "type": "feature",
          "title": "Add user authentication",
          "description": "Implement login functionality with JWT tokens",
          "acceptanceCriteria": [
            "Login form renders correctly",
            "JWT tokens are generated on success",
            "Invalid credentials show error message",
            "Tests pass"
          ],
          "priority": "P2",
          "status": "open",
          "dependsOn": []
        }
      ]
    }
    ```

---

## Step 3: Check Status

Before running, see what's ready:

```bash
cub status
```

Output shows:

```
Project: my-project
Backend: beads

Tasks:
  Open:        3
  In Progress: 0
  Closed:      0

Ready to run:
  [P2] myproj-001: Add user authentication
  [P2] myproj-002: Create login form component
```

---

## Step 4: Run the Loop

Start the autonomous execution:

```bash
# Run until all tasks complete
cub run

# Or run a single iteration
cub run --once

# Watch in real-time
cub run --stream
```

Cub will:

1. Pick the highest-priority ready task
2. Generate a prompt from the task details
3. Invoke your AI harness (Claude Code by default)
4. Detect success or failure
5. Loop until done or budget exhausted

---

## Step 5: Monitor Progress

While Cub is running, you can:

```bash
# Check status in another terminal
cub status

# View live dashboard
cub monitor

# Check artifacts after completion
cub artifacts
```

---

## Common Commands Reference

| Command | Description |
|---------|-------------|
| `cub init` | Initialize project |
| `cub init --global` | Set up global config |
| `cub prep` | Run prep pipeline (vision to tasks) |
| `cub status` | Show task progress |
| `cub run` | Run autonomous loop |
| `cub run --once` | Single iteration |
| `cub run --stream` | Run with real-time output |
| `cub run --harness codex` | Use specific harness |
| `cub run --epic my-epic` | Filter to epic's tasks |
| `cub monitor` | Live dashboard |
| `cub artifacts` | View task outputs |
| `cub doctor` | Diagnose issues |

---

## Example Session

Here's a complete example session:

```bash
# Start in your project
cd ~/projects/my-api

# Initialize Cub
cub init

# Create some tasks
bd init
bd create "Add health check endpoint" --type task --priority 1
bd create "Add request logging middleware" --type task --priority 2
bd create "Write API documentation" --type task --priority 3

# Check what's ready
cub status

# Run a single iteration to test
cub run --once --stream

# If that looks good, let it run
cub run --stream

# Check results
cub status
cub artifacts
```

---

## What Happens During a Run?

```
┌─────────────────────────────────────────┐
│              cub run                     │
│                                          │
│  1. Find highest-priority ready task     │
│                    │                     │
│                    ▼                     │
│  2. Generate prompt from task details    │
│                    │                     │
│                    ▼                     │
│  3. Invoke AI harness (claude, codex)    │
│                    │                     │
│                    ▼                     │
│  4. Harness works: edits, tests, commits │
│                    │                     │
│                    ▼                     │
│  5. Task complete? ─── No ──▶ Retry      │
│         │                                │
│         Yes                              │
│         │                                │
│         ▼                                │
│  6. More tasks? ─── Yes ──▶ Loop         │
│         │                                │
│         No                               │
│         │                                │
│         ▼                                │
│      Done!                               │
└─────────────────────────────────────────┘
```

---

## Troubleshooting

### "No harness found"

Install at least one AI harness:

```bash
npm install -g @anthropic-ai/claude-code
```

### "No tasks ready"

Check that you have tasks with `status: "open"` and no unmet dependencies:

```bash
cub status
bd list --status open
```

### "Task keeps failing"

Try running in debug mode to see what's happening:

```bash
cub run --once --debug
```

Check the logs:

```bash
ls ~/.local/share/cub/logs/
```

---

## Next Steps

Now that you have Cub running:

- **[Core Concepts](concepts.md)** - Understand the architecture
- **[Configuration](../guide/configuration/index.md)** - Customize Cub for your workflow
- **[Prep Pipeline](../guide/prep-pipeline/index.md)** - Master the vision-to-tasks flow
- **[AI Harnesses](../guide/harnesses/index.md)** - Learn about different harness options
