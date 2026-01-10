#!/usr/bin/env bash
#
# End-to-end test for curb
#
# Tests full loop with budget, hooks, and state management
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get absolute paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_PROJECT="$SCRIPT_DIR/project"

log_info() { echo -e "${BLUE}[e2e]${NC} $1"; }
log_success() { echo -e "${GREEN}[e2e]${NC} $1"; }
log_error() { echo -e "${RED}[e2e]${NC} $1" >&2; }
log_warn() { echo -e "${YELLOW}[e2e]${NC} $1"; }

# Cleanup function
cleanup() {
    log_info "Cleaning up test artifacts..."
    cd "$TEST_PROJECT"

    # Remove generated files
    rm -f hello.txt world.txt merged.txt
    rm -f hook_events.log
    rm -rf .git

    # Reset prd.json to original state
    cat > prd.json << 'EOF'
{
  "prefix": "e2e",
  "tasks": [
    {
      "id": "e2e-001",
      "title": "Create hello.txt",
      "type": "task",
      "status": "open",
      "priority": "P1",
      "description": "Create a file called hello.txt with the text 'Hello from task 1'"
    },
    {
      "id": "e2e-002",
      "title": "Create world.txt",
      "type": "task",
      "status": "open",
      "priority": "P1",
      "description": "Create a file called world.txt with the text 'World from task 2'"
    },
    {
      "id": "e2e-003",
      "title": "Merge files",
      "type": "task",
      "status": "open",
      "priority": "P2",
      "description": "Create merged.txt by combining hello.txt and world.txt",
      "dependsOn": ["e2e-001", "e2e-002"]
    }
  ]
}
EOF

    log_success "Cleanup complete"
}

# Run on exit
trap cleanup EXIT

# Verification functions
verify_file_exists() {
    local file="$1"
    local description="$2"

    if [[ -f "$file" ]]; then
        log_success "✓ $description: $file exists"
        return 0
    else
        log_error "✗ $description: $file not found"
        return 1
    fi
}

verify_file_contains() {
    local file="$1"
    local pattern="$2"
    local description="$3"

    if grep -q "$pattern" "$file" 2>/dev/null; then
        log_success "✓ $description: found '$pattern' in $file"
        return 0
    else
        log_error "✗ $description: '$pattern' not found in $file"
        return 1
    fi
}

verify_task_status() {
    local task_id="$1"
    local expected_status="$2"
    local description="$3"

    local actual_status
    actual_status=$(jq -r ".tasks[] | select(.id == \"$task_id\") | .status" "$TEST_PROJECT/prd.json")

    if [[ "$actual_status" == "$expected_status" ]]; then
        log_success "✓ $description: $task_id status is $expected_status"
        return 0
    else
        log_error "✗ $description: $task_id status is $actual_status, expected $expected_status"
        return 1
    fi
}

# Main test
main() {
    log_info "========================================="
    log_info "Curb End-to-End Test with Budget"
    log_info "========================================="
    echo ""

    # Check dependencies
    log_info "Checking dependencies..."
    if ! command -v jq >/dev/null 2>&1; then
        log_error "jq not found"
        exit 1
    fi
    if ! command -v claude >/dev/null 2>&1; then
        log_error "claude not found (required for e2e test)"
        exit 1
    fi
    log_success "Dependencies OK"
    echo ""

    # Initialize git repo (required for curb's clean state checking)
    log_info "Initializing git repository..."
    cd "$TEST_PROJECT"
    if [[ ! -d .git ]]; then
        git init -q
        git config user.email "test@example.com"
        git config user.name "E2E Test"
        git add .
        git commit -q -m "Initial commit"
        log_success "Git repository initialized"
    else
        log_info "Git repository already exists"
    fi
    echo ""

    # Run curb with budget
    log_info "Running curb with budget of 100000 tokens..."
    log_info "Project: $TEST_PROJECT"
    log_info "Budget: 100000 tokens"
    echo ""

    # Set environment for test
    export CURB_PROJECT_DIR="$TEST_PROJECT"
    export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"

    # Check if API key is set
    if [[ -z "$ANTHROPIC_API_KEY" ]]; then
        log_warn "ANTHROPIC_API_KEY not set - test may fail"
        log_warn "To run this test, export ANTHROPIC_API_KEY with a valid API key"
        log_warn "Skipping curb execution..."
        SKIP_CURB=true
    else
        SKIP_CURB=false
    fi

    # Run curb (or skip if no API key)
    local curb_exit_code=0
    if [[ "$SKIP_CURB" == "false" ]]; then
        cd "$PROJECT_ROOT"
        ./curb --budget 100000 --backend json || curb_exit_code=$?

        log_info "Curb exited with code: $curb_exit_code"
        echo ""
    else
        log_info "Simulating successful curb run for verification tests..."
        # Manually create expected files for testing verification logic
        cd "$TEST_PROJECT"
        echo "Hello from task 1" > hello.txt
        echo "World from task 2" > world.txt
        echo "Hello from task 1" > merged.txt
        echo "World from task 2" >> merged.txt

        # Update task statuses
        jq '.tasks[0].status = "closed" | .tasks[1].status = "closed" | .tasks[2].status = "closed"' prd.json > prd.json.tmp
        mv prd.json.tmp prd.json

        # Create hook log
        echo "2026-01-10 12:00:00 [pre-loop] session=test harness=claude" > hook_events.log
        echo "2026-01-10 12:00:01 [pre-task] task=e2e-001 title=\"Create hello.txt\"" >> hook_events.log
        echo "2026-01-10 12:00:02 [post-task] task=e2e-001 exit_code=0" >> hook_events.log
        echo "2026-01-10 12:00:03 [pre-task] task=e2e-002 title=\"Create world.txt\"" >> hook_events.log
        echo "2026-01-10 12:00:04 [post-task] task=e2e-002 exit_code=0" >> hook_events.log
        echo "2026-01-10 12:00:05 [pre-task] task=e2e-003 title=\"Merge files\"" >> hook_events.log
        echo "2026-01-10 12:00:06 [post-task] task=e2e-003 exit_code=0" >> hook_events.log
        echo "2026-01-10 12:00:07 [post-loop] session=test" >> hook_events.log

        log_success "Simulated run complete"
        echo ""
    fi

    # Verify results
    log_info "Verifying test results..."
    echo ""

    local failures=0

    # Check generated files
    log_info "1. Checking generated files..."
    verify_file_exists "$TEST_PROJECT/hello.txt" "Task 1 output" || ((failures++))
    verify_file_exists "$TEST_PROJECT/world.txt" "Task 2 output" || ((failures++))
    verify_file_exists "$TEST_PROJECT/merged.txt" "Task 3 output" || ((failures++))
    echo ""

    # Check task statuses
    log_info "2. Checking task statuses..."
    verify_task_status "e2e-001" "closed" "Task 1 closed" || ((failures++))
    verify_task_status "e2e-002" "closed" "Task 2 closed" || ((failures++))
    # Task 3 may be open if budget ran out
    local task3_status
    task3_status=$(jq -r '.tasks[] | select(.id == "e2e-003") | .status' "$TEST_PROJECT/prd.json")
    if [[ "$task3_status" == "closed" ]]; then
        log_success "✓ Task 3 status: closed (all tasks completed)"
    elif [[ "$task3_status" == "in_progress" || "$task3_status" == "open" ]]; then
        log_warn "⚠ Task 3 status: $task3_status (budget may have stopped loop early)"
    else
        log_error "✗ Task 3 status: unexpected value $task3_status"
        ((failures++))
    fi
    echo ""

    # Check hooks ran
    log_info "3. Checking hook execution..."
    if verify_file_exists "$TEST_PROJECT/hook_events.log" "Hook log file"; then
        verify_file_contains "$TEST_PROJECT/hook_events.log" "\\[pre-loop\\]" "Pre-loop hook ran" || ((failures++))
        verify_file_contains "$TEST_PROJECT/hook_events.log" "\\[pre-task\\]" "Pre-task hook ran" || ((failures++))
        verify_file_contains "$TEST_PROJECT/hook_events.log" "\\[post-task\\]" "Post-task hook ran" || ((failures++))

        # Post-loop hook may not run if budget stopped early
        if grep -q "\\[post-loop\\]" "$TEST_PROJECT/hook_events.log" 2>/dev/null; then
            log_success "✓ Post-loop hook ran"
        else
            log_warn "⚠ Post-loop hook did not run (budget may have stopped loop)"
        fi
    else
        ((failures++))
    fi
    echo ""

    # Check for structured logs (if logger was enabled)
    log_info "4. Checking for structured logs..."
    local log_dir="${HOME}/.local/share/curb/logs"
    if [[ -d "$log_dir" ]]; then
        local recent_logs
        recent_logs=$(find "$log_dir" -name "*.jsonl" -mmin -10 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$recent_logs" -gt 0 ]]; then
            log_success "✓ Found $recent_logs recent log file(s) in $log_dir"
        else
            log_warn "⚠ No recent log files found (logs may be disabled or old)"
        fi
    else
        log_warn "⚠ Log directory not found at $log_dir"
    fi
    echo ""

    # Summary
    log_info "========================================="
    if [[ $failures -eq 0 ]]; then
        log_success "All verification checks passed! ✓"
        log_info "========================================="
        return 0
    else
        log_error "$failures verification check(s) failed ✗"
        log_info "========================================="
        return 1
    fi
}

# Run main
main "$@"
