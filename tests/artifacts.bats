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
