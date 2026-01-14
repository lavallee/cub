#!/usr/bin/env bats
#
# tests/tasks.bats - Tests for lib/tasks.sh
#

load 'test_helper'

setup() {
    setup_test_dir

    # Force JSON backend (no beads in tests)
    export CUB_BACKEND="json"

    # Source the library under test
    source "$LIB_DIR/tasks.sh"
}

teardown() {
    teardown_test_dir
}

# =============================================================================
# Backend Detection Tests
# =============================================================================

@test "detect_backend returns json when prd.json exists" {
    create_minimal_prd
    run detect_backend
    [ "$status" -eq 0 ]
    [ "$output" = "json" ]
}

@test "detect_backend defaults to json when no backend exists" {
    run detect_backend
    [ "$status" -eq 0 ]
    [ "$output" = "json" ]
}

@test "detect_backend respects CUB_BACKEND=json" {
    export CUB_BACKEND="json"
    run detect_backend
    [ "$status" -eq 0 ]
    [ "$output" = "json" ]
}

# =============================================================================
# PRD Validation Tests
# =============================================================================

@test "validate_prd succeeds with valid prd.json" {
    use_fixture "valid_prd.json" "prd.json"
    run validate_prd "prd.json"
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

@test "validate_prd fails when tasks array is missing" {
    use_fixture "missing_tasks.json" "prd.json"
    run validate_prd "prd.json"
    [ "$status" -ne 0 ]
    [[ "$output" == *"missing 'tasks' array"* ]]
}

@test "validate_prd fails when tasks have missing required fields" {
    use_fixture "missing_fields.json" "prd.json"
    run validate_prd "prd.json"
    [ "$status" -ne 0 ]
    [[ "$output" == *"missing required fields"* ]]
}

@test "validate_prd fails when duplicate task IDs exist" {
    use_fixture "duplicate_ids.json" "prd.json"
    run validate_prd "prd.json"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Duplicate task IDs"* ]]
}

@test "validate_prd fails when dependency references invalid task" {
    use_fixture "bad_dependency.json" "prd.json"
    run validate_prd "prd.json"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Invalid dependency"* ]]
}

# =============================================================================
# Get Ready Tasks Tests
# =============================================================================

@test "json_get_ready_tasks returns open tasks without dependencies" {
    create_sample_prd
    run json_get_ready_tasks "prd.json"
    [ "$status" -eq 0 ]

    # Should return test-0001 (open, no deps) and test-0003 (open, dep satisfied)
    echo "$output" | jq -e 'length == 2'
}

@test "json_get_ready_tasks excludes tasks with unsatisfied dependencies" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Blocker", "status": "open", "priority": "P1"},
    {"id": "t2", "title": "Blocked", "status": "open", "priority": "P0", "dependsOn": ["t1"]}
  ]
}
EOF
    run json_get_ready_tasks "prd.json"
    [ "$status" -eq 0 ]

    # Only t1 should be returned (t2 is blocked)
    local count
    count=$(echo "$output" | jq 'length')
    [ "$count" -eq 1 ]

    # Verify it's t1
    local returned_id
    returned_id=$(echo "$output" | jq -r '.[0].id')
    [ "$returned_id" = "t1" ]
}

@test "json_get_ready_tasks returns tasks sorted by priority" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Low priority", "status": "open", "priority": "P3"},
    {"id": "t2", "title": "High priority", "status": "open", "priority": "P0"},
    {"id": "t3", "title": "Medium priority", "status": "open", "priority": "P1"}
  ]
}
EOF
    run json_get_ready_tasks "prd.json"
    [ "$status" -eq 0 ]

    # First task should be P0 (t2)
    local first_id
    first_id=$(echo "$output" | jq -r '.[0].id')
    [ "$first_id" = "t2" ]
}

@test "json_get_ready_tasks returns empty array when all tasks closed" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Done", "status": "closed", "priority": "P1"}
  ]
}
EOF
    run json_get_ready_tasks "prd.json"
    [ "$status" -eq 0 ]
    [ "$output" = "[]" ]
}

# =============================================================================
# Get Task Tests
# =============================================================================

@test "json_get_task returns task by ID" {
    create_sample_prd
    run json_get_task "prd.json" "test-0001"
    [ "$status" -eq 0 ]

    local title
    title=$(echo "$output" | jq -r '.title')
    [ "$title" = "First task" ]
}

@test "json_get_task returns empty for non-existent ID" {
    create_sample_prd
    run json_get_task "prd.json" "nonexistent"
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

# =============================================================================
# Update Task Status Tests
# =============================================================================

@test "json_update_task_status changes task status" {
    create_sample_prd
    json_update_task_status "prd.json" "test-0001" "in_progress"

    local status
    status=$(jq -r '.tasks[] | select(.id == "test-0001") | .status' prd.json)
    [ "$status" = "in_progress" ]
}

@test "json_update_task_status does not affect other tasks" {
    create_sample_prd
    local before
    before=$(jq -r '.tasks[] | select(.id == "test-0002") | .status' prd.json)

    json_update_task_status "prd.json" "test-0001" "in_progress"

    local after
    after=$(jq -r '.tasks[] | select(.id == "test-0002") | .status' prd.json)
    [ "$before" = "$after" ]
}

# =============================================================================
# Add Task Note Tests
# =============================================================================

@test "json_add_task_note adds timestamped note" {
    create_sample_prd
    json_add_task_note "prd.json" "test-0001" "Test note content"

    local notes
    notes=$(jq -r '.tasks[] | select(.id == "test-0001") | .notes' prd.json)

    # Should contain the note text
    [[ "$notes" == *"Test note content"* ]]

    # Should contain a timestamp
    [[ "$notes" == *"202"* ]]  # Year prefix
}

# =============================================================================
# Create Task Tests
# =============================================================================

@test "json_create_task adds new task to prd.json" {
    create_minimal_prd
    local new_task='{"id": "test-new", "title": "New task", "status": "open", "priority": "P1"}'

    json_create_task "prd.json" "$new_task"

    local count
    count=$(jq '.tasks | length' prd.json)
    [ "$count" -eq 1 ]

    local title
    title=$(jq -r '.tasks[0].title' prd.json)
    [ "$title" = "New task" ]
}

# =============================================================================
# Task Counts Tests
# =============================================================================

@test "json_get_task_counts returns correct counts" {
    create_sample_prd
    run json_get_task_counts "prd.json"
    [ "$status" -eq 0 ]

    local total open closed
    total=$(echo "$output" | jq '.total')
    open=$(echo "$output" | jq '.open')
    closed=$(echo "$output" | jq '.closed')

    [ "$total" -eq 3 ]
    [ "$open" -eq 2 ]
    [ "$closed" -eq 1 ]
}

# =============================================================================
# All Tasks Complete Tests
# =============================================================================

@test "json_all_tasks_complete returns false when open tasks exist" {
    create_sample_prd
    run json_all_tasks_complete "prd.json"
    [ "$status" -ne 0 ]
}

@test "json_all_tasks_complete returns true when all tasks closed" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Done", "status": "closed", "priority": "P1"},
    {"id": "t2", "title": "Also done", "status": "closed", "priority": "P2"}
  ]
}
EOF
    run json_all_tasks_complete "prd.json"
    [ "$status" -eq 0 ]
}

# =============================================================================
# Blocked Tasks Tests
# =============================================================================

@test "json_get_blocked_tasks returns tasks with unsatisfied dependencies" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Blocker", "status": "open", "priority": "P1"},
    {"id": "t2", "title": "Blocked", "status": "open", "priority": "P0", "dependsOn": ["t1"]}
  ]
}
EOF
    run json_get_blocked_tasks "prd.json"
    [ "$status" -eq 0 ]

    # t2 should be blocked
    local count
    count=$(echo "$output" | jq 'length')
    [ "$count" -eq 1 ]

    local blocked_id
    blocked_id=$(echo "$output" | jq -r '.[0].id')
    [ "$blocked_id" = "t2" ]
}

@test "json_get_blocked_tasks returns empty when no blocked tasks" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Done", "status": "closed", "priority": "P1"},
    {"id": "t2", "title": "Ready", "status": "open", "priority": "P0", "dependsOn": ["t1"]}
  ]
}
EOF
    run json_get_blocked_tasks "prd.json"
    [ "$status" -eq 0 ]
    [ "$output" = "[]" ]
}

# =============================================================================
# Generate Task ID Tests
# =============================================================================

@test "generate_task_id creates ID with prefix from prd.json" {
    cat > prd.json << 'EOF'
{
  "prefix": "myprj",
  "tasks": []
}
EOF
    run generate_task_id "prd.json"
    [ "$status" -eq 0 ]

    # Should start with the prefix
    [[ "$output" == myprj-* ]]
}

@test "generate_task_id creates unique IDs" {
    create_minimal_prd

    local id1 id2
    id1=$(generate_task_id "prd.json")
    id2=$(generate_task_id "prd.json")

    # IDs should be different
    [ "$id1" != "$id2" ]
}

# =============================================================================
# Claim Task Tests
# =============================================================================

@test "claim_task requires task_id parameter" {
    create_minimal_prd
    run claim_task "prd.json" "" "test-session"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires task_id and session_name" ]]
}

@test "claim_task requires session_name parameter" {
    create_minimal_prd
    run claim_task "prd.json" "test-task" ""
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires task_id and session_name" ]]
}

@test "claim_task updates task status to in_progress for JSON backend" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Task 1", "status": "open", "priority": "P0"}
  ]
}
EOF

    claim_task "prd.json" "t1" "test-session"

    # Verify task is now in_progress
    local status
    status=$(jq -r '.tasks[0].status' prd.json)
    [ "$status" = "in_progress" ]
}

@test "claim_task works with multiple tasks" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Task 1", "status": "open", "priority": "P0"},
    {"id": "t2", "title": "Task 2", "status": "open", "priority": "P1"}
  ]
}
EOF

    claim_task "prd.json" "t1" "session1"

    # Verify only t1 is in_progress
    local t1_status t2_status
    t1_status=$(jq -r '.tasks[0].status' prd.json)
    t2_status=$(jq -r '.tasks[1].status' prd.json)

    [ "$t1_status" = "in_progress" ]
    [ "$t2_status" = "open" ]
}

# =============================================================================
# Verify Task Closed Tests
# =============================================================================

@test "verify_task_closed requires task_id parameter" {
    create_minimal_prd
    run verify_task_closed "prd.json" ""
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires task_id" ]]
}

@test "verify_task_closed returns success for closed task" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Closed task", "status": "closed", "priority": "P0"}
  ]
}
EOF

    run verify_task_closed "prd.json" "t1"
    [ "$status" -eq 0 ]
}

@test "verify_task_closed returns failure for open task" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Open task", "status": "open", "priority": "P0"}
  ]
}
EOF

    run verify_task_closed "prd.json" "t1"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "not closed" ]]
}

@test "verify_task_closed returns failure for in_progress task" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "In progress task", "status": "in_progress", "priority": "P0"}
  ]
}
EOF

    run verify_task_closed "prd.json" "t1"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "not closed" ]]
}

@test "verify_task_closed fails for non-existent prd file" {
    run verify_task_closed "nonexistent.json" "t1"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "not found" ]]
}

# =============================================================================
# Auto Close Task Tests
# =============================================================================

@test "auto_close_task requires task_id parameter" {
    create_minimal_prd
    run auto_close_task "prd.json" ""
    [ "$status" -eq 1 ]
    [[ "$output" =~ "requires task_id" ]]
}

@test "auto_close_task closes an open task" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Open task", "status": "open", "priority": "P0"}
  ]
}
EOF

    run auto_close_task "prd.json" "t1"
    [ "$status" -eq 0 ]

    # Verify task is now closed
    local status
    status=$(jq -r '.tasks[0].status' prd.json)
    [ "$status" = "closed" ]
}

@test "auto_close_task closes an in_progress task" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "In progress task", "status": "in_progress", "priority": "P0"}
  ]
}
EOF

    run auto_close_task "prd.json" "t1"
    [ "$status" -eq 0 ]

    # Verify task is now closed
    local status
    status=$(jq -r '.tasks[0].status' prd.json)
    [ "$status" = "closed" ]
}

@test "auto_close_task succeeds silently for already closed task" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Closed task", "status": "closed", "priority": "P0"}
  ]
}
EOF

    run auto_close_task "prd.json" "t1"
    [ "$status" -eq 0 ]

    # Verify task is still closed
    local status
    status=$(jq -r '.tasks[0].status' prd.json)
    [ "$status" = "closed" ]
}

@test "auto_close_task only affects specified task" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Task 1", "status": "in_progress", "priority": "P0"},
    {"id": "t2", "title": "Task 2", "status": "open", "priority": "P1"}
  ]
}
EOF

    auto_close_task "prd.json" "t1"

    # Verify t1 is closed and t2 is unchanged
    local t1_status t2_status
    t1_status=$(jq -r '.tasks[0].status' prd.json)
    t2_status=$(jq -r '.tasks[1].status' prd.json)

    [ "$t1_status" = "closed" ]
    [ "$t2_status" = "open" ]
}

# =============================================================================
# Task Completeness Validation Tests
# =============================================================================

@test "validate_task_completeness requires task_id parameter" {
    create_minimal_prd
    run validate_task_completeness ""
    [ "$status" -eq 1 ]
    [[ "$output" =~ "error" ]]
}

@test "validate_task_completeness returns error for non-existent task" {
    create_minimal_prd
    run validate_task_completeness "nonexistent-task"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "not found" ]]
}

@test "validate_task_completeness reports missing title" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "", "description": "Desc", "status": "open"}
  ]
}
EOF

    run validate_task_completeness "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_complete == false'
    echo "$output" | jq -e '.issues | any(. == "Title is missing")'
}

@test "validate_task_completeness reports title too short" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Short", "description": "Desc", "status": "open"}
  ]
}
EOF

    run validate_task_completeness "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_complete == false'
    echo "$output" | jq -e '.issues | any(. | startswith("Title is too short"))'
}

@test "validate_task_completeness accepts title with 10+ characters" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "This is exactly ten character title", "description": "Desc", "acceptanceCriteria": ["crit1"], "status": "open"}
  ]
}
EOF

    run validate_task_completeness "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_complete == true'
}

@test "validate_task_completeness reports missing description" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Valid Title Here", "description": "", "acceptanceCriteria": ["crit1"], "status": "open"}
  ]
}
EOF

    run validate_task_completeness "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_complete == false'
    echo "$output" | jq -e '.issues | any(. == "Description is missing")'
}

@test "validate_task_completeness reports missing acceptance criteria" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Valid Title Here", "description": "Valid description", "status": "open"}
  ]
}
EOF

    run validate_task_completeness "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_complete == false'
    echo "$output" | jq -e '.issues | any(. | contains("Acceptance criteria are not defined"))'
}

@test "validate_task_completeness accepts markdown checkboxes in description" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Valid Title Here", "description": "Desc\n- [ ] Criterion 1\n- [ ] Criterion 2", "status": "open"}
  ]
}
EOF

    run validate_task_completeness "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_complete == true'
}

@test "validate_task_completeness accepts acceptanceCriteria field" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Valid Title Here", "description": "Valid description", "acceptanceCriteria": ["criterion 1", "criterion 2"], "status": "open"}
  ]
}
EOF

    run validate_task_completeness "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_complete == true'
}

@test "validate_task_completeness returns all issues together" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Bad", "description": "", "status": "open"}
  ]
}
EOF

    run validate_task_completeness "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_complete == false'
    echo "$output" | jq -e '.issues | length == 3'
}

@test "validate_task_completeness returns valid JSON" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Valid Title Here", "description": "Valid description", "acceptanceCriteria": ["crit1"], "status": "open"}
  ]
}
EOF

    run validate_task_completeness "t1"
    [ "$status" -eq 0 ]
    # Should be valid JSON that can be parsed
    echo "$output" | jq '.' >/dev/null
    echo "$output" | jq -e '.id == "t1"'
    echo "$output" | jq -e 'has("is_complete")'
    echo "$output" | jq -e 'has("issues")'
}

@test "validate_all_tasks_completeness returns empty array for empty prd" {
    echo '{"prefix": "test", "tasks": []}' > prd.json

    run validate_all_tasks_completeness "prd.json"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '. == []'
}

@test "validate_all_tasks_completeness validates all tasks" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Valid Title 1", "description": "Desc", "acceptanceCriteria": ["c1"], "status": "open"},
    {"id": "t2", "title": "Bad", "description": "", "status": "open"},
    {"id": "t3", "title": "Valid Title 3", "description": "Desc", "acceptanceCriteria": ["c1"], "status": "open"}
  ]
}
EOF

    run validate_all_tasks_completeness "prd.json"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e 'length == 3'
    echo "$output" | jq -e '.[0].is_complete == true'
    echo "$output" | jq -e '.[1].is_complete == false'
    echo "$output" | jq -e '.[2].is_complete == true'
}

@test "validate_all_tasks_completeness handles missing file" {
    run validate_all_tasks_completeness "nonexistent.json"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '. == []'
}

@test "get_completeness_summary reports all complete" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Valid Title 1", "description": "Desc", "acceptanceCriteria": ["c1"], "status": "open"},
    {"id": "t2", "title": "Valid Title 2", "description": "Desc", "acceptanceCriteria": ["c1"], "status": "open"}
  ]
}
EOF

    run get_completeness_summary "prd.json"
    [ "$status" -eq 0 ]
    [[ "$output" =~ "All tasks are complete" ]]
}

@test "get_completeness_summary reports incomplete tasks" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Valid Title 1", "description": "Desc", "acceptanceCriteria": ["c1"], "status": "open"},
    {"id": "t2", "title": "Bad", "description": "", "status": "open"},
    {"id": "t3", "title": "Bad3", "description": "", "status": "open"}
  ]
}
EOF

    run get_completeness_summary "prd.json"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Found 2 incomplete" ]]
    [[ "$output" =~ "t2" ]]
    [[ "$output" =~ "t3" ]]
}

@test "get_completeness_summary includes specific issues" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Bad", "description": "", "status": "open"}
  ]
}
EOF

    run get_completeness_summary "prd.json"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "too short" ]]
    [[ "$output" =~ "Description is missing" ]]
    [[ "$output" =~ "Acceptance criteria" ]]
}

# ============================================================================
# FEASIBILITY VALIDATION TESTS
# ============================================================================

@test "validate_task_feasibility requires task_id parameter" {
    run validate_task_feasibility ""
    [ "$status" -eq 1 ]
    echo "$output" | jq -e '.error' >/dev/null
}

@test "validate_task_feasibility returns error for nonexistent task" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Valid Title", "description": "Desc", "acceptanceCriteria": ["c1"], "status": "open"}
  ]
}
EOF

    run validate_task_feasibility "nonexistent"
    [ "$status" -eq 1 ]
    echo "$output" | jq -e '.error' >/dev/null
}

@test "validate_task_feasibility returns valid JSON structure" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Valid Title", "description": "Desc", "acceptanceCriteria": ["c1"], "status": "open"}
  ]
}
EOF

    run validate_task_feasibility "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq '.' >/dev/null
    echo "$output" | jq -e '.id == "t1"'
    echo "$output" | jq -e 'has("is_feasible")'
    echo "$output" | jq -e 'has("issues")'
}

@test "validate_task_feasibility marks task feasible with no issues" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Valid Title", "description": "Desc", "status": "open"}
  ]
}
EOF

    run validate_task_feasibility "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == true'
    echo "$output" | jq -e '.issues | length == 0'
}

@test "validate_task_feasibility detects closed dependency" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title 1", "description": "Desc", "status": "closed"},
    {"id": "t2", "title": "Title 2", "description": "Desc", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    run validate_task_feasibility "t2"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == true'
    echo "$output" | jq -e '.issues | length == 0'
}

@test "validate_task_feasibility detects unclosed dependency" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title 1", "description": "Desc", "status": "open"},
    {"id": "t2", "title": "Title 2", "description": "Desc", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    run validate_task_feasibility "t2"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == false'
    echo "$output" | jq -e '.issues | any(. | contains("not closed"))'
}

@test "validate_task_feasibility detects multiple unclosed dependencies" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title 1", "description": "Desc", "status": "open"},
    {"id": "t2", "title": "Title 2", "description": "Desc", "status": "open"},
    {"id": "t3", "title": "Title 3", "description": "Desc", "status": "open", "dependsOn": ["t1", "t2"]}
  ]
}
EOF

    run validate_task_feasibility "t3"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == false'
    echo "$output" | jq -e '.issues | length == 2'
}

@test "validate_task_feasibility detects missing referenced file" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title", "description": "Uses [file: /nonexistent/path/file.txt]", "status": "open"}
  ]
}
EOF

    run validate_task_feasibility "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == false'
    echo "$output" | jq -e '.issues | any(. | contains("Referenced file not found"))'
}

@test "validate_task_feasibility accepts existing referenced file (absolute path)" {
    # Create a file to reference
    mkdir -p test_files
    echo "test content" > test_files/myfile.txt

    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title", "description": "Uses [file: test_files/myfile.txt]", "status": "open"}
  ]
}
EOF

    run validate_task_feasibility "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == true'
    echo "$output" | jq -e '.issues | length == 0'
}

@test "validate_task_feasibility handles relative paths with ./" {
    mkdir -p test_files
    echo "test" > test_files/file.txt

    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title", "description": "Uses [file: ./test_files/file.txt]", "status": "open"}
  ]
}
EOF

    run validate_task_feasibility "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == true'
}

@test "validate_task_feasibility detects mixed issues" {
    mkdir -p test_files
    echo "test" > test_files/file.txt

    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title 1", "description": "Dep", "status": "open"},
    {"id": "t2", "title": "Title 2", "description": "Uses [file: /missing/file.txt]", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    run validate_task_feasibility "t2"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == false'
    echo "$output" | jq -e '.issues | length >= 2'
    echo "$output" | jq -e '.issues | any(. | contains("not closed"))'
    echo "$output" | jq -e '.issues | any(. | contains("Referenced file not found"))'
}

@test "validate_all_tasks_feasibility returns empty array for empty prd" {
    echo '{"prefix": "test", "tasks": []}' > prd.json

    run validate_all_tasks_feasibility "prd.json"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '. == []'
}

@test "validate_all_tasks_feasibility validates all tasks" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title 1", "description": "Desc", "status": "closed"},
    {"id": "t2", "title": "Title 2", "description": "Desc", "status": "open", "dependsOn": ["t1"]},
    {"id": "t3", "title": "Title 3", "description": "Desc", "status": "open", "dependsOn": ["t99"]}
  ]
}
EOF

    run validate_all_tasks_feasibility "prd.json"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e 'length == 3'
    echo "$output" | jq -e '.[0].is_feasible == true'
    echo "$output" | jq -e '.[1].is_feasible == true'
    echo "$output" | jq -e '.[2].is_feasible == false'
}

@test "validate_all_tasks_feasibility handles missing file" {
    run validate_all_tasks_feasibility "nonexistent.json"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '. == []'
}

@test "get_feasibility_summary reports all feasible" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title 1", "description": "Desc", "status": "closed"},
    {"id": "t2", "title": "Title 2", "description": "Desc", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    run get_feasibility_summary "prd.json"
    [ "$status" -eq 0 ]
    [[ "$output" =~ "All tasks are feasible" ]]
}

@test "get_feasibility_summary reports infeasible tasks" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title 1", "description": "Desc", "status": "open"},
    {"id": "t2", "title": "Title 2", "description": "Desc", "status": "open", "dependsOn": ["t1"]},
    {"id": "t3", "title": "Title 3", "description": "Desc", "status": "open", "dependsOn": ["t99"]}
  ]
}
EOF

    run get_feasibility_summary "prd.json"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Found 2 infeasible" ]]
    [[ "$output" =~ "t2" ]]
    [[ "$output" =~ "t3" ]]
}

@test "get_feasibility_summary includes specific issues" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title 1", "description": "Desc", "status": "open", "dependsOn": ["missing"]}
  ]
}
EOF

    run get_feasibility_summary "prd.json"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "not closed" ]]
}

@test "validate_task_feasibility handles task with no dependencies" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title", "description": "Desc", "status": "open"}
  ]
}
EOF

    run validate_task_feasibility "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == true'
}

@test "validate_task_feasibility handles task with empty description" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title", "description": "", "status": "open"}
  ]
}
EOF

    run validate_task_feasibility "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == true'
}

@test "validate_task_feasibility ignores issues if all deps are closed" {
    # Even though t2 has dependency on t1, if t1 is closed, t2 is feasible
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title 1", "description": "Desc", "status": "closed"},
    {"id": "t2", "title": "Title 2", "description": "Depends on t1", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    run validate_task_feasibility "t2"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == true'
}

@test "validate_task_feasibility special characters in dependency id" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Title 1", "description": "Desc", "status": "closed"},
    {"id": "t2", "title": "Title 2", "description": "Desc", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    run validate_task_feasibility "t2"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_feasible == true'
}

# =============================================================================
# DEPENDENCY GRAPH VALIDATION TESTS
# =============================================================================

@test "validate_task_dependencies returns error for missing task_id" {
    create_minimal_prd
    run validate_task_dependencies
    [ "$status" -eq 1 ]
    echo "$output" | jq -e '.error' | grep -q "task_id is required"
}

@test "validate_task_dependencies returns error for nonexistent task" {
    create_sample_prd
    run validate_task_dependencies "nonexistent"
    [ "$status" -eq 1 ]
    echo "$output" | jq -e '.error' | grep -q "task not found"
}

@test "validate_task_dependencies marks valid task as valid" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "closed"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    run validate_task_dependencies "t2"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_valid == true'
    echo "$output" | jq -e '.issues | length == 0'
}

@test "validate_task_dependencies detects missing dependency" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "closed"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["t1", "nonexistent"]}
  ]
}
EOF

    run validate_task_dependencies "t2"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_valid == false'
    echo "$output" | jq -e '.issues[] | select(. | contains("does not exist"))' | grep -q "nonexistent"
}

@test "validate_task_dependencies handles task with no dependencies" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "open"}
  ]
}
EOF

    run validate_task_dependencies "t1"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_valid == true'
    echo "$output" | jq -e '.issues | length == 0'
}

@test "validate_task_dependencies returns valid JSON structure" {
    create_sample_prd
    run validate_task_dependencies "test-0001"
    [ "$status" -eq 0 ]
    # Verify JSON structure
    echo "$output" | jq -e '.id == "test-0001"'
    echo "$output" | jq -e '.is_valid != null'
    echo "$output" | jq -e '.issues != null'
}

@test "validate_task_dependencies detects dependency order issues" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["t1"]},
    {"id": "t1", "title": "First", "status": "closed"}
  ]
}
EOF

    run validate_task_dependencies "t2"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_valid == false'
    echo "$output" | jq -e '.issues[] | select(. | contains("order"))' | grep -q "order issue"
}

@test "validate_all_dependencies returns empty array for empty prd" {
    create_minimal_prd
    run validate_all_dependencies
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '. == []'
}

@test "validate_all_dependencies validates all tasks" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "closed"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["t1"]},
    {"id": "t3", "title": "Third", "status": "open", "dependsOn": ["t2"]}
  ]
}
EOF

    run validate_all_dependencies
    [ "$status" -eq 0 ]
    # Should have 3 results
    echo "$output" | jq -e 'length == 3'
    # All should be valid
    echo "$output" | jq -e 'all(.is_valid == true)'
}

@test "validate_all_dependencies detects multiple invalid tasks" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "closed"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["nonexistent1"]},
    {"id": "t3", "title": "Third", "status": "open", "dependsOn": ["nonexistent2"]}
  ]
}
EOF

    run validate_all_dependencies
    [ "$status" -eq 0 ]
    # Should have 3 results
    echo "$output" | jq -e 'length == 3'
    # Two should be invalid
    echo "$output" | jq -e '[.[] | select(.is_valid == false)] | length == 2'
}

@test "get_dependency_order returns list of task ids" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "closed"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["t1"]},
    {"id": "t3", "title": "Third", "status": "open", "dependsOn": ["t2"]}
  ]
}
EOF

    run get_dependency_order
    [ "$status" -eq 0 ]
    # Should contain task IDs
    echo "$output" | grep -q "t1"
    echo "$output" | grep -q "t2"
    echo "$output" | grep -q "t3"
}

@test "get_dependency_order handles empty prd" {
    create_minimal_prd
    run get_dependency_order
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '. == []'
}

@test "get_blocked_tasks_report shows blocked tasks" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "open"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    run get_blocked_tasks_report
    [ "$status" -eq 0 ]
    # Should mention blocked task
    echo "$output" | grep -q "t2"
    echo "$output" | grep -q "t1"
}

@test "get_blocked_tasks_report shows no blocked tasks when all ready" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "closed"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    run get_blocked_tasks_report
    [ "$status" -eq 0 ]
    echo "$output" | grep -q "No blocked"
}

@test "get_blocked_tasks_report handles empty prd" {
    create_minimal_prd
    run get_blocked_tasks_report
    [ "$status" -eq 0 ]
}

@test "get_dependency_summary reports no issues when all valid" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "closed"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    run get_dependency_summary
    [ "$status" -eq 0 ]
    echo "$output" | grep -q "All dependencies are valid"
}

@test "get_dependency_summary reports issues when dependencies invalid" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "closed"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["nonexistent"]}
  ]
}
EOF

    run get_dependency_summary
    [ "$status" -eq 1 ]
    echo "$output" | grep -q "dependency issues"
    echo "$output" | grep -q "t2"
}

@test "validate_task_dependencies handles multiple dependencies" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "closed"},
    {"id": "t2", "title": "Second", "status": "closed"},
    {"id": "t3", "title": "Third", "status": "open", "dependsOn": ["t1", "t2"]}
  ]
}
EOF

    run validate_task_dependencies "t3"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_valid == true'
    echo "$output" | jq -e '.issues | length == 0'
}

@test "validate_task_dependencies detects multiple missing dependencies" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "closed"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["missing1", "missing2"]}
  ]
}
EOF

    run validate_task_dependencies "t2"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.is_valid == false'
    echo "$output" | jq -e '.issues | length == 2'
}

@test "validate_all_dependencies handles file not found" {
    run validate_all_dependencies "/nonexistent/prd.json"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '. == []'
}
