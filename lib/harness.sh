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
# Token Usage Tracking (file-based to survive command substitution)
# ============================================================================

# File paths for usage tracking (process-specific)
_USAGE_INPUT_FILE="${TMPDIR:-/tmp}/curb_usage_input_$$"
_USAGE_OUTPUT_FILE="${TMPDIR:-/tmp}/curb_usage_output_$$"
_USAGE_CACHE_INPUT_FILE="${TMPDIR:-/tmp}/curb_usage_cache_input_$$"
_USAGE_CACHE_CREATION_FILE="${TMPDIR:-/tmp}/curb_usage_cache_creation_$$"
_USAGE_COST_FILE="${TMPDIR:-/tmp}/curb_usage_cost_$$"

# Cleanup trap for usage files
trap 'rm -f "$_USAGE_INPUT_FILE" "$_USAGE_OUTPUT_FILE" "$_USAGE_CACHE_INPUT_FILE" "$_USAGE_CACHE_CREATION_FILE" "$_USAGE_COST_FILE" 2>/dev/null' EXIT

# Clear all usage tracking state
# Usage: harness_clear_usage
harness_clear_usage() {
    rm -f "$_USAGE_INPUT_FILE" "$_USAGE_OUTPUT_FILE" "$_USAGE_CACHE_INPUT_FILE" "$_USAGE_CACHE_CREATION_FILE" "$_USAGE_COST_FILE" 2>/dev/null
    return 0
}

# Store usage data (internal function)
# Usage: _harness_store_usage input_tokens output_tokens [cache_read_tokens] [cache_creation_tokens] [cost_usd]
_harness_store_usage() {
    local input_tokens="${1:-0}"
    local output_tokens="${2:-0}"
    local cache_read_tokens="${3:-0}"
    local cache_creation_tokens="${4:-0}"
    local cost_usd="${5:-}"

    echo "$input_tokens" > "$_USAGE_INPUT_FILE"
    echo "$output_tokens" > "$_USAGE_OUTPUT_FILE"
    echo "$cache_read_tokens" > "$_USAGE_CACHE_INPUT_FILE"
    echo "$cache_creation_tokens" > "$_USAGE_CACHE_CREATION_FILE"
    if [[ -n "$cost_usd" && "$cost_usd" != "null" ]]; then
        echo "$cost_usd" > "$_USAGE_COST_FILE"
    fi
}

# Get usage from last harness invocation
# Returns JSON object: {"input_tokens": N, "output_tokens": N, "cache_read_tokens": N, "cache_creation_tokens": N, "cost_usd": N, "estimated": bool}
# Usage: harness_get_usage
harness_get_usage() {
    local input_tokens=$(cat "$_USAGE_INPUT_FILE" 2>/dev/null || echo "0")
    local output_tokens=$(cat "$_USAGE_OUTPUT_FILE" 2>/dev/null || echo "0")
    local cache_read_tokens=$(cat "$_USAGE_CACHE_INPUT_FILE" 2>/dev/null || echo "0")
    local cache_creation_tokens=$(cat "$_USAGE_CACHE_CREATION_FILE" 2>/dev/null || echo "0")
    local cost_usd=$(cat "$_USAGE_COST_FILE" 2>/dev/null || echo "")
    local estimated="false"

    # If we have no usage data but have cost, estimate tokens from cost
    # Claude pricing: ~$3 per million input tokens, ~$15 per million output tokens (rough average)
    # For simplicity, use total tokens estimate: cost * 150000 (average ~$6.5 per million)
    if [[ "$input_tokens" == "0" && "$output_tokens" == "0" && -n "$cost_usd" && "$cost_usd" != "0" ]]; then
        # Estimate: assume 2/3 output, 1/3 input based on typical usage
        # Total tokens = cost * 150000 (rough estimate)
        local total_estimate=$(echo "$cost_usd * 150000" | bc 2>/dev/null | cut -d. -f1)
        if [[ -n "$total_estimate" && "$total_estimate" != "0" ]]; then
            output_tokens=$((total_estimate * 2 / 3))
            input_tokens=$((total_estimate / 3))
            estimated="true"
        fi
    fi

    # Build JSON response
    local json
    if [[ -n "$cost_usd" && "$cost_usd" != "" ]]; then
        json=$(jq -n \
            --argjson input "$input_tokens" \
            --argjson output "$output_tokens" \
            --argjson cache_read "$cache_read_tokens" \
            --argjson cache_creation "$cache_creation_tokens" \
            --argjson cost "$cost_usd" \
            --argjson estimated "$estimated" \
            '{input_tokens: $input, output_tokens: $output, cache_read_tokens: $cache_read, cache_creation_tokens: $cache_creation, cost_usd: $cost, estimated: $estimated}')
    else
        json=$(jq -n \
            --argjson input "$input_tokens" \
            --argjson output "$output_tokens" \
            --argjson cache_read "$cache_read_tokens" \
            --argjson cache_creation "$cache_creation_tokens" \
            --argjson estimated "$estimated" \
            '{input_tokens: $input, output_tokens: $output, cache_read_tokens: $cache_read, cache_creation_tokens: $cache_creation, cost_usd: null, estimated: $estimated}')
    fi

    echo "$json"
}

# Get total tokens (input + output) from last invocation
# Usage: harness_get_total_tokens
harness_get_total_tokens() {
    local input_tokens=$(cat "$_USAGE_INPUT_FILE" 2>/dev/null || echo "0")
    local output_tokens=$(cat "$_USAGE_OUTPUT_FILE" 2>/dev/null || echo "0")
    echo $((input_tokens + output_tokens))
}

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

    # Clear previous usage
    harness_clear_usage

    local flags="--dangerously-skip-permissions --output-format json"
    [[ "$debug" == "true" ]] && flags="$flags --debug"

    # Add model flag if specified
    [[ -n "${CURB_MODEL:-}" ]] && flags="$flags --model $CURB_MODEL"

    # Add any extra flags from environment
    [[ -n "${CLAUDE_FLAGS:-}" ]] && flags="$flags $CLAUDE_FLAGS"

    # Capture JSON output to extract usage, then display result
    local output
    output=$(echo "$task_prompt" | claude -p --append-system-prompt "$system_prompt" $flags 2>&1)
    local exit_code=$?

    # Try to extract usage from JSON output
    # Claude --output-format json returns a JSON object with usage field
    if echo "$output" | jq -e '.usage' >/dev/null 2>&1; then
        local input=$(echo "$output" | jq -r '.usage.input_tokens // 0' 2>/dev/null)
        local out=$(echo "$output" | jq -r '.usage.output_tokens // 0' 2>/dev/null)
        local cache_read=$(echo "$output" | jq -r '.usage.cache_read_input_tokens // 0' 2>/dev/null)
        local cache_creation=$(echo "$output" | jq -r '.usage.cache_creation_input_tokens // 0' 2>/dev/null)
        local cost=$(echo "$output" | jq -r '.cost_usd // empty' 2>/dev/null)
        _harness_store_usage "$input" "$out" "$cache_read" "$cache_creation" "$cost"

        # Extract and display the result text
        local result_text=$(echo "$output" | jq -r '.result // .content // empty' 2>/dev/null)
        [[ -n "$result_text" ]] && echo "$result_text"
    else
        # If not valid JSON with usage, output as-is (error message or raw text)
        echo "$output"
    fi

    return $exit_code
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
# Extracts text output for display and captures token usage from message events
claude_parse_stream() {
    # Clear previous usage before parsing new stream
    harness_clear_usage

    # Local variables for accumulating usage across multiple messages
    local total_input=0
    local total_output=0
    local total_cache_read=0
    local total_cache_creation=0
    local final_cost=""

    while IFS= read -r line; do
        # Skip empty lines
        [[ -z "$line" ]] && continue

        # Parse JSON and extract relevant info
        local msg_type=$(echo "$line" | jq -r '.type // empty' 2>/dev/null)

        case "$msg_type" in
            "assistant"|"message")
                # Message events contain usage information
                # Check for usage object first
                local has_usage=$(echo "$line" | jq -r 'has("usage") // false' 2>/dev/null)
                if [[ "$has_usage" == "true" ]]; then
                    local input=$(echo "$line" | jq -r '.usage.input_tokens // 0' 2>/dev/null)
                    local output=$(echo "$line" | jq -r '.usage.output_tokens // 0' 2>/dev/null)
                    local cache_read=$(echo "$line" | jq -r '.usage.cache_read_input_tokens // 0' 2>/dev/null)
                    local cache_creation=$(echo "$line" | jq -r '.usage.cache_creation_input_tokens // 0' 2>/dev/null)

                    # Accumulate usage (multiple message events possible)
                    total_input=$((total_input + input))
                    total_output=$((total_output + output))
                    total_cache_read=$((total_cache_read + cache_read))
                    total_cache_creation=$((total_cache_creation + cache_creation))
                fi

                # Also check for text content in assistant messages
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
                if [[ -n "$cost" && "$cost" != "null" ]]; then
                    echo -e "${DIM}  Cost: \$${cost}${NC}"
                    final_cost="$cost"
                fi
                ;;
            "system")
                local sys_msg=$(echo "$line" | jq -r '.message // empty' 2>/dev/null)
                [[ -n "$sys_msg" ]] && echo -e "${DIM}[system] ${sys_msg}${NC}"
                ;;
        esac
    done

    # Store accumulated usage after processing all events
    _harness_store_usage "$total_input" "$total_output" "$total_cache_read" "$total_cache_creation" "$final_cost"
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
