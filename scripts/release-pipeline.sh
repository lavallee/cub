#!/usr/bin/env bash
#
# release-pipeline.sh - Automated release pipeline for cub
#
# Supports both major versions (0.21, 0.23) and sub-point releases (0.23.3).
# Major versions get .0 suffix (0.23 -> v0.23.0), sub-point releases don't (0.23.3 -> v0.23.3).
#
# Usage:
#   ./scripts/release-pipeline.sh                  # Run all releases
#   ./scripts/release-pipeline.sh --start 0.23.3  # Start from 0.23.3
#   ./scripts/release-pipeline.sh --only 0.23.3   # Only run 0.23.3
#   ./scripts/release-pipeline.sh --dry-run       # Show what would be done
#   ./scripts/release-pipeline.sh --max-retries 10  # More retries per epic
#   ./scripts/release-pipeline.sh --retry-delay 30  # Wait longer between retries
#
# Environment variables:
#   CUB_MAX_RETRIES  - Max retry attempts per epic (default: 5)
#   CUB_RETRY_DELAY  - Seconds between retries (default: 10)
#
# Each release cycle:
#   1. Run cub to implement epic tasks
#   2. Create PR, review, fix CI issues
#   3. Merge to main
#   4. Update CHANGELOG.md and version
#   5. Tag and create GitHub release
#   6. Sync beads, return to main
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/.cub/logs"

# Version to Epic mapping (bash 3.2 compatible)
# Supports both major versions (0.21) and sub-point releases (0.23.3)
get_epic_for_version() {
    case "$1" in
        0.21) echo "cub-E07" ;;
        0.23) echo "cub-E09" ;;
        0.23.3) echo "cub-E08" ;;
        0.24) echo "cub-E10" ;;
        0.25) echo "cub-E11" ;;
        *) echo "" ;;
    esac
}

get_epic_title() {
    case "$1" in
        cub-E07) echo "Python Core Migration" ;;
        cub-E08) echo "Codebase Health Audit" ;;
        cub-E09) echo "Live Dashboard" ;;
        cub-E10) echo "Git Worktrees for Parallel Development" ;;
        cub-E11) echo "Sandbox Mode" ;;
        *) echo "Unknown" ;;
    esac
}

# Check if version is a sub-point release (e.g., 0.23.3 vs 0.23)
is_subpoint_release() {
    local version="$1"
    # Count dots - sub-point releases have 2 dots (e.g., 0.23.3)
    local dots
    dots=$(echo "$version" | tr -cd '.' | wc -c)
    [[ $dots -ge 2 ]]
}

# Get the full version string for tags/releases
# Major releases: 0.23 -> 0.23.0
# Sub-point releases: 0.23.3 -> 0.23.3 (no .0 suffix)
get_full_version() {
    local version="$1"
    if is_subpoint_release "$version"; then
        echo "$version"
    else
        echo "${version}.0"
    fi
}

VERSIONS="0.24 0.25"

# Flags
DRY_RUN=false
START_VERSION=""
ONLY_VERSION=""

# Retry configuration
MAX_RETRIES="${CUB_MAX_RETRIES:-5}"
RETRY_DELAY="${CUB_RETRY_DELAY:-10}"  # seconds between retries

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

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --start)
            START_VERSION="$2"
            shift 2
            ;;
        --only)
            ONLY_VERSION="$2"
            shift 2
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
            head -25 "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Ensure we're in project root
cd "$PROJECT_DIR"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()

    command -v claude &>/dev/null || missing+=("claude")
    command -v gh &>/dev/null || missing+=("gh")
    command -v bd &>/dev/null || missing+=("bd")
    command -v jq &>/dev/null || missing+=("jq")

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing[*]}"
        exit 1
    fi

    # Check gh auth
    if ! gh auth status &>/dev/null; then
        log_error "GitHub CLI not authenticated. Run: gh auth login"
        exit 1
    fi

    # Check git status
    if [[ -n "$(git status --porcelain)" ]]; then
        log_warn "Working directory has uncommitted changes"
        git status --short
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] || exit 1
    fi

    log_success "Prerequisites OK"
}

# Get branch name for a version
get_branch_name() {
    local version="$1"
    echo "release/v${version}"
}

# Run cub for an epic
run_epic_implementation() {
    local version="$1"
    local epic
    epic=$(get_epic_for_version "$version")
    local branch
    branch=$(get_branch_name "$version")
    local log_file="${LOG_DIR}/${epic}.log"

    log_info "═══════════════════════════════════════════════════════════"
    log_info "Starting implementation for v${version} (${epic})"
    log_info "═══════════════════════════════════════════════════════════"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would run: cub --debug run --epic ${epic} --stream"
        return 0
    fi

    # Check current branch
    local current_branch
    current_branch=$(git branch --show-current)

    if [[ "$current_branch" == "$branch" ]]; then
        log_info "Already on branch ${branch}, pulling latest..."
        git pull --rebase || true
    else
        # Ensure we're on main and up to date
        log_info "Switching to main to create/checkout release branch..."
        git checkout main
        git pull --rebase

        # Create release branch
        git checkout -b "$branch" 2>/dev/null || git checkout "$branch"
    fi

    # Run cub for this epic with retry loop
    log_info "Running cub for epic ${epic}..."
    log_info "Log file: ${log_file}"
    log_info "Max retries: ${MAX_RETRIES}, delay: ${RETRY_DELAY}s"

    local attempt=1
    local epic_complete=false

    while [[ $attempt -le $MAX_RETRIES ]]; do
        log_info "━━━ Attempt ${attempt}/${MAX_RETRIES} ━━━"

        # Run cub - it will work on tasks until epic is complete or fails
        if cub --debug run --epic "$epic" --stream 2>&1 | tee -a "$log_file"; then
            # cub exited cleanly - check if epic is actually complete
            local open_tasks
            open_tasks=$(bd list --epic "$epic" --status open --count 2>/dev/null || echo "0")

            if [[ "$open_tasks" == "0" ]]; then
                epic_complete=true
                break
            else
                log_warn "cub exited but ${open_tasks} tasks still open for ${epic}"
            fi
        else
            log_warn "cub run exited with error for ${epic}"
        fi

        # Check if we should retry
        if [[ $attempt -lt $MAX_RETRIES ]]; then
            log_info "Waiting ${RETRY_DELAY}s before retry..."
            sleep "$RETRY_DELAY"
        fi

        ((attempt++))
    done

    if [[ "$epic_complete" != "true" ]]; then
        log_error "Epic ${epic} not complete after ${MAX_RETRIES} attempts"
        log_error "Check log: ${log_file}"

        # Show remaining tasks
        log_error "Remaining open tasks:"
        bd list --epic "$epic" --status open 2>/dev/null || true

        return 1
    fi

    log_success "Epic ${epic} implementation complete"
}

# Create and manage PR
create_and_merge_pr() {
    local version="$1"
    local epic
    epic=$(get_epic_for_version "$version")
    local title
    title=$(get_epic_title "$epic")
    local branch
    branch=$(get_branch_name "$version")

    log_info "Creating PR for v${version}..."

    local full_version
    full_version=$(get_full_version "$version")

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create PR: v${full_version} - ${title}"
        return 0
    fi

    # Push branch
    git push -u origin "$branch"

    # Use Claude to create PR, handle review, and merge
    claude --print "
You are managing a release PR for cub v${full_version} - ${title}

Epic: ${epic}
Branch: ${branch}

Please do the following:

1. Create a pull request:
   - Title: v${full_version} - ${title}
   - Generate a summary from the epic's completed tasks
   - Target: main

2. Wait for CI to complete. If CI fails:
   - Analyze the failure
   - Push fixes
   - Repeat until CI passes

3. Review any PR comments and address them

4. Once CI passes and reviews are addressed, merge the PR to main

5. Report back with the merged PR URL

Use gh cli for GitHub operations.
"

    log_success "PR merged for v${version}"
}

# Update version and changelog
update_version_and_changelog() {
    local version="$1"
    local epic
    epic=$(get_epic_for_version "$version")
    local title
    title=$(get_epic_title "$epic")
    local full_version
    full_version=$(get_full_version "$version")

    log_info "Updating version and changelog for v${full_version}..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would update CUB_VERSION to ${full_version}"
        log_info "[DRY-RUN] Would update CHANGELOG.md"
        return 0
    fi

    # Ensure we're on main
    git checkout main
    git pull --rebase

    # Use Claude to update changelog and version
    claude --print "
Update the release artifacts for cub v${full_version} - ${title}

1. Update CHANGELOG.md:
   - Add a new section at the top: ## [${full_version}] - $(date +%Y-%m-%d)
   - Summarize what was accomplished in epic ${epic}
   - Group changes by: Added, Changed, Fixed, Removed (as applicable)
   - Reference task IDs where helpful

2. Update the version number in the cub executable:
   - Change CUB_VERSION=\"...\" to CUB_VERSION=\"${full_version}\"
   - The version is near line 32 in the 'cub' file

3. Commit both changes:
   git add CHANGELOG.md cub
   git commit -m 'chore: release v${full_version} - ${title}'

4. Push to main:
   git push origin main

Report the commit SHA when done.
"

    log_success "Version and changelog updated"
}

# Create release tag and GitHub release
create_release() {
    local version="$1"
    local epic
    epic=$(get_epic_for_version "$version")
    local title
    title=$(get_epic_title "$epic")
    local full_version
    full_version=$(get_full_version "$version")
    local tag="v${full_version}"

    log_info "Creating release ${tag}..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create tag: ${tag}"
        log_info "[DRY-RUN] Would create GitHub release: ${tag} - ${title}"
        return 0
    fi

    # Use Claude to create the release
    claude --print "
Create a GitHub release for cub ${tag} - ${title}

1. Create and push the tag:
   git tag -a '${tag}' -m 'Release ${tag} - ${title}'
   git push origin '${tag}'

2. Extract the release notes from CHANGELOG.md for version ${full_version}

3. Create the GitHub release:
   gh release create '${tag}' \\
     --title '${tag} - ${title}' \\
     --notes-file <(extract notes from changelog)

4. Report the release URL when done.
"

    log_success "Release ${tag} created"
}

# Cleanup and sync beads
cleanup_release() {
    local version="$1"
    local epic
    epic=$(get_epic_for_version "$version")

    log_info "Cleaning up after v${version} release..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would sync beads and return to main"
        return 0
    fi

    # Ensure epic tasks are closed
    claude --print "
Verify beads state after v${version} release:

1. Check that all tasks under epic ${epic} are closed:
   bd list --epic ${epic} --status open

   If any are still open that should be closed, close them with appropriate reasons.

2. Sync beads:
   bd sync

3. Switch to main branch:
   git checkout main
   git pull

4. Delete the release branch locally (remote can stay for history):
   git branch -d release/v${version} || true

5. Report the final state.
"

    log_success "Cleanup complete for v${version}"
}

# Run a single release cycle
run_release_cycle() {
    local version="$1"
    local full_version
    full_version=$(get_full_version "$version")

    log_info ""
    log_info "╔═══════════════════════════════════════════════════════════╗"
    log_info "║  RELEASE CYCLE: v${full_version}$(printf '%*s' $((30 - ${#full_version})) '')║"
    log_info "╚═══════════════════════════════════════════════════════════╝"
    log_info ""

    # Step 1: Implement the epic
    run_epic_implementation "$version"

    # Step 2: Create and merge PR
    create_and_merge_pr "$version"

    # Step 3: Update version and changelog
    update_version_and_changelog "$version"

    # Step 4: Create release
    create_release "$version"

    # Step 5: Cleanup
    cleanup_release "$version"

    log_success ""
    log_success "═══════════════════════════════════════════════════════════"
    log_success "  RELEASE v${full_version} COMPLETE!"
    log_success "═══════════════════════════════════════════════════════════"
    log_success ""
}

# Main execution
main() {
    log_info "Cub Release Pipeline"
    log_info "===================="

    check_prerequisites

    # Determine which versions to run
    local versions_to_run=""
    local started=false

    if [[ -n "$ONLY_VERSION" ]]; then
        versions_to_run="$ONLY_VERSION"
    else
        for v in $VERSIONS; do
            if [[ -n "$START_VERSION" ]]; then
                if [[ "$v" == "$START_VERSION" ]]; then
                    started=true
                fi
                if [[ "$started" == "true" ]]; then
                    versions_to_run="$versions_to_run $v"
                fi
            else
                versions_to_run="$versions_to_run $v"
            fi
        done
    fi

    log_info "Will process versions:$versions_to_run"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "DRY RUN MODE - no changes will be made"
    fi

    # Run each release cycle
    for version in $versions_to_run; do
        run_release_cycle "$version"
    done

    log_success ""
    log_success "╔═══════════════════════════════════════════════════════════╗"
    log_success "║  ALL RELEASES COMPLETE!                                   ║"
    log_success "╚═══════════════════════════════════════════════════════════╝"
}

main "$@"
