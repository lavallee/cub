# Agent Instructions

This file contains instructions for building and running the Cub project.
Update this file as you learn new things about the codebase.

## Project Overview

Cub is a Python-based CLI tool that wraps AI coding assistants (Claude Code, Codex, Gemini, etc.) to provide a reliable "set and forget" loop for autonomous coding sessions. It handles task management, clean state verification, budget tracking, and structured logging.

## Tech Stack

- **Language**: Python 3.10+
- **CLI Framework**: Typer (for subcommands and type-safe CLI)
- **Data Models**: Pydantic v2 (validation and serialization)
- **Terminal UI**: Rich (progress bars, tables, live output)
- **Test Framework**: pytest with pytest-mock
- **Type Checking**: mypy (strict mode)
- **Linting**: ruff
- **Task Management**: Beads CLI (`bd`) - stores tasks in `.beads/issues.jsonl`
- **Harnesses**: Claude Code, Codex, Google Gemini, OpenCode

## Development Setup

```bash
# Using uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Or using pip
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the Project

```bash
# Run cub from source (after setup)
cub --help

# Single iteration mode
cub run --once

# Specify harness
cub run --harness claude

# Global setup for first-time users
cub init --global

# Initialize a project
cub init
```

## Feedback Loops

Run these before committing:

```bash
# Type checking
mypy src/cub

# Tests (primary feedback loop)
pytest tests/ -v

# Linting
ruff check src/ tests/

# Code formatting
ruff format src/ tests/
```

## Project Structure

```
├── src/cub/              # Main package
│   ├── cli/              # Typer CLI subcommands
│   │   ├── __init__.py
│   │   ├── app.py        # Main Typer app
│   │   ├── run.py        # cub run subcommand
│   │   ├── status.py     # cub status subcommand
│   │   ├── init.py       # cub init subcommand
│   │   └── ...          # Other subcommands
│   ├── core/             # Core logic (independent of CLI)
│   │   ├── config.py     # Configuration loading/merging
│   │   ├── models.py     # Pydantic models (Task, Config, etc.)
│   │   ├── tasks/        # Task backends
│   │   │   ├── backend.py    # Task backend interface (Protocol)
│   │   │   ├── beads.py      # Beads backend implementation
│   │   │   └── json.py       # JSON backend implementation
│   │   ├── harness/      # AI harness backends
│   │   │   ├── backend.py    # Harness interface (Protocol)
│   │   │   ├── claude.py     # Claude Code harness
│   │   │   ├── codex.py      # OpenAI Codex harness
│   │   │   ├── gemini.py     # Google Gemini harness
│   │   │   └── opencode.py   # OpenCode harness
│   │   ├── logger.py     # JSONL structured logging
│   │   └── git_utils.py  # Git operations
│   ├── utils/            # Utilities
│   │   ├── hooks.py      # Hook execution system
│   │   ├── status.py     # Status display (Rich tables)
│   │   └── ...
│   ├── __init__.py
│   ├── __main__.py       # Entry point for python -m cub
│   └── cli.py            # Main app factory
├── tests/                # pytest test suite
│   ├── test_*.py         # Test files
│   ├── conftest.py       # pytest fixtures and configuration
│   └── fixtures/         # Test data files
├── .beads/              # Beads task tracking
│   ├── issues.jsonl     # Task database
│   └── branches.yaml    # Branch-epic bindings
├── pyproject.toml       # Python project metadata and config
├── README.md            # User documentation
├── UPGRADING.md         # Migration guide from Bash version
└── CLAUDE.md            # This file (agent instructions)
```

## Key Modules

- `cub.cli.app` - Main Typer CLI application
- `cub.core.config` - Configuration loading with precedence: env vars > project > global > defaults
- `cub.core.models` - Pydantic data models (Task, Config, RunMetadata, etc.)
- `cub.core.logger` - JSONL logging with structured events
- `cub.core.tasks.backend` - Abstract task backend interface
- `cub.core.harness.backend` - Abstract harness interface
- `cub.utils.hooks` - Hook execution system

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

- **Python 3.10+**: Cub requires Python 3.10+ for features like match statements and type unions (`|` syntax)
- **Pydantic v2**: Models use Pydantic v2 API with `model_validate`, `model_dump`, etc. Not v1 compatible.
- **Protocol classes**: Harness and task backends use `typing.Protocol` for pluggability. No ABC inheritance.
- **mypy strict mode**: All code must pass `mypy --strict`. Use explicit types, no `Any`.
- **Relative imports**: Use absolute imports from `cub.core`, not relative imports between packages.
- **Task management**: This project uses `bd` (beads) as the primary backend. JSON backend is legacy. Use `bd close <id> -r "reason"` for task closure.
- **Config precedence**: CLI flags > env vars > project config > global config > hardcoded defaults
- **Test isolation**: pytest tests use temporary directories via `tmp_path` fixture.
- **Rich for terminal output**: Use Rich tables, progress bars, and console for all user-facing output.

## Common Commands

```bash
# Development setup
uv sync                    # Install dependencies (recommended)
source .venv/bin/activate # Activate virtual environment

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_config_loader.py -v

# Run with coverage
pytest tests/ --cov=src/cub --cov-report=html

# Type checking
mypy src/cub

# Linting
ruff check src/ tests/
ruff format src/ tests/

# Task management (beads)
bd list                    # List all tasks
bd list --status open     # List open tasks
bd close <task-id> -r "reason"  # Close a task
bd show <task-id>          # View task details

# Run cub from source
cub run --once            # Single iteration
cub status                # Show task progress
cub init --global         # Set up global config
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
