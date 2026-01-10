#!/usr/bin/env bats

# Test suite for lib/state.sh

# Load the test helper
load test_helper

# Setup function runs before each test
setup() {
    # Create temp directory for test
    TEST_DIR="${BATS_TMPDIR}/state_test_$$"
    mkdir -p "$TEST_DIR"
    cd "$TEST_DIR"

    # Initialize a git repo for testing
    git init -q
    git config user.email "test@example.com"
    git config user.name "Test User"

    # Create initial commit so we have a HEAD
    echo "initial" > README.md
    git add README.md
    git commit -q -m "Initial commit"

    # Source the state library
    source "${PROJECT_ROOT}/lib/state.sh"

    # Create temp config directory
    TEST_CONFIG_DIR="${BATS_TMPDIR}/config_test_$$"
    mkdir -p "$TEST_CONFIG_DIR"

    # Override curb_config_dir to use test directory
    curb_config_dir() {
        echo "$TEST_CONFIG_DIR"
    }

    # Override logger functions to avoid creating log files in tests
    logger_init() { return 0; }
    log_error() { return 0; }

    # Clear config cache
    config_clear_cache
}

# Teardown function runs after each test
teardown() {
    cd /
    rm -rf "$TEST_DIR" "$TEST_CONFIG_DIR" 2>/dev/null || true
}

# ============================================================================
# state_is_clean tests
# ============================================================================

@test "state_is_clean returns 0 when repository is clean" {
    # Repository is already clean from setup
    run state_is_clean
    [[ $status -eq 0 ]]
}

@test "state_is_clean returns 1 when working tree has changes" {
    # Modify a tracked file
    echo "modified content" > README.md

    run state_is_clean
    [[ $status -eq 1 ]]
}

@test "state_is_clean returns 1 when there are staged changes" {
    # Create and stage a new file
    echo "new file" > new.txt
    git add new.txt

    run state_is_clean
    [[ $status -eq 1 ]]
}

@test "state_is_clean returns 1 when there are untracked files" {
    # Create untracked file
    echo "untracked" > untracked.txt

    run state_is_clean
    [[ $status -eq 1 ]]
}

@test "state_is_clean returns 0 after committing changes" {
    # Make changes and commit
    echo "new content" > README.md
    git add README.md
    git commit -q -m "Update README"

    run state_is_clean
    [[ $status -eq 0 ]]
}

@test "state_is_clean ignores .gitignore'd files" {
    # Create .gitignore
    echo "ignored.txt" > .gitignore
    git add .gitignore
    git commit -q -m "Add gitignore"

    # Create ignored file
    echo "ignored content" > ignored.txt

    # Should still be clean
    run state_is_clean
    [[ $status -eq 0 ]]
}

@test "state_is_clean detects deleted files" {
    # Delete a tracked file
    rm README.md

    run state_is_clean
    [[ $status -eq 1 ]]
}

# ============================================================================
# state_ensure_clean tests - with require_commit=true
# ============================================================================

@test "state_ensure_clean returns 0 when clean and require_commit=true" {
    # Create config with require_commit=true
    echo '{"clean_state": {"require_commit": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    run state_ensure_clean
    [[ $status -eq 0 ]]
}

@test "state_ensure_clean returns 1 when dirty and require_commit=true" {
    # Create config with require_commit=true
    echo '{"clean_state": {"require_commit": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # Make changes
    echo "modified" > README.md

    run state_ensure_clean
    [[ $status -eq 1 ]]
}

@test "state_ensure_clean shows error message when dirty and require_commit=true" {
    # Create config with require_commit=true
    echo '{"clean_state": {"require_commit": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # Make changes
    echo "modified" > README.md

    run state_ensure_clean
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Repository has uncommitted changes" ]]
    [[ "$output" =~ "README.md" ]]
}

# ============================================================================
# state_ensure_clean tests - with require_commit=false
# ============================================================================

@test "state_ensure_clean returns 0 when clean and require_commit=false" {
    # Create config with require_commit=false
    echo '{"clean_state": {"require_commit": false}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    run state_ensure_clean
    [[ $status -eq 0 ]]
}

@test "state_ensure_clean shows warning when dirty and require_commit=false" {
    # Create config with require_commit=false
    echo '{"clean_state": {"require_commit": false}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # Make changes
    echo "modified" > README.md

    run state_ensure_clean
    [[ $status -eq 0 ]]
    [[ "$output" =~ "WARNING: Repository has uncommitted changes" ]]
    [[ "$output" =~ "README.md" ]]
}

# ============================================================================
# state_ensure_clean tests - default behavior
# ============================================================================

@test "state_ensure_clean defaults to require_commit=true when config missing" {
    # No config file, should default to true
    config_clear_cache

    # Make changes
    echo "modified" > README.md

    run state_ensure_clean
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR" ]]
}

# ============================================================================
# Acceptance criteria tests
# ============================================================================

@test "ACCEPTANCE: Detects uncommitted changes after harness run" {
    # Simulate harness leaving uncommitted changes
    echo "harness output" > output.txt
    git add output.txt
    # Intentionally don't commit

    run state_is_clean
    [[ $status -eq 1 ]]
}

@test "ACCEPTANCE: Respects clean_state.require_commit config" {
    # Set require_commit to true
    echo '{"clean_state": {"require_commit": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # Create uncommitted changes
    echo "uncommitted" > file.txt

    run state_ensure_clean
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR" ]]
}

@test "ACCEPTANCE: Clear error message pointing to uncommitted files" {
    # Set require_commit to true
    echo '{"clean_state": {"require_commit": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # Create multiple uncommitted files
    echo "modified" > README.md
    echo "new" > new-file.txt

    run state_ensure_clean
    [[ $status -eq 1 ]]
    # Should mention uncommitted files
    [[ "$output" =~ "uncommitted" || "$output" =~ "Uncommitted" ]]
    # Should list the files
    [[ "$output" =~ "README.md" ]]
    [[ "$output" =~ "new-file.txt" ]]
}

# ============================================================================
# Edge cases
# ============================================================================

@test "state_ensure_clean handles multiple types of changes" {
    # Create config
    echo '{"clean_state": {"require_commit": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # Create different types of changes
    echo "modified" > README.md       # Modified
    echo "new" > new.txt               # Untracked
    echo "staged" > staged.txt
    git add staged.txt                 # Staged

    run state_ensure_clean
    [[ $status -eq 1 ]]
    [[ "$output" =~ "README.md" ]]
    [[ "$output" =~ "new.txt" ]]
    [[ "$output" =~ "staged.txt" ]]
}

@test "state_ensure_clean provides helpful guidance in error message" {
    # Create config
    echo '{"clean_state": {"require_commit": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # Make changes
    echo "modified" > README.md

    run state_ensure_clean
    [[ $status -eq 1 ]]
    # Should explain what's wrong
    [[ "$output" =~ "harness should commit" ]]
    # Should provide hint to disable
    [[ "$output" =~ "clean_state.require_commit" ]]
}
