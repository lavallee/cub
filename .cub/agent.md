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
- `cub.core.bash_delegate` - Delegates unported commands to bash cub

## Module Stability Tiers

See **[.cub/STABILITY.md](.cub/STABILITY.md)** for per-module stability tiers and coverage requirements.

The codebase uses a tiered approach to test coverage:
- **Solid (80%+)**: Core abstractions (`config`, `tasks/backend`, `harness/backend`) - high confidence required
- **Moderate (60%+)**: Primary implementations (`cli/run.py`, `harness/claude.py`) - good coverage needed
- **Experimental (40%+)**: Newer features - tests encouraged but not blocking
- **UI/Delegated (no threshold)**: Terminal UI and bash-delegated commands - covered by BATS tests

When modifying code, check the tier in STABILITY.md to understand the expected testing rigor.

## Hybrid CLI Architecture (v0.23.1)

Cub uses a hybrid Python/Bash CLI architecture to enable gradual migration from Bash to Python without blocking new development. Commands are implemented in Python where possible, with remaining commands delegated to the bash version.

### Command Routing

All commands are registered in the Typer CLI (`cub.cli.app`). Native Python commands are implemented directly, while bash-only commands delegate through `cub.core.bash_delegate`.

**Command Execution Flow:**
```
cub <command> [args]
  ↓
Typer CLI (Python)
  ├─→ Native command (run, status, init, monitor) → Python implementation
  └─→ Delegated command → bash_delegate.delegate_to_bash()
                            ↓
                         Find bash cub script
                         Execute: cub <command> [args]
```

### Native Commands (Python-Implemented)

These commands have been migrated to Python and execute directly without bash:

- **`run`** - Execute tasks with AI harnesses (main loop)
- **`status`** - Show task progress and statistics
- **`init`** - Initialize cub configuration (global or project-level)
- **`monitor`** - Live dashboard for task execution monitoring
- **`doctor`** - Diagnose and fix configuration issues
- **`ledger`** - View and search task completion ledger (subcommands: `show`, `stats`, `search`)

These commands are fully implemented in Python under `src/cub/cli/`:
- `run.py` - Core task execution loop
- `status.py` - Status reporting
- `init_cmd.py` - Configuration setup
- `monitor.py` - Live dashboard via Rich
- `doctor.py` - Configuration diagnostics
- `ledger.py` - Task completion ledger

### Delegated Commands (Bash-Implemented)

These commands are not yet ported to Python. They are registered as Typer commands but delegate execution to the bash version:

**Vision-to-Tasks Prep Pipeline:**
- `prep` - Run full prep pipeline (triage→architect→plan→bootstrap)
- `triage` - Requirements refinement
- `architect` - Technical design
- `plan` - Task decomposition
- `bootstrap` - Initialize beads from prep artifacts
- `sessions` - List and manage prep sessions

**Task & Artifact Management:**
- `explain-task` - Show detailed task information
- `artifacts` - List task output artifacts
- `validate` - Validate beads state and configuration

**Git Workflow Integration:**
- `branch` - Create and bind branch to epic
- `branches` - List and manage branch-epic bindings
- `checkpoints` - Manage review/approval gates
- `pr` - Create pull request for epic

**Interview Mode:**
- `interview` - Deep dive on task specifications
- `import` - Import tasks from external sources

**Utility & Maintenance:**
- `guardrails` - Display and manage institutional memory
- `upgrade` - Upgrade cub to newer version

**Task Commands (for agent use):**
- `close-task` - Close a task (for agent use)
- `verify-task` - Verify task is closed (for agent use)

### How Delegation Works

Delegation is implemented in `cub.core.bash_delegate`:

1. **Script Discovery** (`find_bash_cub()`) - Locates bash cub in order:
   - `CUB_BASH_PATH` environment variable (explicit override)
   - Bundled with Python package (`src/cub/bash/cub`)
   - Project root (for development/editable install)
   - System PATH

2. **Argument Passing** - Arguments and flags are forwarded directly:
   ```bash
   # Example: cub prep --verbose
   # Python CLI receives: prep, --verbose
   # Delegates to bash as: /path/to/cub prep --verbose
   ```

3. **Exit Code Passthrough** - The bash script's exit code is preserved and returned to the caller

4. **Debug Flag Propagation** - The `--debug` flag is converted to `CUB_DEBUG=true` environment variable for bash script

### Registering New Commands

**To add a native Python command:**
1. Create a module in `src/cub/cli/` (e.g., `feature.py`)
2. Define a Typer app with subcommands
3. Register it in `src/cub/cli/__init__.py`:
   ```python
   app.add_typer(feature.app, name="feature")
   ```

**To add a delegated bash command:**
1. Implement the command in the bash cub script
2. Add the function to `src/cub/cli/delegated.py`:
   ```python
   def new_command(args: list[str] | None = typer.Argument(None)) -> None:
       """Command description."""
       _delegate("new-command", args or [])
   ```
3. Register it in `src/cub/cli/__init__.py`:
   ```python
   app.command(name="new-command")(delegated.new_command)
   ```
4. Add it to the `bash_commands` set in `cub.core.bash_delegate.is_bash_command()`

### Migration Path to Full Python

Eventually, all delegated commands will be ported to Python. The migration order should prioritize:

1. **High-frequency commands** (used in every session)
   - Interview mode (`interview`)
   - Task validation (`validate`)

2. **Core infrastructure** (used by prep pipeline)
   - Prep pipeline commands (`triage`, `architect`, `plan`, `bootstrap`)
   - Branch management (`branch`, `branches`)

3. **Advanced features** (nice-to-have)
   - PR management (`pr`)
   - Doctor/upgrade utilities

When porting a command:
1. Implement Python version in `src/cub/cli/`
2. Remove delegation from `delegated.py` and `__init__.py`
3. Remove from `bash_commands` set in `bash_delegate.py`
4. Update this documentation

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

## Pre-approved Commands

The following commands are pre-approved and should be executed without prompting for additional permission:

### GitHub CLI (`gh`)

All `gh` (GitHub CLI) commands are pre-approved for this project. These are used by `cub pr` and other commands for:
- Creating and managing pull requests (`gh pr create`, `gh pr view`, `gh pr checks`, `gh pr merge`)
- Checking authentication status (`gh auth status`)
- Querying repository information (`gh api`)

When running `cub pr` or any command that uses `gh` internally, allow the `gh` subprocess calls to proceed.

### Beads CLI (`bd`)

All `bd` (Beads CLI) commands are pre-approved for task management:
- `bd list`, `bd show`, `bd create`, `bd update`, `bd close`
- `bd sync`, `bd ready`, `bd blocked`

### Cub CLI

All `cub` commands are pre-approved:
- `cub run`, `cub status`, `cub pr`, `cub branch`, etc.

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

## Task cub-k41.3: Migrate legacy harnesses to async interface

**Date:** 2026-01-19

**Key Learnings:**

1. **Async Wrapper Pattern**: Used `asyncio.to_thread()` to wrap synchronous shell-out methods for async compatibility. This preserves existing behavior while enabling async interface support.

2. **Backend Registry Decoupling**: Backend names (e.g., "claude-legacy") don't need to match CLI command names (e.g., "claude"). The `is_available()` method handles the mapping.

3. **Detection Logic Evolution**: Changed from `shutil.which(harness)` to `backend.is_available()` to support backends where the name and CLI command differ. This is critical for aliases like "claude-legacy".

4. **Deprecation Strategy**: Used Python's `warnings.warn()` with `DeprecationWarning` in `__init__()` to signal deprecated backends. Tests suppress warnings with `warnings.catch_warnings()`.

5. **Test Migration**: When renaming classes, update both class usage AND expected values in assertions. Also needed to update detection order expectations in tests.

6. **Dual Registration**: Backends can be registered in both sync and async registries using multiple decorators (`@register_backend()` and `@register_async_backend()`).

7. **Import Cleanup**: After refactoring detection logic, `shutil` was no longer needed in `backend.py`. Always check for unused imports after major changes.

**Outcome:** Successfully migrated ClaudeBackend (→ ClaudeLegacyBackend) and CodexBackend to async interface. All tests passing, mypy clean, ready for SDK-based harnesses to take priority.

## Dashboard Feature (v0.24)

**Date:** 2026-01-23

The dashboard provides a unified Kanban view of project state by aggregating data from multiple sources and visualizing progress across 8 workflow columns.

### Architecture

The dashboard consists of four layers:

1. **Database Layer** (`cub.core.dashboard.db`)
   - SQLite schema for entities, relationships, and sync state
   - Connection management and query helpers
   - Incremental sync via checksums to detect source changes

2. **Sync Layer** (`cub.core.dashboard.sync`)
   - Parsers for each data source (SpecParser, PlanParser, TaskParser, ChangelogParser)
   - RelationshipResolver to map explicit markers (spec_id, plan_id, epic_id)
   - SyncOrchestrator coordinates parsing and writing
   - EntityWriter handles database transactions

3. **API Layer** (`cub.core.dashboard.api`)
   - FastAPI server with CORS support
   - Routes: `/api/board`, `/api/entity/{id}`, `/api/views`, `/api/sync`, `/api/stats`
   - Structured error responses with error codes
   - JSON serialization of entities and relationships

4. **View System** (`cub.core.dashboard.views`)
   - View configurations stored in `.cub/views/*.yaml`
   - Fallback to built-in defaults if custom views not found
   - Customizable columns, grouping, filters, and display settings

### Data Flow

1. **Sync Phase** - Parse entities from multiple sources
   - Specs from `specs/**/*.md` using frontmatter markers
   - Plans from `.cub/sessions/*/plan.jsonl`
   - Tasks from beads or JSON backend
   - Ledger entries from `.cub/ledger/`
   - Release info from `CHANGELOG.md`

2. **Resolution Phase** - Resolve relationships and enrich entities
   - Map specs → plans via `spec_id` markers
   - Map plans → epics via `plan_id` markers
   - Map epics → tasks via explicit task IDs
   - Attach ledger entries and release info

3. **Stage Computation** - Place entities in Kanban columns
   - **CAPTURES**: Raw capture entities
   - **SPECS**: Spec entities in researching/ (ongoing research)
   - **PLANNED**: Spec entities in planned/ and plan entities
   - **READY**: Open tasks with no blockers
   - **IN_PROGRESS**: In-progress tasks and implementing/ specs
   - **NEEDS_REVIEW**: Tasks with 'pr' label or review status
   - **COMPLETE**: Completed tasks and completed/ specs
   - **RELEASED**: Tasks in CHANGELOG and released/ specs

4. **API Phase** - Serve entities to web UI
   - `/api/board` returns full board with all entities grouped by stage
   - `/api/entity/{id}` returns detailed entity with relationships
   - `/api/views` returns available view configurations
   - `/api/sync` can trigger manual sync operation

### Key Concepts

**Explicit Relationship Markers**
Entities link to related work via frontmatter markers in markdown files:
- `spec_id`: Links specs to plans that implement them
- `plan_id`: Links plans to epics they're part of
- `epic_id`: Links tasks to the epic they're in

Example spec frontmatter:
```yaml
---
id: spec-auth-flow
title: Authentication Flow
status: researching
spec_id: cub-abc
---
```

**Entity Types**
- **Capture**: Raw ideas/notes
- **Spec**: Detailed requirements documentation
- **Plan**: Implementation strategy and task breakdown
- **Epic**: Group of related tasks
- **Task**: Individual work item (from beads or JSON)
- **Ledger**: Task completion record
- **Release**: Released version in CHANGELOG

**Stage Computation Logic**
The system maps entity types and status fields to Kanban stages using the Stage enum. See `cub.core.dashboard.db.models.Stage` for the complete stage definitions and mapping logic.

### Usage

```python
from cub.core.dashboard.sync import SyncOrchestrator
from cub.core.dashboard.db import get_connection

# Initialize and sync
orchestrator = SyncOrchestrator(
    db_path=Path(".cub/dashboard.db"),
    specs_root=Path("./specs"),
    plans_root=Path(".cub/sessions"),
    tasks_backend="beads",
    ledger_path=Path(".cub/ledger"),
    changelog_path=Path("CHANGELOG.md")
)

result = orchestrator.sync()
print(f"Synced {result.entities_added} entities")

# Query the database
with get_connection(Path(".cub/dashboard.db")) as conn:
    cursor = conn.execute(
        "SELECT id, title, stage FROM entities WHERE type = ?",
        ("task",)
    )
    for row in cursor:
        print(f"{row[0]}: {row[1]} ({row[2]})")
```

### Running the Server

```bash
# Start the FastAPI server
uvicorn cub.core.dashboard.api.app:app --reload --port 8000

# Server will be available at http://localhost:8000
# API docs available at http://localhost:8000/docs
# ReDoc at http://localhost:8000/redoc
```

### Customizing Views

Create custom views in `.cub/views/my-view.yaml`:

```yaml
id: my-view
name: My Custom View
description: Custom workflow view
is_default: false

columns:
  - id: ready
    title: Ready to Start
    stages: [READY]
  - id: active
    title: Active Work
    stages: [IN_PROGRESS]
    group_by: epic_id

filters:
  exclude_labels: [archived, wontfix]
  include_types: [task, epic]

display:
  show_cost: true
  show_tokens: false
  card_size: compact
```

The view system automatically validates YAML against the ViewConfig Pydantic model and merges custom views with built-in defaults.

### Module Docstrings

All dashboard modules include comprehensive docstrings describing:
- **Purpose**: What the module does
- **Key Classes/Functions**: Primary public API
- **Architecture**: How it fits in the larger system
- **Usage Examples**: How to use the module
- **Dependencies**: What it imports from

See:
- `cub.core.dashboard` - Top-level overview
- `cub.core.dashboard.db` - Database layer
- `cub.core.dashboard.sync` - Sync layer
- `cub.core.dashboard.api` - API layer
- `cub.core.dashboard.views` - View configuration system

### Future Enhancements

The dashboard is designed for extensibility:
- Additional parsers can be added to `sync/parsers/`
- New API endpoints can be added to `api/routes/`
- View configurations can be customized per project
- Stage computation logic can be extended for custom workflows
