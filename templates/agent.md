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

# View recent hook activity (diagnostic)
cub hooks log --limit 10

# Re-install hooks if needed
cub init
```

### Hook Forensics

When Claude Code hooks are installed, session activity is automatically logged to `.cub/ledger/forensics/` as JSONL files. These forensics are auto-generated by hooks and should not be manually edited.

**Location:** `.cub/ledger/forensics/{session_id}.jsonl`

**JSONL Schema:**

Each line is a JSON object with common fields:
- `event_type`: Type of event (see below)
- `timestamp`: ISO 8601 timestamp of when event occurred
- `session_id`: Claude Code session identifier

**Event Types:**

| Event Type | Description | Additional Fields |
|------------|-------------|-------------------|
| `session_start` | Session began | `cwd` |
| `file_write` | File created or modified | `file_path`, `tool_name`, `file_category` |
| `task_claim` | Task marked in-progress | `task_id`, `command` |
| `task_close` | Task marked closed | `task_id`, `command`, `reason` |
| `git_commit` | Commit created | `command`, `message_preview` |
| `session_end` | Session completed | `transcript_path` |
| `session_checkpoint` | Session compacted | `reason` |

**Example JSONL contents:**
```json
{"event_type": "session_start", "timestamp": "2026-01-28T12:54:31.834779+00:00", "session_id": "claude-20260128-125431", "cwd": "/home/user/myproject"}
{"event_type": "task_claim", "timestamp": "2026-01-28T12:55:02.123456+00:00", "session_id": "claude-20260128-125431", "task_id": "proj-abc.1", "command": "cub task claim proj-abc.1"}
{"event_type": "file_write", "timestamp": "2026-01-28T12:58:15.789012+00:00", "session_id": "claude-20260128-125431", "file_path": "/home/user/myproject/src/feature.py", "tool_name": "Write", "file_category": "source"}
{"event_type": "git_commit", "timestamp": "2026-01-28T13:02:45.456789+00:00", "session_id": "claude-20260128-125431", "command": "git commit -m \"feat: add new feature\"", "message_preview": "feat: add new feature"}
{"event_type": "session_end", "timestamp": "2026-01-28T13:05:00.000000+00:00", "session_id": "claude-20260128-125431", "transcript_path": "/home/user/.claude/sessions/123.jsonl"}
```

**View forensics with `cub hooks log`:**
```bash
cub hooks log                      # Show last 20 events
cub hooks log --limit 50           # Show last 50 events
cub hooks log --session <id>       # Filter by session ID
cub hooks log --type file_write    # Filter by event type
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
