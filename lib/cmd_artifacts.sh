#!/usr/bin/env bash
#
# cmd_artifacts.sh - artifacts subcommand implementation
#

# Include guard
if [[ -n "${_CUB_CMD_ARTIFACTS_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_ARTIFACTS_SH_LOADED=1

cmd_artifacts_help() {
    cat <<'EOF'
cub artifacts [<task-id>]

Access and navigate to task artifact directories and output files.

USAGE:
  cub artifacts              List recent tasks with artifact paths
  cub artifacts <task-id>    Show path to specific task artifacts
  cub artifacts <prefix>     Find tasks by ID prefix (partial match)

TASK ARTIFACTS INCLUDE:
  - task.json              Task metadata and status
  - summary.md             Execution summary
  - changes.patch          Git diff of changes made
  - logs/                  Detailed execution logs
  - run.json               Run-level information

EXAMPLES:
  # List all recent tasks
  cub artifacts

  # Get path to specific task (useful for scripts)
  cub artifacts curb-018
  # Output: .cub/runs/panda-20260110-141339/tasks/curb-018

  # Use in shell command
  cd $(cub artifacts curb-018)
  cat summary.md

  # Find by prefix (shows matches if ambiguous)
  cub artifacts curb-01

  # View recent task summary
  cat $(cub artifacts curb-017)/summary.md

  # Examine git changes made by task
  patch -p1 -R < $(cub artifacts curb-016)/changes.patch

  # Find task logs
  ls $(cub artifacts curb-015)/logs/

SEE ALSO:
  cub status      Check task progress
  cub --help      Show all commands
EOF
}

cmd_artifacts() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_artifacts_help
        return 0
    fi

    local artifacts_base=".cub/runs"

    # If no arguments given, list recent tasks with paths
    if [[ $# -eq 0 ]]; then
        if [[ ! -d "$artifacts_base" ]]; then
            log_info "No artifacts found"
            return 0
        fi

        log_info "Recent tasks:"
        # Find all task directories, sort by modification time (newest first)
        find "$artifacts_base" -maxdepth 3 -type d -name "curb-*" | sort -r | while read -r task_dir; do
            if [[ -f "$task_dir/task.json" ]]; then
                local task_id
                task_id=$(basename "$task_dir")
                echo "  ${task_id}: ${task_dir}"
            fi
        done
        return 0
    fi

    # Find a task by task_id (supports prefix matching)
    local search_id="$1"
    local artifacts_base=".cub/runs"

    if [[ ! -d "$artifacts_base" ]]; then
        _log_error_console "No artifacts found (no runs yet)"
        return 1
    fi

    # Search for matching task_id across all runs
    # Support both exact and prefix matches
    local matches=()
    while IFS= read -r task_dir; do
        if [[ -f "$task_dir/task.json" ]]; then
            local task_id
            task_id=$(basename "$task_dir")
            # Check for exact match first, or prefix match
            if [[ "$task_id" == "$search_id" ]] || [[ "$task_id" == "$search_id"* ]]; then
                matches+=("$task_dir")
            fi
        fi
    done < <(find "$artifacts_base" -maxdepth 3 -type d -name "curb-*" 2>/dev/null)

    if [[ ${#matches[@]} -eq 0 ]]; then
        _log_error_console "Task not found: ${search_id}"
        _log_error_console "Tip: Run 'cub artifacts' to see available tasks"
        return 1
    fi

    if [[ ${#matches[@]} -eq 1 ]]; then
        # Single match - print the path
        echo "${matches[0]}"
        return 0
    fi

    # Multiple matches - show them and ask user to be more specific
    _log_error_console "Ambiguous task ID '${search_id}' matches ${#matches[@]} tasks:"
    for match in "${matches[@]}"; do
        _log_error_console "  $(basename "$match"): ${match}"
    done
    _log_error_console "Please use a more specific prefix"
    return 1
}
