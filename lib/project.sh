#!/usr/bin/env bash
#
# project.sh - project validation and dependency checks
#

# Include guard
if [[ -n "${_CUB_PROJECT_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_PROJECT_SH_LOADED=1

check_deps() {
    local missing=()
    command -v jq >/dev/null 2>&1 || missing+=("jq")

    # Check for at least one harness
    if ! harness_available; then
        missing+=("harness (claude or codex)")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        _log_error_console "Missing dependencies: ${missing[*]}"
        exit 1
    fi

    # Log which harness is active
    local current_harness
    current_harness=$(harness_get)
    log_debug "Harness: ${current_harness}"

    # Log harness capabilities in debug mode
    if [[ "$DEBUG" == "true" ]]; then
        log_debug "Harness capabilities:"
        if harness_supports "streaming"; then
            log_debug "  - streaming: yes"
        else
            log_debug "  - streaming: no (will use non-streaming mode)"
        fi
        if harness_supports "token_reporting"; then
            log_debug "  - token_reporting: yes"
        else
            log_debug "  - token_reporting: no (will estimate from cost)"
        fi
        if harness_supports "system_prompt"; then
            log_debug "  - system_prompt: yes"
        else
            log_debug "  - system_prompt: no (will combine prompts)"
        fi
        if harness_supports "auto_mode"; then
            log_debug "  - auto_mode: yes"
        else
            log_debug "  - auto_mode: no (may require manual approval)"
        fi
    fi
}

validate_project() {
    log_debug "Validating project structure in ${PROJECT_DIR}"

    # Detect and initialize task backend
    # Note: tasks.sh is already sourced at top of script, defining _TASK_BACKEND global
    # detect_backend echoes the result AND sets _TASK_BACKEND, but command substitution
    # runs in subshell, so we explicitly set the global after getting the value
    local detected_backend
    detected_backend=$(detect_backend "${PROJECT_DIR}")
    _TASK_BACKEND="$detected_backend"  # Explicitly set global to persist across function calls
    log_debug "Task backend: ${detected_backend}"

    if [[ "$detected_backend" == "beads" ]]; then
        log_info "Using beads backend"
        # Beads doesn't need prd.json
    else
        log_info "Using JSON backend (prd.json)"
        if [[ ! -f "${PROJECT_DIR}/prd.json" ]]; then
            _log_error_console "No prd.json found in ${PROJECT_DIR}"
            log_info "Run 'cub-init' to scaffold a new project"
            exit 1
        fi
        log_debug "Found prd.json ($(wc -c < "${PROJECT_DIR}/prd.json") bytes)"
    fi

    # Detect layout and ensure layout root directory exists
    local layout
    layout=$(detect_layout "${PROJECT_DIR}")
    log_debug "Project layout: ${layout}"

    local layout_root
    layout_root=$(get_layout_root "${PROJECT_DIR}")
    mkdir -p "$layout_root"

    local prompt_file
    prompt_file=$(get_prompt_file "${PROJECT_DIR}")
    if [[ ! -f "$prompt_file" ]]; then
        log_warn "No prompt.md found at ${prompt_file}, using default template"
        cp "${CUB_DIR}/templates/PROMPT.md" "$prompt_file"
    fi
    log_debug "Found prompt.md ($(wc -l < "$prompt_file") lines)"

    local agent_file
    agent_file=$(get_agent_file "${PROJECT_DIR}")
    if [[ ! -f "$agent_file" ]]; then
        log_warn "No agent.md found at ${agent_file}, using default template"
        cp "${CUB_DIR}/templates/AGENT.md" "$agent_file"
    fi
    log_debug "Found agent.md ($(wc -l < "$agent_file") lines)"
    log_debug "Project validation complete"
}
