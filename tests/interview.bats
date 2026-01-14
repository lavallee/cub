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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

    local question='{"category":"Test","question":"Test question"}'
    local responses='[]'

    if interview_should_skip_question "$question" "$responses"; then
        # Should not skip (return 1 means don't skip)
        fail "Expected question not to be skipped"
    fi
}

@test "interview_should_skip_question skips when condition matches" {
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

    # Create test project with tests in TEST_DIR
    mkdir -p "tests"
    touch "tests/test_sample.sh"

    local context
    context=$(interview_gather_codebase_context)

    # Should mention tests directory
    echo "$context" | grep -q "tests/"
}

@test "interview_gather_codebase_context detects docker compose" {
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

    # Create test project with docker-compose in TEST_DIR
    echo 'version: "3"' > "docker-compose.yml"

    local context
    context=$(interview_gather_codebase_context)

    # Should mention Docker Compose
    echo "$context" | grep -q "Docker Compose"
}

@test "interview_gather_codebase_context limits file list" {
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

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
    source "${PROJECT_ROOT}/lib/cmd_interview.sh"

    local responses='[
        {"category":"Functional Requirements","question":"What is the primary user goal this feature enables?","answer":"Users can export their data"}
    ]'

    local criteria
    criteria=$(interview_extract_acceptance_criteria "$responses")

    # Should use primary goal if no explicit success criteria
    echo "$criteria" | grep -q "\- \[ \] Users can export their data"
    echo "$criteria" | grep -q "\- \[ \] All tests passing"
}
