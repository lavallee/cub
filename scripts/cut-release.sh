#!/usr/bin/env bash
#
# cut-release.sh - Cut a release using a release branch workflow
#
# Creates a release branch, bumps versions, generates changelog, opens a PR
# to main, waits for CI, merges, tags, and creates a GitHub release.
#
# Usage:
#   ./scripts/cut-release.sh 0.29.0 --title "Spectral Projection"
#   ./scripts/cut-release.sh 0.29.0 --title "Spectral Projection" --dry-run
#   ./scripts/cut-release.sh 0.29.0 --title "Spectral Projection" --no-push
#   ./scripts/cut-release.sh 0.29.0 --title "Spectral Projection" --no-wait
#   ./scripts/cut-release.sh 0.29.0 --title "Spectral Projection" --skip-changelog
#
# Finish a previously created release PR:
#   ./scripts/cut-release.sh 0.29.0 --title "Spectral Projection" --finish 42
#   ./scripts/cut-release.sh 0.29.0 --title "Spectral Projection" --finish 42 --dry-run
#
# Required:
#   VERSION              Semver version (e.g. 0.29.0)
#   --title "Name"       Human-readable release name
#
# Optional:
#   --dry-run            Preview only, no changes
#   --no-push            Stop after local commit on release branch
#   --no-wait            Create PR but don't wait for CI or merge
#   --skip-changelog     Skip changelog generation
#   --finish <PR>        Finish a release from an existing PR (merge, tag, release)
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
NO_PUSH=false
NO_WAIT=false
SKIP_CHANGELOG=false
FINISH_PR=""
VERSION=""
RELEASE_TITLE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-push)
            NO_PUSH=true
            shift
            ;;
        --no-wait)
            NO_WAIT=true
            shift
            ;;
        --skip-changelog)
            SKIP_CHANGELOG=true
            shift
            ;;
        --title)
            if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
                RELEASE_TITLE="$2"
                shift 2
            else
                log_error "--title requires a value"
                exit 1
            fi
            ;;
        --finish)
            if [[ -n "${2:-}" && ! "$2" =~ ^- ]]; then
                FINISH_PR="$2"
                shift 2
            else
                log_error "--finish requires a PR number or URL"
                exit 1
            fi
            ;;
        --help|-h)
            head -29 "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            exit 1
            ;;
        *)
            if [[ -z "$VERSION" ]]; then
                VERSION="$1"
            else
                log_error "Unexpected argument: $1"
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate version argument
if [[ -z "$VERSION" ]]; then
    log_error "Version argument required"
    echo "Usage: $0 <version> --title \"Release Name\" [--dry-run] [--no-push] [--no-wait] [--skip-changelog]"
    echo "       $0 <version> --title \"Release Name\" --finish <PR>"
    echo "Example: $0 0.29.0 --title \"Spectral Projection\""
    echo "Example: $0 0.29.0 --title \"Spectral Projection\" --finish 42"
    exit 1
fi

# Validate version format (X.Y.Z)
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    log_error "Invalid version format: $VERSION"
    echo "Version must be in format X.Y.Z (e.g., 0.29.0)"
    exit 1
fi

# Validate --title is provided
if [[ -z "$RELEASE_TITLE" ]]; then
    log_error "--title is required"
    echo "Usage: $0 <version> --title \"Release Name\""
    echo "Example: $0 0.29.0 --title \"Spectral Projection\""
    exit 1
fi

TAG="v${VERSION}"
RELEASE_BRANCH="release/${TAG}"
FORMATTED_TITLE="${TAG} - ${RELEASE_TITLE}"

cd "$PROJECT_DIR"

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()

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

    # Check we're on main
    local current_branch
    current_branch=$(git branch --show-current)
    if [[ "$current_branch" != "main" ]]; then
        log_error "Must be on main branch (currently on: $current_branch)"
        exit 1
    fi

    # Check for uncommitted changes
    if [[ -n "$(git status --porcelain)" ]]; then
        log_error "Working directory has uncommitted changes"
        git status --short
        exit 1
    fi

    # Check if tag already exists
    if git rev-parse "$TAG" &>/dev/null; then
        log_error "Tag $TAG already exists"
        exit 1
    fi

    # Pull latest
    log_info "Pulling latest from origin/main..."
    git pull --rebase

    log_success "Prerequisites OK"
}

# Create release branch from main
create_release_branch() {
    log_info "Creating release branch: $RELEASE_BRANCH"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create branch: $RELEASE_BRANCH"
        return 0
    fi

    git checkout -b "$RELEASE_BRANCH"
    log_success "Created and switched to $RELEASE_BRANCH"
}

# Update version in pyproject.toml
update_pyproject_version() {
    local file="$PROJECT_DIR/pyproject.toml"

    log_info "Updating version in pyproject.toml to $VERSION..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would update pyproject.toml"
        return 0
    fi

    # Use sed to update version line
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" "$file"
    else
        sed -i "s/^version = \".*\"/version = \"$VERSION\"/" "$file"
    fi

    # Verify the change
    if grep -q "version = \"$VERSION\"" "$file"; then
        log_success "Updated pyproject.toml"
    else
        log_error "Failed to update pyproject.toml"
        exit 1
    fi
}

# Update version in src/cub/__init__.py
update_init_version() {
    local file="$PROJECT_DIR/src/cub/__init__.py"

    log_info "Updating version in src/cub/__init__.py to $VERSION..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would update src/cub/__init__.py"
        return 0
    fi

    # Use sed to update __version__ line
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "s/^__version__ = \".*\"/__version__ = \"$VERSION\"/" "$file"
    else
        sed -i "s/^__version__ = \".*\"/__version__ = \"$VERSION\"/" "$file"
    fi

    # Verify the change
    if grep -q "__version__ = \"$VERSION\"" "$file"; then
        log_success "Updated src/cub/__init__.py"
    else
        log_error "Failed to update src/cub/__init__.py"
        exit 1
    fi
}

# Generate and update changelog
update_changelog() {
    local changelog="$PROJECT_DIR/CHANGELOG.md"

    log_info "Generating CHANGELOG.md entry..."

    # Check if this version already has an entry
    if grep -q "## \[$VERSION\]" "$changelog"; then
        log_success "CHANGELOG.md already has entry for $VERSION"
        return 0
    fi

    if [[ "$SKIP_CHANGELOG" == "true" ]]; then
        log_warn "Skipping changelog update (--skip-changelog)"
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would generate changelog entry:"
        python3 "${SCRIPT_DIR}/generate_changelog.py" "$VERSION" --dry-run || true
        return 0
    fi

    # Generate and prepend changelog entry
    if [[ -f "${SCRIPT_DIR}/generate_changelog.py" ]]; then
        python3 "${SCRIPT_DIR}/generate_changelog.py" "$VERSION" --prepend || {
            log_error "Failed to generate changelog"
            exit 1
        }
        log_success "CHANGELOG.md updated"
    else
        log_error "generate_changelog.py not found"
        exit 1
    fi
}

# Extract release notes from changelog
extract_release_notes() {
    local changelog="$PROJECT_DIR/CHANGELOG.md"

    # Extract content between this version header and the next
    awk "/^## \[$VERSION\]/{found=1; next} /^## \[/{if(found) exit} found{print}" "$changelog"
}

# Commit version changes on release branch
commit_version_changes() {
    log_info "Committing version changes on $RELEASE_BRANCH..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would commit: chore: bump version to $VERSION"
        return 0
    fi

    git add pyproject.toml src/cub/__init__.py CHANGELOG.md

    # Check if there are changes to commit
    if git diff --cached --quiet; then
        log_warn "No changes to commit"
        return 0
    fi

    git commit -m "chore: bump version to $VERSION"
    log_success "Committed version changes"
}

# Push release branch and create PR
create_pr() {
    if [[ "$NO_PUSH" == "true" ]]; then
        log_warn "Skipping PR creation (--no-push)"
        return 0
    fi

    log_info "Pushing release branch and creating PR..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would push $RELEASE_BRANCH and create PR to main"
        return 0
    fi

    git push -u origin "$RELEASE_BRANCH"

    local notes
    notes=$(extract_release_notes)
    if [[ -z "$notes" ]]; then
        notes="Release ${TAG}"
    fi

    local pr_url
    pr_url=$(gh pr create \
        --base main \
        --head "$RELEASE_BRANCH" \
        --title "chore: release ${TAG}" \
        --body "$(cat <<EOF
## Release ${FORMATTED_TITLE}

${notes}

---
*Auto-generated by \`cut-release.sh\`*
EOF
)")

    log_success "Created PR: $pr_url"
}

# Wait for CI checks to pass
wait_for_ci() {
    if [[ "$NO_PUSH" == "true" || "$NO_WAIT" == "true" ]]; then
        if [[ "$NO_WAIT" == "true" && "$NO_PUSH" != "true" ]]; then
            log_warn "Skipping CI wait (--no-wait). Use --finish <PR#> to complete the release later."
        fi
        return 0
    fi

    log_info "Waiting for CI checks to pass (timeout: 10 min)..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would wait for CI checks on $RELEASE_BRANCH"
        return 0
    fi

    local timeout=600  # 10 minutes
    local interval=15
    local elapsed=0

    while [[ $elapsed -lt $timeout ]]; do
        local status
        local rc=0
        status=$(gh pr checks "$RELEASE_BRANCH" 2>&1) || rc=$?

        if [[ $rc -eq 0 ]]; then
            log_success "All CI checks passed"
            return 0
        fi

        # rc=1 means some checks failed (not pending)
        if echo "$status" | grep -q "fail"; then
            log_error "CI checks failed:"
            echo "$status"
            exit 1
        fi

        # No checks yet or still pending
        log_info "CI checks pending... (${elapsed}s / ${timeout}s)"
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    log_error "CI checks timed out after ${timeout}s"
    log_info "Finish later: $0 $VERSION --title \"$RELEASE_TITLE\" --finish \$(gh pr view $RELEASE_BRANCH --json number --jq .number)"
    exit 1
}

# Merge the PR via squash merge
merge_pr() {
    if [[ "$NO_PUSH" == "true" || "$NO_WAIT" == "true" ]]; then
        return 0
    fi

    log_info "Merging release PR..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would squash-merge PR and delete $RELEASE_BRANCH"
        return 0
    fi

    gh pr merge "$RELEASE_BRANCH" --squash --delete-branch

    # Switch back to main and pull the merge commit
    git checkout main
    git pull --rebase

    log_success "PR merged and $RELEASE_BRANCH deleted"
}

# Create and push tag on main
create_tag() {
    if [[ "$NO_PUSH" == "true" || "$NO_WAIT" == "true" ]]; then
        if [[ "$NO_PUSH" == "true" ]]; then
            log_warn "Skipping tag creation (--no-push)"
        else
            log_warn "Skipping tag creation (--no-wait, will tag after merge)"
        fi
        return 0
    fi

    log_info "Creating tag $TAG on main..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create and push tag: $TAG"
        return 0
    fi

    git tag -a "$TAG" -m "Release ${FORMATTED_TITLE}"
    git push origin "$TAG"
    log_success "Created and pushed tag $TAG"
}

# Create GitHub release
create_github_release() {
    if [[ "$NO_PUSH" == "true" || "$NO_WAIT" == "true" ]]; then
        log_warn "Skipping GitHub release (not merged yet)"
        return 0
    fi

    log_info "Creating GitHub release for $TAG..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create GitHub release: $TAG (title: $FORMATTED_TITLE)"
        return 0
    fi

    # Extract release notes
    local notes
    notes=$(extract_release_notes)

    if [[ -z "$notes" ]]; then
        log_warn "No release notes found in CHANGELOG.md"
        notes="Release ${FORMATTED_TITLE}"
    fi

    gh release create "$TAG" \
        --title "$FORMATTED_TITLE" \
        --notes "$notes"

    log_success "Created GitHub release: $FORMATTED_TITLE"

    # Show release URL
    local release_url
    release_url=$(gh release view "$TAG" --json url --jq '.url')
    log_info "Release URL: $release_url"
}

# Update webpage changelog
update_webpage() {
    if [[ "$NO_PUSH" == "true" || "$NO_WAIT" == "true" ]]; then
        log_warn "Skipping webpage update"
        return 0
    fi

    log_info "Updating webpage changelog..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would run update_webpage_changelog.py"
        return 0
    fi

    if [[ -f "${SCRIPT_DIR}/update_webpage_changelog.py" ]]; then
        python3 "${SCRIPT_DIR}/update_webpage_changelog.py" \
            --version "$VERSION" --title "$RELEASE_TITLE" || {
            log_warn "Failed to update webpage changelog (non-fatal)"
            return 0
        }

        # Commit webpage changes if any
        if [[ -n "$(git status --porcelain docs/)" ]]; then
            git add docs/
            git commit -m "docs: update webpage for $TAG"
            git push origin main
            log_success "Webpage updated and pushed"
        else
            log_info "No webpage changes needed"
        fi
    else
        log_warn "update_webpage_changelog.py not found, skipping"
    fi
}

# Check prerequisites for --finish mode
check_finish_prerequisites() {
    log_info "Checking prerequisites for --finish..."

    local missing=()

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

    # Check for uncommitted changes
    if [[ -n "$(git status --porcelain)" ]]; then
        log_error "Working directory has uncommitted changes"
        git status --short
        exit 1
    fi

    # Check if tag already exists
    if git rev-parse "$TAG" &>/dev/null; then
        log_error "Tag $TAG already exists"
        exit 1
    fi

    # Verify the PR exists and is open/merged
    local pr_state
    pr_state=$(gh pr view "$FINISH_PR" --json state --jq '.state' 2>/dev/null) || {
        log_error "Could not find PR: $FINISH_PR"
        exit 1
    }

    if [[ "$pr_state" == "CLOSED" ]]; then
        log_error "PR $FINISH_PR is closed (not merged). Cannot finish."
        exit 1
    fi

    # Verify the PR head branch matches expected release branch
    local pr_head
    pr_head=$(gh pr view "$FINISH_PR" --json headRefName --jq '.headRefName')
    if [[ "$pr_head" != "$RELEASE_BRANCH" ]]; then
        log_warn "PR head branch is '$pr_head', expected '$RELEASE_BRANCH'"
        log_warn "Proceeding anyway — make sure this is the right PR"
    fi

    log_success "Finish prerequisites OK (PR $FINISH_PR, state: $pr_state)"
}

# Finish a release from an existing PR: merge → tag → release → webpage → cleanup
finish_release() {
    log_info "╔═══════════════════════════════════════════════════════════╗"
    log_info "║  FINISH RELEASE: ${FORMATTED_TITLE}$(printf '%*s' $((35 - ${#FORMATTED_TITLE})) '' 2>/dev/null || echo '')║"
    log_info "╚═══════════════════════════════════════════════════════════╝"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "DRY RUN MODE - no changes will be made"
    fi

    log_info "Finishing release from PR $FINISH_PR"
    echo ""

    # Step 1: Check finish prerequisites
    check_finish_prerequisites

    # Step 2: Check if PR is already merged
    local pr_state
    pr_state=$(gh pr view "$FINISH_PR" --json state --jq '.state')

    if [[ "$pr_state" == "MERGED" ]]; then
        log_info "PR $FINISH_PR is already merged"

        if [[ "$DRY_RUN" != "true" ]]; then
            # Make sure we're on main with the merge commit
            git checkout main 2>/dev/null || true
            git pull --rebase
        fi
    else
        # PR is still open — wait for CI then merge
        log_info "PR $FINISH_PR is still open, checking CI..."

        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "[DRY-RUN] Would wait for CI and merge PR $FINISH_PR"
        else
            # Wait for CI (reuse existing function but target PR number)
            local timeout=600
            local interval=15
            local elapsed=0

            while [[ $elapsed -lt $timeout ]]; do
                local status
                local rc=0
                status=$(gh pr checks "$FINISH_PR" 2>&1) || rc=$?

                if [[ $rc -eq 0 ]]; then
                    log_success "All CI checks passed"
                    break
                fi

                # rc=1 means some checks failed (not pending)
                if echo "$status" | grep -q "fail"; then
                    log_error "CI checks failed:"
                    echo "$status"
                    exit 1
                fi

                log_info "CI checks pending... (${elapsed}s / ${timeout}s)"
                sleep "$interval"
                elapsed=$((elapsed + interval))
            done

            if [[ $elapsed -ge $timeout ]]; then
                log_error "CI checks timed out after ${timeout}s"
                exit 1
            fi

            # Merge
            log_info "Merging PR $FINISH_PR..."
            gh pr merge "$FINISH_PR" --squash --delete-branch

            git checkout main
            git pull --rebase

            log_success "PR merged"
        fi
    fi

    # Step 3: Tag on main
    log_info "Creating tag $TAG on main..."
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create and push tag: $TAG"
    else
        git tag -a "$TAG" -m "Release ${FORMATTED_TITLE}"
        git push origin "$TAG"
        log_success "Created and pushed tag $TAG"
    fi

    # Step 4: Create GitHub release
    log_info "Creating GitHub release for $TAG..."
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create GitHub release: $TAG (title: $FORMATTED_TITLE)"
    else
        local notes
        notes=$(extract_release_notes)

        if [[ -z "$notes" ]]; then
            log_warn "No release notes found in CHANGELOG.md"
            notes="Release ${FORMATTED_TITLE}"
        fi

        gh release create "$TAG" \
            --title "$FORMATTED_TITLE" \
            --notes "$notes"

        log_success "Created GitHub release: $FORMATTED_TITLE"

        local release_url
        release_url=$(gh release view "$TAG" --json url --jq '.url')
        log_info "Release URL: $release_url"
    fi

    # Step 5: Update webpage
    update_webpage_for_finish

    # Step 6: Clean up
    cleanup

    echo ""
    log_success "═══════════════════════════════════════════════════════════"
    log_success "  RELEASE ${FORMATTED_TITLE} COMPLETE!"
    log_success "═══════════════════════════════════════════════════════════"
}

# Webpage update for --finish mode (no NO_PUSH/NO_WAIT guards)
update_webpage_for_finish() {
    log_info "Updating webpage changelog..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would run update_webpage_changelog.py"
        return 0
    fi

    if [[ -f "${SCRIPT_DIR}/update_webpage_changelog.py" ]]; then
        python3 "${SCRIPT_DIR}/update_webpage_changelog.py" \
            --version "$VERSION" --title "$RELEASE_TITLE" || {
            log_warn "Failed to update webpage changelog (non-fatal)"
            return 0
        }

        # Commit webpage changes if any
        if [[ -n "$(git status --porcelain docs/)" ]]; then
            git add docs/
            git commit -m "docs: update webpage for $TAG"
            git push origin main
            log_success "Webpage updated and pushed"
        else
            log_info "No webpage changes needed"
        fi
    else
        log_warn "update_webpage_changelog.py not found, skipping"
    fi
}

# Clean up local release branch if it still exists
cleanup() {
    if git rev-parse --verify "$RELEASE_BRANCH" &>/dev/null 2>&1; then
        if [[ "$DRY_RUN" != "true" ]]; then
            git branch -d "$RELEASE_BRANCH" 2>/dev/null || true
        fi
    fi
}

# Main execution
main() {
    # Dispatch to --finish mode if set
    if [[ -n "$FINISH_PR" ]]; then
        finish_release
        return $?
    fi

    log_info "╔═══════════════════════════════════════════════════════════╗"
    log_info "║  CUT RELEASE: ${FORMATTED_TITLE}$(printf '%*s' $((38 - ${#FORMATTED_TITLE})) '' 2>/dev/null || echo '')║"
    log_info "╚═══════════════════════════════════════════════════════════╝"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "DRY RUN MODE - no changes will be made"
    fi
    if [[ "$NO_PUSH" == "true" ]]; then
        log_warn "NO-PUSH MODE - will stop after local commit"
    fi
    if [[ "$NO_WAIT" == "true" ]]; then
        log_warn "NO-WAIT MODE - will create PR but not wait for CI or merge"
    fi

    echo ""

    # Step 1: Check prerequisites (on main, clean, up-to-date)
    check_prerequisites

    # Step 2: Create release branch
    create_release_branch

    # Step 3: Update version files
    update_pyproject_version
    update_init_version

    # Step 4: Update changelog
    update_changelog

    # Step 5: Commit on release branch
    commit_version_changes

    # Step 6: Push release branch and create PR
    create_pr

    # Step 7: Wait for CI
    wait_for_ci

    # Step 8: Merge PR
    merge_pr

    # Step 9: Tag the merge commit on main
    create_tag

    # Step 10: Create GitHub release
    create_github_release

    # Step 11: Update webpage
    update_webpage

    # Step 12: Clean up
    cleanup

    echo ""
    if [[ "$NO_PUSH" == "true" ]]; then
        log_success "═══════════════════════════════════════════════════════════"
        log_success "  VERSION BUMP COMMITTED ON $RELEASE_BRANCH"
        log_success "  Next: push and create PR manually"
        log_success "═══════════════════════════════════════════════════════════"
    elif [[ "$NO_WAIT" == "true" ]]; then
        log_success "═══════════════════════════════════════════════════════════"
        log_success "  PR CREATED FOR $TAG"
        log_success "  To finish: $0 $VERSION --title \"$RELEASE_TITLE\" --finish <PR#>"
        log_success "═══════════════════════════════════════════════════════════"
    else
        log_success "═══════════════════════════════════════════════════════════"
        log_success "  RELEASE ${FORMATTED_TITLE} COMPLETE!"
        log_success "═══════════════════════════════════════════════════════════"
    fi
}

main
