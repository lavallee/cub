#!/usr/bin/env bats
#
# markdown_parser.bats - Tests for markdown parser
#

load test_helper

setup() {
    setup_test_dir
    source "$LIB_DIR/parsers/markdown.sh"
}

teardown() {
    teardown_test_dir
}

# Test: Parse simple heading to epic
@test "markdown: parse H1 heading as epic" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# User Authentication
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    # Verify epic was created
    local epic_count
    epic_count=$(echo "$result" | jq '.epics | length')
    [[ "$epic_count" -eq 1 ]]

    # Verify epic title
    local epic_title
    epic_title=$(echo "$result" | jq -r '.epics[0].title')
    [[ "$epic_title" == "User Authentication" ]]

    # Verify epic type
    local epic_type
    epic_type=$(echo "$result" | jq -r '.epics[0].type')
    [[ "$epic_type" == "epic" ]]
}

# Test: Parse multiple headings
@test "markdown: parse multiple H1 headings as epics" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Authentication
# Payment Processing
# Analytics
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    local epic_count
    epic_count=$(echo "$result" | jq '.epics | length')
    [[ "$epic_count" -eq 3 ]]

    # Verify titles
    local titles
    titles=$(echo "$result" | jq -r '.epics[].title')
    [[ "$titles" == *"Authentication"* ]]
    [[ "$titles" == *"Payment Processing"* ]]
    [[ "$titles" == *"Analytics"* ]]
}

# Test: Parse subheading as feature/task group
@test "markdown: parse H2 subheading as task group" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Authentication
## Login System
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    # Should have 1 epic and 1 task (the feature)
    local epic_count task_count
    epic_count=$(echo "$result" | jq '.epics | length')
    task_count=$(echo "$result" | jq '.tasks | length')

    [[ "$epic_count" -eq 1 ]]
    [[ "$task_count" -eq 1 ]]

    # Verify task title and parent
    local task_title task_parent
    task_title=$(echo "$result" | jq -r '.tasks[0].title')
    task_parent=$(echo "$result" | jq -r '.tasks[0].parent')

    [[ "$task_title" == "Login System" ]]
    [[ "$task_parent" == "epic-1" ]]
}

# Test: Parse checkbox as task
@test "markdown: parse checkbox as task" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Authentication
## Login
- [ ] Create login form
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    # Should have 1 epic, 2 tasks (feature + checkbox task)
    local epic_count task_count
    epic_count=$(echo "$result" | jq '.epics | length')
    task_count=$(echo "$result" | jq '.tasks | length')

    [[ "$epic_count" -eq 1 ]]
    [[ "$task_count" -eq 2 ]]

    # Verify checkbox task
    local checkbox_task
    checkbox_task=$(echo "$result" | jq -r '.tasks[] | select(.title == "Create login form") | .title')
    [[ "$checkbox_task" == "Create login form" ]]
}

# Test: Parse bullet points as acceptance criteria
@test "markdown: parse bullets as acceptance criteria" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Feature
## Task Group
- [ ] Main task
- Criterion one
- Criterion two
- Criterion three
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    # Find the task with acceptance criteria
    local criteria_count
    criteria_count=$(echo "$result" | jq '.tasks[] | select(.title == "Main task") | .acceptanceCriteria | length')

    [[ "$criteria_count" -eq 3 ]]

    # Verify criteria content
    local criteria
    criteria=$(echo "$result" | jq -r '.tasks[] | select(.title == "Main task") | .acceptanceCriteria[]')

    [[ "$criteria" == *"Criterion one"* ]]
    [[ "$criteria" == *"Criterion two"* ]]
    [[ "$criteria" == *"Criterion three"* ]]
}

# Test: Complex nested structure
@test "markdown: parse complex nested structure" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Authentication System

## Registration Flow
- [ ] Create registration form
- Email validation
- Password strength requirements
- Terms acceptance checkbox
- [ ] Implement password hashing
- Use bcrypt
- Store salt separately

## Login Flow
- [ ] Create login form
- Email/password fields
- Remember me option
- [ ] Session management
- Create session tokens
- Set session timeout
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    # Verify structure
    local epic_count task_count
    epic_count=$(echo "$result" | jq '.epics | length')
    task_count=$(echo "$result" | jq '.tasks | length')

    [[ "$epic_count" -eq 1 ]]
    # 1 epic + 2 features + 4 checkboxes = 7 total tasks
    [[ "$task_count" -eq 7 ]]

    # Verify specific task
    local specific_task
    specific_task=$(echo "$result" | jq '.tasks[] | select(.title == "Create registration form")')
    [[ -n "$specific_task" ]]

    # Verify it has acceptance criteria
    local criteria_count
    criteria_count=$(echo "$result" | jq '.tasks[] | select(.title == "Create registration form") | .acceptanceCriteria | length')
    [[ "$criteria_count" -eq 3 ]]
}

# Test: File not found error
@test "markdown: return error for non-existent file" {
    local result
    result=$(parse_markdown_file "$TEST_DIR/nonexistent.md" 2>&1) || true

    [[ "$result" == *"File not found"* ]]
}

# Test: Empty file
@test "markdown: handle empty markdown file" {
    cat > "$TEST_DIR/empty.md" << 'EOF'
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/empty.md")

    local epic_count task_count
    epic_count=$(echo "$result" | jq '.epics | length')
    task_count=$(echo "$result" | jq '.tasks | length')

    [[ "$epic_count" -eq 0 ]]
    [[ "$task_count" -eq 0 ]]
}

# Test: File with only text (no structure)
@test "markdown: handle file with no markdown structure" {
    cat > "$TEST_DIR/plain.md" << 'EOF'
This is just plain text.
No structured content here.
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/plain.md")

    local epic_count task_count
    epic_count=$(echo "$result" | jq '.epics | length')
    task_count=$(echo "$result" | jq '.tasks | length')

    [[ "$epic_count" -eq 0 ]]
    [[ "$task_count" -eq 0 ]]
}

# Test: Extract epics function
@test "markdown: extract_epics returns only epics" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# First Epic
## Feature 1
- [ ] Task 1

# Second Epic
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    local epics
    epics=$(extract_epics "$result")

    local count
    count=$(echo "$epics" | jq 'length')
    [[ "$count" -eq 2 ]]

    # Verify all items are epics
    local types
    types=$(echo "$epics" | jq -r '.[].type')
    [[ "$types" == "epic"* ]]
}

# Test: Extract tasks function
@test "markdown: extract_tasks returns all tasks and features" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Epic
## Feature 1
- [ ] Task 1

## Feature 2
- [ ] Task 2
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    local tasks
    tasks=$(extract_tasks "$result")

    local count
    count=$(echo "$tasks" | jq 'length')
    # 2 features + 2 tasks = 4
    [[ "$count" -eq 4 ]]
}

# Test: Count items function
@test "markdown: count_items returns total count" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Epic 1
## Feature 1
- [ ] Task 1

# Epic 2
## Feature 2
- [ ] Task 2
- [ ] Task 3
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    local count
    count=$(count_items "$result")
    # 2 epics + 2 features + 3 tasks = 7
    [[ "$count" -eq 7 ]]
}

# Test: Checkboxes with various formats
@test "markdown: parse checkboxes with different formats" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Features
- [ ] Unchecked task
- [x] Checked task
- [X] Capital X task
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    local task_count
    task_count=$(echo "$result" | jq '.tasks | length')
    [[ "$task_count" -eq 3 ]]

    # Verify all are tasks (not epics)
    local all_tasks
    all_tasks=$(echo "$result" | jq '.tasks | length')
    [[ "$all_tasks" -eq 3 ]]
}

# Test: Preserve line numbers in output
@test "markdown: preserve line numbers for source references" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# First Epic
This is line 2
## Feature
This is line 4
- [ ] Task
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    # Verify line numbers are present in epic (in source object)
    local epic_has_source
    epic_has_source=$(echo "$result" | jq '.epics[0] | has("source")')
    [[ "$epic_has_source" == "true" ]]

    # Verify line number is correct
    local line_num
    line_num=$(echo "$result" | jq '.epics[0].source.line')
    [[ "$line_num" -eq 1 ]]
}

# Test: Mixed content with headers, tasks, and bullets
@test "markdown: handle mixed content correctly" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Dashboard

## User Profile Widget
- [ ] Display user avatar
- Support circular avatars
- Add fallback for missing images
- Handle large image files
- [ ] Show user statistics
- Display post count
- Show follower count

## Sidebar Navigation
- [ ] Create navigation menu
- Add dashboard link
- Add settings link
- Add logout link
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    # Verify epic
    local epic_title
    epic_title=$(echo "$result" | jq -r '.epics[0].title')
    [[ "$epic_title" == "Dashboard" ]]

    # Verify features
    local feature_titles
    feature_titles=$(echo "$result" | jq -r '.tasks[] | select(.parent != null) | select(.parent | contains("epic")) | .title')
    [[ "$feature_titles" == *"User Profile Widget"* ]]
    [[ "$feature_titles" == *"Sidebar Navigation"* ]]

    # Verify tasks with acceptance criteria
    local user_avatar_criteria
    user_avatar_criteria=$(echo "$result" | jq '.tasks[] | select(.title == "Display user avatar") | .acceptanceCriteria | length')
    [[ "$user_avatar_criteria" -eq 3 ]]

    local nav_menu_criteria
    nav_menu_criteria=$(echo "$result" | jq '.tasks[] | select(.title == "Create navigation menu") | .acceptanceCriteria | length')
    [[ "$nav_menu_criteria" -eq 3 ]]
}

# Test: JSON output is valid
@test "markdown: output valid JSON" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Test
## Feature
- [ ] Task
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    # Should not error when parsing as JSON
    local valid
    valid=$(echo "$result" | jq empty && echo "true" || echo "false")
    [[ "$valid" == "true" ]]

    # Should have required top-level keys
    local has_keys
    has_keys=$(echo "$result" | jq 'has("epics") and has("tasks") and has("dependencies")')
    [[ "$has_keys" == "true" ]]
}

# Test: Multiple tasks under same feature
@test "markdown: multiple checkboxes under one feature" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Feature
## Implementation
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    local task_count
    task_count=$(echo "$result" | jq '.tasks | length')
    # 1 feature + 3 tasks = 4
    [[ "$task_count" -eq 4 ]]

    # All tasks should have same parent
    local all_same_parent
    all_same_parent=$(echo "$result" | jq '[.tasks[] | select(.title != "Implementation")] | map(.parent) | unique | length')
    [[ "$all_same_parent" -eq 1 ]]
}

# Test: Acceptance criteria only associated with tasks, not features
@test "markdown: acceptance criteria only on checkbox tasks, not features" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Epic
## Feature Group
- [ ] Real task
- Real criterion
EOF

    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    # Feature should not have criteria
    local feature_criteria
    feature_criteria=$(echo "$result" | jq '.tasks[] | select(.title == "Feature Group") | .acceptanceCriteria | length')
    [[ "$feature_criteria" -eq 0 ]]

    # Task should have criteria
    local task_criteria
    task_criteria=$(echo "$result" | jq '.tasks[] | select(.title == "Real task") | .acceptanceCriteria | length')
    [[ "$task_criteria" -eq 1 ]]
}
