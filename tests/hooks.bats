#!/usr/bin/env bats
#
# Tests for lib/hooks.sh - Hook framework
#

load test_helper

setup() {
    setup_test_dir

    # Override curb_config_dir BEFORE sourcing hooks.sh
    # This ensures hooks.sh uses our test directory
    curb_config_dir() {
        echo "$TEST_DIR/.config/curb"
    }
    export -f curb_config_dir

    # Source the hooks library (will use our curb_config_dir)
    source "${PROJECT_ROOT}/lib/hooks.sh"

    # Create config directory
    mkdir -p "$(curb_config_dir)"

    # Create default config with hooks enabled
    cat > "$(curb_config_dir)/config.json" <<EOF
{
    "hooks": {
        "enabled": true,
        "fail_fast": false
    }
}
EOF

    # Reload config
    config_load
}

teardown() {
    hooks_clear_context
    teardown_test_dir
}

# Helper: Create a hook script
create_hook() {
    local hook_name="$1"
    local script_name="$2"
    local script_content="$3"
    local location="${4:-global}"  # global or project

    local hook_dir
    if [[ "$location" == "global" ]]; then
        hook_dir="$(curb_config_dir)/hooks/${hook_name}.d"
    else
        hook_dir="./.curb/hooks/${hook_name}.d"
    fi

    mkdir -p "$hook_dir"
    echo "$script_content" > "$hook_dir/$script_name"
    chmod +x "$hook_dir/$script_name"
}

# Test: hooks_run with no scripts returns success
@test "hooks_run with no scripts returns success" {
    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
}

# Test: hooks_run executes script in global directory
@test "hooks_run executes script in global directory" {
    create_hook "pre-task" "01-test.sh" '#!/bin/bash
echo "Hook executed"
exit 0' "global"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Hook executed"* ]]
}

# Test: hooks_run executes script in project directory
@test "hooks_run executes script in project directory" {
    create_hook "pre-task" "01-test.sh" '#!/bin/bash
echo "Project hook executed"
exit 0' "project"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Project hook executed"* ]]
}

# Test: hooks_run executes scripts in sorted order
@test "hooks_run executes scripts in sorted order" {
    create_hook "pre-task" "02-second.sh" '#!/bin/bash
echo "Second"
exit 0' "global"

    create_hook "pre-task" "01-first.sh" '#!/bin/bash
echo "First"
exit 0' "global"

    create_hook "pre-task" "03-third.sh" '#!/bin/bash
echo "Third"
exit 0' "global"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
    # Check order by looking at line positions
    echo "$output" | grep -n "First" | cut -d: -f1 > /tmp/first_line
    echo "$output" | grep -n "Second" | cut -d: -f1 > /tmp/second_line
    echo "$output" | grep -n "Third" | cut -d: -f1 > /tmp/third_line

    first_line=$(cat /tmp/first_line)
    second_line=$(cat /tmp/second_line)
    third_line=$(cat /tmp/third_line)

    [ "$first_line" -lt "$second_line" ]
    [ "$second_line" -lt "$third_line" ]
}

# Test: hooks_run exports CURB_HOOK_NAME
@test "hooks_run exports CURB_HOOK_NAME" {
    create_hook "pre-task" "01-test.sh" '#!/bin/bash
echo "Hook name: $CURB_HOOK_NAME"
exit 0' "global"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Hook name: pre-task"* ]]
}

# Test: hooks_run exports CURB_PROJECT_DIR
@test "hooks_run exports CURB_PROJECT_DIR" {
    create_hook "pre-task" "01-test.sh" '#!/bin/bash
echo "Project dir: $CURB_PROJECT_DIR"
exit 0' "global"

    export CURB_PROJECT_DIR="$TEST_DIR"
    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Project dir: $TEST_DIR"* ]]
}

# Test: hooks_set_task_context exports task variables
@test "hooks_set_task_context exports task variables" {
    create_hook "pre-task" "01-test.sh" '#!/bin/bash
echo "Task ID: $CURB_TASK_ID"
echo "Task Title: $CURB_TASK_TITLE"
exit 0' "global"

    hooks_set_task_context "test-001" "Test Task"
    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Task ID: test-001"* ]]
    [[ "$output" == *"Task Title: Test Task"* ]]
}

# Test: hooks_set_task_context exports exit code
@test "hooks_set_task_context exports exit code" {
    create_hook "post-task" "01-test.sh" '#!/bin/bash
echo "Exit code: $CURB_EXIT_CODE"
exit 0' "global"

    hooks_set_task_context "test-001" "Test Task" "42"
    run hooks_run "post-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Exit code: 42"* ]]
}

# Test: hooks_set_session_context exports session variables
@test "hooks_set_session_context exports session variables" {
    create_hook "pre-loop" "01-test.sh" '#!/bin/bash
echo "Session ID: $CURB_SESSION_ID"
echo "Harness: $CURB_HARNESS"
exit 0' "global"

    hooks_set_session_context "20260110-123456" "claude"
    run hooks_run "pre-loop"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Session ID: 20260110-123456"* ]]
    [[ "$output" == *"Harness: claude"* ]]
}

# Test: hooks_run passes arguments to scripts
@test "hooks_run passes arguments to scripts" {
    create_hook "pre-task" "01-test.sh" '#!/bin/bash
echo "Args: $@"
exit 0' "global"

    run hooks_run "pre-task" "arg1" "arg2" "arg3"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Args: arg1 arg2 arg3"* ]]
}

# Test: hook failure logged when fail_fast is false (default)
@test "hook failure logged but doesn't stop execution when fail_fast is false" {
    create_hook "pre-task" "01-fail.sh" '#!/bin/bash
echo "Failing hook"
exit 1' "global"

    create_hook "pre-task" "02-success.sh" '#!/bin/bash
echo "Success hook"
exit 0' "global"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]  # Should still succeed with fail_fast=false
    [[ "$output" == *"01-fail.sh failed with exit code 1"* ]]
    [[ "$output" == *"Success hook"* ]]
}

# Test: hook failure stops execution when fail_fast is true
@test "hook failure stops execution when fail_fast is true" {
    # Update config to enable fail_fast
    cat > "$(curb_config_dir)/config.json" <<EOF
{
    "hooks": {
        "enabled": true,
        "fail_fast": true
    }
}
EOF
    config_load

    create_hook "pre-task" "01-fail.sh" '#!/bin/bash
echo "Failing hook"
exit 1' "global"

    create_hook "pre-task" "02-success.sh" '#!/bin/bash
echo "Success hook"
exit 0' "global"

    run hooks_run "pre-task"
    [ "$status" -eq 1 ]  # Should fail with fail_fast=true
    [[ "$output" == *"01-fail.sh failed with exit code 1"* ]]
    [[ "$output" != *"Success hook"* ]]  # Second hook should not run
}

# Test: hooks_run requires hook_name parameter
@test "hooks_run requires hook_name parameter" {
    run hooks_run ""
    [ "$status" -eq 1 ]
    [[ "$output" == *"ERROR: hook_name is required"* ]]
}

# Test: non-executable files are skipped
@test "non-executable files are skipped" {
    local hook_dir="$(curb_config_dir)/hooks/pre-task.d"
    mkdir -p "$hook_dir"

    # Create non-executable file
    echo '#!/bin/bash
echo "Should not execute"' > "$hook_dir/01-not-executable.sh"
    # Don't chmod +x

    # Create executable file
    create_hook "pre-task" "02-executable.sh" '#!/bin/bash
echo "Should execute"
exit 0' "global"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" != *"Should not execute"* ]]
    [[ "$output" == *"Should execute"* ]]
}

# Test: both global and project hooks are executed
@test "both global and project hooks are executed" {
    create_hook "pre-task" "01-global.sh" '#!/bin/bash
echo "Global hook"
exit 0' "global"

    create_hook "pre-task" "02-project.sh" '#!/bin/bash
echo "Project hook"
exit 0' "project"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Global hook"* ]]
    [[ "$output" == *"Project hook"* ]]
}

# Test: hook output captured and displayed
@test "hook output captured and displayed" {
    create_hook "pre-task" "01-test.sh" '#!/bin/bash
echo "Standard output"
echo "Error output" >&2
exit 0' "global"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Standard output"* ]]
    [[ "$output" == *"Error output"* ]]
}

# Test: hooks_clear_context clears environment variables
@test "hooks_clear_context clears environment variables" {
    hooks_set_task_context "test-001" "Test Task" "0"
    hooks_set_session_context "20260110-123456" "claude"

    # Verify variables are set
    [ -n "$CURB_TASK_ID" ]
    [ -n "$CURB_SESSION_ID" ]

    hooks_clear_context

    # Verify variables are cleared
    [ -z "$CURB_TASK_ID" ]
    [ -z "$CURB_TASK_TITLE" ]
    [ -z "$CURB_EXIT_CODE" ]
    [ -z "$CURB_SESSION_ID" ]
    [ -z "$CURB_HARNESS" ]
}

# tests for hooks_find function

# Test: hooks_find with no scripts returns empty
@test "hooks_find with no scripts returns empty" {
    run hooks_find "pre-task"
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

# Test: hooks_find finds scripts in global directory
@test "hooks_find finds scripts in global directory" {
    create_hook "pre-task" "01-test.sh" '#!/bin/bash
exit 0' "global"

    run hooks_find "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"01-test.sh"* ]]
}

# Test: hooks_find finds scripts in project directory
@test "hooks_find finds scripts in project directory" {
    create_hook "pre-task" "01-test.sh" '#!/bin/bash
exit 0' "project"

    run hooks_find "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"01-test.sh"* ]]
}

# Test: hooks_find returns scripts in sorted order
@test "hooks_find returns scripts in sorted order" {
    create_hook "pre-task" "03-third.sh" '#!/bin/bash
exit 0' "global"

    create_hook "pre-task" "01-first.sh" '#!/bin/bash
exit 0' "global"

    create_hook "pre-task" "02-second.sh" '#!/bin/bash
exit 0' "global"

    run hooks_find "pre-task"
    [ "$status" -eq 0 ]

    # Check order by looking at line positions
    first_line=$(echo "$output" | grep -n "01-first.sh" | cut -d: -f1)
    second_line=$(echo "$output" | grep -n "02-second.sh" | cut -d: -f1)
    third_line=$(echo "$output" | grep -n "03-third.sh" | cut -d: -f1)

    [ "$first_line" -lt "$second_line" ]
    [ "$second_line" -lt "$third_line" ]
}

# Test: hooks_find only returns executable files
@test "hooks_find only returns executable files" {
    local hook_dir="$(curb_config_dir)/hooks/pre-task.d"
    mkdir -p "$hook_dir"

    # Create non-executable file
    echo '#!/bin/bash
exit 0' > "$hook_dir/01-not-executable.sh"
    # Don't chmod +x

    # Create executable file
    create_hook "pre-task" "02-executable.sh" '#!/bin/bash
exit 0' "global"

    run hooks_find "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" != *"01-not-executable.sh"* ]]
    [[ "$output" == *"02-executable.sh"* ]]
}

# Test: hooks_find returns both global and project scripts
@test "hooks_find returns both global and project scripts" {
    create_hook "pre-task" "01-global.sh" '#!/bin/bash
exit 0' "global"

    create_hook "pre-task" "02-project.sh" '#!/bin/bash
exit 0' "project"

    run hooks_find "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"01-global.sh"* ]]
    [[ "$output" == *"02-project.sh"* ]]
}

# Test: hooks_find merges global and project hooks in sorted order (global first)
@test "hooks_find merges global and project hooks in sorted order (global first)" {
    create_hook "pre-task" "02-global.sh" '#!/bin/bash
exit 0' "global"

    create_hook "pre-task" "01-project.sh" '#!/bin/bash
exit 0' "project"

    run hooks_find "pre-task"
    [ "$status" -eq 0 ]

    # Both should be present
    [[ "$output" == *"02-global.sh"* ]]
    [[ "$output" == *"01-project.sh"* ]]

    # Global hooks should come first
    global_line=$(echo "$output" | grep -n "02-global.sh" | cut -d: -f1)
    project_line=$(echo "$output" | grep -n "01-project.sh" | cut -d: -f1)
    [ "$global_line" -lt "$project_line" ]
}

# Test: hooks_find requires hook_name parameter
@test "hooks_find requires hook_name parameter" {
    run hooks_find ""
    [ "$status" -eq 1 ]
    [[ "$output" == *"ERROR: hook_name is required"* ]]
}

# Acceptance Criteria Tests

# Test: AC - hooks_run "pre-task" executes scripts in pre-task.d/
@test "AC: hooks_run executes all scripts in pre-task.d/" {
    create_hook "pre-task" "01-first.sh" '#!/bin/bash
echo "First script"
exit 0' "global"

    create_hook "pre-task" "02-second.sh" '#!/bin/bash
echo "Second script"
exit 0' "global"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"First script"* ]]
    [[ "$output" == *"Second script"* ]]
}

# Test: AC - Scripts receive context via environment vars
@test "AC: scripts receive context via environment vars" {
    create_hook "pre-task" "01-test.sh" '#!/bin/bash
[ -n "$CURB_HOOK_NAME" ] || exit 1
[ -n "$CURB_PROJECT_DIR" ] || exit 1
[ -n "$CURB_TASK_ID" ] || exit 1
echo "All context vars present"
exit 0' "global"

    hooks_set_task_context "test-001" "Test Task"
    export CURB_PROJECT_DIR="$TEST_DIR"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"All context vars present"* ]]
}

# Test: AC - Hook failure logged but doesn't stop loop (when fail_fast is false)
@test "AC: hook failure logged but doesn't stop loop when configurable" {
    create_hook "pre-task" "01-fail.sh" '#!/bin/bash
exit 1' "global"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]  # Returns success when fail_fast is false
    [[ "$output" == *"failed with exit code 1"* ]]
}

# Test: AC - Scripts run in sorted order
@test "AC: scripts run in sorted order (01-first.sh before 02-second.sh)" {
    create_hook "pre-task" "02-second.sh" '#!/bin/bash
echo "SECOND"
exit 0' "global"

    create_hook "pre-task" "01-first.sh" '#!/bin/bash
echo "FIRST"
exit 0' "global"

    run hooks_run "pre-task"
    [ "$status" -eq 0 ]

    # Verify FIRST appears before SECOND in output
    first_pos=$(echo "$output" | grep -n "FIRST" | cut -d: -f1)
    second_pos=$(echo "$output" | grep -n "SECOND" | cut -d: -f1)

    [ "$first_pos" -lt "$second_pos" ]
}

# Acceptance Criteria Tests for hooks_find

# Test: AC - hooks_find finds hooks in global directory
@test "AC: hooks_find finds hooks in global directory" {
    create_hook "pre-task" "01-global.sh" '#!/bin/bash
exit 0' "global"

    run hooks_find "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"01-global.sh"* ]]
}

# Test: AC - hooks_find finds hooks in project directory
@test "AC: hooks_find finds hooks in project directory" {
    create_hook "pre-task" "01-project.sh" '#!/bin/bash
exit 0' "project"

    run hooks_find "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" == *"01-project.sh"* ]]
}

# Test: AC - hooks_find merges both (global runs first)
@test "AC: hooks_find merges both global and project (global first)" {
    create_hook "pre-task" "01-global.sh" '#!/bin/bash
exit 0' "global"

    create_hook "pre-task" "02-project.sh" '#!/bin/bash
exit 0' "project"

    run hooks_find "pre-task"
    [ "$status" -eq 0 ]

    # Both should be present
    [[ "$output" == *"01-global.sh"* ]]
    [[ "$output" == *"02-project.sh"* ]]

    # Global should come first
    global_line=$(echo "$output" | grep -n "01-global.sh" | cut -d: -f1)
    project_line=$(echo "$output" | grep -n "02-project.sh" | cut -d: -f1)
    [ "$global_line" -lt "$project_line" ]
}

# Test: AC - hooks_find only returns executable files
@test "AC: hooks_find only returns executable files" {
    local hook_dir="$(curb_config_dir)/hooks/pre-task.d"
    mkdir -p "$hook_dir"

    # Create non-executable file
    echo '#!/bin/bash
exit 0' > "$hook_dir/01-not-executable.sh"

    # Create executable file
    create_hook "pre-task" "02-executable.sh" '#!/bin/bash
exit 0' "global"

    run hooks_find "pre-task"
    [ "$status" -eq 0 ]
    [[ "$output" != *"01-not-executable.sh"* ]]
    [[ "$output" == *"02-executable.sh"* ]]
}
