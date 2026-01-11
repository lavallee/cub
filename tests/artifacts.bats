#!/usr/bin/env bats
#
# Tests for lib/artifacts.sh
#

load test_helper

setup() {
    setup_test_dir
    source "$LIB_DIR/artifacts.sh"
}

teardown() {
    teardown_test_dir
}

@test "artifacts_get_run_dir: fails when session not initialized" {
    run artifacts_get_run_dir
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Session not initialized" ]]
}

@test "artifacts_get_run_dir: returns correct path format" {
    session_init --name "test-session"
    run artifacts_get_run_dir
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^\.curb/runs/test-session-[0-9]{8}-[0-9]{6}$ ]]
}

@test "artifacts_get_task_dir: fails without task_id" {
    session_init --name "test-session"
    run artifacts_get_task_dir ""
    [ "$status" -eq 1 ]
    [[ "$output" =~ "task_id is required" ]]
}

@test "artifacts_get_task_dir: returns correct path format" {
    session_init --name "test-session"
    run artifacts_get_task_dir "test-001"
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^\.curb/runs/test-session-.*/tasks/test-001$ ]]
}

@test "artifacts_ensure_dirs: fails without task_id" {
    session_init --name "test-session"
    run artifacts_ensure_dirs ""
    [ "$status" -eq 1 ]
    [[ "$output" =~ "task_id is required" ]]
}

@test "artifacts_ensure_dirs: creates task directory" {
    session_init --name "test-session"
    run artifacts_ensure_dirs "test-001"
    [ "$status" -eq 0 ]

    local task_dir
    task_dir=$(artifacts_get_task_dir "test-001")
    [ -d "$task_dir" ]
}

@test "artifacts_ensure_dirs: creates directory with 700 permissions" {
    session_init --name "test-session"
    artifacts_ensure_dirs "test-001"

    local task_dir
    task_dir=$(artifacts_get_task_dir "test-001")

    # Check directory permissions (should be 700)
    assert_permissions "$task_dir" "700"
}

@test "artifacts_init_run: fails when session not initialized" {
    run artifacts_init_run
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Session not initialized" ]]
}

@test "artifacts_init_run: creates run directory" {
    session_init --name "test-session"
    run artifacts_init_run
    [ "$status" -eq 0 ]

    local run_dir=".curb/runs/test-session-"*
    [ -d $run_dir ]
}

@test "artifacts_init_run: creates run.json with correct schema" {
    session_init --name "test-session"
    artifacts_init_run

    local run_dir
    run_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)
    local run_json="${run_dir}/run.json"

    [ -f "$run_json" ]

    # Validate JSON is parseable
    run jq empty "$run_json"
    [ "$status" -eq 0 ]

    # Check required fields exist
    run jq -r '.run_id' "$run_json"
    [ "$status" -eq 0 ]
    [[ "$output" =~ "test-session-" ]]

    run jq -r '.session_name' "$run_json"
    [ "$status" -eq 0 ]
    [ "$output" = "test-session" ]

    run jq -r '.started_at' "$run_json"
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]

    run jq -r '.status' "$run_json"
    [ "$status" -eq 0 ]
    [ "$output" = "in_progress" ]

    run jq -r '.config' "$run_json"
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^\{.*\}$ ]]
}

@test "artifacts_init_run: timestamps are ISO 8601 format" {
    session_init --name "test-session"
    artifacts_init_run

    local run_dir
    run_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)
    local run_json="${run_dir}/run.json"

    local timestamp
    timestamp=$(jq -r '.started_at' "$run_json")

    # Verify ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
    [[ "$timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "artifacts_start_task: fails without task_id" {
    session_init --name "test-session"
    artifacts_init_run

    run artifacts_start_task "" "Task title"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "task_id is required" ]]
}

@test "artifacts_start_task: fails without task_title" {
    session_init --name "test-session"
    artifacts_init_run

    run artifacts_start_task "test-001" ""
    [ "$status" -eq 1 ]
    [[ "$output" =~ "task_title is required" ]]
}

@test "artifacts_start_task: creates task directory" {
    session_init --name "test-session"
    artifacts_init_run

    run artifacts_start_task "test-001" "Test task"
    [ "$status" -eq 0 ]

    local task_dir=".curb/runs/test-session-"*/tasks/test-001
    [ -d $task_dir ]
}

@test "artifacts_start_task: creates task.json with correct schema" {
    session_init --name "test-session"
    artifacts_init_run
    artifacts_start_task "test-001" "Test task" "high"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local task_json="${task_dir}/task.json"

    [ -f "$task_json" ]

    # Validate JSON is parseable
    run jq empty "$task_json"
    [ "$status" -eq 0 ]

    # Check required fields
    run jq -r '.task_id' "$task_json"
    [ "$status" -eq 0 ]
    [ "$output" = "test-001" ]

    run jq -r '.title' "$task_json"
    [ "$status" -eq 0 ]
    [ "$output" = "Test task" ]

    run jq -r '.priority' "$task_json"
    [ "$status" -eq 0 ]
    [ "$output" = "high" ]

    run jq -r '.status' "$task_json"
    [ "$status" -eq 0 ]
    [ "$output" = "in_progress" ]

    run jq -r '.started_at' "$task_json"
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]

    run jq -r '.iterations' "$task_json"
    [ "$status" -eq 0 ]
    [ "$output" = "0" ]
}

@test "artifacts_start_task: defaults priority to 'normal'" {
    session_init --name "test-session"
    artifacts_init_run
    artifacts_start_task "test-001" "Test task"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local task_json="${task_dir}/task.json"

    run jq -r '.priority' "$task_json"
    [ "$status" -eq 0 ]
    [ "$output" = "normal" ]
}

@test "artifacts_start_task: timestamps are ISO 8601 format" {
    session_init --name "test-session"
    artifacts_init_run
    artifacts_start_task "test-001" "Test task"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local task_json="${task_dir}/task.json"

    local timestamp
    timestamp=$(jq -r '.started_at' "$task_json")

    # Verify ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
    [[ "$timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "artifacts_start_task: works without artifacts_init_run" {
    session_init --name "test-session"

    # Should still work because ensure_dirs creates the structure
    run artifacts_start_task "test-001" "Test task"
    [ "$status" -eq 0 ]

    local task_dir=".curb/runs/test-session-"*/tasks/test-001
    [ -d $task_dir ]
}

@test "artifacts integration: run and task creation" {
    session_init --name "integration-test"
    artifacts_init_run
    artifacts_start_task "test-001" "First task" "high"
    artifacts_start_task "test-002" "Second task" "low"

    # Verify run.json exists
    local run_dir
    run_dir=$(find .curb/runs -type d -name "integration-test-*" | head -1)
    [ -f "${run_dir}/run.json" ]

    # Verify both task directories exist
    [ -d "${run_dir}/tasks/test-001" ]
    [ -d "${run_dir}/tasks/test-002" ]

    # Verify both task.json files exist
    [ -f "${run_dir}/tasks/test-001/task.json" ]
    [ -f "${run_dir}/tasks/test-002/task.json" ]
}

@test "artifacts_capture_plan: fails without task_id" {
    session_init --name "test-session"

    run artifacts_capture_plan "" "# Plan content"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "task_id is required" ]]
}

@test "artifacts_capture_plan: fails without plan_content" {
    session_init --name "test-session"

    run artifacts_capture_plan "test-001" ""
    [ "$status" -eq 1 ]
    [[ "$output" =~ "plan_content is required" ]]
}

@test "artifacts_capture_plan: writes plan.md" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    local plan_content="# Implementation Plan\n\n1. Step one\n2. Step two"
    run artifacts_capture_plan "test-001" "$plan_content"
    [ "$status" -eq 0 ]

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    [ -f "${task_dir}/plan.md" ]
}

@test "artifacts_capture_plan: plan.md has correct content" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    local plan_content="# Implementation Plan

1. Step one
2. Step two"
    artifacts_capture_plan "test-001" "$plan_content"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local plan_file="${task_dir}/plan.md"

    # Verify content matches
    local stored_content
    stored_content=$(cat "$plan_file")
    [ "$stored_content" = "$plan_content" ]
}

@test "artifacts_capture_plan: plan.md has 600 permissions" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    artifacts_capture_plan "test-001" "# Plan"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local plan_file="${task_dir}/plan.md"

    # Check permissions (should be 600)
    assert_permissions "$plan_file" "600"
}

@test "artifacts_capture_plan: is idempotent (overwrites)" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    artifacts_capture_plan "test-001" "First plan"
    artifacts_capture_plan "test-001" "Second plan"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local plan_file="${task_dir}/plan.md"

    # Should contain only the second plan
    local stored_content
    stored_content=$(cat "$plan_file")
    [ "$stored_content" = "Second plan" ]
}

@test "artifacts_capture_command: fails without task_id" {
    session_init --name "test-session"

    run artifacts_capture_command "" "npm test" "0" "output"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "task_id is required" ]]
}

@test "artifacts_capture_command: fails without cmd" {
    session_init --name "test-session"

    run artifacts_capture_command "test-001" "" "0" "output"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "cmd is required" ]]
}

@test "artifacts_capture_command: fails without exit_code" {
    session_init --name "test-session"

    run artifacts_capture_command "test-001" "npm test" "" "output"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "exit_code is required" ]]
}

@test "artifacts_capture_command: creates commands.jsonl" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    run artifacts_capture_command "test-001" "npm test" "0" "All tests passed" "5.2"
    [ "$status" -eq 0 ]

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    [ -f "${task_dir}/commands.jsonl" ]
}

@test "artifacts_capture_command: appends valid JSONL" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    artifacts_capture_command "test-001" "npm test" "0" "All tests passed" "5.2"
    artifacts_capture_command "test-001" "npm build" "1" "Build failed" "2.3"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local commands_file="${task_dir}/commands.jsonl"

    # Should have 2 lines
    local line_count
    line_count=$(wc -l < "$commands_file" | tr -d ' ')
    [ "$line_count" = "2" ]

    # Each line should be valid JSON (JSONL - validate line by line)
    while IFS= read -r line; do
        echo "$line" | jq empty
        [ $? -eq 0 ]
    done < "$commands_file"
}

@test "artifacts_capture_command: includes timestamp" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    artifacts_capture_command "test-001" "npm test" "0" "output" "5.2"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local commands_file="${task_dir}/commands.jsonl"

    # Check timestamp format
    local timestamp
    timestamp=$(jq -r '.timestamp' "$commands_file")
    [[ "$timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "artifacts_capture_command: includes all fields" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    artifacts_capture_command "test-001" "npm test" "0" "All tests passed" "5.2"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local commands_file="${task_dir}/commands.jsonl"

    # Check all fields exist
    run jq -r '.command' "$commands_file"
    [ "$status" -eq 0 ]
    [ "$output" = "npm test" ]

    run jq -r '.exit_code' "$commands_file"
    [ "$status" -eq 0 ]
    [ "$output" = "0" ]

    run jq -r '.output' "$commands_file"
    [ "$status" -eq 0 ]
    [ "$output" = "All tests passed" ]

    run jq -r '.duration' "$commands_file"
    [ "$status" -eq 0 ]
    [ "$output" = "5.2" ]
}

@test "artifacts_capture_command: handles empty output" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    run artifacts_capture_command "test-001" "npm test" "0" "" "5.2"
    [ "$status" -eq 0 ]

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local commands_file="${task_dir}/commands.jsonl"

    run jq -r '.output' "$commands_file"
    [ "$status" -eq 0 ]
    [ "$output" = "" ]
}

@test "artifacts_capture_command: defaults duration to 0" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    artifacts_capture_command "test-001" "npm test" "0" "output"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local commands_file="${task_dir}/commands.jsonl"

    run jq -r '.duration' "$commands_file"
    [ "$status" -eq 0 ]
    [ "$output" = "0" ]
}

@test "artifacts_capture_command: commands.jsonl has 600 permissions" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    artifacts_capture_command "test-001" "npm test" "0" "output" "5.2"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local commands_file="${task_dir}/commands.jsonl"

    # Check permissions (should be 600)
    assert_permissions "$commands_file" "600"
}

@test "artifacts_capture_diff: fails without task_id" {
    session_init --name "test-session"

    run artifacts_capture_diff ""
    [ "$status" -eq 1 ]
    [[ "$output" =~ "task_id is required" ]]
}

@test "artifacts_capture_diff: creates changes.patch" {
    # Initialize git repo in test directory
    git init >/dev/null 2>&1
    git config user.email "test@example.com"
    git config user.name "Test User"

    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    run artifacts_capture_diff "test-001"
    [ "$status" -eq 0 ]

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    [ -f "${task_dir}/changes.patch" ]
}

@test "artifacts_capture_diff: captures git diff output" {
    # Initialize git repo in test directory
    git init >/dev/null 2>&1
    git config user.email "test@example.com"
    git config user.name "Test User"

    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    # Create a file and modify it
    echo "original" > test_file.txt
    git add test_file.txt
    git commit -m "Add test file" >/dev/null 2>&1
    echo "modified" > test_file.txt

    artifacts_capture_diff "test-001"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local patch_file="${task_dir}/changes.patch"

    # Should contain diff output
    local patch_content
    patch_content=$(cat "$patch_file")
    [[ "$patch_content" =~ "test_file.txt" ]]
    [[ "$patch_content" =~ "original" ]]
    [[ "$patch_content" =~ "modified" ]]
}

@test "artifacts_capture_diff: handles empty diff gracefully" {
    # Initialize git repo in test directory
    git init >/dev/null 2>&1
    git config user.email "test@example.com"
    git config user.name "Test User"

    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    # No changes to capture
    run artifacts_capture_diff "test-001"
    [ "$status" -eq 0 ]

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local patch_file="${task_dir}/changes.patch"

    # File should exist but be empty (or just a newline)
    [ -f "$patch_file" ]
    local file_size
    file_size=$(wc -c < "$patch_file" | tr -d ' ')
    # Empty diff results in 1 byte (newline from echo)
    [ "$file_size" -le "1" ]
}

@test "artifacts_capture_diff: changes.patch has 600 permissions" {
    # Initialize git repo in test directory
    git init >/dev/null 2>&1
    git config user.email "test@example.com"
    git config user.name "Test User"

    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    artifacts_capture_diff "test-001"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local patch_file="${task_dir}/changes.patch"

    # Check permissions (should be 600)
    assert_permissions "$patch_file" "600"
}

@test "artifacts_capture_diff: is idempotent (overwrites)" {
    # Initialize git repo in test directory
    git init >/dev/null 2>&1
    git config user.email "test@example.com"
    git config user.name "Test User"

    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    # Create and commit a file
    echo "original" > test_file.txt
    git add test_file.txt
    git commit -m "Initial commit" >/dev/null 2>&1

    # First capture (no changes)
    artifacts_capture_diff "test-001"

    # Make a change
    echo "modified" > test_file.txt

    # Second capture should overwrite
    artifacts_capture_diff "test-001"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local patch_file="${task_dir}/changes.patch"

    # Should contain the modified file (not the empty diff from first capture)
    local patch_content
    patch_content=$(cat "$patch_file")
    [[ "$patch_content" =~ "test_file.txt" ]]
    [[ "$patch_content" =~ "modified" ]]
}

# ============================================================================
# artifacts_capture_harness_output
# ============================================================================

@test "artifacts_capture_harness_output: fails without task_id" {
    session_init --name "test-session"

    run artifacts_capture_harness_output "" "/tmp/nonexistent"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "task_id is required" ]]
}

@test "artifacts_capture_harness_output: fails without output_file" {
    session_init --name "test-session"

    run artifacts_capture_harness_output "test-001" ""
    [ "$status" -eq 1 ]
    [[ "$output" =~ "output_file is required" ]]
}

@test "artifacts_capture_harness_output: fails if output_file doesn't exist" {
    session_init --name "test-session"

    run artifacts_capture_harness_output "test-001" "/tmp/nonexistent_file_12345"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "output_file does not exist" ]]
}

@test "artifacts_capture_harness_output: creates harness_output.log" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    # Create a temp file with some content
    local temp_file="${BATS_TEST_TMPDIR}/harness_output"
    echo '{"type":"assistant","message":"test"}' > "$temp_file"

    run artifacts_capture_harness_output "test-001" "$temp_file"
    [ "$status" -eq 0 ]

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local log_file="${task_dir}/harness_output.log"

    [ -f "$log_file" ]
}

@test "artifacts_capture_harness_output: content is captured correctly" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    # Create a temp file with some JSON content
    local temp_file="${BATS_TEST_TMPDIR}/harness_output"
    echo '{"type":"assistant","message":"hello world"}' > "$temp_file"

    artifacts_capture_harness_output "test-001" "$temp_file"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local log_file="${task_dir}/harness_output.log"

    # Verify content
    local content
    content=$(cat "$log_file")
    [[ "$content" =~ "hello world" ]]
}

@test "artifacts_capture_harness_output: appends with iteration header" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    # Create temp files for two iterations
    local temp1="${BATS_TEST_TMPDIR}/harness1"
    local temp2="${BATS_TEST_TMPDIR}/harness2"
    echo '{"iteration":1}' > "$temp1"
    echo '{"iteration":2}' > "$temp2"

    artifacts_capture_harness_output "test-001" "$temp1" "1"
    artifacts_capture_harness_output "test-001" "$temp2" "2"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local log_file="${task_dir}/harness_output.log"

    # Verify iteration headers
    local content
    content=$(cat "$log_file")
    [[ "$content" =~ "Iteration: 1" ]]
    [[ "$content" =~ "Iteration: 2" ]]
    [[ "$content" =~ "iteration\":1" ]]
    [[ "$content" =~ "iteration\":2" ]]
}

@test "artifacts_capture_harness_output: harness_output.log has 600 permissions" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    local temp_file="${BATS_TEST_TMPDIR}/harness_output"
    echo '{"test":true}' > "$temp_file"

    artifacts_capture_harness_output "test-001" "$temp_file"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local log_file="${task_dir}/harness_output.log"

    # Check permissions (should be 600)
    assert_permissions "$log_file" "600"
}

@test "artifacts integration: capture all artifact types" {
    # Initialize git repo in test directory
    git init >/dev/null 2>&1
    git config user.email "test@example.com"
    git config user.name "Test User"

    session_init --name "capture-test"
    artifacts_init_run
    artifacts_start_task "test-001" "Integration test"

    # Capture plan
    artifacts_capture_plan "test-001" "# Plan\n1. Do something"

    # Capture commands
    artifacts_capture_command "test-001" "npm test" "0" "Success" "5.2"
    artifacts_capture_command "test-001" "npm build" "1" "Failed" "2.3"

    # Capture diff
    artifacts_capture_diff "test-001"

    # Verify all files exist
    local task_dir
    task_dir=$(find .curb/runs -type d -name "capture-test-*" | head -1)/tasks/test-001

    [ -f "${task_dir}/task.json" ]
    [ -f "${task_dir}/plan.md" ]
    [ -f "${task_dir}/commands.jsonl" ]
    [ -f "${task_dir}/changes.patch" ]

    # Verify commands has 2 entries
    local line_count
    line_count=$(wc -l < "${task_dir}/commands.jsonl" | tr -d ' ')
    [ "$line_count" = "2" ]
}

@test "artifacts_get_path: fails without task_id" {
    session_init --name "test-session"

    run artifacts_get_path ""
    [ "$status" -eq 1 ]
    [[ "$output" =~ "task_id is required" ]]
}

@test "artifacts_get_path: returns absolute path" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    run artifacts_get_path "test-001"
    [ "$status" -eq 0 ]

    # Output should be an absolute path (starts with /)
    [[ "$output" =~ ^/ ]]

    # Should contain the expected structure
    [[ "$output" =~ .curb/runs/test-session-.*/tasks/test-001 ]]
}

@test "artifacts_get_path: path is actually absolute and valid" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    local abs_path
    abs_path=$(artifacts_get_path "test-001")

    # Directory should exist when we use the absolute path
    [ -d "$abs_path" ]
}

@test "artifacts_finalize_task: fails without task_id" {
    session_init --name "test-session"

    run artifacts_finalize_task "" "completed" "0" "Summary"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "task_id is required" ]]
}

@test "artifacts_finalize_task: fails without status" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    run artifacts_finalize_task "test-001" "" "0" "Summary"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "status is required" ]]
}

@test "artifacts_finalize_task: fails without exit_code" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    run artifacts_finalize_task "test-001" "completed" "" "Summary"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "exit_code is required" ]]
}

@test "artifacts_finalize_task: fails if task.json doesn't exist" {
    session_init --name "test-session"

    run artifacts_finalize_task "test-001" "completed" "0" "Summary"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "task.json not found" ]]
}

@test "artifacts_finalize_task: updates task.json with final status" {
    session_init --name "test-session"
    artifacts_init_run
    artifacts_start_task "test-001" "Test task"

    run artifacts_finalize_task "test-001" "completed" "0" "All done"
    [ "$status" -eq 0 ]

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local task_json="${task_dir}/task.json"

    # Check status
    run jq -r '.status' "$task_json"
    [ "$status" -eq 0 ]
    [ "$output" = "completed" ]

    # Check exit_code
    run jq -r '.exit_code' "$task_json"
    [ "$status" -eq 0 ]
    [ "$output" = "0" ]

    # Check completed_at exists and is ISO 8601 format
    run jq -r '.completed_at' "$task_json"
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]

    # Check iterations incremented
    run jq -r '.iterations' "$task_json"
    [ "$status" -eq 0 ]
    [ "$output" = "1" ]
}

@test "artifacts_finalize_task: increments iterations" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    # Finalize twice
    artifacts_finalize_task "test-001" "failed" "1" "First attempt"
    artifacts_finalize_task "test-001" "completed" "0" "Second attempt"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local task_json="${task_dir}/task.json"

    # Iterations should be 2
    run jq -r '.iterations' "$task_json"
    [ "$status" -eq 0 ]
    [ "$output" = "2" ]
}

@test "artifacts_finalize_task: creates summary.md" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    artifacts_finalize_task "test-001" "completed" "0" "Task completed successfully"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001

    [ -f "${task_dir}/summary.md" ]
}

@test "artifacts_finalize_task: summary.md contains required fields" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    artifacts_finalize_task "test-001" "completed" "0" "Task completed successfully"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local summary_file="${task_dir}/summary.md"

    [ -f "$summary_file" ] || { echo "summary.md not found at $summary_file"; return 1; }

    local summary_content
    summary_content=$(cat "$summary_file")

    # Check for required fields (using markdown format with ** bold **)
    [[ "$summary_content" == *"# Task Summary: Test task"* ]]
    [[ "$summary_content" == *"**Task ID:** test-001"* ]]
    [[ "$summary_content" == *"**Status:** completed"* ]]
    [[ "$summary_content" == *"**Exit Code:** 0"* ]]
    [[ "$summary_content" == *"**Duration:**"* ]]
    [[ "$summary_content" == *"**Files Changed:**"* ]]
    [[ "$summary_content" == *"Task completed successfully"* ]]
}

@test "artifacts_finalize_task: summary.md has 600 permissions" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    artifacts_finalize_task "test-001" "completed" "0" "Done"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local summary_file="${task_dir}/summary.md"

    # Check permissions (should be 600)
    assert_permissions "$summary_file" "600"
}

@test "artifacts_finalize_task: updates run.json with tasks_completed counter" {
    session_init --name "test-session"
    artifacts_init_run
    artifacts_start_task "test-001" "Test task"

    artifacts_finalize_task "test-001" "completed" "0" "Done"

    local run_dir
    run_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)
    local run_json="${run_dir}/run.json"

    # Check tasks_completed counter
    run jq -r '.tasks_completed' "$run_json"
    [ "$status" -eq 0 ]
    [ "$output" = "1" ]
}

@test "artifacts_finalize_task: updates run.json with tasks_failed counter" {
    session_init --name "test-session"
    artifacts_init_run
    artifacts_start_task "test-001" "Test task"

    artifacts_finalize_task "test-001" "failed" "1" "Failed"

    local run_dir
    run_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)
    local run_json="${run_dir}/run.json"

    # Check tasks_failed counter
    run jq -r '.tasks_failed' "$run_json"
    [ "$status" -eq 0 ]
    [ "$output" = "1" ]
}

@test "artifacts_finalize_task: increments counters correctly for multiple tasks" {
    session_init --name "test-session"
    artifacts_init_run

    # Create and finalize multiple tasks
    artifacts_start_task "test-001" "Task 1"
    artifacts_finalize_task "test-001" "completed" "0" "Done"

    artifacts_start_task "test-002" "Task 2"
    artifacts_finalize_task "test-002" "completed" "0" "Done"

    artifacts_start_task "test-003" "Task 3"
    artifacts_finalize_task "test-003" "failed" "1" "Failed"

    local run_dir
    run_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)
    local run_json="${run_dir}/run.json"

    # Check tasks_completed counter
    run jq -r '.tasks_completed' "$run_json"
    [ "$status" -eq 0 ]
    [ "$output" = "2" ]

    # Check tasks_failed counter
    run jq -r '.tasks_failed' "$run_json"
    [ "$status" -eq 0 ]
    [ "$output" = "1" ]
}

@test "artifacts_finalize_task: handles empty summary_text" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    run artifacts_finalize_task "test-001" "completed" "0" ""
    [ "$status" -eq 0 ]

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local summary_file="${task_dir}/summary.md"

    local summary_content
    summary_content=$(cat "$summary_file")

    # Should have default text
    [[ "$summary_content" =~ "No summary provided" ]]
}

@test "artifacts_finalize_task: calculates duration correctly" {
    session_init --name "test-session"
    artifacts_start_task "test-001" "Test task"

    # Sleep for a bit to ensure duration is non-zero
    sleep 2

    artifacts_finalize_task "test-001" "completed" "0" "Done"

    local task_dir
    task_dir=$(find .curb/runs -type d -name "test-session-*" | head -1)/tasks/test-001
    local summary_file="${task_dir}/summary.md"

    local summary_content
    summary_content=$(cat "$summary_file")

    # Duration should be at least 1 second (we slept for 2)
    # Match pattern like "**Duration:** 2s" (markdown bold)
    [[ "$summary_content" =~ \*\*Duration:\*\*\ [0-9]+[smh] ]]
}

@test "artifacts integration: full task lifecycle with finalization" {
    # Initialize git repo in test directory
    git init >/dev/null 2>&1
    git config user.email "test@example.com"
    git config user.name "Test User"

    session_init --name "lifecycle-test"
    artifacts_init_run
    artifacts_start_task "test-001" "Full lifecycle test"

    # Capture plan
    artifacts_capture_plan "test-001" "# Implementation Plan"

    # Capture commands
    artifacts_capture_command "test-001" "npm test" "0" "All tests passed" "5.2"

    # Make some changes and capture diff
    echo "test file" > test.txt
    artifacts_capture_diff "test-001"

    # Finalize the task
    artifacts_finalize_task "test-001" "completed" "0" "Successfully implemented feature"

    # Verify all files exist
    local task_dir
    task_dir=$(find .curb/runs -type d -name "lifecycle-test-*" | head -1)/tasks/test-001

    [ -f "${task_dir}/task.json" ]
    [ -f "${task_dir}/plan.md" ]
    [ -f "${task_dir}/commands.jsonl" ]
    [ -f "${task_dir}/changes.patch" ]
    [ -f "${task_dir}/summary.md" ]

    # Verify task.json has completed status
    run jq -r '.status' "${task_dir}/task.json"
    [ "$status" -eq 0 ]
    [ "$output" = "completed" ]

    # Verify run.json has correct counter
    local run_dir
    run_dir=$(find .curb/runs -type d -name "lifecycle-test-*" | head -1)
    run jq -r '.tasks_completed' "${run_dir}/run.json"
    [ "$status" -eq 0 ]
    [ "$output" = "1" ]
}
