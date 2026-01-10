#!/usr/bin/env bash
#
# budget.sh - Token budget tracking and enforcement
#
# Tracks cumulative token usage across loop iterations to enforce spending limits.
# Provides functions to initialize budget, record usage, check limits, and query remaining budget.
#
# Usage:
#   budget_init 1000000              # Set budget limit to 1M tokens
#   budget_record 5000               # Record 5K tokens used
#   budget_check                     # Returns 1 if over budget
#   budget_remaining                 # Echoes remaining tokens
#

# State files for budget tracking
# Using files instead of variables because bash command substitution creates subshells
_BUDGET_LIMIT_FILE="${TMPDIR:-/tmp}/curb_budget_limit_$$"
_BUDGET_USED_FILE="${TMPDIR:-/tmp}/curb_budget_used_$$"
_BUDGET_WARNED_FILE="${TMPDIR:-/tmp}/curb_budget_warned_$$"

# Clean up state files on exit
trap 'rm -f "$_BUDGET_LIMIT_FILE" "$_BUDGET_USED_FILE" "$_BUDGET_WARNED_FILE" 2>/dev/null' EXIT

# Initialize the budget limit for this run
# Sets the maximum number of tokens allowed for this session.
#
# Parameters:
#   $1 - limit (required): Maximum number of tokens allowed
#
# Returns:
#   0 on success
#   1 if limit parameter is missing or invalid
#
# Example:
#   budget_init 1000000  # Set limit to 1 million tokens
budget_init() {
    local limit="$1"

    # Validate parameter
    if [[ -z "$limit" ]]; then
        echo "ERROR: budget_init requires limit parameter" >&2
        return 1
    fi

    # Validate it's a number
    if ! [[ "$limit" =~ ^[0-9]+$ ]]; then
        echo "ERROR: budget_init limit must be a positive integer" >&2
        return 1
    fi

    # Write state to files
    echo "$limit" > "$_BUDGET_LIMIT_FILE"
    echo "0" > "$_BUDGET_USED_FILE"

    return 0
}

# Record token usage
# Adds the specified number of tokens to the cumulative usage counter.
#
# Parameters:
#   $1 - tokens (required): Number of tokens to add to usage
#
# Returns:
#   0 on success
#   1 if tokens parameter is missing or invalid
#
# Example:
#   budget_record 5000  # Add 5K tokens to usage
budget_record() {
    local tokens="$1"

    # Validate parameter
    if [[ -z "$tokens" ]]; then
        echo "ERROR: budget_record requires tokens parameter" >&2
        return 1
    fi

    # Validate it's a number
    if ! [[ "$tokens" =~ ^[0-9]+$ ]]; then
        echo "ERROR: budget_record tokens must be a positive integer" >&2
        return 1
    fi

    # Read current usage, add new tokens, write back
    local current_used
    current_used=$(cat "$_BUDGET_USED_FILE" 2>/dev/null || echo "0")
    local new_used=$((current_used + tokens))
    echo "$new_used" > "$_BUDGET_USED_FILE"

    return 0
}

# Check if budget has been exceeded
# Compares cumulative usage against the limit.
#
# Returns:
#   0 if within budget
#   1 if over budget or budget not initialized
#
# Example:
#   if budget_check; then
#     echo "Within budget"
#   else
#     echo "Over budget!"
#   fi
budget_check() {
    # Check if budget was initialized
    if [[ ! -f "$_BUDGET_LIMIT_FILE" ]]; then
        echo "ERROR: budget_check called before budget_init" >&2
        return 1
    fi

    # Read current state
    local limit=$(cat "$_BUDGET_LIMIT_FILE")
    local used=$(cat "$_BUDGET_USED_FILE" 2>/dev/null || echo "0")

    # Check if over budget
    if [[ "$used" -gt "$limit" ]]; then
        return 1
    fi

    return 0
}

# Get remaining budget
# Echoes the number of tokens remaining in the budget.
# Returns negative number if over budget.
#
# Returns:
#   0 on success (remaining budget echoed to stdout)
#   1 if budget not initialized
#
# Example:
#   remaining=$(budget_remaining)
#   echo "Tokens remaining: $remaining"
budget_remaining() {
    # Check if budget was initialized
    if [[ ! -f "$_BUDGET_LIMIT_FILE" ]]; then
        echo "ERROR: budget_remaining called before budget_init" >&2
        return 1
    fi

    # Read current state and calculate remaining
    local limit=$(cat "$_BUDGET_LIMIT_FILE")
    local used=$(cat "$_BUDGET_USED_FILE" 2>/dev/null || echo "0")
    local remaining=$((limit - used))
    echo "$remaining"

    return 0
}

# Get current usage
# Echoes the number of tokens used so far.
#
# Returns:
#   0 on success (current usage echoed to stdout)
#
# Example:
#   used=$(budget_get_used)
#   echo "Tokens used: $used"
budget_get_used() {
    local used=$(cat "$_BUDGET_USED_FILE" 2>/dev/null || echo "0")
    echo "$used"
    return 0
}

# Get current limit
# Echoes the budget limit.
#
# Returns:
#   0 on success (limit echoed to stdout)
#
# Example:
#   limit=$(budget_get_limit)
#   echo "Budget limit: $limit"
budget_get_limit() {
    local limit=$(cat "$_BUDGET_LIMIT_FILE" 2>/dev/null || echo "0")
    echo "$limit"
    return 0
}

# Check if budget warning threshold has been crossed
# Warns when usage exceeds warn_at threshold (default 80% of budget).
# Warning is only shown once per run.
#
# Parameters:
#   $1 - warn_at (optional): Percentage threshold (default 80)
#
# Returns:
#   0 always (warning is logged, not an error condition)
#
# Example:
#   budget_check_warning 80  # Warn at 80% of budget (default)
budget_check_warning() {
    local warn_at="${1:-80}"

    # Check if budget was initialized
    if [[ ! -f "$_BUDGET_LIMIT_FILE" ]]; then
        return 0
    fi

    # Check if warning already shown
    if [[ -f "$_BUDGET_WARNED_FILE" ]]; then
        return 0
    fi

    # Read current state
    local limit=$(cat "$_BUDGET_LIMIT_FILE")
    local used=$(cat "$_BUDGET_USED_FILE" 2>/dev/null || echo "0")

    # Guard against division by zero
    if [[ "$limit" -eq 0 ]]; then
        return 0
    fi

    # Calculate percentage used
    local percentage=$((used * 100 / limit))

    # Check if threshold crossed
    if [[ "$percentage" -ge "$warn_at" ]]; then
        # Mark that warning has been shown
        echo "1" > "$_BUDGET_WARNED_FILE"
        # Return 1 to indicate warning was just triggered
        return 1
    fi

    return 0
}

# Clear budget state (for testing)
# Resets budget limit and usage to zero.
#
# Returns:
#   0 on success
#
# Example:
#   budget_clear  # Reset for next test
budget_clear() {
    rm -f "$_BUDGET_LIMIT_FILE" "$_BUDGET_USED_FILE" "$_BUDGET_WARNED_FILE" 2>/dev/null
    return 0
}
