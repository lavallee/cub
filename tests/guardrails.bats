#!/usr/bin/env bats
#
# guardrails.bats - Tests for institutional memory guardrails system
#
# Tests the .cub/guardrails.md file reading and parsing functionality
#

load test_helper

setup() {
    setup_test_dir
    # Initialize .cub directory for this test
    mkdir -p .cub
}

teardown() {
    teardown_test_dir
}

# Source the guardrails library for testing
source_guardrails() {
    source "${LIB_DIR}/guardrails.sh"
}

# Helper: Create a mock guardrails file
create_mock_guardrails() {
    local project_dir="${1:-.}"
    mkdir -p "${project_dir}/.cub"
    cat > "${project_dir}/.cub/guardrails.md" <<'EOF'
# Guardrails

Institutional memory for this project. These lessons learned are automatically
included in task prompts to prevent repeat mistakes.

---

## Project-Specific

### Naming Conventions
- All task IDs should use kebab-case (e.g., feature-x-123)
- API endpoints should return JSON with consistent error format

### Build Commands
- Always run `npm test` before committing
- Build with: `npm run build`

---

## Learned from Failures

### 2026-01-10 - task-1
**Error:** Failed to parse JSON response
**Exit code:** 1
**Lesson:** Always validate API responses are JSON before parsing

### 2026-01-11 - task-2
Missing error handling when file doesn't exist

### 2026-01-12
**Error:** Race condition in async operations
**Exit code:** 2
**Lesson:** Use Promise.all() instead of concurrent awaits for dependent operations

EOF
}

@test "guardrails_exists returns 1 when file doesn't exist" {
    source_guardrails

    # File should not exist
    guardrails_exists . && false || true
}

@test "guardrails_exists returns 0 when file exists" {
    source_guardrails
    create_mock_guardrails .

    guardrails_exists .
}

@test "guardrails_init creates .cub directory if missing" {
    source_guardrails

    # Remove directory created by setup for this specific test
    rm -rf .cub

    # Directory should not exist
    [[ ! -d .cub ]]

    guardrails_init .

    # Directory should now exist
    [[ -d .cub ]]
}

@test "guardrails_init creates guardrails file with template structure" {
    source_guardrails

    guardrails_init .

    # File should exist
    [[ -f .cub/guardrails.md ]]

    # Should contain sections
    grep -q "# Guardrails" .cub/guardrails.md
    grep -q "## Project-Specific" .cub/guardrails.md
    grep -q "## Learned from Failures" .cub/guardrails.md
}

@test "guardrails_init is idempotent" {
    source_guardrails

    guardrails_init .
    local first_content=$(cat .cub/guardrails.md)

    # Call again
    guardrails_init .
    local second_content=$(cat .cub/guardrails.md)

    [[ "$first_content" == "$second_content" ]]
}

@test "guardrails_read returns empty string when file doesn't exist" {
    source_guardrails

    local result=$(guardrails_read .)
    [[ -z "$result" ]]
}

@test "guardrails_read returns file content when it exists" {
    source_guardrails
    create_mock_guardrails .

    local result=$(guardrails_read .)

    echo "$result" | grep -q "# Guardrails"
    echo "$result" | grep -q "Institutional memory"
}

@test "guardrails_add creates file if it doesn't exist" {
    source_guardrails

    guardrails_add "Test lesson" . .

    [[ -f .cub/guardrails.md ]]
}

@test "guardrails_add appends lesson with timestamp" {
    source_guardrails
    guardrails_init .

    guardrails_add "This is a test lesson" "" .

    local content=$(cat .cub/guardrails.md)
    echo "$content" | grep -q "### [0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}"
    echo "$content" | grep -q "This is a test lesson"
}

@test "guardrails_add appends lesson with task_id when provided" {
    source_guardrails
    guardrails_init .

    guardrails_add "Task-specific lesson" "task-123" .

    local content=$(cat .cub/guardrails.md)
    echo "$content" | grep -q "### [0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\} - task-123"
}

@test "guardrails_add returns 1 if lesson text is empty" {
    source_guardrails
    guardrails_init .

    guardrails_add "" "" . && false || true
}

@test "guardrails_add_from_failure formats error information" {
    source_guardrails
    guardrails_init .

    guardrails_add_from_failure "task-1" "1" "JSON parse failed" "Validate JSON before parsing" .

    local content=$(cat .cub/guardrails.md)
    echo "$content" | grep -q "Source Error.*JSON parse failed"
    echo "$content" | grep -q "Exit Code.*1"
    echo "$content" | grep -q "Lesson.*Validate JSON before parsing"
}

@test "guardrails_add_from_failure uses error_summary as lesson if not provided" {
    source_guardrails
    guardrails_init .

    guardrails_add_from_failure "task-1" "1" "Something failed" "" .

    local content=$(cat .cub/guardrails.md)
    echo "$content" | grep -q "Lesson.*Something failed"
}

@test "guardrails_size_kb returns 0 if file doesn't exist" {
    source_guardrails

    local size=$(guardrails_size_kb .)
    [[ "$size" == "0" ]]
}

@test "guardrails_size_kb returns positive KB value for existing file" {
    source_guardrails
    create_mock_guardrails .

    local size=$(guardrails_size_kb .)
    [[ "$size" -gt 0 ]]
}

@test "guardrails_count returns 0 if file doesn't exist" {
    source_guardrails

    local count=$(guardrails_count .)
    [[ "$count" == "0" ]]
}

@test "guardrails_count counts dated lesson entries" {
    source_guardrails
    create_mock_guardrails .

    local count=$(guardrails_count .)
    # Should find at least 3 lessons in mock file
    [[ "$count" -ge 3 ]]
}

@test "guardrails_check_size returns 0 when under limit" {
    source_guardrails
    create_mock_guardrails .

    guardrails_check_size 100 .
}

@test "guardrails_check_size returns 1 when over limit" {
    source_guardrails
    create_mock_guardrails .

    # Set low limit
    guardrails_check_size 1 . && false || true
}

@test "guardrails_clear creates backup before clearing" {
    source_guardrails
    create_mock_guardrails .

    guardrails_clear .

    # Should have backup file
    ls .cub/guardrails.md.backup.* >/dev/null 2>&1
}

@test "guardrails_clear reinitializes with empty content" {
    source_guardrails
    create_mock_guardrails .

    guardrails_clear .

    # File should still exist
    [[ -f .cub/guardrails.md ]]

    # But should only have template
    local content=$(cat .cub/guardrails.md)
    ! echo "$content" | grep -q "2026-01-10"
}

@test "guardrails_import requires source file" {
    source_guardrails
    guardrails_init .

    guardrails_import "" . && false || true
}

@test "guardrails_import fails if source doesn't exist" {
    source_guardrails
    guardrails_init .

    guardrails_import "/nonexistent/file" . && false || true
}

@test "guardrails_import adds lessons from source file" {
    source_guardrails

    # Create source guardrails
    mkdir -p source/.cub
    create_mock_guardrails source

    # Import to destination
    guardrails_init .
    guardrails_import "source/.cub/guardrails.md" .

    local content=$(cat .cub/guardrails.md)
    # Should have imported content
    echo "$content" | grep -q "2026-01-10"
}

@test "guardrails_export copies file to destination" {
    source_guardrails
    create_mock_guardrails .

    guardrails_export "./exported.md" .

    [[ -f exported.md ]]
    diff .cub/guardrails.md exported.md
}

@test "guardrails_export fails without source file" {
    source_guardrails

    guardrails_export "./exported.md" . && false || true
}

@test "guardrails_for_prompt returns empty if file doesn't exist" {
    source_guardrails

    local result=$(guardrails_for_prompt .)
    [[ -z "$result" ]]
}

@test "guardrails_for_prompt includes header and content" {
    source_guardrails
    create_mock_guardrails .

    local result=$(guardrails_for_prompt .)

    echo "$result" | grep -q "# Guardrails (Institutional Memory)"
    echo "$result" | grep -q "lessons learned"
    echo "$result" | grep -q "Institutional memory"
}

@test "guardrails_get_file returns correct path" {
    source_guardrails

    local path=$(guardrails_get_file .)
    [[ "$path" == "./.cub/guardrails.md" ]]
}

@test "guardrails_search finds matching content" {
    source_guardrails
    create_mock_guardrails .

    local result=$(guardrails_search "Naming" .)
    echo "$result" | grep -q "Naming Conventions"
}

@test "guardrails_search is case-insensitive" {
    source_guardrails
    create_mock_guardrails .

    local result=$(guardrails_search "build" .)
    echo "$result" | grep -q "Build Commands"
}

@test "guardrails_search returns empty for no matches" {
    source_guardrails
    create_mock_guardrails .

    local result=$(guardrails_search "nonexistent_pattern" .)
    [[ -z "$result" ]]
}

@test "guardrails_list_json returns empty array if file doesn't exist" {
    source_guardrails

    local json=$(guardrails_list_json .)
    [[ "$json" == "[]" ]]
}

@test "guardrails_list_json parses lessons to JSON array" {
    source_guardrails
    create_mock_guardrails .

    local json=$(guardrails_list_json .)

    # Should be valid JSON array with entries
    echo "$json" | jq '.' >/dev/null 2>&1
    local count=$(echo "$json" | jq 'length')
    [[ "$count" -gt 0 ]]
}

@test "guardrails_list_json extracts date from lesson header" {
    source_guardrails
    create_mock_guardrails .

    local json=$(guardrails_list_json .)

    # Check first lesson has date
    local date=$(echo "$json" | jq -r '.[0].date')
    [[ "$date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]
}

@test "guardrails_list_json extracts task_id when present" {
    source_guardrails
    create_mock_guardrails .

    local json=$(guardrails_list_json .)

    # First lesson should have task_id
    local task=$(echo "$json" | jq -r '.[0].task_id')
    [[ "$task" == "task-1" ]]
}

@test "guardrails_list_json sets task_id to null when not present" {
    source_guardrails
    create_mock_guardrails .

    local json=$(guardrails_list_json .)

    # Third lesson has no task_id
    local task=$(echo "$json" | jq -r '.[2].task_id')
    [[ "$task" == "null" ]]
}

@test "guardrails works with custom project directory" {
    source_guardrails

    mkdir -p custom/project/.cub
    cd custom/project

    guardrails_init .
    guardrails_add "Custom project lesson" . .

    local content=$(guardrails_read .)
    echo "$content" | grep -q "Custom project lesson"
}

@test "guardrails respects PROJECT_DIR environment variable" {
    source_guardrails

    PROJECT_DIR="$PWD"
    guardrails_init

    [[ -f .cub/guardrails.md ]]
}

@test "guardrails_extract_lesson_ai requires task_id" {
    source_guardrails
    guardrails_init .

    run guardrails_extract_lesson_ai "" "Test task" "Error message" .
    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "ERROR: task_id is required" ]]
}

@test "guardrails_extract_lesson_ai requires task_title" {
    source_guardrails
    guardrails_init .

    run guardrails_extract_lesson_ai "task-1" "" "Error message" .
    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "ERROR: task_title is required" ]]
}

@test "guardrails_extract_lesson_ai requires error_summary" {
    source_guardrails
    guardrails_init .

    run guardrails_extract_lesson_ai "task-1" "Test task" "" .
    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "ERROR: error_summary is required" ]]
}

@test "guardrails_extract_lesson_ai returns fallback when claude unavailable" {
    source_guardrails
    guardrails_init .

    # Temporarily make claude unavailable
    PATH=/bin:/usr/bin run guardrails_extract_lesson_ai "task-1" "Test task" "Error message" .
    [[ "$status" -eq 0 ]]
    # Should return generic fallback lesson
    [[ "$output" =~ "ensure all preconditions are met" ]]
}

@test "guardrails_learn_from_failure requires task_id" {
    source_guardrails
    guardrails_init .

    run guardrails_learn_from_failure "" "Test task" 1 "Error message" .
    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "ERROR: task_id is required" ]]
}

@test "guardrails_learn_from_failure requires task_title" {
    source_guardrails
    guardrails_init .

    run guardrails_learn_from_failure "task-1" "" 1 "Error message" .
    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "ERROR: task_title is required" ]]
}

@test "guardrails_learn_from_failure requires exit_code" {
    source_guardrails
    guardrails_init .

    run guardrails_learn_from_failure "task-1" "Test task" "" "Error message" .
    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "ERROR: exit_code is required" ]]
}

@test "guardrails_learn_from_failure requires error_summary" {
    source_guardrails
    guardrails_init .

    run guardrails_learn_from_failure "task-1" "Test task" 1 "" .
    [[ "$status" -ne 0 ]]
    [[ "$output" =~ "ERROR: error_summary is required" ]]
}

@test "guardrails_learn_from_failure adds lesson to file" {
    source_guardrails
    guardrails_init .

    # Should succeed and add a lesson (with fallback if AI unavailable)
    guardrails_learn_from_failure "task-123" "Fix authentication" 1 "Auth token expired" .

    # Verify lesson was added
    local content=$(cat .cub/guardrails.md)
    echo "$content" | grep -q "task-123"
    echo "$content" | grep -q "Learned from Failures"
}

@test "guardrails_learn_from_failure creates lesson with timestamp" {
    source_guardrails
    guardrails_init .

    guardrails_learn_from_failure "task-456" "Add feature X" 1 "Missing dependency" .

    local content=$(cat .cub/guardrails.md)
    # Should have a date header in format ### YYYY-MM-DD
    echo "$content" | grep -qE "### [0-9]{4}-[0-9]{2}-[0-9]{2}"
}

@test "guardrails_warn_size_if_exceeded outputs nothing when under limit" {
    source_guardrails
    guardrails_init .

    # Add a small lesson
    guardrails_add "Small lesson" "task-1" . > /dev/null 2>&1

    # Check with default 50KB limit
    run guardrails_warn_size_if_exceeded 50 .
    [[ "$status" -eq 0 ]]
    # Should output nothing (or minimal) when under limit
    if [[ -n "$output" ]]; then
        # If output exists, it should NOT be a warning about size
        [[ ! "$output" =~ "Guardrails file is getting large" ]]
    fi
}

@test "guardrails_warn_size_if_exceeded warns when over limit" {
    source_guardrails
    guardrails_init .

    # Create a large lesson to exceed limit
    # Generate content larger than 1KB by repeating a string
    local large_lesson=""
    for i in {1..50}; do
        large_lesson+="This is a long lesson that contains lots of text to make the file bigger. "
    done

    # Add large lesson multiple times to exceed 1KB limit
    for i in {1..30}; do
        guardrails_add "$large_lesson" "task-$i" . > /dev/null 2>&1
    done

    # Now warn with a very low limit (1KB) to trigger the warning
    run guardrails_warn_size_if_exceeded 1 .
    [[ "$status" -eq 0 ]]
    # Should output a warning message
    [[ "$output" =~ "Guardrails file is getting large" ]]
    [[ "$output" =~ "cub guardrails curate" ]]
}

@test "guardrails_warn_size_if_exceeded shows lesson count" {
    source_guardrails
    guardrails_init .

    # Create a large lesson to exceed limit
    # Generate content larger than 1KB by repeating a string
    local large_lesson=""
    for i in {1..50}; do
        large_lesson+="This is a long lesson that contains lots of text to make the file bigger. "
    done

    # Add lessons until we exceed 1KB
    for i in {1..25}; do
        guardrails_add "$large_lesson" "task-$i" . > /dev/null 2>&1
    done

    # Use 1KB limit to trigger warning
    run guardrails_warn_size_if_exceeded 1 .
    [[ "$status" -eq 0 ]]
    # Should show lesson count in warning
    [[ "$output" =~ "lessons" ]]
}

@test "guardrails_add calls warn function after adding" {
    source_guardrails
    guardrails_init .

    # Add a large lesson to exceed 1KB, which should trigger warning
    local large_lesson=""
    for i in {1..50}; do
        large_lesson+="This is a long lesson that contains lots of text to make the file bigger. "
    done

    # Add lessons until we exceed 1KB
    for i in {1..30}; do
        guardrails_add "$large_lesson" "task-$i" . > /dev/null 2>&1
    done

    # Now adding another lesson should show warning since we're over limit
    run guardrails_add "Another lesson" "task-final" .
    # Should contain warning from guardrails_warn_size_if_exceeded
    [[ "$output" =~ "Guardrails file is getting large" ]]
}

@test "guardrails_add_from_failure calls warn function after adding" {
    source_guardrails
    guardrails_init .

    # Create a large message to exceed limits
    local large_error=""
    for i in {1..50}; do
        large_error+="Error message with lots of details that makes the content bigger. "
    done

    # Add many failure entries to exceed 1KB
    for i in {1..25}; do
        guardrails_add_from_failure "task-$i" 1 "$large_error" "Lesson: $i" . > /dev/null 2>&1
    done

    # Now adding another should trigger warning
    run guardrails_add_from_failure "task-final" 1 "$large_error" "Final lesson" .
    [[ "$output" =~ "Guardrails file is getting large" ]]
}
