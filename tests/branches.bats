#!/usr/bin/env bats

# Test suite for lib/branches.sh - branch-epic binding management

load test_helper

# Setup function runs before each test
setup() {
    # Create temp directory for test files
    TEST_TEMP_DIR="${BATS_TMPDIR}/branches_test_$$"
    mkdir -p "${TEST_TEMP_DIR}"

    # Create a mock .beads directory
    mkdir -p "${TEST_TEMP_DIR}/.beads"

    # Source the branches library
    source "${LIB_DIR}/branches.sh"
}

# Teardown function runs after each test
teardown() {
    # Clean up test directories
    rm -rf "$TEST_TEMP_DIR" 2>/dev/null || true
}

# =============================================================================
# branches_init tests
# =============================================================================

@test "branches_init creates branches.yaml in .beads directory" {
    run branches_init "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ -f "${TEST_TEMP_DIR}/.beads/branches.yaml" ]]
}

@test "branches_init fails if .beads directory does not exist" {
    rm -rf "${TEST_TEMP_DIR}/.beads"
    run branches_init "${TEST_TEMP_DIR}"
    [[ $status -eq 1 ]]
    [[ "$output" == *"ERROR: .beads directory does not exist"* ]]
}

@test "branches_init creates file with empty bindings array" {
    run branches_init "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]

    run branches_read "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ "$output" == *'"bindings":[]'* ]]
}

@test "branches_init is idempotent" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "test-epic" "test-branch" "main" "${TEST_TEMP_DIR}"

    # Init again should not overwrite
    branches_init "${TEST_TEMP_DIR}"

    run branches_get_branch "test-epic" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ "$output" == "test-branch" ]]
}

# =============================================================================
# branches_bind tests
# =============================================================================

@test "branches_bind creates a new binding" {
    branches_init "${TEST_TEMP_DIR}"

    run branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]

    run branches_get_branch "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ "$output" == "feature/v19" ]]
}

@test "branches_bind requires epic_id" {
    branches_init "${TEST_TEMP_DIR}"

    run branches_bind "" "feature/v19" "main" "${TEST_TEMP_DIR}"
    [[ $status -eq 1 ]]
    [[ "$output" == *"ERROR: epic_id is required"* ]]
}

@test "branches_bind prevents duplicate epic bindings" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"

    run branches_bind "cub-vd6" "another-branch" "main" "${TEST_TEMP_DIR}"
    [[ $status -eq 1 ]]
    [[ "$output" == *"already bound"* ]]
}

@test "branches_bind prevents duplicate branch bindings" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"

    run branches_bind "cub-vd7" "feature/v19" "main" "${TEST_TEMP_DIR}"
    [[ $status -eq 1 ]]
    [[ "$output" == *"already bound"* ]]
}

@test "branches_bind sets correct metadata fields" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "develop" "${TEST_TEMP_DIR}"

    run branches_get_binding "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]

    # Check all fields are present
    local binding="$output"
    [[ $(echo "$binding" | jq -r '.epic_id') == "cub-vd6" ]]
    [[ $(echo "$binding" | jq -r '.branch_name') == "feature/v19" ]]
    [[ $(echo "$binding" | jq -r '.base_branch') == "develop" ]]
    [[ $(echo "$binding" | jq -r '.status') == "active" ]]
    [[ $(echo "$binding" | jq '.merged') == "false" ]]
    [[ $(echo "$binding" | jq '.pr_number') == "null" ]]
    [[ $(echo "$binding" | jq -r '.created_at') =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T ]]
}

# =============================================================================
# branches_get_branch tests
# =============================================================================

@test "branches_get_branch returns branch for epic" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"

    run branches_get_branch "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ "$output" == "feature/v19" ]]
}

@test "branches_get_branch returns empty for unknown epic" {
    branches_init "${TEST_TEMP_DIR}"

    run branches_get_branch "unknown-epic" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ -z "$output" ]]
}

# =============================================================================
# branches_get_epic tests
# =============================================================================

@test "branches_get_epic returns epic for branch" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"

    run branches_get_epic "feature/v19" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ "$output" == "cub-vd6" ]]
}

@test "branches_get_epic returns empty for unknown branch" {
    branches_init "${TEST_TEMP_DIR}"

    run branches_get_epic "unknown-branch" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ -z "$output" ]]
}

# =============================================================================
# branches_list tests
# =============================================================================

@test "branches_list returns empty array when no bindings" {
    branches_init "${TEST_TEMP_DIR}"

    run branches_list "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ "$output" == "[]" ]]
}

@test "branches_list returns all bindings" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"
    branches_bind "cub-vd7" "feature/v20" "main" "${TEST_TEMP_DIR}"

    run branches_list "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]

    local count
    count=$(echo "$output" | jq 'length')
    [[ "$count" -eq 2 ]]
}

# =============================================================================
# branches_unbind tests
# =============================================================================

@test "branches_unbind removes a binding" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"

    run branches_unbind "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]

    run branches_get_branch "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ -z "$output" ]]
}

@test "branches_unbind handles non-existent binding gracefully" {
    branches_init "${TEST_TEMP_DIR}"

    run branches_unbind "unknown-epic" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ "$output" == *"WARNING: No binding found"* ]]
}

@test "branches_unbind requires epic_id" {
    branches_init "${TEST_TEMP_DIR}"

    run branches_unbind "" "${TEST_TEMP_DIR}"
    [[ $status -eq 1 ]]
    [[ "$output" == *"ERROR: epic_id is required"* ]]
}

# =============================================================================
# branches_update_pr tests
# =============================================================================

@test "branches_update_pr sets PR number" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"

    run branches_update_pr "cub-vd6" 42 "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]

    run branches_get_binding "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ $(echo "$output" | jq '.pr_number') == "42" ]]
}

@test "branches_update_pr clears PR number with null" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"
    branches_update_pr "cub-vd6" 42 "${TEST_TEMP_DIR}"

    run branches_update_pr "cub-vd6" null "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]

    run branches_get_binding "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ $(echo "$output" | jq '.pr_number') == "null" ]]
}

@test "branches_update_pr fails for non-existent binding" {
    branches_init "${TEST_TEMP_DIR}"

    run branches_update_pr "unknown-epic" 42 "${TEST_TEMP_DIR}"
    [[ $status -eq 1 ]]
    [[ "$output" == *"ERROR: No binding found"* ]]
}

# =============================================================================
# branches_update_status tests
# =============================================================================

@test "branches_update_status changes status" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"

    run branches_update_status "cub-vd6" "closed" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]

    run branches_get_binding "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ $(echo "$output" | jq -r '.status') == "closed" ]]
}

@test "branches_update_status sets merged flag when status is merged" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"

    run branches_update_status "cub-vd6" "merged" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]

    run branches_get_binding "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ $(echo "$output" | jq -r '.status') == "merged" ]]
    [[ $(echo "$output" | jq '.merged') == "true" ]]
}

# =============================================================================
# branches_by_status tests
# =============================================================================

@test "branches_by_status filters by status" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"
    branches_bind "cub-vd7" "feature/v20" "main" "${TEST_TEMP_DIR}"
    branches_update_status "cub-vd6" "merged" "${TEST_TEMP_DIR}"

    run branches_by_status "active" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ $(echo "$output" | jq 'length') -eq 1 ]]
    [[ $(echo "$output" | jq -r '.[0].epic_id') == "cub-vd7" ]]

    run branches_by_status "merged" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ $(echo "$output" | jq 'length') -eq 1 ]]
    [[ $(echo "$output" | jq -r '.[0].epic_id') == "cub-vd6" ]]
}

# =============================================================================
# YAML parsing tests
# =============================================================================

@test "branches reads and writes YAML correctly" {
    branches_init "${TEST_TEMP_DIR}"
    branches_bind "cub-vd6" "feature/v19" "main" "${TEST_TEMP_DIR}"

    # Verify file is valid YAML-ish format
    local content
    content=$(cat "${TEST_TEMP_DIR}/.beads/branches.yaml")
    [[ "$content" == *"bindings:"* ]]
    [[ "$content" == *"epic_id: cub-vd6"* ]]
    [[ "$content" == *"branch_name: feature/v19"* ]]

    # Verify we can read it back
    run branches_get_branch "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ "$output" == "feature/v19" ]]
}

@test "branches handles special characters in branch names" {
    branches_init "${TEST_TEMP_DIR}"

    run branches_bind "cub-vd6" "feature/v19-test_branch" "main" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]

    run branches_get_branch "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ "$output" == "feature/v19-test_branch" ]]
}

@test "branches handles forward slashes in branch names" {
    branches_init "${TEST_TEMP_DIR}"

    run branches_bind "cub-vd6" "cub/mink/20260114-165751" "main" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]

    run branches_get_branch "cub-vd6" "${TEST_TEMP_DIR}"
    [[ $status -eq 0 ]]
    [[ "$output" == "cub/mink/20260114-165751" ]]
}
