# Changelog

All notable changes to Cub (formerly Curb) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.26.2] - 2026-01-17

### Changed

- Non-interactive mode for cub prep steps (#33)
- Create CNAME
- Delete CNAME
- Create CNAME
- Improve quick install + use bash
- Add PM workbench + repo-as-workbench notes
- Add capture-to-task workflow spec
- Update webpage for v0.26.1

---

## [0.26.1] - 2026-01-16

### Added

- Captures system overhaul and investigate command
- **release**: Add --title option to cut-release.sh
- **tasks**: Add TaskService for consistent task creation
- **investigate**: Implement all category processors
- **investigate**: Add spike category and capture archiving support
- Add investigate command for processing captures

### Changed

- Cub config
- **tasks**: Add backend_name and get_agent_instructions to protocol
- Update webpage for v0.26.0

### Fixed

- **investigate**: Improve categorization heuristics for quick tasks

---

## [0.26.0] - 2026-01-16

### Added

- Auto-generate changelog from git commits
- Add cut-release.sh for standalone release creation
- AI-generated titles and new filename format for captures
- Random IDs, AI slugs, and simplified timestamps for captures
- Implement two-tier capture storage model

### Changed

- Updated to include changelog (#32)
- Update capture spec with two-tier storage model

---

## [0.25.1] - 2026-01-16

### Changed

- **CLI help reorganized** - Commands grouped by function with descriptive headers
  - Key Commands, Status, Tasks, Prep/Planning, Epics, Project, Roadmap, Installation
  - Advanced commands (worktree, sandbox) hidden from default help

- **Command renames for clarity**
  - `agent-close` → `close-task`
  - `agent-verify` → `verify-task`
  - `explain` → `explain-task`

- **`cub init` is now backend-aware** - Templates adapt to selected task backend
  - Beads backend: agent.md shows `.beads/`, prompt.md uses `bd close`
  - JSON backend: agent.md shows `prd.json`, prompt.md uses prd.json update

### Improved

- **Install script** - Better error handling with multiple fallback options
  - Tries existing tools (pipx, uv) before installing new ones
  - Shows actual errors and manual installation options on failure

- **`cub doctor`** - Added optional tool checks for common dev tools

- **CONTRIBUTING.md** - Rewritten for hybrid Python/Bash architecture
  - Documents native vs delegated commands
  - Examples for adding harnesses, task backends, and CLI commands

### Removed

- Duplicate non-namespaced skill files (keep only `cub:*` prefixed)
- Dead bash code and duplicate lib directories
- Deprecated `migrate-layout` command

---

## [0.25.0] - 2026-01-16

### Added - Sandbox Mode for Safe Autonomous Execution

Docker-based sandboxing for running cub with full isolation and review capabilities:

- **SandboxProvider Protocol** - Pluggable provider interface for sandbox backends
  - `register_provider()` decorator for backend registration
  - `get_provider()` for provider discovery
  - Extensible for future backends (Nix, VMs, etc.)

- **DockerProvider** - Production-ready Docker sandbox implementation
  - Full filesystem isolation via bind mounts
  - Network isolation option for offline execution
  - Resource limits (memory, CPU)
  - Security hardening (no-new-privileges)
  - Fast startup (~2-5s)

- **`--sandbox` flag for `cub run`** - Execute tasks in Docker isolation
  - Automatic sandbox provisioning
  - Changes isolated until explicitly applied
  - Resource usage tracking

- **`cub sandbox` subcommands** - CLI for sandbox management
  - `cub sandbox status` - Show running sandboxes
  - `cub sandbox diff` - Review pending changes
  - `cub sandbox apply` - Apply changes to host
  - `cub sandbox discard` - Discard sandbox changes
  - `cub sandbox shell` - Interactive sandbox session

- **Docker image** - Pre-built image for sandbox execution
  - Multi-stage build for minimal size
  - Includes cub and essential dependencies
  - `docker/Dockerfile` and `docker-compose.yml` for local builds

### Fixed

- **detect_harness()** - Only returns harnesses with registered Python backends
  - Prevents fallback to unregistered backends (e.g., gemini CLI without backend)
  - Clearer error messages when no valid harness available

---

## [0.24.0] - 2026-01-16

### Added - Git Worktrees for Parallel Development

Support for running cub in isolated worktrees and processing multiple tasks concurrently:

- **WorktreeManager class** - Core worktree management functionality
  - Create/remove worktrees for isolated execution
  - Track worktree state and cleanup
  - Safe concurrent access patterns

- **`--worktree` flag for `cub run`** - Run in isolated worktree
  - Automatically creates temporary worktree
  - Isolates file changes from main working directory
  - Clean merge back to main branch on completion

- **`--parallel N` flag for `cub run`** - Concurrent task execution
  - Process N independent tasks simultaneously
  - Respects task dependencies (only runs unblocked tasks)
  - Each parallel task runs in its own worktree

- **`cub worktree` subcommands** - CLI for worktree management
  - `cub worktree list` - Show active worktrees
  - `cub worktree clean` - Remove stale worktrees
  - `cub worktree status` - Check worktree health

### Fixed

- **release-pipeline.sh** - Added `safe_checkout_main()` to handle beads worktree conflicts

---

## [0.23.3] - 2026-01-15

### Added - Codebase Health Audit

Tools to maintain code quality and identify technical debt:

- **`cub audit` Command** - Unified codebase health checking
  - `cub audit` - Run all available checks
  - `cub audit --dead-code` - Find unused Python functions/classes (via vulture)
  - `cub audit --bash-dead-code` - Find unused Bash functions
  - `cub audit --docs` - Validate docstrings and README accuracy
  - `cub audit --coverage` - Show test coverage metrics
  - `cub audit --fix` - Auto-fix issues where possible

- **Native Python `cub upgrade` Command**
  - Migrated from bash delegation to full Python implementation
  - `--local` flag to install from current cub repository
  - `--editable` flag for development mode (`pip install -e .`)
  - Auto-detects install method (pipx, pip, editable)
  - `--check`, `--version`, `--force` flags supported

### Fixed

- **`--debug` flag propagation** - Debug flag now properly passed through delegated bash commands via `CUB_DEBUG` environment variable
- **release-pipeline.sh** - Skip main checkout if already on target branch (fixes worktree conflict)
- **release-pipeline.sh** - Correct position for `--debug` flag (`cub --debug run` not `cub run --debug`)

### Changed

- Gitignored `*.egg-info/` build artifacts
- Removed `upgrade` from bash-delegated commands

### Tasks Completed

- cub-069: Implement dead code detection for Python
- cub-070: Implement dead code detection for Bash
- cub-071: Implement documentation validation
- cub-072: Implement test coverage reporting
- cub-073: Implement cub audit command

---

## [0.23.2] - 2026-01-15

### Fixed - Unimplemented Commands

Commands that printed "not yet implemented" now delegate to bash.

- **`cub init`** - Now properly delegates to bash implementation
  - Was previously printing "Init command not yet implemented"
  - Now runs the full bash init workflow

### Changed

- Removed `init_cmd.py` from active CLI registration
- Added `init` to delegated commands module

---

## [0.23.1] - 2026-01-15

### Added - Hybrid Python/Bash CLI

Bridges the Python and Bash implementations so users have access to all cub functionality from a single `cub` command.

- **Bash Delegation Module** (`src/cub/core/bash_delegate.py`)
  - Locates bundled bash script or system installation
  - Delegates commands to bash with full argument passthrough
  - Exit code and output handling

- **Delegated CLI Commands** (`src/cub/cli/delegated.py`)
  - All bash-only commands registered in Python CLI
  - Seamless UX - users don't need to know which backend runs
  - `cub --help` shows unified command list

- **Bundled Bash Scripts** (`src/cub/bash/`)
  - Full bash cub script and lib/ bundled with Python package
  - Works after `pip install` without separate bash setup
  - Templates included for init command

### Delegated Commands

Commands that delegate to bash: `prep`, `triage`, `architect`, `plan`, `bootstrap`, `sessions`, `branch`, `branches`, `checkpoints`, `pr`, `interview`, `import`, `explain`, `artifacts`, `validate`, `doctor`, `upgrade`, `guardrails`, `agent-close`, `agent-verify`, `migrate-layout`

### Python-Native Commands

Commands with full Python implementation: `run`, `status`, `monitor`, `init`

### Tasks Completed

- cub-m7a.1: Create bash delegation module
- cub-m7a.2: Add delegated commands to CLI
- cub-m7a.3: Bundle bash script with Python package
- cub-m7a.4: Add tests for bash delegation
- cub-m7a.5: Update CLAUDE.md with hybrid CLI docs

---

## [0.23.0] - 2026-01-15

### Added - Live Dashboard

Real-time monitoring dashboard for cub runs, with Rich-based terminal UI and tmux integration for split-pane workflows.

- **Rich-Based Dashboard Renderer** (`src/cub/dashboard/renderer.py`)
  - Live terminal UI with Rich library
  - Task progress visualization
  - Token usage and budget tracking
  - Event log with color-coded levels
  - Auto-refresh with configurable intervals

- **Status File Polling** (`src/cub/dashboard/status.py`)
  - Watches `.cub/runs/<session>/status.json` for changes
  - Event-driven updates via file system monitoring
  - Graceful handling of file changes during writes

- **Tmux Integration** (`src/cub/dashboard/tmux.py`)
  - `--monitor` flag creates split pane with live dashboard
  - Automatic pane management (create/resize/close)
  - Works with existing tmux sessions
  - Fallback to standalone mode outside tmux

- **`cub monitor` Command** (`src/cub/cli/monitor.py`)
  - `cub monitor` - Watch current/latest run
  - `cub monitor <session>` - Watch specific session
  - `--refresh <seconds>` - Set refresh interval
  - Standalone dashboard without running tasks

### Technical

- `src/cub/dashboard/` - New dashboard module
- `src/cub/cli/monitor.py` - Monitor command implementation
- `tests/test_dashboard_renderer.py` - Dashboard renderer tests
- `tests/test_dashboard_status_watcher.py` - Status watcher tests
- Updated `src/cub/cli/run.py` with `--monitor` flag support

### Tasks Completed

- cub-074: Implement Rich-based dashboard renderer
- cub-075: Implement status file polling
- cub-076: Implement tmux integration for --monitor
- cub-077: Implement cub monitor command

---

## [0.22.0] - 2026-01-15

### There is no spoon

---

## [0.21.0] - 2026-01-15

### Added - Python Core Migration

A complete Python implementation of cub's core functionality, providing a foundation for future enhancements while maintaining full compatibility with the bash implementation.

- **Python Project Structure**
  - Initialized with `uv` for fast dependency management
  - Pydantic models for Task and Config validation
  - Type-safe protocol-based architecture

- **Task Backend System**
  - `TaskBackend` protocol with registry pattern
  - `BeadsBackend` - Full integration with beads CLI (`bd`)
  - `JsonBackend` - Direct prd.json manipulation
  - Automatic backend detection and selection

- **Harness Backend System**
  - `HarnessBackend` protocol for LLM integrations
  - `ClaudeBackend` - Claude Code CLI integration
  - `CodexBackend` - OpenAI Codex CLI integration
  - Unified interface for task execution

- **Configuration System**
  - Multi-layer config merging (CLI > env > project > global > defaults)
  - XDG-compliant paths for config and data
  - Pydantic validation for all config values

- **CLI Commands** (via Typer)
  - `cub run` - Main autonomous loop with all existing flags
  - `cub status` - Project status display
  - Full compatibility with bash implementation flags

- **Hook System**
  - Python hook executor with pre/post task hooks
  - Error hooks for failure handling
  - Compatible with existing bash hook scripts

- **Structured Logging**
  - JSONL logging with task_start/task_end events
  - Token usage tracking
  - Git SHA capture for audit trails

- **Test Suite**
  - Comprehensive pytest tests for all core modules
  - Async test support for harness operations
  - Mock backends for isolated testing

### Fixed

- **Epic Filter Bug** - `cub run --epic` now correctly counts remaining tasks within the specified epic only, instead of all tasks across all epics. This fixes premature "no ready tasks" errors when an epic completes.

### Technical

- `src/cub/` - Python package structure
- `src/cub/models/` - Pydantic models (task.py, config.py)
- `src/cub/backends/` - Task and harness backends
- `src/cub/cli/` - Typer CLI implementation
- `src/cub/logging.py` - Structured JSONL logging
- `src/cub/hooks.py` - Hook execution system
- `tests/` - Pytest test suite
- `pyproject.toml` - Project configuration with uv

---

## [0.20.0] - 2026-01-14 (PR #24)

### Added - Guardrails System (Institutional Memory)

A complete system for capturing, preserving, and applying project-specific lessons learned. Guardrails are automatically included in task prompts to prevent repeat mistakes and share institutional knowledge with AI coding assistants.

- **Core Guardrails File** (`.cub/guardrails.md`)
  - Markdown format with structured lessons
  - YAML frontmatter for metadata (source, task_id, timestamp, category)
  - Auto-created during `cub init`

- **`cub guardrails show`** - Display current guardrails
  - `--category <name>` - Filter by category
  - `--search <term>` - Full-text search
  - `--count` - Show lesson count only
  - `--raw` - Output raw markdown

- **`cub guardrails add`** - Add new guardrails manually
  - `--category <name>` - Specify category (default: "Manual")
  - `--task <id>` - Link to source task
  - Interactive prompts for lesson text

- **`cub guardrails learn`** - Interactive lesson capture
  - Reviews recent task completions
  - Prompts for lessons learned
  - Links lessons to source tasks

- **`cub guardrails curate`** - AI-assisted guardrails cleanup
  - Detects duplicate lessons
  - Suggests merges for similar entries
  - Recommends pruning of outdated items
  - `--dry-run` - Preview changes without applying

- **`cub guardrails import/export`** - Share guardrails between projects
  - `cub guardrails export <file>` - Export to file
  - `cub guardrails import <file>` - Import from file
  - `--merge` - Combine with existing (default)
  - `--replace` - Overwrite existing

- **Auto-Learn from Failures** - AI extracts lessons from task failures
  - Triggered on non-zero exit codes
  - Captures error context and exit code
  - Links to source task automatically

- **Size Monitoring** - Warns when guardrails grow too large
  - Configurable threshold in `.cub.json`
  - Suggests running `cub guardrails curate`

- **Task Prompt Integration** - Guardrails included automatically
  - Appended to task prompts during `cub run`
  - Helps AI avoid known pitfalls

- **Run Artifacts** - Guardrails snapshot with each run
  - Captured in `.cub/runs/<session>/guardrails.md`
  - Enables debugging and audit trails

### Technical

- Added `lib/guardrails.sh` - Core guardrails functionality
- Added `lib/cmd_guardrails.sh` - CLI command implementation
- Added `lib/artifacts.sh` - Run artifact capture
- Updated `lib/cmd_init.sh` - Create empty guardrails on init
- Updated `lib/cmd_run.sh` - Include guardrails in prompts
- Updated `lib/failure.sh` - Auto-learn from failures
- Added `templates/guardrails.md` - Template for new projects
- Added comprehensive test suite in `tests/guardrails.bats` (80+ tests)

---

## [0.19.0] - 2026-01-14 (PR #23)

### Added - Git Workflow Integration

- **Branch-Epic Binding** - Bind git branches to beads epics for organized workflow
  - `cub branch <epic-id>` - Create and bind a new branch to an epic
  - `cub branch <epic-id> --bind-only` - Bind current branch without creating new one
  - `cub branch <epic-id> --name <custom-name>` - Custom branch name
  - `cub branches` - List all branch bindings with status
  - `cub branches --cleanup` - Remove bindings for merged branches
  - `cub branches --sync` - Sync branch status with remote
  - `cub branches --unbind <epic-id>` - Remove a binding

- **Checkpoint System** - Review gates that block downstream tasks
  - Create checkpoints with `bd create "Review milestone" --type gate`
  - `cub checkpoints` - List all checkpoints
  - `cub checkpoints --epic <id>` - List checkpoints for specific epic
  - `cub checkpoints --blocking` - Show only blocking checkpoints
  - `cub checkpoints approve <id>` - Approve checkpoint to unblock tasks
  - Tasks blocked by unapproved checkpoints are skipped during `cub run`

- **PR Management** - Auto-generate PRs from epic work
  - `cub pr <epic-id>` - Create PR with auto-generated body from completed tasks
  - `cub pr <epic-id> --draft` - Create as draft PR
  - `cub pr <epic-id> --push` - Push branch before creating PR
  - `cub pr <epic-id> --base <branch>` - Specify target branch
  - PR body includes summary of all completed child tasks

### Changed

- **Auto Branch Switching** - `cub run` automatically switches to epic's bound branch
- **Branch Metadata** - Stored in `.beads/branches.yaml` for persistence

### Technical

- Added `lib/branches.sh` - Branch-epic binding management
- Added `lib/checkpoints.sh` - Checkpoint/gate management
- Added `lib/cmd_branch.sh` - Branch commands
- Added `lib/cmd_checkpoint.sh` - Checkpoint commands
- Added `lib/cmd_pr.sh` - PR commands
- Updated `lib/cmd_run.sh` - Auto branch switching, checkpoint blocking
- Added comprehensive test suite in `tests/branches.bats`

---

## [0.18.1] - 2026-01-14 (PR #22)

### Changed - Prep Workflow
- **Renamed `cub pipeline` to `cub prep`** - Clearer naming for project preparation
- **Interactive Claude sessions** - Prep stages now launch as Claude Code skills
- **One stage at a time** - `cub prep` runs the next incomplete stage, showing progress
- **Enriched prep skills** - Triage, architect, and plan skills now include acceptance criteria, model preferences, complexity labels, and comprehensive guidance

### Changed - Init Command
- **Non-interactive by default** - Auto-detects project type without prompting
- **Added `--interactive` / `-i` flag** - Opt-in to menu prompt for project type
- **Removed `--quick` flag** - No longer needed since non-interactive is default
- **Fixed backend selection** - Only creates `prd.json` for json backend; beads backend skips it
- **Backend-aware help** - "Next steps" now shows appropriate commands per backend

### Changed - Naming
- **Renamed `cub update` to `cub upgrade`** - More intuitive naming for self-update

### Fixed
- **Bash 3.2 compatibility** - Lowered requirement from 4.0 to 3.2 for macOS
- **Unbound variable errors** - Safe array expansion with `${array[@]+"${array[@]}"}`
- **Pre-increment in init** - Fixed `((skills_installed++))` causing errexit failure

### Technical
- Added Claude Code skills: `cub:triage.md`, `cub:architect.md`, `cub:plan.md`
- Renamed `lib/cmd_pipeline.sh` to `lib/cmd_prep.sh`
- Renamed `lib/cmd_update.sh` to `lib/cmd_upgrade.sh`
- Updated doctor command to check for bash 3.2+

---

## [0.18.0] - 2026-01-14 (PR #18)

### Added - Project Organization
- **`.cub/` directory structure** - Centralized project configuration
- **Backward-compatible symlinks** - CLAUDE.md, AGENT.md, AGENTS.md, PROMPT.md
- **`cub migrate-layout`** - Migrate existing projects to new structure

### Added - Project Initialization
- **`cub init`** - Interactive project setup with type detection
- **`cub init --quick`** - Non-interactive mode for automation
- **Project-type templates** - Node.js, Python, Go, Rust-specific configs
- **Contextual help** - In-file comments with project recommendations

### Added - Doctor Command
- **`cub doctor`** - System requirements check
- **`cub doctor --config`** - Configuration validation
- **`cub doctor --structure`** - Project layout verification
- **Harness detection** - Claude, Codex version display
- **Recommendations engine** - Project-specific suggestions

### Added - Documentation
- **QUICK_START.md** - 5-minute getting started guide
- **TROUBLESHOOTING.md** - Common issues and solutions (~800 lines)
- **.cub/README.md generation** - Auto-generated project documentation

### Technical
- `lib/cmd_init.sh` - ~1200 lines of initialization logic
- `lib/cmd_doctor.sh` - ~500 lines of validation
- `lib/layout.sh` - Directory structure management
- `lib/recommendations.sh` - ~375 lines of recommendation engine
- `tests/doctor.bats` - 284 lines of doctor tests
- `tests/migrate_layout.bats` - 300 lines of migration tests

---

## [0.17.0] - 2026-01-14 (PR #17)

### Added - PRD Import / Document Conversion
- **`cub import <file>`** - Import tasks from various document formats
- **`cub import --format markdown|json|github|pdf`** - Explicit format selection
- **`cub import --dry-run`** - Preview import without making changes

### Added - Parsers
- **Markdown parser** - H1 headings to epics, H2 to features, checkboxes to tasks
- **JSON parser** - Array and structured PRD formats with validation
- **GitHub issues import** - Via `gh` CLI for external project migration
- **PDF support** - Extract tasks from PDF documents using pdftotext

### Added - Intelligent Processing
- **Priority inference** - Automatic priority detection from content keywords
- **Dependency detection** - Extract task relationships from text patterns
- **Acceptance criteria extraction** - Parse requirements from descriptions
- **Source reference preservation** - Track import origin for audit trails

### Added - Backend Support
- Works with both beads and JSON backends
- Validates task structure (IDs, titles, status)
- Detects duplicate IDs and circular dependencies

### Technical
- `lib/cmd_import.sh` - ~550 lines of implementation
- `lib/parsers/` - Markdown, JSON, GitHub, PDF parsers
- `lib/priority.sh` - ~220 lines of priority inference
- `lib/dependencies.sh` - ~360 lines of dependency detection
- 5 new test files with ~1600 lines of tests

---

## [0.16.0] - 2026-01-14 (PR #16)

### Added - Interview Mode
- **`cub interview <task-id>`** - Deep questioning to refine task specifications
- **`cub interview <task-id> --auto`** - AI-generated answers with review
- **`cub interview --all --auto`** - Batch mode for all open tasks

### Added - Question Engine
- **40+ built-in questions** across 9 categories:
  - Context & Background
  - Requirements Clarity
  - Technical Approach
  - Edge Cases & Error Handling
  - Testing Strategy
  - Integration Points
  - Security & Performance
  - User Experience
  - Documentation & Maintenance
- Task-type filtering (feature/task/bugfix questions)
- Category-based organization with skip support

### Added - Custom Questions
- Project-specific questions via `.cub.json` configuration
- `applies_to` filtering by task type
- `requires_labels` conditional filtering
- `requires_tech` tech stack filtering
- `skip_if` conditional skip logic

### Added - Output Options
- **`--output-dir`** - Custom output directory (default: specs/)
- **`--update-task`** - Append generated specs to task descriptions
- **`--skip-review`** - Skip interactive review for autonomous operation
- **`--skip-categories`** - Skip specific question categories
- Markdown specification file generation

### Added - Batch Processing
- `--all` flag processes all open tasks
- Uses `bd list --status open` to enumerate tasks
- Sequential processing with AI-generated answers
- Progress tracking and summary output

### Technical
- `lib/cmd_interview.sh` - ~1570 lines of implementation
- `tests/interview.bats` - ~970 lines of tests

---

## [0.15.0] - 2026-01-14 (PR #15)

### Added - Plan Review System
- **`cub review --plan <task-id>`** - Review specific task before execution
- **`cub review --plan --all`** - Review all ready tasks
- **`cub run --review-plans`** - Auto-review during autonomous runs

### Added - Validation Dimensions
- **Completeness Check** - Title (≥10 chars), description, acceptance criteria
- **Feasibility Check** - Dependencies complete, required files exist
- **Dependency Validation** - No circular dependencies, correct ordering
- **Architecture Review** - AI-assisted pattern checking (Sonnet model)

### Added - Configuration
- Configurable strictness levels (pass/warn/block)
- Model selection: Haiku for structural, Sonnet for AI analysis
- Pipeline integration (auto-review between stages)
- Review results logging with timestamps

### Added - Output Formats
- Summary format (human-readable markdown)
- JSON format (CI/CD integration)

### Fixed
- jq syntax bug in cycle detection (immutable variable binding)
- Infinite loop in topological sort ($completed tracking)

### Technical
- `lib/tasks.sh` - ~1000 lines of validation functions
- `tests/tasks.bats` - ~1100 lines of tests

---

## [0.14.0] - 2026-01-13 (PR #14)

### Added - Vision-to-Tasks Pipeline (chopshop integration)
- **`cub pipeline VISION.md`** - Full interactive pipeline from vision to executable tasks
- **`cub triage`** - Requirements refinement with depth options (light/standard/deep)
- **`cub architect`** - Technical design with mindset framework
- **`cub plan`** - Task decomposition into AI-friendly micro-tasks
- **`cub bootstrap`** - Beads initialization, PROMPT.md/AGENT.md generation
- **`cub validate`** - Validate beads state after import

### Added - Mindset Framework
- Prototype → MVP → Production → Enterprise progression
- Architecture decisions guided by project maturity level
- Appropriate rigor for each stage (testing, structure, security)

### Added - Task Generation
- Vertical slice organization (features deliver end-to-end value)
- Rich task descriptions with context, hints, acceptance criteria
- Label system: `phase-*`, `model:*`, `complexity:*`, `domain:*`, `risk:*`
- JSONL generation compatible with beads import
- Model recommendations per task (opus/sonnet/haiku)

### Added - Session Management
- Session artifacts stored in `.cub/sessions/{id}/`
- triage.md, architect.md, plan.jsonl, plan.md outputs
- Session ID format: `{project}-{YYYYMMDD-HHMMSS}`

### Added - Migration
- chopshop → cub migration path
- `.chopshop/sessions/` → `.cub/sessions/` artifact migration

### Technical
- `lib/cmd_pipeline.sh` - ~1900 lines of implementation
- `tests/pipeline.bats` - ~430 lines of tests

---

## [0.13.0] - 2026-01-13 (PR #13)

### Changed
- **Renamed project from "Curb" to "Cub"** across entire codebase
- All scripts, libraries, config files, documentation updated
- Environment variables changed: `CURB_*` → `CUB_*`
- Config directories: `~/.config/curb/` → `~/.config/cub/`
- Project config: `.curb.json` → `.cub.json`

### Added
- `install.sh` - Installation script for easy setup
- `uninstall.sh` - Clean removal script
- Symlink resolution in main script for installed copies

### Fixed
- Bash version check now supports macOS default bash 3.2+
- Fixed arguments lost when re-executing with sudo

### Technical
- 790 BATS tests passing

---

## [0.12.0] - 2026-01-13 (PR #12)

### Changed
- **Major refactoring**: Extracted commands from monolithic 2900-line curb script
- New modular structure under `lib/cmd_*.sh` files

### Added
- `lib/cmd_agent.sh` - Agent command implementation
- `lib/cmd_artifacts.sh` - Artifacts command implementation
- `lib/cmd_doctor.sh` - Doctor command with health checks
- `lib/cmd_explain.sh` - Explain command implementation
- `lib/cmd_init.sh` - Init command implementation
- `lib/cmd_run.sh` - Run command implementation
- `lib/cmd_status.sh` - Status command implementation
- `lib/beads.sh` - Beads integration utilities (extracted)
- `lib/project.sh` - Project management utilities
- `get_in_progress_tasks()` function for stuck task detection

---

## [0.11.1] - 2026-01-11

### Added
- `curb doctor` subcommand for diagnosing issues
- Backend-aware task completion with auto-close safety net
- Auto-commit remaining changes when agent forgets
- Error trap for debugging script crashes
- Harness output logging to `.curb/runs/` for task review
- Harness capability matrix documentation

### Fixed
- Doctor detects and commits curb artifacts (`.beads/`, `.curb/`)
- Auto-commit session files left behind by agent
- `--epic` filter uses epic's labels for beads backend
- Prevent `set -e` exit on uninitialized `git_get_run_branch`

### Changed
- Loops more resilient to exiting
- Codex harness updated for YOLO mode and streaming output
- Enhanced codex harness with JSONL streaming and model selection

---

## [0.11.0] - 2026-01-11 (PR #10)

### Added - Phase 4: Guardrails & Safety
- Iteration tracking in `budget.sh`
- Secret redaction in logger
- Configurable limits for runaway prevention

### Added - Phase 5: Failure Handling
- `lib/failure.sh` with stop/move-on/retry modes
- `curb explain` command for analyzing failures
- Main loop integration for failure modes

### Added - Phase 6: Polish
- Pre/post-loop hooks implementation
- Debug command logging
- Acceptance criteria parsing
- CLI migration docs

### Fixed
- BATS test isolation (CURB_PROJECT_DIR leak)
- Streaming output buffering
- 2 silently skipped tests

### Technical
- 732 BATS tests passing

---

## [0.10.0] - 2026-01-10 (PR #9)

### Added
- `lib/git.sh` - Complete git workflow module
- Branch-per-run naming convention (`run/<timestamp>-<run-id>`)
- Commit-per-task with structured commit messages
- `--push` flag for explicit opt-in to push branches
- Functions: `git_init_run_branch`, `git_commit_task`, `git_has_changes`, `git_get_run_branch`, `git_push_branch`

### Changed
- `lib/state.sh` refactored to use new git module

### Technical
- 1302 lines of new BATS tests for git functions

---

## [0.9.0] - 2026-01-10 (PR #8)

### Changed
- **CLI architecture refactored** from flags to subcommands
- `curb --init` → `curb init`
- `curb --status` → `curb status`
- `curb` (no args) → `curb run`
- Added `curb artifacts` subcommand

### Added
- Subcommand dispatcher in curb entry point
- `cmd_*` functions for each command
- Deprecation warnings for legacy flag syntax

### Fixed
- `cmd_artifacts` completion and checkpoint verification

---

## [0.8.0] - 2026-01-10 (PR #7)

### Added
- `lib/session.sh` - Session management with animal-based ID generation
- `lib/artifacts.sh` - Run/task artifact capture system
  - Directory structure management for runs and tasks
  - Git diff/patch capture for task changes
  - Automatic task summary generation via LLM backends
- `curb version` subcommand
- 451 lines of session tests
- 987 lines of artifacts tests

### Fixed
- Backend detection persistence bug

---

## [0.7.0] - 2026-01-10 (PR #6)

### Added - Documentation
- `CONFIG.md` - Complete configuration schema reference
- `UPGRADING.md` - Migration guide for existing users
- `CHANGELOG.md` - Initial changelog
- Expanded README with all features

### Added - Examples
- `examples/hooks/post-task/slack-notify.sh`
- `examples/hooks/post-loop/datadog-metric.sh`
- `examples/hooks/on-error/pagerduty-alert.sh`

### Added - Testing
- `tests/e2e.bats` - End-to-end test suite
- Full workflow tests with budget enforcement

### Changed
- Improved `--help` output formatting

---

## [0.6.0] - 2026-01-10 (PR #5)

### Added - Reliability Features
- Token usage extraction from Claude harness output
- `--budget` CLI flag with threshold warnings
- `lib/budget.sh` - Token budget tracking and enforcement
- `lib/state.sh` - State management with clean state checks
- Optional test runner integration
- New test suites: `budget.bats`, `harness.bats`, `state.bats`

### Changed
- Enhanced logging support in `lib/logger.sh`
- Budget enforcement integrated into main loop

---

## [0.5.0] - 2026-01-10 (PR #4)

### Added - Configuration System
- XDG-compliant global config (`~/.config/curb/config.json`)
- Project-level config (`.curb.json`)
- Full precedence: CLI > env vars > project > global > defaults
- `curb-init --global` for global onboarding

### Added - Structured Logging
- JSONL logging at `~/.local/share/curb/logs/{project}/{session}.jsonl`
- Events: `task_start`, `task_end`, `error`
- Timestamps, durations, git SHAs

### Added - Task Filtering
- `--epic <id>` flag for epic filtering
- `--label <name>` flag for label filtering
- Per-task model selection via `model:` labels

### Added - Beads Backend Improvements
- Proper abstraction (no hardcoded prd.json)
- Blocked task detection
- Filter support in queries

### Technical
- 189 BATS tests passing

---

## [0.4.0] - 2026-01-09 (PR #3)

### Added
- **OpenAI Codex CLI support** as alternative to Claude Code
- `lib/harness.sh` - Unified harness abstraction for LLM backends
- Harness selection during project initialization
- `codex` harness with full-auto mode

### Changed
- Renamed `llm` terminology to `harness` throughout codebase

### Fixed
- Removed invalid `--json` flag from Codex streaming mode

---

## [0.3.0] - 2026-01-09 (PR #2)

### Added
- Claude GitHub Actions for PR assistance
- Claude Code Review workflow
- Automated PR handling

---

## [0.2.0] - 2026-01-09 (PR #1)

### Added
- **Beads backend support** (`bd` CLI) as alternative to `prd.json`
- Auto-detection of backend based on availability
- `--backend auto|beads|json` flag
- `--migrate-to-beads` command for migration
- `--migrate-to-beads-dry-run` for preview
- `lib/beads.sh` - Wrapper functions for beads CLI

### Changed
- Backend selection is now configurable via env var `CURB_BACKEND`

---

## [0.1.0] - 2026-01-09

### Added - Initial Release
- Core autonomous loop functionality
- Claude Code integration for task execution
- `prd.json` based task management
- Task dependency tracking
- Priority-based task selection (P0-P4)
- `--debug` flag for verbose output
- `--stream` flag for real-time output
- `--once` flag for single iteration mode
- Task title and type display in output

### Technical
- Basic project structure
- Initial test coverage

---

## Version Summary

| Version | Date | PR | Highlight |
|---------|------|-----|-----------|
| 0.23.3 | 2026-01-15 | #28 | Codebase Health Audit |
| 0.23.0 | 2026-01-15 | - | Live Dashboard |
| 0.21.0 | 2026-01-15 | - | Python Core Migration |
| 0.20.0 | 2026-01-14 | #24 | Guardrails System |
| 0.19.0 | 2026-01-14 | #23 | Git Workflow Integration |
| 0.18.1 | 2026-01-14 | #22 | Prep Workflow |
| 0.18.0 | 2026-01-14 | #18 | Onboarding & Project Organization |
| 0.17.0 | 2026-01-14 | #17 | PRD Import |
| 0.16.0 | 2026-01-14 | #16 | Interview Mode |
| 0.15.0 | 2026-01-14 | #15 | Plan Review |
| 0.14.0 | 2026-01-13 | #14 | Vision-to-Tasks Pipeline |
| 0.13.0 | 2026-01-13 | #13 | Rename Curb → Cub |
| 0.12.0 | 2026-01-13 | #12 | Modular architecture |
| 0.11.1 | 2026-01-11 | - | Doctor command, auto-commit |
| 0.11.0 | 2026-01-11 | #10 | Guardrails, failure handling |
| 0.10.0 | 2026-01-10 | #9 | Git workflow |
| 0.9.0 | 2026-01-10 | #8 | Subcommand CLI |
| 0.8.0 | 2026-01-10 | #7 | Sessions & artifacts |
| 0.7.0 | 2026-01-10 | #6 | Documentation & polish |
| 0.6.0 | 2026-01-10 | #5 | Reliability features |
| 0.5.0 | 2026-01-10 | #4 | Config & logging |
| 0.4.0 | 2026-01-09 | #3 | Codex support |
| 0.3.0 | 2026-01-09 | #2 | GitHub Actions |
| 0.2.0 | 2026-01-09 | #1 | Beads backend |
| 0.1.0 | 2026-01-09 | - | Initial release |

---

## Upgrade Notes

### 0.12.x → 0.13.x (Curb → Cub)
- Update all `curb` references to `cub`
- Rename config: `.curb.json` → `.cub.json`
- Update env vars: `CURB_*` → `CUB_*`
- Move config dir: `~/.config/curb/` → `~/.config/cub/`
- See [UPGRADING.md](UPGRADING.md) for detailed migration steps

### 0.8.x → 0.9.x (Flag → Subcommand)
- `curb --init` → `curb init`
- `curb --status` → `curb status`
- `curb` → `curb run`
- Legacy flags show deprecation warnings but still work

---

## Test Coverage History

| Version | Tests |
|---------|-------|
| 0.13.0 | 790 |
| 0.11.0 | 732 |
| 0.5.0 | 189 |
| 0.1.0 | ~20 |
