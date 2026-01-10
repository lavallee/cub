#!/usr/bin/env bash
#
# logger.sh - Structured logging with JSONL output
#
# Provides functions for writing structured logs in JSON Lines format.
# Logs are written to ~/.local/share/curb/logs/{project}/{session}.jsonl
# Each log line is valid JSON with timestamp, event type, and data.
#
# Environment Variables:
#   _LOG_FILE    - Path to current log file (set by logger_init)
#

# Source dependencies
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/xdg.sh"

# Global variable to store log file path
_LOG_FILE=""

# Initialize logger with project name and session ID
# Creates log directory and sets up log file path
#
# Args:
#   $1 - project_name: Name of the project (used for directory)
#   $2 - session_id: Unique session identifier (used for filename)
#
# Returns:
#   0 on success, 1 on failure
#
# Example:
#   logger_init "myproject" "20260109-123456"
logger_init() {
    local project_name="$1"
    local session_id="$2"

    # Validate arguments
    if [[ -z "$project_name" ]]; then
        echo "ERROR: project_name is required" >&2
        return 1
    fi

    if [[ -z "$session_id" ]]; then
        echo "ERROR: session_id is required" >&2
        return 1
    fi

    # Ensure base log directory exists
    local logs_base
    logs_base="$(curb_logs_dir)"
    mkdir -p "$logs_base"

    # Create project-specific log directory
    local project_log_dir="${logs_base}/${project_name}"
    mkdir -p "$project_log_dir"

    # Set log file path
    _LOG_FILE="${project_log_dir}/${session_id}.jsonl"

    # Create log file if it doesn't exist
    touch "$_LOG_FILE"

    return 0
}

# Write a log entry in JSONL format
# Appends a single JSON line to the log file
#
# Args:
#   $1 - event_type: Type of event (e.g., "task_start", "error", "info")
#   $2 - data_json: JSON string containing event data (optional)
#
# Returns:
#   0 on success, 1 on failure
#
# Example:
#   logger_write "task_start" '{"task_id": "curb-123", "name": "test"}'
#   logger_write "info" '{"message": "Processing complete"}'
logger_write() {
    local event_type="$1"
    local data_json="$2"

    # Set default if not provided
    if [[ -z "$data_json" ]]; then
        data_json="{}"
    fi

    # Check if logger is initialized
    if [[ -z "$_LOG_FILE" ]]; then
        echo "ERROR: Logger not initialized. Call logger_init first." >&2
        return 1
    fi

    # Validate event_type
    if [[ -z "$event_type" ]]; then
        echo "ERROR: event_type is required" >&2
        return 1
    fi

    # Get current timestamp in ISO 8601 format
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Validate data_json is valid JSON
    if ! echo "$data_json" | jq -e '.' > /dev/null 2>&1; then
        echo "ERROR: data_json is not valid JSON: $data_json" >&2
        return 1
    fi

    # Build JSON log entry using jq for safe construction
    # Use echo to pipe the data_json so it's properly parsed
    local log_entry
    log_entry=$(echo "$data_json" | jq -c \
        --arg ts "$timestamp" \
        --arg type "$event_type" \
        '{timestamp: $ts, event_type: $type, data: .}')

    # Check if jq succeeded
    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to construct JSON log entry" >&2
        return 1
    fi

    # Append to log file
    echo "$log_entry" >> "$_LOG_FILE"

    return 0
}

# Get current log file path
# Returns the path to the current log file
#
# Returns:
#   Path to log file if initialized, empty string otherwise
#
# Example:
#   log_path=$(logger_get_file)
logger_get_file() {
    echo "$_LOG_FILE"
}

# Clear logger state (useful for testing)
# Resets the _LOG_FILE variable
#
# Returns:
#   0 always
#
# Example:
#   logger_clear
logger_clear() {
    _LOG_FILE=""
    return 0
}

# Log task start event with metadata
# Records task_id, title, harness, and timestamp
#
# Args:
#   $1 - task_id: Unique task identifier (e.g., "curb-123")
#   $2 - task_title: Human-readable task title
#   $3 - harness: Harness being used (e.g., "claude", "opencode")
#
# Returns:
#   0 on success, 1 on failure
#
# Example:
#   log_task_start "curb-123" "Implement feature X" "claude"
log_task_start() {
    local task_id="$1"
    local task_title="$2"
    local harness="$3"

    # Validate required arguments
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    if [[ -z "$task_title" ]]; then
        echo "ERROR: task_title is required" >&2
        return 1
    fi

    if [[ -z "$harness" ]]; then
        echo "ERROR: harness is required" >&2
        return 1
    fi

    # Build JSON data using jq for safe construction
    local data_json
    data_json=$(jq -cn \
        --arg task_id "$task_id" \
        --arg task_title "$task_title" \
        --arg harness "$harness" \
        '{task_id: $task_id, task_title: $task_title, harness: $harness}')

    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to construct task_start JSON" >&2
        return 1
    fi

    # Write log entry
    logger_write "task_start" "$data_json"
}

# Log task end event with metadata
# Records task_id, exit_code, duration, tokens used, and git SHA
#
# Args:
#   $1 - task_id: Unique task identifier (e.g., "curb-123")
#   $2 - exit_code: Exit code from task execution
#   $3 - duration_sec: Duration in seconds
#   $4 - tokens_used: Number of tokens used (optional, defaults to 0)
#
# Returns:
#   0 on success, 1 on failure
#
# Example:
#   log_task_end "curb-123" 0 42 1500
log_task_end() {
    local task_id="$1"
    local exit_code="$2"
    local duration_sec="$3"
    local tokens_used="${4:-0}"
    local budget_remaining="${5:-}"
    local budget_total="${6:-}"

    # Validate required arguments
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    if [[ -z "$exit_code" ]]; then
        echo "ERROR: exit_code is required" >&2
        return 1
    fi

    if [[ -z "$duration_sec" ]]; then
        echo "ERROR: duration_sec is required" >&2
        return 1
    fi

    # Capture git SHA for traceability
    local git_sha
    git_sha=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

    # Build JSON data using jq for safe construction
    local data_json
    if [[ -n "$budget_remaining" && -n "$budget_total" ]]; then
        data_json=$(jq -cn \
            --arg task_id "$task_id" \
            --argjson exit_code "$exit_code" \
            --argjson duration_sec "$duration_sec" \
            --argjson tokens_used "$tokens_used" \
            --argjson budget_remaining "$budget_remaining" \
            --argjson budget_total "$budget_total" \
            --arg git_sha "$git_sha" \
            '{task_id: $task_id, exit_code: $exit_code, duration_sec: $duration_sec, tokens_used: $tokens_used, budget_remaining: $budget_remaining, budget_total: $budget_total, git_sha: $git_sha}')
    else
        data_json=$(jq -cn \
            --arg task_id "$task_id" \
            --argjson exit_code "$exit_code" \
            --argjson duration_sec "$duration_sec" \
            --argjson tokens_used "$tokens_used" \
            --arg git_sha "$git_sha" \
            '{task_id: $task_id, exit_code: $exit_code, duration_sec: $duration_sec, tokens_used: $tokens_used, git_sha: $git_sha}')
    fi

    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to construct task_end JSON" >&2
        return 1
    fi

    # Write log entry
    logger_write "task_end" "$data_json"
}

# Log error event with message and context
# Records error message and optional context object
#
# Args:
#   $1 - message: Error message
#   $2 - context: JSON object with additional context (optional)
#
# Returns:
#   0 on success, 1 on failure
#
# Example:
#   log_error "Task failed" '{"task_id": "curb-123", "reason": "timeout"}'
#   log_error "Configuration error"
log_error() {
    local message="$1"
    local context="$2"

    # Validate required arguments
    if [[ -z "$message" ]]; then
        echo "ERROR: message is required" >&2
        return 1
    fi

    # Set default context if not provided
    if [[ -z "$context" ]]; then
        context="{}"
    fi

    # Validate context is valid JSON
    if ! echo "$context" | jq -e '.' > /dev/null 2>&1; then
        echo "ERROR: context is not valid JSON: $context" >&2
        return 1
    fi

    # Build JSON data using jq for safe construction
    local data_json
    data_json=$(echo "$context" | jq -c \
        --arg message "$message" \
        '{message: $message, context: .}')

    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to construct error JSON" >&2
        return 1
    fi

    # Write log entry
    logger_write "error" "$data_json"
}
