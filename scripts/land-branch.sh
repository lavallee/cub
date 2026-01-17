#!/usr/bin/env bash
#
# land-branch.sh - Create PR, verify CI, and optionally merge to main
#
# Takes a branch (or uses current), creates a PR, waits for CI to pass,
# addresses any review comments, and merges to main.
#
# Usage:
#   ./scripts/land-branch.sh                    # Use current branch
#   ./scripts/land-branch.sh feature/my-branch  # Specific branch
#   ./scripts/land-branch.sh --no-merge         # Do everything except merge
#   ./scripts/land-branch.sh --dry-run          # Show what would be done
#   ./scripts/land-branch.sh --title "PR Title" # Custom PR title
#   ./scripts/land-branch.sh --base develop     # Target branch (default: main)
#
# Flags:
#   --no-merge      Do everything except the final merge to main
#   --dry-run       Show what would be done without making changes
#   --title         Custom PR title (default: auto-generated from branch)
#   --base          Target branch for the PR (default: main)
#   --push          Push branch before creating PR (default: auto-detect)
#
# The script will:
#   1. Push the branch to origin (if needed)
#   2. Create a PR (or use existing)
#   3. Wait for CI to complete, fix any failures
#   4. Address PR review comments
#   5. Merge to main (unless --no-merge)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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

# Flags
DRY_RUN=false
NO_MERGE=false
FORCE_PUSH=false
BRANCH=""
PR_TITLE=""
BASE_BRANCH="main"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-merge)
            NO_MERGE=true
            shift
            ;;
        --push)
            FORCE_PUSH=true
            shift
            ;;
        --title)
            if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
                PR_TITLE="$2"
                shift 2
            else
                log_error "--title requires a value"
                exit 1
            fi
            ;;
        --base)
            if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
                BASE_BRANCH="$2"
                shift 2
            else
                log_error "--base requires a value"
                exit 1
            fi
            ;;
        --help|-h)
            head -30 "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            exit 1
            ;;
        *)
            if [[ -z "$BRANCH" ]]; then
                BRANCH="$1"
            else
                log_error "Unexpected argument: $1"
                exit 1
            fi
            shift
            ;;
    esac
done

cd "$PROJECT_DIR"

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()

    command -v claude &>/dev/null || missing+=("claude")
    command -v gh &>/dev/null || missing+=("gh")
    command -v git &>/dev/null || missing+=("git")

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing[*]}"
        exit 1
    fi

    # Check gh auth
    if ! gh auth status &>/dev/null; then
        log_error "GitHub CLI not authenticated. Run: gh auth login"
        exit 1
    fi

    log_success "Prerequisites OK"
}

# Determine branch to use
determine_branch() {
    if [[ -z "$BRANCH" ]]; then
        BRANCH=$(git branch --show-current)
        log_info "Using current branch: $BRANCH"
    fi

    if [[ "$BRANCH" == "$BASE_BRANCH" ]]; then
        log_error "Cannot create PR from $BASE_BRANCH to $BASE_BRANCH"
        exit 1
    fi

    # Verify branch exists
    if ! git rev-parse --verify "$BRANCH" &>/dev/null; then
        log_error "Branch '$BRANCH' does not exist"
        exit 1
    fi
}

# Check if branch needs to be pushed
needs_push() {
    local upstream
    upstream=$(git rev-parse --abbrev-ref --symbolic-full-name "$BRANCH@{upstream}" 2>/dev/null || echo "")

    if [[ -z "$upstream" ]]; then
        return 0  # No upstream, needs push
    fi

    # Check if local is ahead of remote
    local ahead
    ahead=$(git rev-list --count "$upstream..$BRANCH" 2>/dev/null || echo "0")
    [[ "$ahead" -gt 0 ]]
}

# Push branch to origin
push_branch() {
    if [[ "$FORCE_PUSH" == "true" ]] || needs_push; then
        log_info "Pushing branch $BRANCH to origin..."

        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "[DRY-RUN] Would push: git push -u origin $BRANCH"
            return 0
        fi

        git push -u origin "$BRANCH"
        log_success "Branch pushed"
    else
        log_info "Branch already up to date with remote"
    fi
}

# Check if PR already exists
get_existing_pr() {
    gh pr list --head "$BRANCH" --base "$BASE_BRANCH" --json number,url --jq '.[0]' 2>/dev/null || echo ""
}

# Create and manage PR using Claude
create_and_manage_pr() {
    log_info "Creating and managing PR for branch $BRANCH..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create PR and manage CI/reviews"
        if [[ "$NO_MERGE" == "true" ]]; then
            log_info "[DRY-RUN] Would NOT merge (--no-merge specified)"
        else
            log_info "[DRY-RUN] Would merge PR to $BASE_BRANCH"
        fi
        return 0
    fi

    # Check for existing PR
    local existing_pr
    existing_pr=$(get_existing_pr)

    local pr_context=""
    if [[ -n "$existing_pr" ]]; then
        local pr_number pr_url
        pr_number=$(echo "$existing_pr" | jq -r '.number')
        pr_url=$(echo "$existing_pr" | jq -r '.url')
        pr_context="An existing PR #${pr_number} already exists: ${pr_url}"
        log_info "Found existing PR: $pr_url"
    fi

    local title_instruction=""
    if [[ -n "$PR_TITLE" ]]; then
        title_instruction="Use this title for the PR: ${PR_TITLE}"
    else
        title_instruction="Generate an appropriate title from the branch name and commits"
    fi

    local merge_instruction=""
    if [[ "$NO_MERGE" == "true" ]]; then
        merge_instruction="DO NOT merge the PR. Stop after CI passes and reviews are addressed. Report the PR URL and status."
    else
        merge_instruction="Once CI passes and reviews are addressed, merge the PR to ${BASE_BRANCH}. Report the merged PR URL."
    fi

    # Use Claude to manage the PR workflow
    claude --print "
You are managing a pull request for branch '${BRANCH}' targeting '${BASE_BRANCH}'.

${pr_context}

${title_instruction}

Please do the following:

1. If no PR exists, create one:
   - Generate a summary from the commits on this branch vs ${BASE_BRANCH}
   - Use: gh pr create --base ${BASE_BRANCH} --head ${BRANCH} --title \"...\" --body \"...\"

2. Wait for CI to complete. Check status with:
   gh pr checks ${BRANCH} --watch

   If CI fails:
   - Analyze the failure using: gh pr checks ${BRANCH}
   - Read the failing check logs
   - Push fixes to the branch
   - Repeat until CI passes

3. Check for and address any PR review comments:
   gh pr view ${BRANCH} --comments

   If there are comments that need addressing:
   - Analyze the feedback
   - Make necessary changes
   - Push fixes
   - Respond to comments if needed

4. ${merge_instruction}

Use gh cli for all GitHub operations. Report progress as you go.
"

    log_success "PR workflow complete"
}

# Main execution
main() {
    local action="LAND BRANCH"
    if [[ "$NO_MERGE" == "true" ]]; then
        action="VERIFY BRANCH (no merge)"
    fi

    log_info "╔═══════════════════════════════════════════════════════════╗"
    log_info "║  ${action}$(printf '%*s' $((43 - ${#action})) '')║"
    log_info "╚═══════════════════════════════════════════════════════════╝"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "DRY RUN MODE - no changes will be made"
    fi

    echo ""

    # Step 1: Check prerequisites
    check_prerequisites

    # Step 2: Determine branch
    determine_branch

    log_info "Branch: $BRANCH -> $BASE_BRANCH"
    if [[ "$NO_MERGE" == "true" ]]; then
        log_info "Mode: Verify only (--no-merge)"
    fi
    echo ""

    # Step 3: Push branch if needed
    push_branch

    # Step 4: Create/manage PR
    create_and_manage_pr

    echo ""
    if [[ "$NO_MERGE" == "true" ]]; then
        log_success "═══════════════════════════════════════════════════════════"
        log_success "  BRANCH $BRANCH VERIFIED (not merged)"
        log_success "═══════════════════════════════════════════════════════════"
    else
        log_success "═══════════════════════════════════════════════════════════"
        log_success "  BRANCH $BRANCH LANDED!"
        log_success "═══════════════════════════════════════════════════════════"
    fi
}

main
