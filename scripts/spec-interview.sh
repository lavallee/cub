#!/usr/bin/env bash
#
# spec-interview.sh - Create a spec through an interactive interview
#
# Usage:
#   ./scripts/spec-interview.sh                    # Start interview with no topic
#   ./scripts/spec-interview.sh "feature name"    # Start with a topic
#
# This script:
#   1. Invokes Claude Code with the /cub:spec skill
#   2. Guides you through a structured interview
#   3. Creates a spec file in specs/researching/
#
# Alternative: Run /cub:spec directly in Claude Code
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
log_error() { echo -e "${RED}ERROR:${NC} $*" >&2; }

usage() {
    cat <<EOF
Usage: $(basename "$0") [TOPIC]

Create a feature spec through an interactive interview.

Arguments:
  TOPIC                  Optional: Feature name or brief description to start with

Options:
  --help, -h             Show this help message

Examples:
  $(basename "$0")                              # Start interview with no topic
  $(basename "$0") "user authentication"       # Start with a topic
  $(basename "$0") "cub run parallel mode"     # Start with a specific feature

Alternative:
  Run /cub:spec directly in Claude Code for the same experience.
EOF
}

main() {
    local topic=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
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
                if [[ -z "$topic" ]]; then
                    topic="$1"
                else
                    # Append additional words to topic
                    topic="$topic $1"
                fi
                shift
                ;;
        esac
    done

    # Check for required tools
    if ! command -v claude &>/dev/null; then
        log_error "Claude CLI not found"
        log_info "Install from: https://claude.ai/code"
        exit 1
    fi

    # Ensure specs/researching directory exists
    mkdir -p "${PROJECT_DIR}/specs/researching"

    # Build the prompt
    local prompt
    if [[ -n "$topic" ]]; then
        prompt="Run /cub:spec with topic: $topic"
        log_info "Starting spec interview for: $topic"
    else
        prompt="Run /cub:spec"
        log_info "Starting spec interview..."
    fi

    log_info "This will guide you through creating a feature spec."
    log_info ""

    # Invoke Claude interactively
    cd "$PROJECT_DIR"
    claude "$prompt"
}

main "$@"
