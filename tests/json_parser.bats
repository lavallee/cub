#!/usr/bin/env bats
#
# tests/json_parser.bats - Tests for JSON parser
#

load test_helper

setup() {
    # Source the parser
    source "$PROJECT_ROOT/lib/parsers/json.sh"
}

# ============================================================================
# Simple Array Format Tests
# ============================================================================

@test "parse_json_file with simple array format - basic task" {
    local json_file="$BATS_TMPDIR/simple.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First Task", "status": "open"}
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    # Check structure
    echo "$result" | jq -e '.tasks | length == 1' >/dev/null
    echo "$result" | jq -e '.tasks[0].id == "t1"' >/dev/null
    echo "$result" | jq -e '.tasks[0].title == "First Task"' >/dev/null
    echo "$result" | jq -e '.tasks[0].status == "open"' >/dev/null
}

@test "parse_json_file with simple array format - multiple tasks" {
    local json_file="$BATS_TMPDIR/multi.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "open"},
    {"id": "t2", "title": "Second", "status": "in_progress"},
    {"id": "t3", "title": "Third", "status": "closed"}
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    echo "$result" | jq -e '.tasks | length == 3' >/dev/null
    echo "$result" | jq -e '.tasks[0].title == "First"' >/dev/null
    echo "$result" | jq -e '.tasks[1].status == "in_progress"' >/dev/null
    echo "$result" | jq -e '.tasks[2].status == "closed"' >/dev/null
}

@test "parse_json_file with simple array format - tasks with dependencies" {
    local json_file="$BATS_TMPDIR/deps.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "closed"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["t1"]},
    {"id": "t3", "title": "Third", "status": "open", "dependsOn": ["t2"]}
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    echo "$result" | jq -e '.tasks | length == 3' >/dev/null
    echo "$result" | jq -e '.dependencies | length == 2' >/dev/null
    echo "$result" | jq -e '.dependencies[0].from == "t2"' >/dev/null
    echo "$result" | jq -e '.dependencies[0].to == "t1"' >/dev/null
    echo "$result" | jq -e '.dependencies[1].from == "t3"' >/dev/null
    echo "$result" | jq -e '.dependencies[1].to == "t2"' >/dev/null
}

@test "parse_json_file with simple array format - optional fields" {
    local json_file="$BATS_TMPDIR/optional.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {
      "id": "t1",
      "title": "Task with details",
      "status": "open",
      "description": "This is a description",
      "priority": "P1",
      "labels": ["feature", "urgent"],
      "acceptanceCriteria": ["Must work", "Must be fast"],
      "notes": "Implementation notes"
    }
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    echo "$result" | jq -e '.tasks[0].description == "This is a description"' >/dev/null
    echo "$result" | jq -e '.tasks[0].priority == "P1"' >/dev/null
    echo "$result" | jq -e '.tasks[0].labels | length == 2' >/dev/null
    echo "$result" | jq -e '.tasks[0].acceptanceCriteria | length == 2' >/dev/null
    echo "$result" | jq -e '.tasks[0].notes == "Implementation notes"' >/dev/null
}

@test "parse_json_file with simple array format - auto-generated IDs" {
    local json_file="$BATS_TMPDIR/autoid.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "myapp",
  "tasks": [
    {"title": "First Task", "status": "open"},
    {"title": "Second Task", "status": "open"}
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    echo "$result" | jq -e '.tasks[0].id == "myapp-1"' >/dev/null
    echo "$result" | jq -e '.tasks[1].id == "myapp-2"' >/dev/null
}

@test "parse_json_file with simple array format - default status" {
    local json_file="$BATS_TMPDIR/default_status.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Task without status"}
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    echo "$result" | jq -e '.tasks[0].status == "open"' >/dev/null
}

# ============================================================================
# Structured PRD Format Tests
# ============================================================================

@test "parse_json_file with structured PRD format - single feature" {
    local json_file="$BATS_TMPDIR/prd_single.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "myapp",
  "features": [
    {
      "id": "feat-1",
      "name": "User Authentication",
      "description": "User login and registration",
      "status": "in_progress"
    }
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    echo "$result" | jq -e '.tasks | length == 1' >/dev/null
    echo "$result" | jq -e '.tasks[0].id == "feat-1"' >/dev/null
    echo "$result" | jq -e '.tasks[0].title == "User Authentication"' >/dev/null
    echo "$result" | jq -e '.tasks[0].status == "in_progress"' >/dev/null
}

@test "parse_json_file with structured PRD format - features with tasks" {
    local json_file="$BATS_TMPDIR/prd_full.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "myapp",
  "features": [
    {
      "id": "feat-auth",
      "name": "User Authentication",
      "status": "in_progress",
      "tasks": [
        {"id": "task-login", "title": "Implement login", "status": "in_progress"},
        {"id": "task-signup", "title": "Implement signup", "status": "open"}
      ]
    },
    {
      "id": "feat-profile",
      "name": "User Profile",
      "status": "open",
      "tasks": [
        {"id": "task-view", "title": "View profile", "status": "open"},
        {"id": "task-edit", "title": "Edit profile", "status": "open"}
      ]
    }
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    # 2 features + 4 subtasks = 6 total tasks
    echo "$result" | jq -e '.tasks | length == 6' >/dev/null

    # Check feature tasks
    echo "$result" | jq -e '.tasks[] | select(.id == "feat-auth")' >/dev/null
    echo "$result" | jq -e '.tasks[] | select(.id == "feat-profile")' >/dev/null

    # Check subtasks have correct parent
    echo "$result" | jq -e '.tasks[] | select(.id == "task-login" and .parent == "feat-auth")' >/dev/null
    echo "$result" | jq -e '.tasks[] | select(.id == "task-signup" and .parent == "feat-auth")' >/dev/null
    echo "$result" | jq -e '.tasks[] | select(.id == "task-view" and .parent == "feat-profile")' >/dev/null
}

@test "parse_json_file with structured PRD format - feature dependencies" {
    local json_file="$BATS_TMPDIR/prd_deps.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "myapp",
  "features": [
    {
      "id": "feat-1",
      "name": "Feature 1",
      "status": "open"
    },
    {
      "id": "feat-2",
      "name": "Feature 2",
      "status": "open",
      "dependsOn": ["feat-1"]
    }
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    echo "$result" | jq -e '.dependencies | length == 1' >/dev/null
    echo "$result" | jq -e '.dependencies[0].from == "feat-2"' >/dev/null
    echo "$result" | jq -e '.dependencies[0].to == "feat-1"' >/dev/null
}

@test "parse_json_file with structured PRD format - auto-generated feature IDs" {
    local json_file="$BATS_TMPDIR/prd_autoid.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "app",
  "features": [
    {"name": "First Feature"},
    {"name": "Second Feature"}
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    echo "$result" | jq -e '.tasks[0].id == "app-feat-1"' >/dev/null
    echo "$result" | jq -e '.tasks[1].id == "app-feat-2"' >/dev/null
}

@test "parse_json_file with structured PRD format - feature with optional fields" {
    local json_file="$BATS_TMPDIR/prd_optional.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "app",
  "features": [
    {
      "id": "feat-1",
      "name": "Feature with details",
      "description": "Detailed description",
      "priority": "P0",
      "labels": ["critical", "ui"],
      "status": "open"
    }
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    echo "$result" | jq -e '.tasks[0].description == "Detailed description"' >/dev/null
    echo "$result" | jq -e '.tasks[0].priority == "P0"' >/dev/null
    echo "$result" | jq -e '.tasks[0].labels | length == 2' >/dev/null
}

# ============================================================================
# Error Handling Tests
# ============================================================================

@test "parse_json_file returns error for missing file" {
    run parse_json_file "/nonexistent/file.json"
    [ "$status" -eq 1 ]
    echo "$output" | grep -q "File not found"
}

@test "parse_json_file returns error for invalid JSON" {
    local json_file="$BATS_TMPDIR/invalid.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "Task" INVALID
  ]
}
EOF

    run parse_json_file "$json_file"
    [ "$status" -eq 1 ]
    echo "$output" | grep -q "Invalid JSON"
}

@test "parse_json_file returns error for missing tasks and features" {
    local json_file="$BATS_TMPDIR/empty.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "name": "Some data"
}
EOF

    run parse_json_file "$json_file"
    [ "$status" -eq 1 ]
    echo "$output" | grep -q "must contain either"
}

@test "parse_json_file returns error for non-array tasks" {
    local json_file="$BATS_TMPDIR/tasks_obj.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": {"t1": "not an array"}
}
EOF

    run parse_json_file "$json_file"
    [ "$status" -eq 1 ]
    echo "$output" | grep -q "must be an array"
}

@test "parse_json_file returns error for duplicate task IDs" {
    local json_file="$BATS_TMPDIR/dup_ids.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "open"},
    {"id": "t1", "title": "Second", "status": "open"}
  ]
}
EOF

    run parse_json_file "$json_file"
    [ "$status" -eq 1 ]
    echo "$output" | grep -q "Duplicate"
}

@test "parse_json_file detects circular dependencies" {
    local json_file="$BATS_TMPDIR/circular.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "open", "dependsOn": ["t2"]},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    run parse_json_file "$json_file"
    [ "$status" -eq 1 ]
    echo "$output" | grep -q "Circular"
}

# ============================================================================
# Helper Function Tests
# ============================================================================

@test "extract_tasks returns only tasks array" {
    local json_file="$BATS_TMPDIR/extract.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "open"},
    {"id": "t2", "title": "Second", "status": "open"}
  ]
}
EOF

    parsed=$(parse_json_file "$json_file")
    tasks=$(extract_tasks "$parsed")

    echo "$tasks" | jq -e 'length == 2' >/dev/null
    echo "$tasks" | jq -e '.[0].id == "t1"' >/dev/null
}

@test "count_items returns correct count" {
    local json_file="$BATS_TMPDIR/count.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "open"},
    {"id": "t2", "title": "Second", "status": "open"},
    {"id": "t3", "title": "Third", "status": "open"}
  ]
}
EOF

    parsed=$(parse_json_file "$json_file")
    count=$(count_items "$parsed")

    [ "$count" -eq 3 ]
}

@test "format_parsed_json produces formatted output" {
    local json_file="$BATS_TMPDIR/format.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "open"},
    {"id": "t2", "title": "Second", "status": "open", "dependsOn": ["t1"]}
  ]
}
EOF

    parsed=$(parse_json_file "$json_file")
    output=$(format_parsed_json "$parsed")

    echo "$output" | grep -q "Parsed JSON"
    echo "$output" | grep -q "Total Tasks"
    echo "$output" | grep -q "First"
    echo "$output" | grep -q "Second"
}

# ============================================================================
# Integration Tests
# ============================================================================

@test "json parser output compatible with markdown parser structure" {
    local json_file="$BATS_TMPDIR/compat.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "test",
  "tasks": [
    {"id": "t1", "title": "First", "status": "open"}
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    # Should have same top-level structure as markdown parser
    echo "$result" | jq -e 'has("epics")' >/dev/null
    echo "$result" | jq -e 'has("tasks")' >/dev/null
    echo "$result" | jq -e 'has("dependencies")' >/dev/null

    # Top level should be arrays
    echo "$result" | jq -e '.epics | type == "array"' >/dev/null
    echo "$result" | jq -e '.tasks | type == "array"' >/dev/null
    echo "$result" | jq -e '.dependencies | type == "array"' >/dev/null
}

@test "complex PRD import scenario" {
    local json_file="$BATS_TMPDIR/complex_prd.json"
    cat >"$json_file" <<'EOF'
{
  "prefix": "acmeapp",
  "features": [
    {
      "id": "auth",
      "name": "Authentication System",
      "description": "User login and security",
      "priority": "P0",
      "status": "in_progress",
      "labels": ["security", "core"],
      "tasks": [
        {
          "id": "auth-login",
          "title": "Login endpoint",
          "status": "in_progress",
          "acceptanceCriteria": ["Validates credentials", "Returns JWT"]
        },
        {
          "id": "auth-logout",
          "title": "Logout endpoint",
          "status": "open",
          "dependsOn": ["auth-login"]
        }
      ]
    },
    {
      "id": "api",
      "name": "API Design",
      "description": "RESTful API structure",
      "priority": "P0",
      "status": "open",
      "dependsOn": ["auth"]
    }
  ]
}
EOF

    result=$(parse_json_file "$json_file")

    # Should have 3 tasks: 2 features + 2 feature tasks = 4 actual tasks
    # Actually: feat-auth, task-login, task-logout, feat-api = 4 tasks
    echo "$result" | jq -e '.tasks | length == 4' >/dev/null

    # Should have dependencies
    echo "$result" | jq -e '.dependencies | length > 0' >/dev/null

    # Verify hierarchy
    echo "$result" | jq -e '.tasks[] | select(.id == "auth-login" and .parent == "auth")' >/dev/null
    echo "$result" | jq -e '.tasks[] | select(.id == "api" and .parent == null)' >/dev/null
}
