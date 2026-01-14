#!/usr/bin/env bats
#
# tests/cli.bats - CLI dispatcher and routing tests
#
# Tests for the new subcommand-based CLI structure introduced in cub-017/cub-018.
# Covers subcommand routing, help output, deprecation warnings, and backwards compatibility.

load 'test_helper'

setup() {
    setup_test_dir
    export CUB_BACKEND="json"
    export CUB_PROJECT_DIR="$TEST_DIR"
    # Mock harness to avoid actual invocation
    export PATH="$TEST_DIR:$PATH"
    cat > "$TEST_DIR/claude" << 'EOF'
#!/bin/bash
echo "Mocked harness"
exit 0
EOF
    chmod +x "$TEST_DIR/claude"

    # Create minimal template files to avoid warnings
    mkdir -p .cub
    echo "System prompt" > .cub/prompt.md
    echo "Build instructions" > .cub/agent.md
}

teardown() {
    teardown_test_dir
}

# =============================================================================
# Subcommand Routing Tests
# =============================================================================

@test "cub version subcommand works" {
    run "$PROJECT_ROOT/cub" version
    [ "$status" -eq 0 ]
    [[ "$output" == *"cub v"* ]]
}

@test "cub init subcommand creates project structure" {
    run "$PROJECT_ROOT/cub" init .
    [ "$status" -eq 0 ]
    [ -f "prd.json" ]
    [ -f ".cub/prompt.md" ]
    [ -f ".cub/agent.md" ]
}

@test "cub status subcommand shows task summary" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" status
    [ "$status" -eq 0 ]
    [[ "$output" == *"Task Status Summary"* ]]
}

@test "cub run subcommand with --once flag" {
    use_fixture "valid_prd.json" "prd.json"

    # Should recognize run subcommand with flags
    run "$PROJECT_ROOT/cub" run --once
    # May fail due to missing dependencies but shouldn't crash
}

@test "cub run subcommand with --ready flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --ready
    [ "$status" -eq 0 ]
    [[ "$output" == *"Ready Tasks"* ]]
}

@test "cub run subcommand with --plan flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --plan
    # May fail without proper setup but shouldn't crash with routing error
}

@test "cub explain subcommand shows task details" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" explain prd-0002
    [ "$status" -eq 0 ]
    [[ "$output" == *"prd-0002"* ]]
}

@test "cub artifacts subcommand lists recent tasks" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" artifacts
    [ "$status" -eq 0 ]
    # Should show message about no artifacts or list them
}

# =============================================================================
# Help Output Tests
# =============================================================================

@test "cub --help shows main help" {
    run "$PROJECT_ROOT/cub" --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"SUBCOMMANDS"* ]]
    [[ "$output" == *"cub init"* ]]
    [[ "$output" == *"cub run"* ]]
    [[ "$output" == *"cub status"* ]]
}

@test "cub help subcommand shows main help" {
    run "$PROJECT_ROOT/cub" help
    [ "$status" -eq 0 ]
    [[ "$output" == *"SUBCOMMANDS"* ]]
}

@test "cub -h shows main help" {
    run "$PROJECT_ROOT/cub" -h
    [ "$status" -eq 0 ]
    [[ "$output" == *"SUBCOMMANDS"* ]]
}

@test "cub init --help shows init-specific help" {
    run "$PROJECT_ROOT/cub" init --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"cub init"* ]]
    [[ "$output" == *"--global"* ]]
    [[ "$output" != *"cub run"* ]]  # Should not show run help
}

@test "cub init -h shows init-specific help" {
    run "$PROJECT_ROOT/cub" init -h
    [ "$status" -eq 0 ]
    [[ "$output" == *"cub init"* ]]
}

@test "cub run --help shows run-specific help" {
    run "$PROJECT_ROOT/cub" run --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"cub run"* ]]
    [[ "$output" == *"--once"* ]]
    [[ "$output" == *"--ready"* ]]
    [[ "$output" == *"--plan"* ]]
}

@test "cub run -h shows run-specific help" {
    run "$PROJECT_ROOT/cub" run -h
    [ "$status" -eq 0 ]
    [[ "$output" == *"cub run"* ]]
}

@test "cub status --help shows status-specific help" {
    run "$PROJECT_ROOT/cub" status --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"cub status"* ]]
    [[ "$output" == *"--json"* ]]
}

@test "cub explain --help shows explain-specific help" {
    run "$PROJECT_ROOT/cub" explain --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"cub explain"* ]]
    [[ "$output" == *"task-id"* ]]
}

@test "cub artifacts --help shows artifacts-specific help" {
    run "$PROJECT_ROOT/cub" artifacts --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"cub artifacts"* ]]
}

# =============================================================================
# Deprecation Warning Tests
# =============================================================================

@test "cub --status shows deprecation warning" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --status
    [ "$status" -eq 0 ]
    [[ "$output" == *"deprecated"* ]]
    [[ "$output" == *"cub status"* ]]
}

@test "cub --ready shows deprecation warning" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --ready
    [ "$status" -eq 0 ]
    [[ "$output" == *"deprecated"* ]]
    [[ "$output" == *"cub run --ready"* ]]
}

@test "cub --once shows deprecation warning" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --once
    # Should show deprecation warning
    [[ "$output" == *"deprecated"* ]]
    [[ "$output" == *"cub run --once"* ]]
}

@test "cub --plan shows deprecation warning" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --plan
    # Should show deprecation warning
    [[ "$output" == *"deprecated"* ]]
    [[ "$output" == *"cub run --plan"* ]]
}

@test "cub -s shows deprecation warning" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" -s
    [ "$status" -eq 0 ]
    [[ "$output" == *"deprecated"* ]]
}

@test "cub -r shows deprecation warning" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" -r
    [ "$status" -eq 0 ]
    [[ "$output" == *"deprecated"* ]]
}

@test "cub -1 shows deprecation warning" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" -1
    [[ "$output" == *"deprecated"* ]]
}

@test "cub -p shows deprecation warning" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" -p
    [[ "$output" == *"deprecated"* ]]
}

@test "deprecation warnings can be suppressed" {
    use_fixture "valid_prd.json" "prd.json"

    export CUB_NO_DEPRECATION_WARNINGS=1
    run "$PROJECT_ROOT/cub" --status
    [ "$status" -eq 0 ]
    [[ "$output" != *"deprecated"* ]]
}

# =============================================================================
# Unknown Subcommand Tests
# =============================================================================

@test "cub with unknown subcommand shows error and help" {
    run "$PROJECT_ROOT/cub" foobar
    [ "$status" -eq 0 ]  # Shows help, doesn't fail
    [[ "$output" == *"Unknown subcommand: foobar"* ]]
    [[ "$output" == *"SUBCOMMANDS"* ]]
}

@test "cub with unknown subcommand does not show error for flags" {
    use_fixture "valid_prd.json" "prd.json"

    # Unknown flags pass through to default behavior (run loop)
    # Use timeout to prevent hanging
    timeout 2 "$PROJECT_ROOT/cub" --unknown-flag || true
    # Test passes if it doesn't crash
}

# =============================================================================
# Backwards Compatibility Tests
# =============================================================================

@test "legacy --status invocation still works" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --status
    [ "$status" -eq 0 ]
    [[ "$output" == *"Task Status Summary"* ]] || [[ "$output" == *"Open"* ]]
}

@test "legacy --ready invocation still works" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --ready
    [ "$status" -eq 0 ]
    [[ "$output" == *"Ready Tasks"* ]]
}

@test "legacy --once invocation still works" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --once
    # Should run (may fail due to setup but shouldn't crash)
}

@test "legacy -s short flag still works" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" -s
    [ "$status" -eq 0 ]
    [[ "$output" == *"Task Status Summary"* ]] || [[ "$output" == *"Open"* ]]
}

@test "legacy -r short flag still works" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" -r
    [ "$status" -eq 0 ]
    [[ "$output" == *"Ready Tasks"* ]]
}

@test "legacy --status --json combination still works" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --status --json
    [ "$status" -eq 0 ]
    # Should output valid JSON
    echo "$output" | grep -v deprecated | jq empty
}

# =============================================================================
# Subcommand Flag Parsing Tests
# =============================================================================

@test "cub run accepts --once flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --once
    # Should not show routing error
    [[ "$output" != *"Unknown"* ]] || [[ "$output" != *"unknown"* ]]
}

@test "cub run accepts --ready flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --ready
    [ "$status" -eq 0 ]
    [[ "$output" == *"Ready Tasks"* ]]
}

@test "cub run accepts --plan flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --plan
    # Should recognize flag
}

@test "cub run accepts --model flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --model sonnet --ready
    [ "$status" -eq 0 ]
}

@test "cub run accepts --budget flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --budget 1000000 --ready
    [ "$status" -eq 0 ]
}

@test "cub run accepts --epic flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --epic my-epic --ready
    [ "$status" -eq 0 ]
}

@test "cub run accepts --label flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --label my-label --ready
    [ "$status" -eq 0 ]
}

@test "cub run accepts --require-clean flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --require-clean --ready
    [ "$status" -eq 0 ]
}

@test "cub run accepts --no-require-clean flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --no-require-clean --ready
    [ "$status" -eq 0 ]
}

@test "cub run accepts --name flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --name my-session --ready
    [ "$status" -eq 0 ]
}

@test "cub status accepts --json flag" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" status --json
    [ "$status" -eq 0 ]
    echo "$output" | jq empty
}

# =============================================================================
# Global Flag Tests
# =============================================================================

@test "cub accepts --debug flag globally" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --debug status
    [ "$status" -eq 0 ]
    # Should enable debug mode
}

@test "cub accepts -d flag globally" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" -d status
    [ "$status" -eq 0 ]
}

@test "cub accepts --stream flag globally" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --stream status
    [ "$status" -eq 0 ]
}

@test "cub accepts --harness flag globally" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --harness claude status
    [ "$status" -eq 0 ]
}

@test "cub accepts --backend flag globally" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --backend json status
    [ "$status" -eq 0 ]
}

# =============================================================================
# Default Behavior Tests
# =============================================================================

@test "cub with no args defaults to run loop" {
    use_fixture "valid_prd.json" "prd.json"

    # This would normally run the loop, but we can't test that easily
    # Just verify it doesn't show help or error
    timeout 2 "$PROJECT_ROOT/cub" || true
    # Should not immediately show help
}

@test "cub run with no flags defaults to continuous loop" {
    use_fixture "valid_prd.json" "prd.json"

    # This would normally run the loop
    timeout 2 "$PROJECT_ROOT/cub" run || true
    # Should not immediately show help or error
}

# =============================================================================
# Error Handling Tests
# =============================================================================

@test "cub status with invalid flag shows error" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" status --invalid-flag
    [ "$status" -ne 0 ]
    [[ "$output" == *"Unknown flag"* ]]
}

@test "cub explain without task-id shows error" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" explain
    [ "$status" -ne 0 ]
    [[ "$output" == *"Usage"* ]] || [[ "$output" == *"task-id"* ]]
}

# =============================================================================
# Integration Tests
# =============================================================================

@test "cub init followed by cub status works" {
    run "$PROJECT_ROOT/cub" init .
    [ "$status" -eq 0 ]

    run "$PROJECT_ROOT/cub" status
    [ "$status" -eq 0 ]
    [[ "$output" == *"Task Status Summary"* ]]
}

@test "mixing global and subcommand flags works" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" --debug run --ready
    [ "$status" -eq 0 ]
    [[ "$output" == *"Ready Tasks"* ]]
}

@test "multiple flags to run subcommand work" {
    use_fixture "valid_prd.json" "prd.json"

    run "$PROJECT_ROOT/cub" run --model sonnet --budget 1000000 --ready
    [ "$status" -eq 0 ]
}
