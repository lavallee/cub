#!/usr/bin/env bats

# Test suite for lib/failure.sh

# Load the test helper
load test_helper

# Override functions at file level for bash 3.2 compatibility
artifacts_get_run_dir() {
    # Allow tests to override with MOCK_ARTIFACTS_DIR
    echo "${MOCK_ARTIFACTS_DIR:-${TEST_ARTIFACTS_DIR:-/tmp/artifacts_test}}"
}

cub_config_dir() {
    # Allow tests to override with MOCK_CONFIG_DIR
    echo "${MOCK_CONFIG_DIR:-${TEST_CONFIG_DIR:-/nonexistent}}"
}

# Setup function runs before each test
setup() {
    # Source the failure library
    source "${PROJECT_ROOT}/lib/failure.sh"

    # Create temp directory for test artifacts
    TEST_ARTIFACTS_DIR="${BATS_TMPDIR}/artifacts_test_$$"
    mkdir -p "$TEST_ARTIFACTS_DIR"

    # Create a mock task directory for failure storage tests
    TEST_TASK_DIR="${TEST_ARTIFACTS_DIR}/cub-test"
    mkdir -p "$TEST_TASK_DIR"

    # Redefine mock after sourcing failure.sh (which sources artifacts.sh)
    # This ensures our mock overrides the real function
    artifacts_get_run_dir() {
        echo "${MOCK_ARTIFACTS_DIR:-${TEST_ARTIFACTS_DIR:-/tmp/artifacts_test}}"
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
# failure_get_mode tests
# ============================================================================

@test "failure_get_mode returns default mode when not configured" {
    # TEST_CONFIG_DIR is unset, so cub_config_dir returns /nonexistent
    unset TEST_CONFIG_DIR

    # Should return default 'move-on'
    run failure_get_mode
    [[ $status -eq 0 ]]
    [[ "$output" == "move-on" ]]
}

@test "failure_get_mode returns configured mode from config" {
    # Create temp config directory
    TEST_CONFIG_DIR="${BATS_TMPDIR}/config_test_$$"
    mkdir -p "$TEST_CONFIG_DIR"

    # Create config with failure mode
    echo '{"failure": {"mode": "stop"}}' > "$TEST_CONFIG_DIR/config.json"

    # Clear cache to force reload
    source "${PROJECT_ROOT}/lib/config.sh"
    config_clear_cache

    # Should return configured mode
    run failure_get_mode
    [[ $status -eq 0 ]]
    [[ "$output" == "stop" ]]

    # Clean up
    rm -rf "$TEST_CONFIG_DIR"
}

@test "failure_get_mode returns stop mode" {
    # Set failure mode to stop
    failure_set_mode "stop"

    # Should return stop
    run failure_get_mode
    [[ $status -eq 0 ]]
    [[ "$output" == "stop" ]]
}

@test "failure_get_mode returns move-on mode" {
    # Set failure mode to move-on
    failure_set_mode "move-on"

    # Should return move-on
    run failure_get_mode
    [[ $status -eq 0 ]]
    [[ "$output" == "move-on" ]]
}

@test "failure_get_mode returns retry mode" {
    # Set failure mode to retry
    failure_set_mode "retry"

    # Should return retry
    run failure_get_mode
    [[ $status -eq 0 ]]
    [[ "$output" == "retry" ]]
}

@test "failure_get_mode returns triage mode" {
    # Set failure mode to triage
    failure_set_mode "triage"

    # Should return triage
    run failure_get_mode
    [[ $status -eq 0 ]]
    [[ "$output" == "triage" ]]
}

# ============================================================================
# failure_set_mode tests
# ============================================================================

@test "failure_set_mode sets stop mode" {
    # Don't use 'run' since it creates a subshell
    failure_set_mode "stop"
    local exit_code=$?
    [[ $exit_code -eq 0 ]]

    # Verify mode was set
    local mode
    mode=$(failure_get_mode)
    [[ "$mode" == "stop" ]]
}

@test "failure_set_mode sets move-on mode" {
    # Don't use 'run' since it creates a subshell
    failure_set_mode "move-on"
    local exit_code=$?
    [[ $exit_code -eq 0 ]]

    # Verify mode was set
    local mode
    mode=$(failure_get_mode)
    [[ "$mode" == "move-on" ]]
}

@test "failure_set_mode sets retry mode" {
    # Don't use 'run' since it creates a subshell
    failure_set_mode "retry"
    local exit_code=$?
    [[ $exit_code -eq 0 ]]

    # Verify mode was set
    local mode
    mode=$(failure_get_mode)
    [[ "$mode" == "retry" ]]
}

@test "failure_set_mode sets triage mode" {
    # Don't use 'run' since it creates a subshell
    failure_set_mode "triage"
    local exit_code=$?
    [[ $exit_code -eq 0 ]]

    # Verify mode was set
    local mode
    mode=$(failure_get_mode)
    [[ "$mode" == "triage" ]]
}

@test "failure_set_mode rejects invalid mode" {
    run failure_set_mode "invalid-mode"
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: invalid failure mode" ]]
}

@test "failure_set_mode requires mode parameter" {
    run failure_set_mode ""
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: mode is required" ]]
}

@test "failure_set_mode validates allowed modes" {
    # Test each allowed mode works
    failure_set_mode "stop"
    [[ $? -eq 0 ]]

    failure_set_mode "move-on"
    [[ $? -eq 0 ]]

    failure_set_mode "retry"
    [[ $? -eq 0 ]]

    failure_set_mode "triage"
    [[ $? -eq 0 ]]

    # Test invalid mode fails
    run failure_set_mode "not-a-mode"
    [[ $status -eq 1 ]]
}

# ============================================================================
# failure_handle_stop tests
# ============================================================================

@test "failure_handle_stop returns exit code 2 (halt signal)" {
    run failure_handle_stop "cub-test" 1 "Test error"

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
    run failure_handle_stop "cub-test" "" "Test error"

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: exit_code is required" ]]
}

@test "failure_handle_stop accepts optional output parameter" {
    run failure_handle_stop "cub-test" 1

    # Should return 2 even without output
    [[ $status -eq 2 ]]
}

@test "failure_handle_stop stores failure info" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call handle_stop
    failure_handle_stop "cub-test" 1 "Test error" 2>/dev/null || true

    # Check if failure.json was created
    [[ -f "${TEST_ARTIFACTS_DIR}/cub-test/failure.json" ]]
}

@test "failure_handle_stop stores correct failure mode in JSON" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call handle_stop
    failure_handle_stop "cub-test" 1 "Test error" 2>/dev/null || true

    # Check failure mode in JSON
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    [[ "$mode" == "stop" ]]
}

# ============================================================================
# failure_handle_move_on tests
# ============================================================================

@test "failure_handle_move_on returns exit code 0 (continue signal)" {
    run failure_handle_move_on "cub-test" 1 "Test error"

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
    run failure_handle_move_on "cub-test" "" "Test error"

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: exit_code is required" ]]
}

@test "failure_handle_move_on accepts optional output parameter" {
    run failure_handle_move_on "cub-test" 1

    # Should return 0 even without output
    [[ $status -eq 0 ]]
}

@test "failure_handle_move_on stores failure info" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call handle_move_on
    failure_handle_move_on "cub-test" 1 "Test error" 2>/dev/null

    # Check if failure.json was created
    [[ -f "${TEST_ARTIFACTS_DIR}/cub-test/failure.json" ]]
}

@test "failure_handle_move_on stores correct failure mode in JSON" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call handle_move_on
    failure_handle_move_on "cub-test" 1 "Test error" 2>/dev/null

    # Check failure mode in JSON
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    [[ "$mode" == "move-on" ]]
}

# ============================================================================
# failure_store_info tests
# ============================================================================

@test "failure_store_info creates failure.json in task directory" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call store_info
    failure_store_info "cub-test" 1 "Test error" "stop"

    # Check if failure.json exists
    [[ -f "${TEST_ARTIFACTS_DIR}/cub-test/failure.json" ]]
}

@test "failure_store_info stores all required fields in JSON" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call store_info
    failure_store_info "cub-test" 1 "Test error message" "stop"

    # Verify JSON structure
    local task_id exit_code output mode timestamp
    task_id=$(jq -r '.task_id' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    exit_code=$(jq -r '.exit_code' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    output=$(jq -r '.output' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    timestamp=$(jq -r '.timestamp' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")

    [[ "$task_id" == "cub-test" ]]
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
    run failure_store_info "cub-test" "" "Test error" "stop"

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: exit_code is required" ]]
}

@test "failure_store_info handles missing artifacts directory gracefully" {
    # Override to return non-existent directory via variable
    MOCK_ARTIFACTS_DIR="/nonexistent/path"

    # Should succeed without error (graceful handling)
    run failure_store_info "cub-test" 1 "Test error" "stop"
    [[ $status -eq 0 ]]
}

@test "failure_store_info handles missing task directory gracefully" {
    # Don't create task directory

    # Should succeed without error (graceful handling)
    run failure_store_info "cub-nonexistent" 1 "Test error" "stop"
    [[ $status -eq 0 ]]
}

@test "failure_store_info uses default mode 'unknown' when not specified" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call store_info without mode parameter
    failure_store_info "cub-test" 1 "Test error"

    # Check mode defaults to 'unknown'
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    [[ "$mode" == "unknown" ]]
}

@test "failure_store_info timestamp is in ISO 8601 format" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call store_info
    failure_store_info "cub-test" 1 "Test error" "stop"

    # Verify timestamp format (YYYY-MM-DDTHH:MM:SSZ)
    local timestamp
    timestamp=$(jq -r '.timestamp' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    [[ "$timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

# ============================================================================
# Integration tests
# ============================================================================

@test "stop mode creates failure.json with exit code 2" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call handle_stop
    run failure_handle_stop "cub-test" 1 "Task failed"

    # Verify exit code 2 (halt signal)
    [[ $status -eq 2 ]]

    # Verify failure.json was created
    [[ -f "${TEST_ARTIFACTS_DIR}/cub-test/failure.json" ]]

    # Verify correct mode
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    [[ "$mode" == "stop" ]]
}

@test "move-on mode creates failure.json with exit code 0" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call handle_move_on
    run failure_handle_move_on "cub-test" 1 "Task failed"

    # Verify exit code 0 (continue signal)
    [[ $status -eq 0 ]]

    # Verify failure.json was created
    [[ -f "${TEST_ARTIFACTS_DIR}/cub-test/failure.json" ]]

    # Verify correct mode
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    [[ "$mode" == "move-on" ]]
}

@test "failure info includes task exit code correctly" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call with exit code 127
    failure_handle_stop "cub-test" 127 "Command not found" 2>/dev/null || true

    # Verify exit code stored correctly
    local stored_exit_code
    stored_exit_code=$(jq -r '.exit_code' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    [[ "$stored_exit_code" == "127" ]]
}

@test "failure info includes output message" {
    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"

    # Call with specific error message
    failure_handle_move_on "cub-test" 1 "Build failed: missing dependency foo" 2>/dev/null

    # Verify output message stored correctly
    local stored_output
    stored_output=$(jq -r '.output' "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    [[ "$stored_output" == "Build failed: missing dependency foo" ]]
}

# ============================================================================
# Acceptance criteria tests
# ============================================================================

@test "AC: Stop mode halts run immediately (returns exit code 2)" {
    run failure_handle_stop "cub-test" 1 "Error"
    [[ $status -eq 2 ]]
}

@test "AC: Move-on mode marks task failed and continues (returns exit code 0)" {
    run failure_handle_move_on "cub-test" 1 "Error"
    [[ $status -eq 0 ]]
}

@test "AC: Failure info stored for retrieval" {
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"
    failure_handle_stop "cub-test" 1 "Error" 2>/dev/null || true
    [[ -f "${TEST_ARTIFACTS_DIR}/cub-test/failure.json" ]]
}

@test "AC: Task artifacts updated with failure details" {
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-test"
    failure_store_info "cub-test" 1 "Test error" "stop"

    # Verify all failure details are present
    local failure_json
    failure_json=$(cat "${TEST_ARTIFACTS_DIR}/cub-test/failure.json")
    [[ "$failure_json" =~ "cub-test" ]]
    [[ "$failure_json" =~ "\"exit_code\":1" ]]
    [[ "$failure_json" =~ "Test error" ]]
    [[ "$failure_json" =~ "stop" ]]
}

@test "AC: Exit codes distinguish stop vs continue" {
    # Stop returns 2
    run failure_handle_stop "cub-test" 1 "Error"
    local stop_exit=$status

    # Move-on returns 0
    run failure_handle_move_on "cub-test" 1 "Error"
    local continue_exit=$status

    # They should be different
    [[ $stop_exit -eq 2 ]]
    [[ $continue_exit -eq 0 ]]
    [[ $stop_exit -ne $continue_exit ]]
}

# ============================================================================
# failure_handle_retry tests
# ============================================================================

@test "failure_handle_retry returns exit code 3 (retry signal) when under limit" {
    # Source budget to initialize
    source "${PROJECT_ROOT}/lib/budget.sh"
    budget_set_max_task_iterations 3

    # First retry should return 3
    run failure_handle_retry "cub-retry-test" 1 "Test error"

    # Should return 3 to signal retry
    [[ $status -eq 3 ]]
}

@test "failure_handle_retry increments task iteration counter" {
    # Source budget to initialize
    source "${PROJECT_ROOT}/lib/budget.sh"
    budget_set_max_task_iterations 3

    # Get initial count
    local initial_count
    initial_count=$(budget_get_task_iterations "cub-retry-test")

    # Call retry
    failure_handle_retry "cub-retry-test" 1 "Test error" 2>/dev/null || true

    # Check count was incremented
    local new_count
    new_count=$(budget_get_task_iterations "cub-retry-test")
    [[ $new_count -eq $((initial_count + 1)) ]]
}

@test "failure_handle_retry falls back to move-on when limit exceeded" {
    # Source budget to initialize (default max is 3)
    source "${PROJECT_ROOT}/lib/budget.sh"

    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-retry-limit"

    # Exhaust retry limit (3 retries with default max=3)
    failure_handle_retry "cub-retry-limit" 1 "Error 1" 2>/dev/null || true
    failure_handle_retry "cub-retry-limit" 1 "Error 2" 2>/dev/null || true
    failure_handle_retry "cub-retry-limit" 1 "Error 3" 2>/dev/null || true

    # Next retry should fall back to move-on (current=3, 3 < 3 is false, return 0)
    failure_handle_retry "cub-retry-limit" 1 "Error 4" 2>/dev/null
    local exit_code=$?

    [[ $exit_code -eq 0 ]]
}

@test "failure_handle_retry requires task_id parameter" {
    run failure_handle_retry "" 1 "Test error"

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: task_id is required" ]]
}

@test "failure_handle_retry requires exit_code parameter" {
    run failure_handle_retry "cub-retry-test" "" "Test error"

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: exit_code is required" ]]
}

@test "failure_handle_retry accepts optional output parameter" {
    # Source budget to initialize
    source "${PROJECT_ROOT}/lib/budget.sh"
    budget_set_max_task_iterations 3

    run failure_handle_retry "cub-retry-test" 1

    # Should return 3 even without output
    [[ $status -eq 3 ]]
}

@test "failure_handle_retry stores failure info with retry mode" {
    # Source budget to initialize
    source "${PROJECT_ROOT}/lib/budget.sh"
    budget_set_max_task_iterations 3

    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-retry-test"

    # Call retry
    failure_handle_retry "cub-retry-test" 1 "Test error" 2>/dev/null || true

    # Check if failure.json was created with retry mode
    [[ -f "${TEST_ARTIFACTS_DIR}/cub-retry-test/failure.json" ]]
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/cub-retry-test/failure.json")
    [[ "$mode" == "retry" ]]
}

@test "failure_handle_retry stores retry-limit-exceeded mode when limit hit" {
    # Source budget to initialize (default max is 3)
    source "${PROJECT_ROOT}/lib/budget.sh"

    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-retry-limit2"

    # Exhaust limit (3 retries)
    failure_handle_retry "cub-retry-limit2" 1 "Error 1" 2>/dev/null || true
    failure_handle_retry "cub-retry-limit2" 1 "Error 2" 2>/dev/null || true
    failure_handle_retry "cub-retry-limit2" 1 "Error 3" 2>/dev/null || true

    # Next call should store retry-limit-exceeded
    failure_handle_retry "cub-retry-limit2" 1 "Error 4" 2>/dev/null

    # Check mode
    local mode
    mode=$(jq -r '.mode' "${TEST_ARTIFACTS_DIR}/cub-retry-limit2/failure.json")
    [[ "$mode" == "retry-limit-exceeded" ]]
}

# ============================================================================
# failure_get_context tests
# ============================================================================

@test "failure_get_context returns formatted context with output" {
    # Create task directory and failure.json
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-context-test"
    echo '{"task_id":"cub-context-test","exit_code":1,"output":"Build failed: missing dependency","mode":"retry"}' \
        > "${TEST_ARTIFACTS_DIR}/cub-context-test/failure.json"

    # Get context
    run failure_get_context "cub-context-test"

    # Should format correctly
    [[ $status -eq 0 ]]
    [[ "$output" == "Previous attempt failed with exit code 1: Build failed: missing dependency. Please try a different approach." ]]
}

@test "failure_get_context returns formatted context without output" {
    # Create task directory and failure.json without output
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-context-test"
    echo '{"task_id":"cub-context-test","exit_code":127,"output":null,"mode":"retry"}' \
        > "${TEST_ARTIFACTS_DIR}/cub-context-test/failure.json"

    # Get context
    run failure_get_context "cub-context-test"

    # Should format correctly
    [[ $status -eq 0 ]]
    [[ "$output" == "Previous attempt failed with exit code 127. Please try a different approach." ]]
}

@test "failure_get_context requires task_id parameter" {
    run failure_get_context ""

    # Should fail with exit code 1
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: task_id is required" ]]
}

@test "failure_get_context handles missing artifacts directory gracefully" {
    # Override to return non-existent directory via variable
    MOCK_ARTIFACTS_DIR="/nonexistent/path"

    # Should succeed without error (graceful handling)
    run failure_get_context "cub-nonexistent"
    [[ $status -eq 0 ]]
    [[ -z "$output" ]]
}

@test "failure_get_context handles missing task directory gracefully" {
    # Don't create task directory

    # Should succeed without error (graceful handling)
    run failure_get_context "cub-nonexistent"
    [[ $status -eq 0 ]]
    [[ -z "$output" ]]
}

@test "failure_get_context handles missing failure.json gracefully" {
    # Create task directory but no failure.json
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-no-failure"

    # Should succeed without error (graceful handling)
    run failure_get_context "cub-no-failure"
    [[ $status -eq 0 ]]
    [[ -z "$output" ]]
}

@test "failure_get_context handles empty output correctly" {
    # Create task directory with empty output
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-empty-output"
    echo '{"task_id":"cub-empty-output","exit_code":1,"output":"","mode":"retry"}' \
        > "${TEST_ARTIFACTS_DIR}/cub-empty-output/failure.json"

    # Get context
    run failure_get_context "cub-empty-output"

    # Should use format without output
    [[ $status -eq 0 ]]
    [[ "$output" == "Previous attempt failed with exit code 1. Please try a different approach." ]]
}

# ============================================================================
# Retry mode acceptance criteria tests
# ============================================================================

@test "AC: Retry increments task iteration counter" {
    # Source budget
    source "${PROJECT_ROOT}/lib/budget.sh"
    budget_set_max_task_iterations 3

    local before
    before=$(budget_get_task_iterations "cub-ac-retry")

    failure_handle_retry "cub-ac-retry" 1 "Error" 2>/dev/null || true

    local after
    after=$(budget_get_task_iterations "cub-ac-retry")

    [[ $after -eq $((before + 1)) ]]
}


@test "AC: Failure context available for prompt augmentation" {
    # Create failure info
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-ac-context"
    echo '{"task_id":"cub-ac-context","exit_code":1,"output":"Test failed","mode":"retry"}' \
        > "${TEST_ARTIFACTS_DIR}/cub-ac-context/failure.json"

    # Get context
    run failure_get_context "cub-ac-context"

    # Should return formatted context
    [[ $status -eq 0 ]]
    [[ "$output" =~ "Previous attempt failed" ]]
    [[ "$output" =~ "Test failed" ]]
    [[ "$output" =~ "Please try a different approach" ]]
}

@test "AC: Falls back to move-on when limit exceeded" {
    # Source budget (default max is 3)
    source "${PROJECT_ROOT}/lib/budget.sh"

    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-ac-fallback"

    # Exhaust limit (3 retries)
    failure_handle_retry "cub-ac-fallback" 1 "Error 1" 2>/dev/null || true
    failure_handle_retry "cub-ac-fallback" 1 "Error 2" 2>/dev/null || true
    failure_handle_retry "cub-ac-fallback" 1 "Error 3" 2>/dev/null || true

    # Should fall back to move-on (return 0)
    failure_handle_retry "cub-ac-fallback" 1 "Error 4" 2>/dev/null
    local exit_code=$?
    [[ $exit_code -eq 0 ]]
}

@test "AC: Context format helpful for agent" {
    # Create failure with specific error
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-ac-helpful"
    echo '{"task_id":"cub-ac-helpful","exit_code":1,"output":"TypeError: undefined is not a function","mode":"retry"}' \
        > "${TEST_ARTIFACTS_DIR}/cub-ac-helpful/failure.json"

    # Get context
    run failure_get_context "cub-ac-helpful"

    # Should include key error info
    [[ "$output" =~ "TypeError: undefined is not a function" ]]
    # Should be concise (less than 200 chars for this example)
    [[ ${#output} -lt 200 ]]
    # Should give actionable guidance
    [[ "$output" =~ "different approach" ]]
}

# ============================================================================
# AI Lesson Extraction Integration Tests
# ============================================================================

@test "failure_handle_retry calls AI lesson extraction when limit exceeded" {
    skip "Integration test - requires working guardrails module"
    # Note: This test is skipped because it requires complex test setup
    # The functionality is tested indirectly through unit tests of individual components
}

@test "failure_handle_retry skips AI lesson extraction when task_title missing" {
    skip "Integration test - requires working guardrails module"
    # Note: This test is skipped because it requires complex test setup
    # The functionality is tested indirectly through unit tests of individual components
}

@test "failure_handle_retry accepts task_title parameter" {
    # Source budget
    source "${PROJECT_ROOT}/lib/budget.sh"
    budget_set_max_task_iterations 3

    # Create task directory
    mkdir -p "${TEST_ARTIFACTS_DIR}/cub-with-title"

    # Call with task_title parameter (should not fail)
    run failure_handle_retry "cub-with-title" 1 "Error message" "Task Title Here"

    # Should succeed (retry mode, return 3)
    [[ $status -eq 3 ]]
}
