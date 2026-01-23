#!/usr/bin/env bash
#
# build-plan.sh - Run cub on all epics from a staged plan
#
# This script takes a plan slug, creates a feature branch, and runs cub
# for each epic in order. It stops on failure and commits any uncommitted
# files left after each run.
#
# Usage:
#   ./scripts/build-plan.sh <plan-slug>
#   ./scripts/build-plan.sh project-kanban-dashboard
#   ./scripts/build-plan.sh project-kanban-dashboard --dry-run
#   ./scripts/build-plan.sh project-kanban-dashboard --start-epic cub-d2v
#   ./scripts/build-plan.sh project-kanban-dashboard --only-epic cub-k8d
#
# Options:
#   --dry-run         Show what would be done without executing
#   --start-epic ID   Start from this epic (skip earlier ones)
#   --only-epic ID    Only run this specific epic
#   --no-branch       Don't create a feature branch, use current branch
#   --max-retries N   Max retry attempts per epic (default: 3)
#   --retry-delay N   Seconds between retries (default: 10)
#
# Environment variables:
#   CUB_MAX_RETRIES  - Max retry attempts per epic (default: 3)
#   CUB_RETRY_DELAY  - Seconds between retries (default: 10)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/.cub/logs"

# Flags
DRY_RUN=false
START_EPIC=""
ONLY_EPIC=""
NO_BRANCH=false

# Retry configuration
MAX_RETRIES="${CUB_MAX_RETRIES:-3}"
RETRY_DELAY="${CUB_RETRY_DELAY:-10}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_step() { echo -e "${CYAN}[STEP]${NC} $*"; }

# Parse arguments
PLAN_SLUG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --start-epic)
            START_EPIC="$2"
            shift 2
            ;;
        --only-epic)
            ONLY_EPIC="$2"
            shift 2
            ;;
        --no-branch)
            NO_BRANCH=true
            shift
            ;;
        --max-retries)
            MAX_RETRIES="$2"
            shift 2
            ;;
        --retry-delay)
            RETRY_DELAY="$2"
            shift 2
            ;;
        --help|-h)
            head -28 "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            exit 1
            ;;
        *)
            if [[ -z "$PLAN_SLUG" ]]; then
                PLAN_SLUG="$1"
            else
                log_error "Unexpected argument: $1"
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$PLAN_SLUG" ]]; then
    log_error "Usage: $0 <plan-slug> [options]"
    log_error "Run '$0 --help' for more information"
    exit 1
fi

# Ensure we're in project root
cd "$PROJECT_DIR"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Validate plan exists
PLAN_DIR="${PROJECT_DIR}/plans/${PLAN_SLUG}"
ITEMIZED_PLAN="${PLAN_DIR}/itemized-plan.md"
PLAN_JSON="${PLAN_DIR}/plan.json"

if [[ ! -d "$PLAN_DIR" ]]; then
    log_error "Plan directory not found: ${PLAN_DIR}"
    exit 1
fi

if [[ ! -f "$ITEMIZED_PLAN" ]]; then
    log_error "Itemized plan not found: ${ITEMIZED_PLAN}"
    exit 1
fi

if [[ ! -f "$PLAN_JSON" ]]; then
    log_error "Plan metadata not found: ${PLAN_JSON}"
    log_error "Run 'cub stage ${PLAN_SLUG}' first"
    exit 1
fi

# Extract spec file for branch name
SPEC_FILE=$(jq -r '.spec_file // empty' "$PLAN_JSON" 2>/dev/null || echo "")
if [[ -z "$SPEC_FILE" ]]; then
    BRANCH_NAME="feature/${PLAN_SLUG}"
else
    # Remove .md extension for branch name
    SPEC_NAME="${SPEC_FILE%.md}"
    BRANCH_NAME="feature/${SPEC_NAME}"
fi

# Extract epics from itemized plan
extract_epics() {
    grep -E "^## Epic:" "$ITEMIZED_PLAN" | sed 's/## Epic: //' | cut -d' ' -f1
}

EPICS=$(extract_epics)
if [[ -z "$EPICS" ]]; then
    log_error "No epics found in ${ITEMIZED_PLAN}"
    exit 1
fi

# Count epics
EPIC_COUNT=$(echo "$EPICS" | wc -l | tr -d ' ')

log_info "╔═══════════════════════════════════════════════════════════╗"
log_info "║  BUILD PLAN: ${PLAN_SLUG}"
log_info "╚═══════════════════════════════════════════════════════════╝"
log_info ""
log_info "Plan directory: ${PLAN_DIR}"
log_info "Branch: ${BRANCH_NAME}"
log_info "Epics found: ${EPIC_COUNT}"
log_info "Max retries: ${MAX_RETRIES}, delay: ${RETRY_DELAY}s"

if [[ "$DRY_RUN" == "true" ]]; then
    log_warn "DRY RUN MODE - no changes will be made"
fi

echo ""
log_info "Epics to process:"
for epic in $EPICS; do
    title=$(grep "^## Epic: ${epic}" "$ITEMIZED_PLAN" | sed "s/## Epic: ${epic} - //")
    echo "  - ${epic}: ${title}"
done
echo ""

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()

    command -v uv &>/dev/null || missing+=("uv")
    command -v bd &>/dev/null || missing+=("bd")
    command -v jq &>/dev/null || missing+=("jq")

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing[*]}"
        exit 1
    fi

    log_success "Prerequisites OK"
}

# Create or switch to feature branch
setup_branch() {
    if [[ "$NO_BRANCH" == "true" ]]; then
        log_info "Using current branch (--no-branch specified)"
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create/checkout branch: ${BRANCH_NAME}"
        return 0
    fi

    local current_branch
    current_branch=$(git branch --show-current)

    if [[ "$current_branch" == "$BRANCH_NAME" ]]; then
        log_info "Already on branch ${BRANCH_NAME}"
        return 0
    fi

    # Check for uncommitted changes
    if [[ -n "$(git status --porcelain)" ]]; then
        log_warn "Working directory has uncommitted changes"
        git status --short
        read -p "Stash changes and continue? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git stash push -m "build-plan: stash before ${BRANCH_NAME}"
        else
            exit 1
        fi
    fi

    # Ensure main is up to date
    log_info "Ensuring main is up to date..."
    git checkout main
    git pull --rebase

    # Create or checkout feature branch
    if git show-ref --verify --quiet "refs/heads/${BRANCH_NAME}"; then
        log_info "Checking out existing branch: ${BRANCH_NAME}"
        git checkout "$BRANCH_NAME"
        git pull --rebase origin main || true
    else
        log_info "Creating new branch: ${BRANCH_NAME}"
        git checkout -b "$BRANCH_NAME"
    fi

    log_success "On branch: ${BRANCH_NAME}"
}

# Commit any uncommitted changes
commit_changes() {
    local epic="$1"
    local message="$2"

    if [[ -z "$(git status --porcelain)" ]]; then
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would commit uncommitted changes"
        return 0
    fi

    log_warn "Uncommitted changes detected after epic ${epic}"
    git status --short

    # Stage all changes
    git add -A

    # Commit with epic context
    git commit -m "$(cat <<EOF
wip(${epic}): ${message}

Auto-committed by build-plan.sh after cub run

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"

    log_success "Changes committed"
}

# Run cub for a single epic
run_epic() {
    local epic="$1"
    local title
    title=$(grep "^## Epic: ${epic}" "$ITEMIZED_PLAN" | sed "s/## Epic: ${epic} - //" || echo "Unknown")
    local log_file="${LOG_DIR}/${epic}.log"

    log_step "═══════════════════════════════════════════════════════════"
    log_step "Epic: ${epic} - ${title}"
    log_step "═══════════════════════════════════════════════════════════"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would run: uv run cub --debug run --epic ${epic} --stream --use-current-branch"
        return 0
    fi

    log_info "Log file: ${log_file}"

    local attempt=1
    local epic_complete=false

    while [[ $attempt -le $MAX_RETRIES ]]; do
        log_info "━━━ Attempt ${attempt}/${MAX_RETRIES} ━━━"

        # Run cub for this epic
        if uv run cub --debug run --epic "$epic" --stream --use-current-branch 2>&1 | tee -a "$log_file"; then
            # cub exited cleanly - check if epic is actually complete
            local open_tasks
            open_tasks=$(bd list --parent "$epic" --status open 2>/dev/null | grep -c "^○" || echo "0")

            if [[ "$open_tasks" == "0" ]]; then
                epic_complete=true
                break
            else
                log_warn "cub exited but ${open_tasks} tasks still open for ${epic}"
            fi
        else
            log_warn "cub run exited with error for ${epic}"
        fi

        # Commit any uncommitted changes before retry
        commit_changes "$epic" "partial progress before retry ${attempt}"

        # Check if we should retry
        if [[ $attempt -lt $MAX_RETRIES ]]; then
            log_info "Waiting ${RETRY_DELAY}s before retry..."
            sleep "$RETRY_DELAY"
        fi

        ((attempt++))
    done

    # Always commit any remaining changes
    commit_changes "$epic" "implementation complete"

    if [[ "$epic_complete" != "true" ]]; then
        log_error "Epic ${epic} not complete after ${MAX_RETRIES} attempts"
        log_error "Check log: ${log_file}"

        # Show remaining tasks
        log_error "Remaining open tasks:"
        bd list --parent "$epic" --status open 2>/dev/null || true

        return 1
    fi

    log_success "Epic ${epic} complete"
    return 0
}

# Main execution
main() {
    check_prerequisites
    setup_branch

    # Determine which epics to run
    local started=false
    local epic_num=0
    local processed=0

    for epic in $EPICS; do
        ((epic_num++))

        # Handle --only-epic
        if [[ -n "$ONLY_EPIC" ]]; then
            if [[ "$epic" != "$ONLY_EPIC" ]]; then
                continue
            fi
        fi

        # Handle --start-epic
        if [[ -n "$START_EPIC" ]]; then
            if [[ "$epic" == "$START_EPIC" ]]; then
                started=true
            fi
            if [[ "$started" != "true" ]]; then
                log_info "Skipping ${epic} (before start epic)"
                continue
            fi
        fi

        echo ""
        log_info "Processing epic ${epic_num}/${EPIC_COUNT}: ${epic}"

        if ! run_epic "$epic"; then
            log_error ""
            log_error "╔═══════════════════════════════════════════════════════════╗"
            log_error "║  BUILD FAILED at epic: ${epic}"
            log_error "╚═══════════════════════════════════════════════════════════╝"
            log_error ""
            log_error "To resume from this epic:"
            log_error "  $0 ${PLAN_SLUG} --start-epic ${epic}"
            exit 1
        fi

        ((processed++))
    done

    # Sync beads at the end
    if [[ "$DRY_RUN" != "true" ]]; then
        log_info "Syncing beads..."
        bd sync || true
    fi

    echo ""
    log_success "╔═══════════════════════════════════════════════════════════╗"
    log_success "║  BUILD COMPLETE: ${PLAN_SLUG}"
    log_success "║  Processed ${processed} epic(s)"
    log_success "╚═══════════════════════════════════════════════════════════╝"
    echo ""
    log_info "Next steps:"
    log_info "  1. Review changes: git log --oneline main..HEAD"
    log_info "  2. Run tests: uv run pytest tests/ -v"
    log_info "  3. Create PR when ready"
}

main "$@"
