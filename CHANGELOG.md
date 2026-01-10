# Changelog

All notable changes to Curb are documented in this file.

## [1.0.0] - 2026-01-10

The inaugural release of Curb! A complete autonomous AI coding agent harness combining the Ralph Wiggum technique with beads-style task management.

### Added - Foundation Phase
- **Configuration System**: XDG-compliant global and project-level configuration with full precedence hierarchy (CLI > env > project > global > defaults)
- **Structured Logging**: JSONL-format logs with task lifecycle events, timestamps, durations, and git SHAs for complete audit trails
- **Task Management**: Dual backend support for both beads CLI and simple JSON-based prd.json task formats with unified interface

### Added - Reliability Phase
- **Clean State Verification**: Git-based state checking to ensure commits before running tasks with configurable enforcement
- **Test Runner Integration**: Automatic test command detection (npm, yarn, make, pytest, go, cargo) with optional execution before proceeding
- **Budget Tracking**: Token-based budget enforcement with warning thresholds to prevent runaway costs from AI API calls
- **Budget Warnings**: Alert when token usage reaches configurable thresholds (default 80%)
- **Structured Logging**: Enhanced task_end events with tokens_used, exit_code, and duration metrics

### Added - Extensibility Phase
- **Claude Code Harness**: Full support for Claude Code CLI with system prompt injection via --append-system-prompt
- **OpenAI Codex Harness**: Integration with Codex CLI in full-auto mode for autonomous operation
- **Google Gemini Harness**: Support for Gemini CLI with YOLO mode (-y) for autonomous execution
- **OpenCode Harness**: Integration with OpenCode CLI with token extraction from JSON output
- **Harness Auto-Detection**: Intelligent detection of available harnesses with configurable priority ordering
- **Per-Task Model Selection**: Tasks can specify model via labels (model:haiku, model:sonnet, model:opus-4.5)
- **Harness Capability Detection**: Automatic detection of harness capabilities like token extraction and streaming support
- **5 Lifecycle Hooks**: Extension points (pre-loop, pre-task, post-task, on-error, post-loop) for custom integrations
- **Hook Examples**: Reference implementations for Slack notifications, Datadog metrics, and PagerDuty alerts
- **Global + Project Hooks**: Hook discovery from both ~/.config/curb/hooks/ and ./.curb/hooks/ directories

### Added - Polish Phase
- **Example Hooks**: Ready-to-use hook implementations for:
  - Slack post-task notifications
  - Datadog metrics submission
  - PagerDuty alert creation
- **Comprehensive Documentation**:
  - Enhanced README with all features, usage patterns, and advanced topics
  - Complete CONFIG.md reference for all configuration options
  - UPGRADING.md migration guide for users upgrading from earlier versions
  - Inline code comments explaining complex bash patterns
- **Help Output**: Clear --help screen with all flags and usage examples
- **Migration Tools**: Utilities to convert between prd.json and beads formats for flexible task management

### Features
- **Autonomous Loop**: Runs until all tasks complete with configurable iteration limits
- **Dependency Tracking**: Respects task dependencies, intelligently picks ready (unblocked) tasks
- **Priority Scheduling**: P0-P4 priority-based task selection with proper ordering
- **Epic/Label Filtering**: Target specific epics or labeled tasks for focused execution
- **Bash 4+ Compatibility**: Works on macOS (Bash 3.2+) with bash 4 on Linux via explicit workarounds
- **Streaming Output**: Real-time harness activity visibility
- **Planning Mode**: Codebase analysis and issue discovery for initial project phase
- **Beads Integration**: Full support for beads CLI task backend when present

### Testing
- **Comprehensive Test Suite**: 341+ BATS tests covering:
  - Configuration loading and precedence
  - Logger event emission
  - Task selection algorithms
  - State management and clean checks
  - Budget tracking and enforcement
  - Harness abstraction and detection
  - Hook discovery and execution
  - Integration scenarios
- **E2E Testing**: Full workflow tests with budget enforcement and task completion
- **Test Fixtures**: Valid/invalid task files for validation testing
- **Test Coverage**: All major code paths tested with proper fixtures and mocks

### Documentation
- **README.md** (809 lines): Complete feature overview, installation, quick start, usage, configuration, and troubleshooting
- **CONFIG.md** (523 lines): Comprehensive configuration reference with all options, environment variables, and examples
- **UPGRADING.md** (394 lines): Migration guide for users upgrading from earlier versions
- **AGENT.md**: Build and run instructions for the curb repository itself
- **CONTRIBUTING.md**: Guidelines for contributors
- **PROMPT.md**: Default system prompt template
- **AGENTS.md**: Description of supported AI coding agents
- **Example Hooks**: Working implementations for Slack, Datadog, and PagerDuty integration

### Project Structure
```
curb/
├── curb              # Main CLI script (autonomous loop)
├── curb-init         # Project and global initialization
├── lib/              # Bash libraries
│   ├── xdg.sh        # XDG Base Directory helpers
│   ├── config.sh     # Configuration loading with precedence
│   ├── logger.sh     # Structured JSONL logging
│   ├── harness.sh    # Multi-harness abstraction
│   ├── tasks.sh      # Unified task interface
│   ├── beads.sh      # Beads CLI wrapper
│   ├── hooks.sh      # Hook framework
│   ├── budget.sh     # Token budget tracking
│   └── state.sh      # Git state management
├── tests/            # BATS test suite (341+ tests)
├── docs/             # Comprehensive documentation
├── examples/         # Example hooks and configurations
└── templates/        # Template files for projects
```

### Dependencies
- **Required**: jq (JSON processing)
- **Required**: Bash 4+ (3.2+ on macOS with workarounds)
- **Optional**: beads CLI (for advanced task management)
- **Optional**: AI coding CLI (Claude, Codex, Gemini, or OpenCode)

### Known Limitations
- Bash 3.2 on macOS requires workarounds for advanced variable expansion (${2:-{}} syntax)
- File-based caching needed due to bash subshell scoping limitations
- Hook failures don't block loop by default (unless fail_fast enabled)

### Contributors
- Primary development: @lavallee
- Architecture influenced by Ralph Wiggum technique and beads project

---

## Versioning

Curb follows semantic versioning:
- **1.x.x**: Stable releases with backward compatibility
- **0.x.x** (pre-release): Early development versions

## Installation

```bash
git clone https://github.com/lavallee/curb ~/tools/curb
export PATH="$PATH:$HOME/tools/curb"
curb-init --global
```

For detailed installation and usage, see [README.md](README.md).
