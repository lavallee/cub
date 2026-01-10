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

    # Extract from title [task_id]
    local task_id_from_title
    task_id_from_title=$(echo "$commit_msg" | head -1 | sed -E 's/^\[([^\]]+)\].*/\1/')
    [[ "$task_id_from_title" == "curb-023" ]]

    # Extract from trailer Task-ID:
    local task_id_from_trailer
    task_id_from_trailer=$(echo "$commit_msg" | grep "^Task-ID:" | sed 's/Task-ID: //')
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
