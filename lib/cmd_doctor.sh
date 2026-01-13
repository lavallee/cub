#!/usr/bin/env bash
#
# cmd_doctor.sh - doctor subcommand implementation
#

# Include guard
if [[ -n "${_CUB_CMD_DOCTOR_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_DOCTOR_SH_LOADED=1

cmd_doctor_help() {
    cat <<'EOF'
cub doctor [options]

Diagnose and optionally fix common curb issues.

USAGE:
  cub doctor              Run diagnostics
  cub doctor --verbose    Show detailed diagnostic info
  cub doctor --fix        Automatically fix detected issues
  cub doctor --dry-run    Show what --fix would do

CHECKS:
  - Environment: jq, harness availability, beads (if used)
  - Project structure: prd.json/.beads, PROMPT.md, AGENT.md
  - Git state: uncommitted files categorized as:
    * session files (progress.txt, fix_plan.md) - safe to commit
    * source code - needs review before committing
    * cruft (.bak, .tmp, .DS_Store, etc.) - safe to clean
    * config files - needs careful review
  - Task state: tasks stuck in "in_progress"

FIX ACTIONS:
  --fix will:
  - Commit session files with "chore: commit session files"
  - Suggest adding cruft patterns to .gitignore
  - Report source/config files that need manual review

EXAMPLES:
  # Run diagnostics
  cub doctor

  # See what would be fixed
  cub doctor --dry-run

  # Auto-fix session files
  cub doctor --fix

SEE ALSO:
  cub init      Initialize project
  cub status    Check task progress
  cub --help    Show all commands
EOF
}

_doctor_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

_doctor_warn() {
    echo -e "${YELLOW}[!!]${NC} $1"
}

_doctor_info() {
    echo -e "${BLUE}[--]${NC} $1"
}

_doctor_fail() {
    echo -e "${RED}[XX]${NC} $1"
}

_doctor_check_env() {
    local issues=0
    echo ""
    echo "Environment:"

    # Check jq
    if command -v jq &>/dev/null; then
        local jq_version
        jq_version=$(jq --version 2>/dev/null | sed 's/jq-//')
        _doctor_ok "jq installed (v${jq_version})"
    else
        _doctor_fail "jq not installed (required)"
        ((issues++))
    fi

    # Check for at least one harness
    local harness_found=false
    if command -v claude &>/dev/null; then
        _doctor_ok "claude harness available"
        harness_found=true
    fi
    if command -v codex &>/dev/null; then
        _doctor_ok "codex harness available"
        harness_found=true
    fi
    if command -v gemini &>/dev/null; then
        _doctor_ok "gemini harness available"
        harness_found=true
    fi
    if command -v opencode &>/dev/null; then
        _doctor_ok "opencode harness available"
        harness_found=true
    fi

    if [[ "$harness_found" == "false" ]]; then
        _doctor_fail "No AI harness found (need claude, codex, gemini, or opencode)"
        ((issues++))
    fi

    # Check beads (optional)
    if command -v bd &>/dev/null; then
        _doctor_ok "beads (bd) installed"
    else
        _doctor_info "beads (bd) not installed (optional)"
    fi

    return $issues
}

_doctor_check_project() {
    local issues=0
    echo ""
    echo "Project Structure:"

    # Check for task backend
    if [[ -d "${PROJECT_DIR}/.beads" ]]; then
        local task_count
        task_count=$(bd list --json 2>/dev/null | jq 'length' 2>/dev/null || echo "?")
        _doctor_ok ".beads/ directory found (${task_count} tasks)"
    elif [[ -f "${PROJECT_DIR}/prd.json" ]]; then
        local task_count
        task_count=$(jq '.tasks | length' "${PROJECT_DIR}/prd.json" 2>/dev/null || echo "?")
        _doctor_ok "prd.json found (${task_count} tasks)"
    else
        _doctor_warn "No task backend found (need prd.json or .beads/)"
        ((issues++))
    fi

    # Check PROMPT.md
    if [[ -f "${PROJECT_DIR}/PROMPT.md" ]]; then
        _doctor_ok "PROMPT.md found"
    else
        _doctor_warn "PROMPT.md not found (run 'cub init')"
        ((issues++))
    fi

    # Check AGENT.md
    if [[ -f "${PROJECT_DIR}/AGENT.md" ]]; then
        _doctor_ok "AGENT.md found"
    else
        _doctor_warn "AGENT.md not found (run 'cub init')"
        ((issues++))
    fi

    # Check .cub/ directory
    if [[ -d "${PROJECT_DIR}/.curb" ]]; then
        _doctor_ok ".cub/ directory exists"
    else
        _doctor_info ".cub/ directory not found (will be created on first run)"
    fi

    return $issues
}

_doctor_check_git() {
    local verbose="${1:-false}"
    local issues=0
    echo ""
    echo "Git State:"

    # Check if in git repo
    if ! git_in_repo; then
        _doctor_info "Not a git repository"
        return 0
    fi

    _doctor_ok "Git repository detected"

    # Check for uncommitted changes
    local changes_json
    changes_json=$(git_categorize_changes)

    if [[ "$changes_json" == *'"error"'* ]]; then
        _doctor_fail "Error categorizing changes"
        return 1
    fi

    # Extract counts
    local session_count source_count cruft_count config_count unknown_count
    session_count=$(echo "$changes_json" | jq '.session | length')
    source_count=$(echo "$changes_json" | jq '.source | length')
    cruft_count=$(echo "$changes_json" | jq '.cruft | length')
    config_count=$(echo "$changes_json" | jq '.config | length')
    unknown_count=$(echo "$changes_json" | jq '.unknown | length')

    local total_count=$((session_count + source_count + cruft_count + config_count + unknown_count))

    # Check for cub artifacts (.beads/ and .cub/) separately
    local cub_artifacts
    cub_artifacts=$(git status --porcelain -u 2>/dev/null | grep -E '^.. \.(beads|curb)/' || true)
    local cub_artifact_count=0
    if [[ -n "$cub_artifacts" ]]; then
        cub_artifact_count=$(echo "$cub_artifacts" | wc -l | tr -d ' ')
    fi

    if [[ $total_count -eq 0 && $cub_artifact_count -eq 0 ]]; then
        _doctor_ok "Working directory clean"
        return 0
    fi

    # Report cub artifacts if present
    if [[ $cub_artifact_count -gt 0 ]]; then
        _doctor_warn "Curb artifacts need committing (${cub_artifact_count} files)"
        ((issues++))
        echo ""
        echo "  Curb artifacts (safe to commit with --fix):"
        # Use here-string to avoid subshell from pipe
        while IFS= read -r line; do
            echo "    $line"
        done <<< "$cub_artifacts"
        # Store for fix phase (exported so it survives function calls)
        export _DOCTOR_CUB_ARTIFACTS="$cub_artifacts"
    fi

    if [[ $total_count -eq 0 ]]; then
        # Only cub artifacts, no other changes
        return $issues
    fi

    # Report session files
    if [[ $session_count -gt 0 ]]; then
        _doctor_warn "Session files modified (${session_count} files)"
        ((issues++))
        if [[ "$verbose" == "true" ]]; then
            echo ""
            echo "  Session files (safe to commit with --fix):"
            echo "$changes_json" | jq -r '.session[] | "    " + .'
        fi
    fi

    # Report source code files
    if [[ $source_count -gt 0 ]]; then
        _doctor_warn "Source code files modified (${source_count} files)"
        ((issues++))
        if [[ "$verbose" == "true" ]]; then
            echo ""
            echo "  Source files (review before committing):"
            echo "$changes_json" | jq -r '.source[] | "    " + .'
        fi
    fi

    # Report cruft files
    if [[ $cruft_count -gt 0 ]]; then
        _doctor_warn "Cruft files present (${cruft_count} files)"
        ((issues++))
        if [[ "$verbose" == "true" ]]; then
            echo ""
            echo "  Cruft files (safe to remove):"
            echo "$changes_json" | jq -r '.cruft[] | "    " + .'
        fi
    fi

    # Report config files
    if [[ $config_count -gt 0 ]]; then
        _doctor_warn "Config files modified (${config_count} files)"
        ((issues++))
        if [[ "$verbose" == "true" ]]; then
            echo ""
            echo "  Config files (review carefully):"
            echo "$changes_json" | jq -r '.config[] | "    " + .'
        fi
    fi

    # Report unknown files
    if [[ $unknown_count -gt 0 ]]; then
        _doctor_warn "Unknown file changes (${unknown_count} files)"
        ((issues++))
        if [[ "$verbose" == "true" ]]; then
            echo ""
            echo "  Unknown files (review carefully):"
            echo "$changes_json" | jq -r '.unknown[] | "    " + .'
        fi
    fi

    return $issues
}

_doctor_check_tasks() {
    local issues=0
    echo ""
    echo "Task State:"

    local prd="${PROJECT_DIR}/prd.json"
    local backend
    backend=$(get_backend "${PROJECT_DIR}")

    # Check for tasks stuck in progress
    local in_progress
    in_progress=$(get_in_progress_tasks "$prd")

    if [[ -z "$in_progress" || "$in_progress" == "[]" ]]; then
        _doctor_ok "No tasks stuck in progress"
    else
        local count
        count=$(echo "$in_progress" | jq 'length')
        _doctor_warn "Found ${count} tasks in progress"
        ((issues++))
        echo ""
        echo "  In-progress tasks:"
        echo "$in_progress" | jq -r '.[] | "    " + .id + " (" + (.title // "no title") + ")"'
        echo ""
        echo "  You may want to reset these tasks to open"
    fi

    return $issues
}

_doctor_fix() {
    local dry_run="${1:-false}"
    local issues=0

    echo ""
    echo "Fix Mode:"

    if ! git_in_repo; then
        _doctor_info "Not a git repository, skipping auto-fix"
        return 0
    fi

    # Commit session files if present
    local changes_json
    changes_json=$(git_categorize_changes)
    local session_count
    session_count=$(echo "$changes_json" | jq '.session | length')

    if [[ $session_count -gt 0 ]]; then
        if [[ "$dry_run" == "true" ]]; then
            _doctor_info "Would commit ${session_count} session files"
        else
            log_info "Committing session files..."
            if git_commit_session_files "doctor"; then
                _doctor_ok "Committed session files"
            else
                _doctor_warn "Failed to commit session files"
                ((issues++))
            fi
        fi
    else
        _doctor_ok "No session files to commit"
    fi

    # Commit cub artifacts if present
    if [[ -n "${_DOCTOR_CUB_ARTIFACTS:-}" ]]; then
        if [[ "$dry_run" == "true" ]]; then
            _doctor_info "Would commit cub artifacts"
        else
            log_info "Committing cub artifacts..."
            if git_commit_cub_artifacts "doctor"; then
                _doctor_ok "Committed cub artifacts"
            else
                _doctor_warn "Failed to commit cub artifacts"
                ((issues++))
            fi
        fi
    fi

    # Report source/config files that need manual review
    local source_count config_count unknown_count
    source_count=$(echo "$changes_json" | jq '.source | length')
    config_count=$(echo "$changes_json" | jq '.config | length')
    unknown_count=$(echo "$changes_json" | jq '.unknown | length')

    if [[ $source_count -gt 0 || $config_count -gt 0 || $unknown_count -gt 0 ]]; then
        _doctor_warn "Manual review needed for ${source_count} source, ${config_count} config, ${unknown_count} unknown files"
        ((issues++))
    fi

    return $issues
}

cmd_doctor() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_doctor_help
        return 0
    fi

    local verbose="false"
    local fix="false"
    local dry_run="false"

    # Parse flags
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --verbose)
                verbose="true"
                shift
                ;;
            --fix)
                fix="true"
                shift
                ;;
            --dry-run)
                dry_run="true"
                shift
                ;;
            *)
                _log_error_console "Unknown flag: $1"
                _log_error_console "Usage: cub doctor [--verbose] [--fix] [--dry-run]"
                return 1
                ;;
        esac
    done

    # Run checks
    local total_issues=0
    _doctor_check_env || total_issues=$((total_issues + $?))
    _doctor_check_project || total_issues=$((total_issues + $?))
    _doctor_check_git "$verbose" || total_issues=$((total_issues + $?))
    _doctor_check_tasks || total_issues=$((total_issues + $?))

    # Run fixes if requested
    if [[ "$fix" == "true" || "$dry_run" == "true" ]]; then
        _doctor_fix "$dry_run" || total_issues=$((total_issues + $?))
    fi

    # Summary
    echo ""
    if [[ $total_issues -eq 0 ]]; then
        _doctor_ok "No issues found"
    else
        _doctor_warn "Found ${total_issues} issue(s)"
        if [[ "$fix" != "true" ]]; then
            echo ""
            echo "Run 'cub doctor --fix' to auto-fix some issues"
            echo "Run 'cub doctor --dry-run' to preview fixes"
        fi
    fi

    return 0
}
