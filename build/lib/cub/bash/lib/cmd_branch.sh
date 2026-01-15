#!/usr/bin/env bash
#
# cmd_branch.sh - Branch management commands for cub
#
# Provides commands for managing epic-branch bindings:
#   cub branch <epic-id>                    # Create/bind branch to epic
#   cub branches                            # List all bindings
#   cub branches --cleanup                  # Clean up merged branches
#   cub branches --sync                     # Sync with remote
#

# Include guard
if [[ -n "${_CUB_CMD_BRANCH_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_BRANCH_SH_LOADED=1

# Source branches library if not already loaded
if [[ -z "${_CUB_BRANCHES_SH_LOADED:-}" ]]; then
    source "${CUB_DIR}/lib/branches.sh"
fi

# Colors (inherit from main cub if available)
_branch_red() { echo -e "\033[0;31m$1\033[0m"; }
_branch_green() { echo -e "\033[0;32m$1\033[0m"; }
_branch_yellow() { echo -e "\033[1;33m$1\033[0m"; }
_branch_blue() { echo -e "\033[0;34m$1\033[0m"; }
_branch_cyan() { echo -e "\033[0;36m$1\033[0m"; }
_branch_dim() { echo -e "\033[2m$1\033[0m"; }

# Show help for branch command
cmd_branch_help() {
    cat <<EOF
cub branch - Create and bind a branch to an epic

Usage:
  cub branch <epic-id> [options]

Options:
  --base <branch>    Base branch for the new branch (default: main)
  --name <name>      Custom branch name (default: auto-generated)
  --bind-only        Only bind current branch, don't create new one
  --help             Show this help message

Examples:
  cub branch cub-vd6                    # Create branch for epic cub-vd6
  cub branch cub-vd6 --base develop     # Use develop as base
  cub branch cub-vd6 --bind-only        # Bind current branch to epic
  cub branch cub-vd6 --name feature/v19 # Use custom branch name

Description:
  Creates a new git branch for an epic and stores the binding in
  .beads/branches.yaml. The branch name follows the pattern:

    cub/<session-name>/<epic-id>

  If --bind-only is used, the current branch is bound to the epic
  without creating a new branch.
EOF
}

# Create and bind a branch to an epic
# Usage: cmd_branch <epic-id> [options]
cmd_branch() {
    local epic_id=""
    local base_branch="main"
    local custom_name=""
    local bind_only=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --base)
                shift
                base_branch="${1:-main}"
                ;;
            --name)
                shift
                custom_name="${1:-}"
                ;;
            --bind-only)
                bind_only=true
                ;;
            --help|-h)
                cmd_branch_help
                return 0
                ;;
            -*)
                echo "Unknown option: $1" >&2
                cmd_branch_help >&2
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
        cmd_branch_help >&2
        return 1
    fi

    # Verify we're in a git repository
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        echo "ERROR: Not in a git repository" >&2
        return 1
    fi

    # Verify the epic exists (if beads is available)
    if command -v bd >/dev/null 2>&1; then
        if ! bd show "$epic_id" >/dev/null 2>&1; then
            echo "WARNING: Epic $epic_id not found in beads (continuing anyway)" >&2
        fi
    fi

    # Check if epic already has a binding
    local existing_branch
    existing_branch=$(branches_get_branch "$epic_id" "${PROJECT_DIR:-.}")
    if [[ -n "$existing_branch" ]]; then
        echo "ERROR: Epic $epic_id is already bound to branch: $existing_branch" >&2
        echo ""
        echo "To switch to this branch: git checkout $existing_branch" >&2
        echo "To unbind: cub branches --unbind $epic_id" >&2
        return 1
    fi

    local branch_name

    if [[ "$bind_only" == "true" ]]; then
        # Bind current branch
        branch_name=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
        if [[ -z "$branch_name" ]] || [[ "$branch_name" == "HEAD" ]]; then
            echo "ERROR: Could not determine current branch" >&2
            return 1
        fi

        echo "Binding current branch '$branch_name' to epic $epic_id..."
    else
        # Generate or use custom branch name
        if [[ -n "$custom_name" ]]; then
            branch_name="$custom_name"
        else
            # Generate branch name: cub/<session-name>/<epic-id>
            local session_name
            session_name="${SESSION_NAME:-$(whoami)}"
            local timestamp
            timestamp=$(date '+%Y%m%d-%H%M%S')
            branch_name="cub/${session_name}/${epic_id}-${timestamp}"
        fi

        # Check if branch already exists
        if git rev-parse --verify "$branch_name" >/dev/null 2>&1; then
            echo "ERROR: Branch '$branch_name' already exists" >&2
            return 1
        fi

        # Verify base branch exists
        if ! git rev-parse --verify "$base_branch" >/dev/null 2>&1; then
            echo "ERROR: Base branch '$base_branch' does not exist" >&2
            return 1
        fi

        # Create the branch
        echo "Creating branch '$branch_name' from '$base_branch'..."
        if ! git checkout -b "$branch_name" "$base_branch"; then
            echo "ERROR: Failed to create branch" >&2
            return 1
        fi
    fi

    # Bind the branch to the epic
    echo "Binding branch to epic $epic_id..."
    if ! branches_bind "$epic_id" "$branch_name" "$base_branch" "${PROJECT_DIR:-.}"; then
        echo "ERROR: Failed to bind branch to epic" >&2
        return 1
    fi

    echo ""
    _branch_green "✓ Branch '$branch_name' bound to epic $epic_id"
    echo ""
    echo "Next steps:"
    echo "  - Work on the epic tasks"
    echo "  - When done, run: cub pr $epic_id"
}

# Show help for branches command
cmd_branches_help() {
    cat <<EOF
cub branches - List and manage epic-branch bindings

Usage:
  cub branches [options]

Options:
  --status <status>   Filter by status (active, merged, closed)
  --json              Output as JSON
  --cleanup           Delete local branches that are merged
  --sync              Sync branch status with git/remote
  --unbind <epic-id>  Remove binding for an epic
  --help              Show this help message

Examples:
  cub branches                          # List all bindings
  cub branches --status active          # List active bindings
  cub branches --json                   # Output as JSON
  cub branches --cleanup                # Clean up merged branches
  cub branches --unbind cub-vd6         # Unbind epic from branch

Description:
  Shows all epic-branch bindings stored in .beads/branches.yaml.

  The --cleanup option deletes local branches that:
    1. Are bound to an epic
    2. Have been merged into their base branch
    3. Are not the currently checked-out branch

  The --sync option updates the status of bindings based on:
    1. Whether the branch still exists locally
    2. Whether the branch has been merged
    3. Whether a PR exists and its status
EOF
}

# List all branch bindings
# Usage: cmd_branches [options]
cmd_branches() {
    local filter_status=""
    local json_output=false
    local cleanup=false
    local sync=false
    local unbind_epic=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --status)
                shift
                filter_status="${1:-}"
                ;;
            --json)
                json_output=true
                ;;
            --cleanup)
                cleanup=true
                ;;
            --sync)
                sync=true
                ;;
            --unbind)
                shift
                unbind_epic="${1:-}"
                ;;
            --help|-h)
                cmd_branches_help
                return 0
                ;;
            -*)
                echo "Unknown option: $1" >&2
                cmd_branches_help >&2
                return 1
                ;;
            *)
                echo "Unexpected argument: $1" >&2
                return 1
                ;;
        esac
        shift
    done

    local project_dir="${PROJECT_DIR:-.}"

    # Handle unbind
    if [[ -n "$unbind_epic" ]]; then
        _cmd_branches_unbind "$unbind_epic" "$project_dir"
        return $?
    fi

    # Handle cleanup
    if [[ "$cleanup" == "true" ]]; then
        _cmd_branches_cleanup "$project_dir"
        return $?
    fi

    # Handle sync
    if [[ "$sync" == "true" ]]; then
        _cmd_branches_sync "$project_dir"
        return $?
    fi

    # List bindings
    _cmd_branches_list "$filter_status" "$json_output" "$project_dir"
}

# List branch bindings
_cmd_branches_list() {
    local filter_status="$1"
    local json_output="$2"
    local project_dir="$3"

    local bindings
    if [[ -n "$filter_status" ]]; then
        bindings=$(branches_by_status "$filter_status" "$project_dir")
    else
        bindings=$(branches_list "$project_dir")
    fi

    if [[ "$json_output" == "true" ]]; then
        echo "$bindings"
        return 0
    fi

    # Get count
    local count
    count=$(echo "$bindings" | jq 'length' 2>/dev/null)

    if [[ -z "$count" ]] || [[ "$count" -eq 0 ]]; then
        echo "No branch bindings found."
        echo ""
        echo "Create one with: cub branch <epic-id>"
        return 0
    fi

    echo "Branch-Epic Bindings ($count):"
    echo ""
    printf "%-15s %-40s %-10s %-6s\n" "EPIC" "BRANCH" "STATUS" "PR"
    printf "%-15s %-40s %-10s %-6s\n" "----" "------" "------" "--"

    echo "$bindings" | jq -r '.[] | [.epic_id, .branch_name, .status, (.pr_number // "-")] | @tsv' | while IFS=$'\t' read -r epic branch st pr; do
        # Color status
        case "$st" in
            active)
                st=$(_branch_green "$st")
                ;;
            merged)
                st=$(_branch_cyan "$st")
                ;;
            closed)
                st=$(_branch_dim "$st")
                ;;
        esac
        printf "%-15s %-40s %-10s %-6s\n" "$epic" "$branch" "$st" "$pr"
    done
}

# Unbind an epic from its branch
_cmd_branches_unbind() {
    local epic_id="$1"
    local project_dir="$2"

    if [[ -z "$epic_id" ]]; then
        echo "ERROR: epic-id is required for --unbind" >&2
        return 1
    fi

    # Get current binding
    local branch
    branch=$(branches_get_branch "$epic_id" "$project_dir")

    if [[ -z "$branch" ]]; then
        echo "No binding found for epic $epic_id"
        return 0
    fi

    echo "Unbinding epic $epic_id from branch '$branch'..."
    branches_unbind "$epic_id" "$project_dir"

    _branch_green "✓ Unbound epic $epic_id"
    echo ""
    echo "Note: The branch '$branch' still exists. Delete it with:"
    echo "  git branch -d $branch"
}

# Clean up merged branches
_cmd_branches_cleanup() {
    local project_dir="$1"

    echo "Checking for merged branches..."

    # Get merged branches
    local merged
    merged=$(branches_find_merged "$project_dir")

    local count
    count=$(echo "$merged" | jq 'length' 2>/dev/null)

    if [[ -z "$count" ]] || [[ "$count" -eq 0 ]]; then
        echo "No merged branches found to clean up."
        return 0
    fi

    echo ""
    echo "Found $count merged branch(es):"
    echo ""

    local current_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

    echo "$merged" | jq -r '.[] | [.epic_id, .branch_name] | @tsv' | while IFS=$'\t' read -r epic branch; do
        if [[ "$branch" == "$current_branch" ]]; then
            _branch_yellow "  ⚠ $epic: $branch (current branch - skipping)"
        else
            echo "  - $epic: $branch"
        fi
    done

    echo ""
    read -p "Delete these branches and update bindings? [y/N] " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        return 0
    fi

    # Delete branches and update status
    echo "$merged" | jq -r '.[] | [.epic_id, .branch_name] | @tsv' | while IFS=$'\t' read -r epic branch; do
        if [[ "$branch" == "$current_branch" ]]; then
            continue
        fi

        echo "Deleting branch '$branch'..."
        if git branch -d "$branch" 2>/dev/null; then
            branches_update_status "$epic" "merged" "$project_dir"
            _branch_green "  ✓ Deleted and marked as merged"
        else
            _branch_yellow "  ⚠ Could not delete (may need force: git branch -D $branch)"
        fi
    done

    echo ""
    _branch_green "Cleanup complete."
}

# Sync branch status with git/remote
_cmd_branches_sync() {
    local project_dir="$1"

    echo "Syncing branch bindings with git..."
    echo ""

    local bindings
    bindings=$(branches_list "$project_dir")

    local count
    count=$(echo "$bindings" | jq 'length' 2>/dev/null)

    if [[ -z "$count" ]] || [[ "$count" -eq 0 ]]; then
        echo "No bindings to sync."
        return 0
    fi

    local updates=0

    echo "$bindings" | jq -c '.[]' | while IFS= read -r binding; do
        local epic branch current_status
        epic=$(echo "$binding" | jq -r '.epic_id')
        branch=$(echo "$binding" | jq -r '.branch_name')
        current_status=$(echo "$binding" | jq -r '.status')

        # Skip if already merged or closed
        if [[ "$current_status" != "active" ]]; then
            continue
        fi

        # Check if branch still exists
        if ! git rev-parse --verify "$branch" >/dev/null 2>&1; then
            echo "  Branch '$branch' no longer exists - marking as closed"
            branches_update_status "$epic" "closed" "$project_dir"
            ((updates++))
            continue
        fi

        # Check if merged into base
        local base
        base=$(echo "$binding" | jq -r '.base_branch // "main"')
        if git branch --merged "$base" 2>/dev/null | grep -q "^[[:space:]]*${branch}$"; then
            echo "  Branch '$branch' is merged into $base - marking as merged"
            branches_update_status "$epic" "merged" "$project_dir"
            ((updates++))
        fi
    done

    echo ""
    if [[ $updates -eq 0 ]]; then
        echo "All bindings are up to date."
    else
        _branch_green "Updated $updates binding(s)."
    fi
}
