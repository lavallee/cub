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
