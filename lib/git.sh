#!/usr/bin/env bash
#
# git.sh - Git repository operations
#
# Provides functions for git repository state checks and workflow operations.
# Used by state.sh for clean state verification and by other modules for
# git-based workflows.
#
# Usage:
#   git_in_repo                       # Check if in a git repository
#   git_get_current_branch            # Get current branch name
#   git_is_clean                      # Check if repository has uncommitted changes
#

# Check if we are in a git repository
# Returns:
#   0 if in a git repository
#   1 if not in a git repository
#
# Example:
#   if git_in_repo; then
#     echo "In a git repository"
#   else
#     echo "Not in a git repository"
#   fi
git_in_repo() {
    git rev-parse --git-dir >/dev/null 2>&1
    return $?
}

# Get the current git branch name
# Returns:
#   Echoes the branch name (e.g., "main", "feature/foo")
#   Returns 0 on success
#   Returns 1 if not in a git repo or HEAD is detached
#
# Example:
#   branch=$(git_get_current_branch)
git_get_current_branch() {
    if ! git_in_repo; then
        return 1
    fi

    local branch
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

    if [[ -z "$branch" ]] || [[ "$branch" == "HEAD" ]]; then
        return 1
    fi

    echo "$branch"
    return 0
}

# Check if the repository has uncommitted changes
# Uses both git diff (working tree) and git diff --cached (staged changes)
#
# Returns:
#   0 if repository is clean (no uncommitted changes)
#   1 if there are uncommitted changes (modified, added, or deleted files)
#
# Example:
#   if git_is_clean; then
#     echo "Repository is clean"
#   else
#     echo "Uncommitted changes detected"
#   fi
git_is_clean() {
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

# Global variable to store the run branch name
_GIT_RUN_BRANCH=""

# Initialize a run branch with naming convention curb/{session_name}/{YYYYMMDD-HHMMSS}
# Creates and checks out a new branch from current HEAD.
# If the branch already exists, warns and uses it.
#
# Parameters:
#   $1 - session_name: The session name to use in the branch name
#
# Returns:
#   0 on success (branch created and checked out, or existing branch checked out)
#   1 on error (invalid session name or git command failure)
#
# Example:
#   git_init_run_branch "panda"
#   # Creates and checks out: curb/panda/20260110-163000
git_init_run_branch() {
    local session_name="$1"

    # Validate session_name is provided
    if [[ -z "$session_name" ]]; then
        echo "ERROR: session_name is required" >&2
        return 1
    fi

    # Check if we're in a git repository
    if ! git_in_repo; then
        echo "ERROR: Not in a git repository" >&2
        return 1
    fi

    # Generate timestamp in YYYYMMDD-HHMMSS format
    local timestamp
    timestamp=$(date +%Y%m%d-%H%M%S)

    # Generate branch name: curb/{session_name}/{timestamp}
    local branch_name="curb/${session_name}/${timestamp}"

    # Check if branch already exists
    if git rev-parse --verify "$branch_name" >/dev/null 2>&1; then
        echo "WARNING: Branch '$branch_name' already exists. Checking out existing branch." >&2

        # Checkout existing branch
        if ! git checkout "$branch_name" >/dev/null 2>&1; then
            echo "ERROR: Failed to checkout existing branch '$branch_name'" >&2
            return 1
        fi
    else
        # Create and checkout new branch
        if ! git checkout -b "$branch_name" >/dev/null 2>&1; then
            echo "ERROR: Failed to create and checkout branch '$branch_name'" >&2
            return 1
        fi
    fi

    # Store branch name in global variable
    _GIT_RUN_BRANCH="$branch_name"

    return 0
}

# Get the current run branch name
# Returns the branch name that was set by git_init_run_branch
#
# Returns:
#   Echoes the run branch name (e.g., "curb/panda/20260110-163000")
#   Returns 0 on success
#   Returns 1 if run branch has not been initialized
#
# Example:
#   branch=$(git_get_run_branch)
git_get_run_branch() {
    if [[ -z "$_GIT_RUN_BRANCH" ]]; then
        echo "ERROR: Run branch not initialized. Call git_init_run_branch first." >&2
        return 1
    fi

    echo "$_GIT_RUN_BRANCH"
    return 0
}
