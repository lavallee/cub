#!/usr/bin/env bash
#
# spec-to-issues.sh - Convert a feature spec to beads issues
#
# Usage:
#   ./scripts/spec-to-issues.sh specs/researching/capture.md --feature cap
#
# This script:
#   1. Runs `cub plan run` to generate the plan (orient → architect → itemize)
#   2. Runs `cub stage` to import tasks into beads
#
# The planning is handled by the native cub pipeline, which generates
# structured artifacts in plans/<slug>/ before importing to beads.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}INFO:${NC} $*"; }
log_success() { echo -e "${GREEN}SUCCESS:${NC} $*"; }
log_warn() { echo -e "${YELLOW}WARN:${NC} $*"; }
log_error() { echo -e "${RED}ERROR:${NC} $*" >&2; }

usage() {
    cat <<EOF
Usage: $(basename "$0") <spec-file> [OPTIONS]

Convert a feature spec to beads issues using the cub plan + stage pipeline.

Arguments:
  spec-file              Path to the feature spec markdown file

Options:
  --feature, -f SLUG     Feature slug for labels (stored in plan metadata)
  --slug SLUG            Explicit plan slug (default: derived from spec name)
  --depth DEPTH          Orient depth: light, standard, or deep (default: standard)
  --mindset MINDSET      Technical mindset: prototype, mvp, production, enterprise (default: mvp)
  --scale SCALE          Expected scale: personal, team, product, internet-scale (default: team)
  --dry-run              Run planning but don't import to beads
  --verbose, -v          Show detailed output
  --help, -h             Show this help message

Examples:
  $(basename "$0") specs/researching/capture.md --feature cap
  $(basename "$0") specs/researching/capture.md -f cap --dry-run
  $(basename "$0") specs/researching/capture.md -f cap --depth deep --mindset production
EOF
}

main() {
    local spec_file=""
    local feature_slug=""
    local plan_slug=""
    local depth="standard"
    local mindset="mvp"
    local scale="team"
    local dry_run=false
    local verbose=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --feature|-f)
                feature_slug="$2"
                shift 2
                ;;
            --slug)
                plan_slug="$2"
                shift 2
                ;;
            --depth)
                depth="$2"
                shift 2
                ;;
            --mindset)
                mindset="$2"
                shift 2
                ;;
            --scale)
                scale="$2"
                shift 2
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --verbose|-v)
                verbose=true
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
            *)
                if [[ -z "$spec_file" ]]; then
                    spec_file="$1"
                else
                    log_error "Unexpected argument: $1"
                    usage
                    exit 1
                fi
                shift
                ;;
        esac
    done

    # Validate arguments
    if [[ -z "$spec_file" ]]; then
        log_error "Spec file required"
        usage
        exit 1
    fi

    if [[ ! -f "$spec_file" ]]; then
        log_error "Spec file not found: $spec_file"
        exit 1
    fi

    # Check for required tools
    if ! command -v cub &>/dev/null; then
        log_error "cub CLI not found"
        exit 1
    fi

    if ! command -v bd &>/dev/null; then
        log_error "beads CLI (bd) not found"
        exit 1
    fi

    # Build cub plan run command
    local plan_cmd="cub plan run \"$spec_file\""
    plan_cmd+=" --depth $depth"
    plan_cmd+=" --mindset $mindset"
    plan_cmd+=" --scale $scale"
    plan_cmd+=" --non-interactive"

    if [[ -n "$plan_slug" ]]; then
        plan_cmd+=" --slug $plan_slug"
    fi

    if [[ "$verbose" == "true" ]]; then
        plan_cmd+=" --verbose"
    fi

    # Step 1: Run planning pipeline
    log_info "Running planning pipeline..."
    log_info "  Spec: $spec_file"
    log_info "  Depth: $depth"
    log_info "  Mindset: $mindset"
    log_info "  Scale: $scale"

    if [[ "$verbose" == "true" ]]; then
        log_info "  Command: $plan_cmd"
    fi

    if ! eval "$plan_cmd"; then
        log_error "Planning pipeline failed"
        exit 1
    fi

    log_success "Planning complete!"

    if [[ "$dry_run" == "true" ]]; then
        log_info "Dry run - not importing to beads"
        log_info ""
        log_info "To stage manually:"
        echo "  cub stage"
        exit 0
    fi

    # Step 2: Stage (import to beads)
    log_info "Staging tasks to beads..."

    local stage_cmd="cub stage"
    if [[ "$verbose" == "true" ]]; then
        stage_cmd+=" --verbose"
    fi

    if ! eval "$stage_cmd"; then
        log_error "Staging failed"
        exit 1
    fi

    # Step 3: Sync beads
    log_info "Syncing beads..."
    bd sync

    # Summary
    echo ""
    log_success "Import complete!"
    echo ""
    if [[ -n "$feature_slug" ]]; then
        log_info "View with: bd list --label feature:${feature_slug}"
    else
        log_info "View with: bd list"
    fi
}

main "$@"
