#!/usr/bin/env bash
#
# cmd_pr.sh - Pull Request management commands for cub
#
# Provides commands for creating and managing PRs for epics:
#   cub pr <epic-id>              # Create PR for epic
#   cub pr <epic-id> --draft      # Create draft PR
#   cub pr <epic-id> --push       # Push branch before creating PR
#

# Include guard
if [[ -n "${_CUB_CMD_PR_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_PR_SH_LOADED=1

# Colors
_pr_red() { echo -e "\033[0;31m$1\033[0m"; }
_pr_green() { echo -e "\033[0;32m$1\033[0m"; }
_pr_yellow() { echo -e "\033[1;33m$1\033[0m"; }
_pr_cyan() { echo -e "\033[0;36m$1\033[0m"; }
_pr_dim() { echo -e "\033[2m$1\033[0m"; }

# Show help for pr command
cmd_pr_help() {
    cat <<EOF
cub pr - Create pull request for an epic

Usage:
  cub pr <epic-id> [options]

Options:
  --draft            Create as draft PR
  --push             Push branch to remote before creating PR
  --title <title>    Override PR title (default: epic title)
  --base <branch>    Target branch (default: from binding or main)
  --help             Show this help message

Examples:
  cub pr cub-vd6                  # Create PR for epic
  cub pr cub-vd6 --draft          # Create draft PR
  cub pr cub-vd6 --push           # Push and create PR
  cub pr cub-vd6 --base develop   # Target develop branch

Description:
  Creates a GitHub pull request for an epic's bound branch. The PR
  body is auto-generated from the epic's closed tasks.

  Requirements:
    - Epic must have a bound branch (use 'cub branch <epic-id>' first)
    - Branch must be pushed to remote (use --push to auto-push)
    - GitHub CLI (gh) must be installed and authenticated

  The generated PR body includes:
    - Epic summary from the epic's description
    - List of completed tasks
    - Links to relevant files changed
EOF
}

# Generate PR body from epic's tasks
# Usage: _generate_pr_body <epic_id>
_generate_pr_body() {
    local epic_id="$1"

    # Get epic details
    local epic
    epic=$(get_task "" "$epic_id")

    if [[ -z "$epic" ]] || [[ "$epic" == "null" ]]; then
        echo "Unable to generate PR body: epic not found"
        return 1
    fi

    local epic_title epic_description
    epic_title=$(echo "$epic" | jq -r '.title // "Epic"')
    epic_description=$(echo "$epic" | jq -r '.description // ""')

    # Get child tasks (closed ones)
    local children
    if command -v bd >/dev/null 2>&1; then
        children=$(bd list --parent "$epic_id" --status closed --json 2>/dev/null || echo "[]")
    else
        children="[]"
    fi

    local task_count
    task_count=$(echo "$children" | jq 'length')

    # Build PR body
    cat <<EOF
## Summary

${epic_description:-$epic_title}

## Changes

EOF

    if [[ -n "$task_count" ]] && [[ "$task_count" -gt 0 ]]; then
        echo "### Completed Tasks ($task_count)"
        echo ""
        echo "$children" | jq -r '.[] | "- [x] \(.id): \(.title)"'
    else
        echo "No completed tasks found."
    fi

    cat <<EOF

## Test Plan

- [ ] Code builds without errors
- [ ] Tests pass
- [ ] Manual testing completed

---
🤖 Generated with [cub](https://github.com/lavallee/cub) v${CUB_VERSION:-0.19}
EOF
}

# Create PR for an epic
# Usage: cmd_pr <epic-id> [options]
cmd_pr() {
    local epic_id=""
    local draft=false
    local push_first=false
    local custom_title=""
    local base_branch=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --draft)
                draft=true
                ;;
            --push)
                push_first=true
                ;;
            --title)
                shift
                custom_title="${1:-}"
                ;;
            --base)
                shift
                base_branch="${1:-}"
                ;;
            --help|-h)
                cmd_pr_help
                return 0
                ;;
            -*)
                echo "Unknown option: $1" >&2
                cmd_pr_help >&2
                return 1
                ;;
            *)
                if [[ -z "$epic_id" ]]; then
                    epic_id="$1"
                else
                    echo "Unexpected argument: $1" >&2
                    return 1
                fi
                ;;
        esac
        shift
    done

    # Validate epic_id
    if [[ -z "$epic_id" ]]; then
        echo "ERROR: epic-id is required" >&2
        cmd_pr_help >&2
        return 1
    fi

    # Check if gh is installed
    if ! command -v gh >/dev/null 2>&1; then
        echo "ERROR: GitHub CLI (gh) is required but not installed" >&2
        echo "Install it with: brew install gh" >&2
        return 1
    fi

    # Check if gh is authenticated
    if ! gh auth status >/dev/null 2>&1; then
        echo "ERROR: GitHub CLI is not authenticated" >&2
        echo "Run: gh auth login" >&2
        return 1
    fi

    # Get branch binding
    local bound_branch
    bound_branch=$(branches_get_branch "$epic_id" "${PROJECT_DIR:-.}")

    if [[ -z "$bound_branch" ]]; then
        echo "ERROR: Epic $epic_id has no bound branch" >&2
        echo ""
        echo "First, bind a branch to this epic:"
        echo "  cub branch $epic_id"
        return 1
    fi

    # Get binding details
    local binding
    binding=$(branches_get_binding "$epic_id" "${PROJECT_DIR:-.}")

    if [[ -z "$base_branch" ]]; then
        base_branch=$(echo "$binding" | jq -r '.base_branch // "main"')
    fi

    # Check if PR already exists
    local existing_pr
    existing_pr=$(echo "$binding" | jq -r '.pr_number // ""')

    if [[ -n "$existing_pr" ]] && [[ "$existing_pr" != "null" ]]; then
        echo "PR #$existing_pr already exists for this epic."
        echo ""
        echo "View it at: gh pr view $existing_pr --web"
        return 0
    fi

    # Get epic details
    local epic
    epic=$(get_task "" "$epic_id")

    if [[ -z "$epic" ]] || [[ "$epic" == "null" ]]; then
        echo "ERROR: Epic $epic_id not found" >&2
        return 1
    fi

    local epic_title
    epic_title=$(echo "$epic" | jq -r '.title // "Epic"')

    if [[ -n "$custom_title" ]]; then
        epic_title="$custom_title"
    fi

    # Check current branch
    local current_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

    if [[ "$current_branch" != "$bound_branch" ]]; then
        echo "ERROR: Not on epic's bound branch" >&2
        echo "  Current: $current_branch"
        echo "  Expected: $bound_branch"
        echo ""
        echo "Switch to the branch first: git checkout $bound_branch"
        return 1
    fi

    # Push branch if requested
    if [[ "$push_first" == "true" ]]; then
        echo "Pushing branch to remote..."
        if ! git push -u origin "$bound_branch" 2>/dev/null; then
            echo "ERROR: Failed to push branch" >&2
            return 1
        fi
        _pr_green "✓ Branch pushed to origin"
        echo ""
    fi

    # Check if branch is pushed
    local remote_branch
    remote_branch=$(git ls-remote --heads origin "$bound_branch" 2>/dev/null)

    if [[ -z "$remote_branch" ]]; then
        echo "ERROR: Branch $bound_branch is not pushed to remote" >&2
        echo ""
        echo "Push it first with:"
        echo "  git push -u origin $bound_branch"
        echo ""
        echo "Or use --push flag:"
        echo "  cub pr $epic_id --push"
        return 1
    fi

    # Generate PR body
    echo "Generating PR body from epic tasks..."
    local pr_body
    pr_body=$(_generate_pr_body "$epic_id")

    # Create PR
    echo "Creating pull request..."
    echo "  Title: $epic_title"
    echo "  Base: $base_branch"
    echo "  Head: $bound_branch"
    echo ""

    local gh_flags=("--title" "$epic_title" "--body" "$pr_body" "--base" "$base_branch")

    if [[ "$draft" == "true" ]]; then
        gh_flags+=("--draft")
    fi

    local pr_url
    pr_url=$(gh pr create "${gh_flags[@]}" 2>&1)
    local gh_status=$?

    if [[ $gh_status -ne 0 ]]; then
        echo "ERROR: Failed to create PR" >&2
        echo "$pr_url" >&2
        return 1
    fi

    # Extract PR number from URL
    local pr_number
    pr_number=$(echo "$pr_url" | grep -oE '/pull/[0-9]+' | grep -oE '[0-9]+')

    if [[ -n "$pr_number" ]]; then
        # Update binding with PR number
        branches_update_pr "$epic_id" "$pr_number" "${PROJECT_DIR:-.}"
        _pr_green "✓ PR #$pr_number created"
    else
        _pr_green "✓ PR created"
    fi

    echo ""
    echo "View: $pr_url"
}

# Prompt user to create PR when closing an epic
# Usage: prompt_create_pr <epic_id>
# Returns: 0 if user wants to create PR, 1 otherwise
prompt_create_pr() {
    local epic_id="$1"

    # Check if epic has a bound branch
    local bound_branch
    bound_branch=$(branches_get_branch "$epic_id" "${PROJECT_DIR:-.}")

    if [[ -z "$bound_branch" ]]; then
        return 1  # No branch, skip prompt
    fi

    # Check if PR already exists
    local binding
    binding=$(branches_get_binding "$epic_id" "${PROJECT_DIR:-.}")
    local existing_pr
    existing_pr=$(echo "$binding" | jq -r '.pr_number // ""')

    if [[ -n "$existing_pr" ]] && [[ "$existing_pr" != "null" ]]; then
        echo ""
        echo "PR #$existing_pr already exists for this epic."
        return 1
    fi

    # Prompt
    echo ""
    _pr_cyan "Epic $epic_id is complete!"
    echo "Branch '$bound_branch' is ready for pull request."
    echo ""
    read -p "Create pull request now? [Y/n] " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "Skipped. Create PR later with: cub pr $epic_id"
        return 1
    fi

    return 0
}
