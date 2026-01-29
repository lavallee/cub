# Cub: Discovery & Help

Welcome to **Cub** - an autonomous AI coding agent for reliable task execution. This meta-skill provides an overview of available capabilities, common commands, and current project status.

## Available Cub Skills

These conversational skills guide you through structured workflows:

| Skill | Description |
|-------|-------------|
| `/cub:capture` | Capture quick ideas, notes, and observations |
| `/cub:spec` | Create a feature specification through interactive interview |
| `/cub:spec-to-issues` | Convert specs into actionable tasks |
| `/cub:orient` | Research and understand the problem space (requirements refinement) |
| `/cub:architect` | Design solution architecture |
| `/cub:itemize` | Break architecture into agent-sized tasks |

**Workflow:** Start with `/cub:capture` for raw ideas, use `/cub:spec` to structure them, then run individual phases (`/cub:orient` → `/cub:architect` → `/cub:itemize`) to generate executable tasks.

## Common CLI Commands

Run these via the Bash tool:

### Planning & Discovery
```bash
cub plan run                # Full planning pipeline (orient → architect → itemize)
cub plan orient             # Research problem space
cub plan architect          # Design solution architecture
cub plan itemize            # Break into agent-sized tasks
cub plan list               # List all plans
```

### Task Execution
```bash
cub run                     # Run autonomous loop until complete
cub run --once              # Single iteration (useful for testing)
cub run --task <id>         # Run specific task
cub run --epic <id>         # Target tasks in specific epic
cub run --stream            # Watch real-time output
```

### Status & Information
```bash
cub status                  # Show task progress summary
cub task ready              # List tasks ready to work on
cub task list               # Show all tasks
cub explain-task <id>       # Show full task details
cub artifacts               # List task outputs
```

### Task Management
```bash
bd ready                    # Show tasks ready to work on (beads backend)
bd show <id>                # View task details
bd update <id> --status in_progress    # Claim a task
bd close <id>               # Mark task complete
bd list --status open       # See remaining open tasks
```

## Execution Modes

Cub supports multiple execution patterns:

### 1. **Conversational Mode** (Claude Code skills)
Interactive sessions using `/cub:*` skills in Claude Code. You're currently in this mode! Structured interviews guide you through planning phases.

### 2. **Structured Planning Mode**
CLI-driven planning pipeline that produces actionable tasks:
- **Orient** → Understand requirements and problem space
- **Architect** → Design technical solution
- **Itemize** → Break into agent-sized chunks with acceptance criteria

### 3. **Supervised Execution**
Run with human oversight:
```bash
cub run --once              # Review after each task
cub run --stream            # Watch in real-time
```

### 4. **Autonomous Execution**
Hands-off execution until budget exhausted or all tasks complete:
```bash
cub run                     # Full autonomous loop
cub run --budget 10         # With cost limit ($USD)
cub run --epic <id>         # Target specific work
```

## Current Project Status

Run `cub status` to see:
- Total tasks (closed, in progress, open)
- Task availability (ready to work, blocked by dependencies)
- Budget & cost summary
- Completion percentage

---

## Quick Start Examples

**New feature workflow:**
```bash
# 1. Start with an idea
/cub:capture
# 2. Turn it into a spec
/cub:spec
# 3. Plan the implementation
cub plan run
# 4. Execute tasks
cub run
```

**Jump right into execution:**
```bash
# View ready tasks
cub task ready
# Run one task
cub run --once
# Run until complete
cub run
```

**Check project health:**
```bash
cub status                  # Task progress
cub artifacts               # View outputs
bd list --status open       # Open tasks
```

## Model Selection

Route tasks to appropriate models for cost efficiency:

- **haiku** - Simple, repetitive work (fast & cheap)
- **sonnet** - Standard development tasks (balanced)
- **opus** - Complex architecture, novel problems (powerful)

```bash
# Label tasks with model preference
bd label add <id> model:haiku
bd label add <id> model:sonnet
bd label add <id> model:opus
```

## Isolation & Safety

```bash
cub run --sandbox           # Docker isolation
cub run --worktree          # Git worktree isolation
cub run --parallel 4        # Run 4 tasks in parallel
```

## Getting Help

- **This skill:** `/cub` - Show this overview
- **CLI help:** `cub --help` or `cub <command> --help`
- **Task backend:** `bd --help` (if using beads)
- **Documentation:** `cub docs` (opens in browser)

---

## Next Steps

**If you're just starting:**
1. Run `/cub:capture` to record your idea
2. Use `/cub:spec` to structure it
3. Run `cub plan run` to generate tasks
4. Execute with `cub run`

**If you have tasks ready:**
1. Check status: `cub status`
2. View ready tasks: `cub task ready`
3. Run loop: `cub run`

**If you need to understand a task:**
1. View details: `cub explain-task <id>`
2. Deep dive: `cub interview <id>`

---

**Pro tip:** Use `cub status` frequently to track progress. The autonomous loop handles dependencies, commits, and structured logging automatically.
