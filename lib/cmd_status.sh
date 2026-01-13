#!/usr/bin/env bash
#
# cmd_status.sh - status and ready subcommands
#

# Include guard
if [[ -n "${_CURB_CMD_STATUS_SH_LOADED:-}" ]]; then
    return 0
fi
_CURB_CMD_STATUS_SH_LOADED=1

cmd_status_help() {
    cat <<'EOF'
curb status [--json]

Display current task progress and status summary.

USAGE:
  curb status           Show formatted status summary
  curb status --json    Output status as machine-readable JSON

OUTPUT:
  When run without --json:
    - Task counts (total, closed, in progress, open)
    - Progress bar showing percentage complete
    - Current session information (if running)
    - Most recent run details

  When run with --json:
    - Machine-readable JSON with task counts
    - Current session object (if initialized)
    - Most recent run information

EXAMPLES:
  # Show human-readable status
  curb status

  # Check progress before running
  curb status

  # Get JSON for scripting
  curb status --json | jq '.task_counts'

  # Monitor while loop runs in background
  watch -n 5 'curb status'

SEE ALSO:
  curb run --ready    List tasks ready to work on
  curb --help         Show all commands
  curb artifacts      Access task output files
EOF
}

cmd_status() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_status_help
        return 0
    fi

    local json_output=false

    # Parse flags
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                json_output=true
                shift
                ;;
            *)
                _log_error_console "Unknown flag: $1"
                _log_error_console "Usage: curb status [--json]"
                return 1
                ;;
        esac
    done

    # In JSON mode, suppress logging during validation
    if [[ "$json_output" == "true" ]]; then
        validate_project >/dev/null 2>&1
        show_status_json
    else
        validate_project
        show_status
    fi
}

show_status() {
    local prd="${PROJECT_DIR}/prd.json"
    local backend
    backend=$(get_backend "${PROJECT_DIR}")

    # Validate JSON before processing (only for json backend)
    if [[ "$backend" == "json" ]]; then
        if ! jq empty "$prd" 2>/dev/null; then
            _log_error_console "Invalid JSON in prd.json"
            return 1
        fi
    fi

    echo ""
    log_info "Task Status Summary"
    echo "===================="

    local counts
    counts=$(get_task_counts "$prd")
    local total
    total=$(echo "$counts" | jq -r '.total')
    local closed
    closed=$(echo "$counts" | jq -r '.closed')
    local in_progress
    in_progress=$(echo "$counts" | jq -r '.in_progress')
    local open
    open=$(echo "$counts" | jq -r '.open')

    echo -e "Total:       ${total}"
    echo -e "Closed:      ${GREEN}${closed}${NC}"
    echo -e "In Progress: ${YELLOW}${in_progress}${NC}"
    echo -e "Open:        ${open}"
    echo ""

    # Progress bar
    if [[ "$total" -gt 0 ]]; then
        local pct=$((closed * 100 / total))
        local filled=$((pct / 5))
        local empty=$((20 - filled))
        printf "Progress: ["
        printf "%0.s#" $(seq 1 $filled 2>/dev/null) || true
        printf "%0.s-" $(seq 1 $empty 2>/dev/null) || true
        printf "] %d%%\n" "$pct"
    fi

    # Show current session if running
    if session_is_initialized; then
        local session_name
        session_name=$(session_get_name 2>/dev/null || echo "unknown")
        local session_id
        session_id=$(session_get_id 2>/dev/null || echo "unknown")
        echo ""
        log_info "Current Session"
        echo "===================="
        echo "Name: ${session_name}"
        echo "ID:   ${session_id}"
    fi

    # Show most recent run
    local artifacts_base="${PROJECT_DIR}/.curb/runs"
    if [[ -d "$artifacts_base" ]]; then
        local most_recent_run
        most_recent_run=$(ls -t "$artifacts_base" 2>/dev/null | head -n 1)
        if [[ -n "$most_recent_run" ]]; then
            echo ""
            log_info "Most Recent Run"
            echo "===================="
            echo "Run ID: ${most_recent_run}"
            if [[ -f "$artifacts_base/$most_recent_run/run.json" ]]; then
                local started_at
                started_at=$(jq -r '.started_at // "unknown"' "$artifacts_base/$most_recent_run/run.json" 2>/dev/null || echo "unknown")
                local status
                status=$(jq -r '.status // "unknown"' "$artifacts_base/$most_recent_run/run.json" 2>/dev/null || echo "unknown")
                echo "Started: ${started_at}"
                echo "Status:  ${status}"
                echo "Path:    ${artifacts_base}/${most_recent_run}"
            fi
        fi
    fi
}

show_status_json() {
    local prd="${PROJECT_DIR}/prd.json"
    local backend
    backend=$(get_backend "${PROJECT_DIR}")

    # Validate JSON before processing (only for json backend)
    if [[ "$backend" == "json" ]]; then
        if ! jq empty "$prd" 2>/dev/null; then
            _log_error_console "Invalid JSON in prd.json"
            return 1
        fi
    fi

    local counts
    counts=$(get_task_counts "$prd")

    # Build JSON output
    local session_name="null"
    local session_id="null"
    if session_is_initialized; then
        session_name="\"$(session_get_name 2>/dev/null || echo "unknown")\""
        session_id="\"$(session_get_id 2>/dev/null || echo "unknown")\""
    fi

    local most_recent_run="null"
    local artifacts_base="${PROJECT_DIR}/.curb/runs"
    if [[ -d "$artifacts_base" ]]; then
        local run_dir
        run_dir=$(ls -t "$artifacts_base" 2>/dev/null | head -n 1)
        if [[ -n "$run_dir" ]]; then
            local started_at="unknown"
            local status="unknown"
            local run_path="${artifacts_base}/${run_dir}"
            if [[ -f "$run_path/run.json" ]]; then
                started_at=$(jq -r '.started_at // "unknown"' "$run_path/run.json" 2>/dev/null || echo "unknown")
                status=$(jq -r '.status // "unknown"' "$run_path/run.json" 2>/dev/null || echo "unknown")
            fi
            most_recent_run=$(jq -n \
                --arg id "$run_dir" \
                --arg started "$started_at" \
                --arg status "$status" \
                --arg path "$run_path" \
                '{id: $id, started_at: $started, status: $status, path: $path}')
        fi
    fi

    # Output JSON
    jq -n \
        --argjson counts "$counts" \
        --argjson session_name "$session_name" \
        --argjson session_id "$session_id" \
        --argjson most_recent_run "$most_recent_run" \
        '{
            task_counts: $counts,
            current_session: (if $session_name != null then {name: $session_name, id: $session_id} else null end),
            most_recent_run: $most_recent_run
        }'
}

show_ready() {
    local prd="${PROJECT_DIR}/prd.json"
    local backend
    backend=$(get_backend "${PROJECT_DIR}")

    # Validate JSON before processing (only for json backend)
    if [[ "$backend" == "json" ]]; then
        if ! jq empty "$prd" 2>/dev/null; then
            _log_error_console "Invalid JSON in prd.json"
            return 1
        fi
    fi

    log_info "Ready Tasks (unblocked, status=open)"
    if [[ -n "$EPIC" ]]; then
        log_info "  Epic filter: $EPIC"
    fi
    if [[ -n "$LABEL" ]]; then
        log_info "  Label filter: $LABEL"
    fi
    echo "======================================"

    local ready
    ready=$(get_ready_tasks "$prd" "$EPIC" "$LABEL")

    if [[ -z "$ready" || "$ready" == "null" || "$ready" == "[]" ]]; then
        log_warn "No ready tasks found"
        return
    fi

    echo "$ready" | jq -r '.[] | "[\(.priority)] \(.id): \(.title)"'
}
