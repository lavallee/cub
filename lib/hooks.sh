#!/usr/bin/env bash
#
# hooks.sh - Hook Framework for Curb
#
# Provides functions for running hook scripts at various points in the curb lifecycle.
# Hooks are executable scripts stored in directories like pre-task.d/, post-task.d/, etc.
# Scripts are run in sorted order (01-first.sh before 02-second.sh).
#
# Hook directories are checked in two locations:
#   1. ~/.config/cub/hooks/{hook_name}.d/  (global hooks)
#   2. ./.cub/hooks/{hook_name}.d/         (project-specific hooks)
#
# Available hook points:
#   - pre-loop: Before starting the main loop
#   - pre-task: Before each task execution
#   - post-task: After each task execution (success or failure)
#   - on-error: When a task fails
#   - post-loop: After the main loop completes
#
# Environment Variables Exported to Hooks:
#   CUB_HOOK_NAME     - Name of the hook being run
#   CUB_PROJECT_DIR   - Project directory
#   CUB_TASK_ID       - Current task ID (if applicable)
#   CUB_TASK_TITLE    - Current task title (if applicable)
#   CUB_EXIT_CODE     - Task exit code (for post-task/on-error hooks)
#   CUB_HARNESS       - Harness being used (claude, codex, etc.)
#   CUB_SESSION_ID    - Current session ID
#

# Source dependencies
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "$(type -t cub_config_dir 2>/dev/null)" ]]; then
    source "${SCRIPT_DIR}/xdg.sh"
fi
if [[ -z "$(type -t config_get_or 2>/dev/null)" ]]; then
    source "${SCRIPT_DIR}/config.sh"
fi

# Find all hook scripts for a given hook name
# Scans both global and project hook directories for executable scripts.
# Returns paths sorted by filename (global hooks first, then project).
#
# Args:
#   $1 - hook_name: Name of the hook (e.g., "pre-task", "post-task")
#
# Returns:
#   0 on success
#   1 if hook_name is empty
#
# Output:
#   Prints one script path per line (newline-separated)
#
# Example:
#   hooks_find "pre-task"
#   # Output:
#   # ~/.config/cub/hooks/pre-task.d/01-global.sh
#   # ./.cub/hooks/pre-task.d/02-project.sh
hooks_find() {
    local hook_name="$1"

    # Validate hook name
    if [[ -z "$hook_name" ]]; then
        echo "ERROR: hook_name is required" >&2
        return 1
    fi

    # Build list of hook directories to check
    local global_hook_dir="$(cub_config_dir)/hooks/${hook_name}.d"
    local project_hook_dir="./.cub/hooks/${hook_name}.d"

    local all_scripts=()

    # Collect scripts from global directory
    if [[ -d "$global_hook_dir" ]]; then
        while IFS= read -r -d '' script; do
            all_scripts+=("$script")
        done < <(find "$global_hook_dir" -type f -perm +111 -print0 2>/dev/null | sort -z)
    fi

    # Collect scripts from project directory
    if [[ -d "$project_hook_dir" ]]; then
        while IFS= read -r -d '' script; do
            all_scripts+=("$script")
        done < <(find "$project_hook_dir" -type f -perm +111 -print0 2>/dev/null | sort -z)
    fi

    # Output each script on a separate line (handle empty array safely)
    if [[ ${#all_scripts[@]} -gt 0 ]]; then
        for script in "${all_scripts[@]}"; do
            echo "$script"
        done
    fi

    return 0
}

# Run all scripts in a hook directory
# Executes scripts in sorted order from both global and project hook directories.
# Scripts receive context via exported environment variables.
# Hook failures are logged but don't stop execution by default (configurable).
#
# Args:
#   $1 - hook_name: Name of the hook (e.g., "pre-task", "post-task")
#   Additional args are passed through to hook scripts
#
# Returns:
#   0 on success (all hooks passed or hooks.fail_fast is false)
#   1 if any hook failed and hooks.fail_fast is true
#
# Example:
#   hooks_run "pre-task"
#   hooks_run "post-task" "$task_id" "$exit_code"
hooks_run() {
    local hook_name="$1"
    shift  # Remove hook_name from args, rest are passed to scripts

    # Validate hook name
    if [[ -z "$hook_name" ]]; then
        echo "ERROR: hook_name is required" >&2
        return 1
    fi

    # Check if hooks are enabled in config
    local hooks_enabled
    hooks_enabled=$(config_get_or "hooks.enabled" "true")
    if [[ "$hooks_enabled" != "true" ]]; then
        return 0
    fi

    # Export hook context variables
    export CUB_HOOK_NAME="$hook_name"
    export CUB_PROJECT_DIR="${CUB_PROJECT_DIR:-$(pwd)}"

    # Find all hook scripts for this hook
    local all_scripts=()
    while IFS= read -r script; do
        all_scripts+=("$script")
    done < <(hooks_find "$hook_name")

    # If no scripts found, return success
    if [[ ${#all_scripts[@]} -eq 0 ]]; then
        return 0
    fi

    # Get fail_fast config (default: false, meaning hooks don't stop loop)
    local fail_fast
    fail_fast=$(config_get_or "hooks.fail_fast" "false")

    # Run each script in sorted order
    local failed_count=0
    for script in "${all_scripts[@]}"; do
        # Skip non-executable files (shouldn't happen due to find filter, but be safe)
        if [[ ! -x "$script" ]]; then
            continue
        fi

        # Run the script and capture output and exit code
        local script_output
        local script_exit_code

        script_output=$("$script" "$@" 2>&1)
        script_exit_code=$?

        # Log execution result
        if [[ $script_exit_code -eq 0 ]]; then
            # Success - log if there was output
            if [[ -n "$script_output" ]]; then
                echo "[hook:$hook_name] $script: $script_output"
            fi
        else
            # Failure - always log
            failed_count=$((failed_count + 1))
            echo "[hook:$hook_name] $script failed with exit code $script_exit_code" >&2
            if [[ -n "$script_output" ]]; then
                echo "$script_output" >&2
            fi

            # If fail_fast is enabled, return immediately
            if [[ "$fail_fast" == "true" ]]; then
                return 1
            fi
        fi
    done

    # Return success if all hooks passed, or if fail_fast is disabled
    if [[ $failed_count -gt 0 && "$fail_fast" == "true" ]]; then
        return 1
    fi

    return 0
}

# Export context for task-related hooks
# Call this before running pre-task, post-task, or on-error hooks
#
# Args:
#   $1 - task_id: Current task ID
#   $2 - task_title: Current task title (optional)
#   $3 - exit_code: Task exit code (optional, for post-task/on-error)
#
# Example:
#   hooks_set_task_context "$task_id" "$task_title"
#   hooks_run "pre-task"
hooks_set_task_context() {
    export CUB_TASK_ID="$1"
    export CUB_TASK_TITLE="${2:-}"
    export CUB_EXIT_CODE="${3:-}"
}

# Export context for session-related hooks
# Call this before running pre-loop or post-loop hooks
#
# Args:
#   $1 - session_id: Current session ID
#   $2 - harness: Harness being used (optional)
#
# Example:
#   hooks_set_session_context "$session_id" "$harness"
#   hooks_run "pre-loop"
hooks_set_session_context() {
    export CUB_SESSION_ID="$1"
    export CUB_HARNESS="${2:-}"
}

# Clear hook context variables
# Useful for testing
hooks_clear_context() {
    unset CUB_HOOK_NAME
    unset CUB_PROJECT_DIR
    unset CUB_TASK_ID
    unset CUB_TASK_TITLE
    unset CUB_EXIT_CODE
    unset CUB_SESSION_ID
    unset CUB_HARNESS
}
