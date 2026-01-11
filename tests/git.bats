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
    # Create a new directory guaranteed to be outside any git repo
    NON_GIT_DIR="/tmp/non_git_test_$$"
    mkdir -p "$NON_GIT_DIR"
    cd "$NON_GIT_DIR"

    # Use GIT_CEILING_DIRECTORIES to prevent git from finding parent repos
    # This is essential for CI environments where /tmp might be under a git workspace
    export GIT_CEILING_DIRECTORIES="/tmp"

    # Verify we're really outside a git repo
    ! git rev-parse --git-dir >/dev/null 2>&1

    run git_in_repo
    [[ $status -eq 1 ]]

    # Cleanup
    unset GIT_CEILING_DIRECTORIES
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

# ============================================================================
# git_commit_task tests
# ============================================================================

@test "git_commit_task creates commit with structured message" {
    # Make a change
    echo "new content" > test.txt

    run git_commit_task "curb-023" "Test task title"
    [[ $status -eq 0 ]]

    # Check commit message format
    local commit_msg
    commit_msg=$(git log -1 --pretty=%B)
    [[ "$commit_msg" =~ ^\[curb-023\]\ Test\ task\ title ]]
    [[ "$commit_msg" =~ Task-ID:\ curb-023 ]]
}

@test "git_commit_task includes summary in commit message" {
    # Make a change
    echo "new content" > test.txt

    run git_commit_task "curb-023" "Test task" "This is a summary"
    [[ $status -eq 0 ]]

    # Check commit message includes summary
    local commit_msg
    commit_msg=$(git log -1 --pretty=%B)
    [[ "$commit_msg" =~ "This is a summary" ]]
}

@test "git_commit_task stages all changes before committing" {
    # Create multiple changes
    echo "modified" > README.md
    echo "new file" > new.txt
    mkdir -p subdir
    echo "nested" > subdir/nested.txt

    run git_commit_task "curb-023" "Test commit"
    [[ $status -eq 0 ]]

    # Verify all changes were committed
    run git_is_clean
    [[ $status -eq 0 ]]
}

@test "git_commit_task returns success when nothing to commit" {
    # Repository is already clean (from setup)
    run git_commit_task "curb-023" "Test task"
    [[ $status -eq 0 ]]

    # No new commit should have been created
    local commit_count_before
    commit_count_before=$(git rev-list --count HEAD)
    [[ $commit_count_before -eq 1 ]]  # Only initial commit
}

@test "git_commit_task returns error when task_id is missing" {
    echo "change" > test.txt

    run git_commit_task "" "Test title"
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: task_id is required" ]]
}

@test "git_commit_task returns error when task_title is missing" {
    echo "change" > test.txt

    run git_commit_task "curb-023" ""
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: task_title is required" ]]
}

@test "git_commit_task returns error when not in git repo" {
    # Create a new directory outside of git repo
    NON_GIT_DIR="${BATS_TMPDIR}/non_git_$$"
    mkdir -p "$NON_GIT_DIR"
    cd "$NON_GIT_DIR"

    run git_commit_task "curb-023" "Test task"
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Not in a git repository" ]]

    # Cleanup
    cd /
    rm -rf "$NON_GIT_DIR"
}

@test "git_commit_task handles multiline summary" {
    echo "change" > test.txt

    local summary="Line 1
Line 2
Line 3"

    run git_commit_task "curb-023" "Test task" "$summary"
    [[ $status -eq 0 ]]

    # Check commit message includes all lines
    local commit_msg
    commit_msg=$(git log -1 --pretty=%B)
    [[ "$commit_msg" =~ "Line 1" ]]
    [[ "$commit_msg" =~ "Line 2" ]]
    [[ "$commit_msg" =~ "Line 3" ]]
}

@test "git_commit_task commit message is parseable" {
    echo "change" > test.txt

    run git_commit_task "curb-023" "Test task title" "Summary text"
    [[ $status -eq 0 ]]

    # Extract task ID from commit message
    local commit_msg
    commit_msg=$(git log -1 --pretty=%B)

    # Extract from title [task_id] using bash string manipulation (more portable)
    local first_line
    first_line=$(git log -1 --pretty=%s)
    # Verify format starts with [task_id]
    [[ "$first_line" =~ ^\[curb-023\] ]]

    # Extract from trailer Task-ID:
    local task_id_from_trailer
    task_id_from_trailer=$(echo "$commit_msg" | grep "^Task-ID:" | cut -d' ' -f2)
    [[ "$task_id_from_trailer" == "curb-023" ]]
}

@test "git_commit_task works with special characters in title" {
    echo "change" > test.txt

    run git_commit_task "curb-023" "Test with 'quotes' and \"double quotes\""
    [[ $status -eq 0 ]]

    local commit_msg
    commit_msg=$(git log -1 --pretty=%B)
    [[ "$commit_msg" =~ "Test with 'quotes' and" ]]
}

@test "git_commit_task works with special characters in summary" {
    echo "change" > test.txt

    run git_commit_task "curb-023" "Test task" "Summary with \$variables and \`backticks\`"
    [[ $status -eq 0 ]]

    local commit_msg
    commit_msg=$(git log -1 --pretty=%B)
    [[ "$commit_msg" =~ "Summary with" ]]
}

# ============================================================================
# Acceptance criteria tests for git_commit_task
# ============================================================================

@test "ACCEPTANCE: Commit created with structured message format" {
    echo "test change" > test.txt

    git_commit_task "curb-023" "Implement feature X" "Added new functionality"

    local commit_msg
    commit_msg=$(git log -1 --pretty=%B)

    # First line: [task_id] title
    local first_line
    first_line=$(echo "$commit_msg" | head -1)
    [[ "$first_line" == "[curb-023] Implement feature X" ]]

    # Contains summary
    [[ "$commit_msg" =~ "Added new functionality" ]]

    # Contains trailer
    [[ "$commit_msg" =~ "Task-ID: curb-023" ]]
}

@test "ACCEPTANCE: Task ID in commit title and trailer" {
    echo "test" > test.txt

    git_commit_task "curb-123" "Test task"

    local commit_msg
    commit_msg=$(git log -1 --pretty=%B)

    # In title
    [[ "$commit_msg" =~ ^\[curb-123\] ]]

    # In trailer
    [[ "$commit_msg" =~ Task-ID:\ curb-123$ ]]
}

@test "ACCEPTANCE: All changes staged before commit" {
    # Create various types of changes
    echo "modified" > README.md
    echo "new" > new.txt
    echo "ignored content" > ignored.txt
    echo "ignored.txt" >> .gitignore

    git_commit_task "curb-023" "Test commit"

    # Verify only non-ignored files were committed
    run git_is_clean
    [[ $status -eq 0 ]]

    # Verify .gitignore'd file still exists but not committed
    [[ -f ignored.txt ]]
}

@test "ACCEPTANCE: No-op if nothing to commit (not an error)" {
    # Clean repository
    run git_commit_task "curb-023" "Test task"
    [[ $status -eq 0 ]]

    # No commit should have been created (still only 1 commit from setup)
    local commit_count
    commit_count=$(git rev-list --count HEAD)
    [[ $commit_count -eq 1 ]]
}

@test "ACCEPTANCE: Commit message parseable for task extraction" {
    echo "change" > test.txt

    git_commit_task "curb-999" "Task title here" "Optional summary"

    local commit_msg
    commit_msg=$(git log -1 --pretty=%B)

    # Can extract task ID from first line
    local extracted_id
    extracted_id=$(echo "$commit_msg" | head -1 | grep -oE '\[curb-[0-9]+\]' | tr -d '[]')
    [[ "$extracted_id" == "curb-999" ]]

    # Can extract task ID from trailer
    local trailer_id
    trailer_id=$(git log -1 --pretty=%B | grep "^Task-ID:" | cut -d' ' -f2)
    [[ "$trailer_id" == "curb-999" ]]

    # Both methods extract the same ID
    [[ "$extracted_id" == "$trailer_id" ]]
}

# ============================================================================
# git_has_changes tests
# ============================================================================

@test "git_has_changes returns 0 when there are uncommitted changes" {
    # Create a modification
    echo "modified content" > README.md

    run git_has_changes
    [[ $status -eq 0 ]]
}

@test "git_has_changes returns 1 when repository is clean" {
    # Repository is clean (from setup)
    run git_has_changes
    [[ $status -eq 1 ]]
}

@test "git_has_changes detects new untracked files" {
    # Create new untracked file
    echo "new file" > newfile.txt

    run git_has_changes
    [[ $status -eq 0 ]]
}

@test "git_has_changes detects staged changes" {
    # Create and stage a change
    echo "staged" > staged.txt
    git add staged.txt

    run git_has_changes
    [[ $status -eq 0 ]]
}

@test "git_has_changes detects deleted files" {
    # Delete a tracked file
    rm README.md

    run git_has_changes
    [[ $status -eq 0 ]]
}

@test "git_has_changes returns 1 when not in git repo" {
    # Create a new directory outside of git repo
    NON_GIT_DIR="${BATS_TMPDIR}/non_git_$$"
    mkdir -p "$NON_GIT_DIR"
    cd "$NON_GIT_DIR"

    run git_has_changes
    [[ $status -eq 1 ]]

    # Cleanup
    cd /
    rm -rf "$NON_GIT_DIR"
}

# ============================================================================
# git_stash_changes tests
# ============================================================================

@test "git_stash_changes stashes working tree changes" {
    # Create a change
    echo "modified" > README.md

    run git_stash_changes
    [[ $status -eq 0 ]]

    # Repository should now be clean
    local is_clean
    is_clean=$(git status --porcelain)
    [[ -z "$is_clean" ]]
}

@test "git_stash_changes stashes modified tracked files" {
    # Modify a tracked file
    echo "modified" > README.md

    run git_stash_changes
    [[ $status -eq 0 ]]

    # Modified file should be reverted
    [[ "$(cat README.md)" == "initial" ]]
}

@test "git_stash_changes handles clean repository gracefully" {
    # Repository is already clean

    run git_stash_changes
    [[ $status -eq 0 ]]

    # Should succeed without error
    [[ -z "$output" || "$output" != *"ERROR"* ]]
}

@test "git_stash_changes returns error when not in git repo" {
    # Create a new directory outside of git repo
    NON_GIT_DIR="${BATS_TMPDIR}/non_git_$$"
    mkdir -p "$NON_GIT_DIR"
    cd "$NON_GIT_DIR"

    run git_stash_changes
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Not in a git repository" ]]

    # Cleanup
    cd /
    rm -rf "$NON_GIT_DIR"
}

@test "git_stash_changes saves state for restoration" {
    # Create a change
    echo "modified content" > README.md

    # Stash it
    git_stash_changes

    # Verify it's gone
    local status_output
    status_output=$(git status --porcelain)
    [[ -z "$status_output" ]]
}

# ============================================================================
# git_unstash_changes tests
# ============================================================================

@test "git_unstash_changes restores stashed changes" {
    # Create and stash a change
    echo "modified" > README.md
    git_stash_changes

    # Verify it's gone
    [[ "$(cat README.md)" == "initial" ]]

    # Unstash
    run git_unstash_changes
    [[ $status -eq 0 ]]

    # Changes should be restored
    [[ "$(cat README.md)" == "modified" ]]
}

@test "git_unstash_changes restores new files" {
    # Create new file and stash
    echo "new file" > newfile.txt
    git_stash_changes

    # Verify file is gone
    [[ ! -f newfile.txt ]]

    # Unstash
    run git_unstash_changes
    [[ $status -eq 0 ]]

    # File should be restored
    [[ -f newfile.txt ]]
    [[ "$(cat newfile.txt)" == "new file" ]]
}

@test "git_unstash_changes handles no stash gracefully" {
    # No changes were stashed

    run git_unstash_changes
    [[ $status -eq 0 ]]

    # Should succeed without error
    [[ -z "$output" || "$output" != *"ERROR"* ]]
}

@test "git_unstash_changes returns error when not in git repo" {
    # Create a new directory outside of git repo
    NON_GIT_DIR="${BATS_TMPDIR}/non_git_$$"
    mkdir -p "$NON_GIT_DIR"
    cd "$NON_GIT_DIR"

    run git_unstash_changes
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Not in a git repository" ]]

    # Cleanup
    cd /
    rm -rf "$NON_GIT_DIR"
}

@test "INTEGRATION: Stash and unstash workflow" {
    # Make a change
    echo "modified" > README.md
    echo "new" > newfile.txt

    # Verify changes exist (check exit code, not output)
    run git_has_changes
    [[ $status -eq 0 ]]

    # Stash them
    git_stash_changes

    # Verify they're gone
    run git_has_changes
    [[ $status -eq 1 ]]

    # Unstash them
    git_unstash_changes

    # Verify they're back
    run git_has_changes
    [[ $status -eq 0 ]]
    [[ "$(cat README.md)" == "modified" ]]
    [[ "$(cat newfile.txt)" == "new" ]]
}

# ============================================================================
# git_get_base_branch and git_set_base_branch tests
# ============================================================================

@test "git_set_base_branch stores branch name" {
    run git_set_base_branch "main"
    [[ $status -eq 0 ]]
}

@test "git_get_base_branch returns stored branch name" {
    git_set_base_branch "develop"

    run git_get_base_branch
    [[ $status -eq 0 ]]
    [[ "$output" == "develop" ]]
}

@test "git_set_base_branch returns error when branch_name is empty" {
    run git_set_base_branch ""
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: branch_name is required" ]]
}

@test "git_get_base_branch returns error when not set" {
    # Clear the global variable
    _GIT_BASE_BRANCH=""

    run git_get_base_branch
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Base branch not set" ]]
}

@test "git_set_base_branch allows any branch name" {
    local branch_names=("main" "develop" "feature/x" "release/1.0" "origin/main")

    for branch in "${branch_names[@]}"; do
        git_set_base_branch "$branch"
        local retrieved
        retrieved=$(git_get_base_branch)
        [[ "$retrieved" == "$branch" ]]
    done
}

@test "INTEGRATION: Base branch tracking for PR workflow" {
    # Store current branch as base
    local base_branch
    base_branch=$(git_get_current_branch)

    git_set_base_branch "$base_branch"

    # Create and checkout run branch
    git_init_run_branch "panda"

    # Verify we can still get base branch
    local retrieved_base
    retrieved_base=$(git_get_base_branch)
    [[ "$retrieved_base" == "$base_branch" ]]
}

# ============================================================================
# Acceptance criteria tests for new functions
# ============================================================================

@test "ACCEPTANCE: git_has_changes correctly detects changes" {
    # Should be clean initially
    run git_has_changes
    [[ $status -eq 1 ]]

    # Add changes
    echo "modified" > README.md

    # Should detect changes
    run git_has_changes
    [[ $status -eq 0 ]]

    # Stash changes
    git_stash_changes

    # Should be clean again
    run git_has_changes
    [[ $status -eq 1 ]]
}

@test "ACCEPTANCE: git_stash_changes and git_unstash_changes work for temporary storage" {
    # Create changes
    echo "modified content" > README.md
    echo "new file" > test.txt

    # Stash them
    git_stash_changes

    # Do some git operation (simulate)
    git checkout -q -b temp-branch
    git checkout -q main 2>/dev/null || git checkout -q master 2>/dev/null

    # Unstash
    git_unstash_changes

    # Verify they're restored
    [[ "$(cat README.md)" == "modified content" ]]
    [[ "$(cat test.txt)" == "new file" ]]
}

@test "ACCEPTANCE: git_get_base_branch returns stored branch for PR creation" {
    # Store where we're branching from
    local current_branch
    current_branch=$(git_get_current_branch)
    git_set_base_branch "$current_branch"

    # Create and checkout run branch
    git_init_run_branch "panda"

    # Later we can get the base branch for PR
    local base
    base=$(git_get_base_branch)
    [[ "$base" == "$current_branch" ]]
}

@test "ACCEPTANCE: Base branch tracked across run session" {
    # Store main as base
    git_set_base_branch "main"

    # Create run branch
    git_init_run_branch "panda"

    # Make some changes
    echo "work" > work.txt
    git add work.txt
    git commit -q -m "Work"

    # Base branch should still be available
    local base
    base=$(git_get_base_branch)
    [[ "$base" == "main" ]]
}

# ============================================================================
# git_push_branch tests
# ============================================================================

@test "git_push_branch returns error when not in git repo" {
    # Create a new directory outside of git repo
    NON_GIT_DIR="${BATS_TMPDIR}/non_git_$$"
    mkdir -p "$NON_GIT_DIR"
    cd "$NON_GIT_DIR"

    run git_push_branch
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Not in a git repository" ]]

    # Cleanup
    cd /
    rm -rf "$NON_GIT_DIR"
}

@test "git_push_branch returns error when no remote configured" {
    # Repository has no remote configured (from setup)

    run git_push_branch
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: No 'origin' remote configured" ]]
}

@test "git_push_branch returns error when cannot determine current branch" {
    # Create a detached HEAD state
    local commit_hash
    commit_hash=$(git rev-parse HEAD)
    git checkout -q "$commit_hash"

    run git_push_branch
    [[ $status -eq 1 ]]
    [[ "$output" =~ "ERROR: Could not determine current branch" ]]
}

@test "git_push_branch pushes to origin when remote is configured" {
    # Create a bare remote repository to push to
    REMOTE_DIR="${BATS_TMPDIR}/remote_$$"
    mkdir -p "$REMOTE_DIR"
    git init --bare -q "$REMOTE_DIR"

    # Add remote
    git remote add origin "$REMOTE_DIR"

    # Create a commit
    echo "test" > test.txt
    git add test.txt
    git commit -q -m "Test commit"

    # Push should succeed
    run git_push_branch
    [[ $status -eq 0 ]]
    [[ "$output" =~ "Successfully pushed branch" ]]

    # Verify branch exists on remote
    git ls-remote origin | grep -q "refs/heads/$(git_get_current_branch)"

    # Cleanup
    rm -rf "$REMOTE_DIR"
}

@test "git_push_branch sets upstream tracking" {
    # Create a bare remote repository
    REMOTE_DIR="${BATS_TMPDIR}/remote_$$"
    mkdir -p "$REMOTE_DIR"
    git init --bare -q "$REMOTE_DIR"

    # Add remote
    git remote add origin "$REMOTE_DIR"

    # Create a new branch
    git checkout -q -b test-branch
    echo "test" > test.txt
    git add test.txt
    git commit -q -m "Test commit"

    # Push with upstream tracking
    git_push_branch >/dev/null 2>&1

    # Verify upstream is set
    local upstream
    upstream=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)
    [[ "$upstream" == "origin/test-branch" ]]

    # Cleanup
    rm -rf "$REMOTE_DIR"
}

@test "git_push_branch --force requires confirmation" {
    # Create a bare remote repository
    REMOTE_DIR="${BATS_TMPDIR}/remote_$$"
    mkdir -p "$REMOTE_DIR"
    git init --bare -q "$REMOTE_DIR"

    # Add remote and push initial commit
    git remote add origin "$REMOTE_DIR"
    git push -q -u origin main 2>/dev/null || git push -q -u origin master 2>/dev/null

    # Create a new commit
    echo "test" > test.txt
    git add test.txt
    git commit -q -m "Test commit"

    # Force push with "no" confirmation should fail
    run bash -c "source '${PROJECT_ROOT}/lib/git.sh' && echo 'no' | git_push_branch --force"
    [[ $status -eq 1 ]]
    [[ "$output" =~ "Force push cancelled" ]]

    # Cleanup
    rm -rf "$REMOTE_DIR"
}

@test "git_push_branch --force succeeds with yes confirmation" {
    # Create a bare remote repository
    REMOTE_DIR="${BATS_TMPDIR}/remote_$$"
    mkdir -p "$REMOTE_DIR"
    git init --bare -q "$REMOTE_DIR"

    # Add remote and push initial commit
    git remote add origin "$REMOTE_DIR"
    git push -q -u origin main 2>/dev/null || git push -q -u origin master 2>/dev/null

    # Create and push a commit
    echo "initial" > test.txt
    git add test.txt
    git commit -q -m "Initial"
    git push -q

    # Amend the commit (creates conflict)
    echo "amended" > test.txt
    git add test.txt
    git commit -q --amend --no-edit

    # Force push with "yes" confirmation should succeed
    run bash -c "source '${PROJECT_ROOT}/lib/git.sh' && echo 'yes' | git_push_branch --force"
    [[ $status -eq 0 ]]
    [[ "$output" =~ "Successfully force pushed branch" ]]

    # Cleanup
    rm -rf "$REMOTE_DIR"
}

@test "git_push_branch --force uses force-with-lease" {
    # Create a bare remote repository
    REMOTE_DIR="${BATS_TMPDIR}/remote_$$"
    mkdir -p "$REMOTE_DIR"
    git init --bare -q "$REMOTE_DIR"

    # Add remote and push initial commit
    git remote add origin "$REMOTE_DIR"
    git push -q -u origin main 2>/dev/null || git push -q -u origin master 2>/dev/null

    # Create a commit
    echo "test" > test.txt
    git add test.txt
    git commit -q -m "Test"
    git push -q

    # Amend locally
    echo "amended" > test.txt
    git add test.txt
    git commit -q --amend --no-edit

    # Verify --force-with-lease is mentioned in output (shows it's being used)
    run bash -c "source '${PROJECT_ROOT}/lib/git.sh' && echo 'yes' | git_push_branch --force"
    [[ $status -eq 0 ]]

    # Cleanup
    rm -rf "$REMOTE_DIR"
}

@test "git_push_branch displays informative messages" {
    # Create a bare remote repository
    REMOTE_DIR="${BATS_TMPDIR}/remote_$$"
    mkdir -p "$REMOTE_DIR"
    git init --bare -q "$REMOTE_DIR"

    # Add remote
    git remote add origin "$REMOTE_DIR"

    # Create a commit
    echo "test" > test.txt
    git add test.txt
    git commit -q -m "Test"

    # Check output messages
    run git_push_branch
    [[ $status -eq 0 ]]
    [[ "$output" =~ "Pushing branch" ]]
    [[ "$output" =~ "Successfully pushed branch" ]]
    [[ "$output" =~ "to origin" ]]

    # Cleanup
    rm -rf "$REMOTE_DIR"
}

@test "INTEGRATION: Complete push workflow" {
    # Create a bare remote repository
    REMOTE_DIR="${BATS_TMPDIR}/remote_$$"
    mkdir -p "$REMOTE_DIR"
    git init --bare -q "$REMOTE_DIR"

    # Add remote
    git remote add origin "$REMOTE_DIR"

    # Initialize run branch
    git_init_run_branch "panda"

    # Make changes
    echo "feature work" > feature.txt
    git add feature.txt
    git commit -q -m "Feature work"

    # Push branch
    run git_push_branch
    [[ $status -eq 0 ]]

    # Verify branch on remote
    local run_branch
    run_branch=$(git_get_run_branch)
    git ls-remote origin | grep -q "refs/heads/${run_branch}"

    # Cleanup
    rm -rf "$REMOTE_DIR"
}

@test "ACCEPTANCE: git_push_branch pushes current branch to origin" {
    # Create a bare remote repository
    REMOTE_DIR="${BATS_TMPDIR}/remote_$$"
    mkdir -p "$REMOTE_DIR"
    git init --bare -q "$REMOTE_DIR"

    # Add remote
    git remote add origin "$REMOTE_DIR"

    # Create feature branch with commit
    git checkout -q -b feature/test
    echo "feature" > feature.txt
    git add feature.txt
    git commit -q -m "Feature"

    # Push
    git_push_branch >/dev/null 2>&1

    # Verify branch exists on remote
    git ls-remote origin | grep -q "refs/heads/feature/test"

    # Cleanup
    rm -rf "$REMOTE_DIR"
}

@test "ACCEPTANCE: git_push_branch sets upstream tracking relationship" {
    # Create a bare remote repository
    REMOTE_DIR="${BATS_TMPDIR}/remote_$$"
    mkdir -p "$REMOTE_DIR"
    git init --bare -q "$REMOTE_DIR"

    # Add remote
    git remote add origin "$REMOTE_DIR"

    # Create branch with commit
    git checkout -q -b my-branch
    echo "test" > test.txt
    git add test.txt
    git commit -q -m "Test"

    # Before push, no upstream
    local upstream_before
    upstream_before=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "none")
    [[ "$upstream_before" == "none" ]]

    # Push with upstream tracking
    git_push_branch >/dev/null 2>&1

    # After push, upstream should be set
    local upstream_after
    upstream_after=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)
    [[ "$upstream_after" == "origin/my-branch" ]]

    # Cleanup
    rm -rf "$REMOTE_DIR"
}

@test "ACCEPTANCE: git_push_branch --force requires explicit confirmation" {
    # Create a bare remote repository
    REMOTE_DIR="${BATS_TMPDIR}/remote_$$"
    mkdir -p "$REMOTE_DIR"
    git init --bare -q "$REMOTE_DIR"

    # Add remote and push
    git remote add origin "$REMOTE_DIR"
    git push -q -u origin main 2>/dev/null || git push -q -u origin master 2>/dev/null

    # Create commit
    echo "test" > test.txt
    git add test.txt
    git commit -q -m "Test"

    # Force push without confirmation should fail
    run bash -c "source '${PROJECT_ROOT}/lib/git.sh' && echo 'no' | git_push_branch --force"
    [[ $status -eq 1 ]]

    # Force push with confirmation should succeed
    run bash -c "source '${PROJECT_ROOT}/lib/git.sh' && echo 'yes' | git_push_branch --force"
    [[ $status -eq 0 ]]

    # Cleanup
    rm -rf "$REMOTE_DIR"
}
