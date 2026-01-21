---
title: cub init
description: Initialize cub in a project or set up global configuration.
---

# cub init

Initialize cub configuration in a project directory or set up global system-wide configuration.

---

## Synopsis

```bash
cub init [OPTIONS] [DIRECTORY]
```

---

## Description

The `init` command sets up cub for use. It operates in two modes:

1. **Project initialization** (default) - Sets up cub in a specific project directory
2. **Global initialization** (`--global`) - Sets up system-wide configuration

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--global` | `-g` | Set up global configuration |
| `--interactive` | `-i` | Enable interactive mode with project type menu |
| `--type TYPE` | | Specify project type directly |
| `--backend BACKEND` | | Specify task backend (`beads`, `json`, `auto`) |
| `-h`, `--help` | | Show help message |

### Project Types

Supported values for `--type`:

| Type | Description |
|------|-------------|
| `nextjs` | Next.js projects (React + Next.js framework) |
| `react` | React projects |
| `node` | Node.js / JavaScript projects |
| `python` | Python projects |
| `go` | Go projects |
| `rust` | Rust projects |
| `generic` | Generic/unknown project type |
| `auto` | Auto-detect from project files (default) |

### Task Backends

Supported values for `--backend`:

| Backend | Description |
|---------|-------------|
| `beads` | Use Beads CLI (`bd`) for task management |
| `json` | Use JSON file (`prd.json`) for tasks |
| `auto` | Auto-detect (prefers beads if available) |

---

## Global Initialization

Set up system-wide cub configuration:

```bash
cub init --global
```

### What It Creates

```
~/.config/cub/
├── config.json       # Default configuration
└── hooks/            # Hook directories
    ├── pre-loop.d/
    ├── pre-task.d/
    ├── post-task.d/
    ├── on-error.d/
    └── post-loop.d/

~/.local/share/cub/
└── logs/             # Session logs

~/.cache/cub/         # Cache directory
```

### Default Configuration

The generated `config.json`:

```json
{
  "harness": {
    "default": "auto",
    "priority": ["claude", "gemini", "codex", "opencode"]
  },
  "budget": {
    "default": 1000000,
    "warn_at": 0.8
  },
  "loop": {
    "max_iterations": 100
  },
  "clean_state": {
    "require_commit": true,
    "require_tests": false
  },
  "hooks": {
    "enabled": true
  }
}
```

### Dependency Check

Global init verifies required dependencies:

- **jq** - Required for JSON processing
- **Harness** - At least one of: `claude`, `codex`, `gemini`, `opencode`

---

## Project Initialization

Initialize cub in a project directory:

```bash
# Initialize current directory
cub init

# Initialize specific directory
cub init ~/projects/my-app

# With specific project type
cub init --type python

# Interactive mode (prompts for type)
cub init --interactive

# With specific backend
cub init --backend beads
```

### What It Creates

Depending on backend and project type:

```
my-project/
├── .cub/
│   ├── README.md        # Quick reference guide
│   ├── prompt.md        # System prompt template
│   ├── agent.md         # Build/run instructions
│   ├── progress.txt     # Progress tracking
│   ├── fix_plan.md      # Issue tracking
│   └── guardrails.md    # Institutional memory
├── .claude/
│   └── commands/        # Claude Code skills
│       ├── cub:triage.md
│       ├── cub:architect.md
│       └── cub:plan.md
├── .beads/              # (beads backend only)
├── prd.json             # (json backend only)
├── specs/               # Specifications directory
├── AGENTS.md            # Symlink to .cub/agent.md
└── .gitignore           # Updated with cub patterns
```

### Project Type Detection

Cub auto-detects project type from files:

| Files Found | Detected Type |
|-------------|---------------|
| `next.config.*`, `.next/` | `nextjs` |
| `package.json` with React | `react` |
| `package.json` | `node` |
| `pyproject.toml`, `setup.py`, `requirements.txt` | `python` |
| `go.mod` | `go` |
| `Cargo.toml` | `rust` |
| Other | `generic` |

### Generated agent.md

The `agent.md` file is customized for your project type:

=== "Next.js"

    ```markdown
    # Agent Instructions

    ## Tech Stack
    - Next.js / React
    - TypeScript / JavaScript

    ## Feedback Loops
    npm run typecheck
    npm test
    npm run lint
    npm run build
    ```

=== "Python"

    ```markdown
    # Agent Instructions

    ## Tech Stack
    - Python 3.x

    ## Feedback Loops
    mypy .
    pytest
    ruff check .
    black --check .
    ```

=== "Go"

    ```markdown
    # Agent Instructions

    ## Tech Stack
    - Go

    ## Feedback Loops
    go fmt ./...
    go test ./...
    golangci-lint run ./...
    ```

---

## Examples

### First-Time Setup

```bash
# 1. Set up global configuration
cub init --global

# 2. Initialize your project
cd my-project
cub init

# 3. Start working
cub plan run  # or create tasks manually
cub run
```

### Specific Project Type

```bash
# Python project with beads
cub init --type python --backend beads

# Node.js project with JSON backend
cub init --type node --backend json
```

### Interactive Mode

```bash
cub init --interactive
```

Output:

```
What type of project is this?

  1) nextjs  - Next.js (React + framework)
  2) react   - React
  3) node    - Node.js / JavaScript
  4) python  - Python
  5) go      - Go
  6) rust    - Rust
  7) generic - Generic / Unknown

Detected: python (press Enter to confirm)

Select (1-7) [default: python]:
```

---

## Layout Detection

Cub supports different file layouts:

| Layout | Config Location |
|--------|-----------------|
| Default | `.cub/` directory |
| Root | Project root |

The layout is auto-detected based on existing files.

---

## Claude Code Skills

Init installs Claude Code skills for the plan pipeline:

| Skill | Description |
|-------|-------------|
| `cub:spec` | Feature specification interview |
| `cub:capture` | Quick idea capture |
| `cub:triage` | Requirements refinement |
| `cub:architect` | Technical design |
| `cub:plan` | Task decomposition |

Use with Claude Code:

```bash
claude
# Then: /cub:spec
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Initialization successful |
| `1` | Error (missing dependencies, invalid options) |

---

## Related Commands

- [`cub doctor`](doctor.md) - Diagnose configuration issues
- [`cub plan`](plan.md) - Run the planning pipeline
- [`cub run`](run.md) - Execute the task loop

---

## See Also

- [Installation Guide](../getting-started/install.md) - Complete installation instructions
- [Configuration Reference](../guide/configuration/reference.md) - All configuration options
- [Quick Start](../getting-started/quickstart.md) - Get started in 5 minutes
