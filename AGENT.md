# Agent Instructions

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

Curb is a CLI tool that wraps AI coding assistants (Claude Code, Codex, etc.) to provide a reliable "set and forget" loop for autonomous coding sessions. It handles task management, clean state verification, budget tracking, and structured logging.

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
chmod +x curb curb-init
```

## Running the Project

```bash
# Run curb in a project directory
./curb

# Single iteration mode
./cub --once

# Specify harness
./cub --harness claude

# Global setup for first-time users
./curb-init --global

# Initialize a project
./curb-init .
```

## Feedback Loops

Run these before committing:

```bash
# Tests (primary feedback loop)
bats tests/*.bats

# No type checking for bash scripts
# shellcheck is recommended but not required:
# shellcheck curb curb-init lib/*.sh
```

## Project Structure

```
├── curb              # Main CLI script
├── curb-init         # Project/global initialization
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

- `curb` - Main entry point, contains the main loop
- `lib/config.sh` - Config loading with precedence: env vars > project > global > defaults
- `lib/logger.sh` - JSONL logging with task_start/end events
- `lib/xdg.sh` - XDG directory helpers for config/data/cache paths
- `lib/harness.sh` - Harness detection and invocation
- `lib/tasks.sh` - Unified task interface (abstracts beads vs JSON backend)

## Gotchas & Learnings

- **Bash 3.2 compatibility**: macOS ships with bash 3.2 which has bugs with `${2:-{}}` syntax when the default contains braces. Use explicit if-checks instead.
- **File-based caching**: Bash command substitution creates subshells, so variable modifications aren't preserved. Use temp files for caching (see `config.sh`).
- **Task management**: This project uses `bd` (beads) instead of `prd.json`. Use `bd close <id> -r "reason"` to close tasks.
- **Config precedence**: CLI flags > env vars > project config > global config > hardcoded defaults
- **Test isolation**: BATS tests use `${BATS_TMPDIR}` for temp directories and `PROJECT_ROOT` (from test_helper) for paths.

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
