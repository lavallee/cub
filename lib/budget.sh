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

# Iteration tracking state files
_BUDGET_TASK_ITERATIONS_DIR="${TMPDIR:-/tmp}/curb_task_iterations_$$"
_BUDGET_RUN_ITERATIONS_FILE="${TMPDIR:-/tmp}/curb_run_iterations_$$"
_BUDGET_MAX_TASK_ITERATIONS_FILE="${TMPDIR:-/tmp}/curb_max_task_iterations_$$"
_BUDGET_MAX_RUN_ITERATIONS_FILE="${TMPDIR:-/tmp}/curb_max_run_iterations_$$"

# Initialize iteration tracking directory and defaults
mkdir -p "$_BUDGET_TASK_ITERATIONS_DIR" 2>/dev/null
echo "0" > "$_BUDGET_RUN_ITERATIONS_FILE"
echo "3" > "$_BUDGET_MAX_TASK_ITERATIONS_FILE"  # Default: 3 per task
echo "50" > "$_BUDGET_MAX_RUN_ITERATIONS_FILE"  # Default: 50 per run

# Clean up state files on exit
trap 'rm -f "$_BUDGET_LIMIT_FILE" "$_BUDGET_USED_FILE" "$_BUDGET_WARNED_FILE" "$_BUDGET_RUN_ITERATIONS_FILE" "$_BUDGET_MAX_TASK_ITERATIONS_FILE" "$_BUDGET_MAX_RUN_ITERATIONS_FILE" 2>/dev/null; rm -rf "$_BUDGET_TASK_ITERATIONS_DIR" 2>/dev/null' EXIT

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
    rm -f "$_BUDGET_RUN_ITERATIONS_FILE" "$_BUDGET_MAX_TASK_ITERATIONS_FILE" "$_BUDGET_MAX_RUN_ITERATIONS_FILE" 2>/dev/null
    rm -rf "$_BUDGET_TASK_ITERATIONS_DIR" 2>/dev/null
    # Reinitialize iteration tracking
    mkdir -p "$_BUDGET_TASK_ITERATIONS_DIR" 2>/dev/null
    echo "0" > "$_BUDGET_RUN_ITERATIONS_FILE"
    echo "3" > "$_BUDGET_MAX_TASK_ITERATIONS_FILE"
    echo "50" > "$_BUDGET_MAX_RUN_ITERATIONS_FILE"
    return 0
}

# ========================================
# Iteration Tracking Functions
# ========================================

# Set maximum iterations allowed per task
# Sets the limit for how many times a single task can be retried.
#
# Parameters:
#   $1 - max_iterations (required): Maximum iterations per task
#
# Returns:
#   0 on success
#   1 if parameter is missing or invalid
#
# Example:
#   budget_set_max_task_iterations 5  # Allow up to 5 retries per task
budget_set_max_task_iterations() {
    local max_iterations="$1"

    # Validate parameter
    if [[ -z "$max_iterations" ]]; then
        echo "ERROR: budget_set_max_task_iterations requires max_iterations parameter" >&2
        return 1
    fi

    # Validate it's a number
    if ! [[ "$max_iterations" =~ ^[0-9]+$ ]]; then
        echo "ERROR: budget_set_max_task_iterations max_iterations must be a positive integer" >&2
        return 1
    fi

    echo "$max_iterations" > "$_BUDGET_MAX_TASK_ITERATIONS_FILE"
    return 0
}

# Set maximum iterations allowed per run
# Sets the limit for how many iterations can occur in a single run.
#
# Parameters:
#   $1 - max_iterations (required): Maximum iterations per run
#
# Returns:
#   0 on success
#   1 if parameter is missing or invalid
#
# Example:
#   budget_set_max_run_iterations 100  # Allow up to 100 iterations per run
budget_set_max_run_iterations() {
    local max_iterations="$1"

    # Validate parameter
    if [[ -z "$max_iterations" ]]; then
        echo "ERROR: budget_set_max_run_iterations requires max_iterations parameter" >&2
        return 1
    fi

    # Validate it's a number
    if ! [[ "$max_iterations" =~ ^[0-9]+$ ]]; then
        echo "ERROR: budget_set_max_run_iterations max_iterations must be a positive integer" >&2
        return 1
    fi

    echo "$max_iterations" > "$_BUDGET_MAX_RUN_ITERATIONS_FILE"
    return 0
}

# Get iteration count for a specific task
# Returns the number of times a task has been attempted.
#
# Parameters:
#   $1 - task_id (required): The task identifier
#
# Returns:
#   0 on success (iteration count echoed to stdout)
#   1 if task_id parameter is missing
#
# Example:
#   iterations=$(budget_get_task_iterations "task-123")
#   echo "Task attempted $iterations times"
budget_get_task_iterations() {
    local task_id="$1"

    # Validate parameter
    if [[ -z "$task_id" ]]; then
        echo "ERROR: budget_get_task_iterations requires task_id parameter" >&2
        return 1
    fi

    # Create safe filename from task_id
    local safe_task_id
    safe_task_id=$(echo "$task_id" | sed 's/[^a-zA-Z0-9_-]/_/g')
    local task_file="${_BUDGET_TASK_ITERATIONS_DIR}/${safe_task_id}"

    # Read iteration count, default to 0 if file doesn't exist
    local iterations
    iterations=$(cat "$task_file" 2>/dev/null || echo "0")
    echo "$iterations"
    return 0
}

# Get total iteration count for the current run
# Returns the number of iterations that have occurred in this run.
#
# Returns:
#   0 on success (iteration count echoed to stdout)
#
# Example:
#   iterations=$(budget_get_run_iterations)
#   echo "Run has completed $iterations iterations"
budget_get_run_iterations() {
    local iterations
    iterations=$(cat "$_BUDGET_RUN_ITERATIONS_FILE" 2>/dev/null || echo "0")
    echo "$iterations"
    return 0
}

# Increment iteration count for a specific task
# Increases the task's iteration counter by 1.
#
# Parameters:
#   $1 - task_id (required): The task identifier
#
# Returns:
#   0 on success
#   1 if task_id parameter is missing
#
# Example:
#   budget_increment_task_iterations "task-123"
budget_increment_task_iterations() {
    local task_id="$1"

    # Validate parameter
    if [[ -z "$task_id" ]]; then
        echo "ERROR: budget_increment_task_iterations requires task_id parameter" >&2
        return 1
    fi

    # Create safe filename from task_id
    local safe_task_id
    safe_task_id=$(echo "$task_id" | sed 's/[^a-zA-Z0-9_-]/_/g')
    local task_file="${_BUDGET_TASK_ITERATIONS_DIR}/${safe_task_id}"

    # Read current count, increment, and write back
    local current
    current=$(cat "$task_file" 2>/dev/null || echo "0")
    local new_count=$((current + 1))
    echo "$new_count" > "$task_file"

    return 0
}

# Increment total iteration count for the current run
# Increases the run's iteration counter by 1.
#
# Returns:
#   0 on success
#
# Example:
#   budget_increment_run_iterations
budget_increment_run_iterations() {
    # Read current count, increment, and write back
    local current
    current=$(cat "$_BUDGET_RUN_ITERATIONS_FILE" 2>/dev/null || echo "0")
    local new_count=$((current + 1))
    echo "$new_count" > "$_BUDGET_RUN_ITERATIONS_FILE"

    return 0
}

# Get maximum iterations allowed per task
# Returns the configured limit for task iterations.
#
# Returns:
#   0 on success (max iterations echoed to stdout)
#
# Example:
#   max=$(budget_get_max_task_iterations)
#   echo "Maximum task iterations: $max"
budget_get_max_task_iterations() {
    local max
    max=$(cat "$_BUDGET_MAX_TASK_ITERATIONS_FILE" 2>/dev/null || echo "3")
    echo "$max"
    return 0
}

# Get maximum iterations allowed per run
# Returns the configured limit for run iterations.
#
# Returns:
#   0 on success (max iterations echoed to stdout)
#
# Example:
#   max=$(budget_get_max_run_iterations)
#   echo "Maximum run iterations: $max"
budget_get_max_run_iterations() {
    local max
    max=$(cat "$_BUDGET_MAX_RUN_ITERATIONS_FILE" 2>/dev/null || echo "50")
    echo "$max"
    return 0
}

# Check if task iteration limit has been exceeded
# Compares task's iteration count against the maximum allowed.
#
# Parameters:
#   $1 - task_id (required): The task identifier
#
# Returns:
#   0 if within limit
#   1 if limit exceeded or task_id missing
#
# Example:
#   if budget_check_task_iterations "task-123"; then
#     echo "Within task iteration limit"
#   else
#     echo "Task iteration limit exceeded!"
#   fi
budget_check_task_iterations() {
    local task_id="$1"

    # Validate parameter
    if [[ -z "$task_id" ]]; then
        echo "ERROR: budget_check_task_iterations requires task_id parameter" >&2
        return 1
    fi

    local current
    current=$(budget_get_task_iterations "$task_id")
    local max
    max=$(budget_get_max_task_iterations)

    # Check if over limit
    if [[ "$current" -gt "$max" ]]; then
        return 1
    fi

    return 0
}

# Check if run iteration limit has been exceeded
# Compares run's iteration count against the maximum allowed.
#
# Returns:
#   0 if within limit
#   1 if limit exceeded
#
# Example:
#   if budget_check_run_iterations; then
#     echo "Within run iteration limit"
#   else
#     echo "Run iteration limit exceeded!"
#   fi
budget_check_run_iterations() {
    local current
    current=$(budget_get_run_iterations)
    local max
    max=$(budget_get_max_run_iterations)

    # Check if over limit
    if [[ "$current" -gt "$max" ]]; then
        return 1
    fi

    return 0
}
