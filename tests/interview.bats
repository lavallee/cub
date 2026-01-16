#!/usr/bin/env bats

load test_helper

setup() {
    setup_test_dir
}

teardown() {
    teardown_test_dir
}

# ============================================================================
# Question Filtering Tests
# ============================================================================

@test "interview_filter_questions filters by task type" {
    source "${LIB_DIR}/cmd_interview.sh"

    local task_json='{"id":"test-1","type":"bugfix","title":"Fix bug"}'
    local questions
    questions=$(interview_load_questions)

    local filtered
    filtered=$(interview_filter_questions "$task_json" "$questions")

    # Bugfix should not get feature-only questions
    local feature_only
    feature_only=$(echo "$filtered" | jq '[.[] | select(.applies_to == ["feature"])] | length')
    [ "$feature_only" -eq 0 ]

    # Bugfix should get questions that apply to bugfix
    local has_bugfix
    has_bugfix=$(echo "$filtered" | jq '[.[] | select(.applies_to | contains(["bugfix"]))] | length')
    [ "$has_bugfix" -gt 0 ]
}

@test "interview_filter_questions filters by task labels" {
    source "${LIB_DIR}/cmd_interview.sh"

    local task_json='{"id":"test-1","type":"task","title":"Test","labels":["api","integration"]}'
    local questions
    questions=$(interview_load_questions)

    local filtered
    filtered=$(interview_filter_questions "$task_json" "$questions")

    # Should include API-related questions
    local has_api
    has_api=$(echo "$filtered" | jq '[.[] | select(.id == "apis_call")] | length')
    [ "$has_api" -eq 1 ]
}

@test "interview_filter_questions filters out questions without matching labels" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Feature task without security/auth labels
    local task_json='{"id":"test-1","type":"feature","title":"Test","labels":["documentation"]}'
    local questions
    questions=$(interview_load_questions)

    local filtered
    filtered=$(interview_filter_questions "$task_json" "$questions")

    # Feature-type security questions requiring auth labels should be filtered out
    local auth_questions
    auth_questions=$(echo "$filtered" | jq '[.[] | select(.category == "Security" and .question == "What authentication is required?")] | length')
    [ "$auth_questions" -eq 0 ]
}

@test "interview_detect_tech_stack detects bash projects" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Create test bash files
    mkdir -p "${BATS_TMPDIR}/test_project/lib"
    touch "${BATS_TMPDIR}/test_project/script.sh"
    touch "${BATS_TMPDIR}/test_project/lib/module.sh"

    cd "${BATS_TMPDIR}/test_project"
    local tech_stack
    tech_stack=$(interview_detect_tech_stack)

    # Should detect bash
    local has_bash
    has_bash=$(echo "$tech_stack" | jq 'contains(["bash"])')
    [ "$has_bash" = "true" ]
}

@test "interview_detect_tech_stack detects nodejs projects" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Create test package.json
    mkdir -p "${BATS_TMPDIR}/test_project"
    echo '{"name":"test","dependencies":{"express":"^4.0.0"}}' > "${BATS_TMPDIR}/test_project/package.json"

    cd "${BATS_TMPDIR}/test_project"
    local tech_stack
    tech_stack=$(interview_detect_tech_stack)

    # Should detect nodejs and express
    local has_nodejs
    has_nodejs=$(echo "$tech_stack" | jq 'contains(["nodejs"])')
    [ "$has_nodejs" = "true" ]

    local has_express
    has_express=$(echo "$tech_stack" | jq 'contains(["express"])')
    [ "$has_express" = "true" ]
}

@test "interview_detect_tech_stack detects python projects" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Create test requirements.txt
    mkdir -p "${BATS_TMPDIR}/test_project"
    echo "flask==2.0.0" > "${BATS_TMPDIR}/test_project/requirements.txt"

    cd "${BATS_TMPDIR}/test_project"
    local tech_stack
    tech_stack=$(interview_detect_tech_stack)

    # Should detect python
    local has_python
    has_python=$(echo "$tech_stack" | jq 'contains(["python"])')
    [ "$has_python" = "true" ]
}

# ============================================================================
# Skip Logic Tests
# ============================================================================

@test "interview_should_skip_question returns 1 when no skip condition" {
    source "${LIB_DIR}/cmd_interview.sh"

    local question='{"category":"Test","question":"Test question"}'
    local responses='[]'

    if interview_should_skip_question "$question" "$responses"; then
        # Should not skip (return 1 means don't skip)
        fail "Expected question not to be skipped"
    fi
}

@test "interview_should_skip_question skips when condition matches" {
    source "${LIB_DIR}/cmd_interview.sh"

    local question='{
        "category":"Test",
        "question":"Follow-up question",
        "skip_if": {
            "question_ids": ["data_write"],
            "answers_match": ["^(none|n/a|no)$"]
        }
    }'

    local responses='[
        {"question_id":"data_write","question":"What data does this write?","answer":"none"}
    ]'

    if ! interview_should_skip_question "$question" "$responses"; then
        fail "Expected question to be skipped when answer matches"
    fi
}

@test "interview_should_skip_question does not skip when condition does not match" {
    source "${LIB_DIR}/cmd_interview.sh"

    local question='{
        "category":"Test",
        "question":"Follow-up question",
        "skip_if": {
            "question_ids": ["data_write"],
            "answers_match": ["^(none|n/a|no)$"]
        }
    }'

    local responses='[
        {"question_id":"data_write","question":"What data does this write?","answer":"User profiles and settings"}
    ]'

    if interview_should_skip_question "$question" "$responses"; then
        fail "Expected question not to be skipped when answer does not match"
    fi
}

@test "interview_should_skip_question handles case-insensitive matching" {
    source "${LIB_DIR}/cmd_interview.sh"

    local question='{
        "category":"Test",
        "question":"Follow-up question",
        "skip_if": {
            "question_ids": ["apis_call"],
            "answers_match": ["^(none|n/a|no)$"]
        }
    }'

    local responses='[
        {"question_id":"apis_call","question":"What APIs does this call?","answer":"NONE"}
    ]'

    if ! interview_should_skip_question "$question" "$responses"; then
        fail "Expected question to be skipped with case-insensitive match"
    fi
}

# ============================================================================
# Integration Tests
# ============================================================================

@test "interview_load_questions returns valid JSON" {
    source "${LIB_DIR}/cmd_interview.sh"

    local questions
    questions=$(interview_load_questions)

    # Verify it's valid JSON
    echo "$questions" | jq . > /dev/null

    # Verify it's an array
    local is_array
    is_array=$(echo "$questions" | jq 'type == "array"')
    [ "$is_array" = "true" ]

    # Verify we have questions
    local count
    count=$(echo "$questions" | jq 'length')
    [ "$count" -gt 40 ]
}

@test "interview_load_questions has required fields" {
    source "${LIB_DIR}/cmd_interview.sh"

    local questions
    questions=$(interview_load_questions)

    # Check first question has required fields
    local first_question
    first_question=$(echo "$questions" | jq '.[0]')

    local has_category
    has_category=$(echo "$first_question" | jq 'has("category")')
    [ "$has_category" = "true" ]

    local has_question
    has_question=$(echo "$first_question" | jq 'has("question")')
    [ "$has_question" = "true" ]

    local has_applies_to
    has_applies_to=$(echo "$first_question" | jq 'has("applies_to")')
    [ "$has_applies_to" = "true" ]
}

@test "interview filtering combines task type and labels correctly" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Feature task with security labels
    local task_json='{"id":"test-1","type":"feature","title":"Auth feature","labels":["security","auth"]}'
    local questions
    questions=$(interview_load_questions)

    local filtered
    filtered=$(interview_filter_questions "$task_json" "$questions")

    # Should include feature questions
    local feature_count
    feature_count=$(echo "$filtered" | jq '[.[] | select(.applies_to | contains(["feature"]))] | length')
    [ "$feature_count" -gt 0 ]

    # Should include security questions since task has security label
    local security_count
    security_count=$(echo "$filtered" | jq '[.[] | select(.category == "Security")] | length')
    [ "$security_count" -gt 0 ]
}

# ============================================================================
# Auto Mode and Codebase Context Tests
# ============================================================================

@test "interview_gather_codebase_context detects bash project" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Create test bash project in TEST_DIR (already set by setup_test_dir)
    mkdir -p "lib"
    touch "script.sh"
    touch "lib/utils.sh"

    local context
    context=$(interview_gather_codebase_context)

    # Should mention key files
    echo "$context" | grep -q "script.sh"
    echo "$context" | grep -q "lib/utils.sh"
}

@test "interview_gather_codebase_context detects nodejs project" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Create test nodejs project in TEST_DIR
    echo '{"name":"test"}' > "package.json"
    touch "package-lock.json"

    local context
    context=$(interview_gather_codebase_context)

    # Should mention Node.js and npm
    echo "$context" | grep -q "Node.js"
    echo "$context" | grep -q "npm"
}

@test "interview_gather_codebase_context detects test directory" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Create test project with tests in TEST_DIR
    mkdir -p "tests"
    touch "tests/test_sample.sh"

    local context
    context=$(interview_gather_codebase_context)

    # Should mention tests directory
    echo "$context" | grep -q "tests/"
}

@test "interview_gather_codebase_context detects docker compose" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Create test project with docker-compose in TEST_DIR
    echo 'version: "3"' > "docker-compose.yml"

    local context
    context=$(interview_gather_codebase_context)

    # Should mention Docker Compose
    echo "$context" | grep -q "Docker Compose"
}

@test "interview_gather_codebase_context limits file list" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Create test project with many files in TEST_DIR
    for i in {1..30}; do
        touch "file${i}.sh"
    done

    local context
    context=$(interview_gather_codebase_context)

    # Should not overwhelm with too many files (limited to 20 in implementation)
    local file_count
    file_count=$(echo "$context" | grep -c "^- file[0-9]" || true)
    [ "$file_count" -le 20 ]
}

@test "interview_generate_spec includes mode in output" {
    source "${LIB_DIR}/cmd_interview.sh"

    local task_json='{"id":"test-1","type":"task","title":"Test Task","description":"Test description"}'
    local responses='[{"category":"Test","question":"Q1","answer":"A1"}]'
    local output_file="${TEST_DIR}/spec.md"

    # Generate spec in auto mode
    interview_generate_spec "$task_json" "$responses" "$output_file" "auto"

    # Check that file was created
    [ -f "$output_file" ]

    # Check that mode is included (with markdown bold markers)
    grep -q "Interview Mode:.*auto" "$output_file"
}

@test "interview_generate_spec defaults to interactive mode" {
    source "${LIB_DIR}/cmd_interview.sh"

    local task_json='{"id":"test-1","type":"task","title":"Test Task","description":"Test description"}'
    local responses='[{"category":"Test","question":"Q1","answer":"A1"}]'
    local output_file="${TEST_DIR}/spec_default.md"

    # Generate spec without mode parameter (should default to interactive)
    interview_generate_spec "$task_json" "$responses" "$output_file"

    # Check that mode defaults to interactive (with markdown bold markers)
    grep -q "Interview Mode:.*interactive" "$output_file"
}

# ============================================================================
# Acceptance Criteria Extraction Tests
# ============================================================================

@test "interview_extract_acceptance_criteria extracts from success criteria" {
    source "${LIB_DIR}/cmd_interview.sh"

    local responses='[
        {"category":"Functional Requirements","question":"What are the success criteria?","answer":"Feature works correctly\nAll edge cases handled\nPerformance meets SLA"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should extract all three criteria
    echo "$criteria" | grep -q "\- \[ \] Feature works correctly"
    echo "$criteria" | grep -q "\- \[ \] All edge cases handled"
    echo "$criteria" | grep -q "\- \[ \] Performance meets SLA"
}

@test "interview_extract_acceptance_criteria extracts from testing questions" {
    source "${LIB_DIR}/cmd_interview.sh"

    local responses='[
        {"category":"Testing","question":"What unit tests are needed?","answer":"Test happy path\nTest error conditions\nTest boundary values"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should extract test criteria
    echo "$criteria" | grep -q "\- \[ \].*Test.*happy path"
    echo "$criteria" | grep -q "\- \[ \].*Test.*error conditions"
    echo "$criteria" | grep -q "\- \[ \].*Test.*boundary values"
}

@test "interview_extract_acceptance_criteria extracts from error handling" {
    source "${LIB_DIR}/cmd_interview.sh"

    local responses='[
        {"category":"Error Handling","question":"How should each error be handled?","answer":"Invalid input: show error message\nTimeout: retry with backoff\nAPI failure: use cached data"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should extract error handling criteria
    echo "$criteria" | grep -q "\- \[ \].*Invalid input"
    echo "$criteria" | grep -q "\- \[ \].*Timeout"
    echo "$criteria" | grep -q "\- \[ \].*API failure"
    # Should add general error handling criterion
    echo "$criteria" | grep -q "\- \[ \] All error scenarios handled gracefully"
}

@test "interview_extract_acceptance_criteria extracts from validation rules" {
    source "${LIB_DIR}/cmd_interview.sh"

    local responses='[
        {"category":"Data & State","question":"Are there data validation rules?","answer":"Email must be valid format\nAge must be positive integer"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should extract validation criteria
    echo "$criteria" | grep -q "\- \[ \].*Email must be valid format"
    echo "$criteria" | grep -q "\- \[ \].*Age must be positive integer"
}

@test "interview_extract_acceptance_criteria extracts from output requirements" {
    source "${LIB_DIR}/cmd_interview.sh"

    local responses='[
        {"category":"Functional Requirements","question":"What outputs does this feature produce?","answer":"JSON response with status\nHTTP 200 on success"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should extract output criteria
    echo "$criteria" | grep -q "\- \[ \].*JSON response"
    echo "$criteria" | grep -q "\- \[ \].*HTTP 200"
}

@test "interview_extract_acceptance_criteria handles bulleted lists" {
    source "${LIB_DIR}/cmd_interview.sh"

    local responses='[
        {"category":"Functional Requirements","question":"What are the success criteria?","answer":"- Feature deployed\n- Users can access it\n- Metrics tracked"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should strip bullet points and create checkboxes
    echo "$criteria" | grep -q "\- \[ \] Feature deployed"
    echo "$criteria" | grep -q "\- \[ \] Users can access it"
    echo "$criteria" | grep -q "\- \[ \] Metrics tracked"
}

@test "interview_extract_acceptance_criteria handles numbered lists" {
    source "${LIB_DIR}/cmd_interview.sh"

    local responses='[
        {"category":"Functional Requirements","question":"What are the success criteria?","answer":"1. First requirement\n2. Second requirement\n3. Third requirement"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should strip numbers and create checkboxes
    echo "$criteria" | grep -q "\- \[ \] First requirement"
    echo "$criteria" | grep -q "\- \[ \] Second requirement"
    echo "$criteria" | grep -q "\- \[ \] Third requirement"
}

@test "interview_extract_acceptance_criteria skips N/A answers" {
    source "${LIB_DIR}/cmd_interview.sh"

    local responses='[
        {"category":"Error Handling","question":"What errors can occur?","answer":"N/A"},
        {"category":"Testing","question":"What unit tests are needed?","answer":"Test the main function"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should not include N/A
    ! echo "$criteria" | grep -q "N/A"
    # Should include valid answer
    echo "$criteria" | grep -q "\- \[ \].*Test.*main function"
}

@test "interview_extract_acceptance_criteria combines multiple sources" {
    source "${LIB_DIR}/cmd_interview.sh"

    local responses='[
        {"category":"Functional Requirements","question":"What are the success criteria?","answer":"Feature works"},
        {"category":"Testing","question":"What unit tests are needed?","answer":"Test main path"},
        {"category":"Error Handling","question":"How should each error be handled?","answer":"Show error message"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should include criteria from all sources
    echo "$criteria" | grep -q "\- \[ \] Feature works"
    echo "$criteria" | grep -q "\- \[ \].*Test.*main path"
    echo "$criteria" | grep -q "\- \[ \].*error message"
    # Should always add test passing
    echo "$criteria" | grep -q "\- \[ \] All tests passing"
}

@test "interview_extract_acceptance_criteria provides fallback criteria" {
    source "${LIB_DIR}/cmd_interview.sh"

    local responses='[
        {"category":"Other","question":"Some question","answer":"Some answer"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should have generic fallback criteria
    echo "$criteria" | grep -q "\- \[ \] Complete implementation as described"
    echo "$criteria" | grep -q "\- \[ \] All tests passing"
    echo "$criteria" | grep -q "\- \[ \] Error handling implemented"
}

@test "interview_extract_acceptance_criteria uses primary goal as fallback" {
    source "${LIB_DIR}/cmd_interview.sh"

    local responses='[
        {"category":"Functional Requirements","question":"What is the primary user goal this feature enables?","answer":"Users can export their data"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should use primary goal if no explicit success criteria
    echo "$criteria" | grep -q "\- \[ \] Users can export their data"
    echo "$criteria" | grep -q "\- \[ \] All tests passing"
}

# ============================================================================
# Custom Question Tests
# ============================================================================

@test "interview_load_custom_questions returns empty array when no config exists" {
    source "${LIB_DIR}/cmd_interview.sh"

    cd "${BATS_TMPDIR}"
    local custom_questions
    custom_questions=$(interview_load_custom_questions)

    # Should return empty array
    [ "$custom_questions" == "[]" ]
}

@test "interview_load_custom_questions loads custom questions from .cub.json" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Create a test directory with .cub.json
    local test_dir="${BATS_TMPDIR}/custom_questions_test"
    mkdir -p "$test_dir"
    cd "$test_dir"

    # Create .cub.json with custom questions
    cat > .cub.json <<'EOF'
{
  "interview": {
    "custom_questions": [
      {
        "category": "Custom Category",
        "question": "Custom question 1?",
        "applies_to": ["feature", "task"]
      },
      {
        "category": "Custom Category",
        "question": "Custom question 2?",
        "applies_to": ["feature"]
      }
    ]
  }
}
EOF

    local custom_questions
    custom_questions=$(interview_load_custom_questions)

    # Should return the custom questions array
    local count
    count=$(echo "$custom_questions" | jq 'length')
    [ "$count" -eq 2 ]

    # Check first custom question
    local first_question
    first_question=$(echo "$custom_questions" | jq -r '.[0].question')
    [ "$first_question" == "Custom question 1?" ]

    # Check category
    local category
    category=$(echo "$custom_questions" | jq -r '.[0].category')
    [ "$category" == "Custom Category" ]
}

@test "interview_merge_questions combines built-in and custom questions" {
    source "${LIB_DIR}/cmd_interview.sh"

    local built_in='[{"category":"A","question":"Q1"},{"category":"B","question":"Q2"}]'
    local custom='[{"category":"C","question":"Q3"}]'

    local merged
    merged=$(interview_merge_questions "$built_in" "$custom")

    # Should have 3 total questions
    local count
    count=$(echo "$merged" | jq 'length')
    [ "$count" -eq 3 ]

    # Built-in questions should be first
    local first
    first=$(echo "$merged" | jq -r '.[0].question')
    [ "$first" == "Q1" ]

    # Custom questions should be at the end
    local last
    last=$(echo "$merged" | jq -r '.[-1].question')
    [ "$last" == "Q3" ]
}

@test "interview_merge_questions handles empty custom questions" {
    source "${LIB_DIR}/cmd_interview.sh"

    local built_in='[{"category":"A","question":"Q1"}]'
    local custom='[]'

    local merged
    merged=$(interview_merge_questions "$built_in" "$custom")

    # Should only have built-in question
    local count
    count=$(echo "$merged" | jq 'length')
    [ "$count" -eq 1 ]

    local first
    first=$(echo "$merged" | jq -r '.[0].question')
    [ "$first" == "Q1" ]
}

@test "custom questions are included in filtering by task type" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Create test directory with custom questions
    local test_dir="${BATS_TMPDIR}/custom_filter_test"
    mkdir -p "$test_dir"
    cd "$test_dir"

    cat > .cub.json <<'EOF'
{
  "interview": {
    "custom_questions": [
      {
        "category": "Custom",
        "question": "Custom feature question?",
        "applies_to": ["feature"]
      },
      {
        "category": "Custom",
        "question": "Custom universal question?",
        "applies_to": ["feature", "task", "bugfix"]
      }
    ]
  }
}
EOF

    local task_json='{"id":"test-1","type":"feature","title":"Test"}'
    local built_in
    built_in=$(interview_load_questions)
    local custom
    custom=$(interview_load_custom_questions)
    local all_questions
    all_questions=$(interview_merge_questions "$built_in" "$custom")

    local filtered
    filtered=$(interview_filter_questions "$task_json" "$all_questions")

    # Both custom questions should be in results for feature
    local custom_count
    custom_count=$(echo "$filtered" | jq '[.[] | select(.category == "Custom")] | length')
    [ "$custom_count" -eq 2 ]
}

@test "custom questions support requires_labels filtering" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Create test directory
    local test_dir="${BATS_TMPDIR}/custom_labels_test"
    mkdir -p "$test_dir"
    cd "$test_dir"

    cat > .cub.json <<'EOF'
{
  "interview": {
    "custom_questions": [
      {
        "category": "Custom API",
        "question": "Custom API question?",
        "applies_to": ["feature"],
        "requires_labels": ["api"]
      }
    ]
  }
}
EOF

    # Task without API label
    local task_json='{"id":"test-1","type":"feature","title":"Test","labels":["ui"]}'
    local built_in
    built_in=$(interview_load_questions)
    local custom
    custom=$(interview_load_custom_questions)
    local all_questions
    all_questions=$(interview_merge_questions "$built_in" "$custom")

    local filtered
    filtered=$(interview_filter_questions "$task_json" "$all_questions")

    # Custom API question should be filtered out
    local custom_count
    custom_count=$(echo "$filtered" | jq '[.[] | select(.category == "Custom API")] | length')
    [ "$custom_count" -eq 0 ]

    # Now test with API label
    task_json='{"id":"test-2","type":"feature","title":"Test","labels":["api"]}'
    filtered=$(interview_filter_questions "$task_json" "$all_questions")

    # Custom API question should now be included
    custom_count=$(echo "$filtered" | jq '[.[] | select(.category == "Custom API")] | length')
    [ "$custom_count" -eq 1 ]
}

# ============================================================================
# Skip Categories Configuration Tests
# ============================================================================

@test "interview_load_skip_categories returns empty string when no config" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Setup: Create temp directory without .cub.json
    local tmpdir
    tmpdir=$(mktemp -d)
    cd "$tmpdir" || exit 1

    # Test
    local result
    result=$(interview_load_skip_categories)

    # Cleanup
    cd - >/dev/null || exit 1
    rmdir "$tmpdir"

    # Verify: Should return empty string
    [ -z "$result" ]
}

@test "interview_load_skip_categories loads from .cub.json" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Setup: Create temp directory with .cub.json
    local tmpdir
    tmpdir=$(mktemp -d)
    cd "$tmpdir" || exit 1

    # Create .cub.json with skip_categories
    cat > .cub.json <<'EOF'
{
  "interview": {
    "skip_categories": ["Security", "Performance & Scale"]
  }
}
EOF

    # Test
    local result
    result=$(interview_load_skip_categories)

    # Cleanup
    cd - >/dev/null || exit 1
    rm -rf "$tmpdir"

    # Verify: Should return comma-separated list
    [ "$result" = "Security,Performance & Scale" ]
}

@test "interview_load_skip_categories returns empty when skip_categories is empty array" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Setup: Create temp directory with .cub.json with empty skip_categories
    local tmpdir
    tmpdir=$(mktemp -d)
    cd "$tmpdir" || exit 1

    # Create .cub.json with empty skip_categories
    cat > .cub.json <<'EOF'
{
  "interview": {
    "skip_categories": []
  }
}
EOF

    # Test
    local result
    result=$(interview_load_skip_categories)

    # Cleanup
    cd - >/dev/null || exit 1
    rm -rf "$tmpdir"

    # Verify: Should return empty string
    [ -z "$result" ]
}

@test "interview_load_skip_categories handles missing interview section" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Setup: Create temp directory with .cub.json without interview section
    local tmpdir
    tmpdir=$(mktemp -d)
    cd "$tmpdir" || exit 1

    # Create .cub.json without interview section
    cat > .cub.json <<'EOF'
{
  "hooks": {
    "enabled": true
  }
}
EOF

    # Test
    local result
    result=$(interview_load_skip_categories)

    # Cleanup
    cd - >/dev/null || exit 1
    rm -rf "$tmpdir"

    # Verify: Should return empty string
    [ -z "$result" ]
}

@test "skip_categories filter excludes specified categories" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Load questions
    local questions
    questions=$(interview_load_questions)

    # Get original count of Security questions
    local original_security_count
    original_security_count=$(echo "$questions" | jq '[.[] | select(.category == "Security")] | length')

    # Apply skip-categories filter for Security
    local skip_array
    skip_array=$(echo "Security" | jq -R 'split(",")')
    local filtered
    filtered=$(echo "$questions" | jq --argjson skip "$skip_array" '
        [.[] | select(.category as $cat | $skip | contains([$cat]) | not)]
    ')

    # Count Security questions after filter
    local filtered_security_count
    filtered_security_count=$(echo "$filtered" | jq '[.[] | select(.category == "Security")] | length')

    # Verify: Security questions should be removed
    [ "$original_security_count" -gt 0 ]
    [ "$filtered_security_count" -eq 0 ]
}

@test "skip_categories filter handles multiple categories" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Load questions
    local questions
    questions=$(interview_load_questions)

    # Apply skip-categories filter for multiple categories
    local skip_array
    skip_array=$(echo "Security,Performance & Scale,Operations" | jq -R 'split(",")')
    local filtered
    filtered=$(echo "$questions" | jq --argjson skip "$skip_array" '
        [.[] | select(.category as $cat | $skip | contains([$cat]) | not)]
    ')

    # Verify no questions from skipped categories exist
    local security_count
    security_count=$(echo "$filtered" | jq '[.[] | select(.category == "Security")] | length')
    [ "$security_count" -eq 0 ]

    local perf_count
    perf_count=$(echo "$filtered" | jq '[.[] | select(.category == "Performance & Scale")] | length')
    [ "$perf_count" -eq 0 ]

    local ops_count
    ops_count=$(echo "$filtered" | jq '[.[] | select(.category == "Operations")] | length')
    [ "$ops_count" -eq 0 ]

    # Verify other categories still exist
    local func_count
    func_count=$(echo "$filtered" | jq '[.[] | select(.category == "Functional Requirements")] | length')
    [ "$func_count" -gt 0 ]
}

@test "skip_categories filter preserves non-skipped categories" {
    source "${LIB_DIR}/cmd_interview.sh"

    # Load questions
    local questions
    questions=$(interview_load_questions)

    # Get original count
    local original_count
    original_count=$(echo "$questions" | jq 'length')

    # Apply skip-categories filter for just one category
    local skip_array
    skip_array=$(echo "Security" | jq -R 'split(",")')
    local filtered
    filtered=$(echo "$questions" | jq --argjson skip "$skip_array" '
        [.[] | select(.category as $cat | $skip | contains([$cat]) | not)]
    ')

    local filtered_count
    filtered_count=$(echo "$filtered" | jq 'length')

    # Verify: Filtered count should be less than original
    [ "$filtered_count" -lt "$original_count" ]

    # Verify: Other categories are preserved
    local has_functional
    has_functional=$(echo "$filtered" | jq '[.[] | select(.category == "Functional Requirements")] | length')
    [ "$has_functional" -gt 0 ]
}
