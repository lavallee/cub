#!/usr/bin/env bats
#
# prep.bats - Tests for the Vision-to-Tasks Prep (v0.14)
#
# Tests cover:
# - Session management functions
# - Prep stage commands (triage, architect, plan, bootstrap)
# - Unified prep command
# - Sessions management
# - Migration from chopshop
#

load test_helper

setup() {
    setup_test_dir

    # Source the prep command
    source "$LIB_DIR/xdg.sh"
    source "$LIB_DIR/config.sh"
    source "$LIB_DIR/session.sh"
    source "$LIB_DIR/cmd_prep.sh"

    # Set PROJECT_DIR for pipeline functions
    export PROJECT_DIR="$TEST_DIR"

    # Create minimal config for testing
    mkdir -p "$TEST_DIR/.cub"

    # Mock the log functions for cleaner test output
    log_info() { :; }
    log_warn() { :; }
    log_success() { :; }
    log_debug() { :; }
    _log_error_console() { echo "ERROR: $1" >&2; }
}

teardown() {
    teardown_test_dir
}

# ============================================================================
# Session Management Tests
# ============================================================================

@test "pipeline: new_session_id generates valid session ID format" {
    local session_id
    session_id=$(pipeline_new_session_id)

    # Should match format: {name}-{YYYYMMDD-HHMMSS}
    [[ "$session_id" =~ ^[a-z0-9]+-[0-9]{8}-[0-9]{6}$ ]]
}

@test "pipeline: new_session_id uses provided project name" {
    local session_id
    session_id=$(pipeline_new_session_id "myproject")

    [[ "$session_id" =~ ^myproject-[0-9]{8}-[0-9]{6}$ ]]
}

@test "pipeline: create_session creates session directory" {
    local session_id
    session_id=$(pipeline_new_session_id)

    pipeline_create_session "$session_id"

    [[ -d "$TEST_DIR/.cub/sessions/$session_id" ]]
}

@test "pipeline: create_session creates session.json metadata" {
    local session_id
    session_id=$(pipeline_new_session_id)

    pipeline_create_session "$session_id"

    [[ -f "$TEST_DIR/.cub/sessions/$session_id/session.json" ]]

    # Verify JSON structure
    local status
    status=$(jq -r '.status' "$TEST_DIR/.cub/sessions/$session_id/session.json")
    [[ "$status" == "created" ]]
}

@test "pipeline: session_exists returns true for existing session" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    pipeline_session_exists "$session_id"
}

@test "pipeline: session_exists returns false for non-existing session" {
    ! pipeline_session_exists "nonexistent-session"
}

@test "pipeline: session_dir returns correct path" {
    local session_id="test-20260113-120000"
    local dir
    dir=$(pipeline_session_dir "$session_id")

    [[ "$dir" == "$TEST_DIR/.cub/sessions/$session_id" ]]
}

# ============================================================================
# Pipeline Stage Checkers Tests
# ============================================================================

@test "pipeline: has_triage returns false when triage.md missing" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    ! pipeline_has_triage "$session_id"
}

@test "pipeline: has_triage returns true when triage.md exists" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    touch "$TEST_DIR/.cub/sessions/$session_id/triage.md"

    pipeline_has_triage "$session_id"
}

@test "pipeline: has_architect returns false when architect.md missing" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    ! pipeline_has_architect "$session_id"
}

@test "pipeline: has_architect returns true when architect.md exists" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    touch "$TEST_DIR/.cub/sessions/$session_id/architect.md"

    pipeline_has_architect "$session_id"
}

@test "pipeline: has_plan returns false when plan.jsonl missing" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    ! pipeline_has_plan "$session_id"
}

@test "pipeline: has_plan returns true when plan.jsonl exists" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    touch "$TEST_DIR/.cub/sessions/$session_id/plan.jsonl"

    pipeline_has_plan "$session_id"
}

# ============================================================================
# Vision Document Finder Tests
# ============================================================================

@test "pipeline: find_vision finds explicit path" {
    local vision_file="$TEST_DIR/my-vision.md"
    echo "# My Vision" > "$vision_file"

    local found
    found=$(pipeline_find_vision "$vision_file")

    [[ "$found" == "$vision_file" ]]
}

@test "pipeline: find_vision finds VISION.md in project root" {
    echo "# Project Vision" > "$TEST_DIR/VISION.md"

    local found
    found=$(pipeline_find_vision)

    [[ "$found" == "$TEST_DIR/VISION.md" ]]
}

@test "pipeline: find_vision finds docs/PRD.md" {
    mkdir -p "$TEST_DIR/docs"
    echo "# PRD" > "$TEST_DIR/docs/PRD.md"

    local found
    found=$(pipeline_find_vision)

    [[ "$found" == "$TEST_DIR/docs/PRD.md" ]]
}

@test "pipeline: find_vision falls back to README.md" {
    echo "# README" > "$TEST_DIR/README.md"

    local found
    found=$(pipeline_find_vision)

    [[ "$found" == "$TEST_DIR/README.md" ]]
}

@test "pipeline: find_vision returns error when no document found" {
    ! pipeline_find_vision
}

@test "pipeline: find_vision priority: VISION.md over docs/PRD.md" {
    echo "# Vision" > "$TEST_DIR/VISION.md"
    mkdir -p "$TEST_DIR/docs"
    echo "# PRD" > "$TEST_DIR/docs/PRD.md"

    local found
    found=$(pipeline_find_vision)

    [[ "$found" == "$TEST_DIR/VISION.md" ]]
}

# ============================================================================
# Command Help Tests
# ============================================================================

@test "pipeline: triage --help shows usage" {
    run cmd_triage --help

    [[ "$status" -eq 0 ]]
    [[ "$output" =~ "Stage 1: Requirements Refinement" ]]
}

@test "pipeline: triage rejects invalid depth" {
    run cmd_triage --depth invalid

    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "Invalid depth" ]]
}

@test "pipeline: triage --session fails for non-existent session" {
    run cmd_triage --session "nonexistent-session"

    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "Session not found" ]]
}

@test "pipeline: architect --help shows usage" {
    run cmd_architect --help

    [[ "$status" -eq 0 ]]
    [[ "$output" =~ "Stage 2: Technical Design" ]]
}

@test "pipeline: architect fails without triage" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    run cmd_architect "$session_id"

    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "Triage not complete" ]]
}

@test "pipeline: plan --help shows usage" {
    run cmd_plan --help

    [[ "$status" -eq 0 ]]
    [[ "$output" =~ "Stage 3: Task Decomposition" ]]
}

@test "pipeline: plan rejects invalid granularity" {
    run cmd_plan --granularity invalid

    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "Invalid granularity" ]]
}

@test "pipeline: plan fails without architect" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"
    echo "# Triage" > "$TEST_DIR/.cub/sessions/$session_id/triage.md"

    run cmd_plan "$session_id"

    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "Architecture not complete" ]]
}

@test "pipeline: bootstrap --help shows usage" {
    run cmd_bootstrap --help

    [[ "$status" -eq 0 ]]
    [[ "$output" =~ "Stage 4: Transition to Execution" ]]
}

@test "pipeline: bootstrap fails without plan" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"
    echo "# Triage" > "$TEST_DIR/.cub/sessions/$session_id/triage.md"
    echo "# Architect" > "$TEST_DIR/.cub/sessions/$session_id/architect.md"

    run cmd_bootstrap "$session_id"

    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "Plan not complete" ]]
}

@test "prep: unified prep --help shows usage" {
    run cmd_prep --help

    [[ "$status" -eq 0 ]]
    [[ "$output" =~ "Run the complete Vision-to-Tasks prep pipeline" ]]
}

# ============================================================================
# Sessions Command Tests
# ============================================================================

@test "pipeline: sessions list shows no sessions when empty" {
    run cmd_sessions list

    [[ "$status" -eq 0 ]]
}

@test "pipeline: sessions show displays session details" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    run cmd_sessions show "$session_id"

    [[ "$status" -eq 0 ]]
    [[ "$output" =~ "$session_id" ]]
}

@test "pipeline: sessions delete removes session" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    [[ -d "$TEST_DIR/.cub/sessions/$session_id" ]]

    run cmd_sessions delete "$session_id"

    [[ "$status" -eq 0 ]]
    [[ ! -d "$TEST_DIR/.cub/sessions/$session_id" ]]
}

@test "pipeline: sessions delete fails for non-existent session" {
    run cmd_sessions delete "nonexistent"

    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "Session not found" ]]
}

# ============================================================================
# Migration Command Tests
# ============================================================================

@test "pipeline: migrate help shows usage" {
    run cmd_migrate help

    [[ "$status" -eq 0 ]]
    [[ "$output" =~ "Migrate from other planning systems" ]]
}

@test "pipeline: migrate chopshop fails when no .chopshop directory" {
    run cmd_migrate chopshop

    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "No .chopshop directory" ]]
}

@test "pipeline: migrate chopshop copies session files" {
    # Create .chopshop structure
    mkdir -p "$TEST_DIR/.chopshop/sessions/test-session"
    echo "# Triage" > "$TEST_DIR/.chopshop/sessions/test-session/triage-output.md"
    echo "# Architect" > "$TEST_DIR/.chopshop/sessions/test-session/architect-output.md"

    run cmd_migrate chopshop

    [[ "$status" -eq 0 ]]

    # Verify files were copied and renamed
    [[ -f "$TEST_DIR/.cub/sessions/test-session/triage.md" ]]
    [[ -f "$TEST_DIR/.cub/sessions/test-session/architect.md" ]]
}

# ============================================================================
# Validation Command Tests
# ============================================================================

@test "pipeline: validate --help shows usage" {
    run cmd_validate --help

    [[ "$status" -eq 0 ]]
    [[ "$output" =~ "Validate beads state" ]]
}

@test "pipeline: validate fails without .beads directory" {
    run cmd_validate

    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "No .beads directory" ]]
}

# ============================================================================
# Session Update Tests
# ============================================================================

@test "pipeline: update_session updates stage status" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    pipeline_update_session "$session_id" "triage" "complete"

    local status
    status=$(jq -r '.stages.triage' "$TEST_DIR/.cub/sessions/$session_id/session.json")
    [[ "$status" == "complete" ]]
}

@test "pipeline: session_info returns session metadata" {
    local session_id
    session_id=$(pipeline_new_session_id)
    pipeline_create_session "$session_id"

    local info
    info=$(pipeline_session_info "$session_id")

    echo "$info" | jq -e '.id' > /dev/null
    echo "$info" | jq -e '.created' > /dev/null
    echo "$info" | jq -e '.status' > /dev/null
}
