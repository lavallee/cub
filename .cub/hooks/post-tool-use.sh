#!/bin/bash
# PostToolUse hook for capturing file writes and plan updates
#
# This hook is called by Claude Code after each tool execution.
# It receives hook event JSON via stdin and processes it to capture
# artifacts for the ledger system.
#
# Exit codes:
#   0 - Success, allow execution to continue
#   2 - Blocking error (won't happen in this hook)
#   Other - Non-blocking error

set -euo pipefail

# Get project directory (set by Claude Code)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Check if cub is available
if ! command -v cub &> /dev/null; then
    # Cub not installed, skip hook silently
    exit 0
fi

# Check if we're in a cub project (check for either config.json or config.yml)
if [ ! -f "$PROJECT_DIR/.cub/config.json" ] && [ ! -f "$PROJECT_DIR/.cub/config.yml" ]; then
    # Not a cub project, skip hook
    exit 0
fi

# Run the Python hook handler
cd "$PROJECT_DIR"
python3 -m cub.core.harness.hooks PostToolUse

# Exit with the handler's exit code
exit $?
