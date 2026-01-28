<!--
╔══════════════════════════════════════════════════════════════════╗
║  AGENT INSTRUCTIONS FOR CUB DEVELOPMENT                          ║
╚══════════════════════════════════════════════════════════════════╝

This file contains instructions for building, running, and developing the Cub project.

Think of this as:
- BUILD INSTRUCTIONS: How to set up, test, and run the project
- ARCHITECTURE: Key modules, patterns, and design decisions
- WORKFLOWS: Git integration, task management, and development practices
- LEARNINGS: Project-specific gotchas and conventions

Update this file as you learn new things about the codebase.

╔══════════════════════════════════════════════════════════════════╗
║  WHAT TO UPDATE                                                  ║
╚══════════════════════════════════════════════════════════════════╝

1. Development Setup (if dependencies or tools change):
   - Add new required tools or package managers
   - Update Python version requirements
   - Document new environment variables

2. Project Structure (when adding new modules):
   - Add new directories or packages to the structure diagram
   - Document new module responsibilities

3. Feedback Loops (when adding new checks):
   - Add new test commands, linters, or type checkers
   - Update quality gate requirements

4. Gotchas & Learnings (when discovering new patterns):
   - Add project-specific conventions
   - Document common pitfalls
   - Note architectural decisions and their rationale

╔══════════════════════════════════════════════════════════════════╗
║  HOW THIS FILE WORKS                                             ║
╚══════════════════════════════════════════════════════════════════╝

- This file is symlinked as AGENT.md, AGENTS.md, and CLAUDE.md for compatibility
- It's referenced by the runloop system prompt (see Context Composition below)
- Changes are available immediately to new sessions
- Keep it focused: detailed specs go in specs/, plans in plans/
-->

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

# Create a new project from scratch
cub new my-project

# Initialize an existing project
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

## Architecture Overview

Cub v0.26+ uses a layered service architecture to separate business logic from interface concerns. This enables multiple interfaces (CLI, skills, API, future UIs) to share core functionality.

### Architectural Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     INTERFACES                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   CLI    │  │  Skills  │  │ Dashboard│  │ Future   │  │
│  │ (Typer)  │  │  (MCP)   │  │  (API)   │  │   UIs    │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
└───────┼─────────────┼─────────────┼─────────────┼─────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                    SERVICE LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  RunService  │  │LaunchService │  │StatusService │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │LedgerService │  │SuggestionSvc │  │  (others)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
│  • Stateless orchestrators                                 │
│  • Typed inputs/outputs                                    │
│  • No presentation logic (no Rich, no print)               │
│  • Factory-based construction                              │
└───────┬─────────────────────────────────────────────┬───────┘
        │                                             │
        ▼                                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     CORE DOMAIN                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │core/run/ │  │core/tasks│  │core/     │  │core/     │  │
│  │          │  │          │  │harness/  │  │ledger/   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │core/     │  │core/     │  │core/     │  │core/     │  │
│  │launch/   │  │suggest/  │  │config/   │  │(others)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│  • Business logic and domain models                        │
│  • No interface dependencies                               │
│  • Pure functions and protocols                            │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Concepts

**Service Layer** (`core/services/`):
- **Purpose**: Stateless orchestrators that compose domain operations into clean APIs
- **Design**: Accept typed inputs, return typed outputs, raise typed exceptions
- **No presentation logic**: Services never call Rich, print(), or sys.exit()
- **Factory construction**: Created via factory methods that accept configuration
- **Interface-agnostic**: Any interface (CLI, API, skills) calls service methods

**Core Domain** (`core/*/`):
- **Purpose**: Business logic, domain models, and pure functions
- **Independence**: No dependencies on interfaces or presentation layers
- **Protocols**: Use typing.Protocol for pluggability (no ABC inheritance)
- **Separation**: Each domain package has clear boundaries and responsibilities

### Core Packages

| Package | Purpose |
|---------|---------|
| `core/services/` | Service layer orchestrators (RunService, LaunchService, etc.) |
| `core/run/` | Run loop logic (prompt building, budget tracking, state machine) |
| `core/launch/` | Harness detection and environment setup |
| `core/suggestions/` | Smart recommendation engine for next actions |
| `core/tasks/` | Task backend abstraction (beads, JSON, JSONL) |
| `core/harness/` | AI harness backends (Claude, Codex, Gemini, OpenCode) |
| `core/ledger/` | Task completion ledger (models, reader, writer, extractor) |
| `core/config/` | Configuration loading with layered precedence |
| `core/hooks/` | Hook execution system for lifecycle events |

### Service Layer Details

**RunService** (`core/services/run.py`):
- Orchestrates the autonomous task execution loop
- Methods: `execute_once()`, `execute_loop()`, `prepare_environment()`
- Composes: task selection, prompt generation, harness invocation, result recording

**LaunchService** (`core/services/launch.py`):
- Detects available harnesses and launches them with proper configuration
- Methods: `detect_harness()`, `launch()`, `validate_environment()`
- Handles: environment variables, model selection, harness-specific flags

**LedgerService** (`core/services/ledger.py`):
- Provides queries and statistics for completed work
- Methods: `query()`, `stats()`, `recent()`, `by_task()`, `by_epic()`
- Returns: Structured data models (no Rich formatting)

**StatusService** (`core/services/status.py`):
- Aggregates project state from multiple sources
- Methods: `get_project_stats()`, `get_epic_progress()`, `get_task_summary()`
- Composes: task backend, ledger, git state, dashboard data

**SuggestionService** (`core/services/suggestions.py`):
- Provides smart recommendations for next actions
- Methods: `suggest_next_action()`, `get_recommendations()`
- Considers: task readiness, epic progress, recent completions, blockers

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
│   │   ├── services/     # Service layer (NEW in v0.26+)
│   │   │   ├── run.py        # RunService orchestrator
│   │   │   ├── launch.py     # LaunchService for harness detection
│   │   │   ├── ledger.py     # LedgerService for queries
│   │   │   ├── status.py     # StatusService for project state
│   │   │   ├── suggestions.py # SuggestionService for recommendations
│   │   │   └── models.py     # Service data models
│   │   ├── run/          # Run loop domain logic (NEW in v0.26+)
│   │   │   ├── prompt_builder.py # System prompt generation
│   │   │   ├── budget.py         # Budget tracking
│   │   │   ├── loop.py           # Run loop state machine
│   │   │   └── models.py         # Run configuration and events
│   │   ├── launch/       # Harness launching (NEW in v0.26+)
│   │   │   ├── detector.py       # Harness detection
│   │   │   ├── environment.py    # Environment setup
│   │   │   └── models.py         # Launch configuration
│   │   ├── suggestions/  # Recommendation engine (NEW in v0.26+)
│   │   │   ├── analyzer.py       # Context analysis
│   │   │   ├── recommender.py    # Suggestion generation
│   │   │   └── models.py         # Suggestion models
│   │   ├── config/       # Configuration loading
│   │   │   ├── loader.py     # Layered config loading
│   │   │   ├── models.py     # Config models
│   │   │   └── env.py        # Environment variable handling
│   │   ├── tasks/        # Task backends
│   │   │   ├── backend.py    # Task backend interface (Protocol)
│   │   │   ├── beads.py      # Beads backend implementation
│   │   │   └── json.py       # JSON backend implementation
│   │   ├── harness/      # AI harness backends
│   │   │   ├── backend.py    # Harness interface (Protocol)
│   │   │   ├── claude.py     # Claude Code harness
│   │   │   ├── codex.py      # OpenAI Codex harness
│   │   │   ├── gemini.py     # Google Gemini harness
│   │   │   ├── opencode.py   # OpenCode harness
│   │   │   └── hooks.py      # Hook handlers for artifact capture
│   │   ├── tools/        # Tool execution runtime
│   │   │   ├── adapter.py    # ToolAdapter protocol and registry
│   │   │   ├── models.py     # Tool models (ToolResult, ToolConfig, etc.)
│   │   │   ├── execution.py  # ExecutionService orchestrator
│   │   │   ├── registry.py   # RegistryService and RegistryStore
│   │   │   ├── metrics.py    # MetricsStore for execution statistics
│   │   │   ├── approvals.py  # ApprovalService and freedom dial
│   │   │   └── adapters/     # HTTP, CLI, MCP stdio adapters
│   │   ├── ledger/       # Task completion ledger
│   │   │   ├── models.py     # Ledger data models
│   │   │   ├── reader.py     # Query interface
│   │   │   ├── writer.py     # Persistence layer
│   │   │   └── extractor.py  # LLM-powered insight extraction
│   │   ├── circuit_breaker.py # Stagnation detection for run loop
│   │   ├── instructions.py   # Instruction file generation
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
├── .cub/                # Cub project metadata and state
│   ├── agent.md         # Build/run/architecture instructions (this file)
│   ├── hooks/           # Hook script references (for documentation)
│   ├── scripts/
│   │   └── hooks/
│   │       └── cub-hook.sh     # Fast-path shell filter for hooks
│   └── ledger/
│       └── forensics/   # Session event logs (JSONL per session)
├── .claude/             # Claude Code configuration
│   └── settings.json    # Hook configuration (auto-installed by cub init)
├── pyproject.toml       # Python project metadata and config
├── README.md            # User documentation
├── UPGRADING.md         # Migration guide from Bash version
└── CLAUDE.md            # Symlink to .cub/agent.md (this file)
```

## Key Modules

- `cub.cli.app` - Main Typer CLI application
- `cub.core.services.*` - Service layer orchestrators (NEW in v0.26+)
- `cub.core.run.*` - Run loop domain logic (NEW in v0.26+)
- `cub.core.launch.*` - Harness launching (NEW in v0.26+)
- `cub.core.suggestions.*` - Recommendation engine (NEW in v0.26+)
- `cub.core.config` - Configuration loading with precedence: env vars > project > global > defaults
- `cub.core.models` - Pydantic data models (Task, Config, RunMetadata, etc.)
- `cub.core.logger` - JSONL logging with structured events
- `cub.core.tasks.backend` - Abstract task backend interface
- `cub.core.harness.backend` - Abstract harness interface
- `cub.core.harness.hooks` - Hook event handlers for symbiotic workflow (SessionStart, PostToolUse, Stop, etc.)
- `cub.utils.hooks` - Hook execution system
- `cub.core.bash_delegate` - Delegates unported commands to bash cub
- `cub.core.tools` - Tool execution runtime with pluggable adapters
- `cub.core.tools.execution` - ExecutionService for tool orchestration
- `cub.core.tools.registry` - Tool registry and approval management
- `cub.core.ledger` - Task completion ledger (models, reader, writer, extractor)
- `cub.core.ledger.session_integration` - Hook-driven ledger integration for direct sessions
- `cub.core.circuit_breaker` - Stagnation detection for the run loop
- `cub.core.instructions` - Instruction file generation for harness sessions

## Module Stability Tiers

See **[.cub/STABILITY.md](.cub/STABILITY.md)** for per-module stability tiers and coverage requirements.

The codebase uses a tiered approach to test coverage:
- **Solid (80%+)**: Core abstractions (`config`, `tasks/backend`, `harness/backend`) - high confidence required
- **Moderate (60%+)**: Primary implementations (`cli/run.py`, `harness/claude.py`) - good coverage needed
- **Experimental (40%+)**: Newer features - tests encouraged but not blocking
- **UI/Delegated (no threshold)**: Terminal UI and bash-delegated commands - covered by BATS tests

When modifying code, check the tier in STABILITY.md to understand the expected testing rigor.

## Available Skills

Cub provides a comprehensive set of commands organized by use case. These commands can be invoked directly or through skills/MCP servers.

### Core Workflow Commands

**Essential Commands:**
- `cub init` - Initialize cub in a project or globally
- `cub new <name>` - Create a new project directory ready for cub
- `cub run` - Execute autonomous task loop with AI harness
- `cub status` - Show current session status and task progress
- `cub suggest` - Get smart suggestions for next actions

### Task Management Commands

**Work with Tasks:**
- `cub task ready` - List tasks ready to work on (no blockers)
- `cub task show <id>` - Show detailed task information
- `cub task claim <id>` - Claim a task for current session
- `cub task close <id> -r "reason"` - Close a completed task
- `cub task list` - List all tasks (with filtering options)
- `cub explain-task <id>` - Show detailed task information and context
- `cub close-task <id>` - Close a completed task (for agent use)
- `cub verify-task <id>` - Verify a task is closed
- `cub interview <id>` - Deep dive on task specifications
- `cub punchlist` - Process punchlist files into epics with tasks
- `cub workflow` - Manage post-completion workflow stages

### Session & Ledger Commands

**Track Your Work:**
- `cub session log` - Log work in a direct harness session
- `cub session done` - Mark current session complete
- `cub session wip` - Mark current session as work-in-progress
- `cub ledger show` - View completed work ledger
- `cub ledger stats` - Show ledger statistics
- `cub ledger search <query>` - Search ledger entries
- `cub reconcile <session-id>` - Reconstruct ledger entries from forensics
- `cub review <id>` - Review completed task implementations
- `cub artifacts` - List and manage task output artifacts

### Epic & Branch Management

**Manage Epics (Groups of Tasks):**
- `cub branch <epic-id>` - Create and bind a feature branch to an epic
- `cub branches` - List and manage branch-epic bindings
- `cub checkpoints` - Manage review/approval gates blocking task execution
- `cub worktree` - Manage git worktrees for parallel task execution
- `cub pr <epic-id>` - Create and manage pull requests
- `cub merge <pr-number>` - Merge pull requests

### Planning & Roadmap Commands

**Plan from Specs:**
- `cub plan` - Plan projects with orient, architect, and itemize phases
- `cub plan orient` - Research and understand the problem space
- `cub plan architect` - Design the solution architecture
- `cub plan itemize` - Break into agent-sized tasks
- `cub stage` - Import tasks from a completed plan into the task backend

**Manage Your Roadmap:**
- `cub capture` - Capture quick ideas, notes, and observations
- `cub captures` - List and manage captures
- `cub organize-captures` - Organize and normalize capture files
- `cub spec` - Create a feature specification through interactive interview
- `cub triage` - Refine requirements through interactive questions
- `cub import` - Import tasks from external sources

### Monitoring & Observability

**See What a Run is Doing:**
- `cub monitor` - Display live dashboard for cub run session
- `cub dashboard` - Launch project kanban dashboard
- `cub sandbox` - Manage Docker sandboxes

### Project Improvement Commands

**Improve Your Project:**
- `cub guardrails` - Display and manage institutional memory
- `cub map` - Generate a project map with structure analysis
- `cub audit` - Run code health audits (dead code, docs, coverage)

### Tool Management Commands

**Discover and Use Tools:**
- `cub tools` - Manage and execute tools via the unified tool runtime
- `cub toolsmith` - Discover and catalog tools
- `cub toolsmith sync` - Sync tool catalog from external sources
- `cub toolsmith search <query>` - Search for tools
- `cub workbench` - PM Workbench: unknowns ledger + next move

### System Management Commands

**Manage Your Cub Installation:**
- `cub version` - Show cub version
- `cub docs` - Open cub documentation in browser
- `cub update` - Update project templates and skills
- `cub system-upgrade` - Upgrade cub to a newer version
- `cub uninstall` - Uninstall cub from your system
- `cub doctor` - Diagnose and fix configuration issues
- `cub hooks` - Manage Claude Code hooks for symbiotic workflow

### Git Integration Commands

**Task State Management:**
- `cub sync` - Sync task state to git branch
- `cub sync status` - Check sync status
- `cub sync init` - Initialize sync branch
- `cub sync --push` - Push changes to remote

## Common Cub Command Patterns

### Run Loop Commands

```bash
# Start autonomous execution
cub run                           # Run until all tasks complete
cub run --once                    # Single iteration
cub run --task <id>               # Run specific task
cub run --epic <id>               # Target tasks within epic
cub run --label <name>            # Target tasks with label
cub run --stream                  # Stream harness activity in real-time
cub run --debug                   # Verbose debug logging
cub run --monitor                 # Launch live dashboard in tmux split

# Harness and model selection
cub run --harness claude          # Use Claude Code (default)
cub run --harness codex           # Use OpenAI Codex CLI
cub run --model haiku             # Use Haiku model
cub run --model sonnet            # Use Sonnet model
cub run --model opus              # Use Opus model

# Budget control
cub run --budget 10               # Max budget in USD
cub run --budget-tokens 100000    # Max token budget

# Isolation modes
cub run --worktree                # Run in isolated git worktree
cub run --sandbox                 # Run in Docker sandbox
cub run --parallel 4              # Run 4 tasks in parallel
```

### Task Management Commands

```bash
# Discovery
cub task ready                    # List ready tasks (no blockers)
cub task list --status open       # List all open tasks
cub task show <id>                # Show task details
cub task show <id> --full         # Include full description

# Claiming and closing
cub task claim <id>               # Claim task for current session
cub task close <id> -r "reason"   # Close with reason
```

### Status and Monitoring

```bash
# Project status
cub status                        # Show task progress
cub status --json                 # JSON output for scripting
cub status -v                     # Verbose status with details
cub suggest                       # Get smart suggestions for next actions

# Live monitoring
cub monitor                       # Live dashboard
cub dashboard                     # Launch Kanban dashboard
```

### Planning Workflow

```bash
# Full planning pipeline
cub plan run                      # Run orient → architect → itemize

# Individual phases
cub plan orient                   # Research problem space
cub plan architect                # Design solution architecture
cub plan itemize                  # Break into agent-sized tasks

# Stage tasks
cub stage                         # Import tasks from completed plan
```

## Bare `cub` Behavior

When you run `cub` without a subcommand, it defaults to `cub run`. This enables quick iteration:

```bash
cub              # Same as: cub run
cub --once       # Same as: cub run --once
cub --epic xyz   # Same as: cub run --epic xyz
```

## Nesting Detection

Cub detects when it's being run inside another `cub run` session (nesting) and warns/exits to prevent infinite loops. This is controlled by the `CUB_RUN_ACTIVE` environment variable.

When hooks execute during a `cub run` session, they skip certain operations to avoid double-tracking.

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
- **`init`** - Initialize cub in a project (backend, templates, hooks, statusline) or globally
- **`new`** - Create a new project directory (mkdir + git init + cub init)
- **`monitor`** - Live dashboard for task execution monitoring
- **`doctor`** - Diagnose and fix configuration issues
- **`ledger`** - View and search task completion ledger (subcommands: `show`, `stats`, `search`, `update`, `export`, `gc`)
- **`review`** - Assess task implementations against requirements
- **`session`** - Track work in direct harness sessions (subcommands: `log`, `done`, `wip`)

These commands are fully implemented in Python under `src/cub/cli/`:
- `run.py` - Core task execution loop
- `status.py` - Status reporting
- `init_cmd.py` - Configuration setup
- `new.py` - New project bootstrapping
- `monitor.py` - Live dashboard via Rich
- `doctor.py` - Configuration diagnostics
- `ledger.py` - Task completion ledger
- `review.py` - Task/epic/plan assessment and deep analysis
- `session.py` - Direct session workflow commands
- `task.py` - Task management for direct sessions and reconciliation
- `reconcile.py` - Post-hoc session reconciliation from hooks

#### Task Management Subcommands (`cub task`)

The `cub task` command provides lightweight task management callable from direct harness sessions:

```bash
# List ready tasks
cub task ready

# Show task details
cub task show <task-id>
cub task show <task-id> --full          # Include full description

# Claim a task (for current session)
cub task claim <task-id>                # Mark as in-progress
cub task claim <task-id> --session <id> # Claim for specific session

# Close a task (for agent/session use)
cub task close <task-id> -r "reason"    # Close with reason
cub task close <task-id> --session <id> # Close from specific session
```

The `cub task` commands are designed for:
1. **Discovery** -- See available tasks from inside a harness session
2. **Claiming** -- Associate current work with a specific task
3. **Closure** -- Complete a task with a reason for the ledger

#### Session Reconciliation (`cub reconcile`)

The `cub reconcile` command processes hook-generated forensics logs and produces complete ledger entries. This is useful for:
- Post-hoc processing after a direct Claude Code session
- Enriching with transcript data (token count, cost)
- Fixing ledger entries if something went wrong
- Batch processing multiple sessions

```bash
# Reconcile a single session
cub reconcile <session-id>              # Process session forensics

# Reconcile all unprocessed sessions
cub reconcile --all                     # Process all forensics

# With transcript enrichment
cub reconcile <session-id> --transcript /path/to/transcript.jsonl

# Batch with transcript directory
cub reconcile --all --transcript-dir .cub/transcripts/

# Dry-run (show what would happen)
cub reconcile <session-id> --dry-run

# Force re-processing (even if already processed)
cub reconcile <session-id> --force
```

The reconciliation process:
1. Reads forensics JSONL from `.cub/ledger/forensics/{session_id}.jsonl`
2. Classifies events (file writes, task claims, git commits)
3. Associates task if detected in forensics
4. Optionally parses transcript for token/cost enrichment
5. Writes ledger entry to `.cub/ledger/by-task/{task_id}/` or creates new entry if no task
6. Updates ledger index in `.cub/ledger/index.jsonl`

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

## Context Composition

Cub uses a layered system prompt composition system to provide context to AI harnesses during autonomous coding sessions. Understanding this system helps you customize the agent experience for your project.

### System Prompt Lookup Order

When `cub run` starts a session, it generates the system prompt by checking these locations in order (first match wins):

1. **`.cub/runloop.md`** - Project-specific runloop instructions (highest priority)
   - Use this to override the default runloop behavior for your project
   - Inherits the demarcated format from `templates/PROMPT.md`
   - Example: Custom workflow steps, project-specific validation gates

2. **`PROMPT.md`** - Legacy project-specific prompt (backwards compatibility)
   - Deprecated in favor of `.cub/runloop.md` but still supported
   - Use when migrating from older cub versions

3. **`templates/PROMPT.md`** - Project templates directory
   - For projects that vendor their own templates
   - Rare use case; most projects use package templates

4. **`templates/runloop.md`** - Package-bundled runloop template
   - Default runloop instructions shipped with cub
   - Contains the "Ralph Loop Iteration" workflow

5. **`templates/PROMPT.md`** - Package-bundled legacy template
   - Fallback for backwards compatibility
   - Contains demarcated format with customization guide

6. **Hardcoded fallback** - Minimal prompt if nothing else found
   - Safety fallback; should never be reached in normal operation

### Context Files Referenced in Prompts

The system prompt (from the lookup chain above) references these files:

- **`@AGENT.md`** - This file (build instructions, architecture, learnings)
- **`@specs/*`** - Detailed specifications for tasks/features (if present)

These references use the `@` syntax to signal they should be loaded as context by the harness.

### Task Context Injection

In addition to the system prompt, `cub run` injects task-specific context into each session:

- **CURRENT TASK section** - Task ID, title, description, files, dependencies
- **Epic context** - Parent epic details if the task is part of an epic
- **Task closure instructions** - How to mark the task complete (beads backend-specific)

### Customizing Your Project's Prompt

To customize the autonomous coding experience for your project:

1. **For minor tweaks**: Edit `AGENT.md` (this file) to add build commands, gotchas, etc.
2. **For workflow changes**: Create `.cub/runloop.md` based on `templates/PROMPT.md`
3. **For task-specific context**: Add detailed specs to `specs/` and reference them in task descriptions

### Implementation

The lookup logic is implemented in `src/cub/cli/run.py::generate_system_prompt()`.

## Gotchas & Learnings

- **Python 3.10+**: Cub requires Python 3.10+ for features like match statements and type unions (`|` syntax)
- **Pydantic v2**: Models use Pydantic v2 API with `model_validate`, `model_dump`, etc. Not v1 compatible.
- **Protocol classes**: Harness and task backends use `typing.Protocol` for pluggability. No ABC inheritance.
- **mypy strict mode**: All code must pass `mypy --strict`. Use explicit types, no `Any`.
- **Relative imports**: Use absolute imports from `cub.core`, not relative imports between packages.
- **Task management**: This project uses `bd` (beads) as the primary backend. JSON backend is legacy. Use `bd close <id> -r "reason"` for task closure.
- **Epic-task association**: The `parent` field is the canonical source for epic-task relationships. The `epic:{parent}` label is a compatibility layer. **DO NOT flip this** - see `.cub/EPIC_TASK_ASSOCIATION.md` for the rationale.
- **Config precedence**: CLI flags > env vars > project config > global config > hardcoded defaults
- **Test isolation**: pytest tests use temporary directories via `tmp_path` fixture.
- **Rich for terminal output**: Use Rich tables, progress bars, and console for all user-facing output.
- **Context composition**: System prompts follow a lookup order (`.cub/runloop.md` → `PROMPT.md` → `templates/PROMPT.md` → `templates/runloop.md` → fallback). See "Context Composition" section above for details. When modifying autonomous agent behavior, edit `.cub/runloop.md` or this file (AGENT.md).
- **Service layer**: v0.26+ separates business logic (services) from presentation (CLI). New features should add service methods first, then interface implementations.

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
   - Parsers for each data source (SpecParser, PlanParser, TaskParser, LedgerParser, ChangelogParser)
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
   - Plans from `plans/*/plan.jsonl`
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

## Symbiotic Workflow (v0.25+)

The symbiotic workflow enables fluid movement between CLI-driven (`cub run`) and interactive harness sessions (Claude Code, etc.) by using hooks to implicitly track task creation, execution, and completion regardless of mode. This solves the "learning degradation" problem: when developers work directly in Claude Code, cub has no visibility into what happened.

### Architecture Overview

The symbiotic workflow uses a three-tier pipeline:

1. **Shell Fast-Path Filter** (`.cub/scripts/hooks/cub-hook.sh`)
   - Lightweight bash shell script (no Python startup latency)
   - Runs first, filters irrelevant events (90% of tool uses)
   - Checks `CUB_RUN_ACTIVE` env var to prevent double-tracking
   - Only pipes to Python handler when relevant

2. **Python Event Handlers** (`cub.core.harness.hooks`)
   - Classifies file writes (plans, specs, captures, source code)
   - Detects task commands (cub task operations, git commits)
   - Maintains session forensics (JSONL event log per session)
   - Triggers ledger integration

3. **Session Ledger Integration** (`cub.core.ledger.session_integration`)
   - Works with partial information (task ID may arrive mid-session)
   - Synthesizes complete ledger entries from accumulated events
   - Supports transcript parsing for token/cost enrichment

### What Hooks Do

Claude Code provides hooks at key lifecycle points. The symbiotic workflow observes:

| Hook Event | What It Captures |
|-----------|------------------|
| **SessionStart** | Session begins; injects ready tasks and project context |
| **PostToolUse** (Write/Edit) | Files written to `plans/`, `specs/`, `captures/`, source |
| **PostToolUse** (Bash) | Task commands (`cub task`), git commits (`git commit`) |
| **Stop** | Session finalized; creates ledger entry if task was worked on |
| **PreCompact** | Checkpoint before context loss (compaction = new session) |

### Installation

Hooks are configured automatically by `cub init`. To verify or manually configure:

**Option 1: Automatic (Recommended)**
```bash
cd your-project
cub init                          # Install hooks and configure settings
```

**Option 2: Manual Configuration**
Add hooks to `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [{
          "type": "command",
          "command": "${CLAUDE_PROJECT_DIR}/.cub/scripts/hooks/cub-hook.sh",
          "timeout": 5
        }]
      },
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "${CLAUDE_PROJECT_DIR}/.cub/scripts/hooks/cub-hook.sh",
          "timeout": 5
        }]
      }
    ],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PROJECT_DIR}/.cub/scripts/hooks/cub-hook.sh",
        "timeout": 10
      }]
    }]
  }
}
```

Then verify installation:
```bash
cub doctor                        # Check hook installation
```

### Session Forensics

Hooks write JSONL event logs to `.cub/ledger/forensics/{session_id}.jsonl`:

```json
{"event": "session_start", "timestamp": "2026-01-28T20:30:00Z"}
{"event": "file_write", "file_path": "plans/foo/plan.md", "tool": "Write"}
{"event": "task_claim", "task_id": "cub-042", "timestamp": "2026-01-28T20:35:00Z"}
{"event": "git_commit", "hash": "abc123", "message": "implement feature"}
{"event": "session_end", "timestamp": "2026-01-28T20:45:00Z"}
```

These logs accumulate during the session and are converted to a ledger entry when the session ends.

### Working in Direct Sessions

The symbiotic workflow guides you to claim a task when starting a direct Claude Code session:

1. **Open Claude Code** in your project
2. **See injected context** -- available tasks and current epic
3. **Claim a task** (if not auto-detected from branch or prompt)
   ```bash
   cub task claim cub-042
   ```
4. **Work normally** -- write code, commit, create plans
5. **Hooks track everything automatically**
6. **Close the task** when done
   ```bash
   cub task close cub-042 -r "Implemented feature"
   ```

### Parity with `cub run`

| Capability | `cub run` | Direct Session + Hooks |
|------------|-----------|------------------------|
| Task selection | Automatic | Manual (guided by context) |
| Task claiming | Automatic | Via command or branch inference |
| Ledger entry creation | Automatic | From hook forensics |
| Plan capture | Auto (harness) | PostToolUse detects writes |
| File tracking | Run loop | PostToolUse tracks Write/Edit |
| Git commits | Run loop | PostToolUse detects commits |
| Session context | Built-in | SessionStart injects context |

### Double-Tracking Prevention

When `cub run` invokes Claude Code as a harness, hooks are disabled for that session via the `CUB_RUN_ACTIVE` environment variable. This prevents duplicate ledger entries -- the run loop already tracks everything. Hooks only activate for direct (non-cub-run) sessions.

### Project Structure

The symbiotic workflow adds these directories and files:

```
.cub/
├── hooks/                        # Hook scripts (for reference)
│   ├── README.md                 # Hook installation and troubleshooting
│   ├── post-tool-use.sh          # Capture file writes
│   ├── session-start.sh          # Initialize session
│   ├── session-end.sh            # Finalize session
│   └── stop.sh                   # Session cleanup
├── scripts/
│   └── hooks/
│       └── cub-hook.sh           # Fast-path shell filter (installed here)
└── ledger/
    └── forensics/                # Session event logs (JSONL per session)
        └── {session_id}.jsonl

.claude/
└── settings.json                 # Hook configuration (auto-installed)
```

### Troubleshooting Hooks

**Hooks not running?**
1. Verify shell scripts are executable:
   ```bash
   ls -la .cub/scripts/hooks/
   # Should show -rwxr-xr-x permissions
   chmod +x .cub/scripts/hooks/cub-hook.sh
   ```

2. Check `.claude/settings.json` has hooks configured:
   ```bash
   grep -A 5 '"hooks"' .claude/settings.json
   ```

3. Enable verbose mode in Claude Code (Ctrl+O) to see hook execution logs

**No forensic logs created?**
1. Ensure `.cub/config.json` exists (run `cub init` if needed)
2. Verify cub is in PATH:
   ```bash
   which cub
   which python3
   ```
3. Test the Python module directly:
   ```bash
   python3 -m cub.core.harness.hooks --help
   ```

**Hook timeouts?**
If hooks timeout (default 5-15 seconds), increase in `.claude/settings.json`:
```json
{
  "hooks": {
    "PostToolUse": [{
      "hooks": [{
        "timeout": 30
      }]
    }]
  }
}
```

**Hooks not installed?**
Run `cub init` to install:
```bash
cub init
cub doctor  # Verify installation
```

**Check hook status with cub doctor:**
```bash
cub doctor
# Output includes:
# Hooks installed: Yes/No
# Shell script present and executable: Yes/No
# Python module importable: Yes/No
# All hook events configured: Yes/No
```
<!-- BEGIN CUB MANAGED SECTION v1 -->
<!-- sha256:cb43dee7c868ba02c061efa07d13ebec49607e2aef56977944ecd8f51ceb4210 -->
# Cub Task Workflow (Claude Code)

**Project:** `cub` | **Context:** @.cub/map.md | **Principles:** @.cub/constitution.md

## Quick Start

1. **Find work**: `cub task ready` or `cub task list --status open`
2. **Claim task**: `cub task claim <task-id>`
3. **Build/test**: See @.cub/agent.md for commands
4. **Complete**: `cub task close <task-id> --reason "what you did"`
5. **Log**: `cub log --notes="session summary"` (optional)

## Task Commands

- `cub task show <id>` - View task details
- `cub status` - Project status and progress

## Claude-Specific Tips

- **Plan mode**: Save complex plans to `plans/<name>/plan.md`
- **Skills**: Use `/commit`, `/review-pr`, and other skills as needed
- **@ References**: Use @.cub/map.md for codebase context, @.cub/constitution.md for principles

## When Stuck

If genuinely blocked (missing files, unclear requirements, external blocker):
```xml
<stuck>Clear description of the blocker</stuck>
```

See @.cub/agent.md for full workflow documentation.
<!-- END CUB MANAGED SECTION -->
