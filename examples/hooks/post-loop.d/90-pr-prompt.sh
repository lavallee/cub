#!/usr/bin/env bash
#
# PR Creation Prompt Hook
#
# Offers to create a GitHub Pull Request at the end of a successful cub run.
# This hook runs after the curb loop completes via the post-loop hook point.
#
# INSTALLATION:
#   1. Ensure you have the GitHub CLI installed: https://cli.github.com/
#      brew install gh    # macOS
#      gh auth login      # authenticate
#
#   2. Copy this script to your hooks directory:
#      mkdir -p .cub/hooks/post-loop.d
#      cp 90-pr-prompt.sh .cub/hooks/post-loop.d/
#      chmod +x .cub/hooks/post-loop.d/90-pr-prompt.sh
#
#   Or for global hooks:
#      mkdir -p ~/.config/cub/hooks/post-loop.d
#      cp 90-pr-prompt.sh ~/.config/cub/hooks/post-loop.d/
#      chmod +x ~/.config/cub/hooks/post-loop.d/90-pr-prompt.sh
#
# CONTEXT VARIABLES:
#   CUB_SESSION_ID    - Session ID (e.g., "porcupine-20260111-114543")
#   CUB_PROJECT_DIR   - Project directory
#   CUB_HARNESS       - Harness used (claude, codex, etc.)
#
# PREREQUISITES:
#   - gh CLI installed and authenticated
#   - Repository has a GitHub remote
#   - Branch has been pushed to origin
#   - Base branch stored in .cub/.base-branch (set by auto-branch hook)
#
# BEHAVIOR:
#   - Skips if gh CLI not installed
#   - Skips if not in a git repo with GitHub remote
#   - Skips if no commits ahead of base branch
#   - Skips in non-interactive mode (no TTY)
#   - Prompts user before creating PR
#   - Generates PR title from branch name or commits
#   - Generates PR body from recent commits
#

set -euo pipefail

# Get context from environment
PROJECT_DIR="${CUB_PROJECT_DIR:-.}"
SESSION_ID="${CUB_SESSION_ID:-}"

# Change to project directory
cd "$PROJECT_DIR"

# Check if running interactively (has a TTY)
if [[ ! -t 0 ]]; then
    echo "[pr-prompt] Not running interactively, skipping PR prompt"
    exit 0
fi

# Check if gh CLI is installed
if ! command -v gh >/dev/null 2>&1; then
    echo "[pr-prompt] GitHub CLI (gh) not installed, skipping PR prompt"
    echo "[pr-prompt] Install: brew install gh && gh auth login"
    exit 0
fi

# Check if we're in a git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "[pr-prompt] Not in a git repository, skipping PR prompt"
    exit 0
fi

# Check if this is a GitHub repository
if ! gh repo view >/dev/null 2>&1; then
    echo "[pr-prompt] Not a GitHub repository, skipping PR prompt"
    exit 0
fi

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [[ -z "$CURRENT_BRANCH" ]]; then
    echo "[pr-prompt] Could not determine current branch, skipping PR prompt"
    exit 0
fi

# Don't create PRs from main/master
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
    echo "[pr-prompt] On main/master branch, skipping PR prompt"
    exit 0
fi

# Read base branch from .cub/.base-branch (set by auto-branch hook)
BASE_BRANCH_FILE="${PROJECT_DIR}/.cub/.base-branch"
if [[ -f "$BASE_BRANCH_FILE" ]]; then
    BASE_BRANCH=$(cat "$BASE_BRANCH_FILE")
else
    # Default to main or master
    if git rev-parse --verify main >/dev/null 2>&1; then
        BASE_BRANCH="main"
    elif git rev-parse --verify master >/dev/null 2>&1; then
        BASE_BRANCH="master"
    else
        echo "[pr-prompt] Could not determine base branch, skipping PR prompt"
        exit 0
    fi
fi

# Check if there are commits ahead of base branch
COMMITS_AHEAD=$(git rev-list --count "${BASE_BRANCH}..HEAD" 2>/dev/null || echo "0")
if [[ "$COMMITS_AHEAD" == "0" ]]; then
    echo "[pr-prompt] No commits ahead of ${BASE_BRANCH}, skipping PR prompt"
    exit 0
fi

# Check if branch has been pushed to origin
if ! git ls-remote --exit-code origin "$CURRENT_BRANCH" >/dev/null 2>&1; then
    echo "[pr-prompt] Branch not pushed to origin, pushing now..."
    if ! git push -u origin "$CURRENT_BRANCH"; then
        echo "[pr-prompt] Failed to push branch, skipping PR prompt"
        exit 0
    fi
fi

# Check if PR already exists for this branch
EXISTING_PR=$(gh pr list --head "$CURRENT_BRANCH" --json number --jq '.[0].number' 2>/dev/null || echo "")
if [[ -n "$EXISTING_PR" ]]; then
    PR_URL=$(gh pr view "$EXISTING_PR" --json url --jq '.url' 2>/dev/null || echo "")
    echo "[pr-prompt] PR already exists: $PR_URL"
    exit 0
fi

# Generate PR title from branch name or first commit
# Extract session name from branch: cub/porcupine/20260111-114543 -> "Porcupine session"
if [[ "$CURRENT_BRANCH" == cub/* ]]; then
    SESSION_NAME=$(echo "$CURRENT_BRANCH" | cut -d'/' -f2 | tr '[:lower:]' '[:upper:]' | head -c1)
    SESSION_NAME_REST=$(echo "$CURRENT_BRANCH" | cut -d'/' -f2 | tail -c+2)
    SUGGESTED_TITLE="Curb: ${SESSION_NAME}${SESSION_NAME_REST} session (${COMMITS_AHEAD} commits)"
else
    # Use first commit message
    SUGGESTED_TITLE=$(git log -1 --format="%s" "${BASE_BRANCH}..HEAD" 2>/dev/null || echo "Changes from $CURRENT_BRANCH")
fi

# Generate PR body from commit messages
COMMIT_LOG=$(git log --oneline "${BASE_BRANCH}..HEAD" 2>/dev/null | head -20 || echo "No commits")
PR_BODY="## Summary

Automated changes from curb session.

## Commits

\`\`\`
${COMMIT_LOG}
\`\`\`

---
Generated by curb post-loop hook"

# Display PR preview
echo ""
echo "=========================================="
echo "[pr-prompt] Ready to create Pull Request"
echo "=========================================="
echo ""
echo "Branch:  $CURRENT_BRANCH"
echo "Base:    $BASE_BRANCH"
echo "Commits: $COMMITS_AHEAD ahead"
echo ""
echo "Title:   $SUGGESTED_TITLE"
echo ""
echo "Body preview:"
echo "$COMMIT_LOG" | head -10 | sed 's/^/  /'
echo ""

# Prompt user
read -r -p "[pr-prompt] Create PR? [y/N/e(dit)] " response
case "$response" in
    [yY]|[yY][eE][sS])
        echo "[pr-prompt] Creating PR..."
        if gh pr create --title "$SUGGESTED_TITLE" --body "$PR_BODY" --base "$BASE_BRANCH"; then
            echo "[pr-prompt] PR created successfully!"
        else
            echo "[pr-prompt] Failed to create PR" >&2
            exit 1
        fi
        ;;
    [eE]|[eE][dD][iI][tT])
        echo "[pr-prompt] Opening PR editor..."
        if gh pr create --base "$BASE_BRANCH"; then
            echo "[pr-prompt] PR created successfully!"
        else
            echo "[pr-prompt] Failed to create PR" >&2
            exit 1
        fi
        ;;
    *)
        echo "[pr-prompt] Skipping PR creation"
        echo "[pr-prompt] To create manually: gh pr create --base $BASE_BRANCH"
        ;;
esac

exit 0
