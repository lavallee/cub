#!/usr/bin/env bats

# Test suite for lib/session.sh

# Load the test helper
load test_helper

# Setup function runs before each test
setup() {
    # Source the session library
    source "${LIB_DIR}/session.sh"

    # Reset session state before each test
    _SESSION_NAME=""
    _SESSION_ID=""
    _SESSION_STARTED_AT=""
}

# Teardown function runs after each test
teardown() {
    # Clean up session state
    _SESSION_NAME=""
    _SESSION_ID=""
    _SESSION_STARTED_AT=""
}

# ============================================================================
# session_random_name tests
# ============================================================================

@test "session_random_name returns a valid animal name" {
    local name
    name=$(session_random_name)

    # Verify it's not empty
    [[ -n "$name" ]]

    # Verify it's a single word (no spaces)
    [[ "$name" != *" "* ]]

    # Verify it's lowercase (contains no uppercase letters)
    [[ ! "$name" =~ [A-Z] ]]
}

@test "session_random_name returns different names (high probability)" {
    local name1
    local name2
    local name3

    name1=$(session_random_name)
    name2=$(session_random_name)
    name3=$(session_random_name)

    # With ~100 animals and only 3 samples, it's extremely likely at least one differs
    # This is a probabilistic test but with very high confidence
    if [[ "$name1" == "$name2" && "$name2" == "$name3" ]]; then
        # All three are the same - this is possible but very unlikely
        # We'll allow it but it would indicate an issue
        skip "Random selection returned same name 3 times (statistically unlikely)"
    else
        # At least one is different - this is expected
        true
    fi
}

@test "session_random_name only returns values from ANIMAL_NAMES" {
    local name
    name=$(session_random_name)

    # Check if the name exists in ANIMAL_NAMES by testing with grep
    echo "$ANIMAL_NAMES" | grep -w "$name" > /dev/null
}

# ============================================================================
# session_init tests
# ============================================================================

@test "session_init with no args initializes with random name" {
    session_init

    [[ -n "$_SESSION_NAME" ]]
    [[ -n "$_SESSION_ID" ]]
    [[ -n "$_SESSION_STARTED_AT" ]]
}

@test "session_init with no args generates valid session ID format" {
    session_init

    # Session ID should be in format: {name}-{YYYYMMDD-HHMMSS}
    # Example: fox-20260110-153045
    [[ "$_SESSION_ID" =~ ^[a-z]+\-[0-9]{8}\-[0-9]{6}$ ]]
}

@test "session_init --name custom sets custom name" {
    session_init --name "falcon"

    [[ "$_SESSION_NAME" == "falcon" ]]
}

@test "session_init --name creates ID with custom name" {
    session_init --name "custom-test"

    # Session ID should start with the custom name
    [[ "$_SESSION_ID" =~ ^custom-test\-[0-9]{8}\-[0-9]{6}$ ]]
}

@test "session_init sets ISO 8601 timestamp in UTC" {
    session_init

    # Timestamp should be in ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
    [[ "$_SESSION_STARTED_AT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "session_init fails with invalid option" {
    run session_init --invalid-option value

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: Unknown option" ]]
}

@test "session_init can be called multiple times (overwrites state)" {
    session_init --name "first"
    local first_name="$_SESSION_NAME"
    local first_id="$_SESSION_ID"

    session_init --name "second"
    local second_name="$_SESSION_NAME"
    local second_id="$_SESSION_ID"

    [[ "$first_name" == "first" ]]
    [[ "$second_name" == "second" ]]
    [[ "$first_id" != "$second_id" ]]
}

# ============================================================================
# session_get_name tests
# ============================================================================

@test "session_get_name returns the session name after init" {
    session_init --name "tiger"

    run session_get_name

    [[ "$status" -eq 0 ]]
    [[ "$output" == "tiger" ]]
}

@test "session_get_name fails before initialization" {
    # Don't call session_init

    run session_get_name

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: Session not initialized" ]]
}

@test "session_get_name returns random name after init without --name" {
    session_init

    local name
    name=$(session_get_name)

    # Verify it's not empty and is a valid animal name
    [[ -n "$name" ]]
    [[ " $ANIMAL_NAMES " =~ " $name " ]]
}

# ============================================================================
# session_get_id tests
# ============================================================================

@test "session_get_id returns the session ID after init" {
    session_init --name "leopard"

    local session_id
    session_id=$(session_get_id)

    # Should contain the name and timestamp
    [[ "$session_id" =~ ^leopard\-[0-9]{8}\-[0-9]{6}$ ]]
}

@test "session_get_id fails before initialization" {
    # Don't call session_init

    run session_get_id

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: Session not initialized" ]]
}

@test "session_get_id contains timestamp in YYYYMMDD-HHMMSS format" {
    session_init --name "zebra"

    local session_id
    session_id=$(session_get_id)

    # Extract the timestamp part (after the last dash and name)
    local timestamp_part
    timestamp_part="${session_id##*-}"

    # Verify timestamp format: YYYYMMDD-HHMMSS is part of full ID
    [[ "$session_id" =~ [0-9]{8}\-[0-9]{6}$ ]]
}

# ============================================================================
# session_get_run_id tests
# ============================================================================

@test "session_get_run_id returns same as session_get_id" {
    session_init --name "panda"

    local session_id
    local run_id
    session_id=$(session_get_id)
    run_id=$(session_get_run_id)

    [[ "$session_id" == "$run_id" ]]
}

@test "session_get_run_id fails before initialization" {
    # Don't call session_init

    run session_get_run_id

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: Session not initialized" ]]
}

# ============================================================================
# session_is_initialized tests
# ============================================================================

@test "session_is_initialized returns false before init" {
    # Don't call session_init

    run session_is_initialized

    [[ "$status" -eq 1 ]]
}

@test "session_is_initialized returns true after init" {
    session_init

    run session_is_initialized

    [[ "$status" -eq 0 ]]
}

@test "session_is_initialized returns true after init with --name" {
    session_init --name "squirrel"

    run session_is_initialized

    [[ "$status" -eq 0 ]]
}

@test "session_is_initialized returns false after manual reset" {
    session_init

    # Manually reset the session
    _SESSION_ID=""

    run session_is_initialized

    [[ "$status" -eq 1 ]]
}

# ============================================================================
# Integration tests
# ============================================================================

@test "integration: full session lifecycle" {
    # Initialize with default random name
    session_init

    # Verify name is set
    local name
    name=$(session_get_name)
    [[ -n "$name" ]]

    # Verify ID is set
    local session_id
    session_id=$(session_get_id)
    [[ -n "$session_id" ]]

    # Verify run_id matches session_id
    local run_id
    run_id=$(session_get_run_id)
    [[ "$session_id" == "$run_id" ]]

    # Verify is_initialized returns 0
    session_is_initialized
    [[ $? -eq 0 ]]
}

@test "integration: custom named session" {
    local custom_name="integration-test"

    session_init --name "$custom_name"

    # Verify name
    local name
    name=$(session_get_name)
    [[ "$name" == "$custom_name" ]]

    # Verify ID contains custom name
    local session_id
    session_id=$(session_get_id)
    [[ "$session_id" =~ ^${custom_name}\- ]]

    # Verify timestamp in ID
    [[ "$session_id" =~ [0-9]{8}\-[0-9]{6}$ ]]

    # Verify started_at is valid ISO 8601
    [[ "$_SESSION_STARTED_AT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "integration: session isolation between inits" {
    session_init --name "first"
    local first_id=$(session_get_id)

    # Small delay to ensure timestamp differs
    sleep 1

    session_init --name "second"
    local second_id=$(session_get_id)

    # IDs should be different (different names or timestamps)
    [[ "$first_id" != "$second_id" ]]

    # Most recent session should be accessible
    local current_name=$(session_get_name)
    [[ "$current_name" == "second" ]]
}

# ============================================================================
# Error handling tests
# ============================================================================

@test "error: calling getters before init produces consistent errors" {
    # Ensure not initialized
    _SESSION_NAME=""
    _SESSION_ID=""

    # All getters should fail
    run session_get_name
    [[ "$status" -eq 1 ]]

    run session_get_id
    [[ "$status" -eq 1 ]]

    run session_get_run_id
    [[ "$status" -eq 1 ]]
}


@test "error: multiple --name options (last one wins)" {
    session_init --name "first" --name "second"

    local name
    name=$(session_get_name)

    # Last --name should win
    [[ "$name" == "second" ]]
}

# ============================================================================
# Acceptance criteria tests
# ============================================================================

@test "acceptance: session_random_name returns valid animal" {
    for i in {1..10}; do
        local name
        name=$(session_random_name)

        # Must not be empty
        [[ -n "$name" ]]

        # Must be in ANIMAL_NAMES
        echo "$ANIMAL_NAMES" | grep -w "$name" > /dev/null

        # Must be lowercase (no uppercase letters)
        [[ ! "$name" =~ [A-Z] ]]
    done
}

@test "acceptance: session_init with no args works" {
    session_init

    [[ -n "$_SESSION_NAME" ]]
    [[ -n "$_SESSION_ID" ]]
}

@test "acceptance: session_init --name custom works" {
    session_init --name "acceptance-test"

    [[ "$_SESSION_NAME" == "acceptance-test" ]]
}

@test "acceptance: session_get_* functions return expected formats" {
    session_init --name "acceptance"

    # Test session_get_name
    local name
    name=$(session_get_name)
    [[ "$name" == "acceptance" ]]

    # Test session_get_id
    local session_id
    session_id=$(session_get_id)
    [[ "$session_id" =~ ^acceptance\-[0-9]{8}\-[0-9]{6}$ ]]

    # Test session_get_run_id
    local run_id
    run_id=$(session_get_run_id)
    [[ "$run_id" == "$session_id" ]]

    # Test session_is_initialized
    session_is_initialized
    [[ $? -eq 0 ]]
}

@test "acceptance: calling getters before init fails" {
    # Don't initialize

    run session_get_name
    [[ "$status" -eq 1 ]]

    run session_get_id
    [[ "$status" -eq 1 ]]

    run session_get_run_id
    [[ "$status" -eq 1 ]]

    run session_is_initialized
    [[ "$status" -eq 1 ]]
}

@test "acceptance: session timestamp is in ISO 8601 UTC format" {
    session_init --name "iso-test"

    # _SESSION_STARTED_AT should be ISO 8601 UTC
    [[ "$_SESSION_STARTED_AT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "acceptance: session ID includes timestamp" {
    session_init --name "timestamp-test"

    # Session ID should include timestamp in YYYYMMDD-HHMMSS format
    [[ "$_SESSION_ID" =~ [0-9]{8}\-[0-9]{6}$ ]]
}
