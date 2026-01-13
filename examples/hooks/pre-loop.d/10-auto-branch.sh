#!/usr/bin/env bash
#
# Auto-Branch Creation Hook
#
# Automatically creates a new git branch when a curb session starts.
# Uses the curb branch naming convention: cub/{session_name}/{timestamp}
#
# INSTALLATION:
#   1. Copy this script to your hooks directory:
#      mkdir -p .cub/hooks/pre-loop.d
#      cp 10-auto-branch.sh .cub/hooks/pre-loop.d/
#      chmod +x .cub/hooks/pre-loop.d/10-auto-branch.sh
#
#   Or for global hooks:
#      mkdir -p ~/.config/cub/hooks/pre-loop.d
#      cp 10-auto-branch.sh ~/.config/cub/hooks/pre-loop.d/
#      chmod +x ~/.config/cub/hooks/pre-loop.d/10-auto-branch.sh
#
# CONTEXT VARIABLES:
#   CUB_SESSION_ID    - Session ID (e.g., "porcupine-20260111-114543")
#   CUB_PROJECT_DIR   - Project directory
#   CUB_HARNESS       - Harness being used (claude, codex, etc.)
#
# BEHAVIOR:
#   - Creates branch: cub/{session_name}/{timestamp}
#   - Stores the base branch for later PR creation
#   - Idempotent: safe to run multiple times
#   - No-op if not in a git repository
#   - No-op if already on a cub/* branch
#

set -euo pipefail

# Get context from environment
PROJECT_DIR="${CUB_PROJECT_DIR:-.}"
SESSION_ID="${CUB_SESSION_ID:-}"

# Change to project directory
cd "$PROJECT_DIR"

# Skip if not in a git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "[auto-branch] Not in a git repository, skipping branch creation"
    exit 0
fi

# Skip if no session ID
if [[ -z "$SESSION_ID" ]]; then
    echo "[auto-branch] No session ID available, skipping branch creation"
    exit 0
fi

# Extract session name from session ID (format: name-YYYYMMDD-HHMMSS)
# e.g., "porcupine-20260111-114543" -> "porcupine"
SESSION_NAME="${SESSION_ID%-*-*}"
if [[ -z "$SESSION_NAME" || "$SESSION_NAME" == "$SESSION_ID" ]]; then
    # Fallback: use first part before any hyphen
    SESSION_NAME="${SESSION_ID%%-*}"
fi

# Check if already on a curb branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [[ "$CURRENT_BRANCH" == cub/* ]]; then
    echo "[auto-branch] Already on curb branch: $CURRENT_BRANCH"
    exit 0
fi

# Store base branch for later PR creation
BASE_BRANCH="$CURRENT_BRANCH"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Create branch name
BRANCH_NAME="cub/${SESSION_NAME}/${TIMESTAMP}"

# Check if branch already exists
if git rev-parse --verify "$BRANCH_NAME" >/dev/null 2>&1; then
    echo "[auto-branch] Branch '$BRANCH_NAME' already exists, checking out"
    git checkout "$BRANCH_NAME"
else
    echo "[auto-branch] Creating branch: $BRANCH_NAME (from $BASE_BRANCH)"
    git checkout -b "$BRANCH_NAME"
fi

# Store base branch in a file for post-loop PR creation
# This allows the post-loop hook to know where to create a PR
BASE_BRANCH_FILE="${PROJECT_DIR}/.cub/.base-branch"
mkdir -p "$(dirname "$BASE_BRANCH_FILE")"
echo "$BASE_BRANCH" > "$BASE_BRANCH_FILE"
echo "[auto-branch] Stored base branch: $BASE_BRANCH"

exit 0
