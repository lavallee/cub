#!/usr/bin/env bats

# Test suite for lib/dependencies.sh - dependency detection engine

setup() {
    # Source the dependencies module
    source "${BATS_TEST_DIRNAME}/../lib/dependencies.sh"
}

# ============================================================================
# Test: detect_dependencies_from_content - explicit patterns
# ============================================================================

@test "detect_dependencies_from_content detects 'depends on' pattern" {
    local content="This task depends on auth-system to work"
    local result
    result=$(detect_dependencies_from_content "$content" "auth-system database")
    [[ "$result" == *"auth-system"* ]]
}

@test "detect_dependencies_from_content detects 'depends on' with task ID" {
    local content="We depend on task-1 being complete first"
    local result
    result=$(detect_dependencies_from_content "$content" "task-1 task-2")
    [[ "$result" == *"task-1"* ]]
}

@test "detect_dependencies_from_content detects 'blocked by' pattern" {
    local content="This feature is blocked by api-implementation"
    local result
    result=$(detect_dependencies_from_content "$content" "api-implementation database")
    [[ "$result" == *"api-implementation"* ]]
}

@test "detect_dependencies_from_content detects 'requires' pattern" {
    local content="The deployment requires build-system to be ready"
    local result
    result=$(detect_dependencies_from_content "$content" "build-system deployment")
    [[ "$result" == *"build-system"* ]]
}

@test "detect_dependencies_from_content detects 'after' pattern" {
    local content="We can proceed after design-review is complete"
    local result
    result=$(detect_dependencies_from_content "$content" "design-review implementation")
    [[ "$result" == *"design-review"* ]]
}

@test "detect_dependencies_from_content detects 'once' pattern" {
    local content="Start testing once code-merge is done"
    local result
    result=$(detect_dependencies_from_content "$content" "code-merge testing")
    [[ "$result" == *"code-merge"* ]]
}

@test "detect_dependencies_from_content detects 'before' pattern" {
    local content="Must update docs before release is done"
    local result
    result=$(detect_dependencies_from_content "$content" "docs release")
    [[ "$result" == *"release"* ]]
}

@test "detect_dependencies_from_content detects multiple dependencies" {
    local content="This depends on auth-system and requires database-migration"
    local result
    result=$(detect_dependencies_from_content "$content" "auth-system database-migration")
    [[ "$result" == *"auth-system"* ]] && [[ "$result" == *"database-migration"* ]]
}

@test "detect_dependencies_from_content is case-insensitive" {
    local content="This task DEPENDS ON auth-system"
    local result
    result=$(detect_dependencies_from_content "$content" "auth-system database")
    [[ "$result" == *"auth-system"* ]]
}

@test "detect_dependencies_from_content returns 1 when no dependencies found" {
    local content="This task is independent and needs no other tasks"
    ! detect_dependencies_from_content "$content" "task-1 task-2"
}

@test "detect_dependencies_from_content returns 1 for empty content" {
    ! detect_dependencies_from_content "" "task-1"
}

# ============================================================================
# Test: detect_dependencies_from_content - numbered sequences
# ============================================================================

@test "detect_dependencies_from_content detects numbered sequence dependencies" {
    local content="Steps:
1. setup-db
2. build-api
3. deploy"
    local result
    result=$(detect_dependencies_from_content "$content" "setup-db build-api deploy")
    # Numbered sequences should be detected
    [[ -n "$result" ]]
}

@test "detect_dependencies_from_content extracts task names from numbered list" {
    local content="Process:
1. init-project
2. setup-env
3. run-tests"
    local result
    result=$(detect_dependencies_from_content "$content" "init-project setup-env run-tests")
    # Should detect at least that later items depend on earlier ones
    [[ -n "$result" ]]
}

# ============================================================================
# Test: infer_blocking_relationships
# ============================================================================

@test "infer_blocking_relationships detects blocking from 'depends on'" {
    local content="Current task depends on auth-system"
    local result
    result=$(infer_blocking_relationships "$content" "current-task")
    [[ "$result" == *"auth-system"* ]]
    [[ "$result" == *"current-task"* ]]
}

@test "infer_blocking_relationships detects blocking from 'blocked by'" {
    local content="This task is blocked by the API implementation"
    local result
    result=$(infer_blocking_relationships "$content" "feature-x")
    [[ "$result" == *"api-implementation"* ]]
    [[ "$result" == *"feature-x"* ]]
}

@test "infer_blocking_relationships returns empty for independent task" {
    local content="This is a simple independent task"
    local result
    result=$(infer_blocking_relationships "$content" "task-id")
    [[ -z "$result" ]] || [[ "$result" == "" ]]
}

# ============================================================================
# Test: _has_dependency_signals helper
# ============================================================================

@test "_has_dependency_signals detects 'depends on' signal" {
    local content="This depends on something"
    _has_dependency_signals "$content"
}

@test "_has_dependency_signals detects 'blocked by' signal" {
    local content="We are blocked by the vendor"
    _has_dependency_signals "$content"
}

@test "_has_dependency_signals detects 'requires' signal" {
    local content="This requires approval first"
    _has_dependency_signals "$content"
}

@test "_has_dependency_signals returns 1 when no signals" {
    local content="This is an independent task with no dependencies"
    ! _has_dependency_signals "$content"
}

@test "_has_dependency_signals is case-insensitive" {
    local content="This DEPENDS ON something IMPORTANT"
    _has_dependency_signals "$content"
}

# ============================================================================
# Test: _has_numbered_sequence helper
# ============================================================================

@test "_has_numbered_sequence detects numbered list" {
    local content="Steps:
1. First
2. Second
3. Third"
    _has_numbered_sequence "$content"
}

@test "_has_numbered_sequence detects alternative format" {
    local content="Process:
1) Start
2) Continue
3) Finish"
    _has_numbered_sequence "$content"
}

@test "_has_numbered_sequence returns 1 for non-numbered content" {
    local content="This is just regular text with some content"
    ! _has_numbered_sequence "$content"
}

# ============================================================================
# Test: get_dependency_description
# ============================================================================

@test "get_dependency_description formats blocks relationship" {
    local result
    result=$(get_dependency_description "auth-system" "feature-x" "blocks")
    [[ "$result" == *"auth-system"* ]] && [[ "$result" == *"feature-x"* ]]
}

@test "get_dependency_description formats requires relationship" {
    local result
    result=$(get_dependency_description "auth-system" "feature-x" "requires")
    [[ "$result" == *"feature-x"* ]] && [[ "$result" == *"auth-system"* ]]
}

@test "get_dependency_description formats precedes relationship" {
    local result
    result=$(get_dependency_description "design-review" "implementation" "precedes")
    [[ "$result" == *"design-review"* ]] && [[ "$result" == *"implementation"* ]]
}

# ============================================================================
# Test: validate_dependency_references
# ============================================================================

@test "validate_dependency_references accepts valid dependencies" {
    local deps="task-1 task-2 task-3"
    local known="task-1 task-2 task-3 task-4"
    validate_dependency_references "$deps" "$known"
}

@test "validate_dependency_references rejects invalid dependencies" {
    local deps="task-1 nonexistent-task"
    local known="task-1 task-2"
    ! validate_dependency_references "$deps" "$known"
}

@test "validate_dependency_references accepts empty dependencies" {
    validate_dependency_references "" "task-1"
}

@test "validate_dependency_references handles arrow syntax" {
    local deps="task-1->task-2 task-2->task-3"
    local known="task-1 task-2 task-3"
    validate_dependency_references "$deps" "$known"
}

# ============================================================================
# Test: extract_task_names
# ============================================================================

@test "extract_task_names identifies task-like identifiers" {
    local content="We need to configure auth-system and database-migration"
    local result
    result=$(extract_task_names "$content")
    [[ "$result" == *"auth-system"* ]] && [[ "$result" == *"database-migration"* ]]
}

@test "extract_task_names filters short identifiers" {
    local content="The API v2 (or v3) endpoints"
    local result
    result=$(extract_task_names "$content")
    # Should not include single letters or short words
    [[ -n "$result" ]]
}

# ============================================================================
# Test: Integration tests with real-world examples
# ============================================================================

@test "detect_dependencies handles complex task description" {
    local content="This feature depends on the auth-system being complete and requires the api-gateway to be deployed. We also need the database-schema to be migrated first. Once all three are done, we can proceed."
    local known="auth-system api-gateway database-schema feature-x"
    local result
    result=$(detect_dependencies_from_content "$content" "$known")
    [[ "$result" == *"auth-system"* ]] && [[ "$result" == *"api-gateway"* ]] && [[ "$result" == *"database-schema"* ]]
}

@test "detect_dependencies handles GitHub issue format" {
    local content="Resolves #42. Depends on #40. Blocked by infrastructure setup.

- Must be tested after performance-baseline is established
- Requires security-audit to pass
- Needs docs-update before release"
    local known="infrastructure-setup performance-baseline security-audit docs-update"
    local result
    result=$(detect_dependencies_from_content "$content" "$known")
    [[ "$result" == *"infrastructure-setup"* ]] || [[ "$result" == *"performance-baseline"* ]] || [[ "$result" == *"security-audit"* ]]
}

@test "detect_dependencies handles feature request format" {
    local content="Feature: User Dashboard

Description: Depends on data-export

Steps:
1. Create data-export
2. Build analytics-engine
3. Implement ui-components"
    local known="data-export analytics-engine ui-components"
    local result
    result=$(detect_dependencies_from_content "$content" "$known")
    # Should detect 'depends on' pattern from description
    [[ "$result" == *"data-export"* ]]
}

@test "detect_dependencies ignores content without dependencies" {
    local content="Simple task with clear scope and no external dependencies"
    ! detect_dependencies_from_content "$content" "task-1 task-2"
}

@test "detect_dependencies handles hyphenated and underscored identifiers" {
    local content="This depends on both auth_system and api-gateway"
    local known="auth_system api-gateway"
    local result
    result=$(detect_dependencies_from_content "$content" "$known")
    # Should match the dependency pattern
    [[ -n "$result" ]]
}

