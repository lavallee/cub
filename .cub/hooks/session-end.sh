#!/bin/bash
# SessionEnd hook for finalizing session
#
# This hook is called by Claude Code when a session terminates.
# It ensures all artifacts are captured and ledger entries are closed.
#
# Note: SessionEnd is only available in TypeScript SDK, not Python SDK.
# This script is provided for Claude Code CLI compatibility.
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
python3 -m cub.core.harness.hooks SessionEnd

# Exit with the handler's exit code
exit $?
