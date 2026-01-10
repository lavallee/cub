#!/usr/bin/env bash
#
# state.sh - Git repository state verification
#
# Provides functions to verify the git repository is in a clean state after
# harness execution. Ensures harnesses commit their changes as expected.
#
# Usage:
#   state_is_clean                    # Returns 0 if clean, 1 if changes exist
#   state_ensure_clean                # Checks state and acts based on config
#

# Source dependencies
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source git.sh if not already loaded
if ! type git_is_clean &>/dev/null; then
    source "${SCRIPT_DIR}/git.sh"
fi

# Source config.sh if not already loaded
if ! type config_get &>/dev/null; then
    source "${SCRIPT_DIR}/config.sh"
fi

# Source logger.sh if not already loaded
if ! type log_error &>/dev/null; then
    source "${SCRIPT_DIR}/logger.sh"
fi

# Check if the repository has uncommitted changes
# Uses both git diff (working tree) and git diff --cached (staged changes)
#
# This is a wrapper around git_is_clean() from git.sh for backward compatibility.
#
# Returns:
#   0 if repository is clean (no uncommitted changes)
#   1 if there are uncommitted changes (modified, added, or deleted files)
#
# Example:
#   if state_is_clean; then
#     echo "Repository is clean"
#   else
#     echo "Uncommitted changes detected"
#   fi
state_is_clean() {
    git_is_clean
}

# Ensure the repository is in a clean state, taking action based on config
# Reads clean_state.require_commit from config to determine behavior:
#   - true: Error and exit if changes detected
#   - false: Warn but continue if changes detected
#
# Parameters:
#   $1 - (optional) Override value: "true" or "false". If empty, uses config.
#
# Returns:
#   0 if repository is clean or require_commit is false
#   1 if repository has changes and require_commit is true (also exits process)
#
# Example:
#   state_ensure_clean           # Checks and acts based on config
#   state_ensure_clean "true"    # Force require clean state
#   state_ensure_clean "false"   # Force allow dirty state
state_ensure_clean() {
    local override="${1:-}"

    # Check if repo is clean
    if state_is_clean; then
        return 0
    fi

    # Get configuration setting (or use override)
    local require_commit
    if [[ -n "$override" ]]; then
        require_commit="$override"
    else
        require_commit=$(config_get_or "clean_state.require_commit" "true")
    fi

    # Get list of uncommitted files for error message
    local uncommitted_files
    uncommitted_files=$(git status --short 2>/dev/null)

    # Act based on configuration
    if [[ "$require_commit" == "true" ]]; then
        # Log error with context
        local error_context
        error_context=$(jq -n \
            --arg files "$uncommitted_files" \
            '{uncommitted_files: $files}')

        log_error "Harness left uncommitted changes in repository" "$error_context"

        # Print error to stderr
        echo "ERROR: Repository has uncommitted changes after harness execution" >&2
        echo "" >&2
        echo "The harness should commit all changes before exiting." >&2
        echo "Uncommitted files:" >&2
        echo "$uncommitted_files" >&2
        echo "" >&2
        echo "To disable this check, set clean_state.require_commit to false in your config." >&2

        return 1
    else
        # Warn but don't fail
        echo "WARNING: Repository has uncommitted changes after harness execution" >&2
        echo "Uncommitted files:" >&2
        echo "$uncommitted_files" >&2
        echo "" >&2

        return 0
    fi
}

# Detect the test command for the current project
# Checks for common test patterns in package.json, Makefile, pytest, etc.
#
# Returns:
#   Echoes the detected test command (e.g., "npm test", "make test")
#   Returns 0 if a test command was detected
#   Returns 1 if no test command could be detected
#
# Example:
#   test_cmd=$(state_detect_test_command)
state_detect_test_command() {
    # Check for npm/yarn projects (package.json with test script)
    if [[ -f "package.json" ]]; then
        # Check if package.json has a test script
        if jq -e '.scripts.test' package.json >/dev/null 2>&1; then
            # Prefer yarn if yarn.lock exists
            if [[ -f "yarn.lock" ]] && command -v yarn >/dev/null 2>&1; then
                echo "yarn test"
                return 0
            # Otherwise use npm if available
            elif command -v npm >/dev/null 2>&1; then
                echo "npm test"
                return 0
            fi
        fi
    fi

    # Check for Makefile with test target
    if [[ -f "Makefile" ]] || [[ -f "makefile" ]]; then
        if command -v make >/dev/null 2>&1; then
            # Check if make has a test target
            if make -n test >/dev/null 2>&1; then
                echo "make test"
                return 0
            fi
        fi
    fi

    # Check for Python pytest
    if [[ -f "pytest.ini" ]] || [[ -f "setup.py" ]] || [[ -f "pyproject.toml" ]] || [[ -d "tests" ]]; then
        if command -v pytest >/dev/null 2>&1; then
            echo "pytest"
            return 0
        # Fallback to python -m pytest
        elif command -v python >/dev/null 2>&1; then
            echo "python -m pytest"
            return 0
        elif command -v python3 >/dev/null 2>&1; then
            echo "python3 -m pytest"
            return 0
        fi
    fi

    # Check for Go projects
    if [[ -f "go.mod" ]] && command -v go >/dev/null 2>&1; then
        echo "go test ./..."
        return 0
    fi

    # Check for Rust projects
    if [[ -f "Cargo.toml" ]] && command -v cargo >/dev/null 2>&1; then
        echo "cargo test"
        return 0
    fi

    # Check for Ruby projects with Rakefile
    if [[ -f "Rakefile" ]] && command -v rake >/dev/null 2>&1; then
        # Check if rake has a test or spec target
        if rake -T | grep -q "test\|spec" 2>/dev/null; then
            echo "rake test"
            return 0
        fi
    fi

    # No test command detected
    return 1
}

# Run tests for the current project if configured to do so
# Reads clean_state.require_tests from config to determine whether to run tests.
# Automatically detects the test command based on project type.
#
# Returns:
#   0 if tests pass, tests are disabled, or no test command was detected
#   1 if tests are required and fail
#
# Example:
#   state_run_tests  # Runs tests based on config
state_run_tests() {
    # Get configuration setting
    local require_tests
    require_tests=$(config_get_or "clean_state.require_tests" "false")

    # If tests not required, return success
    if [[ "$require_tests" != "true" ]]; then
        return 0
    fi

    # Detect test command
    local test_cmd
    test_cmd=$(state_detect_test_command)

    if [[ $? -ne 0 ]]; then
        # No test command detected - warn but don't fail
        echo "WARNING: clean_state.require_tests is true but no test command detected" >&2
        echo "Skipping test run. Supported: npm/yarn, make, pytest, go, cargo, rake" >&2
        return 0
    fi

    echo "Running tests: $test_cmd" >&2

    # Run the test command and capture output
    local test_output
    local test_exit_code

    # Run tests and capture both stdout and stderr
    test_output=$($test_cmd 2>&1)
    test_exit_code=$?

    # Check if tests passed
    if [[ $test_exit_code -eq 0 ]]; then
        echo "Tests passed" >&2
        return 0
    else
        # Tests failed - log error with context
        local error_context
        error_context=$(jq -n \
            --arg cmd "$test_cmd" \
            --arg output "$test_output" \
            --argjson exit_code "$test_exit_code" \
            '{test_command: $cmd, exit_code: $exit_code, output: $output}')

        log_error "Tests failed after harness execution" "$error_context"

        # Print error to stderr
        echo "ERROR: Tests failed with exit code $test_exit_code" >&2
        echo "" >&2
        echo "Test command: $test_cmd" >&2
        echo "Test output:" >&2
        echo "$test_output" >&2
        echo "" >&2
        echo "To disable test requirements, set clean_state.require_tests to false in your config." >&2

        return 1
    fi
}
