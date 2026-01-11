#!/usr/bin/env bats

# Test suite for lib/failure.sh

# Load the test helper
load test_helper

# Setup function runs before each test
setup() {
    # Source the failure library
    source "${PROJECT_ROOT}/lib/failure.sh"

    # Create temp directory for test artifacts
    TEST_ARTIFACTS_DIR="${BATS_TMPDIR}/artifacts_test_$$"
    mkdir -p "$TEST_ARTIFACTS_DIR"

    # Create a mock task directory for failure storage tests
    TEST_TASK_DIR="${TEST_ARTIFACTS_DIR}/curb-test"
    mkdir -p "$TEST_TASK_DIR"

    # Override artifacts_get_base_dir to use test directory
    artifacts_get_base_dir() {
        echo "$TEST_ARTIFACTS_DIR"
    }

    # Clear failure mode before each test
    failure_mode="move-on"
}

# Teardown function runs after each test
teardown() {
    # Clean up test directories
    rm -rf "$TEST_ARTIFACTS_DIR" 2>/dev/null || true
}

# ============================================================================
# failure_handle_stop tests
# ============================================================================

@test "failure_handle_stop returns exit code 2 (halt signal)" {
    run failure_handle_stop "curb-test" 1 "Test error"

    # Should return 2 to signal halt
    [[ $status -eq 2 ]]
}

@test "failure_handle_stop requires task_id parameter" {
    run failure_handle_stop "" 1 "Test error"

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: task_id is required" ]]
}

@test "failure_handle_stop requires exit_code parameter" {
    run failure_handle_stop "curb-test" "" "Test error"

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: exit_code is required" ]]
}

@test "failure_handle_stop accepts optional output parameter" {
    run failure_handle_stop "curb-test" 1

    # Should return 2 even without output
    [[ $status -eq 2 ]]
}

@test "failure_handle_stop stores failure info" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call handle_stop
    failure_handle_stop "curb-test" 1 "Test error" 2>/dev/null || true

    # Check if failure.json was created
    [[ -f "${TEST_ARTIFACTS_DIR}/curb-test/failure.json" ]]
}

@test "failure_handle_stop stores correct failure mode in JSON" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call handle_stop
    failure_handle_stop "curb-test" 1 "Test error" 2>/dev/null || true

    # Check failure mode in JSON
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    [[ "$mode" == "stop" ]]
}

# ============================================================================
# failure_handle_move_on tests
# ============================================================================

@test "failure_handle_move_on returns exit code 0 (continue signal)" {
    run failure_handle_move_on "curb-test" 1 "Test error"

    # Should return 0 to signal continue
    [[ $status -eq 0 ]]
}

@test "failure_handle_move_on requires task_id parameter" {
    run failure_handle_move_on "" 1 "Test error"

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: task_id is required" ]]
}

@test "failure_handle_move_on requires exit_code parameter" {
    run failure_handle_move_on "curb-test" "" "Test error"

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: exit_code is required" ]]
}

@test "failure_handle_move_on accepts optional output parameter" {
    run failure_handle_move_on "curb-test" 1

    # Should return 0 even without output
    [[ $status -eq 0 ]]
}

@test "failure_handle_move_on stores failure info" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call handle_move_on
    failure_handle_move_on "curb-test" 1 "Test error" 2>/dev/null

    # Check if failure.json was created
    [[ -f "${TEST_ARTIFACTS_DIR}/curb-test/failure.json" ]]
}

@test "failure_handle_move_on stores correct failure mode in JSON" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call handle_move_on
    failure_handle_move_on "curb-test" 1 "Test error" 2>/dev/null

    # Check failure mode in JSON
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    [[ "$mode" == "move-on" ]]
}

# ============================================================================
# failure_store_info tests
# ============================================================================

@test "failure_store_info creates failure.json in task directory" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call store_info
    failure_store_info "curb-test" 1 "Test error" "stop"

    # Check if failure.json exists
    [[ -f "${TEST_ARTIFACTS_DIR}/curb-test/failure.json" ]]
}

@test "failure_store_info stores all required fields in JSON" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call store_info
    failure_store_info "curb-test" 1 "Test error message" "stop"

    # Verify JSON structure
    local task_id exit_code output mode timestamp
    task_id=$(jq -r '.task_id' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    exit_code=$(jq -r '.exit_code' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    output=$(jq -r '.output' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    timestamp=$(jq -r '.timestamp' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")

    [[ "$task_id" == "curb-test" ]]
    [[ "$exit_code" == "1" ]]
    [[ "$output" == "Test error message" ]]
    [[ "$mode" == "stop" ]]
    [[ -n "$timestamp" ]]
}

@test "failure_store_info requires task_id parameter" {
    run failure_store_info "" 1 "Test error" "stop"

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: task_id is required" ]]
}

@test "failure_store_info requires exit_code parameter" {
    run failure_store_info "curb-test" "" "Test error" "stop"

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: exit_code is required" ]]
}

@test "failure_store_info handles missing artifacts directory gracefully" {
    # Override to return non-existent directory
    artifacts_get_base_dir() {
        echo "/nonexistent/path"
    }

    # Should succeed without error (graceful handling)
    run failure_store_info "curb-test" 1 "Test error" "stop"
    [[ $status -eq 0 ]]
}

@test "failure_store_info handles missing task directory gracefully" {
    # Don't create task directory

    # Should succeed without error (graceful handling)
    run failure_store_info "curb-nonexistent" 1 "Test error" "stop"
    [[ $status -eq 0 ]]
}

@test "failure_store_info uses default mode 'unknown' when not specified" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call store_info without mode parameter
    failure_store_info "curb-test" 1 "Test error"

    # Check mode defaults to 'unknown'
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    [[ "$mode" == "unknown" ]]
}

@test "failure_store_info timestamp is in ISO 8601 format" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call store_info
    failure_store_info "curb-test" 1 "Test error" "stop"

    # Verify timestamp format (YYYY-MM-DDTHH:MM:SSZ)
    local timestamp
    timestamp=$(jq -r '.timestamp' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    [[ "$timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

# ============================================================================
# Integration tests
# ============================================================================

@test "stop mode creates failure.json with exit code 2" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call handle_stop
    run failure_handle_stop "curb-test" 1 "Task failed"

    # Verify exit code 2 (halt signal)
    [[ $status -eq 2 ]]

    # Verify failure.json was created
    [[ -f "${TEST_ARTIFACTS_DIR}/curb-test/failure.json" ]]

    # Verify correct mode
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    [[ "$mode" == "stop" ]]
}

@test "move-on mode creates failure.json with exit code 0" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call handle_move_on
    run failure_handle_move_on "curb-test" 1 "Task failed"

    # Verify exit code 0 (continue signal)
    [[ $status -eq 0 ]]

    # Verify failure.json was created
    [[ -f "${TEST_ARTIFACTS_DIR}/curb-test/failure.json" ]]

    # Verify correct mode
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    [[ "$mode" == "move-on" ]]
}

@test "failure info includes task exit code correctly" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call with exit code 127
    failure_handle_stop "curb-test" 127 "Command not found" 2>/dev/null || true

    # Verify exit code stored correctly
    local stored_exit_code
    stored_exit_code=$(jq -r '.exit_code' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    [[ "$stored_exit_code" == "127" ]]
}

@test "failure info includes output message" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"

    # Call with specific error message
    failure_handle_move_on "curb-test" 1 "Build failed: missing dependency foo" 2>/dev/null

    # Verify output message stored correctly
    local stored_output
    stored_output=$(jq -r '.output' "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    [[ "$stored_output" == "Build failed: missing dependency foo" ]]
}

# ============================================================================
# Acceptance criteria tests
# ============================================================================

@test "AC: Stop mode halts run immediately (returns exit code 2)" {
    run failure_handle_stop "curb-test" 1 "Error"
    [[ $status -eq 2 ]]
}

@test "AC: Move-on mode marks task failed and continues (returns exit code 0)" {
    run failure_handle_move_on "curb-test" 1 "Error"
    [[ $status -eq 0 ]]
}

@test "AC: Failure info stored for retrieval" {
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"
    failure_handle_stop "curb-test" 1 "Error" 2>/dev/null || true
    [[ -f "${TEST_ARTIFACTS_DIR}/curb-test/failure.json" ]]
}

@test "AC: Task artifacts updated with failure details" {
    mkdir -p "${TEST_ARTIFACTS_DIR}/curb-test"
    failure_store_info "curb-test" 1 "Test error" "stop"

    # Verify all failure details are present
    local failure_json
    failure_json=$(cat "${TEST_ARTIFACTS_DIR}/curb-test/failure.json")
    [[ "$failure_json" =~ "curb-test" ]]
    [[ "$failure_json" =~ "\"exit_code\":1" ]]
    [[ "$failure_json" =~ "Test error" ]]
    [[ "$failure_json" =~ "stop" ]]
}

@test "AC: Exit codes distinguish stop vs continue" {
    # Stop returns 2
    run failure_handle_stop "curb-test" 1 "Error"
    local stop_exit=$status

    # Move-on returns 0
    run failure_handle_move_on "curb-test" 1 "Error"
    local continue_exit=$status

    # They should be different
    [[ $stop_exit -eq 2 ]]
    [[ $continue_exit -eq 0 ]]
    [[ $stop_exit -ne $continue_exit ]]
}
