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
# Harness Capability Detection
# ============================================================================
#
# Different harnesses have different capabilities. This section provides
# a unified way to query what features a harness supports so the main loop
# can adapt its behavior accordingly.
#
# Capabilities:
#   streaming        - Supports real-time streaming output with --output-format stream-json
#   token_reporting  - Reports token usage after invocation
#   system_prompt    - Supports separate system prompt (--append-system-prompt)
#   auto_mode        - Has autonomous/auto-approve mode for unattended operation
#
# Usage:
#   if harness_supports "streaming"; then
#       harness_invoke_streaming "$sys" "$task"
#   else
#       harness_invoke "$sys" "$task"
#   fi

# Capability constants (for documentation and consistency)
readonly HARNESS_CAP_STREAMING="streaming"
readonly HARNESS_CAP_TOKEN_REPORTING="token_reporting"
readonly HARNESS_CAP_SYSTEM_PROMPT="system_prompt"
readonly HARNESS_CAP_AUTO_MODE="auto_mode"
readonly HARNESS_CAP_JSON_OUTPUT="json_output"
readonly HARNESS_CAP_MODEL_SELECTION="model_selection"

# Get capabilities for a specific harness
# Returns a space-separated list of supported capabilities
# Usage: _harness_get_capabilities [harness]
_harness_get_capabilities() {
    local harness="${1:-$(harness_get)}"

    case "$harness" in
        claude)
            # Claude Code: Full featured
            # - streaming: --output-format stream-json
            # - token_reporting: .usage in JSON output
            # - system_prompt: --append-system-prompt
            # - auto_mode: --dangerously-skip-permissions
            # - json_output: --output-format json
            # - model_selection: --model flag
            echo "streaming token_reporting system_prompt auto_mode json_output model_selection"
            ;;
        opencode)
            # OpenCode: Streaming with token reporting, no separate system prompt
            # - streaming: --format json (outputs step_finish events with token counts)
            # - token_reporting: .part.tokens in step_finish events
            # - auto_mode: 'run' subcommand (auto-approves all permissions)
            # - json_output: --format json
            # - No system_prompt flag (must combine prompts)
            # - No model_selection (configured via project, not CLI)
            echo "streaming token_reporting auto_mode json_output"
            ;;
        codex)
            # Codex CLI 0.80+: Enhanced capabilities
            # - auto_mode: --full-auto
            # - streaming: --json outputs JSONL events
            # - json_output: --json flag
            # - model_selection: -m flag
            # - No system_prompt flag (must combine prompts)
            # - No token_reporting in CLI output (estimated only)
            echo "auto_mode streaming json_output model_selection"
            ;;
        gemini)
            # Gemini CLI: Basic auto mode with model selection
            # - auto_mode: -y (YOLO mode, auto-accept all actions)
            # - model_selection: -m flag
            # - No streaming (v0.1.9 doesn't support --output-format stream-json)
            # - No token_reporting in CLI output (uses estimation)
            # - No system_prompt flag (must combine prompts)
            # - No json_output format
            echo "auto_mode model_selection"
            ;;
        *)
            # Unknown harness - return empty (no capabilities)
            echo ""
            ;;
    esac
}

# Check if current harness supports a specific capability
# Returns 0 (success) if supported, 1 (failure) if not
# Usage: harness_supports "capability_name"
# Usage: harness_supports "capability_name" "harness_name"
harness_supports() {
    local capability="$1"
    local harness="${2:-$(harness_get)}"

    if [[ -z "$capability" ]]; then
        echo "Error: harness_supports requires a capability name" >&2
        return 1
    fi

    local caps
    caps=$(_harness_get_capabilities "$harness")

    # Check if capability is in the space-separated list
    case " $caps " in
        *" $capability "*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Get all capabilities for the current harness as JSON
# Useful for logging and debugging
# Usage: harness_get_capabilities_json [harness]
harness_get_capabilities_json() {
    local harness="${1:-$(harness_get)}"
    local caps
    caps=$(_harness_get_capabilities "$harness")

    # Build JSON object with all capability flags
    local streaming="false"
    local token_reporting="false"
    local system_prompt="false"
    local auto_mode="false"
    local json_output="false"
    local model_selection="false"

    case " $caps " in
        *" streaming "*) streaming="true" ;;
    esac
    case " $caps " in
        *" token_reporting "*) token_reporting="true" ;;
    esac
    case " $caps " in
        *" system_prompt "*) system_prompt="true" ;;
    esac
    case " $caps " in
        *" auto_mode "*) auto_mode="true" ;;
    esac
    case " $caps " in
        *" json_output "*) json_output="true" ;;
    esac
    case " $caps " in
        *" model_selection "*) model_selection="true" ;;
    esac

    jq -n \
        --arg harness "$harness" \
        --argjson streaming "$streaming" \
        --argjson token_reporting "$token_reporting" \
        --argjson system_prompt "$system_prompt" \
        --argjson auto_mode "$auto_mode" \
        --argjson json_output "$json_output" \
        --argjson model_selection "$model_selection" \
        '{harness: $harness, streaming: $streaming, token_reporting: $token_reporting, system_prompt: $system_prompt, auto_mode: $auto_mode, json_output: $json_output, model_selection: $model_selection}'
}

# ============================================================================
# Token Usage Tracking (file-based to survive command substitution)
# ============================================================================

# File paths for usage tracking (process-specific)
_USAGE_INPUT_FILE="${TMPDIR:-/tmp}/curb_usage_input_$$"
_USAGE_OUTPUT_FILE="${TMPDIR:-/tmp}/curb_usage_output_$$"
_USAGE_CACHE_INPUT_FILE="${TMPDIR:-/tmp}/curb_usage_cache_input_$$"
_USAGE_CACHE_CREATION_FILE="${TMPDIR:-/tmp}/curb_usage_cache_creation_$$"
_USAGE_COST_FILE="${TMPDIR:-/tmp}/curb_usage_cost_$$"
_USAGE_ESTIMATED_FILE="${TMPDIR:-/tmp}/curb_usage_estimated_$$"

# Cleanup trap for usage files
trap 'rm -f "$_USAGE_INPUT_FILE" "$_USAGE_OUTPUT_FILE" "$_USAGE_CACHE_INPUT_FILE" "$_USAGE_CACHE_CREATION_FILE" "$_USAGE_COST_FILE" "$_USAGE_ESTIMATED_FILE" 2>/dev/null' EXIT

# Clear all usage tracking state
# Usage: harness_clear_usage
harness_clear_usage() {
    rm -f "$_USAGE_INPUT_FILE" "$_USAGE_OUTPUT_FILE" "$_USAGE_CACHE_INPUT_FILE" "$_USAGE_CACHE_CREATION_FILE" "$_USAGE_COST_FILE" "$_USAGE_ESTIMATED_FILE" 2>/dev/null
    return 0
}

# Store usage data (internal function)
# Usage: _harness_store_usage input_tokens output_tokens [cache_read_tokens] [cache_creation_tokens] [cost_usd] [estimated]
_harness_store_usage() {
    local input_tokens="${1:-0}"
    local output_tokens="${2:-0}"
    local cache_read_tokens="${3:-0}"
    local cache_creation_tokens="${4:-0}"
    local cost_usd="${5:-}"
    local estimated="${6:-false}"

    echo "$input_tokens" > "$_USAGE_INPUT_FILE"
    echo "$output_tokens" > "$_USAGE_OUTPUT_FILE"
    echo "$cache_read_tokens" > "$_USAGE_CACHE_INPUT_FILE"
    echo "$cache_creation_tokens" > "$_USAGE_CACHE_CREATION_FILE"
    if [[ -n "$cost_usd" && "$cost_usd" != "null" ]]; then
        echo "$cost_usd" > "$_USAGE_COST_FILE"
    fi
    if [[ "$estimated" == "true" ]]; then
        echo "true" > "$_USAGE_ESTIMATED_FILE"
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

    # Check if usage was marked as estimated
    if [[ -f "$_USAGE_ESTIMATED_FILE" ]]; then
        estimated="true"
    fi

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
# Debug Command Logging
# ============================================================================

# Log the full harness command in debug mode
# Helps with troubleshooting and allows easy copy-paste for manual testing
# Usage: _harness_log_command harness_name command [flags...]
# Example: _harness_log_command "claude" "claude" "-p" "--append-system-prompt" "..."
_harness_log_command() {
    local debug="${1:-false}"
    local harness_name="$2"
    shift 2
    local cmd_args=("$@")

    # Only log in debug mode
    if [[ "$debug" != "true" ]]; then
        return 0
    fi

    # Build the full command string with proper quoting for display
    local full_cmd="$harness_name"
    for arg in "${cmd_args[@]}"; do
        # Quote arguments that contain spaces or special characters
        if [[ "$arg" =~ [[:space:]] || "$arg" =~ [\'\"\$\`\\] ]]; then
            full_cmd="$full_cmd \"${arg//\"/\\\"}\""
        else
            full_cmd="$full_cmd $arg"
        fi
    done

    # Redact potential secrets in the command
    # Common patterns: API keys, tokens, passwords
    local redacted_cmd="$full_cmd"
    redacted_cmd=$(echo "$redacted_cmd" | sed -E 's/(api[_-]?key|password|token|secret|authorization|credentials)[=:][^ "]*/**REDACTED**/gi')
    redacted_cmd=$(echo "$redacted_cmd" | sed -E 's/(sk-[a-zA-Z0-9]{20,})/**REDACTED**/g')
    redacted_cmd=$(echo "$redacted_cmd" | sed -E 's/(anthropic_api_key|openai_api_key)[=:][^ "]*/\1=**REDACTED**/gi')

    # Output debug message (will be captured by caller's debug logging)
    echo "[debug] Harness command: $redacted_cmd" >&2
    echo "[debug] Copy-paste ready (unredacted version may contain secrets):" >&2
    echo "[debug] echo 'PROMPT_HERE' | $harness_name ${cmd_args[*]}" >&2
}

# ============================================================================
# Harness Detection
# ============================================================================

# Detect available harness
# Priority: explicit HARNESS setting > config priority list > default detection order
harness_detect() {
    # If explicitly set and not "auto", use that
    if [[ -n "${HARNESS:-}" && "$HARNESS" != "auto" ]]; then
        _HARNESS="$HARNESS"
        echo "$_HARNESS"
        return 0
    fi

    # Try to read priority from config
    local priority_json
    priority_json=$(config_get "harness.priority" 2>/dev/null || echo "")

    # If priority is configured, use it
    if [[ -n "$priority_json" ]]; then
        # Extract priorities from JSON array and try each one in order
        local priority_list
        priority_list=$(echo "$priority_json" | jq -r '.[]?' 2>/dev/null)

        # Try each harness in priority order
        while IFS= read -r harness; do
            if [[ -n "$harness" ]] && command -v "$harness" >/dev/null 2>&1; then
                _HARNESS="$harness"
                echo "$_HARNESS"
                return 0
            fi
        done <<< "$priority_list"
        # If we get here, no harness from priority list was found
    fi

    # Fallback to default detection order: claude > opencode > codex > gemini
    if command -v claude >/dev/null 2>&1; then
        _HARNESS="claude"
    elif command -v opencode >/dev/null 2>&1; then
        _HARNESS="opencode"
    elif command -v codex >/dev/null 2>&1; then
        _HARNESS="codex"
    elif command -v gemini >/dev/null 2>&1; then
        _HARNESS="gemini"
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
    command -v claude >/dev/null 2>&1 || command -v opencode >/dev/null 2>&1 || command -v codex >/dev/null 2>&1 || command -v gemini >/dev/null 2>&1
}

# Get version of current harness
harness_version() {
    local harness=$(harness_get)

    case "$harness" in
        claude)
            claude --version 2>&1 || echo "unknown"
            ;;
        opencode)
            opencode --version 2>&1 || echo "unknown"
            ;;
        codex)
            codex --version 2>&1 || echo "unknown"
            ;;
        gemini)
            gemini --version 2>&1 || echo "unknown"
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
        opencode)
            opencode_invoke "$system_prompt" "$task_prompt" "$debug"
            ;;
        codex)
            codex_invoke "$system_prompt" "$task_prompt" "$debug"
            ;;
        gemini)
            gemini_invoke "$system_prompt" "$task_prompt" "$debug"
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
        opencode)
            opencode_invoke_streaming "$system_prompt" "$task_prompt" "$debug"
            ;;
        codex)
            codex_invoke_streaming "$system_prompt" "$task_prompt" "$debug"
            ;;
        gemini)
            gemini_invoke_streaming "$system_prompt" "$task_prompt" "$debug"
            ;;
        *)
            echo "Error: No harness available" >&2
            return 1
            ;;
    esac
}

# ============================================================================
# Output Buffering Helpers
# ============================================================================

# Get stdbuf command for line buffering if available
# Returns: "stdbuf -oL" or "gstdbuf -oL" or empty string
# Usage: local stdbuf_cmd=$(_get_stdbuf_cmd)
_get_stdbuf_cmd() {
    if command -v stdbuf >/dev/null 2>&1; then
        echo "stdbuf -oL"
    elif command -v gstdbuf >/dev/null 2>&1; then
        echo "gstdbuf -oL"  # macOS with homebrew coreutils
    else
        echo ""
    fi
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

    # Log full command in debug mode
    _harness_log_command "$debug" "claude" "-p" "--append-system-prompt" "[SYSTEM_PROMPT]" $flags

    # Capture JSON output to extract usage, then display result
    local output
    output=$(echo "$task_prompt" | claude -p --append-system-prompt "$system_prompt" $flags 2>&1)
    local exit_code=$?

    # Log raw output if CURB_HARNESS_LOG is set
    if [[ -n "${CURB_HARNESS_LOG:-}" ]]; then
        echo "$output" >> "${CURB_HARNESS_LOG}"
    fi

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

    # Log full command in debug mode
    _harness_log_command "$debug" "claude" "-p" "--append-system-prompt" "[SYSTEM_PROMPT]" $flags

    # Use stdbuf for line buffering if available (prevents output truncation)
    # Falls back to temp file capture when stdbuf is not available
    local stdbuf_cmd
    stdbuf_cmd=$(_get_stdbuf_cmd)

    # Optional: tee raw output to log file if CURB_HARNESS_LOG is set
    local tee_cmd="cat"
    if [[ -n "${CURB_HARNESS_LOG:-}" ]]; then
        tee_cmd="tee -a ${CURB_HARNESS_LOG}"
    fi

    if [[ -n "$stdbuf_cmd" ]]; then
        # Line-buffered streaming - output appears in real-time
        # With optional logging via tee
        echo "$task_prompt" | $stdbuf_cmd claude -p --append-system-prompt "$system_prompt" $flags | $tee_cmd | claude_parse_stream
        return ${PIPESTATUS[1]}
    else
        # Temp file fallback - ensures complete output capture
        local tmpfile="${TMPDIR:-/tmp}/curb_claude_stream_$$"
        echo "$task_prompt" | claude -p --append-system-prompt "$system_prompt" $flags > "$tmpfile" 2>&1
        local exit_code=${PIPESTATUS[1]}
        # Log raw output if requested
        if [[ -n "${CURB_HARNESS_LOG:-}" ]]; then
            cat "$tmpfile" >> "${CURB_HARNESS_LOG}"
        fi
        claude_parse_stream < "$tmpfile"
        rm -f "$tmpfile"
        return $exit_code
    fi
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

# Map complexity label to codex model
# Complexity levels: low -> gpt-4o-mini, medium -> gpt-4o, high -> o3
# Also supports explicit model: labels like model:o3
_codex_get_model_for_complexity() {
    local complexity="${1:-medium}"

    case "$complexity" in
        low|simple)
            echo "gpt-4o-mini"
            ;;
        high|complex)
            echo "o3"
            ;;
        *)
            # medium or unspecified - use default (gpt-4o or config default)
            echo ""
            ;;
    esac
}

codex_invoke() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    # Clear previous usage
    harness_clear_usage

    # Codex doesn't have --append-system-prompt, so we combine prompts
    # The system prompt goes first, then a separator, then the task
    local combined_prompt="${system_prompt}

---

${task_prompt}"

    # Use full bypass for autonomous operation - matches claude's --dangerously-skip-permissions
    # --full-auto alone still prompts for network/git operations
    local flags="--dangerously-bypass-approvals-and-sandbox"

    # Add model flag if specified via CURB_MODEL
    if [[ -n "${CURB_MODEL:-}" ]]; then
        flags="$flags -m $CURB_MODEL"
    fi

    # Add any extra flags from environment
    [[ -n "${CODEX_FLAGS:-}" ]] && flags="$flags $CODEX_FLAGS"

    # Log full command in debug mode
    _harness_log_command "$debug" "codex" "exec" $flags "-"

    # Run codex and capture output
    local output
    output=$(echo "$combined_prompt" | codex exec $flags - 2>&1)
    local exit_code=$?

    # Display the output
    echo "$output"

    # Estimate token usage based on character counts
    # Codex CLI doesn't report actual usage in stdout
    local input_chars=${#combined_prompt}
    local output_chars=${#output}
    local estimated_input=$((input_chars / 4))
    local estimated_output=$((output_chars / 4))

    _harness_store_usage "$estimated_input" "$estimated_output" 0 0 "" "true"

    return $exit_code
}

codex_invoke_streaming() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    # Clear previous usage
    harness_clear_usage

    local combined_prompt="${system_prompt}

---

${task_prompt}"

    # Use full bypass for autonomous operation + JSON for streaming
    local flags="--dangerously-bypass-approvals-and-sandbox --json"

    # Add model flag if specified via CURB_MODEL
    if [[ -n "${CURB_MODEL:-}" ]]; then
        flags="$flags -m $CURB_MODEL"
    fi

    # Add any extra flags from environment
    [[ -n "${CODEX_FLAGS:-}" ]] && flags="$flags $CODEX_FLAGS"

    # Log full command in debug mode
    _harness_log_command "$debug" "codex" "exec" $flags "-"

    # Optional: tee raw output to log file if CURB_HARNESS_LOG is set
    local tee_cmd="cat"
    if [[ -n "${CURB_HARNESS_LOG:-}" ]]; then
        tee_cmd="tee -a ${CURB_HARNESS_LOG}"
    fi

    # Use stdbuf for line buffering if available
    local stdbuf_cmd
    stdbuf_cmd=$(_get_stdbuf_cmd)

    if [[ -n "$stdbuf_cmd" ]]; then
        echo "$combined_prompt" | $stdbuf_cmd codex exec $flags - | $tee_cmd | codex_parse_stream
        return ${PIPESTATUS[1]}
    else
        local tmpfile="${TMPDIR:-/tmp}/curb_codex_stream_$$"
        echo "$combined_prompt" | codex exec $flags - > "$tmpfile" 2>&1
        local exit_code=${PIPESTATUS[1]}
        if [[ -n "${CURB_HARNESS_LOG:-}" ]]; then
            cat "$tmpfile" >> "${CURB_HARNESS_LOG}"
        fi
        codex_parse_stream < "$tmpfile"
        rm -f "$tmpfile"
        return $exit_code
    fi
}

# Parse Codex's --json JSONL output
# Codex emits events like: thread.started, turn.started, item.started, item.completed
# Item types include: reasoning, command_execution, message, file_edit, etc.
codex_parse_stream() {
    local total_input=0
    local total_output=0

    while IFS= read -r line; do
        # Skip empty lines
        [[ -z "$line" ]] && continue

        # Parse JSON event type
        local event_type=$(echo "$line" | jq -r '.type // empty' 2>/dev/null)

        case "$event_type" in
            item.started)
                # Show what's starting
                local item_type=$(echo "$line" | jq -r '.item.type // empty' 2>/dev/null)
                case "$item_type" in
                    command_execution)
                        local cmd=$(echo "$line" | jq -r '.item.command // empty' 2>/dev/null)
                        [[ -n "$cmd" ]] && echo -e "${CYAN}$ ${cmd}${NC}"
                        ;;
                    file_edit|file_write)
                        local file=$(echo "$line" | jq -r '.item.file_path // .item.path // empty' 2>/dev/null)
                        [[ -n "$file" ]] && echo -e "${YELLOW}▶ Editing: ${file}${NC}"
                        ;;
                esac
                ;;
            item.completed)
                # Extract item details
                local item_type=$(echo "$line" | jq -r '.item.type // empty' 2>/dev/null)
                case "$item_type" in
                    reasoning)
                        local text=$(echo "$line" | jq -r '.item.text // empty' 2>/dev/null)
                        [[ -n "$text" ]] && echo -e "${DIM}${text}${NC}"
                        ;;
                    message)
                        local content=$(echo "$line" | jq -r '.item.content // .item.text // empty' 2>/dev/null)
                        [[ -n "$content" ]] && echo -e "$content"
                        ;;
                    command_execution)
                        local output=$(echo "$line" | jq -r '.item.aggregated_output // empty' 2>/dev/null)
                        local exit_code=$(echo "$line" | jq -r '.item.exit_code // empty' 2>/dev/null)
                        if [[ -n "$output" ]]; then
                            # Truncate long output
                            if [[ ${#output} -gt 500 ]]; then
                                echo "${output:0:500}..."
                            else
                                echo "$output"
                            fi
                        fi
                        ;;
                    file_edit|file_write)
                        local status=$(echo "$line" | jq -r '.item.status // empty' 2>/dev/null)
                        [[ "$status" == "completed" ]] && echo -e "${GREEN}✓ File updated${NC}"
                        ;;
                esac
                ;;
            turn.completed)
                # Turn completed - could extract usage here if available
                local usage=$(echo "$line" | jq -r '.usage // empty' 2>/dev/null)
                if [[ -n "$usage" && "$usage" != "null" ]]; then
                    local input=$(echo "$line" | jq -r '.usage.input_tokens // 0' 2>/dev/null)
                    local output=$(echo "$line" | jq -r '.usage.output_tokens // 0' 2>/dev/null)
                    total_input=$((total_input + input))
                    total_output=$((total_output + output))
                fi
                ;;
            thread.started|turn.started)
                # Session lifecycle events - skip silently
                ;;
            *)
                # For unknown events, try to extract any text content
                local text=$(echo "$line" | jq -r '.item.text // .text // .output // empty' 2>/dev/null)
                [[ -n "$text" ]] && echo "$text"
                ;;
        esac
    done

    # Store accumulated usage (or estimate if none reported)
    if [[ $total_input -gt 0 || $total_output -gt 0 ]]; then
        _harness_store_usage "$total_input" "$total_output" 0 0 ""
    fi
}

# ============================================================================
# Gemini Backend
# ============================================================================

gemini_invoke() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    # Clear previous usage
    harness_clear_usage

    # Gemini CLI doesn't have --append-system-prompt, so we combine prompts
    # The system prompt goes first, then a separator, then the task
    local combined_prompt="${system_prompt}

---

${task_prompt}"

    # YOLO mode (-y) is REQUIRED for autonomous operation (auto-accept all actions)
    local flags="-y"
    [[ "$debug" == "true" ]] && flags="$flags -d"

    # Add model flag if specified (default: gemini-2.5-pro)
    [[ -n "${CURB_MODEL:-}" ]] && flags="$flags -m $CURB_MODEL"

    # Add any extra flags from environment
    [[ -n "${GEMINI_FLAGS:-}" ]] && flags="$flags $GEMINI_FLAGS"

    # Log full command in debug mode
    _harness_log_command "$debug" "gemini" "-p" "[PROMPT]" $flags

    # Capture output to estimate token usage (Gemini CLI doesn't report actual usage)
    local output
    output=$(echo "" | gemini -p "$combined_prompt" $flags 2>&1)
    local exit_code=$?

    # Display the output
    echo "$output"

    # Estimate token usage based on character counts
    # Note: Gemini CLI v0.1.9 does NOT report token usage in stdout or session files
    # Rough estimation: ~4 characters per token (common rule of thumb)
    # This is marked as estimated in harness_get_usage output
    local input_chars=${#combined_prompt}
    local output_chars=${#output}
    local estimated_input=$((input_chars / 4))
    local estimated_output=$((output_chars / 4))

    # Store estimated usage (will be marked as estimated=true in harness_get_usage)
    _harness_store_usage "$estimated_input" "$estimated_output" 0 0 "" "true"

    return $exit_code
}

gemini_invoke_streaming() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    # Gemini CLI v0.1.9 does NOT support --output-format stream-json
    # The flag is documented but not recognized in the homebrew version
    # TODO: Test newer versions for streaming support
    # For now, streaming mode just runs the same as non-streaming
    gemini_invoke "$system_prompt" "$task_prompt" "$debug"
}

# ============================================================================
# OpenCode Backend
# ============================================================================

opencode_invoke() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    # Clear previous usage
    harness_clear_usage

    # OpenCode doesn't have --append-system-prompt, so we combine prompts
    # The system prompt goes first, then a separator, then the task
    # Note: For production use, consider using AGENTS.md file instead
    local combined_prompt="${system_prompt}

---

${task_prompt}"

    # Use --format json for token extraction
    local flags="--format json"
    [[ "$debug" == "true" ]] && flags="$flags --print-logs --log-level DEBUG"

    # Add model flag if specified (requires provider/model format)
    if [[ -n "${CURB_MODEL:-}" ]]; then
        # If model doesn't contain '/', assume anthropic provider
        if [[ "$CURB_MODEL" != */* ]]; then
            flags="$flags -m anthropic/$CURB_MODEL"
        else
            flags="$flags -m $CURB_MODEL"
        fi
    fi

    # Add any extra flags from environment
    [[ -n "${OPENCODE_FLAGS:-}" ]] && flags="$flags $OPENCODE_FLAGS"

    # Log full command in debug mode
    _harness_log_command "$debug" "opencode" "run" $flags "[PROMPT]"

    # OpenCode uses 'run' subcommand for autonomous operation (auto-approves all permissions)
    # Use --format json to get token usage, then parse with opencode_parse_stream
    # Use stdbuf for line buffering if available (prevents output truncation)
    local stdbuf_cmd
    stdbuf_cmd=$(_get_stdbuf_cmd)

    if [[ -n "$stdbuf_cmd" ]]; then
        $stdbuf_cmd opencode run $flags "$combined_prompt" | opencode_parse_stream
        return ${PIPESTATUS[0]}
    else
        # Temp file fallback - ensures complete output capture
        local tmpfile="${TMPDIR:-/tmp}/curb_opencode_$$"
        opencode run $flags "$combined_prompt" > "$tmpfile" 2>&1
        local exit_code=$?
        opencode_parse_stream < "$tmpfile"
        rm -f "$tmpfile"
        return $exit_code
    fi
}

opencode_invoke_streaming() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    # Clear previous usage
    harness_clear_usage

    local combined_prompt="${system_prompt}

---

${task_prompt}"

    # Use --format json for structured streaming output
    local flags="--format json"
    [[ "$debug" == "true" ]] && flags="$flags --print-logs --log-level DEBUG"

    # Add model flag if specified
    if [[ -n "${CURB_MODEL:-}" ]]; then
        if [[ "$CURB_MODEL" != */* ]]; then
            flags="$flags -m anthropic/$CURB_MODEL"
        else
            flags="$flags -m $CURB_MODEL"
        fi
    fi

    # Add any extra flags from environment
    [[ -n "${OPENCODE_FLAGS:-}" ]] && flags="$flags $OPENCODE_FLAGS"

    # Log full command in debug mode
    _harness_log_command "$debug" "opencode" "run" $flags "[PROMPT]"

    # Use stdbuf for line buffering if available (prevents output truncation)
    local stdbuf_cmd
    stdbuf_cmd=$(_get_stdbuf_cmd)

    if [[ -n "$stdbuf_cmd" ]]; then
        $stdbuf_cmd opencode run $flags "$combined_prompt" | opencode_parse_stream
        return ${PIPESTATUS[0]}
    else
        # Temp file fallback - ensures complete output capture
        local tmpfile="${TMPDIR:-/tmp}/curb_opencode_stream_$$"
        opencode run $flags "$combined_prompt" > "$tmpfile" 2>&1
        local exit_code=$?
        opencode_parse_stream < "$tmpfile"
        rm -f "$tmpfile"
        return $exit_code
    fi
}

# Parse OpenCode's JSON streaming output
# Extracts text output for display and captures token usage from step_finish events
opencode_parse_stream() {
    # Clear previous usage before parsing new stream
    harness_clear_usage

    # Local variables for accumulating usage across multiple steps
    local total_input=0
    local total_output=0
    local total_cache_read=0
    local total_cache_write=0
    local total_reasoning=0
    local final_cost=""

    while IFS= read -r line; do
        # Skip empty lines
        [[ -z "$line" ]] && continue

        # Parse JSON and extract relevant info
        local msg_type=$(echo "$line" | jq -r '.type // empty' 2>/dev/null)

        case "$msg_type" in
            "text")
                # Extract and display text content
                local text=$(echo "$line" | jq -r '.part.text // empty' 2>/dev/null)
                [[ -n "$text" ]] && printf "%s" "$text"
                ;;
            "step_finish")
                # Extract token usage from step_finish events
                # OpenCode structure: .part.tokens.input, .part.tokens.output, etc.
                local input=$(echo "$line" | jq -r '.part.tokens.input // 0' 2>/dev/null)
                local output=$(echo "$line" | jq -r '.part.tokens.output // 0' 2>/dev/null)
                local reasoning=$(echo "$line" | jq -r '.part.tokens.reasoning // 0' 2>/dev/null)
                local cache_read=$(echo "$line" | jq -r '.part.tokens.cache.read // 0' 2>/dev/null)
                local cache_write=$(echo "$line" | jq -r '.part.tokens.cache.write // 0' 2>/dev/null)
                local cost=$(echo "$line" | jq -r '.part.cost // empty' 2>/dev/null)

                # Accumulate usage (multiple steps possible in a session)
                total_input=$((total_input + input))
                total_output=$((total_output + output))
                total_reasoning=$((total_reasoning + reasoning))
                total_cache_read=$((total_cache_read + cache_read))
                total_cache_write=$((total_cache_write + cache_write))
                [[ -n "$cost" && "$cost" != "null" ]] && final_cost="$cost"
                ;;
        esac
    done

    # Store accumulated usage
    # Note: OpenCode reports cache.write, which maps to cache_creation_tokens
    # Reasoning tokens are not currently tracked separately (included in output for simplicity)
    _harness_store_usage "$total_input" "$total_output" "$total_cache_read" "$total_cache_write" "$final_cost"
}
