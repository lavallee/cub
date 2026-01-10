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

# ============================================================================
# state_detect_test_command tests
# ============================================================================

@test "state_detect_test_command detects npm test from package.json" {
    # Create package.json with test script
    echo '{"scripts": {"test": "echo test"}}' > package.json

    run state_detect_test_command
    [[ $status -eq 0 ]]
    [[ "$output" == "npm test" ]]
}

@test "state_detect_test_command prefers yarn when yarn.lock exists" {
    # Create package.json with test script
    echo '{"scripts": {"test": "echo test"}}' > package.json
    touch yarn.lock

    run state_detect_test_command
    [[ $status -eq 0 ]]
    [[ "$output" == "yarn test" ]]
}

@test "state_detect_test_command returns 1 when package.json has no test script" {
    # Create package.json without test script
    echo '{"scripts": {"build": "echo build"}}' > package.json

    run state_detect_test_command
    [[ $status -eq 1 ]]
}

@test "state_detect_test_command detects make test from Makefile" {
    # Create Makefile with test target
    cat > Makefile <<EOF
test:
	@echo "Running tests"
EOF

    run state_detect_test_command
    [[ $status -eq 0 ]]
    [[ "$output" == "make test" ]]
}

@test "state_detect_test_command detects pytest from pytest.ini" {
    # Create pytest.ini
    echo "[pytest]" > pytest.ini

    run state_detect_test_command
    [[ $status -eq 0 ]]
    [[ "$output" =~ "pytest" ]]
}

@test "state_detect_test_command detects pytest from tests directory" {
    # Create tests directory
    mkdir -p tests
    touch tests/test_example.py

    run state_detect_test_command
    [[ $status -eq 0 ]]
    [[ "$output" =~ "pytest" ]]
}

@test "state_detect_test_command detects go test from go.mod" {
    # Create go.mod
    echo 'module example.com/test' > go.mod

    run state_detect_test_command
    [[ $status -eq 0 ]]
    [[ "$output" == "go test ./..." ]]
}

@test "state_detect_test_command detects cargo test from Cargo.toml" {
    # Create Cargo.toml
    cat > Cargo.toml <<EOF
[package]
name = "test"
version = "0.1.0"
EOF

    run state_detect_test_command
    [[ $status -eq 0 ]]
    [[ "$output" == "cargo test" ]]
}

@test "state_detect_test_command returns 1 when no test command detected" {
    # Empty directory - no test indicators
    run state_detect_test_command
    [[ $status -eq 1 ]]
}

# ============================================================================
# state_run_tests tests - with require_tests=false (default)
# ============================================================================

@test "state_run_tests returns 0 when require_tests=false" {
    # Create config with require_tests=false
    echo '{"clean_state": {"require_tests": false}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    run state_run_tests
    [[ $status -eq 0 ]]
}

@test "state_run_tests returns 0 when config missing (defaults to false)" {
    # No config file
    config_clear_cache

    run state_run_tests
    [[ $status -eq 0 ]]
}

# ============================================================================
# state_run_tests tests - with require_tests=true
# ============================================================================

@test "state_run_tests runs tests when require_tests=true and package.json exists" {
    # Create config with require_tests=true
    echo '{"clean_state": {"require_tests": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # Create package.json with passing test
    echo '{"scripts": {"test": "exit 0"}}' > package.json

    run state_run_tests
    [[ $status -eq 0 ]]
    [[ "$output" =~ "Running tests:" ]]
    [[ "$output" =~ "npm test" ]]
    [[ "$output" =~ "Tests passed" ]]
}

@test "state_run_tests fails when tests fail and require_tests=true" {
    # Create config with require_tests=true
    echo '{"clean_state": {"require_tests": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # Create package.json with failing test
    echo '{"scripts": {"test": "exit 1"}}' > package.json

    run state_run_tests
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Tests failed" ]]
    [[ "$output" =~ "npm test" ]]
}

@test "state_run_tests warns when no test command detected and require_tests=true" {
    # Create config with require_tests=true
    echo '{"clean_state": {"require_tests": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # No test command in empty directory
    run state_run_tests
    [[ $status -eq 0 ]]
    [[ "$output" =~ "WARNING" ]]
    [[ "$output" =~ "no test command detected" ]]
}

@test "state_run_tests detects and runs make test" {
    # Create config with require_tests=true
    echo '{"clean_state": {"require_tests": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # Create Makefile with test target
    cat > Makefile <<'EOF'
test:
	@exit 0
EOF

    run state_run_tests
    [[ $status -eq 0 ]]
    [[ "$output" =~ "make test" ]]
}

@test "state_run_tests provides helpful error message on test failure" {
    # Create config with require_tests=true
    echo '{"clean_state": {"require_tests": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    # Create package.json with failing test that outputs error
    echo '{"scripts": {"test": "echo \"Test error message\" && exit 1"}}' > package.json

    run state_run_tests
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Tests failed" ]]
    [[ "$output" =~ "Test command:" ]]
    [[ "$output" =~ "Test output:" ]]
    [[ "$output" =~ "clean_state.require_tests" ]]
}

# ============================================================================
# Acceptance criteria tests for test runner
# ============================================================================

@test "ACCEPTANCE: Detects test command for npm projects" {
    echo '{"scripts": {"test": "echo test"}}' > package.json

    run state_detect_test_command
    [[ $status -eq 0 ]]
    [[ "$output" =~ "npm test" ]]
}

@test "ACCEPTANCE: Detects test command for yarn projects" {
    echo '{"scripts": {"test": "echo test"}}' > package.json
    touch yarn.lock

    run state_detect_test_command
    [[ $status -eq 0 ]]
    [[ "$output" =~ "yarn test" ]]
}

@test "ACCEPTANCE: Detects test command for make projects" {
    cat > Makefile <<EOF
test:
	@echo "test"
EOF

    run state_detect_test_command
    [[ $status -eq 0 ]]
    [[ "$output" == "make test" ]]
}

@test "ACCEPTANCE: Detects test command for pytest projects" {
    mkdir -p tests
    touch tests/test_example.py

    run state_detect_test_command
    [[ $status -eq 0 ]]
    [[ "$output" =~ "pytest" ]]
}

@test "ACCEPTANCE: Only runs tests if require_tests is true" {
    # Test with require_tests=false
    echo '{"clean_state": {"require_tests": false}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache
    echo '{"scripts": {"test": "exit 1"}}' > package.json

    run state_run_tests
    [[ $status -eq 0 ]]

    # Test with require_tests=true
    echo '{"clean_state": {"require_tests": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache

    run state_run_tests
    [[ $status -eq 1 ]]
}

@test "ACCEPTANCE: Test failures logged clearly" {
    echo '{"clean_state": {"require_tests": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache
    echo '{"scripts": {"test": "echo \"FAILURE\" && exit 1"}}' > package.json

    run state_run_tests
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Tests failed" ]]
    [[ "$output" =~ "exit code" ]]
    [[ "$output" =~ "FAILURE" ]]
}

@test "ACCEPTANCE: Test output captured in logs" {
    echo '{"clean_state": {"require_tests": true}}' > "$TEST_CONFIG_DIR/config.json"
    config_clear_cache
    echo '{"scripts": {"test": "echo \"Test output line 1\" && echo \"Test output line 2\""}}' > package.json

    run state_run_tests
    [[ $status -eq 0 ]]
    # Output should be shown to user
    [[ "$output" =~ "Running tests:" ]]
}
