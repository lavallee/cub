#!/usr/bin/env bats
#
# tests/harness.bats - Tests for lib/harness.sh
#

load 'test_helper'

setup() {
    setup_test_dir

    # Reset harness cache
    export _HARNESS=""
    unset HARNESS
    unset CLAUDE_FLAGS
    unset CODEX_FLAGS

    # Source the library under test
    source "$LIB_DIR/harness.sh"
}

teardown() {
    teardown_test_dir
}

# =============================================================================
# Harness Detection Tests
# =============================================================================

@test "harness_detect respects explicit HARNESS setting" {
    export HARNESS="codex"
    run harness_detect
    [ "$status" -eq 0 ]
    [ "$output" = "codex" ]
}

@test "harness_detect ignores HARNESS=auto" {
    export HARNESS="auto"
    run harness_detect
    # Should fall through to auto-detection
    [ "$status" -eq 0 ]
    # Output will be whatever is installed (claude, codex, or empty)
}

@test "harness_get caches detected harness" {
    _HARNESS="claude"
    run harness_get
    [ "$output" = "claude" ]
}

# =============================================================================
# Harness Availability Tests
# =============================================================================

@test "harness_available returns true when specified harness exists" {
    # Test with a command we know exists
    run harness_available "bash"
    [ "$status" -eq 0 ]
}

@test "harness_available returns false when specified harness missing" {
    run harness_available "nonexistent_harness_xyz"
    [ "$status" -ne 0 ]
}

# =============================================================================
# Harness Version Tests
# =============================================================================

@test "harness_version returns value for installed harness" {
    # If claude or codex is installed, version should return something
    # If neither is installed, it returns "no harness"
    run harness_version
    [ "$status" -eq 0 ]
    [ -n "$output" ]
}

# =============================================================================
# Claude Stream Parsing Tests
# =============================================================================

@test "claude_parse_stream extracts text from assistant message" {
    local json='{"type":"assistant","message":{"content":[{"type":"text","text":"Hello world"}]}}'
    result=$(echo "$json" | claude_parse_stream)
    [[ "$result" == *"Hello world"* ]]
}

@test "claude_parse_stream handles content_block_delta text" {
    local json='{"type":"content_block_delta","delta":{"type":"text_delta","text":"streaming text"}}'
    result=$(echo "$json" | claude_parse_stream)
    [[ "$result" == *"streaming text"* ]]
}

@test "claude_parse_stream skips empty lines gracefully" {
    result=$(echo "" | claude_parse_stream)
    [ -z "$result" ]
}

@test "claude_parse_stream handles result messages" {
    local json='{"type":"result","result":"Task completed successfully","cost_usd":"0.05"}'
    result=$(echo "$json" | claude_parse_stream)
    [[ "$result" == *"Result"* ]] || [[ "$result" == *"Task completed"* ]]
}

@test "claude_parse_stream shows tool use in content_block_start" {
    local json='{"type":"content_block_start","content_block":{"type":"tool_use","name":"Read"}}'
    result=$(echo "$json" | claude_parse_stream)
    [[ "$result" == *"Read"* ]]
}

# =============================================================================
# Harness Invoke Tests
# =============================================================================

@test "harness_invoke dispatches to correct harness" {
    # Set harness explicitly to a value
    _HARNESS="nonexistent"
    # Since nonexistent harness doesn't match claude or codex case,
    # it should hit the error case
    run harness_invoke "system prompt" "task prompt"
    [ "$status" -ne 0 ]
    [[ "$output" == *"No harness available"* ]]
}

@test "harness_invoke_streaming fails gracefully for unknown harness" {
    _HARNESS="unknown"
    run harness_invoke_streaming "system prompt" "task prompt"
    [ "$status" -ne 0 ]
    [[ "$output" == *"No harness available"* ]]
}

# =============================================================================
# Flag Handling Tests
# =============================================================================

@test "CLAUDE_FLAGS environment variable is accessible" {
    export CLAUDE_FLAGS="--max-turns 5"
    [ "$CLAUDE_FLAGS" = "--max-turns 5" ]
}

@test "CODEX_FLAGS environment variable is accessible" {
    export CODEX_FLAGS="--model gpt-4"
    [ "$CODEX_FLAGS" = "--model gpt-4" ]
}

# =============================================================================
# Integration Tests (only run if harness installed)
# =============================================================================

@test "harness_detect finds claude when installed" {
    if ! command -v claude >/dev/null 2>&1; then
        skip "claude not installed"
    fi
    unset HARNESS
    _HARNESS=""
    run harness_detect
    [ "$output" = "claude" ]
}

@test "harness_available returns true for any installed harness" {
    run harness_available
    # Should succeed if either claude or codex is installed
    if command -v claude >/dev/null 2>&1 || command -v codex >/dev/null 2>&1; then
        [ "$status" -eq 0 ]
    else
        [ "$status" -ne 0 ]
    fi
}

# =============================================================================
# Token Usage Tracking Tests
# =============================================================================

@test "harness_clear_usage clears all usage state" {
    # Store some usage
    _harness_store_usage 100 200 50 25 "0.05"

    # Clear it
    harness_clear_usage

    # Verify all cleared
    run harness_get_usage
    [ "$status" -eq 0 ]
    local input=$(echo "$output" | jq -r '.input_tokens')
    local output_tokens=$(echo "$output" | jq -r '.output_tokens')
    [ "$input" -eq 0 ]
    [ "$output_tokens" -eq 0 ]
}

@test "harness_get_usage returns JSON with correct structure" {
    harness_clear_usage
    _harness_store_usage 1000 500 200 100 "0.03"

    run harness_get_usage
    [ "$status" -eq 0 ]

    # Verify JSON structure
    local input=$(echo "$output" | jq -r '.input_tokens')
    local output_tokens=$(echo "$output" | jq -r '.output_tokens')
    local cache_read=$(echo "$output" | jq -r '.cache_read_tokens')
    local cache_creation=$(echo "$output" | jq -r '.cache_creation_tokens')
    local cost=$(echo "$output" | jq -r '.cost_usd')
    local estimated=$(echo "$output" | jq -r '.estimated')

    [ "$input" -eq 1000 ]
    [ "$output_tokens" -eq 500 ]
    [ "$cache_read" -eq 200 ]
    [ "$cache_creation" -eq 100 ]
    [ "$cost" = "0.03" ]
    [ "$estimated" = "false" ]
}

@test "harness_get_usage handles no usage data gracefully" {
    harness_clear_usage

    run harness_get_usage
    [ "$status" -eq 0 ]

    local input=$(echo "$output" | jq -r '.input_tokens')
    local output_tokens=$(echo "$output" | jq -r '.output_tokens')
    local estimated=$(echo "$output" | jq -r '.estimated')

    [ "$input" -eq 0 ]
    [ "$output_tokens" -eq 0 ]
    [ "$estimated" = "false" ]
}

@test "harness_get_total_tokens returns sum of input and output" {
    harness_clear_usage
    _harness_store_usage 1000 500 0 0 ""

    run harness_get_total_tokens
    [ "$status" -eq 0 ]
    [ "$output" -eq 1500 ]
}

@test "claude_parse_stream extracts usage from message events" {
    harness_clear_usage

    # Simulate a message event with usage (based on actual Claude output)
    local json='{"type":"message","usage":{"input_tokens":4,"output_tokens":72,"cache_read_input_tokens":25484,"cache_creation_input_tokens":0}}'
    echo "$json" | claude_parse_stream

    run harness_get_usage
    [ "$status" -eq 0 ]

    local input=$(echo "$output" | jq -r '.input_tokens')
    local output_tokens=$(echo "$output" | jq -r '.output_tokens')
    local cache_read=$(echo "$output" | jq -r '.cache_read_tokens')

    [ "$input" -eq 4 ]
    [ "$output_tokens" -eq 72 ]
    [ "$cache_read" -eq 25484 ]
}

@test "claude_parse_stream captures cost from result events" {
    harness_clear_usage

    # Simulate result event with cost
    local json='{"type":"result","result":"Task completed","cost_usd":0.0172697}'
    echo "$json" | claude_parse_stream

    run harness_get_usage
    [ "$status" -eq 0 ]

    local cost=$(echo "$output" | jq -r '.cost_usd')
    [ "$cost" = "0.0172697" ]
}

@test "claude_parse_stream accumulates usage from multiple messages" {
    harness_clear_usage

    # Simulate multiple message events (multi-turn conversation)
    cat > "$TEST_DIR/stream.json" << 'EOF'
{"type":"message","usage":{"input_tokens":100,"output_tokens":50,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}
{"type":"message","usage":{"input_tokens":200,"output_tokens":75,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}
{"type":"result","result":"done","cost_usd":0.05}
EOF

    cat "$TEST_DIR/stream.json" | claude_parse_stream

    run harness_get_usage
    [ "$status" -eq 0 ]

    local input=$(echo "$output" | jq -r '.input_tokens')
    local output_tokens=$(echo "$output" | jq -r '.output_tokens')

    # Should be accumulated: 100+200=300 input, 50+75=125 output
    [ "$input" -eq 300 ]
    [ "$output_tokens" -eq 125 ]
}

@test "harness_get_usage estimates tokens from cost when usage unavailable" {
    harness_clear_usage

    # Store only cost, no token counts
    echo "0" > "$_USAGE_INPUT_FILE"
    echo "0" > "$_USAGE_OUTPUT_FILE"
    echo "0.10" > "$_USAGE_COST_FILE"

    run harness_get_usage
    [ "$status" -eq 0 ]

    local estimated=$(echo "$output" | jq -r '.estimated')
    local input=$(echo "$output" | jq -r '.input_tokens')
    local output_tokens=$(echo "$output" | jq -r '.output_tokens')

    # Should be estimated=true with non-zero values
    [ "$estimated" = "true" ]
    [ "$input" -gt 0 ]
    [ "$output_tokens" -gt 0 ]
}

# =============================================================================
# Acceptance Criteria Tests
# =============================================================================

@test "ACCEPTANCE: Token count extracted from Claude streaming output" {
    harness_clear_usage

    # Simulate real Claude stream-json output with usage
    local json='{"type":"message","usage":{"input_tokens":1500,"output_tokens":300,"cache_read_input_tokens":100,"cache_creation_input_tokens":50}}'
    echo "$json" | claude_parse_stream

    run harness_get_usage
    [ "$status" -eq 0 ]

    local input=$(echo "$output" | jq -r '.input_tokens')
    [ "$input" -eq 1500 ]
}

@test "ACCEPTANCE: Tokens returned in structured format" {
    harness_clear_usage
    _harness_store_usage 1000 500 200 100 "0.05"

    run harness_get_usage
    [ "$status" -eq 0 ]

    # Verify all required fields present
    echo "$output" | jq -e '.input_tokens' >/dev/null
    echo "$output" | jq -e '.output_tokens' >/dev/null
    echo "$output" | jq -e '.estimated' >/dev/null
}

@test "ACCEPTANCE: Fallback to estimate if not available" {
    harness_clear_usage

    # Set cost but no token counts
    echo "0" > "$_USAGE_INPUT_FILE"
    echo "0" > "$_USAGE_OUTPUT_FILE"
    echo "0.05" > "$_USAGE_COST_FILE"

    run harness_get_usage
    [ "$status" -eq 0 ]

    local estimated=$(echo "$output" | jq -r '.estimated')
    [ "$estimated" = "true" ]
}

@test "ACCEPTANCE: Works with streaming mode via claude_parse_stream" {
    harness_clear_usage

    # Full streaming scenario with message and result events
    cat > "$TEST_DIR/full_stream.json" << 'EOF'
{"type":"assistant","message":{"content":[{"type":"text","text":"Hello"}]}}
{"type":"message","usage":{"input_tokens":500,"output_tokens":100,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}
{"type":"result","result":"Task completed","cost_usd":0.02}
EOF

    cat "$TEST_DIR/full_stream.json" | claude_parse_stream

    run harness_get_usage
    [ "$status" -eq 0 ]

    local input=$(echo "$output" | jq -r '.input_tokens')
    local output_tokens=$(echo "$output" | jq -r '.output_tokens')
    local cost=$(echo "$output" | jq -r '.cost_usd')

    [ "$input" -eq 500 ]
    [ "$output_tokens" -eq 100 ]
    [ "$cost" = "0.02" ]
}
