#!/usr/bin/env bash
#
# llm.sh - LLM Backend Abstraction Layer
#
# Provides a unified interface for different LLM CLI tools (Claude Code, Codex).
# Follows the same pattern as tasks.sh for backend abstraction.
#

# Cache for detected backend
_LLM_BACKEND=""

# ============================================================================
# Backend Detection
# ============================================================================

# Detect available LLM backend
# Priority: explicit LLM_BACKEND setting > claude > codex
llm_detect() {
    # If explicitly set, use that
    if [[ -n "${LLM_BACKEND:-}" && "$LLM_BACKEND" != "auto" ]]; then
        _LLM_BACKEND="$LLM_BACKEND"
        echo "$_LLM_BACKEND"
        return 0
    fi

    # Auto-detect: prefer claude, fallback to codex
    if command -v claude >/dev/null 2>&1; then
        _LLM_BACKEND="claude"
    elif command -v codex >/dev/null 2>&1; then
        _LLM_BACKEND="codex"
    else
        _LLM_BACKEND=""
    fi

    echo "$_LLM_BACKEND"
}

# Get current backend (cached)
llm_get_backend() {
    if [[ -z "$_LLM_BACKEND" ]]; then
        llm_detect >/dev/null
    fi
    echo "$_LLM_BACKEND"
}

# Check if any LLM CLI is available
# Optional: pass backend name to check specific one
llm_available() {
    local backend="${1:-}"

    if [[ -n "$backend" ]]; then
        command -v "$backend" >/dev/null 2>&1
        return $?
    fi

    # Check if any backend is available
    command -v claude >/dev/null 2>&1 || command -v codex >/dev/null 2>&1
}

# Get version of current backend
llm_version() {
    local backend=$(llm_get_backend)

    case "$backend" in
        claude)
            claude --version 2>&1 || echo "unknown"
            ;;
        codex)
            codex --version 2>&1 || echo "unknown"
            ;;
        *)
            echo "no backend"
            ;;
    esac
}

# ============================================================================
# Unified Interface
# ============================================================================

# Main invocation - delegates to backend
# Usage: llm_invoke system_prompt task_prompt [debug]
llm_invoke() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    local backend=$(llm_get_backend)

    case "$backend" in
        claude)
            claude_invoke "$system_prompt" "$task_prompt" "$debug"
            ;;
        codex)
            codex_invoke "$system_prompt" "$task_prompt" "$debug"
            ;;
        *)
            echo "Error: No LLM backend available" >&2
            return 1
            ;;
    esac
}

# Streaming invocation with output parsing
# Usage: llm_invoke_streaming system_prompt task_prompt [debug]
llm_invoke_streaming() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    local backend=$(llm_get_backend)

    case "$backend" in
        claude)
            claude_invoke_streaming "$system_prompt" "$task_prompt" "$debug"
            ;;
        codex)
            codex_invoke_streaming "$system_prompt" "$task_prompt" "$debug"
            ;;
        *)
            echo "Error: No LLM backend available" >&2
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

    local combined_prompt="${system_prompt}

---

${task_prompt}"

    local flags="--full-auto --json"

    # Add any extra flags from environment
    [[ -n "${CODEX_FLAGS:-}" ]] && flags="$flags $CODEX_FLAGS"

    echo "$combined_prompt" | codex exec $flags - | codex_parse_stream
    return ${PIPESTATUS[1]}
}

# Parse Codex's JSONL output
# Note: Exact schema may need adjustment based on actual codex output
codex_parse_stream() {
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue

        local event_type=$(echo "$line" | jq -r '.type // empty' 2>/dev/null)

        case "$event_type" in
            "message"|"text")
                local content=$(echo "$line" | jq -r '.content // .text // empty' 2>/dev/null)
                [[ -n "$content" ]] && echo -e "${content}"
                ;;
            "function_call"|"tool_call")
                local tool_name=$(echo "$line" | jq -r '.name // .function.name // empty' 2>/dev/null)
                [[ -n "$tool_name" ]] && echo -e "${YELLOW}▶ Tool: ${tool_name}${NC}"
                ;;
            "function_result"|"tool_result")
                local result=$(echo "$line" | jq -r '.result // .output // empty' 2>/dev/null)
                [[ -n "$result" ]] && echo -e "${GREEN}✓ Result: ${result:0:200}${NC}"
                ;;
            "error")
                local error=$(echo "$line" | jq -r '.message // .error // empty' 2>/dev/null)
                [[ -n "$error" ]] && echo -e "${RED}Error: ${error}${NC}" >&2
                ;;
            "done"|"complete"|"end")
                local cost=$(echo "$line" | jq -r '.usage.cost // .cost // empty' 2>/dev/null)
                [[ -n "$cost" && "$cost" != "null" ]] && echo -e "${DIM}  Cost: \$${cost}${NC}"
                ;;
            *)
                # For unknown types, try to extract any content
                local content=$(echo "$line" | jq -r '.content // .text // .message // empty' 2>/dev/null)
                [[ -n "$content" ]] && printf "%s" "$content"
                ;;
        esac
    done
}
