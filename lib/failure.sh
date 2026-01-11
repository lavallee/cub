#!/usr/bin/env bash
#
# failure.sh - Failure Handling Configuration
#
# Provides configurable modes for handling task failures.
# Supports different strategies: stop, move-on, retry, or triage.
#
# Environment Variables:
#   failure_mode - Current failure handling mode
#
# Available Modes:
#   stop       - Stop execution when a task fails
#   move-on    - Continue to next task (default)
#   retry      - Automatically retry failed task
#   triage      - Send to triage queue for manual review
#

# Mode constants for failure handling
readonly FAILURE_STOP="stop"
readonly FAILURE_MOVE_ON="move-on"
readonly FAILURE_RETRY="retry"
readonly FAILURE_TRIAGE="triage"

# Source dependencies
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# Default failure mode - can be overridden by config
failure_mode="move-on"

# Get the current failure handling mode
# Returns: current mode string (stop, move-on, retry, or triage)
# Exit code: 0 on success, 1 if mode not configured
#
# Example:
#   mode=$(failure_get_mode)
#   if [[ "$mode" == "stop" ]]; then
#     exit 1
#   fi
failure_get_mode() {
    # Try to get from config first
    local mode
    mode=$(config_get "failure.mode" 2>/dev/null)

    # If not in config, return the default
    if [[ -z "$mode" ]]; then
        echo "$failure_mode"
        return 0
    fi

    echo "$mode"
    return 0
}

# Set the failure handling mode at runtime
# Args:
#   $1 - mode to set (stop, move-on, retry, triage)
#
# Returns: 0 on success, 1 if mode is invalid
#
# Example:
#   failure_set_mode "retry" || exit 1
failure_set_mode() {
    local mode="$1"

    # Validate mode argument
    if [[ -z "$mode" ]]; then
        echo "ERROR: mode is required" >&2
        return 1
    fi

    # Validate mode is one of the allowed values
    case "$mode" in
        stop|move-on|retry|triage)
            failure_mode="$mode"
            return 0
            ;;
        *)
            echo "ERROR: invalid failure mode: $mode" >&2
            echo "Valid modes: stop, move-on, retry, triage" >&2
            return 1
            ;;
    esac
}

# Handle stop failure mode - halts run immediately
# Args:
#   $1 - task_id: The ID of the failed task
#   $2 - exit_code: The exit code from task execution
#   $3 - output: Output/error message from the failed task (optional)
#
# Returns: 2 (signals main loop to halt run)
#
# Example:
#   failure_handle_stop "curb-038" 1 "Tests failed" || exit $?
failure_handle_stop() {
    local task_id="$1"
    local exit_code="$2"
    local output="$3"

    # Validate required parameters
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    if [[ -z "$exit_code" ]]; then
        echo "ERROR: exit_code is required" >&2
        return 1
    fi

    # Log failure with stop mode
    source "${SCRIPT_DIR}/logger.sh"
    log_error "Task failed in stop mode - halting run" \
        "{\"task_id\": \"$task_id\", \"exit_code\": $exit_code, \"mode\": \"stop\"}"

    # Store failure info for explain command
    failure_store_info "$task_id" "$exit_code" "$output" "stop"

    # Return 2 to signal 'halt run' to main loop
    return 2
}

# Handle move-on failure mode - marks task as failed and continues
# Args:
#   $1 - task_id: The ID of the failed task
#   $2 - exit_code: The exit code from task execution
#   $3 - output: Output/error message from the failed task (optional)
#
# Returns: 0 (signals main loop to continue)
#
# Example:
#   failure_handle_move_on "curb-038" 1 "Tests failed"
failure_handle_move_on() {
    local task_id="$1"
    local exit_code="$2"
    local output="$3"

    # Validate required parameters
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    if [[ -z "$exit_code" ]]; then
        echo "ERROR: exit_code is required" >&2
        return 1
    fi

    # Log failure with move-on mode
    source "${SCRIPT_DIR}/logger.sh"
    log_error "Task failed in move-on mode - continuing to next task" \
        "{\"task_id\": \"$task_id\", \"exit_code\": $exit_code, \"mode\": \"move-on\"}"

    # Store failure info for explain command
    failure_store_info "$task_id" "$exit_code" "$output" "move-on"

    # Return 0 to signal 'continue' to main loop
    return 0
}

# Handle retry failure mode - retries with context if under limit
# Args:
#   $1 - task_id: The ID of the failed task
#   $2 - exit_code: The exit code from task execution
#   $3 - output: Output/error message from the failed task (optional)
#
# Returns: 3 (signals main loop to retry task)
#          0 (falls back to move-on if limit exceeded)
#
# Example:
#   failure_handle_retry "curb-038" 1 "Tests failed" || handle_result=$?
failure_handle_retry() {
    local task_id="$1"
    local exit_code="$2"
    local output="$3"

    # Validate required parameters
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    if [[ -z "$exit_code" ]]; then
        echo "ERROR: exit_code is required" >&2
        return 1
    fi

    # Source budget module to check iteration limits
    source "${SCRIPT_DIR}/budget.sh"

    # Get current and max iterations
    local current_iterations
    current_iterations=$(budget_get_task_iterations "$task_id")
    local max_iterations
    max_iterations=$(budget_get_max_task_iterations)

    # Check if we're under the limit
    if [[ "$current_iterations" -lt "$max_iterations" ]]; then
        # Increment iteration counter
        budget_increment_task_iterations "$task_id"

        # Log retry attempt
        source "${SCRIPT_DIR}/logger.sh"
        log_info "Task failed - retrying with context" \
            "{\"task_id\": \"$task_id\", \"exit_code\": $exit_code, \"mode\": \"retry\", \"iteration\": $((current_iterations + 1)), \"max_iterations\": $max_iterations}"

        # Store failure info for context retrieval
        failure_store_info "$task_id" "$exit_code" "$output" "retry"

        # Return 3 to signal 'retry' to main loop
        return 3
    else
        # Limit exceeded - fall back to move-on behavior
        source "${SCRIPT_DIR}/logger.sh"
        log_error "Task retry limit exceeded - falling back to move-on" \
            "{\"task_id\": \"$task_id\", \"exit_code\": $exit_code, \"mode\": \"retry\", \"iteration\": $current_iterations, \"max_iterations\": $max_iterations}"

        # Store failure info with retry mode
        failure_store_info "$task_id" "$exit_code" "$output" "retry-limit-exceeded"

        # Fall back to move-on behavior (return 0 = continue)
        return 0
    fi
}

# Get failure context for prompt augmentation
# Args:
#   $1 - task_id: The ID of the failed task
#
# Returns: 0 on success, 1 on error
# Outputs: Formatted failure context to stdout
#
# Example:
#   context=$(failure_get_context "curb-038")
#   # Returns: "Previous attempt failed with exit code 1: Tests failed. Please try a different approach."
failure_get_context() {
    local task_id="$1"

    # Validate required parameter
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    # Source artifacts module to find task directory
    source "${SCRIPT_DIR}/artifacts.sh"

    # Find the task artifacts directory
    local artifacts_base
    artifacts_base=$(artifacts_get_base_dir)

    if [[ ! -d "$artifacts_base" ]]; then
        # No artifacts directory - no context available
        return 0
    fi

    # Find task directory (search in current run)
    local task_dir
    task_dir=$(find "$artifacts_base" -maxdepth 2 -type d -name "$task_id" 2>/dev/null | head -n 1)

    if [[ -z "$task_dir" || ! -d "$task_dir" ]]; then
        # Task directory doesn't exist - no context available
        return 0
    fi

    # Check if failure.json exists
    local failure_file="${task_dir}/failure.json"
    if [[ ! -f "$failure_file" ]]; then
        # No failure info - no context available
        return 0
    fi

    # Parse failure info
    local exit_code output
    exit_code=$(jq -r '.exit_code' "$failure_file" 2>/dev/null)
    output=$(jq -r '.output' "$failure_file" 2>/dev/null)

    # Format context message
    if [[ -n "$output" && "$output" != "null" && "$output" != "" ]]; then
        echo "Previous attempt failed with exit code $exit_code: $output. Please try a different approach."
    else
        echo "Previous attempt failed with exit code $exit_code. Please try a different approach."
    fi

    return 0
}

# Store failure information for later retrieval
# Args:
#   $1 - task_id: The ID of the failed task
#   $2 - exit_code: The exit code from task execution
#   $3 - output: Output/error message from the failed task (optional)
#   $4 - mode: The failure mode that was used (optional)
#
# Returns: 0 on success, 1 on error
#
# Stores failure info in task artifacts directory for retrieval by explain command
failure_store_info() {
    local task_id="$1"
    local exit_code="$2"
    local output="$3"
    local mode="${4:-unknown}"

    # Validate required parameters
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    if [[ -z "$exit_code" ]]; then
        echo "ERROR: exit_code is required" >&2
        return 1
    fi

    # Source artifacts module to find task directory
    source "${SCRIPT_DIR}/artifacts.sh"

    # Find the task artifacts directory
    local artifacts_base
    artifacts_base=$(artifacts_get_base_dir)

    if [[ ! -d "$artifacts_base" ]]; then
        # No artifacts directory yet - skip storing failure info
        return 0
    fi

    # Find task directory (search in current run)
    local task_dir
    task_dir=$(find "$artifacts_base" -maxdepth 2 -type d -name "$task_id" 2>/dev/null | head -n 1)

    if [[ -z "$task_dir" || ! -d "$task_dir" ]]; then
        # Task directory doesn't exist - skip storing failure info
        return 0
    fi

    # Create failure.json in task artifacts directory
    local failure_file="${task_dir}/failure.json"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Build failure JSON
    local failure_json
    failure_json=$(jq -n \
        --arg task_id "$task_id" \
        --argjson exit_code "$exit_code" \
        --arg output "$output" \
        --arg mode "$mode" \
        --arg timestamp "$timestamp" \
        '{task_id: $task_id, exit_code: $exit_code, output: $output, mode: $mode, timestamp: $timestamp}')

    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to create failure JSON" >&2
        return 1
    fi

    # Write failure info to file
    echo "$failure_json" > "$failure_file"
    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to write failure.json" >&2
        return 1
    fi

    return 0
}
