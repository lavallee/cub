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
