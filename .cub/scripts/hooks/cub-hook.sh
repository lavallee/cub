#!/usr/bin/env bash
#
# cub-hook.sh - Fast-path filter for Claude Code hook events
#
# This script acts as the entry point for Claude Code hooks. It performs
# quick relevance checks to filter out 90%+ of events without invoking
# Python, keeping latency under 50ms. Only relevant events are forwarded
# to the Python handler at cub.core.harness.hooks.
#
# Usage:
#   cub-hook.sh <hook_event_name>
#
# Input:
#   - Hook event name as $1 (PostToolUse, SessionStart, Stop, etc.)
#   - JSON payload from stdin (Claude Code hook event data)
#
# Output:
#   - JSON response to stdout (for Claude Code)
#   - Exit 0 for success (allow execution to continue)
#
# Environment:
#   CUB_RUN_ACTIVE - If set, exits immediately (double-tracking prevention)
#
# Fast-path filters:
#   - If CUB_RUN_ACTIVE is set, exit 0 (no processing)
#   - PostToolUse with irrelevant tools (Read, Glob, etc.) -> exit 0
#   - PostToolUse Write/Edit to irrelevant paths -> exit 0
#   - PostToolUse Bash without task/git commands -> exit 0
#   - SessionStart/Stop/PreCompact/UserPromptSubmit -> always pass through
#

set -euo pipefail

# Exit immediately if we're in a cub run session (double-tracking prevention)
if [[ -n "${CUB_RUN_ACTIVE:-}" ]]; then
    # Return minimal success response
    echo '{"continue": true}'
    exit 0
fi

# Get hook event name from first argument
HOOK_EVENT="${1:-}"

# Read stdin into variable for potential passthrough
STDIN_DATA=$(cat)

# Check if jq is available for JSON parsing
if command -v jq >/dev/null 2>&1; then
    HAS_JQ=1
else
    HAS_JQ=0
fi

# Extract tool_name from JSON (if PostToolUse event)
extract_tool_name() {
    if [[ $HAS_JQ -eq 1 ]]; then
        echo "$STDIN_DATA" | jq -r '.tool_name // empty' 2>/dev/null || true
    else
        # Fallback: grep for "tool_name": "value"
        echo "$STDIN_DATA" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"tool_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || true
    fi
}

# Extract file_path from tool_input (for Write/Edit tools)
extract_file_path() {
    if [[ $HAS_JQ -eq 1 ]]; then
        echo "$STDIN_DATA" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' 2>/dev/null || true
    else
        # Fallback: grep for file_path or notebook_path
        echo "$STDIN_DATA" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || true
        if [[ -z "${file_path:-}" ]]; then
            echo "$STDIN_DATA" | grep -o '"notebook_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"notebook_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || true
        fi
    fi
}

# Extract command from tool_input (for Bash tool)
extract_command() {
    if [[ $HAS_JQ -eq 1 ]]; then
        echo "$STDIN_DATA" | jq -r '.tool_input.command // empty' 2>/dev/null || true
    else
        # Fallback: grep for command field (be careful with multiline)
        echo "$STDIN_DATA" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || true
    fi
}

# Check if path is in a tracked directory
is_tracked_path() {
    local path="$1"
    if [[ "$path" == *"/plans/"* ]] || \
       [[ "$path" == *"/specs/"* ]] || \
       [[ "$path" == *"/captures/"* ]] || \
       [[ "$path" == *"/src/"* ]] || \
       [[ "$path" == *"/.cub/"* ]]; then
        return 0
    fi
    return 1
}

# Check if command contains tracked patterns
is_tracked_command() {
    local cmd="$1"
    if [[ "$cmd" == *"cub "* ]] || \
       [[ "$cmd" == *"git commit"* ]] || \
       [[ "$cmd" == *"git add"* ]]; then
        return 0
    fi
    return 1
}

# Detect dev_mode from config or environment
detect_dev_mode() {
    # Check env var first (highest priority)
    if [[ -n "${CUB_DEV_MODE:-}" ]]; then
        echo "$CUB_DEV_MODE"
        return
    fi

    # Check .cub/config.json (if jq available)
    if [[ $HAS_JQ -eq 1 ]] && [[ -f ".cub/config.json" ]]; then
        local dev_mode=$(jq -r '.dev_mode // "false"' .cub/config.json 2>/dev/null || echo "false")
        echo "$dev_mode"
        return
    fi

    # Default: not in dev mode
    echo "false"
}

# Invoke Python handler with stdin passthrough
invoke_python_handler() {
    local dev_mode=$(detect_dev_mode)

    if [[ "$dev_mode" == "true" ]]; then
        # Dev mode: use uv run to execute in local venv
        echo "$STDIN_DATA" | uv run cub-hooks "$HOOK_EVENT"
    else
        # Production mode: use installed cub-hooks command
        echo "$STDIN_DATA" | cub-hooks "$HOOK_EVENT"
    fi
}

# Main logic: fast-path filtering
case "$HOOK_EVENT" in
    PostToolUse)
        # Extract tool name to determine relevance
        TOOL_NAME=$(extract_tool_name)

        case "$TOOL_NAME" in
            Write|Edit|NotebookEdit)
                # Check if file path is in tracked directory
                FILE_PATH=$(extract_file_path)
                if [[ -n "$FILE_PATH" ]] && is_tracked_path "$FILE_PATH"; then
                    # Relevant: pass to Python handler
                    invoke_python_handler
                else
                    # Irrelevant path: skip
                    echo '{"continue": true}'
                fi
                ;;
            Bash)
                # Check if command contains tracked patterns
                COMMAND=$(extract_command)
                if [[ -n "$COMMAND" ]] && is_tracked_command "$COMMAND"; then
                    # Relevant: pass to Python handler
                    invoke_python_handler
                else
                    # Irrelevant command: skip
                    echo '{"continue": true}'
                fi
                ;;
            *)
                # Other tools (Read, Glob, etc.): skip
                echo '{"continue": true}'
                ;;
        esac
        ;;

    SessionStart|Stop|PreCompact|UserPromptSubmit|SessionEnd)
        # Always pass through session lifecycle events
        invoke_python_handler
        ;;

    *)
        # Unknown event: safe default is to skip
        echo '{"continue": true}'
        ;;
esac

exit 0
