#!/usr/bin/env bats

# Test suite for lib/budget.sh

# Load the test helper
load test_helper

# Setup function runs before each test
setup() {
    # Source the budget library
    source "${PROJECT_ROOT}/lib/budget.sh"

    # Clear budget state before each test
    budget_clear
}

# Teardown function runs after each test
teardown() {
    # Clear budget state after each test
    budget_clear
}

# ========================================
# budget_init tests
# ========================================

@test "budget_init sets limit correctly" {
    run budget_init 1000000
    [ "$status" -eq 0 ]

    # Verify limit was set
    limit=$(budget_get_limit)
    [ "$limit" -eq 1000000 ]

    # Verify usage starts at 0
    used=$(budget_get_used)
    [ "$used" -eq 0 ]
}

@test "budget_init resets usage to zero" {
    # Set initial budget and record usage
    budget_init 1000000
    budget_record 5000

    # Re-initialize with new limit
    run budget_init 500000
    [ "$status" -eq 0 ]

    # Verify usage was reset
    used=$(budget_get_used)
    [ "$used" -eq 0 ]

    # Verify new limit
    limit=$(budget_get_limit)
    [ "$limit" -eq 500000 ]
}

@test "budget_init fails without limit parameter" {
    run budget_init
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires limit parameter" ]]
}

@test "budget_init fails with non-numeric limit" {
    run budget_init "abc"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "must be a positive integer" ]]
}

@test "budget_init accepts zero as limit" {
    run budget_init 0
    [ "$status" -eq 0 ]

    limit=$(budget_get_limit)
    [ "$limit" -eq 0 ]
}

# ========================================
# budget_record tests
# ========================================

@test "budget_record accumulates usage" {
    budget_init 1000000

    # Record first usage
    run budget_record 1000
    [ "$status" -eq 0 ]
    used=$(budget_get_used)
    [ "$used" -eq 1000 ]

    # Record second usage
    run budget_record 2000
    [ "$status" -eq 0 ]
    used=$(budget_get_used)
    [ "$used" -eq 3000 ]

    # Record third usage
    run budget_record 500
    [ "$status" -eq 0 ]
    used=$(budget_get_used)
    [ "$used" -eq 3500 ]
}

@test "budget_record fails without tokens parameter" {
    budget_init 1000000

    run budget_record
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires tokens parameter" ]]
}

@test "budget_record fails with non-numeric tokens" {
    budget_init 1000000

    run budget_record "xyz"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "must be a positive integer" ]]
}

@test "budget_record accepts zero tokens" {
    budget_init 1000000

    run budget_record 0
    [ "$status" -eq 0 ]

    used=$(budget_get_used)
    [ "$used" -eq 0 ]
}

# ========================================
# budget_check tests
# ========================================

@test "budget_check returns 0 when within budget" {
    budget_init 1000000
    budget_record 500000

    run budget_check
    [ "$status" -eq 0 ]
}

@test "budget_check returns 1 when over budget" {
    budget_init 1000000
    budget_record 1000001

    run budget_check
    [ "$status" -eq 1 ]
}

@test "budget_check returns 0 when exactly at budget" {
    budget_init 1000000
    budget_record 1000000

    run budget_check
    [ "$status" -eq 0 ]
}

@test "budget_check fails if budget not initialized" {
    # Don't call budget_init
    run budget_check
    [ "$status" -eq 1 ]
    [[ "$output" =~ "called before budget_init" ]]
}

# ========================================
# budget_remaining tests
# ========================================

@test "budget_remaining shows correct value" {
    budget_init 1000000
    budget_record 300000

    remaining=$(budget_remaining)
    [ "$remaining" -eq 700000 ]
}

@test "budget_remaining shows negative when over budget" {
    budget_init 1000000
    budget_record 1200000

    remaining=$(budget_remaining)
    [ "$remaining" -eq -200000 ]
}

@test "budget_remaining shows full budget when no usage" {
    budget_init 1000000

    remaining=$(budget_remaining)
    [ "$remaining" -eq 1000000 ]
}

@test "budget_remaining fails if budget not initialized" {
    # Don't call budget_init
    run budget_remaining
    [ "$status" -eq 1 ]
    [[ "$output" =~ "called before budget_init" ]]
}

# ========================================
# Integration tests
# ========================================

@test "full budget lifecycle within budget" {
    # Initialize with 100K token budget
    budget_init 100000

    # Simulate multiple iterations
    budget_record 10000  # Iteration 1: 10K tokens
    [ "$(budget_get_used)" -eq 10000 ]
    budget_check
    [ "$?" -eq 0 ]

    budget_record 20000  # Iteration 2: 20K tokens
    [ "$(budget_get_used)" -eq 30000 ]
    budget_check
    [ "$?" -eq 0 ]

    budget_record 30000  # Iteration 3: 30K tokens
    [ "$(budget_get_used)" -eq 60000 ]
    budget_check
    [ "$?" -eq 0 ]

    # Check remaining budget
    remaining=$(budget_remaining)
    [ "$remaining" -eq 40000 ]
}

@test "full budget lifecycle exceeding budget" {
    # Initialize with small budget
    budget_init 50000

    # Use up most of budget
    budget_record 45000
    budget_check
    [ "$?" -eq 0 ]

    # This iteration pushes us over
    budget_record 10000
    [ "$(budget_get_used)" -eq 55000 ]

    # Now we're over budget
    run budget_check
    [ "$status" -eq 1 ]

    # Remaining is negative
    remaining=$(budget_remaining)
    [ "$remaining" -eq -5000 ]
}

@test "budget re-initialization clears previous state" {
    # First run
    budget_init 100000
    budget_record 50000
    budget_record 30000
    [ "$(budget_get_used)" -eq 80000 ]

    # Re-initialize for new run
    budget_init 200000
    [ "$(budget_get_limit)" -eq 200000 ]
    [ "$(budget_get_used)" -eq 0 ]

    # Start fresh
    budget_record 10000
    [ "$(budget_get_used)" -eq 10000 ]
}

# ========================================
# Acceptance criteria tests
# ========================================

@test "ACCEPTANCE: budget_init sets limit correctly" {
    budget_init 1000000
    [ "$(budget_get_limit)" -eq 1000000 ]
}

@test "ACCEPTANCE: budget_record accumulates usage" {
    budget_init 1000000
    budget_record 100
    budget_record 200
    budget_record 300
    [ "$(budget_get_used)" -eq 600 ]
}

@test "ACCEPTANCE: budget_check returns 1 when over" {
    budget_init 1000
    budget_record 1001
    run budget_check
    [ "$status" -eq 1 ]
}

@test "ACCEPTANCE: budget_remaining shows correct value" {
    budget_init 1000000
    budget_record 400000
    [ "$(budget_remaining)" -eq 600000 ]
}

# ========================================
# budget_check_warning tests
# ========================================

@test "budget_check_warning returns 0 when budget not initialized" {
    run budget_check_warning 80
    [ "$status" -eq 0 ]
}

@test "budget_check_warning does nothing when under threshold" {
    budget_init 1000000
    budget_record 700000
    run budget_check_warning 80
    [ "$status" -eq 0 ]
    # Warning file should not exist
    [ ! -f "${TMPDIR:-/tmp}/curb_budget_warned_$$" ]
}

@test "budget_check_warning sets flag when at threshold" {
    budget_init 1000000
    budget_record 800000
    run budget_check_warning 80
    # Returns 1 when warning is triggered
    [ "$status" -eq 1 ]
    # Warning file should exist
    [ -f "${TMPDIR:-/tmp}/curb_budget_warned_$$" ]
}

@test "budget_check_warning sets flag when over threshold" {
    budget_init 1000000
    budget_record 900000
    run budget_check_warning 80
    # Returns 1 when warning is triggered
    [ "$status" -eq 1 ]
    # Warning file should exist
    [ -f "${TMPDIR:-/tmp}/curb_budget_warned_$$" ]
}

@test "budget_check_warning only warns once" {
    budget_init 1000000
    budget_record 800000

    # First call should set the warning and return 1
    run budget_check_warning 80
    [ "$status" -eq 1 ]
    [ -f "${TMPDIR:-/tmp}/curb_budget_warned_$$" ]

    # Second call should return 0 (already warned)
    run budget_check_warning 80
    [ "$status" -eq 0 ]
    [ -f "${TMPDIR:-/tmp}/curb_budget_warned_$$" ]
}

@test "budget_check_warning uses custom threshold" {
    budget_init 1000000
    budget_record 500000

    # At 50% usage, should not warn at 80% threshold
    run budget_check_warning 80
    [ "$status" -eq 0 ]
    [ ! -f "${TMPDIR:-/tmp}/curb_budget_warned_$$" ]

    # Clear and try with lower threshold
    budget_clear
    budget_init 1000000
    budget_record 500000
    run budget_check_warning 40
    [ "$status" -eq 1 ]
    [ -f "${TMPDIR:-/tmp}/curb_budget_warned_$$" ]
}

@test "ACCEPTANCE: budget_check_warning shows only once per run" {
    budget_init 1000000
    budget_record 800000

    # First warning - returns 1
    run budget_check_warning 80
    [ "$status" -eq 1 ]
    [ -f "${TMPDIR:-/tmp}/curb_budget_warned_$$" ]

    # Record more usage
    budget_record 100000

    # Second call returns 0 (already warned)
    run budget_check_warning 80
    [ "$status" -eq 0 ]
    [ -f "${TMPDIR:-/tmp}/curb_budget_warned_$$" ]
}

# ========================================
# Iteration tracking tests
# ========================================

@test "budget_set_max_task_iterations sets limit correctly" {
    run budget_set_max_task_iterations 5
    [ "$status" -eq 0 ]

    # Verify limit was set
    max=$(budget_get_max_task_iterations)
    [ "$max" -eq 5 ]
}

@test "budget_set_max_task_iterations fails without parameter" {
    run budget_set_max_task_iterations
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires max_iterations parameter" ]]
}

@test "budget_set_max_task_iterations fails with non-numeric value" {
    run budget_set_max_task_iterations "abc"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "must be a positive integer" ]]
}

@test "budget_set_max_run_iterations sets limit correctly" {
    run budget_set_max_run_iterations 100
    [ "$status" -eq 0 ]

    # Verify limit was set
    max=$(budget_get_max_run_iterations)
    [ "$max" -eq 100 ]
}

@test "budget_set_max_run_iterations fails without parameter" {
    run budget_set_max_run_iterations
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires max_iterations parameter" ]]
}

@test "budget_set_max_run_iterations fails with non-numeric value" {
    run budget_set_max_run_iterations "xyz"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "must be a positive integer" ]]
}

@test "budget_get_task_iterations returns 0 for new task" {
    iterations=$(budget_get_task_iterations "task-123")
    [ "$iterations" -eq 0 ]
}

@test "budget_get_task_iterations fails without task_id" {
    run budget_get_task_iterations
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires task_id parameter" ]]
}

@test "budget_get_run_iterations returns 0 initially" {
    iterations=$(budget_get_run_iterations)
    [ "$iterations" -eq 0 ]
}

@test "budget_increment_task_iterations increments counter" {
    # First increment
    run budget_increment_task_iterations "task-123"
    [ "$status" -eq 0 ]
    iterations=$(budget_get_task_iterations "task-123")
    [ "$iterations" -eq 1 ]

    # Second increment
    run budget_increment_task_iterations "task-123"
    [ "$status" -eq 0 ]
    iterations=$(budget_get_task_iterations "task-123")
    [ "$iterations" -eq 2 ]

    # Third increment
    run budget_increment_task_iterations "task-123"
    [ "$status" -eq 0 ]
    iterations=$(budget_get_task_iterations "task-123")
    [ "$iterations" -eq 3 ]
}

@test "budget_increment_task_iterations fails without task_id" {
    run budget_increment_task_iterations
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires task_id parameter" ]]
}

@test "budget_increment_task_iterations tracks multiple tasks separately" {
    # Increment task-123
    budget_increment_task_iterations "task-123"
    budget_increment_task_iterations "task-123"

    # Increment task-456
    budget_increment_task_iterations "task-456"

    # Verify separate counters
    iterations_123=$(budget_get_task_iterations "task-123")
    iterations_456=$(budget_get_task_iterations "task-456")
    [ "$iterations_123" -eq 2 ]
    [ "$iterations_456" -eq 1 ]
}

@test "budget_increment_run_iterations increments counter" {
    # First increment
    run budget_increment_run_iterations
    [ "$status" -eq 0 ]
    iterations=$(budget_get_run_iterations)
    [ "$iterations" -eq 1 ]

    # Second increment
    run budget_increment_run_iterations
    [ "$status" -eq 0 ]
    iterations=$(budget_get_run_iterations)
    [ "$iterations" -eq 2 ]

    # Third increment
    run budget_increment_run_iterations
    [ "$status" -eq 0 ]
    iterations=$(budget_get_run_iterations)
    [ "$iterations" -eq 3 ]
}

@test "budget_get_max_task_iterations returns default of 3" {
    max=$(budget_get_max_task_iterations)
    [ "$max" -eq 3 ]
}

@test "budget_get_max_run_iterations returns default of 50" {
    max=$(budget_get_max_run_iterations)
    [ "$max" -eq 50 ]
}

@test "budget_check_task_iterations returns 0 when within limit" {
    budget_set_max_task_iterations 3
    budget_increment_task_iterations "task-123"
    budget_increment_task_iterations "task-123"

    run budget_check_task_iterations "task-123"
    [ "$status" -eq 0 ]
}

@test "budget_check_task_iterations returns 1 when over limit" {
    budget_set_max_task_iterations 3
    budget_increment_task_iterations "task-123"
    budget_increment_task_iterations "task-123"
    budget_increment_task_iterations "task-123"
    budget_increment_task_iterations "task-123"

    run budget_check_task_iterations "task-123"
    [ "$status" -eq 1 ]
}

@test "budget_check_task_iterations returns 0 when exactly at limit" {
    budget_set_max_task_iterations 3
    budget_increment_task_iterations "task-123"
    budget_increment_task_iterations "task-123"
    budget_increment_task_iterations "task-123"

    run budget_check_task_iterations "task-123"
    [ "$status" -eq 0 ]
}

@test "budget_check_task_iterations fails without task_id" {
    run budget_check_task_iterations
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires task_id parameter" ]]
}

@test "budget_check_run_iterations returns 0 when within limit" {
    budget_set_max_run_iterations 5
    budget_increment_run_iterations
    budget_increment_run_iterations

    run budget_check_run_iterations
    [ "$status" -eq 0 ]
}

@test "budget_check_run_iterations returns 1 when over limit" {
    budget_set_max_run_iterations 3
    budget_increment_run_iterations
    budget_increment_run_iterations
    budget_increment_run_iterations
    budget_increment_run_iterations

    run budget_check_run_iterations
    [ "$status" -eq 1 ]
}

@test "budget_check_run_iterations returns 0 when exactly at limit" {
    budget_set_max_run_iterations 3
    budget_increment_run_iterations
    budget_increment_run_iterations
    budget_increment_run_iterations

    run budget_check_run_iterations
    [ "$status" -eq 0 ]
}

@test "budget_clear resets iteration counters" {
    # Set some iterations
    budget_increment_task_iterations "task-123"
    budget_increment_task_iterations "task-123"
    budget_increment_run_iterations
    budget_set_max_task_iterations 10
    budget_set_max_run_iterations 20

    # Clear
    budget_clear

    # Verify all reset to defaults
    [ "$(budget_get_task_iterations "task-123")" -eq 0 ]
    [ "$(budget_get_run_iterations)" -eq 0 ]
    [ "$(budget_get_max_task_iterations)" -eq 3 ]
    [ "$(budget_get_max_run_iterations)" -eq 50 ]
}

@test "task_id with special characters is handled safely" {
    # Test with task IDs containing special characters
    budget_increment_task_iterations "task/with/slashes"
    budget_increment_task_iterations "task:with:colons"
    budget_increment_task_iterations "task with spaces"

    # Verify they work
    [ "$(budget_get_task_iterations "task/with/slashes")" -eq 1 ]
    [ "$(budget_get_task_iterations "task:with:colons")" -eq 1 ]
    [ "$(budget_get_task_iterations "task with spaces")" -eq 1 ]
}

# ========================================
# Acceptance criteria tests for iteration tracking
# ========================================

@test "ACCEPTANCE: iteration counters track per-task" {
    # Track multiple tasks
    budget_increment_task_iterations "task-001"
    budget_increment_task_iterations "task-001"
    budget_increment_task_iterations "task-001"

    budget_increment_task_iterations "task-002"
    budget_increment_task_iterations "task-002"

    # Verify separate tracking
    [ "$(budget_get_task_iterations "task-001")" -eq 3 ]
    [ "$(budget_get_task_iterations "task-002")" -eq 2 ]
}

@test "ACCEPTANCE: iteration counters track per-run" {
    # Track run iterations
    budget_increment_run_iterations
    budget_increment_run_iterations
    budget_increment_run_iterations

    # Verify tracking
    [ "$(budget_get_run_iterations)" -eq 3 ]
}

@test "ACCEPTANCE: config options for max iterations" {
    # Set custom limits
    budget_set_max_task_iterations 5
    budget_set_max_run_iterations 100

    # Verify they're set
    [ "$(budget_get_max_task_iterations)" -eq 5 ]
    [ "$(budget_get_max_run_iterations)" -eq 100 ]
}

@test "ACCEPTANCE: defaults are 3 per task and 50 per run" {
    # Check defaults after clear
    budget_clear

    [ "$(budget_get_max_task_iterations)" -eq 3 ]
    [ "$(budget_get_max_run_iterations)" -eq 50 ]
}

@test "ACCEPTANCE: counters persist across function calls" {
    # Increment in multiple calls
    budget_increment_task_iterations "task-123"
    local first=$(budget_get_task_iterations "task-123")

    budget_increment_task_iterations "task-123"
    local second=$(budget_get_task_iterations "task-123")

    budget_increment_task_iterations "task-123"
    local third=$(budget_get_task_iterations "task-123")

    # Verify persistence
    [ "$first" -eq 1 ]
    [ "$second" -eq 2 ]
    [ "$third" -eq 3 ]
}
