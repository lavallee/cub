# Agent Instructions

This file contains instructions for building, running, and developing this project.
Update this file as you learn new things about the codebase.

## Project Overview

<!-- Brief description of your project -->

## Tech Stack

- **Language**:
- **Framework**:
- **Database**:

## Development Setup

```bash
# Setup commands here
```

## Running the Project

```bash
# Run commands here
```

## Feedback Loops

Run these before committing:

```bash
# Tests
# Type checking
# Linting
```

---

## Cub Task Workflow

This project uses [cub](https://github.com/lavallee/cub) for autonomous task management.

**Key files:**
- **@.cub/agent.md** - This file (project instructions)
- **@.cub/map.md** - Codebase structure map
- **@.cub/constitution.md** - Project principles and guidelines

### Quick Start Workflow

1. **Find work**: `cub task ready --agent` to see tasks with no blockers
2. **Understand context**: `cub task show <id> --full` for full details
3. **Claim task**: `cub task claim <id>` to mark it in-progress
4. **Do the work**: Implement, test, and verify using Feedback Loops above
5. **Complete task**: `cub task close <id> -r "what you accomplished"`

**Pro tips:**
- Always pass `--agent` flag for markdown output optimized for LLM consumption
- Use `--all` to disable truncation when you need complete lists
- Run `cub suggest --agent` for smart recommendations on what to do next

### Finding Work

```bash
cub task ready --agent              # Ready tasks (no blockers)
cub task list --status open --agent # All open tasks
cub task show <id> --full           # Full task details with description
cub suggest --agent                 # Smart suggestions for next action
cub status --agent                  # Project progress overview
```

### Working on Tasks

```bash
cub task claim <id>               # Claim a task (mark in-progress)
cub run --task <id>               # Run autonomous loop for a task
cub run --epic <id>               # Run all tasks in an epic
cub run --once                    # Single iteration
```

### Completing Tasks

```bash
cub task close <id> -r "reason"   # Close with completion reason
```

**Important:** Always run your feedback loops (tests, lint, typecheck) BEFORE closing a task.

### Planning

```bash
cub capture "idea"                # Quick capture
cub spec                          # Create feature spec
cub plan run                      # Plan implementation
cub stage <plan-slug>             # Import tasks from plan
```

---

## Common Command Patterns

### Task Discovery and Selection

```bash
# See what's ready to work on
cub task ready --agent            # Tasks with no blockers
cub task blocked --agent          # Tasks blocked by dependencies
cub task list --parent <epic> --agent  # Tasks in specific epic

# Get context before starting
cub task show <id> --full         # Full description and metadata
cub status --agent -v             # Verbose project status
```

### Run Loop Commands

```bash
# Start autonomous execution
cub run                           # Run until all tasks complete
cub run --once                    # Single iteration (recommended for direct work)
cub run --task <id>               # Run specific task
cub run --epic <id>               # Target tasks within epic

# Options
cub run --stream                  # Stream harness activity in real-time
cub run --debug                   # Verbose debug logging
cub run --monitor                 # Launch live dashboard
```

### Status and Monitoring

```bash
# Project status
cub status --agent                # Show task progress (markdown)
cub status --json                 # JSON output for scripting
cub suggest --agent               # Get smart suggestions for next actions

# Live monitoring
cub monitor                       # Live dashboard
```

### Session Tracking

```bash
# Track work in direct harness sessions
cub session log                   # Log current work
cub session done                  # Mark session complete
cub session wip                   # Mark session as work-in-progress

# View completed work
cub ledger show                   # View completion ledger
cub ledger stats                  # Show statistics
```

---

## Reading Task Output

When you run `cub task show <id> --full`, you'll see structured task metadata. Here's how to interpret it:

### Task Fields

| Field | Meaning |
|-------|---------|
| **id** | Unique task identifier (e.g., `project-abc.1`) |
| **title** | Short task title |
| **description** | Full task requirements and acceptance criteria |
| **status** | `open`, `in_progress`, or `closed` |
| **type** | `task`, `epic`, `gate` (checkpoint), or `bug` |
| **parent** | Epic this task belongs to (if any) |
| **blocks** | Other tasks this one blocks |
| **blocked_by** | Tasks that must complete before this one |
| **labels** | Tags for categorization |

### Understanding Blockers

Tasks can be blocked by:
- **Other tasks**: Listed in `blocked_by` field - these must complete first
- **Checkpoints**: Gate-type tasks requiring human approval
- **Missing dependencies**: External requirements not yet met

Use `cub task blocked --agent` to see all blocked tasks and their blockers.

### Epic-Task Relationships

- The `parent` field links tasks to their parent epic
- Use `cub task list --parent <epic-id>` to see all tasks in an epic
- Epics provide context - check the epic's description for overall goals

---

## Troubleshooting

### Common Issues

**Tasks not showing up?**
```bash
cub doctor --agent                # Run diagnostics
cub task list --all --agent       # List all tasks without filters
```

**Hook issues?**
```bash
# Verify hooks are installed
cub doctor --agent

# Check hook script is executable
ls -la .cub/scripts/hooks/

# Re-install hooks if needed
cub init
```

### Forensics and Debugging

Session activity is logged to `.cub/ledger/forensics/` as JSONL files:

```
.cub/ledger/forensics/
├── {session_id}.jsonl            # Events from each session
```

Each forensics file contains events like:
- `session_start` - Session began
- `file_write` - Files modified
- `task_claim` - Task claimed
- `git_commit` - Commits made
- `session_end` - Session completed

**View recent forensics:**
```bash
ls -lt .cub/ledger/forensics/ | head  # Recent sessions
cat .cub/ledger/forensics/{session}.jsonl | head  # View events
```

### Getting Help

```bash
cub --help                        # All available commands
cub <command> --help              # Help for specific command
cub docs                          # Open documentation in browser
```

---

## Git Workflow

- Feature branches per epic: `cub branch <epic-id>`
- Pull requests: `cub pr <epic-id>`
- Merge: `cub merge <pr-number>`

---

## Gotchas & Learnings

<!-- Add project-specific conventions, pitfalls, and decisions here -->

---

## Common Commands

```bash
# Add frequently used commands here
```

---

## Additional Resources

- **Full documentation**: Run `cub docs` to open in browser
- **Project map**: See @.cub/map.md for codebase structure
- **Principles**: See @.cub/constitution.md for project guidelines
- **Task backend**: Tasks stored in `.cub/tasks.jsonl` (JSONL format)
- **Session logs**: Forensics in `.cub/ledger/forensics/`

### When Stuck

If genuinely blocked (missing files, unclear requirements, external blocker):
```xml
<stuck>Clear description of the blocker</stuck>
```

This signals the autonomous loop to stop gracefully rather than consuming budget on a blocked task.
