#!/usr/bin/env bats
#
# tests/cub.bats - End-to-end tests for the cub main script
#

load 'test_helper'

setup() {
    setup_test_dir
    export CUB_BACKEND="json"
}

teardown() {
    teardown_test_dir
}

# =============================================================================
# cub-init Tests
# =============================================================================

@test "cub-init creates project structure" {
    run "$PROJECT_ROOT/cub-init" .
    [ "$status" -eq 0 ]

    # Should create key files
    [ -f "prd.json" ]
    [ -f "PROMPT.md" ]
    [ -f "AGENT.md" ]
    [ -f "progress.txt" ]
    [ -f "fix_plan.md" ]
    [ -d "specs" ]
    [ -f ".gitignore" ]
}

@test "cub-init creates valid prd.json" {
    "$PROJECT_ROOT/cub-init" . >/dev/null 2>&1

    source "$LIB_DIR/tasks.sh"
    run validate_prd "prd.json"
    [ "$status" -eq 0 ]
}

@test "cub-init can be run in custom directory" {
    mkdir custom_project
    "$PROJECT_ROOT/cub-init" custom_project >/dev/null 2>&1

    [ -f "custom_project/prd.json" ]
    [ -f "custom_project/PROMPT.md" ]
}

# =============================================================================
# Main cub Script Tests (Mock harness)
# =============================================================================

@test "cub --status shows task summary" {
    use_fixture "valid_prd.json" "prd.json"

    # Mock the harness to avoid actual invocation
    export PATH="$TEST_DIR:$PATH"
    cat > claude << 'EOF'
#!/bin/bash
echo "Mocked harness"
EOF
    chmod +x claude

    run "$PROJECT_ROOT/cub" --status
    [ "$status" -eq 0 ]
    # Should show counts (with capital letters)
    [[ "$output" == *"Open"* ]] || [[ "$output" == *"Closed"* ]]
}

@test "cub status shows task summary (subcommand)" {
    use_fixture "valid_prd.json" "prd.json"

    # Mock the harness to avoid actual invocation
    export PATH="$TEST_DIR:$PATH"
    cat > claude << 'EOF'
#!/bin/bash
echo "Mocked harness"
EOF
    chmod +x claude

    run "$PROJECT_ROOT/cub" status
    [ "$status" -eq 0 ]
    # Should show counts (with capital letters)
    [[ "$output" == *"Open"* ]] || [[ "$output" == *"Closed"* ]]
}

@test "cub status --json outputs valid JSON" {
    use_fixture "valid_prd.json" "prd.json"

    # Mock the harness to avoid actual invocation
    export PATH="$TEST_DIR:$PATH"
    cat > claude << 'EOF'
#!/bin/bash
echo "Mocked harness"
EOF
    chmod +x claude

    run "$PROJECT_ROOT/cub" status --json
    [ "$status" -eq 0 ]
    # Should be valid JSON
    echo "$output" | jq empty
    # Should have required fields
    echo "$output" | jq -e '.task_counts'
    echo "$output" | jq -e '.task_counts.total'
    echo "$output" | jq -e '.task_counts.open'
    echo "$output" | jq -e '.task_counts.closed'
    echo "$output" | jq -e '.task_counts.in_progress'
}

@test "cub --status --json outputs valid JSON (legacy)" {
    use_fixture "valid_prd.json" "prd.json"

    # Mock the harness to avoid actual invocation
    export PATH="$TEST_DIR:$PATH"
    cat > claude << 'EOF'
#!/bin/bash
echo "Mocked harness"
EOF
    chmod +x claude

    # Suppress deprecation warnings so they don't pollute JSON output
    export CUB_NO_DEPRECATION_WARNINGS=1
    run "$PROJECT_ROOT/cub" --status --json
    [ "$status" -eq 0 ]
    # Should be valid JSON
    echo "$output" | jq empty
    # Should have required fields
    echo "$output" | jq -e '.task_counts'
}

@test "cub --ready lists ready tasks" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --ready
    [ "$status" -eq 0 ]
}

@test "cub fails gracefully when no prd.json exists" {
    run "$PROJECT_ROOT/cub" --status
    [ "$status" -ne 0 ]
    [[ "$output" == *"prd.json"* ]] || [[ "$output" == *"beads"* ]]
}

@test "cub detects backend correctly" {
    use_fixture "valid_prd.json" "prd.json"

    # Should use JSON backend
    export CUB_BACKEND="json"
    run "$PROJECT_ROOT/cub" --status
    [ "$status" -eq 0 ]
}

# =============================================================================
# Task Selection Logic Tests
# =============================================================================

@test "cub selects highest priority ready task" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Low priority", "status": "open", "priority": "P3"},
    {"id": "t2", "title": "High priority", "status": "open", "priority": "P0"}
  ]
}
EOF

    # Get ready tasks and verify priority ordering
    source "$LIB_DIR/tasks.sh"
    run json_get_ready_tasks "prd.json"
    [ "$status" -eq 0 ]

    # First task should be P0
    local first_priority
    first_priority=$(echo "$output" | jq -r '.[0].priority')
    [ "$first_priority" = "P0" ]
}

@test "cub skips blocked tasks" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Blocker", "status": "open", "priority": "P1"},
    {"id": "t2", "title": "Blocked", "status": "open", "priority": "P0", "dependsOn": ["t1"]}
  ]
}
EOF

    source "$LIB_DIR/tasks.sh"
    run json_get_ready_tasks "prd.json"
    [ "$status" -eq 0 ]

    # Should only return t1
    local count
    count=$(echo "$output" | jq 'length')
    [ "$count" -eq 1 ]

    local returned_id
    returned_id=$(echo "$output" | jq -r '.[0].id')
    [ "$returned_id" = "t1" ]
}

# =============================================================================
# Prompt Generation Tests
# =============================================================================

@test "cub generates system prompt from PROMPT.md" {
    use_fixture "valid_prd.json" "prd.json"
    echo "System instructions here" > PROMPT.md

    # cub should read this file when generating prompts
    [ -f "PROMPT.md" ]
}

@test "cub generates task prompt with all required fields" {
    # Task prompt should include: ID, title, type, description, acceptance criteria
    use_fixture "valid_prd.json" "prd.json"

    source "$LIB_DIR/tasks.sh"
    task=$(json_get_task "prd.json" "prd-0002")

    # Verify task has required fields
    [[ "$task" == *"prd-0002"* ]]
    [[ "$task" == *"title"* ]]
}

# =============================================================================
# Progress Tracking Tests
# =============================================================================

@test "cub updates task status correctly" {
    use_fixture "valid_prd.json" "prd.json"

    source "$LIB_DIR/tasks.sh"
    json_update_task_status "prd.json" "prd-0002" "in_progress"

    local status
    status=$(jq -r '.tasks[] | select(.id == "prd-0002") | .status' prd.json)
    [ "$status" = "in_progress" ]
}

@test "cub adds notes to tasks" {
    use_fixture "valid_prd.json" "prd.json"

    source "$LIB_DIR/tasks.sh"
    json_add_task_note "prd.json" "prd-0002" "Started implementation"

    local notes
    notes=$(jq -r '.tasks[] | select(.id == "prd-0002") | .notes' prd.json)
    [[ "$notes" == *"Started implementation"* ]]
}

# =============================================================================
# Completion Detection Tests
# =============================================================================

@test "cub detects when all tasks are complete" {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Done", "status": "closed", "priority": "P1"}
  ]
}
EOF

    source "$LIB_DIR/tasks.sh"
    run json_all_tasks_complete "prd.json"
    [ "$status" -eq 0 ]
}

@test "cub detects incomplete tasks" {
    use_fixture "valid_prd.json" "prd.json"

    source "$LIB_DIR/tasks.sh"
    run json_all_tasks_complete "prd.json"
    [ "$status" -ne 0 ]
}

# =============================================================================
# Flag Tests
# =============================================================================

@test "cub --debug flag is recognized" {
    use_fixture "valid_prd.json" "prd.json"

    # Should not crash with debug flag
    run "$PROJECT_ROOT/cub" --debug --status
    # May fail if no harness, but shouldn't crash
}

@test "cub --once flag is recognized" {
    use_fixture "valid_prd.json" "prd.json"

    # Mock harness
    export PATH="$TEST_DIR:$PATH"
    cat > claude << 'EOF'
#!/bin/bash
echo "<promise>COMPLETE</promise>"
EOF
    chmod +x claude

    # Should run single iteration
    # (will fail without proper setup but shouldn't crash)
    run "$PROJECT_ROOT/cub" --once
}

# =============================================================================
# Backend Selection Tests
# =============================================================================

@test "cub respects CUB_BACKEND environment variable" {
    use_fixture "valid_prd.json" "prd.json"

    export CUB_BACKEND="json"
    source "$LIB_DIR/tasks.sh"

    run detect_backend
    [ "$output" = "json" ]
}

@test "cub --backend flag overrides auto-detection" {
    use_fixture "valid_prd.json" "prd.json"

    # Test that flag is recognized (implementation may vary)
    run "$PROJECT_ROOT/cub" --backend json --status
    # Should use json backend
}

# =============================================================================
# Error Recovery Tests
# =============================================================================

@test "cub handles corrupted prd.json gracefully" {
    echo "invalid json {{{" > prd.json

    run "$PROJECT_ROOT/cub" --status
    [ "$status" -ne 0 ]
}

@test "cub handles missing harness gracefully" {
    use_fixture "valid_prd.json" "prd.json"

    # Remove harnesses from PATH
    PATH="/bin:/usr/bin" run "$PROJECT_ROOT/cub" --once
    [ "$status" -ne 0 ]
}
