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
│   ├── beads.sh      # Beads backend wrapper
│   ├── branches.sh   # Branch-epic binding management (v0.19)
│   ├── checkpoints.sh # Checkpoint/gate management (v0.19)
│   ├── cmd_branch.sh  # Branch commands (v0.19)
│   ├── cmd_checkpoint.sh # Checkpoint commands (v0.19)
│   └── cmd_pr.sh      # PR commands (v0.19)
├── tests/            # BATS test files
│   ├── *.bats        # Test suites
│   ├── test_helper.bash  # Common test setup
│   └── fixtures/     # Test fixtures
├── templates/        # Template files
├── .beads/           # Beads task tracking
│   ├── issues.jsonl  # Task database
│   └── branches.yaml # Branch-epic bindings (v0.19)
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

## Git Workflow Integration (v0.19)

v0.19 adds branch-epic bindings, checkpoints, and PR management:

### Branch Management

```bash
# Create and bind a branch to an epic
cub branch cub-vd6                    # Create new branch
cub branch cub-vd6 --bind-only        # Bind current branch
cub branch cub-vd6 --name feature/v19 # Custom branch name

# List all branch bindings
cub branches
cub branches --status active
cub branches --json

# Cleanup merged branches
cub branches --cleanup

# Sync branch status with git
cub branches --sync

# Remove binding
cub branches --unbind cub-vd6
```

Branch bindings are stored in `.beads/branches.yaml`.

### Checkpoints

Checkpoints are review/approval gates that block downstream tasks:

```bash
# Create a checkpoint (gate type in beads)
bd create "Review: feature complete" --type gate

# List checkpoints
cub checkpoints
cub checkpoints --epic cub-vd6
cub checkpoints --blocking

# Approve a checkpoint (unblocks dependent tasks)
cub checkpoints approve <checkpoint-id>
```

When running `cub run`, tasks blocked by unapproved checkpoints are skipped.

### Pull Request Management

```bash
# Create PR for an epic
cub pr cub-vd6
cub pr cub-vd6 --draft
cub pr cub-vd6 --push          # Push branch first
cub pr cub-vd6 --base develop  # Target branch

# PR body is auto-generated from epic's completed tasks
```

Requirements:
- Epic must have a bound branch
- Branch must be pushed to remote
- GitHub CLI (`gh`) must be installed and authenticated

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

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
