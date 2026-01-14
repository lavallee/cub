#!/usr/bin/env bash
#
# cmd_interview.sh - Interview Mode implementation
#
# Deep questioning phase to refine task specifications before execution,
# covering edge cases, error handling, and integration points through
# structured interviews.
#

# Include guard
if [[ -n "${_CUB_CMD_INTERVIEW_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_INTERVIEW_SH_LOADED=1

# ============================================================================
# Question Bank
# ============================================================================

# Load question bank
# Returns: JSON array of question objects
interview_load_questions() {
    cat <<'EOF'
[
  {"category": "Functional Requirements", "question": "What is the primary user goal this feature enables?", "applies_to": ["feature", "task"]},
  {"category": "Functional Requirements", "question": "What inputs does this feature accept?", "applies_to": ["feature", "task"]},
  {"category": "Functional Requirements", "question": "What outputs does this feature produce?", "applies_to": ["feature", "task"]},
  {"category": "Functional Requirements", "question": "What are the success criteria?", "applies_to": ["feature", "task", "bugfix"]},
  {"category": "Functional Requirements", "question": "What existing features does this interact with?", "applies_to": ["feature", "task"]},

  {"category": "Edge Cases", "question": "What happens with empty input?", "applies_to": ["feature", "task"]},
  {"category": "Edge Cases", "question": "What happens with malformed input?", "applies_to": ["feature", "task"]},
  {"category": "Edge Cases", "question": "What happens with extremely large input?", "applies_to": ["feature", "task"]},
  {"category": "Edge Cases", "question": "What happens during concurrent access?", "applies_to": ["feature", "task"]},
  {"category": "Edge Cases", "question": "What happens if a dependency is unavailable?", "applies_to": ["feature", "task"]},
  {"category": "Edge Cases", "question": "What happens on timeout?", "applies_to": ["feature", "task"]},

  {"category": "Error Handling", "question": "What errors can occur?", "applies_to": ["feature", "task", "bugfix"]},
  {"category": "Error Handling", "question": "How should each error be handled?", "applies_to": ["feature", "task", "bugfix"]},
  {"category": "Error Handling", "question": "What error messages should users see?", "applies_to": ["feature", "task", "bugfix"]},
  {"category": "Error Handling", "question": "Should errors be logged? Where?", "applies_to": ["feature", "task", "bugfix"]},
  {"category": "Error Handling", "question": "Are there retry scenarios?", "applies_to": ["feature", "task"]},
  {"category": "Error Handling", "question": "What's the fallback behavior?", "applies_to": ["feature", "task"]},

  {"category": "User Experience", "question": "What does the user see during loading?", "applies_to": ["feature", "task"]},
  {"category": "User Experience", "question": "What feedback indicates success?", "applies_to": ["feature", "task"]},
  {"category": "User Experience", "question": "What feedback indicates failure?", "applies_to": ["feature", "task", "bugfix"]},
  {"category": "User Experience", "question": "Is there a way to undo/cancel?", "applies_to": ["feature"]},
  {"category": "User Experience", "question": "What accessibility considerations apply?", "applies_to": ["feature"]},

  {"category": "Data & State", "question": "What data does this feature read?", "applies_to": ["feature", "task"]},
  {"category": "Data & State", "question": "What data does this feature write?", "applies_to": ["feature", "task"]},
  {"category": "Data & State", "question": "How is state persisted?", "applies_to": ["feature", "task"]},
  {"category": "Data & State", "question": "What happens to existing data on upgrade?", "applies_to": ["feature"]},
  {"category": "Data & State", "question": "Are there data validation rules?", "applies_to": ["feature", "task"]},

  {"category": "Integration Points", "question": "What APIs does this call?", "applies_to": ["feature", "task"]},
  {"category": "Integration Points", "question": "What APIs does this expose?", "applies_to": ["feature"]},
  {"category": "Integration Points", "question": "What events does this emit?", "applies_to": ["feature"]},
  {"category": "Integration Points", "question": "What events does this listen for?", "applies_to": ["feature"]},
  {"category": "Integration Points", "question": "Are there rate limits to consider?", "applies_to": ["feature", "task"]},

  {"category": "Performance & Scale", "question": "What's the expected response time?", "applies_to": ["feature", "task"]},
  {"category": "Performance & Scale", "question": "What's the expected throughput?", "applies_to": ["feature"]},
  {"category": "Performance & Scale", "question": "Are there caching opportunities?", "applies_to": ["feature", "task"]},
  {"category": "Performance & Scale", "question": "What are the memory constraints?", "applies_to": ["feature"]},
  {"category": "Performance & Scale", "question": "How does this scale?", "applies_to": ["feature"]},

  {"category": "Security", "question": "What authentication is required?", "applies_to": ["feature"]},
  {"category": "Security", "question": "What authorization rules apply?", "applies_to": ["feature"]},
  {"category": "Security", "question": "Is there sensitive data involved?", "applies_to": ["feature", "task"]},
  {"category": "Security", "question": "What input sanitization is needed?", "applies_to": ["feature", "task"]},
  {"category": "Security", "question": "Are there rate limiting requirements?", "applies_to": ["feature"]},

  {"category": "Testing", "question": "What unit tests are needed?", "applies_to": ["feature", "task", "bugfix"]},
  {"category": "Testing", "question": "What integration tests are needed?", "applies_to": ["feature", "task"]},
  {"category": "Testing", "question": "What edge cases must be tested?", "applies_to": ["feature", "task", "bugfix"]},
  {"category": "Testing", "question": "How is this manually tested?", "applies_to": ["feature", "task", "bugfix"]},

  {"category": "Operations", "question": "How is this feature toggled?", "applies_to": ["feature"]},
  {"category": "Operations", "question": "What monitoring is needed?", "applies_to": ["feature"]},
  {"category": "Operations", "question": "How is this debugged in production?", "applies_to": ["feature", "task"]},
  {"category": "Operations", "question": "What rollback procedure exists?", "applies_to": ["feature"]}
]
EOF
}

# Filter questions based on task type
# Args: task_type all_questions
interview_filter_questions() {
    local task_type="$1"
    local all_questions="$2"

    # Default to 'task' if type is not recognized
    local filter_type="$task_type"
    if [[ ! "$filter_type" =~ ^(feature|task|bugfix)$ ]]; then
        filter_type="task"
    fi

    echo "$all_questions" | jq --arg type "$filter_type" '
        [.[] | select(
            (.applies_to == null) or
            (.applies_to | contains([$type]))
        )]
    '
}

# ============================================================================
# Interview Engine
# ============================================================================

# Run interactive interview
# Args: task_id task_json questions
interview_run_interactive() {
    local task_id="$1"
    local task_json="$2"
    local questions="$3"

    local title
    title=$(echo "$task_json" | jq -r '.title')

    echo ""
    echo "========================================="
    echo "Interview: $title"
    echo "Task ID: $task_id"
    echo "========================================="
    echo ""

    local total
    total=$(echo "$questions" | jq 'length')

    local q_num=1
    local responses_json="[]"

    # Iterate through questions
    while read -r question_obj; do
        local category
        category=$(echo "$question_obj" | jq -r '.category')
        local question
        question=$(echo "$question_obj" | jq -r '.question')

        echo -e "${CYAN}[$q_num/$total] $category${NC}"
        echo "$question"
        echo -n "> "

        local answer
        read -r answer
        echo ""

        # Store response
        responses_json=$(echo "$responses_json" | jq --arg cat "$category" --arg q "$question" --arg ans "$answer" \
            '. += [{"category": $cat, "question": $q, "answer": $ans}]')

        ((q_num++))
    done < <(echo "$questions" | jq -c '.[]')

    echo "$responses_json"
}

# Run auto interview (AI-generated answers)
# Args: task_id task_json questions
interview_run_auto() {
    local task_id="$1"
    local task_json="$2"
    local questions="$3"

    local title
    title=$(echo "$task_json" | jq -r '.title')
    local description
    description=$(echo "$task_json" | jq -r '.description // ""')

    echo ""
    echo "========================================="
    echo "Auto Interview: $title"
    echo "Task ID: $task_id"
    echo "========================================="
    echo ""
    log_info "Generating AI responses based on task context..."
    echo ""

    # Build prompt for Claude to answer all questions
    local prompt
    local questions_list
    questions_list=$(echo "$questions" | jq -r '.[] | "[" + .category + "] " + .question')

    prompt=$(cat <<PROMPT
You are helping to refine a task specification by answering questions about it.

Task ID: $task_id
Title: $title
Description:
$description

Please answer the following questions about this task. Provide concise, specific answers based on the task description and common software engineering practices. If a question does not apply, say "N/A".

Questions:
$questions_list

Respond in JSON format as an array of objects with "category", "question", and "answer" fields:
[
  {"category": "...", "question": "...", "answer": "..."},
  ...
]
PROMPT
)

    # Call Claude to generate answers
    local ai_response
    if ai_response=$(echo "$prompt" | claude --print 2>&1); then
        # Try to extract JSON from response
        local responses_json
        # Look for JSON array in the response
        if responses_json=$(echo "$ai_response" | grep -o '\[.*\]' | head -1); then
            # Validate it's proper JSON
            if echo "$responses_json" | jq empty 2>/dev/null; then
                echo "$responses_json"
                return 0
            fi
        fi

        # Fallback: try to parse the whole response as JSON
        if echo "$ai_response" | jq empty 2>/dev/null; then
            echo "$ai_response"
            return 0
        fi

        # If JSON parsing fails, return error
        echo "ERROR: Failed to parse AI response as JSON" >&2
        return 1
    else
        echo "ERROR: Failed to get AI response" >&2
        return 1
    fi
}

# ============================================================================
# Spec Document Generation
# ============================================================================

# Generate specification document from interview responses
# Args: task_json responses_json output_file
interview_generate_spec() {
    local task_json="$1"
    local responses_json="$2"
    local output_file="$3"

    local task_id
    task_id=$(echo "$task_json" | jq -r '.id')
    local title
    title=$(echo "$task_json" | jq -r '.title')
    local description
    description=$(echo "$task_json" | jq -r '.description // ""')
    local task_type
    task_type=$(echo "$task_json" | jq -r '.type // "task"')

    # Generate markdown document
    cat > "$output_file" <<HEADER
# Task Specification: $title

## Overview
**Task ID:** $task_id
**Type:** $task_type
**Generated:** $(date +%Y-%m-%d)
**Interview Mode:** interactive

## Original Description
$description

HEADER

    # Group responses by category
    local categories
    categories=$(echo "$responses_json" | jq -r '[.[].category] | unique | .[]')

    while IFS= read -r category; do
        if [[ -n "$category" ]]; then
            echo "" >> "$output_file"
            echo "## $category" >> "$output_file"
            echo "" >> "$output_file"

            # Get all responses for this category
            echo "$responses_json" | jq -r --arg cat "$category" \
                '.[] | select(.category == $cat) | "### " + .question + "\n\n" + .answer + "\n"' >> "$output_file"
        fi
    done <<< "$categories"

    # Generate acceptance criteria from responses
    echo "" >> "$output_file"
    echo "## Acceptance Criteria (Generated)" >> "$output_file"
    echo "" >> "$output_file"
    echo "Based on interview responses:" >> "$output_file"
    echo "" >> "$output_file"

    # Extract key acceptance criteria from success criteria and functional requirements
    echo "$responses_json" | jq -r '
        .[] |
        select(.question | contains("success criteria") or contains("Success Criteria")) |
        .answer |
        split("\n") |
        .[] |
        select(length > 0) |
        "- [ ] " + .
    ' >> "$output_file" || true

    # If no success criteria found, add a placeholder
    if ! grep -q "^\- \[" "$output_file" 2>/dev/null; then
        echo "- [ ] Complete implementation as described" >> "$output_file"
        echo "- [ ] All tests passing" >> "$output_file"
        echo "- [ ] Error handling implemented" >> "$output_file"
    fi
}

# ============================================================================
# Command Implementation
# ============================================================================

cmd_interview_help() {
    cat <<'EOF'
cub interview <task-id> [options]

Deep questioning phase to refine task specifications before execution,
covering edge cases, error handling, and integration points.

USAGE:
  cub interview <task-id>              Interactive interview mode
  cub interview <task-id> --auto       AI-generated answers
  cub interview <task-id> --output FILE   Save to specific file
  cub interview --all                  Interview all open tasks (batch mode)

OPTIONS:
  --auto              Use AI to generate answers based on task context
  --output FILE       Save spec to specific file (default: specs/task-{id}-spec.md)
  --update-task       Update task description with spec (not implemented)
  --all               Interview all open tasks in batch mode
  --skip-categories   Skip specific categories (comma-separated)

EXAMPLES:
  # Interactive interview
  cub interview cub-h87.1

  # Auto mode (AI-generated answers)
  cub interview cub-h87.1 --auto

  # Save to custom location
  cub interview cub-h87.1 --output docs/task-spec.md

  # Interview all open tasks
  cub interview --all --auto

OUTPUT:
  Generates comprehensive markdown specification covering:
  - Functional requirements
  - Edge cases and error handling
  - User experience considerations
  - Data and state management
  - Integration points
  - Performance and security
  - Testing requirements
  - Operations and monitoring

SEE ALSO:
  cub run           Execute tasks
  cub status        Check progress
  cub explain       View task details
EOF
}

cmd_interview() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_interview_help
        return 0
    fi

    # Parse arguments
    local task_id=""
    local mode="interactive"
    local output_file=""
    local batch_mode=false
    local skip_categories=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --auto)
                mode="auto"
                shift
                ;;
            --output)
                output_file="$2"
                shift 2
                ;;
            --all)
                batch_mode=true
                shift
                ;;
            --skip-categories)
                skip_categories="$2"
                shift 2
                ;;
            --update-task)
                log_warn "Warning: --update-task not yet implemented"
                shift
                ;;
            -*)
                _log_error_console "Unknown option: $1"
                return 1
                ;;
            *)
                task_id="$1"
                shift
                ;;
        esac
    done

    # Validate arguments
    if [[ "$batch_mode" == "false" && -z "$task_id" ]]; then
        _log_error_console "Error: task-id required (or use --all for batch mode)"
        echo ""
        cmd_interview_help
        return 1
    fi

    # Batch mode not implemented yet
    if [[ "$batch_mode" == "true" ]]; then
        _log_error_console "Error: Batch mode (--all) not yet implemented"
        return 1
    fi

    # Get task
    local prd="${PROJECT_DIR}/prd.json"
    local task_json
    task_json=$(get_task "$prd" "$task_id" 2>/dev/null) || true

    if [[ -z "$task_json" || "$task_json" == "null" ]]; then
        _log_error_console "Error: Task not found: $task_id"
        return 1
    fi

    # Get task type for question filtering
    local task_type
    task_type=$(echo "$task_json" | jq -r '.type // "task"')

    # Load and filter questions
    local all_questions
    all_questions=$(interview_load_questions)
    local questions
    questions=$(interview_filter_questions "$task_type" "$all_questions")

    # Apply skip-categories filter if specified
    if [[ -n "$skip_categories" ]]; then
        local skip_array
        skip_array=$(echo "$skip_categories" | jq -R 'split(",")')
        questions=$(echo "$questions" | jq --argjson skip "$skip_array" '
            [.[] | select(.category as $cat | $skip | contains([$cat]) | not)]
        ')
    fi

    # Run interview
    local responses_json
    if [[ "$mode" == "auto" ]]; then
        responses_json=$(interview_run_auto "$task_id" "$task_json" "$questions")
        if [[ $? -ne 0 ]]; then
            _log_error_console "Error: Failed to generate AI responses"
            return 1
        fi
    else
        responses_json=$(interview_run_interactive "$task_id" "$task_json" "$questions")
    fi

    # Determine output file
    if [[ -z "$output_file" ]]; then
        mkdir -p "${PROJECT_DIR}/specs"
        output_file="${PROJECT_DIR}/specs/task-${task_id}-spec.md"
    fi

    # Generate spec document
    interview_generate_spec "$task_json" "$responses_json" "$output_file"

    echo ""
    log_success "Interview complete!"
    log_info "Specification saved to: $output_file"
    echo ""

    # Show preview
    if [[ -f "$output_file" ]]; then
        echo "Preview (first 20 lines):"
        echo "----------------------------------------"
        head -20 "$output_file"
        echo "----------------------------------------"
        echo ""
        log_info "View full spec: cat $output_file"
    fi

    return 0
}
