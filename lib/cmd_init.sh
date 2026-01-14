#!/usr/bin/env bash
#
# cmd_init.sh - init subcommand implementation
#

# Include guard
if [[ -n "${_CUB_CMD_INIT_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_INIT_SH_LOADED=1

cmd_init_help() {
    cat <<'EOF'
cub init [--global] [--type TYPE] [<directory>]

Initialize cub in a project or globally.

USAGE:
  cub init              Initialize in current directory (interactive)
  cub init --global    Set up global configuration
  cub init <dir>       Initialize in specific directory (interactive)
  cub init --type nextjs <dir>   Initialize with specific type (non-interactive)

OPTIONS:
  --global              Set up global configuration (~/.config/cub)
                        Creates config templates and hook directories.
                        Only needs to run once per system.

  --type TYPE           Specify project type directly (nextjs, react, node, python, go, rust, generic)
                        Skips interactive prompts and auto-detects if not specified.

  <directory>           Directory to initialize (default: current dir)
                        Creates prd.json, PROMPT.md, AGENT.md, etc.

WHAT IT CREATES:
  prd.json              Task backlog in JSON format
  .cub/
    ├── prompt.md        System prompt template
    ├── agent.md         Build/run instructions (customized by project type)
    ├── progress.txt     Progress tracking (auto-updated)
    └── fix_plan.md      Issue tracking (auto-updated)
  .gitignore            With cub patterns

SUPPORTED PROJECT TYPES:
  nextjs  - Next.js projects (React + Next.js framework)
  react   - React projects
  node    - Node.js / JavaScript projects
  python  - Python projects
  go      - Go projects
  rust    - Rust projects
  generic - Generic/unknown project type

GLOBAL SETUP:
  ~/.config/cub/config.json       Configuration defaults
  ~/.config/cub/hooks/            Hook directories

EXAMPLES:
  # Initialize in current directory (with prompts)
  cub init

  # Initialize specific project (with prompts)
  cub init ~/my-project

  # Initialize with auto-detection
  cub init --type auto /path/to/project

  # Initialize with specific type (no prompts)
  cub init --type nextjs /path/to/project

  # Set up system-wide defaults
  cub init --global

SEE ALSO:
  cub --help       Show all commands
  cub status       Check project status
EOF
}

# Prompt user for project type with menu
_prompt_project_type() {
    local detected_type="$1"
    local project_type=""

    echo ""
    echo "What type of project is this?"
    echo ""
    echo "  1) nextjs  - Next.js (React + framework)"
    echo "  2) react   - React"
    echo "  3) node    - Node.js / JavaScript"
    echo "  4) python  - Python"
    echo "  5) go      - Go"
    echo "  6) rust    - Rust"
    echo "  7) generic - Generic / Unknown"
    echo ""
    if [[ -n "$detected_type" && "$detected_type" != "generic" ]]; then
        echo "Detected: $detected_type (press Enter to confirm)"
    fi
    echo ""

    read -p "Select (1-7) [default: ${detected_type:-generic}]: " -r choice

    case "$choice" in
        1) project_type="nextjs" ;;
        2) project_type="react" ;;
        3) project_type="node" ;;
        4) project_type="python" ;;
        5) project_type="go" ;;
        6) project_type="rust" ;;
        7) project_type="generic" ;;
        "") project_type="${detected_type:-generic}" ;;
        *)
            _log_error_console "Invalid choice: $choice"
            return 1
            ;;
    esac

    echo "$project_type"
    return 0
}

# Generate agent.md template based on project type
_generate_agent_template() {
    local project_type="$1"

    case "$project_type" in
        nextjs)
            cat <<'EOF'
# Agent Instructions

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

<!-- Brief description of what this project does -->

## Tech Stack

- Next.js / React
- TypeScript / JavaScript
- Node.js
- <!-- Add other key dependencies -->

## Development Setup

```bash
# Install dependencies
npm install

# Or with other package managers:
# yarn install
# bun install
# pnpm install
```

## Running the Project

```bash
# Development server
npm run dev

# Production build
npm run build
npm start
```

## Feedback Loops

Run these before committing:

```bash
# Type checking
npm run typecheck

# Tests
npm test

# Linting
npm run lint

# Build
npm run build
```

## Project Structure

```
├── src/
│   ├── pages/         # Next.js pages
│   ├── components/    # React components
│   ├── lib/           # Utilities
│   └── styles/        # CSS/Styling
├── public/            # Static assets
├── specs/             # Specifications
├── tests/             # Test files
├── prd.json           # Task backlog
├── progress.txt       # Session learnings
└── AGENT.md           # This file
```

## Key Files

<!-- List important files the agent should know about -->

## Gotchas & Learnings

<!-- Add things you learn while working on this project -->

## Common Commands

```bash
npm run dev      # Start dev server
npm run build    # Build for production
npm test         # Run tests
npm run lint     # Run linter
npm run format   # Format code
```
EOF
            ;;

        react)
            cat <<'EOF'
# Agent Instructions

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

<!-- Brief description of what this project does -->

## Tech Stack

- React
- TypeScript / JavaScript
- Node.js / Vite / Create React App
- <!-- Add other key dependencies -->

## Development Setup

```bash
# Install dependencies
npm install

# Or with other package managers:
# yarn install
# bun install
# pnpm install
```

## Running the Project

```bash
# Development server
npm run dev
# or npm start (for CRA)

# Production build
npm run build
```

## Feedback Loops

Run these before committing:

```bash
# Type checking (if using TypeScript)
npm run typecheck

# Tests
npm test

# Linting
npm run lint

# Build
npm run build
```

## Project Structure

```
├── src/
│   ├── components/    # React components
│   ├── pages/         # Page components
│   ├── lib/           # Utilities
│   └── styles/        # CSS/Styling
├── public/            # Static assets
├── specs/             # Specifications
├── tests/             # Test files
├── prd.json           # Task backlog
├── progress.txt       # Session learnings
└── AGENT.md           # This file
```

## Key Files

<!-- List important files the agent should know about -->

## Gotchas & Learnings

<!-- Add things you learn while working on this project -->

## Common Commands

```bash
npm run dev      # Start dev server
npm run build    # Build for production
npm test         # Run tests
npm run lint     # Run linter
```
EOF
            ;;

        node)
            cat <<'EOF'
# Agent Instructions

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

<!-- Brief description of what this project does -->

## Tech Stack

- Node.js
- TypeScript / JavaScript
- <!-- Add frameworks: Express, Fastify, etc. -->
- <!-- Add other key dependencies -->

## Development Setup

```bash
# Install dependencies
npm install

# Or with other package managers:
# yarn install
# bun install
# pnpm install
```

## Running the Project

```bash
# Development
npm run dev

# Or if no dev script:
node src/index.js
# or
npm start
```

## Feedback Loops

Run these before committing:

```bash
# Type checking (if using TypeScript)
npm run typecheck

# Tests
npm test

# Linting
npm run lint

# Build (if applicable)
npm run build
```

## Project Structure

```
├── src/
│   ├── index.js      # Entry point
│   ├── routes/       # API routes
│   ├── lib/          # Utilities
│   └── middleware/   # Custom middleware
├── tests/            # Test files
├── specs/            # Specifications
├── prd.json          # Task backlog
├── progress.txt      # Session learnings
└── AGENT.md          # This file
```

## Key Files

<!-- List important files the agent should know about -->

## Gotchas & Learnings

<!-- Add things you learn while working on this project -->

## Common Commands

```bash
npm run dev      # Start development server
npm test         # Run tests
npm run lint     # Run linter
npm start        # Start production server
```
EOF
            ;;

        python)
            cat <<'EOF'
# Agent Instructions

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

<!-- Brief description of what this project does -->

## Tech Stack

- Python 3.x
- <!-- Add frameworks: Django, FastAPI, Flask, etc. -->
- <!-- Add other key dependencies -->

## Development Setup

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or with poetry:
# poetry install

# Or with pipenv:
# pipenv install
```

## Running the Project

```bash
# Activate virtual environment first
source venv/bin/activate

# Run the application
python main.py

# Or with a framework like Flask:
# flask run

# Or with FastAPI:
# uvicorn main:app --reload
```

## Feedback Loops

Run these before committing:

```bash
# Type checking
mypy .

# Tests
pytest

# Linting and formatting
ruff check .
black --check .

# Or use other tools:
# pylint .
# flake8 .
```

## Project Structure

```
├── src/
│   ├── main.py       # Entry point
│   ├── app/          # Application code
│   └── lib/          # Utilities
├── tests/            # Test files
├── specs/            # Specifications
├── requirements.txt  # Dependencies
├── pyproject.toml    # Project config
├── prd.json          # Task backlog
├── progress.txt      # Session learnings
└── AGENT.md          # This file
```

## Key Files

<!-- List important files the agent should know about -->

## Gotchas & Learnings

<!-- Add things you learn while working on this project -->

## Common Commands

```bash
python main.py       # Run application
pytest               # Run tests
mypy .               # Type check
ruff check .         # Lint code
black .              # Format code
pip freeze           # See installed packages
```
EOF
            ;;

        go)
            cat <<'EOF'
# Agent Instructions

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

<!-- Brief description of what this project does -->

## Tech Stack

- Go
- <!-- Add frameworks: Gin, Echo, etc. -->
- <!-- Add other key dependencies -->

## Development Setup

```bash
# Install dependencies
go mod download

# Or initialize a new module:
# go mod init github.com/user/project
```

## Running the Project

```bash
# Development
go run main.go

# Or run all in current directory:
# go run .

# Build binary
go build -o app
./app
```

## Feedback Loops

Run these before committing:

```bash
# Format code
go fmt ./...

# Run tests
go test ./...

# Lint code
golangci-lint run ./...

# Type checking is built-in to Go compiler

# Build
go build -o app
```

## Project Structure

```
├── main.go           # Entry point
├── cmd/              # Command-line tools
├── internal/         # Private packages
├── pkg/              # Public packages
├── tests/            # Test files
├── go.mod            # Module definition
├── go.sum            # Dependency checksums
├── specs/            # Specifications
├── prd.json          # Task backlog
├── progress.txt      # Session learnings
└── AGENT.md          # This file
```

## Key Files

<!-- List important files the agent should know about -->

## Gotchas & Learnings

<!-- Add things you learn while working on this project -->

## Common Commands

```bash
go run main.go       # Run application
go test ./...        # Run tests
go fmt ./...         # Format code
go build -o app      # Build binary
go mod tidy          # Clean up dependencies
```
EOF
            ;;

        rust)
            cat <<'EOF'
# Agent Instructions

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

<!-- Brief description of what this project does -->

## Tech Stack

- Rust
- <!-- Add frameworks or libraries -->
- <!-- Add other key dependencies -->

## Development Setup

```bash
# Install dependencies
cargo fetch

# Or let cargo handle it automatically:
# cargo build
```

## Running the Project

```bash
# Development
cargo run

# With arguments:
# cargo run -- --arg value

# Debug build
cargo build
./target/debug/app
```

## Feedback Loops

Run these before committing:

```bash
# Format code
cargo fmt

# Lint code (clippy)
cargo clippy -- -D warnings

# Run tests
cargo test

# Build
cargo build --release
```

## Project Structure

```
├── src/
│   ├── main.rs       # Entry point (or lib.rs for libraries)
│   └── lib.rs        # Library code
├── tests/            # Integration tests
├── benches/          # Benchmarks
├── Cargo.toml        # Project manifest
├── Cargo.lock        # Dependency lock file
├── specs/            # Specifications
├── prd.json          # Task backlog
├── progress.txt      # Session learnings
└── AGENT.md          # This file
```

## Key Files

<!-- List important files the agent should know about -->

## Gotchas & Learnings

<!-- Add things you learn while working on this project -->

## Common Commands

```bash
cargo run            # Run application
cargo test           # Run tests
cargo fmt            # Format code
cargo clippy         # Lint code
cargo build --release  # Build optimized binary
cargo doc --open     # Generate and view docs
```
EOF
            ;;

        *)
            # Generic template
            cat <<'EOF'
# Agent Instructions

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

<!-- Brief description of what this project does -->

## Tech Stack

<!-- Languages, frameworks, key dependencies -->

## Development Setup

```bash
# Install dependencies
# npm install / bun install / pip install -r requirements.txt / etc.
```

## Running the Project

```bash
# Development server
# npm run dev / bun dev / python main.py / etc.
```

## Feedback Loops

Run these before committing:

```bash
# Type checking
# npx tsc --noEmit / mypy . / etc.

# Tests
# npm test / bun test / pytest / etc.

# Linting
# npm run lint / eslint . / ruff check . / etc.

# Build (if applicable)
# npm run build / bun build / etc.
```

## Project Structure

```
├── src/           # Source code
├── specs/         # Specifications
├── tests/         # Test files
├── prd.json       # Task backlog
├── progress.txt   # Session learnings
└── AGENT.md       # This file
```

## Key Files

<!-- List important files the agent should know about -->

## Gotchas & Learnings

<!-- Add things you learn while working on this project -->

## Common Commands

<!-- Useful commands discovered during development -->
EOF
            ;;
    esac
}

cmd_init() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_init_help
        return 0
    fi

    # Parse flags
    local global_init=false
    local project_type=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --global)
                global_init=true
                shift
                ;;
            --type)
                if [[ $# -lt 2 ]]; then
                    _log_error_console "Error: --type requires an argument"
                    return 1
                fi
                project_type="$2"
                shift 2
                ;;
            *)
                break
                ;;
        esac
    done

    local target_dir="${1:-.}"

    # ============================================================================
    # Global initialization (--global flag)
    # ============================================================================
    if [[ "$global_init" == "true" ]]; then
        log_info "Initializing global cub configuration"
        echo ""

        # Check dependencies
        log_info "Checking dependencies..."
        local missing_deps=()

        # Check for jq
        if ! command -v jq >/dev/null 2>&1; then
            missing_deps+=("jq")
            _log_error_console "Missing dependency: jq"
            echo "  Install with: brew install jq (macOS) or apt-get install jq (Linux)"
        else
            log_success "Found jq"
        fi

        # Check for at least one harness
        local harness_found=false
        if command -v claude >/dev/null 2>&1; then
            log_success "Found claude harness"
            harness_found=true
        fi
        if command -v codex >/dev/null 2>&1; then
            log_success "Found codex harness"
            harness_found=true
        fi

        if [[ "$harness_found" == "false" ]]; then
            missing_deps+=("harness (claude or codex)")
            _log_error_console "No harness found (need claude or codex)"
            echo "  Install Claude Code: https://claude.com/claude-code"
            echo "  Or Codex: npm install -g @anthropic/codex"
        fi

        # Exit if dependencies missing
        if [[ ${#missing_deps[@]} -gt 0 ]]; then
            echo ""
            _log_error_console "Missing required dependencies. Please install them and try again."
            return 1
        fi

        echo ""
        log_info "Creating global directory structure..."

        # Create XDG directories
        cub_ensure_dirs

        local config_dir
        config_dir="$(cub_config_dir)"
        local config_file="${config_dir}/config.json"
        local hooks_dir="${config_dir}/hooks"

        log_success "Created ${config_dir}"
        log_success "Created $(cub_logs_dir)"
        log_success "Created $(cub_cache_dir)"

        # Create config file with sensible defaults
        log_info "Creating default configuration..."

        if [[ -f "$config_file" ]]; then
            log_warn "Config file already exists at ${config_file}"
            log_warn "Skipping config creation (remove file to recreate)"
        else
            cat > "$config_file" <<'EOF'
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
EOF
            log_success "Created ${config_file}"
        fi

        # Create hook directories
        log_info "Creating hook directories..."

        local hook_types=("pre-loop" "pre-task" "post-task" "on-error" "post-loop")
        for hook_type in "${hook_types[@]}"; do
            local hook_dir="${hooks_dir}/${hook_type}.d"
            if [[ ! -d "$hook_dir" ]]; then
                mkdir -p "$hook_dir"
                log_success "Created ${hook_dir}"
            else
                log_warn "${hook_dir} already exists"
            fi
        done

        echo ""
        log_success "Global cub configuration complete!"
        echo ""
        echo "Configuration:"
        echo "  Config file:  ${config_file}"
        echo "  Hooks:        ${hooks_dir}"
        echo "  Logs:         $(cub_logs_dir)"
        echo ""
        echo "Next steps:"
        echo "  1. Review and customize ${config_file}"
        echo "  2. Add custom hooks to ${hooks_dir}/<hook-type>.d/"
        echo "  3. Initialize a project with: cub init <project-dir>"
        echo "  4. Start building: cd <project-dir> && cub"
        echo ""
        echo "Configuration options:"
        echo "  harness.default       - Default harness to use (auto|claude|codex)"
        echo "  harness.priority      - Order to try harnesses when auto"
        echo "  budget.default        - Default token budget per run"
        echo "  loop.max_iterations   - Maximum iterations before stopping"
        echo "  clean_state.require_commit - Require harness to commit changes"
        echo ""

        return 0
    fi

    # ============================================================================
    # Project initialization (default behavior)
    # ============================================================================

    # Get project name from directory
    local project_name
    project_name=$(basename "$(cd "$target_dir" && pwd)")
    local prefix
    prefix=$(echo "$project_name" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]' | head -c 8)
    [[ -z "$prefix" ]] && prefix="prd"

    log_info "Initializing cub in: ${target_dir}"
    log_info "Project prefix: ${prefix}"

    cd "$target_dir" || return 1

    # Detect and set project type
    local detected_type
    detected_type=$(detect_project_type ".")
    log_debug "Auto-detected project type: ${detected_type}"

    if [[ -z "$project_type" ]]; then
        # No --type flag provided, show interactive prompt
        project_type=$(_prompt_project_type "$detected_type") || return 1
    elif [[ "$project_type" == "auto" ]]; then
        # --type auto was explicitly set, use detected type
        project_type="$detected_type"
    else
        # Validate the provided project_type
        case "$project_type" in
            nextjs|react|node|python|go|rust|generic)
                log_debug "Using provided project type: ${project_type}"
                ;;
            *)
                _log_error_console "Invalid project type: $project_type"
                _log_error_console "Supported types: nextjs, react, node, python, go, rust, generic"
                return 1
                ;;
        esac
    fi

    log_info "Using project type: ${project_type}"
    echo ""

    # Create specs directory
    if [[ ! -d "specs" ]]; then
        mkdir -p specs
        log_success "Created specs/"
    fi

    # Create prd.json if not exists
    if [[ ! -f "prd.json" ]]; then
        cat > prd.json <<EOF
{
  "projectName": "${project_name}",
  "branchName": "feature/${project_name}",
  "prefix": "${prefix}",
  "projectType": "${project_type}",
  "tasks": [
    {
      "id": "${prefix}-init",
      "type": "task",
      "title": "Project initialization",
      "description": "Set up the initial project structure and configuration",
      "acceptanceCriteria": [
        "Project builds successfully",
        "Basic structure in place",
        "typecheck passes",
        "tests pass (or test framework configured)"
      ],
      "priority": "P0",
      "status": "open",
      "dependsOn": [],
      "notes": ""
    }
  ]
}
EOF
        log_success "Created prd.json with initial task"
    else
        log_warn "prd.json already exists, skipping"
    fi

    # Detect layout and ensure layout root directory exists
    local layout
    layout=$(detect_layout ".")
    log_debug "Using layout: ${layout}"

    local layout_root
    layout_root=$(get_layout_root ".")
    mkdir -p "$layout_root"

    # Create prompt.md in layout root
    local prompt_file
    prompt_file=$(get_prompt_file ".")
    if [[ ! -f "$prompt_file" ]]; then
        cp "${CUB_DIR}/templates/PROMPT.md" "$prompt_file"
        log_success "Created $(basename "$prompt_file")"
    else
        log_warn "$(basename "$prompt_file") already exists, skipping"
    fi

    # Create agent.md in layout root with project-type-specific template
    local agent_file
    agent_file=$(get_agent_file ".")
    if [[ ! -f "$agent_file" ]]; then
        _generate_agent_template "$project_type" > "$agent_file"
        log_success "Created $(basename "$agent_file") for ${project_type} project"
    else
        log_warn "$(basename "$agent_file") already exists, skipping"
    fi

    # Create AGENTS.md symlink for Codex compatibility
    # Codex CLI looks for AGENTS.md in the project root
    if [[ ! -f "AGENTS.md" && ! -L "AGENTS.md" ]]; then
        ln -s .cub/agent.md AGENTS.md
        log_success "Created AGENTS.md symlink (for Codex compatibility)"
    elif [[ -L "AGENTS.md" ]]; then
        log_warn "AGENTS.md symlink already exists, skipping"
    else
        log_warn "AGENTS.md already exists as file, skipping symlink"
    fi

    # Create progress.txt in layout root
    local progress_file
    progress_file=$(get_progress_file ".")
    if [[ ! -f "$progress_file" ]]; then
        cat > "$progress_file" <<EOF
# Progress Log
Started: $(date -u +"%Y-%m-%d")

## Codebase Patterns
<!-- Agent adds discovered patterns here for future iterations -->

## Key Files
<!-- Important files to be aware of -->

---
EOF
        log_success "Created $(basename "$progress_file")"
    else
        log_warn "$(basename "$progress_file") already exists, skipping"
    fi

    # Create fix_plan.md in layout root
    local fix_plan_file
    fix_plan_file=$(get_fix_plan_file ".")
    if [[ ! -f "$fix_plan_file" ]]; then
        cat > "$fix_plan_file" <<EOF
# Fix Plan

Discovered issues and planned improvements.
Agent maintains this file during development.

## High Priority

## Medium Priority

## Low Priority

## Completed
EOF
        log_success "Created $(basename "$fix_plan_file")"
    else
        log_warn "$(basename "$fix_plan_file") already exists, skipping"
    fi

    # Create .gitignore additions
    if [[ -f ".gitignore" ]]; then
        if ! grep -q "# Cub" .gitignore 2>/dev/null; then
            cat >> .gitignore <<EOF

# Cub
*.cub.tmp
EOF
            log_success "Updated .gitignore"
        fi
    else
        cat > .gitignore <<EOF
# Cub
*.cub.tmp
EOF
        log_success "Created .gitignore"
    fi

    echo ""
    log_success "Cub initialized!"
    echo ""
    echo "Next steps:"
    echo "  1. Edit prd.json to add your tasks (use ChatPRD template output)"
    echo "  2. Add specifications to specs/"
    echo "  3. Update AGENT.md with build instructions"
    echo "  4. Run 'cub status' to see task summary"
    echo "  5. Run 'cub' to start the autonomous loop"
    echo ""
    echo "Useful commands:"
    echo "  cub status        Show task progress"
    echo "  cub run --ready   Show ready tasks"
    echo "  cub run --once    Run single iteration"
    echo "  cub run --plan    Run planning mode"
    echo "  cub --harness codex Use OpenAI Codex instead of Claude"
    echo ""

    return 0
}
