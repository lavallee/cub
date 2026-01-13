#!/usr/bin/env bats
#
# tests/error_handling.bats - Tests for error conditions and edge cases
#

load 'test_helper'

setup() {
    setup_test_dir
    export CUB_BACKEND="json"
    source "$LIB_DIR/tasks.sh"
    source "$LIB_DIR/harness.sh"
}

teardown() {
    teardown_test_dir
}

# =============================================================================
# File System Error Tests
# =============================================================================

@test "json_get_ready_tasks handles missing prd.json gracefully" {
    run json_get_ready_tasks "nonexistent.json"
    [ "$status" -ne 0 ]
}

@test "json_get_task handles missing prd.json gracefully" {
    run json_get_task "nonexistent.json" "task-1"
    [ "$status" -ne 0 ]
}

@test "validate_prd handles missing file" {
    run validate_prd "nonexistent.json"
    [ "$status" -ne 0 ]
}

@test "validate_prd handles malformed JSON" {
    echo "not valid json {" > prd.json
    run validate_prd "prd.json"
    [ "$status" -ne 0 ]
}

@test "json_update_task_status handles read-only directory" {
    mkdir readonly_dir
    cd readonly_dir
    create_minimal_prd
    cd ..
    chmod 555 readonly_dir
    run json_update_task_status "readonly_dir/prd.json" "test-1" "closed"
    [ "$status" -ne 0 ]
    chmod 755 readonly_dir  # cleanup
}

# =============================================================================
# Invalid Input Tests
# =============================================================================

@test "json_get_task handles empty task ID" {
    create_sample_prd
    run json_get_task "prd.json" ""
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "json_update_task_status handles nonexistent task ID" {
    create_minimal_prd
    # Should succeed but not change anything
    json_update_task_status "prd.json" "nonexistent" "closed"
    [ "$?" -eq 0 ]
}

@test "json_add_task_note handles special characters in note" {
    create_sample_prd
    json_add_task_note "prd.json" "test-0001" "Note with 'quotes' and \"double quotes\" and \$vars"
    [ "$?" -eq 0 ]

    local notes
    notes=$(jq -r '.tasks[] | select(.id == "test-0001") | .notes' prd.json)
    [[ "$notes" == *"quotes"* ]]
}

@test "json_create_task handles malformed JSON input" {
    create_minimal_prd
    run json_create_task "prd.json" "not valid json"
    [ "$status" -ne 0 ]
}

# =============================================================================
# Circular Dependency Tests
# =============================================================================

@test "json_get_ready_tasks handles circular dependencies" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Task 1", "status": "open", "dependsOn": ["t2"]},
    {"id": "t2", "title": "Task 2", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF
    run json_get_ready_tasks "prd.json"
    [ "$status" -eq 0 ]
    # Both tasks should be blocked (empty result)
    [ "$output" = "[]" ]
}

@test "json_get_blocked_tasks identifies all tasks in circular dependency" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Task 1", "status": "open", "dependsOn": ["t2"]},
    {"id": "t2", "title": "Task 2", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF
    run json_get_blocked_tasks "prd.json"
    [ "$status" -eq 0 ]

    local count
    count=$(echo "$output" | jq 'length')
    [ "$count" -eq 2 ]
}

# =============================================================================
# Harness Error Handling Tests
# =============================================================================

@test "harness_invoke returns error when harness command fails" {
    # Mock a failing harness
    _HARNESS="claude"
    claude() { return 1; }
    export -f claude

    run harness_invoke "system" "task"
    [ "$status" -ne 0 ]
}

@test "claude_parse_stream handles invalid JSON gracefully" {
    echo "not json" | claude_parse_stream
    # Should not crash, just skip invalid lines
    [ "$?" -eq 0 ]
}

@test "claude_parse_stream handles partial JSON stream" {
    local json='{"type":"assistant","message":{"content"'
    echo "$json" | claude_parse_stream
    # Should handle gracefully
    [ "$?" -eq 0 ]
}

@test "harness_detect handles no harness installed" {
    # Override PATH to hide any real harnesses
    PATH="/usr/bin:/bin" run harness_detect
    # Should return empty string
    [ "$status" -eq 0 ]
}

# =============================================================================
# Edge Cases
# =============================================================================

@test "json_get_ready_tasks handles empty tasks array" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": []
}
EOF
    run json_get_ready_tasks "prd.json"
    [ "$status" -eq 0 ]
    [ "$output" = "[]" ]
}

@test "json_get_ready_tasks handles tasks with empty dependsOn array" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Task 1", "status": "open", "dependsOn": []}
  ]
}
EOF
    run json_get_ready_tasks "prd.json"
    [ "$status" -eq 0 ]

    local count
    count=$(echo "$output" | jq 'length')
    [ "$count" -eq 1 ]
}

@test "json_get_task_counts handles missing status field" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Task 1", "status": "open"},
    {"id": "t2", "title": "Task 2"}
  ]
}
EOF
    run json_get_task_counts "prd.json"
    [ "$status" -eq 0 ]
    # Should still return counts
    [[ "$output" == *"total"* ]]
}

@test "generate_task_id handles missing prefix field" {
    cat > prd.json << 'EOF'
{
  "tasks": []
}
EOF
    run generate_task_id "prd.json"
    [ "$status" -eq 0 ]
    # Should use default prefix "prd"
    [[ "$output" == prd-* ]]
}

# =============================================================================
# Concurrency/Race Condition Tests
# =============================================================================

@test "json_update_task_status is atomic" {
    create_sample_prd

    # Update same task twice in quick succession
    json_update_task_status "prd.json" "test-0001" "in_progress" &
    json_update_task_status "prd.json" "test-0001" "closed" &
    wait

    # File should still be valid JSON
    run validate_prd "prd.json"
    [ "$status" -eq 0 ]

    # Status should be one of the two (last write wins)
    local status
    status=$(jq -r '.tasks[] | select(.id == "test-0001") | .status' prd.json)
    [[ "$status" == "in_progress" || "$status" == "closed" ]]
}

# =============================================================================
# Large Dataset Tests
# =============================================================================

@test "json_get_ready_tasks handles large task lists" {
    # Create prd.json with 100 tasks
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": []
}
EOF

    for i in {1..100}; do
        local task='{"id": "test-'$i'", "title": "Task '$i'", "status": "open", "priority": "P2"}'
        json_create_task "prd.json" "$task"
    done

    run json_get_ready_tasks "prd.json"
    [ "$status" -eq 0 ]

    local count
    count=$(echo "$output" | jq 'length')
    [ "$count" -eq 100 ]
}

@test "validate_prd handles deeply nested dependencies" {
    # Create chain: t1 -> t2 -> t3 -> t4 -> t5
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Task 1", "status": "open", "priority": "P1"},
    {"id": "t2", "title": "Task 2", "status": "open", "priority": "P1", "dependsOn": ["t1"]},
    {"id": "t3", "title": "Task 3", "status": "open", "priority": "P1", "dependsOn": ["t2"]},
    {"id": "t4", "title": "Task 4", "status": "open", "priority": "P1", "dependsOn": ["t3"]},
    {"id": "t5", "title": "Task 5", "status": "open", "priority": "P1", "dependsOn": ["t4"]}
  ]
}
EOF
    run validate_prd "prd.json"
    [ "$status" -eq 0 ]
}
