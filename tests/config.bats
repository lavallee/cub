#!/usr/bin/env bats

# Test suite for lib/config.sh

# Load the test helper
load test_helper

# Setup function runs before each test
setup() {
    # Source the config library
    source "${PROJECT_ROOT}/lib/config.sh"

    # Create temp directory for test configs
    TEST_CONFIG_DIR="${BATS_TMPDIR}/config_test_$$"
    TEST_PROJECT_DIR="${BATS_TMPDIR}/project_test_$$"
    mkdir -p "$TEST_CONFIG_DIR"
    mkdir -p "$TEST_PROJECT_DIR"

    # Override cub_config_dir to use test directory
    cub_config_dir() {
        echo "$TEST_CONFIG_DIR"
    }

    # Clear config cache before each test
    config_clear_cache
}

# Teardown function runs after each test
teardown() {
    # Clean up test directories
    rm -rf "$TEST_CONFIG_DIR" "$TEST_PROJECT_DIR" 2>/dev/null || true
}

# ============================================================================
# Basic config_get tests
# ============================================================================

@test "config_get returns empty for nonexistent key" {
    # Create empty config
    echo '{}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get "nonexistent" || true)
    [[ -z "$result" ]]
}

@test "config_get returns simple string value" {
    # Create config with string
    echo '{"name": "cub"}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get "name")
    [[ "$result" == "cub" ]]
}

@test "config_get returns number value" {
    # Create config with number
    echo '{"budget": {"default": 100}}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get "budget.default")
    [[ "$result" == "100" ]]
}

@test "config_get returns array value" {
    # Create config with array
    echo '{"harness": {"priority": ["claude", "codex"]}}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get "harness.priority")
    # jq returns arrays as JSON - check it contains expected values
    [[ "$result" == *"claude"* ]]
    [[ "$result" == *"codex"* ]]
    # Verify it's valid JSON array
    echo "$result" | jq -e 'type == "array"' >/dev/null
}

@test "config_get returns boolean value" {
    # Create config with boolean
    echo '{"debug": true}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get "debug")
    [[ "$result" == "true" ]]
}

@test "config_get returns nested object value" {
    # Create config with nested object
    echo '{"server": {"host": "localhost", "port": 8080}}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get "server.host")
    [[ "$result" == "localhost" ]]

    result=$(config_get "server.port")
    [[ "$result" == "8080" ]]
}

# ============================================================================
# config_get_or tests (with fallback)
# ============================================================================

@test "config_get_or returns value when key exists" {
    echo '{"name": "cub"}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get_or "name" "fallback")
    [[ "$result" == "cub" ]]
}

@test "config_get_or returns fallback when key does not exist" {
    echo '{}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get_or "nonexistent" "fallback")
    [[ "$result" == "fallback" ]]
}

@test "config_get_or returns fallback for empty config" {
    # No config file exists
    result=$(config_get_or "nonexistent" "default_value")
    [[ "$result" == "default_value" ]]
}

@test "config_get_or works with numeric fallback" {
    echo '{}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get_or "missing.number" "42")
    [[ "$result" == "42" ]]
}

# ============================================================================
# Config merging tests
# ============================================================================

@test "project config overrides user config" {
    # Create user config
    echo '{"name": "user_value", "user_only": "user"}' > "$TEST_CONFIG_DIR/config.json"

    # Create project config that overrides name
    cd "$TEST_PROJECT_DIR"
    echo '{"name": "project_value", "project_only": "project"}' > ./.cub.json

    # Clear cache to force reload
    config_clear_cache

    result=$(config_get "name")
    [[ "$result" == "project_value" ]]

    result=$(config_get "user_only")
    [[ "$result" == "user" ]]

    result=$(config_get "project_only")
    [[ "$result" == "project" ]]
}

@test "config_load works with only user config" {
    echo '{"user": "value"}' > "$TEST_CONFIG_DIR/config.json"

    config_load
    result=$(config_get "user")
    [[ "$result" == "value" ]]
}

@test "config_load works with only project config" {
    cd "$TEST_PROJECT_DIR"
    echo '{"project": "value"}' > ./.cub.json

    config_load
    result=$(config_get "project")
    [[ "$result" == "value" ]]
}

@test "config_load works with no config files" {
    config_load
    # Should not error, just have empty config
    result=$(config_get "anything" || true)
    [[ -z "$result" ]]
}

# ============================================================================
# Caching tests
# ============================================================================

@test "config is cached after first load" {
    echo '{"cached": "value"}' > "$TEST_CONFIG_DIR/config.json"

    # First call loads config
    result=$(config_get "cached")
    [[ "$result" == "value" ]]

    # Modify config file
    echo '{"cached": "new_value"}' > "$TEST_CONFIG_DIR/config.json"

    # Second call should return cached value (still the old one)
    result=$(config_get "cached")
    [[ "$result" == "value" ]]
}

@test "config_clear_cache forces reload" {
    echo '{"cached": "value"}' > "$TEST_CONFIG_DIR/config.json"

    # First call loads config
    result=$(config_get "cached")
    [[ "$result" == "value" ]]

    # Modify config file
    echo '{"cached": "new_value"}' > "$TEST_CONFIG_DIR/config.json"

    # Clear cache and reload
    config_clear_cache
    result=$(config_get "cached")
    [[ "$result" == "new_value" ]]
}

# ============================================================================
# Edge cases and error handling
# ============================================================================

@test "config_get handles invalid JSON gracefully" {
    echo 'invalid json' > "$TEST_CONFIG_DIR/config.json"

    # Should not crash, just return empty
    result=$(config_get "anything" || true)
    [[ -z "$result" ]]
}

@test "config_get handles null values" {
    echo '{"nullable": null}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get "nullable" || true)
    [[ -z "$result" ]]
}

@test "config_get handles deeply nested keys" {
    echo '{"a": {"b": {"c": {"d": "deep_value"}}}}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get "a.b.c.d")
    [[ "$result" == "deep_value" ]]
}

@test "config_dump returns full config JSON" {
    echo '{"key1": "value1", "key2": "value2"}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_dump)
    # Should be valid JSON containing both keys
    echo "$result" | jq -e '.key1 == "value1"'
    echo "$result" | jq -e '.key2 == "value2"'
}

# ============================================================================
# Acceptance criteria tests (from task description)
# ============================================================================

@test "acceptance: config_get 'harness.priority' returns array" {
    echo '{"harness": {"priority": ["claude", "codex"]}}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get "harness.priority")
    # jq returns arrays as JSON strings
    [[ "$result" == *"claude"* ]]
    [[ "$result" == *"codex"* ]]
}

@test "acceptance: config_get 'budget.default' returns number" {
    echo '{"budget": {"default": 100}}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get "budget.default")
    [[ "$result" == "100" ]]
}

@test "acceptance: config_get 'nonexistent' returns empty" {
    echo '{}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get "nonexistent" || true)
    [[ -z "$result" ]]
}

@test "acceptance: config_get_or 'nonexistent' 'fallback' returns 'fallback'" {
    echo '{}' > "$TEST_CONFIG_DIR/config.json"

    result=$(config_get_or "nonexistent" "fallback")
    [[ "$result" == "fallback" ]]
}

# ============================================================================
# Environment variable override tests
# ============================================================================

@test "CUB_BUDGET env var overrides config budget" {
    echo '{"budget": {"default": 100}}' > "$TEST_CONFIG_DIR/config.json"

    # Set CUB_BUDGET environment variable
    export CUB_BUDGET=500
    config_clear_cache

    result=$(config_get "budget.default")
    [[ "$result" == "500" ]]

    # Clean up
    unset CUB_BUDGET
}

@test "CUB_BUDGET env var overrides project config budget" {
    echo '{"budget": {"default": 100}}' > "$TEST_CONFIG_DIR/config.json"

    cd "$TEST_PROJECT_DIR"
    echo '{"budget": {"default": 200}}' > ./.cub.json

    # Set CUB_BUDGET environment variable (should have highest priority)
    export CUB_BUDGET=500
    config_clear_cache

    result=$(config_get "budget.default")
    [[ "$result" == "500" ]]

    # Clean up
    unset CUB_BUDGET
}

@test "CUB_BUDGET env var creates budget structure if not present" {
    echo '{}' > "$TEST_CONFIG_DIR/config.json"

    # Set CUB_BUDGET environment variable
    export CUB_BUDGET=300
    config_clear_cache

    result=$(config_get "budget.default")
    [[ "$result" == "300" ]]

    # Clean up
    unset CUB_BUDGET
}

@test "config without CUB_BUDGET env var uses file values" {
    echo '{"budget": {"default": 100}}' > "$TEST_CONFIG_DIR/config.json"

    # Ensure CUB_BUDGET is not set
    unset CUB_BUDGET
    config_clear_cache

    result=$(config_get "budget.default")
    [[ "$result" == "100" ]]
}
