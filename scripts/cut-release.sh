#!/usr/bin/env bash
#
# cut-release.sh - Cut a release from main branch
#
# Takes a snapshot of main, updates version numbers, auto-generates changelog,
# and creates a GitHub release. This is the release-specific subset of
# release-pipeline.sh.
#
# Usage:
#   ./scripts/cut-release.sh 0.25.2              # Cut release v0.25.2
#   ./scripts/cut-release.sh 0.26.0 --dry-run    # Show what would be done
#   ./scripts/cut-release.sh 0.25.2 --no-push    # Don't push or create GitHub release
#   ./scripts/cut-release.sh 0.25.2 --skip-changelog  # Skip changelog generation
#   ./scripts/cut-release.sh 0.25.2 --title "Release Title"  # Custom release title
#
# The script will:
#   1. Verify we're on main with clean working directory
#   2. Update version in pyproject.toml and src/cub/__init__.py
#   3. Auto-generate CHANGELOG.md entry from git commits
#   4. Commit version and changelog changes
#   5. Create and push git tag
#   6. Create GitHub release with notes from changelog
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
SKIP_CHANGELOG=false
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
        --help|-h)
            head -20 "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
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
    echo "Usage: $0 <version> [--dry-run] [--no-push] [--skip-changelog] [--title \"Title\"]"
    echo "Example: $0 0.25.2"
    echo "Example: $0 0.25.2 --title \"Feature Release: New Dashboard\""
    exit 1
fi

# Validate version format (X.Y.Z)
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    log_error "Invalid version format: $VERSION"
    echo "Version must be in format X.Y.Z (e.g., 0.25.2)"
    exit 1
fi

TAG="v${VERSION}"

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

# Commit version changes
commit_version_changes() {
    log_info "Committing version changes..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would commit: chore: bump version to $VERSION"
        return 0
    fi

    git add pyproject.toml src/cub/__init__.py CHANGELOG.md
    # Also add specs/ if any were moved
    if [[ -d "$PROJECT_DIR/specs" ]]; then
        git add "$PROJECT_DIR/specs/" 2>/dev/null || true
    fi

    # Check if there are changes to commit
    if git diff --cached --quiet; then
        log_warn "No changes to commit"
        return 0
    fi

    git commit -m "chore: bump version to $VERSION"
    log_success "Committed version changes"
}

# Move specs from implementing/ to released/
move_specs_to_released() {
    log_info "Moving specs from implementing/ to released/..."

    # Check if move_specs_released.py exists
    if [[ ! -f "${SCRIPT_DIR}/move_specs_released.py" ]]; then
        log_warn "move_specs_released.py not found, skipping spec transition"
        return 0
    fi

    local dry_run_flag=""
    if [[ "$DRY_RUN" == "true" ]]; then
        dry_run_flag="--dry-run"
    fi

    if python3 "${SCRIPT_DIR}/move_specs_released.py" $dry_run_flag --verbose --project-root "$PROJECT_DIR"; then
        if [[ "$DRY_RUN" != "true" ]]; then
            # Stage any spec moves for the release commit
            if [[ -d "$PROJECT_DIR/specs" ]]; then
                git add "$PROJECT_DIR/specs/"
            fi
        fi
        log_success "Specs transitioned"
    else
        log_warn "Failed to move specs (non-fatal)"
    fi
}

# Create and push tag
create_tag() {
    log_info "Creating tag $TAG..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create tag: $TAG"
        return 0
    fi

    git tag -a "$TAG" -m "Release $TAG"
    log_success "Created tag $TAG"
}

# Push changes and tag
push_changes() {
    if [[ "$NO_PUSH" == "true" ]]; then
        log_warn "Skipping push (--no-push)"
        return 0
    fi

    log_info "Pushing changes and tag to origin..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would push to origin"
        return 0
    fi

    git push origin main
    git push origin "$TAG"
    log_success "Pushed changes and tag"
}

# Create GitHub release
create_github_release() {
    if [[ "$NO_PUSH" == "true" ]]; then
        log_warn "Skipping GitHub release (--no-push)"
        return 0
    fi

    log_info "Creating GitHub release for $TAG..."

    if [[ "$DRY_RUN" == "true" ]]; then
        local title="${RELEASE_TITLE:-$TAG}"
        log_info "[DRY-RUN] Would create GitHub release: $TAG (title: $title)"
        return 0
    fi

    # Extract release notes
    local notes
    notes=$(extract_release_notes)

    if [[ -z "$notes" ]]; then
        log_warn "No release notes found in CHANGELOG.md"
        notes="Release $TAG"
    fi

    # Create release (use custom title if provided, otherwise use tag)
    local title="${RELEASE_TITLE:-$TAG}"
    gh release create "$TAG" \
        --title "$title" \
        --notes "$notes"

    log_success "Created GitHub release: $TAG"

    # Show release URL
    local release_url
    release_url=$(gh release view "$TAG" --json url --jq '.url')
    log_info "Release URL: $release_url"
}

# Update webpage changelog
update_webpage() {
    if [[ "$NO_PUSH" == "true" ]]; then
        log_warn "Skipping webpage update (--no-push)"
        return 0
    fi

    log_info "Updating webpage changelog..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would run update_webpage_changelog.py"
        return 0
    fi

    if [[ -f "${SCRIPT_DIR}/update_webpage_changelog.py" ]]; then
        # Build command with optional title
        local cmd=(python3 "${SCRIPT_DIR}/update_webpage_changelog.py")
        if [[ -n "$RELEASE_TITLE" ]]; then
            cmd+=(--version "$VERSION" --title "$RELEASE_TITLE")
        fi

        "${cmd[@]}" || {
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

# Main execution
main() {
    log_info "╔═══════════════════════════════════════════════════════════╗"
    log_info "║  CUT RELEASE: $TAG$(printf '%*s' $((38 - ${#TAG})) '')║"
    log_info "╚═══════════════════════════════════════════════════════════╝"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "DRY RUN MODE - no changes will be made"
    fi

    echo ""

    # Step 1: Check prerequisites
    check_prerequisites

    # Step 2: Update version files
    update_pyproject_version
    update_init_version

    # Step 3: Update changelog
    update_changelog

    # Step 4: Move specs from implementing/ to released/
    move_specs_to_released

    # Step 5: Commit changes (includes version, changelog, and spec moves)
    commit_version_changes

    # Step 6: Create tag
    create_tag

    # Step 7: Push
    push_changes

    # Step 8: Create GitHub release
    create_github_release

    # Step 9: Update webpage
    update_webpage

    echo ""
    log_success "═══════════════════════════════════════════════════════════"
    log_success "  RELEASE $TAG COMPLETE!"
    log_success "═══════════════════════════════════════════════════════════"
}

main
