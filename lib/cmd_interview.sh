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
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE}Interview: $title${NC}"
    echo -e "${BLUE}Task ID: ${GREEN}$task_id${BLUE}${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo ""
    echo "Answer questions about this task to refine the specification."
    echo "Press Ctrl+C to quit, or leave a line blank to skip a question."
    echo ""

    local total
    total=$(echo "$questions" | jq 'length')

    local q_num=1
    local responses_json="[]"
    local current_category=""

    # Iterate through questions
    while read -r question_obj; do
        local category
        category=$(echo "$question_obj" | jq -r '.category')
        local question
        question=$(echo "$question_obj" | jq -r '.question')

        # Print category header when it changes
        if [[ "$category" != "$current_category" ]]; then
            if [[ -n "$current_category" ]]; then
                echo ""
            fi
            echo -e "${YELLOW}## $category${NC}"
            echo ""
            current_category="$category"
        fi

        # Show progress and question
        echo -e "${CYAN}[$q_num/$total]${NC} $question"
        echo -n -e "${GREEN}>${NC} "

        # Read answer with graceful handling
        local answer=""
        if read -r answer; then
            # User entered something (or empty line)
            echo ""

            # Store response (including empty answers for context)
            responses_json=$(echo "$responses_json" | jq --arg cat "$category" --arg q "$question" --arg ans "$answer" \
                '. += [{"category": $cat, "question": $q, "answer": $ans}]')
        else
            # EOF or error (e.g., Ctrl+C handled by trap)
            echo ""
            echo ""
            log_warn "Interview interrupted"
            return 1
        fi

        ((q_num++))
    done < <(echo "$questions" | jq -c '.[]')

    echo ""
    echo -e "${GREEN}✓ All questions answered${NC}"
    echo ""
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
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE}Auto Interview: $title${NC}"
    echo -e "${BLUE}Task ID: ${GREEN}$task_id${BLUE}${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo ""
    log_info "Generating AI responses based on task context..."
    echo -e "${YELLOW}Processing $(echo "$questions" | jq 'length') questions...${NC}"
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
    local exit_code
    ai_response=$(echo "$prompt" | claude --print 2>&1)
    exit_code=$?

    if [[ $exit_code -eq 0 && -n "$ai_response" ]]; then
        # Try to extract JSON from response
        local responses_json

        # First, try to parse the whole response as JSON
        if echo "$ai_response" | jq empty 2>/dev/null; then
            echo "$ai_response"
            return 0
        fi

        # Look for JSON array in the response (between [ and ])
        # Extract content between first [ and last ]
        responses_json=$(echo "$ai_response" | grep -o '\[.*' | head -1)
        if [[ -n "$responses_json" ]]; then
            # Ensure it ends with ]
            if [[ ! "$responses_json" == *"]" ]]; then
                responses_json="${responses_json%\]*}]"
            fi
            # Try to validate as JSON
            if echo "$responses_json" | jq empty 2>/dev/null; then
                echo "$responses_json"
                return 0
            fi
        fi

        # If JSON parsing fails, show warning and return error
        log_warn "AI response parsing failed. Response was:"
        echo "$ai_response" | head -10 >&2
        echo "ERROR: Failed to parse AI response as JSON" >&2
        return 1
    else
        echo "ERROR: Failed to get AI response (exit code: $exit_code)" >&2
        if [[ -n "$ai_response" ]]; then
            echo "Response: $ai_response" >&2
        fi
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

    # Detect backend for the project directory (not current working directory)
    # This ensures we use the correct backend (beads vs json)
    if [[ -z "${_TASK_BACKEND:-}" ]]; then
        # Only detect once - reuse if already set
        if command -v detect_backend &>/dev/null; then
            detect_backend "$PROJECT_DIR" >/dev/null
        fi
    fi

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
        if [[ $? -ne 0 ]]; then
            # User interrupted (Ctrl+C)
            return 1
        fi
    fi

    # Determine output file
    if [[ -z "$output_file" ]]; then
        mkdir -p "${PROJECT_DIR}/specs"
        output_file="${PROJECT_DIR}/specs/task-${task_id}-spec.md"
    fi

    # Generate spec document
    interview_generate_spec "$task_json" "$responses_json" "$output_file"

    echo ""
    echo -e "${GREEN}✓ Interview complete!${NC}"
    log_info "Specification saved to: $output_file"
    echo ""

    # Show preview
    if [[ -f "$output_file" ]]; then
        echo -e "${BLUE}Preview (first 20 lines):${NC}"
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        head -20 "$output_file"
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        log_info "View full spec: cat $output_file"
    fi

    return 0
}
