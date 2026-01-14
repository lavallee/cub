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
