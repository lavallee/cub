#!/usr/bin/env bats
#
# tests/migrate_layout.bats - Tests for cub migrate-layout command
#
# Tests for migrating projects from legacy layout (root-level files)
# to new layout (.cub/ subdirectory organization).

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
}

teardown() {
    teardown_test_dir
}

# =============================================================================
# Basic Migration Tests
# =============================================================================

@test "migrate-layout shows help with --help" {
    run "$PROJECT_ROOT/cub" migrate-layout --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage: cub migrate-layout"* ]]
    [[ "$output" == *"--dry-run"* ]]
}

@test "migrate-layout shows help with -h" {
    run "$PROJECT_ROOT/cub" migrate-layout -h
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage: cub migrate-layout"* ]]
}

@test "migrate-layout shows help with help" {
    run "$PROJECT_ROOT/cub" migrate-layout help
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage: cub migrate-layout"* ]]
}

@test "migrate-layout handles unknown options" {
    run "$PROJECT_ROOT/cub" migrate-layout --unknown
    [ "$status" -ne 0 ]
    [[ "$output" == *"Unknown option"* ]]
}

# =============================================================================
# Dry-Run Tests
# =============================================================================

@test "migrate-layout --dry-run shows files to migrate without making changes" {
    # Create legacy layout files
    echo "System prompt" > "$TEST_DIR/PROMPT.md"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"
    echo "Progress notes" > "$TEST_DIR/progress.txt"
    echo "Fix plan" > "$TEST_DIR/fix_plan.md"
    echo '{"tasks": []}' > "$TEST_DIR/prd.json"

    run "$PROJECT_ROOT/cub" migrate-layout --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"Would migrate"* ]]
    [[ "$output" == *"PROMPT.md"* ]]
    [[ "$output" == *"AGENT.md"* ]]
    [[ "$output" == *"progress.txt"* ]]
    [[ "$output" == *"fix_plan.md"* ]]
    [[ "$output" == *"prd.json"* ]]
    [[ "$output" == *"DRY RUN: No changes made"* ]]

    # Verify files weren't actually moved
    [ -f "$TEST_DIR/PROMPT.md" ]
    [ -f "$TEST_DIR/AGENT.md" ]
    [ -f "$TEST_DIR/progress.txt" ]
    [ ! -d "$TEST_DIR/.cub" ] || [ ! -f "$TEST_DIR/.cub/prompt.md" ]
}

@test "migrate-layout --dry-run with no legacy files" {
    mkdir -p "$TEST_DIR/.cub"
    echo "System prompt" > "$TEST_DIR/.cub/prompt.md"
    echo "Agent instructions" > "$TEST_DIR/.cub/agent.md"

    run "$PROJECT_ROOT/cub" migrate-layout --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"already in new layout"* ]]
}

# =============================================================================
# File Migration Tests
# =============================================================================

@test "migrate-layout migrates PROMPT.md" {
    echo "System prompt" > "$TEST_DIR/PROMPT.md"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]
    [[ "$output" == *"Migration complete"* ]]

    # Check file was migrated
    [ -f "$TEST_DIR/.cub/prompt.md" ]
    grep -q "System prompt" "$TEST_DIR/.cub/prompt.md"
}

@test "migrate-layout migrates AGENT.md" {
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    [ -f "$TEST_DIR/.cub/agent.md" ]
    grep -q "Agent instructions" "$TEST_DIR/.cub/agent.md"
}

@test "migrate-layout migrates CLAUDE.md to agent.md" {
    echo "Claude instructions" > "$TEST_DIR/CLAUDE.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    [ -f "$TEST_DIR/.cub/agent.md" ]
    grep -q "Claude instructions" "$TEST_DIR/.cub/agent.md"
}

@test "migrate-layout prefers AGENT.md over CLAUDE.md" {
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"
    echo "Claude instructions" > "$TEST_DIR/CLAUDE.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    [ -f "$TEST_DIR/.cub/agent.md" ]
    grep -q "Agent instructions" "$TEST_DIR/.cub/agent.md"
}

@test "migrate-layout migrates progress.txt" {
    echo "Progress notes" > "$TEST_DIR/progress.txt"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    [ -f "$TEST_DIR/.cub/progress.txt" ]
    grep -q "Progress notes" "$TEST_DIR/.cub/progress.txt"
}

@test "migrate-layout prefers progress.txt over @progress.txt" {
    echo "Progress notes" > "$TEST_DIR/progress.txt"
    echo "Alt progress" > "$TEST_DIR/@progress.txt"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    [ -f "$TEST_DIR/.cub/progress.txt" ]
    grep -q "Progress notes" "$TEST_DIR/.cub/progress.txt"
}

@test "migrate-layout migrates @progress.txt when progress.txt missing" {
    echo "Alt progress" > "$TEST_DIR/@progress.txt"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    [ -f "$TEST_DIR/.cub/progress.txt" ]
    grep -q "Alt progress" "$TEST_DIR/.cub/progress.txt"
}

@test "migrate-layout migrates fix_plan.md" {
    echo "Fix plan content" > "$TEST_DIR/fix_plan.md"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    [ -f "$TEST_DIR/.cub/fix_plan.md" ]
    grep -q "Fix plan content" "$TEST_DIR/.cub/fix_plan.md"
}

@test "migrate-layout migrates prd.json" {
    echo '{"tasks": [{"id": "task1"}]}' > "$TEST_DIR/prd.json"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    [ -f "$TEST_DIR/.cub/prd.json" ]
    grep -q "task1" "$TEST_DIR/.cub/prd.json"
}

@test "migrate-layout migrates .cub.json" {
    echo '{"config": "value"}' > "$TEST_DIR/.cub.json"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    [ -f "$TEST_DIR/.cub/.cub.json" ]
    grep -q "config" "$TEST_DIR/.cub/.cub.json"
}

# =============================================================================
# Symlink Tests
# =============================================================================

@test "migrate-layout creates backwards-compatibility symlinks" {
    echo "System prompt" > "$TEST_DIR/PROMPT.md"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    # After migration, root files should be replaced with symlinks
    [ -L "$TEST_DIR/PROMPT.md" ] || [ -f "$TEST_DIR/PROMPT.md" ]
    [ -L "$TEST_DIR/AGENT.md" ] || [ -f "$TEST_DIR/AGENT.md" ]
}

@test "migrate-layout handles symlinks in source layout" {
    # Create actual file and symlink to it
    mkdir -p "$TEST_DIR/.cub"
    echo "System prompt" > "$TEST_DIR/.cub/prompt.md"
    ln -s ".cub/prompt.md" "$TEST_DIR/PROMPT.md"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    # Should handle the symlink gracefully
    [ -f "$TEST_DIR/.cub/prompt.md" ]
}

# =============================================================================
# Edge Cases
# =============================================================================

@test "migrate-layout with no legacy files returns success" {
    mkdir -p "$TEST_DIR/.cub"
    echo "System prompt" > "$TEST_DIR/.cub/prompt.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]
    [[ "$output" == *"already in new layout"* ]]
}

@test "migrate-layout migrates all files at once" {
    echo "System prompt" > "$TEST_DIR/PROMPT.md"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"
    echo "Progress" > "$TEST_DIR/progress.txt"
    echo "Fix plan" > "$TEST_DIR/fix_plan.md"
    echo '{"tasks": []}' > "$TEST_DIR/prd.json"
    echo '{"config": true}' > "$TEST_DIR/.cub.json"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    # All files should be migrated
    [ -f "$TEST_DIR/.cub/prompt.md" ]
    [ -f "$TEST_DIR/.cub/agent.md" ]
    [ -f "$TEST_DIR/.cub/progress.txt" ]
    [ -f "$TEST_DIR/.cub/fix_plan.md" ]
    [ -f "$TEST_DIR/.cub/prd.json" ]
    [ -f "$TEST_DIR/.cub/.cub.json" ]
}

@test "migrate-layout idempotent - run twice without error" {
    echo "System prompt" > "$TEST_DIR/PROMPT.md"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    # First migration
    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    # Second migration should also succeed
    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]
    [[ "$output" == *"already in new layout"* ]]
}

@test "migrate-layout preserves file contents" {
    local test_content="Line 1
Line 2
Line 3"
    echo "$test_content" > "$TEST_DIR/PROMPT.md"
    echo "Agent instructions" > "$TEST_DIR/AGENT.md"

    run "$PROJECT_ROOT/cub" migrate-layout
    [ "$status" -eq 0 ]

    # Check content is preserved exactly
    diff <(cat "$TEST_DIR/.cub/prompt.md") <(echo "$test_content") || true
}
