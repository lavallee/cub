#!/usr/bin/env bash
#
# cmd_init.sh - init subcommand implementation
#

# Include guard
if [[ -n "${_CURB_CMD_INIT_SH_LOADED:-}" ]]; then
    return 0
fi
_CURB_CMD_INIT_SH_LOADED=1

cmd_init_help() {
    cat <<'EOF'
curb init [--global] [<directory>]

Initialize curb in a project or globally.

USAGE:
  curb init              Initialize in current directory
  curb init --global    Set up global configuration
  curb init <dir>       Initialize in specific directory

OPTIONS:
  --global              Set up global configuration (~/.config/curb)
                        Creates config templates and hook directories.
                        Only needs to run once per system.

  <directory>           Directory to initialize (default: current dir)
                        Creates prd.json, PROMPT.md, AGENT.md, etc.

WHAT IT CREATES:
  prd.json              Task backlog in JSON format
  PROMPT.md             System prompt template
  AGENT.md              Build/run instructions
  progress.txt          Progress tracking (auto-updated)
  fix_plan.md           Issue tracking (auto-updated)
  .gitignore            With curb patterns

GLOBAL SETUP:
  ~/.config/curb/config.json       Configuration defaults
  ~/.config/curb/hooks/            Hook directories

EXAMPLES:
  # Initialize in current directory
  curb init

  # Initialize specific project
  curb init ~/my-project

  # Set up system-wide defaults
  curb init --global

  # Then initialize a project
  curb init ~/my-project

SEE ALSO:
  curb --help       Show all commands
  curb status       Check project status
EOF
}

cmd_init() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_init_help
        return 0
    fi

    # Parse flags
    local global_init=false
    if [[ "${1:-}" == "--global" ]]; then
        global_init=true
        shift
    fi

    local target_dir="${1:-.}"

    # ============================================================================
    # Global initialization (--global flag)
    # ============================================================================
    if [[ "$global_init" == "true" ]]; then
        log_info "Initializing global curb configuration"
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
        curb_ensure_dirs

        local config_dir
        config_dir="$(curb_config_dir)"
        local config_file="${config_dir}/config.json"
        local hooks_dir="${config_dir}/hooks"

        log_success "Created ${config_dir}"
        log_success "Created $(curb_logs_dir)"
        log_success "Created $(curb_cache_dir)"

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
        log_success "Global curb configuration complete!"
        echo ""
        echo "Configuration:"
        echo "  Config file:  ${config_file}"
        echo "  Hooks:        ${hooks_dir}"
        echo "  Logs:         $(curb_logs_dir)"
        echo ""
        echo "Next steps:"
        echo "  1. Review and customize ${config_file}"
        echo "  2. Add custom hooks to ${hooks_dir}/<hook-type>.d/"
        echo "  3. Initialize a project with: curb init <project-dir>"
        echo "  4. Start building: cd <project-dir> && curb"
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

    log_info "Initializing curb in: ${target_dir}"
    log_info "Project prefix: ${prefix}"

    cd "$target_dir" || return 1

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

    # Create PROMPT.md
    if [[ ! -f "PROMPT.md" ]]; then
        cp "${CURB_DIR}/templates/PROMPT.md" PROMPT.md
        log_success "Created PROMPT.md"
    else
        log_warn "PROMPT.md already exists, skipping"
    fi

    # Create AGENT.md
    if [[ ! -f "AGENT.md" ]]; then
        cp "${CURB_DIR}/templates/AGENT.md" AGENT.md
        log_success "Created AGENT.md"
    else
        log_warn "AGENT.md already exists, skipping"
    fi

    # Create AGENTS.md symlink for Codex compatibility
    # Codex CLI looks for AGENTS.md in the project root
    if [[ ! -f "AGENTS.md" && ! -L "AGENTS.md" ]]; then
        ln -s AGENT.md AGENTS.md
        log_success "Created AGENTS.md symlink (for Codex compatibility)"
    elif [[ -L "AGENTS.md" ]]; then
        log_warn "AGENTS.md symlink already exists, skipping"
    else
        log_warn "AGENTS.md already exists as file, skipping symlink"
    fi

    # Create progress.txt
    if [[ ! -f "progress.txt" ]]; then
        cat > progress.txt <<EOF
# Progress Log
Started: $(date -u +"%Y-%m-%d")

## Codebase Patterns
<!-- Agent adds discovered patterns here for future iterations -->

## Key Files
<!-- Important files to be aware of -->

---
EOF
        log_success "Created progress.txt"
    else
        log_warn "progress.txt already exists, skipping"
    fi

    # Create fix_plan.md
    if [[ ! -f "fix_plan.md" ]]; then
        cat > fix_plan.md <<EOF
# Fix Plan

Discovered issues and planned improvements.
Agent maintains this file during development.

## High Priority

## Medium Priority

## Low Priority

## Completed
EOF
        log_success "Created fix_plan.md"
    else
        log_warn "fix_plan.md already exists, skipping"
    fi

    # Create .gitignore additions
    if [[ -f ".gitignore" ]]; then
        if ! grep -q "# Curb" .gitignore 2>/dev/null; then
            cat >> .gitignore <<EOF

# Curb
*.curb.tmp
EOF
            log_success "Updated .gitignore"
        fi
    else
        cat > .gitignore <<EOF
# Curb
*.curb.tmp
EOF
        log_success "Created .gitignore"
    fi

    echo ""
    log_success "Curb initialized!"
    echo ""
    echo "Next steps:"
    echo "  1. Edit prd.json to add your tasks (use ChatPRD template output)"
    echo "  2. Add specifications to specs/"
    echo "  3. Update AGENT.md with build instructions"
    echo "  4. Run 'curb status' to see task summary"
    echo "  5. Run 'curb' to start the autonomous loop"
    echo ""
    echo "Useful commands:"
    echo "  curb status        Show task progress"
    echo "  curb run --ready   Show ready tasks"
    echo "  curb run --once    Run single iteration"
    echo "  curb run --plan    Run planning mode"
    echo "  curb --harness codex Use OpenAI Codex instead of Claude"
    echo ""

    return 0
}
