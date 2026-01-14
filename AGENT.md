# Agent Instructions

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

Cub is a CLI tool that wraps AI coding assistants (Claude Code, Codex, etc.) to provide a reliable "set and forget" loop for autonomous coding sessions. It handles task management, clean state verification, budget tracking, and structured logging.

## Tech Stack

- **Language**: Bash (compatible with bash 3.2 on macOS)
- **Test Framework**: BATS (Bash Automated Testing System)
- **Task Management**: Beads (`bd` CLI) - stores tasks in `.beads/issues.jsonl`
- **JSON Processing**: `jq` (required dependency)
- **Harnesses**: Claude Code, Codex (more planned)

## Development Setup

```bash
# No package manager - just bash scripts
# Ensure jq is installed
brew install jq  # or apt-get install jq

# Clone and make scripts executable
chmod +x cub cub-init
```

## Running the Project

```bash
# Run cub in a project directory
./cub

# Single iteration mode
./cub --once

# Specify harness
./cub --harness claude

# Global setup for first-time users
./cub-init --global

# Initialize a project
./cub-init .
```

## Feedback Loops

Run these before committing:

```bash
# Tests (primary feedback loop)
bats tests/*.bats

# No type checking for bash scripts
# shellcheck is recommended but not required:
# shellcheck cub cub-init lib/*.sh
```

## Project Structure

```
├── cub              # Main CLI script
├── cub-init         # Project/global initialization
├── lib/              # Bash libraries
│   ├── xdg.sh        # XDG Base Directory helpers
│   ├── config.sh     # Configuration loading/merging
│   ├── logger.sh     # Structured JSONL logging
│   ├── harness.sh    # Harness abstraction (claude, codex)
│   ├── tasks.sh      # Task management interface
│   └── beads.sh      # Beads backend wrapper
├── tests/            # BATS test files
│   ├── *.bats        # Test suites
│   ├── test_helper.bash  # Common test setup
│   └── fixtures/     # Test fixtures
├── templates/        # Template files
├── .beads/           # Beads task tracking
│   └── issues.jsonl  # Task database
├── progress.txt      # Session learnings
└── AGENT.md          # This file
```

## Key Files

- `cub` - Main entry point, contains the main loop
- `lib/config.sh` - Config loading with precedence: env vars > project > global > defaults
- `lib/logger.sh` - JSONL logging with task_start/end events
- `lib/xdg.sh` - XDG directory helpers for config/data/cache paths
- `lib/harness.sh` - Harness detection and invocation
- `lib/tasks.sh` - Unified task interface (abstracts beads vs JSON backend)
- `lib/cmd_interview.sh` - Interview mode for task specifications (v0.16)

## Interview Mode (v0.16)

The interview command provides deep questioning to refine task specifications:

```bash
# Single task interview
cub interview <task-id>              # Interactive mode
cub interview <task-id> --auto       # AI-generated answers with review

# Batch mode (interview all open tasks)
cub interview --all --auto --skip-review --output-dir specs/interviews

# With task description update
cub interview --all --auto --skip-review --update-task
```

**Batch Processing Features:**
- `--all`: Interview all open tasks automatically
- `--output-dir`: Specify custom output directory (default: specs/)
- `--auto`: Use AI to generate answers
- `--skip-review`: Skip interactive review (for autonomous operation)
- `--update-task`: Append generated specs to task descriptions

Batch mode uses `bd list --status open` to find tasks and processes them sequentially with AI-generated answers.

### Custom Questions Support

Add project-specific interview questions to `.cub.json`:

```json
{
  "interview": {
    "custom_questions": [
      {
        "category": "Project Specific",
        "question": "What is the business impact?",
        "applies_to": ["feature", "task"]
      },
      {
        "category": "Project Specific",
        "question": "What third-party integrations are affected?",
        "applies_to": ["feature"],
        "requires_labels": ["integration"]
      }
    ]
  }
}
```

Custom questions support:
- **applies_to**: Array of task types (feature, task, bugfix) - required
- **requires_labels**: Array of labels - question only appears for tasks with matching labels (optional)
- **requires_tech**: Array of tech stack tags - question only appears when tech stack matches (optional)
- **skip_if**: Conditional skip logic based on previous answers (optional)

## Gotchas & Learnings

- **Bash 3.2 compatibility**: macOS ships with bash 3.2 which has bugs with `${2:-{}}` syntax when the default contains braces. Use explicit if-checks instead.
- **File-based caching**: Bash command substitution creates subshells, so variable modifications aren't preserved. Use temp files for caching (see `config.sh`).
- **Task management**: This project uses `bd` (beads) instead of `prd.json`. Use `bd close <id> -r "reason"` to close tasks.
- **Config precedence**: CLI flags > env vars > project config > global config > hardcoded defaults
- **Test isolation**: BATS tests use `${BATS_TMPDIR}` for temp directories and `PROJECT_ROOT` (from test_helper) for paths.
- **Interview batch mode**: Uses `bd list --status open --json` to enumerate tasks. Processes each task with auto mode and skips review for autonomous operation.

## Common Commands

```bash
# Run all tests
bats tests/*.bats

# Run specific test file
bats tests/config.bats

# List tasks
bd list

# List open tasks
bd list --status open

# Close a task
bd close <task-id> -r "reason"

# View task details
bd show <task-id>
```
