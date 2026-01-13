# Changelog

All notable changes to Cub (formerly Curb) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
