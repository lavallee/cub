#!/usr/bin/env bats

# Test suite for cub doctor command

# Load the test helper
load test_helper

# Setup function runs before each test
setup() {
    # Create temp directory for test
    TEST_DIR="${BATS_TMPDIR}/doctor_test_$$"
    mkdir -p "$TEST_DIR"
    cd "$TEST_DIR"

    # Initialize a git repo for testing
    git init -q
    git config user.email "test@example.com"
    git config user.name "Test User"

    # Create initial commit so we have a HEAD
    echo "initial" > README.md
    git add README.md
    git commit -q -m "Initial commit"

    # Source libraries
    source "${PROJECT_ROOT}/lib/git.sh"
}

# Teardown function runs after each test
teardown() {
    cd /
    rm -rf "$TEST_DIR" 2>/dev/null || true
}

# ============================================================================
# git_categorize_file tests
# ============================================================================

@test "git_categorize_file returns 'session' for progress.txt" {
    run git_categorize_file "progress.txt"
    [[ $status -eq 0 ]]
    [[ "$output" == "session" ]]
}

@test "git_categorize_file returns 'session' for fix_plan.md" {
    run git_categorize_file "fix_plan.md"
    [[ $status -eq 0 ]]
    [[ "$output" == "session" ]]
}

@test "git_categorize_file returns 'cruft' for .DS_Store" {
    run git_categorize_file ".DS_Store"
    [[ $status -eq 0 ]]
    [[ "$output" == "cruft" ]]
}

@test "git_categorize_file returns 'cruft' for .bak files" {
    run git_categorize_file "file.bak"
    [[ $status -eq 0 ]]
    [[ "$output" == "cruft" ]]
}

@test "git_categorize_file returns 'cruft' for .tmp files" {
    run git_categorize_file "temp.tmp"
    [[ $status -eq 0 ]]
    [[ "$output" == "cruft" ]]
}

@test "git_categorize_file returns 'cruft' for __pycache__" {
    run git_categorize_file "__pycache__/module.pyc"
    [[ $status -eq 0 ]]
    [[ "$output" == "cruft" ]]
}

@test "git_categorize_file returns 'source' for .ts files" {
    run git_categorize_file "src/component.ts"
    [[ $status -eq 0 ]]
    [[ "$output" == "source" ]]
}

@test "git_categorize_file returns 'source' for .py files" {
    run git_categorize_file "app/main.py"
    [[ $status -eq 0 ]]
    [[ "$output" == "source" ]]
}

@test "git_categorize_file returns 'source' for .sh files" {
    run git_categorize_file "scripts/build.sh"
    [[ $status -eq 0 ]]
    [[ "$output" == "source" ]]
}

@test "git_categorize_file returns 'source' for .md files (not session)" {
    run git_categorize_file "README.md"
    [[ $status -eq 0 ]]
    [[ "$output" == "source" ]]
}

@test "git_categorize_file returns 'config' for .env files" {
    run git_categorize_file ".env"
    [[ $status -eq 0 ]]
    [[ "$output" == "config" ]]
}

@test "git_categorize_file returns 'config' for .env.local" {
    run git_categorize_file ".env.local"
    [[ $status -eq 0 ]]
    [[ "$output" == "config" ]]
}

@test "git_categorize_file returns 'unknown' for unrecognized files" {
    run git_categorize_file "random.xyz"
    [[ $status -eq 0 ]]
    [[ "$output" == "unknown" ]]
}

# ============================================================================
# git_categorize_changes tests
# ============================================================================

@test "git_categorize_changes returns empty categories when repo is clean" {
    run git_categorize_changes
    [[ $status -eq 0 ]]

    local session_count source_count cruft_count
    session_count=$(echo "$output" | jq '.session | length')
    source_count=$(echo "$output" | jq '.source | length')
    cruft_count=$(echo "$output" | jq '.cruft | length')

    [[ "$session_count" -eq 0 ]]
    [[ "$source_count" -eq 0 ]]
    [[ "$cruft_count" -eq 0 ]]
}

@test "git_categorize_changes categorizes session files correctly" {
    echo "test" > progress.txt

    run git_categorize_changes
    [[ $status -eq 0 ]]

    local session_count
    session_count=$(echo "$output" | jq '.session | length')
    [[ "$session_count" -eq 1 ]]

    local first_file
    first_file=$(echo "$output" | jq -r '.session[0]')
    [[ "$first_file" == "progress.txt" ]]
}

@test "git_categorize_changes categorizes source files correctly" {
    mkdir -p src
    echo "const x = 1;" > src/app.ts

    run git_categorize_changes
    [[ $status -eq 0 ]]

    local source_count
    source_count=$(echo "$output" | jq '.source | length')
    [[ "$source_count" -eq 1 ]]

    local first_file
    first_file=$(echo "$output" | jq -r '.source[0]')
    [[ "$first_file" == "src/app.ts" ]]
}

@test "git_categorize_changes categorizes cruft files correctly" {
    touch .DS_Store

    run git_categorize_changes
    [[ $status -eq 0 ]]

    local cruft_count
    cruft_count=$(echo "$output" | jq '.cruft | length')
    [[ "$cruft_count" -eq 1 ]]

    local first_file
    first_file=$(echo "$output" | jq -r '.cruft[0]')
    [[ "$first_file" == ".DS_Store" ]]
}

@test "git_categorize_changes handles multiple files in different categories" {
    # Create files in different categories
    echo "progress" > progress.txt
    mkdir -p src
    echo "code" > src/main.py
    touch .DS_Store

    run git_categorize_changes
    [[ $status -eq 0 ]]

    local session_count source_count cruft_count
    session_count=$(echo "$output" | jq '.session | length')
    source_count=$(echo "$output" | jq '.source | length')
    cruft_count=$(echo "$output" | jq '.cruft | length')

    [[ "$session_count" -eq 1 ]]
    [[ "$source_count" -eq 1 ]]
    [[ "$cruft_count" -eq 1 ]]
}

@test "git_categorize_changes excludes .cub directory" {
    mkdir -p .cub
    echo "artifact" > .cub/test.log

    run git_categorize_changes
    [[ $status -eq 0 ]]

    # Should not include .cub files
    local total
    total=$(echo "$output" | jq '[.session, .source, .cruft, .config, .unknown] | add | length')
    [[ "$total" -eq 0 ]]
}

@test "git_categorize_changes excludes .beads directory" {
    mkdir -p .beads
    echo "beads data" > .beads/issues.jsonl

    run git_categorize_changes
    [[ $status -eq 0 ]]

    # Should not include .beads files
    local total
    total=$(echo "$output" | jq '[.session, .source, .cruft, .config, .unknown] | add | length')
    [[ "$total" -eq 0 ]]
}

# ============================================================================
# git_list_changes_with_status tests
# ============================================================================

@test "git_list_changes_with_status returns empty for clean repo" {
    run git_list_changes_with_status
    [[ $status -eq 0 ]]
    [[ -z "$output" ]]
}

@test "git_list_changes_with_status includes modified files" {
    echo "modified" > README.md

    run git_list_changes_with_status
    [[ $status -eq 0 ]]
    [[ "$output" == *"README.md"* ]]
}

@test "git_list_changes_with_status includes untracked files" {
    echo "new" > newfile.txt

    run git_list_changes_with_status
    [[ $status -eq 0 ]]
    [[ "$output" == *"newfile.txt"* ]]
}

# ============================================================================
# Config validation tests
# ============================================================================

@test "_doctor_validate_json accepts valid JSON" {
    echo '{"test": "value"}' > test.json

    source "${PROJECT_ROOT}/lib/cmd_doctor.sh"
    run _doctor_validate_json test.json
    [[ $status -eq 0 ]]
}

@test "_doctor_validate_json rejects invalid JSON" {
    echo '{invalid json}' > test.json

    source "${PROJECT_ROOT}/lib/cmd_doctor.sh"
    run _doctor_validate_json test.json
    [[ $status -ne 0 ]]
}

@test "_doctor_validate_json accepts empty object" {
    echo '{}' > test.json

    source "${PROJECT_ROOT}/lib/cmd_doctor.sh"
    run _doctor_validate_json test.json
    [[ $status -eq 0 ]]
}

@test "_doctor_validate_json accepts arrays" {
    echo '[]' > test.json

    source "${PROJECT_ROOT}/lib/cmd_doctor.sh"
    run _doctor_validate_json test.json
    [[ $status -eq 0 ]]
}

@test "_doctor_check_deprecated_options detects deprecated fields" {
    cat > config.json <<'EOF'
{
  "harness.priority": "claude",
  "budget.tokens": 100000
}
EOF

    local deprecated=$(cat <<'EOF'
{
  "harness.priority": "Use 'harness.default' instead",
  "budget.tokens": "Use 'budget.max_tokens_per_task' instead"
}
EOF
)

    source "${PROJECT_ROOT}/lib/cmd_doctor.sh"
    run _doctor_check_deprecated_options config.json "$deprecated"
    [[ $status -ne 0 ]]
    [[ "$output" == *"harness.priority"* ]]
    [[ "$output" == *"budget.tokens"* ]]
}

@test "_doctor_check_deprecated_options passes clean config" {
    cat > config.json <<'EOF'
{
  "harness": {
    "default": "claude"
  },
  "budget": {
    "max_tokens_per_task": 100000
  }
}
EOF

    local deprecated=$(cat <<'EOF'
{
  "harness.priority": "Use 'harness.default' instead",
  "budget.tokens": "Use 'budget.max_tokens_per_task' instead"
}
EOF
)

    source "${PROJECT_ROOT}/lib/cmd_doctor.sh"
    run _doctor_check_deprecated_options config.json "$deprecated"
    [[ $status -eq 0 ]]
}

@test "_doctor_check_deprecated_options finds single deprecated option" {
    cat > config.json <<'EOF'
{
  "state.clean": true
}
EOF

    local deprecated=$(cat <<'EOF'
{
  "state.clean": "Use 'state.require_clean' instead"
}
EOF
)

    source "${PROJECT_ROOT}/lib/cmd_doctor.sh"
    run _doctor_check_deprecated_options config.json "$deprecated"
    [[ $status -ne 0 ]]
    [[ "$output" == *"state.clean"* ]]
}

@test "_doctor_check_required_fields detects missing fields" {
    cat > config.json <<'EOF'
{
  "harness": "claude"
}
EOF

    local required='["harness", "budget", "state"]'

    source "${PROJECT_ROOT}/lib/cmd_doctor.sh"
    run _doctor_check_required_fields config.json "$required"
    [[ $status -ne 0 ]]
    [[ "$output" == *"budget"* ]]
    [[ "$output" == *"state"* ]]
}

@test "_doctor_check_required_fields passes with all required fields" {
    cat > config.json <<'EOF'
{
  "harness": "claude",
  "budget": {
    "max_tokens_per_task": 100000
  },
  "state": {
    "require_clean": true
  }
}
EOF

    local required='["harness", "budget", "state"]'

    source "${PROJECT_ROOT}/lib/cmd_doctor.sh"
    run _doctor_check_required_fields config.json "$required"
    [[ $status -eq 0 ]]
}
