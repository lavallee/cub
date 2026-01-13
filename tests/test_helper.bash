#!/usr/bin/env bash
#
# test_helper.bash - Common setup and utilities for cub tests
#

# Get absolute path to project root
export PROJECT_ROOT="$(cd "$(dirname "$BATS_TEST_DIRNAME")" && pwd)"
export LIB_DIR="$PROJECT_ROOT/lib"
export FIXTURES_DIR="$BATS_TEST_DIRNAME/fixtures"

# Setup function called before each test
setup_test_dir() {
    # Create a temp directory for this test
    TEST_DIR="$(mktemp -d)"
    cd "$TEST_DIR"

    # Reset backend state and project directory
    unset CUB_BACKEND
    unset CUB_PROJECT_DIR
    export _TASK_BACKEND=""

    # Create mock harness (claude) for tests that don't actually invoke it
    # This satisfies the dependency check in curb
    MOCK_BIN_DIR="$TEST_DIR/bin"
    mkdir -p "$MOCK_BIN_DIR"
    cat > "$MOCK_BIN_DIR/claude" << 'MOCK_EOF'
#!/usr/bin/env bash
# Mock claude harness for testing
# Simulate auth error if ANTHROPIC_API_KEY is "invalid"
if [[ "${ANTHROPIC_API_KEY:-}" == "invalid" ]]; then
    echo "Error: Invalid API key" >&2
    exit 1
fi
echo "Mock claude: $*"
exit 0
MOCK_EOF
    chmod +x "$MOCK_BIN_DIR/claude"
    export PATH="$MOCK_BIN_DIR:$PATH"
}

# Teardown function to clean up after tests
teardown_test_dir() {
    if [[ -n "$TEST_DIR" && -d "$TEST_DIR" ]]; then
        rm -rf "$TEST_DIR"
    fi
}

# Copy a fixture file to the test directory
use_fixture() {
    local fixture_name="$1"
    local dest_name="${2:-$fixture_name}"

    if [[ -f "$FIXTURES_DIR/$fixture_name" ]]; then
        cp "$FIXTURES_DIR/$fixture_name" "$TEST_DIR/$dest_name"
    else
        echo "Fixture not found: $fixture_name" >&2
        return 1
    fi
}

# Mock a command by creating a function that shadows it
mock_command() {
    local cmd="$1"
    local output="$2"
    local exit_code="${3:-0}"

    eval "${cmd}() { echo '$output'; return $exit_code; }"
    export -f "$cmd"
}

# Assert that a JSON file contains expected value at path
assert_json_equals() {
    local file="$1"
    local jq_path="$2"
    local expected="$3"

    local actual
    actual=$(jq -r "$jq_path" "$file")

    if [[ "$actual" != "$expected" ]]; then
        echo "JSON assertion failed:"
        echo "  Path: $jq_path"
        echo "  Expected: $expected"
        echo "  Actual: $actual"
        return 1
    fi
}

# Assert JSON array length
assert_json_length() {
    local file="$1"
    local jq_path="$2"
    local expected="$3"

    local actual
    actual=$(jq "$jq_path | length" "$file")

    if [[ "$actual" != "$expected" ]]; then
        echo "JSON length assertion failed:"
        echo "  Path: $jq_path"
        echo "  Expected length: $expected"
        echo "  Actual length: $actual"
        return 1
    fi
}

# Create a minimal valid prd.json
create_minimal_prd() {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": []
}
EOF
}

# Create a prd.json with sample tasks
create_sample_prd() {
    cat > prd.json << 'EOF'
{
  "prefix": "test",
  "tasks": [
    {
      "id": "test-0001",
      "title": "First task",
      "type": "task",
      "status": "open",
      "priority": "P2"
    },
    {
      "id": "test-0002",
      "title": "Second task",
      "type": "task",
      "status": "closed",
      "priority": "P1"
    },
    {
      "id": "test-0003",
      "title": "Third task with dependency",
      "type": "task",
      "status": "open",
      "priority": "P0",
      "dependsOn": ["test-0002"]
    }
  ]
}
EOF
}

# Cross-platform permission checking helper
# Returns octal permissions (e.g., "700", "600")
get_permissions() {
    local path="$1"
    if [[ "$(uname)" == "Darwin" ]]; then
        stat -f "%Lp" "$path"
    else
        stat -c "%a" "$path"
    fi
}

# Check if file/dir has expected permissions
# Usage: assert_permissions "/path/to/file" "600"
assert_permissions() {
    local path="$1"
    local expected="$2"
    local actual

    actual=$(get_permissions "$path")
    if [[ "$actual" != "$expected" ]]; then
        echo "Permission assertion failed:"
        echo "  Path: $path"
        echo "  Expected: $expected"
        echo "  Actual: $actual"
        return 1
    fi
}
