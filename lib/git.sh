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

# Check if the repository has uncommitted changes
# Returns 0 if there are uncommitted changes, 1 if clean
# Uses git status --porcelain for efficiency
#
# Returns:
#   0 if there are changes (has changes)
#   1 if repository is clean (no changes)
#
# Example:
#   if git_has_changes; then
#     echo "Repository has uncommitted changes"
#   else
#     echo "Repository is clean"
#   fi
git_has_changes() {
    # Check if we're in a git repository
    if ! git_in_repo; then
        return 1
    fi

    # Use git status --porcelain for efficient change detection
    # Returns empty string if clean, non-empty if there are changes
    local changes
    changes=$(git status --porcelain 2>/dev/null)

    if [[ -n "$changes" ]]; then
        return 0
    else
        return 1
    fi
}

# Global variables to store stash state
_GIT_STASH_ID=""
_GIT_STASH_SAVED=0

# Stash uncommitted changes temporarily
# Useful for switching branches or doing other git operations
#
# Returns:
#   0 on success (changes stashed or nothing to stash)
#   1 on error
#
# Example:
#   git_stash_changes
#   # do some git operations
#   git_unstash_changes
git_stash_changes() {
    # Check if we're in a git repository
    if ! git_in_repo; then
        echo "ERROR: Not in a git repository" >&2
        return 1
    fi

    # Check if there are changes to stash
    if ! git_has_changes; then
        # No changes to stash
        return 0
    fi

    # Generate a unique stash identifier based on timestamp
    _GIT_STASH_ID="curb-stash-$(date +%s)"

    # Stash changes with our identifier (include untracked files)
    if ! git stash push -u -m "$_GIT_STASH_ID" >/dev/null 2>&1; then
        echo "ERROR: Failed to stash changes" >&2
        _GIT_STASH_ID=""
        return 1
    fi

    _GIT_STASH_SAVED=1
    return 0
}

# Unstash previously stashed changes
# Restores changes that were stashed with git_stash_changes
#
# Returns:
#   0 on success (changes restored or nothing to restore)
#   1 on error
#
# Example:
#   git_stash_changes
#   # do some git operations
#   git_unstash_changes
git_unstash_changes() {
    # Check if we're in a git repository
    if ! git_in_repo; then
        echo "ERROR: Not in a git repository" >&2
        return 1
    fi

    # If no stash was saved, nothing to do
    if [[ $_GIT_STASH_SAVED -eq 0 ]] || [[ -z "$_GIT_STASH_ID" ]]; then
        return 0
    fi

    # Apply and remove the stash
    if ! git stash pop >/dev/null 2>&1; then
        echo "ERROR: Failed to unstash changes" >&2
        return 1
    fi

    # Clear stash tracking variables
    _GIT_STASH_ID=""
    _GIT_STASH_SAVED=0

    return 0
}

# Global variable to store the base branch (where we branched from)
_GIT_BASE_BRANCH=""

# Store the base branch name
# This remembers what branch we branched from, useful for PR creation
#
# Parameters:
#   $1 - branch_name: The base branch name (e.g., "main", "develop")
#
# Returns:
#   0 on success
#   1 on error (invalid branch name)
#
# Example:
#   git_set_base_branch "main"
#   # later...
#   base=$(git_get_base_branch)
git_set_base_branch() {
    local branch_name="$1"

    if [[ -z "$branch_name" ]]; then
        echo "ERROR: branch_name is required" >&2
        return 1
    fi

    _GIT_BASE_BRANCH="$branch_name"
    return 0
}

# Get the base branch name
# Returns the branch name that was set by git_set_base_branch
#
# Returns:
#   Echoes the base branch name
#   Returns 0 on success
#   Returns 1 if base branch has not been set
#
# Example:
#   base=$(git_get_base_branch)
git_get_base_branch() {
    if [[ -z "$_GIT_BASE_BRANCH" ]]; then
        echo "ERROR: Base branch not set. Call git_set_base_branch first." >&2
        return 1
    fi

    echo "$_GIT_BASE_BRANCH"
    return 0
}

# Commit all changes with a structured task message format
# Stages all changes and creates a commit with task attribution.
#
# Parameters:
#   $1 - task_id: The task identifier (e.g., "curb-023")
#   $2 - task_title: The task title/description
#   $3 - summary: Optional summary text for the commit body
#
# Returns:
#   0 on success (commit created)
#   0 if nothing to commit (not an error, just a no-op)
#   1 on error (invalid parameters or git command failure)
#
# Commit Message Format:
#   [task_id] task_title
#
#   summary (if provided)
#
#   Task-ID: task_id
#
# Example:
#   git_commit_task "curb-023" "Implement git_commit_task" "Added function with tests"
git_commit_task() {
    local task_id="$1"
    local task_title="$2"
    local summary="$3"

    # Validate required parameters
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    if [[ -z "$task_title" ]]; then
        echo "ERROR: task_title is required" >&2
        return 1
    fi

    # Check if we're in a git repository
    if ! git_in_repo; then
        echo "ERROR: Not in a git repository" >&2
        return 1
    fi

    # Stage all changes
    if ! git add -A 2>/dev/null; then
        echo "ERROR: Failed to stage changes" >&2
        return 1
    fi

    # Check if there's anything to commit
    if git diff --cached --quiet HEAD 2>/dev/null; then
        # Nothing staged, check if repo is completely clean
        if git_is_clean; then
            # Nothing to commit, but this is not an error
            return 0
        fi
    fi

    # Build commit message
    local commit_msg
    commit_msg="[${task_id}] ${task_title}"

    # Add summary if provided
    if [[ -n "$summary" ]]; then
        commit_msg="${commit_msg}

${summary}"
    fi

    # Add task ID trailer
    commit_msg="${commit_msg}

Task-ID: ${task_id}"

    # Create commit using heredoc for proper multi-line handling
    if ! git commit -m "$commit_msg" >/dev/null 2>&1; then
        echo "ERROR: Failed to create commit" >&2
        return 1
    fi

    return 0
}

# Push the current branch to remote with upstream tracking
# Pushes the current branch to origin and sets up tracking relationship.
# Requires explicit opt-in via --push flag for safety.
#
# Parameters:
#   --force: Optional flag to force push (requires explicit confirmation)
#
# Returns:
#   0 on success (branch pushed successfully)
#   1 on error (not in a git repo, no remote, push failed, or user declined force push)
#
# Example:
#   git_push_branch
#   git_push_branch --force
git_push_branch() {
    local force_push=false

    # Parse optional --force flag
    if [[ "${1:-}" == "--force" ]]; then
        force_push=true
    fi

    # Check if we're in a git repository
    if ! git_in_repo; then
        echo "ERROR: Not in a git repository" >&2
        return 1
    fi

    # Get current branch name
    local current_branch
    current_branch=$(git_get_current_branch)
    if [[ $? -ne 0 ]]; then
        echo "ERROR: Could not determine current branch" >&2
        return 1
    fi

    # Check if remote 'origin' exists
    if ! git remote get-url origin >/dev/null 2>&1; then
        echo "ERROR: No 'origin' remote configured" >&2
        return 1
    fi

    # Handle force push with extra confirmation
    if [[ "$force_push" == "true" ]]; then
        echo "WARNING: Force push requested for branch: ${current_branch}" >&2
        echo "This will overwrite remote history. Are you sure? (yes/no)" >&2
        read -r confirmation
        if [[ "$confirmation" != "yes" ]]; then
            echo "Force push cancelled" >&2
            return 1
        fi

        # Perform force push
        echo "Force pushing branch '${current_branch}' to origin..." >&2
        if git push --force-with-lease -u origin "$current_branch" 2>&1; then
            echo "Successfully force pushed branch '${current_branch}' to origin" >&2
            return 0
        else
            echo "ERROR: Failed to force push branch '${current_branch}'" >&2
            return 1
        fi
    fi

    # Normal push with upstream tracking
    echo "Pushing branch '${current_branch}' to origin..." >&2
    if git push -u origin "$current_branch" 2>&1; then
        echo "Successfully pushed branch '${current_branch}' to origin" >&2
        return 0
    else
        echo "ERROR: Failed to push branch '${current_branch}'" >&2
        return 1
    fi
}
