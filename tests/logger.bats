#!/usr/bin/env bats

# Test suite for lib/logger.sh

# Load the test helper
load test_helper

# Setup function runs before each test
setup() {
    # Source the logger library
    source "${PROJECT_ROOT}/lib/logger.sh"

    # Create temp directory for test logs
    TEST_LOGS_DIR="${BATS_TMPDIR}/logs_test_$$"
    mkdir -p "$TEST_LOGS_DIR"

    # Override curb_logs_dir to use test directory
    curb_logs_dir() {
        echo "$TEST_LOGS_DIR"
    }

    # Clear logger state before each test
    logger_clear
}

# Teardown function runs after each test
teardown() {
    # Clean up test directories
    rm -rf "$TEST_LOGS_DIR" 2>/dev/null || true
}

# ============================================================================
# logger_init tests
# ============================================================================

@test "logger_init creates log directory structure" {
    logger_init "testproject" "session123"

    # Verify project directory was created
    [[ -d "${TEST_LOGS_DIR}/testproject" ]]
}

@test "logger_init creates log file" {
    logger_init "testproject" "session123"

    # Verify log file was created
    [[ -f "${TEST_LOGS_DIR}/testproject/session123.jsonl" ]]
}

@test "logger_init sets _LOG_FILE variable" {
    logger_init "testproject" "session123"

    local log_file
    log_file=$(logger_get_file)

    [[ "$log_file" == "${TEST_LOGS_DIR}/testproject/session123.jsonl" ]]
}

@test "logger_init fails without project_name" {
    run logger_init "" "session123"

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: project_name is required" ]]
}

@test "logger_init fails without session_id" {
    run logger_init "testproject" ""

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: session_id is required" ]]
}

@test "logger_init creates nested project directories" {
    logger_init "nested/project/path" "session123"

    # Verify nested directory was created
    [[ -d "${TEST_LOGS_DIR}/nested/project/path" ]]
    [[ -f "${TEST_LOGS_DIR}/nested/project/path/session123.jsonl" ]]
}

# ============================================================================
# logger_write tests
# ============================================================================

@test "logger_write fails if logger not initialized" {
    run logger_write "test_event" '{}'

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: Logger not initialized" ]]
}

@test "logger_write fails without event_type" {
    logger_init "testproject" "session123"

    run logger_write "" '{}'

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: event_type is required" ]]
}

@test "logger_write creates valid JSON line" {
    logger_init "testproject" "session123"
    logger_write "test_event" '{"key": "value"}'

    local log_file
    log_file=$(logger_get_file)

    # Verify file has content
    [[ -s "$log_file" ]]

    # Verify it's valid JSON
    run jq -e '.' "$log_file"
    [[ "$status" -eq 0 ]]
}

@test "logger_write includes timestamp in ISO 8601 format" {
    logger_init "testproject" "session123"
    logger_write "test_event" '{"key": "value"}'

    local log_file
    log_file=$(logger_get_file)

    # Extract timestamp and verify format (YYYY-MM-DDTHH:MM:SSZ)
    local timestamp
    timestamp=$(jq -r '.timestamp' "$log_file")

    # Check ISO 8601 format with regex
    [[ "$timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "logger_write includes event_type field" {
    logger_init "testproject" "session123"
    logger_write "task_start" '{"task_id": "123"}'

    local log_file
    log_file=$(logger_get_file)

    # Extract event_type
    local event_type
    event_type=$(jq -r '.event_type' "$log_file")

    [[ "$event_type" == "task_start" ]]
}

@test "logger_write includes data field" {
    logger_init "testproject" "session123"
    logger_write "test_event" '{"key": "value", "number": 42}'

    local log_file
    log_file=$(logger_get_file)

    # Extract and verify data
    local key
    local number
    key=$(jq -r '.data.key' "$log_file")
    number=$(jq -r '.data.number' "$log_file")

    [[ "$key" == "value" ]]
    [[ "$number" == "42" ]]
}

@test "logger_write handles empty data (defaults to {})" {
    logger_init "testproject" "session123"
    logger_write "test_event"

    local log_file
    log_file=$(logger_get_file)

    # Verify data is empty object
    local data
    data=$(jq -c '.data' "$log_file")

    [[ "$data" == "{}" ]]
}

@test "logger_write appends multiple entries" {
    logger_init "testproject" "session123"

    logger_write "event1" '{"msg": "first"}'
    logger_write "event2" '{"msg": "second"}'
    logger_write "event3" '{"msg": "third"}'

    local log_file
    log_file=$(logger_get_file)

    # Count lines (should be 3)
    local line_count
    line_count=$(wc -l < "$log_file" | tr -d ' ')

    [[ "$line_count" == "3" ]]
}

@test "logger_write preserves existing log entries" {
    logger_init "testproject" "session123"

    logger_write "event1" '{"msg": "first"}'
    logger_write "event2" '{"msg": "second"}'

    local log_file
    log_file=$(logger_get_file)

    # Verify both entries exist
    local event1_msg
    local event2_msg
    event1_msg=$(sed -n '1p' "$log_file" | jq -r '.data.msg')
    event2_msg=$(sed -n '2p' "$log_file" | jq -r '.data.msg')

    [[ "$event1_msg" == "first" ]]
    [[ "$event2_msg" == "second" ]]
}

@test "logger_write handles complex nested JSON data" {
    logger_init "testproject" "session123"

    logger_write "complex_event" '{
        "nested": {
            "array": [1, 2, 3],
            "object": {"key": "value"}
        },
        "string": "test"
    }'

    local log_file
    log_file=$(logger_get_file)

    # Verify nested structure is preserved
    local array_val
    local obj_val
    array_val=$(jq -c '.data.nested.array' "$log_file")
    obj_val=$(jq -r '.data.nested.object.key' "$log_file")

    [[ "$array_val" == "[1,2,3]" ]]
    [[ "$obj_val" == "value" ]]
}

# ============================================================================
# logger_get_file tests
# ============================================================================

@test "logger_get_file returns empty string when not initialized" {
    local log_file
    log_file=$(logger_get_file)

    [[ -z "$log_file" ]]
}

@test "logger_get_file returns correct path after init" {
    logger_init "testproject" "session123"

    local log_file
    log_file=$(logger_get_file)

    [[ "$log_file" == "${TEST_LOGS_DIR}/testproject/session123.jsonl" ]]
}

# ============================================================================
# logger_clear tests
# ============================================================================

@test "logger_clear resets logger state" {
    logger_init "testproject" "session123"

    # Verify it's initialized
    local log_file_before
    log_file_before=$(logger_get_file)
    [[ -n "$log_file_before" ]]

    # Clear and verify
    logger_clear

    local log_file_after
    log_file_after=$(logger_get_file)
    [[ -z "$log_file_after" ]]
}

# ============================================================================
# Integration tests
# ============================================================================

@test "full logger workflow: init, write multiple events, verify output" {
    logger_init "integration_test" "20260109-123456"

    # Write various event types
    logger_write "session_start" '{"user": "testuser"}'
    logger_write "task_start" '{"task_id": "curb-123", "name": "test task"}'
    logger_write "info" '{"message": "processing..."}'
    logger_write "task_complete" '{"task_id": "curb-123", "status": "success"}'
    logger_write "session_end" '{}'

    local log_file
    log_file=$(logger_get_file)

    # Verify file structure
    [[ -f "$log_file" ]]

    # Verify line count
    local line_count
    line_count=$(wc -l < "$log_file" | tr -d ' ')
    [[ "$line_count" == "5" ]]

    # Verify all lines are valid JSON
    while IFS= read -r line; do
        echo "$line" | jq -e '.' > /dev/null
    done < "$log_file"

    # Verify specific events
    local session_start_user
    local task_start_id
    session_start_user=$(sed -n '1p' "$log_file" | jq -r '.data.user')
    task_start_id=$(sed -n '2p' "$log_file" | jq -r '.data.task_id')

    [[ "$session_start_user" == "testuser" ]]
    [[ "$task_start_id" == "curb-123" ]]
}

@test "acceptance: log file created at correct XDG path" {
    # Note: In real usage, curb_logs_dir returns ~/.local/share/curb/logs
    # In tests, it returns our test directory
    logger_init "myproject" "mysession"

    local log_file
    log_file=$(logger_get_file)

    # Verify path structure
    [[ "$log_file" =~ /myproject/mysession\.jsonl$ ]]
}

@test "acceptance: each line is valid JSON" {
    logger_init "testproject" "session123"

    logger_write "event1" '{"test": 1}'
    logger_write "event2" '{"test": 2}'

    local log_file
    log_file=$(logger_get_file)

    # Validate each line individually
    while IFS= read -r line; do
        echo "$line" | jq -e '.' > /dev/null || exit 1
    done < "$log_file"
}

@test "acceptance: timestamps in ISO 8601 format" {
    logger_init "testproject" "session123"

    logger_write "test_event" '{}'

    local log_file
    log_file=$(logger_get_file)

    local timestamp
    timestamp=$(jq -r '.timestamp' "$log_file")

    # ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
    [[ "$timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "acceptance: log file is append-only" {
    logger_init "testproject" "session123"

    logger_write "event1" '{"msg": "first"}'
    logger_write "event2" '{"msg": "second"}'

    local log_file
    log_file=$(logger_get_file)

    # Verify first event is still present after second write
    local first_msg
    first_msg=$(sed -n '1p' "$log_file" | jq -r '.data.msg')

    [[ "$first_msg" == "first" ]]
}

# ============================================================================
# log_task_start tests
# ============================================================================

@test "log_task_start creates task_start event with all metadata" {
    logger_init "testproject" "session123"
    log_task_start "curb-123" "Test Task" "claude"

    local log_file
    log_file=$(logger_get_file)

    # Verify event type
    local event_type
    event_type=$(jq -r '.event_type' "$log_file")
    [[ "$event_type" == "task_start" ]]

    # Verify all metadata fields
    local task_id
    local task_title
    local harness
    task_id=$(jq -r '.data.task_id' "$log_file")
    task_title=$(jq -r '.data.task_title' "$log_file")
    harness=$(jq -r '.data.harness' "$log_file")

    [[ "$task_id" == "curb-123" ]]
    [[ "$task_title" == "Test Task" ]]
    [[ "$harness" == "claude" ]]
}

@test "log_task_start fails without task_id" {
    logger_init "testproject" "session123"

    run log_task_start "" "Test Task" "claude"

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: task_id is required" ]]
}

@test "log_task_start fails without task_title" {
    logger_init "testproject" "session123"

    run log_task_start "curb-123" "" "claude"

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: task_title is required" ]]
}

@test "log_task_start fails without harness" {
    logger_init "testproject" "session123"

    run log_task_start "curb-123" "Test Task" ""

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: harness is required" ]]
}

@test "log_task_start handles special characters in title" {
    logger_init "testproject" "session123"
    log_task_start "curb-123" "Task with \"quotes\" and 'apostrophes'" "claude"

    local log_file
    log_file=$(logger_get_file)

    local task_title
    task_title=$(jq -r '.data.task_title' "$log_file")

    [[ "$task_title" == "Task with \"quotes\" and 'apostrophes'" ]]
}

# ============================================================================
# log_task_end tests
# ============================================================================

@test "log_task_end creates task_end event with all metadata" {
    logger_init "testproject" "session123"
    log_task_end "curb-123" 0 42 1500

    local log_file
    log_file=$(logger_get_file)

    # Verify event type
    local event_type
    event_type=$(jq -r '.event_type' "$log_file")
    [[ "$event_type" == "task_end" ]]

    # Verify all metadata fields
    local task_id
    local exit_code
    local duration_sec
    local tokens_used
    local git_sha
    task_id=$(jq -r '.data.task_id' "$log_file")
    exit_code=$(jq -r '.data.exit_code' "$log_file")
    duration_sec=$(jq -r '.data.duration_sec' "$log_file")
    tokens_used=$(jq -r '.data.tokens_used' "$log_file")
    git_sha=$(jq -r '.data.git_sha' "$log_file")

    [[ "$task_id" == "curb-123" ]]
    [[ "$exit_code" == "0" ]]
    [[ "$duration_sec" == "42" ]]
    [[ "$tokens_used" == "1500" ]]
    [[ -n "$git_sha" ]]  # Should have some value
}

@test "log_task_end captures current git SHA" {
    logger_init "testproject" "session123"
    log_task_end "curb-123" 0 10 100

    local log_file
    log_file=$(logger_get_file)

    local git_sha
    git_sha=$(jq -r '.data.git_sha' "$log_file")

    # Should be a valid SHA (40 hex chars) or "unknown"
    [[ "$git_sha" =~ ^[0-9a-f]{40}$ ]] || [[ "$git_sha" == "unknown" ]]
}

@test "log_task_end defaults tokens_used to 0 when omitted" {
    logger_init "testproject" "session123"
    log_task_end "curb-123" 0 10

    local log_file
    log_file=$(logger_get_file)

    local tokens_used
    tokens_used=$(jq -r '.data.tokens_used' "$log_file")

    [[ "$tokens_used" == "0" ]]
}

@test "log_task_end fails without task_id" {
    logger_init "testproject" "session123"

    run log_task_end "" 0 10 100

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: task_id is required" ]]
}

@test "log_task_end fails without exit_code" {
    logger_init "testproject" "session123"

    run log_task_end "curb-123" "" 10 100

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: exit_code is required" ]]
}

@test "log_task_end fails without duration_sec" {
    logger_init "testproject" "session123"

    run log_task_end "curb-123" 0 "" 100

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: duration_sec is required" ]]
}

@test "log_task_end handles non-zero exit codes" {
    logger_init "testproject" "session123"
    log_task_end "curb-123" 1 30 500

    local log_file
    log_file=$(logger_get_file)

    local exit_code
    exit_code=$(jq -r '.data.exit_code' "$log_file")

    [[ "$exit_code" == "1" ]]
}

# ============================================================================
# log_error tests
# ============================================================================

@test "log_error creates error event with message" {
    logger_init "testproject" "session123"
    log_error "Something went wrong"

    local log_file
    log_file=$(logger_get_file)

    # Verify event type
    local event_type
    event_type=$(jq -r '.event_type' "$log_file")
    [[ "$event_type" == "error" ]]

    # Verify message
    local message
    message=$(jq -r '.data.message' "$log_file")
    [[ "$message" == "Something went wrong" ]]

    # Verify context defaults to empty object
    local context
    context=$(jq -c '.data.context' "$log_file")
    [[ "$context" == "{}" ]]
}

@test "log_error includes context when provided" {
    logger_init "testproject" "session123"
    log_error "Task failed" '{"task_id": "curb-123", "reason": "timeout"}'

    local log_file
    log_file=$(logger_get_file)

    # Verify message
    local message
    message=$(jq -r '.data.message' "$log_file")
    [[ "$message" == "Task failed" ]]

    # Verify context fields
    local task_id
    local reason
    task_id=$(jq -r '.data.context.task_id' "$log_file")
    reason=$(jq -r '.data.context.reason' "$log_file")

    [[ "$task_id" == "curb-123" ]]
    [[ "$reason" == "timeout" ]]
}

@test "log_error fails without message" {
    logger_init "testproject" "session123"

    run log_error ""

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: message is required" ]]
}

@test "log_error fails with invalid JSON context" {
    logger_init "testproject" "session123"

    run log_error "Test error" "not valid json"

    [[ "$status" -eq 1 ]]
    [[ "$output" =~ "ERROR: context is not valid JSON" ]]
}

@test "log_error handles complex context objects" {
    logger_init "testproject" "session123"
    log_error "Complex error" '{"level": "critical", "details": {"code": 500, "message": "Internal error"}}'

    local log_file
    log_file=$(logger_get_file)

    local level
    local code
    level=$(jq -r '.data.context.level' "$log_file")
    code=$(jq -r '.data.context.details.code' "$log_file")

    [[ "$level" == "critical" ]]
    [[ "$code" == "500" ]]
}

# ============================================================================
# Integration tests for task logging
# ============================================================================

@test "integration: full task lifecycle logging" {
    logger_init "testproject" "session123"

    # Log task start
    log_task_start "curb-456" "Integration Test Task" "claude"

    # Simulate some work (in real usage, would use $SECONDS)
    sleep 1

    # Log task end
    log_task_end "curb-456" 0 1 2500

    local log_file
    log_file=$(logger_get_file)

    # Verify we have 2 log entries
    local line_count
    line_count=$(wc -l < "$log_file" | tr -d ' ')
    [[ "$line_count" == "2" ]]

    # Verify first entry is task_start
    local start_event
    local start_task_id
    start_event=$(sed -n '1p' "$log_file" | jq -r '.event_type')
    start_task_id=$(sed -n '1p' "$log_file" | jq -r '.data.task_id')

    [[ "$start_event" == "task_start" ]]
    [[ "$start_task_id" == "curb-456" ]]

    # Verify second entry is task_end
    local end_event
    local end_task_id
    end_event=$(sed -n '2p' "$log_file" | jq -r '.event_type')
    end_task_id=$(sed -n '2p' "$log_file" | jq -r '.data.task_id')

    [[ "$end_event" == "task_end" ]]
    [[ "$end_task_id" == "curb-456" ]]
}

@test "integration: task with error logging" {
    logger_init "testproject" "session123"

    # Log task start
    log_task_start "curb-789" "Failing Task" "claude"

    # Log error
    log_error "Task encountered an error" '{"task_id": "curb-789", "phase": "execution"}'

    # Log task end with failure exit code
    log_task_end "curb-789" 1 5 100

    local log_file
    log_file=$(logger_get_file)

    # Verify we have 3 log entries
    local line_count
    line_count=$(wc -l < "$log_file" | tr -d ' ')
    [[ "$line_count" == "3" ]]

    # Verify error entry is in the middle
    local error_event
    local error_msg
    error_event=$(sed -n '2p' "$log_file" | jq -r '.event_type')
    error_msg=$(sed -n '2p' "$log_file" | jq -r '.data.message')

    [[ "$error_event" == "error" ]]
    [[ "$error_msg" == "Task encountered an error" ]]

    # Verify task_end has non-zero exit code
    local exit_code
    exit_code=$(sed -n '3p' "$log_file" | jq -r '.data.exit_code')
    [[ "$exit_code" == "1" ]]
}

# ============================================================================
# Acceptance criteria tests
# ============================================================================

@test "acceptance: task_start event logged with task_id, title, harness" {
    logger_init "testproject" "session123"
    log_task_start "curb-abc" "Acceptance Test" "opencode"

    local log_file
    log_file=$(logger_get_file)

    local event_type
    local task_id
    local task_title
    local harness
    event_type=$(jq -r '.event_type' "$log_file")
    task_id=$(jq -r '.data.task_id' "$log_file")
    task_title=$(jq -r '.data.task_title' "$log_file")
    harness=$(jq -r '.data.harness' "$log_file")

    [[ "$event_type" == "task_start" ]]
    [[ "$task_id" == "curb-abc" ]]
    [[ "$task_title" == "Acceptance Test" ]]
    [[ "$harness" == "opencode" ]]
}

@test "acceptance: task_end event logged with duration, exit_code, tokens, git_sha" {
    logger_init "testproject" "session123"
    log_task_end "curb-def" 0 123 4567

    local log_file
    log_file=$(logger_get_file)

    local event_type
    local task_id
    local exit_code
    local duration_sec
    local tokens_used
    local git_sha
    event_type=$(jq -r '.event_type' "$log_file")
    task_id=$(jq -r '.data.task_id' "$log_file")
    exit_code=$(jq -r '.data.exit_code' "$log_file")
    duration_sec=$(jq -r '.data.duration_sec' "$log_file")
    tokens_used=$(jq -r '.data.tokens_used' "$log_file")
    git_sha=$(jq -r '.data.git_sha' "$log_file")

    [[ "$event_type" == "task_end" ]]
    [[ "$task_id" == "curb-def" ]]
    [[ "$exit_code" == "0" ]]
    [[ "$duration_sec" == "123" ]]
    [[ "$tokens_used" == "4567" ]]
    [[ -n "$git_sha" ]]
    [[ "$git_sha" != "null" ]]
}

@test "acceptance: errors logged with context" {
    logger_init "testproject" "session123"
    log_error "Critical failure" '{"component": "harness", "details": "connection timeout"}'

    local log_file
    log_file=$(logger_get_file)

    local event_type
    local message
    local component
    local details
    event_type=$(jq -r '.event_type' "$log_file")
    message=$(jq -r '.data.message' "$log_file")
    component=$(jq -r '.data.context.component' "$log_file")
    details=$(jq -r '.data.context.details' "$log_file")

    [[ "$event_type" == "error" ]]
    [[ "$message" == "Critical failure" ]]
    [[ "$component" == "harness" ]]
    [[ "$details" == "connection timeout" ]]
}

# ============================================================================
# logger_redact tests
# ============================================================================

@test "logger_redact redacts api_key values" {
    local input='{"api_key": "sk_live_1234567890abcdef"}'
    local output
    output=$(logger_redact "$input")

    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ sk_live_1234567890abcdef ]]
}

@test "logger_redact redacts API_KEY (uppercase) values" {
    local input='{"API_KEY": "AKIAIOSFODNN7EXAMPLE"}'
    local output
    output=$(logger_redact "$input")

    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ AKIAIOSFODNN7EXAMPLE ]]
}

@test "logger_redact redacts token values" {
    local input='{"token": "ghp_1234567890abcdefghijklmnopqrstuv"}'
    local output
    output=$(logger_redact "$input")

    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ ghp_1234567890abcdefghijklmnopqrstuv ]]
}

@test "logger_redact redacts secret values" {
    local input='{"secret": "my-super-secret-value-123"}'
    local output
    output=$(logger_redact "$input")

    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ my-super-secret-value-123 ]]
}

@test "logger_redact redacts password values" {
    local input='{"password": "P@ssw0rd123!"}'
    local output
    output=$(logger_redact "$input")

    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ 'P@ssw0rd123!' ]]
}

@test "logger_redact redacts Bearer tokens" {
    local input='Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
    local output
    output=$(logger_redact "$input")

    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 ]]
}

@test "logger_redact redacts private_key values" {
    local input='{"private_key": "-----BEGIN-RSA-PRIVATE-KEY-----"}'
    local output
    output=$(logger_redact "$input")

    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ '-----BEGIN-RSA-PRIVATE-KEY-----' ]]
}

@test "logger_redact redacts access_token values" {
    local input='{"access_token": "ya29.a0AfH6SMBx..."}'
    local output
    output=$(logger_redact "$input")

    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ 'ya29.a0AfH6SMBx...' ]]
}

@test "logger_redact redacts client_secret values" {
    local input='{"client_secret": "GOCSPX-1234567890abcdef"}'
    local output
    output=$(logger_redact "$input")

    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ 'GOCSPX-1234567890abcdef' ]]
}

@test "logger_redact preserves key names for context" {
    local input='{"api_key": "secret123"}'
    local output
    output=$(logger_redact "$input")

    # Should preserve the key name
    [[ "$output" =~ api_key ]]
    # But redact the value
    [[ "$output" =~ \[REDACTED\] ]]
}

@test "logger_redact handles multiple secrets in one string" {
    local input='{"api_key": "key123", "token": "tok456", "password": "pass789"}'
    local output
    output=$(logger_redact "$input")

    # All secrets should be redacted
    [[ ! "$output" =~ key123 ]]
    [[ ! "$output" =~ tok456 ]]
    [[ ! "$output" =~ pass789 ]]

    # Should have multiple [REDACTED] markers
    local redacted_count
    redacted_count=$(echo "$output" | grep -o '\[REDACTED\]' | wc -l | tr -d ' ')
    [[ "$redacted_count" -ge 3 ]]
}

@test "logger_redact handles different separators (equals, colon, space)" {
    local input1='api_key=secret123'
    local input2='api_key:secret456'
    local input3='api_key secret789'

    local output1 output2 output3
    output1=$(logger_redact "$input1")
    output2=$(logger_redact "$input2")
    output3=$(logger_redact "$input3")

    [[ "$output1" =~ \[REDACTED\] ]]
    [[ "$output2" =~ \[REDACTED\] ]]
    [[ "$output3" =~ \[REDACTED\] ]]
}

@test "logger_redact does not redact common words" {
    # Should not redact "token" when it's not a key
    local input='This is a token message about secrets'
    local output
    output=$(logger_redact "$input")

    # The word "token" and "secrets" as regular words should remain
    [[ "$output" == "$input" ]]
}

@test "logger_redact returns original string if no secrets found" {
    local input='{"message": "Hello world", "count": 42}'
    local output
    output=$(logger_redact "$input")

    [[ "$output" == "$input" ]]
}

@test "logger_redact handles empty string" {
    local output
    output=$(logger_redact "")

    [[ -z "$output" ]]
}

@test "logger_write automatically redacts secrets" {
    logger_init "testproject" "session123"

    # Write log with secret
    logger_write "test_event" '{"api_key": "sk_live_1234567890", "message": "test"}'

    local log_file
    log_file=$(logger_get_file)

    # Read the logged data
    local logged_data
    logged_data=$(jq -c '.data' "$log_file")

    # Secret should be redacted
    [[ "$logged_data" =~ \[REDACTED\] ]]
    [[ ! "$logged_data" =~ sk_live_1234567890 ]]

    # Message should be preserved
    [[ "$logged_data" =~ test ]]
}

@test "logger_write redacts secrets in nested JSON" {
    logger_init "testproject" "session123"

    # Write log with nested secret
    logger_write "test_event" '{"config": {"api_key": "secret123"}, "status": "ok"}'

    local log_file
    log_file=$(logger_get_file)

    # Read the logged data
    local logged_data
    logged_data=$(jq -c '.data' "$log_file")

    # Secret should be redacted
    [[ "$logged_data" =~ \[REDACTED\] ]]
    [[ ! "$logged_data" =~ secret123 ]]
}

# ============================================================================
# Config integration tests for redaction
# ============================================================================

@test "logger_redact uses custom patterns from config" {
    # Source config.sh to make config_get available
    source "${PROJECT_ROOT}/lib/config.sh"

    # Create a test config with custom patterns
    local test_config="${BATS_TMPDIR}/test_config_$$"
    mkdir -p "$test_config"

    cat > "${test_config}/config.json" <<EOF
{
    "logger": {
        "secret_patterns": [
            "([Cc][Uu][Ss][Tt][Oo][Mm][_-]?[Kk][Ee][Yy][\"'= :])([^ \"'}\\],]+)"
        ]
    }
}
EOF

    # Override config dir for this test
    curb_config_dir() {
        echo "$test_config"
    }

    # Clear and reload config
    config_clear_cache
    config_load

    # Test redaction with custom pattern
    local input='{"custom_key": "should-be-redacted"}'
    local output
    output=$(logger_redact "$input")

    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ should-be-redacted ]]

    # Cleanup
    rm -rf "$test_config"
}

# ============================================================================
# Acceptance criteria tests for redaction
# ============================================================================

@test "acceptance: common secret patterns detected and redacted" {
    local patterns_to_test=(
        '{"api_key": "test123"}'
        '{"token": "test456"}'
        '{"secret": "test789"}'
        '{"password": "testpwd"}'
        'Bearer testbearer'
        '{"private_key": "testpk"}'
    )

    for pattern in "${patterns_to_test[@]}"; do
        local output
        output=$(logger_redact "$pattern")

        # Each should have [REDACTED]
        [[ "$output" =~ \[REDACTED\] ]]
    done
}

@test "acceptance: redaction replaces value with [REDACTED]" {
    local input='{"api_key": "sk_live_1234567890"}'
    local output
    output=$(logger_redact "$input")

    # Should contain [REDACTED]
    [[ "$output" =~ \[REDACTED\] ]]

    # Should NOT contain the original secret value
    [[ ! "$output" =~ sk_live_1234567890 ]]
}

@test "acceptance: logger_write applies redaction automatically" {
    logger_init "testproject" "session123"

    # Write multiple events with secrets
    logger_write "event1" '{"api_key": "secret1"}'
    logger_write "event2" '{"password": "secret2"}'
    logger_write "event3" '{"token": "secret3"}'

    local log_file
    log_file=$(logger_get_file)

    # None of the secrets should appear in the log file
    local log_contents
    log_contents=$(cat "$log_file")

    [[ ! "$log_contents" =~ secret1 ]]
    [[ ! "$log_contents" =~ secret2 ]]
    [[ ! "$log_contents" =~ secret3 ]]

    # Should have [REDACTED] markers
    [[ "$log_contents" =~ \[REDACTED\] ]]
}

@test "acceptance: no false positives on common words" {
    # Words like "token", "key", "secret" in normal text should not be redacted
    local input='{"message": "The token system handles secret keys properly"}'
    local output
    output=$(logger_redact "$input")

    # Should be unchanged (no redaction for words in normal text)
    [[ "$output" == "$input" ]]
}

@test "acceptance: no false positives on JSON field names" {
    # Field names containing words like "token" should not be redacted
    local input='{"tokens_used":100,"git_sha":"abc123","duration_sec":42}'
    local output
    output=$(logger_redact "$input")

    # Field names should be preserved
    [[ "$output" =~ "tokens_used" ]]
    [[ "$output" =~ "git_sha" ]]
    [[ "$output" =~ "duration_sec" ]]

    # Values should also be preserved (they're not secrets)
    [[ "$output" =~ "100" ]]
    [[ "$output" =~ "abc123" ]]
    [[ "$output" =~ "42" ]]
}

# ============================================================================
# logger_stream tests
# ============================================================================

@test "logger_stream outputs message with timestamp to stdout" {
    local output
    output=$(logger_stream "Test message")

    # Should have timestamp format [HH:MM:SS]
    [[ "$output" =~ ^\[[0-9]{2}:[0-9]{2}:[0-9]{2}\] ]]

    # Should contain the message
    [[ "$output" =~ Test\ message ]]
}

@test "logger_stream applies secret redaction" {
    local output
    output=$(logger_stream "api_key=sk_live_secret123")

    # Should have timestamp
    [[ "$output" =~ ^\[[0-9]{2}:[0-9]{2}:[0-9]{2}\] ]]

    # Secret should be redacted
    [[ "$output" =~ \[REDACTED\] ]]

    # Original secret should not appear
    [[ ! "$output" =~ sk_live_secret123 ]]
}

@test "logger_stream supports custom timestamp format" {
    local output
    output=$(logger_stream "Test" "%H:%M")

    # Should have custom timestamp format [HH:MM]
    [[ "$output" =~ ^\[[0-9]{2}:[0-9]{2}\] ]]
}

@test "logger_stream returns 0 on success" {
    logger_stream "Test message"
    [[ $? -eq 0 ]]
}

@test "logger_stream handles empty message gracefully" {
    logger_stream ""
    [[ $? -eq 0 ]]
}

@test "logger_stream outputs to stdout not stderr" {
    local stdout_output
    local stderr_output

    stdout_output=$(logger_stream "Test message" 2>/dev/null)
    stderr_output=$(logger_stream "Test message" 2>&1 >/dev/null)

    # Should have content in stdout
    [[ -n "$stdout_output" ]]

    # Should have no content in stderr
    [[ -z "$stderr_output" ]]
}

@test "logger_stream works with special characters" {
    local output
    output=$(logger_stream "Message with special chars: @#$%^&*()")

    # Should preserve special characters (but still apply redaction)
    [[ "$output" =~ \@\#\$%\^ ]]
}

@test "logger_stream multiple secrets redacted" {
    local output
    output=$(logger_stream "api_key=secret1 password=secret2 token=secret3")

    # All secrets should be redacted
    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ secret1 ]]
    [[ ! "$output" =~ secret2 ]]
    [[ ! "$output" =~ secret3 ]]
}

@test "logger_stream with Bearer token redaction" {
    local output
    output=$(logger_stream "Authorization: Bearer sk_live_secret_token_here")

    # Token should be redacted
    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ sk_live_secret_token_here ]]
}

# ============================================================================
# Acceptance criteria tests for logger_stream
# ============================================================================

@test "acceptance: logger_stream outputs with timestamp prefix" {
    local output
    output=$(logger_stream "Processing task...")

    # Must have [HH:MM:SS] format timestamp
    [[ "$output" =~ ^\[[0-9]{2}:[0-9]{2}:[0-9]{2}\] ]]
    [[ "$output" =~ Processing\ task ]]
}

@test "acceptance: logger_stream applies secret redaction before output" {
    local output
    output=$(logger_stream "Connecting with api_key=sk_live_abc123def456")

    # Message visible, secret redacted
    [[ "$output" =~ Connecting ]]
    [[ "$output" =~ \[REDACTED\] ]]
    [[ ! "$output" =~ sk_live_abc123def456 ]]
}

@test "acceptance: logger_stream outputs to stdout" {
    local output
    output=$(logger_stream "Test output" 2>/dev/null)

    # Should have output on stdout
    [[ -n "$output" ]]

    # Should contain both timestamp and message
    [[ "$output" =~ ^\[[0-9]{2}:[0-9]{2}:[0-9]{2}\] ]]
    [[ "$output" =~ Test\ output ]]
}

@test "acceptance: logger_stream timestamp format HH:MM:SS" {
    local output
    output=$(logger_stream "test")

    # Must match [HH:MM:SS] exactly (hours, minutes, seconds)
    [[ "$output" =~ ^\[[0-2][0-9]:[0-5][0-9]:[0-5][0-9]\] ]]
}
