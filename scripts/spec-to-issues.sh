#!/usr/bin/env bash
#
# spec-to-issues.sh - Convert a feature spec to beads issues
#
# Usage:
#   ./scripts/spec-to-issues.sh specs/features/capture.md --feature cap
#
# This script:
#   1. Reads the spec file
#   2. Determines the next available issue IDs to avoid collisions
#   3. Invokes Claude with the /cub:spec-to-issues skill to generate plan.jsonl
#   4. Imports the plan into beads
#
# The script uses bd commands for import. This should be abstracted into
# a cub command in the future for backend independence.
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

Convert a feature spec to beads issues.

Arguments:
  spec-file              Path to the feature spec markdown file

Options:
  --feature, -f SLUG     Feature slug for labels (e.g., 'cap' for capture)
  --prefix PREFIX        Issue ID prefix (default: cub)
  --dry-run              Generate plan.jsonl but don't import
  --output, -o PATH      Output path for plan.jsonl (default: temp file)
  --help, -h             Show this help message

Examples:
  $(basename "$0") specs/features/capture.md --feature cap
  $(basename "$0") specs/features/capture.md -f cap --dry-run
  $(basename "$0") specs/features/capture.md -f cap -o /tmp/capture-plan.jsonl
EOF
}

# Get the next available issue IDs
get_next_ids() {
    local prefix="${1:-cub}"

    # Get highest task ID (format: prefix-NNN)
    local highest_task
    highest_task=$(bd list --status all --json 2>/dev/null | \
        jq -r '.[].id' | \
        grep -E "^${prefix}-[0-9]+\$" | \
        sed "s/${prefix}-//" | \
        sort -n | \
        tail -1)

    if [[ -z "$highest_task" ]]; then
        highest_task=0
    fi

    # Get highest epic ID (format: prefix-ENN)
    local highest_epic
    highest_epic=$(bd list --status all --json 2>/dev/null | \
        jq -r '.[].id' | \
        grep -E "^${prefix}-E[0-9]+\$" | \
        sed "s/${prefix}-E//" | \
        sort -n | \
        tail -1)

    if [[ -z "$highest_epic" ]]; then
        highest_epic=0
    fi

    # Return next available IDs
    local next_task=$((highest_task + 1))
    local next_epic=$((highest_epic + 1))

    echo "${next_epic}:${next_task}"
}

# Wire dependencies after import (bd import doesn't preserve them)
wire_dependencies() {
    local plan_file="$1"
    local dep_count=0

    if [[ ! -f "$plan_file" ]]; then
        log_warn "Plan file not found: ${plan_file}"
        return 0
    fi

    log_info "Wiring dependencies..."

    while IFS= read -r line; do
        local issue_id
        issue_id=$(echo "$line" | jq -r '.id // empty')

        if [[ -z "$issue_id" ]]; then
            continue
        fi

        # Extract dependencies array
        local deps
        deps=$(echo "$line" | jq -c '.dependencies // []')

        if [[ "$deps" == "[]" || "$deps" == "null" ]]; then
            continue
        fi

        # Process each dependency
        echo "$deps" | jq -c '.[]' | while IFS= read -r dep; do
            local depends_on_id dep_type
            depends_on_id=$(echo "$dep" | jq -r '.depends_on_id // empty')
            dep_type=$(echo "$dep" | jq -r '.type // "blocks"')

            if [[ -n "$depends_on_id" ]]; then
                if bd dep add "$issue_id" "$depends_on_id" --type "$dep_type" 2>/dev/null; then
                    ((dep_count++)) || true
                fi
            fi
        done
    done < "$plan_file"

    log_info "  Added ${dep_count} dependencies"
}

main() {
    local spec_file=""
    local feature_slug=""
    local prefix="cub"
    local dry_run=false
    local output_path=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --feature|-f)
                feature_slug="$2"
                shift 2
                ;;
            --prefix)
                prefix="$2"
                shift 2
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --output|-o)
                output_path="$2"
                shift 2
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

    if [[ -z "$feature_slug" ]]; then
        log_error "Feature slug required (--feature)"
        usage
        exit 1
    fi

    # Check for required tools
    if ! command -v bd &>/dev/null; then
        log_error "beads CLI (bd) not found"
        exit 1
    fi

    if ! command -v claude &>/dev/null; then
        log_error "Claude CLI not found"
        exit 1
    fi

    # Get next available IDs
    log_info "Checking for ID collisions..."
    local next_ids
    next_ids=$(get_next_ids "$prefix")
    local next_epic="${next_ids%%:*}"
    local next_task="${next_ids##*:}"
    log_info "  Next epic ID: ${prefix}-E$(printf '%02d' "$next_epic")"
    log_info "  Next task ID: ${prefix}-$(printf '%03d' "$next_task")"

    # Set output path
    if [[ -z "$output_path" ]]; then
        output_path=$(mktemp -d)/plan.jsonl
    fi
    local output_dir
    output_dir=$(dirname "$output_path")
    mkdir -p "$output_dir"

    # Generate plan using Claude
    log_info "Generating plan from spec..."
    log_info "  Spec: $spec_file"
    log_info "  Feature: $feature_slug"
    log_info "  Output: $output_path"

    # Read spec content
    local spec_content
    spec_content=$(cat "$spec_file")

    # Invoke Claude with the spec-to-issues skill
    # Capture stdout and extract JSONL content
    local claude_output
    local temp_output
    temp_output=$(mktemp)

    log_info "Running Claude (this may take a minute)..."

    if ! claude --print "Run /cub:spec-to-issues with these parameters:

SPEC_FILE: $spec_file
OUTPUT_PATH: $output_path
FEATURE_SLUG: $feature_slug
PREFIX: $prefix
NEXT_EPIC_NUM: $next_epic
NEXT_TASK_NUM: $next_task

Here is the spec content:

$spec_content" > "$temp_output" 2>&1; then
        log_error "Claude invocation failed"
        cat "$temp_output"
        rm -f "$temp_output"
        exit 1
    fi

    # Extract JSONL content (everything before ---END_JSONL--- marker)
    # Filter to only lines that start with { and are valid JSON
    if grep -q "---END_JSONL---" "$temp_output"; then
        sed -n '/^{/,/---END_JSONL---/p' "$temp_output" | grep -v "---END_JSONL---" | while read -r line; do
            if echo "$line" | jq -e . >/dev/null 2>&1; then
                echo "$line"
            fi
        done > "$output_path"
    else
        # Fallback: extract all lines that look like JSON objects
        grep '^{' "$temp_output" | while read -r line; do
            if echo "$line" | jq -e . >/dev/null 2>&1; then
                echo "$line"
            fi
        done > "$output_path"
    fi

    # Show any summary output
    if grep -q "---END_JSONL---" "$temp_output"; then
        sed -n '/---END_JSONL---/,$p' "$temp_output" | tail -n +2
    fi

    rm -f "$temp_output"

    # Verify output was created and has content
    if [[ ! -f "$output_path" ]] || [[ ! -s "$output_path" ]]; then
        log_error "Plan file was not created or is empty: $output_path"
        exit 1
    fi

    # Count generated items
    local epic_count task_count
    epic_count=$(grep -c '"issue_type":"epic"' "$output_path" 2>/dev/null || echo "0")
    task_count=$(grep -c '"issue_type":"task"' "$output_path" 2>/dev/null || echo "0")

    log_success "Plan generated: ${epic_count} epics, ${task_count} tasks"

    if [[ "$dry_run" == "true" ]]; then
        log_info "Dry run - not importing"
        log_info "Plan saved to: $output_path"
        echo ""
        log_info "To import manually:"
        echo "  bd import -i $output_path"
        exit 0
    fi

    # Import into beads
    log_info "Importing into beads..."
    if ! bd import -i "$output_path"; then
        log_error "Import failed"
        exit 1
    fi

    # Wire up dependencies
    wire_dependencies "$output_path"

    # Sync
    log_info "Syncing beads..."
    bd sync

    # Summary
    echo ""
    log_success "Import complete!"
    log_info "  Epics: ${epic_count}"
    log_info "  Tasks: ${task_count}"
    echo ""
    log_info "View with: bd list --label feature:${feature_slug}"
}

main "$@"
