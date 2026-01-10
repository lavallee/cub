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
    # Check for uncommitted changes in working tree
    if ! git diff --quiet HEAD 2>/dev/null; then
        return 1
    fi

    # Check for staged but uncommitted changes
    if ! git diff --cached --quiet HEAD 2>/dev/null; then
        return 1
    fi

    # Check for untracked files (files not in .gitignore)
    local untracked
    untracked=$(git ls-files --others --exclude-standard 2>/dev/null)
    if [[ -n "$untracked" ]]; then
        return 1
    fi

    # Repository is clean
    return 0
}

# Ensure the repository is in a clean state, taking action based on config
# Reads clean_state.require_commit from config to determine behavior:
#   - true: Error and exit if changes detected
#   - false: Warn but continue if changes detected
#
# Returns:
#   0 if repository is clean or require_commit is false
#   1 if repository has changes and require_commit is true (also exits process)
#
# Example:
#   state_ensure_clean  # Checks and acts based on config
state_ensure_clean() {
    # Check if repo is clean
    if state_is_clean; then
        return 0
    fi

    # Get configuration setting
    local require_commit
    require_commit=$(config_get_or "clean_state.require_commit" "true")

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
