#!/usr/bin/env bats

# Test suite for lib/git.sh

# Load the test helper
load test_helper

# Setup function runs before each test
setup() {
    # Create temp directory for test
    TEST_DIR="${BATS_TMPDIR}/git_test_$$"
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

    # Source the git library
    source "${PROJECT_ROOT}/lib/git.sh"
}

# Teardown function runs after each test
teardown() {
    cd /
    rm -rf "$TEST_DIR" 2>/dev/null || true
}

# ============================================================================
# git_in_repo tests
# ============================================================================

@test "git_in_repo returns 0 when in a git repository" {
    run git_in_repo
    [[ $status -eq 0 ]]
}

@test "git_in_repo returns 1 when not in a git repository" {
    # Create a new directory outside of git repo
    NON_GIT_DIR="${BATS_TMPDIR}/non_git_$$"
    mkdir -p "$NON_GIT_DIR"
    cd "$NON_GIT_DIR"

    run git_in_repo
    [[ $status -eq 1 ]]

    # Cleanup
    cd /
    rm -rf "$NON_GIT_DIR"
}

# ============================================================================
# git_get_current_branch tests
# ============================================================================

@test "git_get_current_branch returns current branch name" {
    run git_get_current_branch
    [[ $status -eq 0 ]]
    # Should be on main or master by default
    [[ "$output" == "main" || "$output" == "master" ]]
}

@test "git_get_current_branch returns new branch after checkout" {
    git checkout -q -b test-branch

    run git_get_current_branch
    [[ $status -eq 0 ]]
    [[ "$output" == "test-branch" ]]
}

@test "git_get_current_branch returns 1 when not in git repo" {
    # Create a new directory outside of git repo
    NON_GIT_DIR="${BATS_TMPDIR}/non_git_$$"
    mkdir -p "$NON_GIT_DIR"
    cd "$NON_GIT_DIR"

    run git_get_current_branch
    [[ $status -eq 1 ]]

    # Cleanup
    cd /
    rm -rf "$NON_GIT_DIR"
}

# ============================================================================
# git_is_clean tests
# ============================================================================

@test "git_is_clean returns 0 when repository is clean" {
    run git_is_clean
    [[ $status -eq 0 ]]
}

@test "git_is_clean returns 1 when working tree has changes" {
    echo "modified content" > README.md

    run git_is_clean
    [[ $status -eq 1 ]]
}

@test "git_is_clean returns 1 when there are staged changes" {
    echo "new file" > new.txt
    git add new.txt

    run git_is_clean
    [[ $status -eq 1 ]]
}

@test "git_is_clean returns 1 when there are untracked files" {
    echo "untracked" > untracked.txt

    run git_is_clean
    [[ $status -eq 1 ]]
}

@test "git_is_clean ignores .gitignore'd files" {
    # Create .gitignore
    echo "ignored.txt" > .gitignore
    git add .gitignore
    git commit -q -m "Add gitignore"

    # Create ignored file
    echo "ignored content" > ignored.txt

    # Should still be clean
    run git_is_clean
    [[ $status -eq 0 ]]
}

# ============================================================================
# git_init_run_branch tests
# ============================================================================

@test "git_init_run_branch creates branch with correct naming convention" {
    run git_init_run_branch "panda"
    [[ $status -eq 0 ]]

    # Check that we're on the new branch
    local current_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD)
    [[ "$current_branch" =~ ^curb/panda/[0-9]{8}-[0-9]{6}$ ]]
}

@test "git_init_run_branch checks out the new branch" {
    # Remember the original branch
    local original_branch
    original_branch=$(git_get_current_branch)

    run git_init_run_branch "panda"
    [[ $status -eq 0 ]]

    # Verify we're on a different branch
    local new_branch
    new_branch=$(git_get_current_branch)
    [[ "$new_branch" != "$original_branch" ]]
    [[ "$new_branch" =~ ^curb/panda/ ]]
}

@test "git_init_run_branch stores branch name in global variable" {
    git_init_run_branch "panda"

    # Global variable should be set (run without 'run' to check variable in same shell)
    [[ -n "$_GIT_RUN_BRANCH" ]]
    [[ "$_GIT_RUN_BRANCH" =~ ^curb/panda/[0-9]{8}-[0-9]{6}$ ]]
}

@test "git_init_run_branch returns error when session_name is empty" {
    run git_init_run_branch ""
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: session_name is required" ]]
}

@test "git_init_run_branch returns error when not in git repo" {
    # Create a new directory outside of git repo
    NON_GIT_DIR="${BATS_TMPDIR}/non_git_$$"
    mkdir -p "$NON_GIT_DIR"
    cd "$NON_GIT_DIR"

    run git_init_run_branch "panda"
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Not in a git repository" ]]

    # Cleanup
    cd /
    rm -rf "$NON_GIT_DIR"
}

@test "git_init_run_branch handles existing branch gracefully" {
    # Create a branch manually
    local branch_name="curb/panda/20260110-120000"
    git checkout -q -b "$branch_name"

    # Switch back to main
    git checkout -q main 2>/dev/null || git checkout -q master 2>/dev/null

    # Try to init with the same branch name (by mocking date command)
    # Create a wrapper function for date
    date() {
        if [[ "$1" == "+%Y%m%d-%H%M%S" ]]; then
            echo "20260110-120000"
        else
            command date "$@"
        fi
    }
    export -f date

    run git_init_run_branch "panda"
    [[ $status -eq 0 ]]
    [[ "$output" =~ "WARNING: Branch" ]]
    [[ "$output" =~ "already exists" ]]

    # Verify we're on that branch
    local current_branch
    current_branch=$(git_get_current_branch)
    [[ "$current_branch" == "$branch_name" ]]
}

@test "git_init_run_branch works from any starting branch" {
    # Create and checkout a feature branch
    git checkout -q -b feature/test

    # Create a commit on this branch
    echo "feature work" > feature.txt
    git add feature.txt
    git commit -q -m "Feature work"

    # Initialize run branch from feature branch
    run git_init_run_branch "panda"
    [[ $status -eq 0 ]]

    # Should be on new curb branch
    local current_branch
    current_branch=$(git_get_current_branch)
    [[ "$current_branch" =~ ^curb/panda/ ]]
}

@test "git_init_run_branch uses current timestamp" {
    # Run twice with small delay to ensure different timestamps
    git_init_run_branch "panda"
    local first_branch="$_GIT_RUN_BRANCH"

    # Switch back to main
    git checkout -q main 2>/dev/null || git checkout -q master 2>/dev/null

    # Small delay to ensure different timestamp (2 seconds to be safe)
    sleep 2

    git_init_run_branch "panda"
    local second_branch="$_GIT_RUN_BRANCH"

    # Branches should be different due to timestamp
    [[ "$first_branch" != "$second_branch" ]]
}

# ============================================================================
# git_get_run_branch tests
# ============================================================================

@test "git_get_run_branch returns branch name after initialization" {
    git_init_run_branch "panda"

    run git_get_run_branch
    [[ $status -eq 0 ]]
    [[ "$output" =~ ^curb/panda/[0-9]{8}-[0-9]{6}$ ]]
}

@test "git_get_run_branch returns error when not initialized" {
    # Clear the global variable
    _GIT_RUN_BRANCH=""

    run git_get_run_branch
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Run branch not initialized" ]]
}

@test "git_get_run_branch returns same branch as initialized" {
    git_init_run_branch "panda"
    local init_branch="$_GIT_RUN_BRANCH"

    run git_get_run_branch
    [[ $status -eq 0 ]]
    [[ "$output" == "$init_branch" ]]
}

# ============================================================================
# Integration tests
# ============================================================================

@test "INTEGRATION: Complete workflow - init branch, get branch, verify checkout" {
    # Initialize run branch
    git_init_run_branch "wallaby"

    # Get the run branch name
    local run_branch
    run_branch=$(git_get_run_branch)

    # Verify we're on that branch
    local current_branch
    current_branch=$(git_get_current_branch)

    [[ "$run_branch" == "$current_branch" ]]
    [[ "$run_branch" =~ ^curb/wallaby/[0-9]{8}-[0-9]{6}$ ]]
}

@test "INTEGRATION: Multiple sessions create different branches" {
    # Create first session branch
    git_init_run_branch "panda"
    local panda_branch="$_GIT_RUN_BRANCH"

    # Switch back
    git checkout -q main 2>/dev/null || git checkout -q master 2>/dev/null

    # Create second session branch
    git_init_run_branch "wallaby"
    local wallaby_branch="$_GIT_RUN_BRANCH"

    # Branches should be different
    [[ "$panda_branch" != "$wallaby_branch" ]]
    [[ "$panda_branch" =~ ^curb/panda/ ]]
    [[ "$wallaby_branch" =~ ^curb/wallaby/ ]]
}

# ============================================================================
# Acceptance criteria tests
# ============================================================================

@test "ACCEPTANCE: Branch created with correct naming convention" {
    git_init_run_branch "panda"

    local branch
    branch=$(git_get_run_branch)

    # Should match: curb/{session-name}/{YYYYMMDD-HHMMSS}
    [[ "$branch" =~ ^curb/panda/[0-9]{8}-[0-9]{6}$ ]]
}

@test "ACCEPTANCE: Branch checked out after creation" {
    git_init_run_branch "panda"

    # Current git branch should match the run branch
    local current_branch
    current_branch=$(git_get_current_branch)
    local run_branch
    run_branch=$(git_get_run_branch)

    [[ "$current_branch" == "$run_branch" ]]
}

@test "ACCEPTANCE: Handles existing branch gracefully" {
    # Create a branch manually
    local branch_name="curb/panda/20260110-120000"
    git checkout -q -b "$branch_name"
    git checkout -q main 2>/dev/null || git checkout -q master 2>/dev/null

    # Mock date to return the same timestamp
    date() {
        if [[ "$1" == "+%Y%m%d-%H%M%S" ]]; then
            echo "20260110-120000"
        else
            command date "$@"
        fi
    }
    export -f date

    # Should warn but succeed
    run git_init_run_branch "panda"
    [[ $status -eq 0 ]]
    [[ "$output" =~ "WARNING" ]]

    # Should be on the existing branch
    local current_branch
    current_branch=$(git_get_current_branch)
    [[ "$current_branch" == "$branch_name" ]]
}

@test "ACCEPTANCE: git_get_run_branch returns current run branch" {
    git_init_run_branch "panda"

    run git_get_run_branch
    [[ $status -eq 0 ]]
    [[ -n "$output" ]]
    [[ "$output" =~ ^curb/panda/ ]]
}

@test "ACCEPTANCE: Works from any starting branch" {
    # Create and checkout feature branch
    git checkout -q -b feature/my-feature
    echo "feature" > feature.txt
    git add feature.txt
    git commit -q -m "Feature commit"

    # Initialize run branch from feature branch
    git_init_run_branch "panda"

    # Should succeed and be on run branch
    local current_branch
    current_branch=$(git_get_current_branch)
    [[ "$current_branch" =~ ^curb/panda/ ]]
}
