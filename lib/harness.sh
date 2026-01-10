#!/usr/bin/env bash
#
# harness.sh - AI Coding Harness Abstraction Layer
#
# Provides a unified interface for different AI coding harnesses (Claude Code, Codex).
# Follows the same pattern as tasks.sh for backend abstraction.
#

# Cache for detected harness
_HARNESS=""

# ============================================================================
# Harness Detection
# ============================================================================

# Detect available harness
# Priority: explicit HARNESS setting > claude > codex
harness_detect() {
    # If explicitly set, use that
    if [[ -n "${HARNESS:-}" && "$HARNESS" != "auto" ]]; then
        _HARNESS="$HARNESS"
        echo "$_HARNESS"
        return 0
    fi

    # Auto-detect: prefer claude, fallback to codex
    if command -v claude >/dev/null 2>&1; then
        _HARNESS="claude"
    elif command -v codex >/dev/null 2>&1; then
        _HARNESS="codex"
    else
        _HARNESS=""
    fi

    echo "$_HARNESS"
}

# Get current harness (cached)
harness_get() {
    if [[ -z "$_HARNESS" ]]; then
        harness_detect >/dev/null
    fi
    echo "$_HARNESS"
}

# Check if any harness is available
# Optional: pass harness name to check specific one
harness_available() {
    local harness="${1:-}"

    if [[ -n "$harness" ]]; then
        command -v "$harness" >/dev/null 2>&1
        return $?
    fi

    # Check if any harness is available
    command -v claude >/dev/null 2>&1 || command -v codex >/dev/null 2>&1
}

# Get version of current harness
harness_version() {
    local harness=$(harness_get)

    case "$harness" in
        claude)
            claude --version 2>&1 || echo "unknown"
            ;;
        codex)
            codex --version 2>&1 || echo "unknown"
            ;;
        *)
            echo "no harness"
            ;;
    esac
}

# ============================================================================
# Unified Interface
# ============================================================================

# Main invocation - delegates to harness
# Usage: harness_invoke system_prompt task_prompt [debug]
harness_invoke() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    local harness=$(harness_get)

    case "$harness" in
        claude)
            claude_invoke "$system_prompt" "$task_prompt" "$debug"
            ;;
        codex)
            codex_invoke "$system_prompt" "$task_prompt" "$debug"
            ;;
        *)
            echo "Error: No harness available" >&2
            return 1
            ;;
    esac
}

# Streaming invocation with output parsing
# Usage: harness_invoke_streaming system_prompt task_prompt [debug]
harness_invoke_streaming() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    local harness=$(harness_get)

    case "$harness" in
        claude)
            claude_invoke_streaming "$system_prompt" "$task_prompt" "$debug"
            ;;
        codex)
            codex_invoke_streaming "$system_prompt" "$task_prompt" "$debug"
            ;;
        *)
            echo "Error: No harness available" >&2
            return 1
            ;;
    esac
}

# ============================================================================
# Claude Backend
# ============================================================================

claude_invoke() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    local flags="--dangerously-skip-permissions"
    [[ "$debug" == "true" ]] && flags="$flags --debug"

    # Add model flag if specified
    [[ -n "${CURB_MODEL:-}" ]] && flags="$flags --model $CURB_MODEL"

    # Add any extra flags from environment
    [[ -n "${CLAUDE_FLAGS:-}" ]] && flags="$flags $CLAUDE_FLAGS"

    echo "$task_prompt" | claude -p --append-system-prompt "$system_prompt" $flags
}

claude_invoke_streaming() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    local flags="--dangerously-skip-permissions --verbose --output-format stream-json"
    [[ "$debug" == "true" ]] && flags="$flags --debug"

    # Add model flag if specified
    [[ -n "${CURB_MODEL:-}" ]] && flags="$flags --model $CURB_MODEL"

    # Add any extra flags from environment
    [[ -n "${CLAUDE_FLAGS:-}" ]] && flags="$flags $CLAUDE_FLAGS"

    echo "$task_prompt" | claude -p --append-system-prompt "$system_prompt" $flags | claude_parse_stream
    # Return claude's exit code from PIPESTATUS
    return ${PIPESTATUS[1]}
}

# Parse Claude Code's stream-json output
claude_parse_stream() {
    while IFS= read -r line; do
        # Skip empty lines
        [[ -z "$line" ]] && continue

        # Parse JSON and extract relevant info
        local msg_type=$(echo "$line" | jq -r '.type // empty' 2>/dev/null)

        case "$msg_type" in
            "assistant")
                # Assistant text response
                local content=$(echo "$line" | jq -r '.message.content[]? | select(.type=="text") | .text // empty' 2>/dev/null)
                [[ -n "$content" ]] && echo -e "${content}"
                ;;
            "content_block_start")
                local block_type=$(echo "$line" | jq -r '.content_block.type // empty' 2>/dev/null)
                if [[ "$block_type" == "tool_use" ]]; then
                    local tool_name=$(echo "$line" | jq -r '.content_block.name // empty' 2>/dev/null)
                    echo -e "${YELLOW}▶ Tool: ${tool_name}${NC}"
                fi
                ;;
            "content_block_delta")
                local delta_type=$(echo "$line" | jq -r '.delta.type // empty' 2>/dev/null)
                if [[ "$delta_type" == "text_delta" ]]; then
                    local text=$(echo "$line" | jq -r '.delta.text // empty' 2>/dev/null)
                    printf "%s" "$text"
                elif [[ "$delta_type" == "input_json_delta" ]]; then
                    : # Skip JSON input deltas (tool arguments building up)
                fi
                ;;
            "result")
                local result=$(echo "$line" | jq -r '.result // empty' 2>/dev/null)
                [[ -n "$result" ]] && echo -e "\n${GREEN}✓ Result: ${result:0:200}${NC}"
                local cost=$(echo "$line" | jq -r '.cost_usd // empty' 2>/dev/null)
                [[ -n "$cost" && "$cost" != "null" ]] && echo -e "${DIM}  Cost: \$${cost}${NC}"
                ;;
            "system")
                local sys_msg=$(echo "$line" | jq -r '.message // empty' 2>/dev/null)
                [[ -n "$sys_msg" ]] && echo -e "${DIM}[system] ${sys_msg}${NC}"
                ;;
        esac
    done
}

# ============================================================================
# Codex Backend
# ============================================================================

codex_invoke() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    # Codex doesn't have --append-system-prompt, so we combine prompts
    # The system prompt goes first, then a separator, then the task
    local combined_prompt="${system_prompt}

---

${task_prompt}"

    local flags="--full-auto"

    # Add any extra flags from environment
    [[ -n "${CODEX_FLAGS:-}" ]] && flags="$flags $CODEX_FLAGS"

    echo "$combined_prompt" | codex exec $flags -
}

codex_invoke_streaming() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    # Codex exec doesn't have a JSON streaming mode like Claude Code's --output-format stream-json
    # For now, streaming mode just runs the same as non-streaming and passes through output
    # TODO: Investigate codex proto command for structured streaming
    codex_invoke "$system_prompt" "$task_prompt" "$debug"
}
