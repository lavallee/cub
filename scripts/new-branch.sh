#!/usr/bin/env bash
#
# new-branch.sh - Create a new branch from origin/main without switching to main
#
# Useful when main is checked out in a worktree and you can't switch to it.
# Creates a branch directly from origin/main, switches to it, and pushes.
#
# Usage:
#   ./scripts/new-branch.sh feature/my-feature
#   ./scripts/new-branch.sh feature/my-feature --no-push
#   ./scripts/new-branch.sh feature/my-feature --base origin/develop
#
# Flags:
#   --no-push   Create branch locally without pushing to origin
#   --base      Base ref to branch from (default: origin/main)
#   --fetch     Fetch before creating branch (default: true)
#   --no-fetch  Skip fetching (use local origin/main as-is)
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Defaults
BRANCH_NAME=""
BASE_REF="origin/main"
DO_PUSH=true
DO_FETCH=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-push)
            DO_PUSH=false
            shift
            ;;
        --no-fetch)
            DO_FETCH=false
            shift
            ;;
        --fetch)
            DO_FETCH=true
            shift
            ;;
        --base)
            if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
                BASE_REF="$2"
                shift 2
            else
                log_error "--base requires a value"
                exit 1
            fi
            ;;
        --help|-h)
            head -20 "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            exit 1
            ;;
        *)
            if [[ -z "$BRANCH_NAME" ]]; then
                BRANCH_NAME="$1"
            else
                log_error "Unexpected argument: $1"
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate
if [[ -z "$BRANCH_NAME" ]]; then
    log_error "Branch name required"
    echo ""
    echo "Usage: $0 <branch-name> [--no-push] [--base <ref>]"
    exit 1
fi

# Check if branch already exists
if git rev-parse --verify "$BRANCH_NAME" &>/dev/null; then
    log_error "Branch '$BRANCH_NAME' already exists"
    exit 1
fi

# Fetch latest from origin
if [[ "$DO_FETCH" == "true" ]]; then
    log_info "Fetching from origin..."
    git fetch origin
fi

# Verify base ref exists
if ! git rev-parse --verify "$BASE_REF" &>/dev/null; then
    log_error "Base ref '$BASE_REF' does not exist"
    log_info "Did you forget to fetch? Try: git fetch origin"
    exit 1
fi

# Create branch from base ref
log_info "Creating branch '$BRANCH_NAME' from $BASE_REF..."
git branch "$BRANCH_NAME" "$BASE_REF"

# Switch to the new branch
log_info "Switching to $BRANCH_NAME..."
git switch "$BRANCH_NAME"

# Push with upstream tracking
if [[ "$DO_PUSH" == "true" ]]; then
    log_info "Pushing to origin with upstream tracking..."
    git push -u origin "$BRANCH_NAME"
    log_success "Branch '$BRANCH_NAME' created and pushed to origin"
else
    log_success "Branch '$BRANCH_NAME' created locally (not pushed)"
    log_info "To push later: git push -u origin $BRANCH_NAME"
fi
