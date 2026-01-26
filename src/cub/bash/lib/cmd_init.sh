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
cub init [--global] [--interactive] [--type TYPE] [--backend BACKEND] [<directory>]

Initialize cub in a project or globally.

USAGE:
  cub init              Initialize in current directory (auto-detects project type)
  cub init --global    Set up global configuration
  cub init <dir>       Initialize in specific directory (auto-detects)
  cub init --interactive   Interactive mode with project type menu
  cub init --type nextjs   Initialize with specific type

OPTIONS:
  --global              Set up global configuration (~/.config/cub)
                        Creates config templates and hook directories.
                        Only needs to run once per system.

  --interactive, -i     Enable interactive mode with project type menu.
                        By default, cub init auto-detects and runs without prompts.

  --type TYPE           Specify project type directly (nextjs, react, node, python, go, rust, generic, auto)
                        By default, auto-detects from project files.

  --backend BACKEND     Specify task backend (beads, json, auto)
                        Default is auto-detection (beads if available, else json).

  <directory>           Directory to initialize (default: current dir)

WHAT IT CREATES:
  .beads/               Task management (if using beads backend)
  prd.json              Task backlog (if using JSON backend)
  .cub/
    ├── README.md        Quick reference guide (editable)
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
  # Initialize in current directory (auto-detects project type)
  cub init

  # Initialize specific project (auto-detects)
  cub init ~/my-project

  # Interactive mode (prompts for project type)
  cub init --interactive
  cub init -i ~/my-project

  # Initialize with specific type
  cub init --type nextjs /path/to/project

  # Initialize with specific backend
  cub init --backend beads

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

    # Use a single printf block to ensure menu is fully printed before prompt
    # This fixes buffering issues where read prompt appears before menu
    {
        printf '\n'
        printf 'What type of project is this?\n'
        printf '\n'
        printf '  1) nextjs  - Next.js (React + framework)\n'
        printf '  2) react   - React\n'
        printf '  3) node    - Node.js / JavaScript\n'
        printf '  4) python  - Python\n'
        printf '  5) go      - Go\n'
        printf '  6) rust    - Rust\n'
        printf '  7) generic - Generic / Unknown\n'
        printf '\n'
        if [[ -n "$detected_type" && "$detected_type" != "generic" ]]; then
            printf 'Detected: %s (press Enter to confirm)\n' "$detected_type"
        fi
        printf '\n'
    } >&2

    # Read from /dev/tty to ensure we get user input even if stdin is redirected
    printf 'Select (1-7) [default: %s]: ' "${detected_type:-generic}" >&2
    read -r choice </dev/tty

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


cmd_init() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_init_help
        return 0
    fi

    # Parse flags
    local global_init=false
    local interactive_init=false
    local project_type=""
    local backend=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --global)
                global_init=true
                shift
                ;;
            --interactive|-i)
                interactive_init=true
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
            --backend)
                if [[ $# -lt 2 ]]; then
                    _log_error_console "Error: --backend requires an argument"
                    return 1
                fi
                backend="$2"
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
        # No --type flag provided
        if [[ "$interactive_init" == "true" ]]; then
            # Interactive mode requested: show prompt
            # Check if we have a TTY for interaction
            if [[ -t 0 ]] || [[ -e /dev/tty ]]; then
                project_type=$(_prompt_project_type "$detected_type") || return 1
            else
                _log_error_console "Error: --interactive requires a TTY"
                return 1
            fi
        else
            # Default: use auto-detected type without prompting
            project_type="$detected_type"
            log_info "Auto-detected project type: ${project_type}"
        fi
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

    # ============================================================================
    # Determine task backend early (affects which files we create)
    # ============================================================================

    local selected_backend
    if [[ -n "$backend" ]]; then
        # Explicit backend specified via --backend flag
        case "$backend" in
            beads|bd)
                selected_backend="beads"
                ;;
            json|prd)
                selected_backend="json"
                ;;
            jsonl)
                selected_backend="jsonl"
                ;;
            auto)
                # Auto-detect: prefer beads if available, otherwise jsonl
                if command -v bd >/dev/null 2>&1; then
                    selected_backend="beads"
                else
                    selected_backend="jsonl"
                fi
                ;;
            *)
                _log_error_console "Invalid backend: $backend"
                _log_error_console "Supported backends: beads, jsonl, json, auto"
                return 1
                ;;
        esac
    elif [[ -n "${CUB_BACKEND:-}" ]]; then
        # Explicit backend specified via environment variable
        case "$CUB_BACKEND" in
            beads|bd)
                selected_backend="beads"
                ;;
            json|prd)
                selected_backend="json"
                ;;
            jsonl)
                selected_backend="jsonl"
                ;;
            auto)
                # Auto-detect: prefer beads if available, otherwise jsonl
                if command -v bd >/dev/null 2>&1; then
                    selected_backend="beads"
                else
                    selected_backend="jsonl"
                fi
                ;;
            *)
                _log_error_console "Invalid CUB_BACKEND: $CUB_BACKEND"
                _log_error_console "Supported backends: beads, jsonl, json, auto"
                return 1
                ;;
        esac
    else
        # No explicit backend specified - default to JSONL (Python runtime will choose beads if .beads/ exists)
        selected_backend="jsonl"
    fi

    log_info "Using task backend: ${selected_backend}"

    # Create specs directory
    if [[ ! -d "specs" ]]; then
        mkdir -p specs
        log_success "Created specs/"
    fi

    # Create prd.json only for json backend
    if [[ "$selected_backend" == "json" ]]; then
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
    fi

    # Detect layout and ensure layout root directory exists
    local layout
    layout=$(detect_layout ".")
    log_debug "Using layout: ${layout}"

    local layout_root
    layout_root=$(get_layout_root ".")
    mkdir -p "$layout_root"

    # Create prompt.md in layout root (customized for selected backend)
    local prompt_file
    prompt_file=$(get_prompt_file ".")
    if [[ ! -f "$prompt_file" ]]; then
        if [[ "$selected_backend" == "beads" ]]; then
            # Beads backend: use bd commands
            sed -e 's|bd close vs prd.json update|bd close|g' \
                -e 's|(either `bd close` or prd.json update)|(`bd close <task-id>`)|g' \
                "${CUB_DIR}/templates/PROMPT.md" > "$prompt_file"
        else
            # JSON/JSONL backend: use cub task close or task status update
            sed -e 's|bd close vs prd.json update|cub task close|g' \
                -e 's|(either `bd close` or prd.json update)|(use `cub task close <task-id>` to close tasks)|g' \
                "${CUB_DIR}/templates/PROMPT.md" > "$prompt_file"
        fi
        log_success "Created $(basename "$prompt_file") (${selected_backend} backend)"
    else
        log_warn "$(basename "$prompt_file") already exists, skipping"
    fi

    # Create agent.md in layout root from template
    local agent_file
    agent_file=$(get_agent_file ".")
    if [[ ! -f "$agent_file" ]]; then
        cp "${CUB_DIR}/templates/AGENT.md" "$agent_file"
        log_success "Created $(basename "$agent_file")"
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
        cp "${CUB_DIR}/templates/progress.txt" "$progress_file"
        log_success "Created $(basename "$progress_file")"
    else
        log_warn "$(basename "$progress_file") already exists, skipping"
    fi

    # Create fix_plan.md in layout root
    local fix_plan_file
    fix_plan_file=$(get_fix_plan_file ".")
    if [[ ! -f "$fix_plan_file" ]]; then
        cp "${CUB_DIR}/templates/fix_plan.md" "$fix_plan_file"
        log_success "Created $(basename "$fix_plan_file")"
    else
        log_warn "$(basename "$fix_plan_file") already exists, skipping"
    fi

    # Create guardrails.md in layout root
    local guardrails_file
    guardrails_file="${layout_root}/guardrails.md"
    if [[ ! -f "$guardrails_file" ]]; then
        cp "${CUB_DIR}/templates/guardrails.md" "$guardrails_file"
        log_success "Created $(basename "$guardrails_file")"
    else
        log_warn "$(basename "$guardrails_file") already exists, skipping"
    fi

    # Create README.md in layout root
    local readme_file
    readme_file="${layout_root}/README.md"
    if [[ ! -f "$readme_file" ]]; then
        cp "${CUB_DIR}/templates/README.md" "$readme_file"
        log_success "Created $(basename "$readme_file")"
    else
        log_warn "$(basename "$readme_file") already exists, skipping"
    fi

    # Install Claude Code skills for prep workflow
    if [[ -d "${CUB_DIR}/templates/commands" ]]; then
        local commands_dir=".claude/commands"
        mkdir -p "$commands_dir"

        local skills_installed=0
        for skill_file in "${CUB_DIR}/templates/commands"/*.md; do
            if [[ -f "$skill_file" ]]; then
                local skill_name
                skill_name=$(basename "$skill_file")
                if [[ ! -f "${commands_dir}/${skill_name}" ]]; then
                    cp "$skill_file" "${commands_dir}/${skill_name}"
                    ((++skills_installed))
                fi
            fi
        done

        if [[ $skills_installed -gt 0 ]]; then
            log_success "Installed ${skills_installed} Claude Code skills to ${commands_dir}/"
        fi
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

    # ============================================================================
    # Initialize the selected backend
    # ============================================================================

    if [[ "$selected_backend" == "beads" ]]; then
        if ! command -v bd >/dev/null 2>&1; then
            _log_error_console "Error: beads (bd) is not installed"
            _log_error_console "Install with: npm install -g @beads/bd"
            return 1
        fi

        # Initialize beads in silent mode
        if bd init --stealth >/dev/null 2>&1; then
            log_success "Initialized beads task backend"
        else
            _log_error_console "Error: Failed to initialize beads backend"
            return 1
        fi
    elif [[ "$selected_backend" == "jsonl" ]]; then
        # JSONL backend doesn't need explicit initialization
        # It will be created in .cub/tasks.jsonl when first task is created
        mkdir -p .cub
        log_success "Initialized JSONL task backend (ready for first task)"
    fi
    # json backend already initialized via prd.json creation above

    echo ""
    log_success "Cub initialized!"
    echo ""
    echo "Project type: ${project_type}"
    echo "Backend: ${selected_backend}"
    echo ""
    echo "Next steps:"
    if [[ "$selected_backend" == "beads" ]]; then
        echo "  1. Use 'bd create' to add tasks"
        echo "  2. Add specifications to specs/"
        echo "  3. Update AGENT.md with build instructions"
        echo "  4. Run 'cub' to start the autonomous loop"
    else
        echo "  1. Edit prd.json to add your tasks"
        echo "  2. Add specifications to specs/"
        echo "  3. Update AGENT.md with build instructions"
        echo "  4. Run 'cub' to start the autonomous loop"
    fi
    echo ""

    return 0
}
