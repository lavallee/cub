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

  {"category": "User Experience", "question": "What does the user see during loading?", "applies_to": ["feature", "task"], "id": "ux_loading"},
  {"category": "User Experience", "question": "What feedback indicates success?", "applies_to": ["feature", "task"], "id": "ux_success"},
  {"category": "User Experience", "question": "What feedback indicates failure?", "applies_to": ["feature", "task", "bugfix"], "id": "ux_failure"},
  {"category": "User Experience", "question": "Is there a way to undo/cancel?", "applies_to": ["feature"], "id": "ux_undo", "skip_if": {"question_ids": ["data_write"], "answers_match": ["^(none|n\\/a|no|not applicable|nothing)$"]}},
  {"category": "User Experience", "question": "What accessibility considerations apply?", "applies_to": ["feature"], "requires_labels": ["ui", "frontend", "web"]},

  {"category": "Data & State", "question": "What data does this feature read?", "applies_to": ["feature", "task"], "id": "data_read"},
  {"category": "Data & State", "question": "What data does this feature write?", "applies_to": ["feature", "task"], "id": "data_write"},
  {"category": "Data & State", "question": "How is state persisted?", "applies_to": ["feature", "task"], "id": "state_persist", "skip_if": {"question_ids": ["data_write"], "answers_match": ["^(none|n\\/a|no|not applicable|nothing)$"]}},
  {"category": "Data & State", "question": "What happens to existing data on upgrade?", "applies_to": ["feature"], "skip_if": {"question_ids": ["data_read", "data_write"], "answers_match": ["^(none|n\\/a|no|not applicable|nothing)$"]}},
  {"category": "Data & State", "question": "Are there data validation rules?", "applies_to": ["feature", "task"], "id": "data_validation"},

  {"category": "Integration Points", "question": "What APIs does this call?", "applies_to": ["feature", "task"], "requires_labels": ["api", "integration"], "id": "apis_call"},
  {"category": "Integration Points", "question": "What APIs does this expose?", "applies_to": ["feature"], "requires_labels": ["api"], "id": "apis_expose"},
  {"category": "Integration Points", "question": "What events does this emit?", "applies_to": ["feature"], "requires_labels": ["events", "pub-sub"], "id": "events_emit"},
  {"category": "Integration Points", "question": "What events does this listen for?", "applies_to": ["feature"], "requires_labels": ["events", "pub-sub"], "id": "events_listen"},
  {"category": "Integration Points", "question": "Are there rate limits to consider?", "applies_to": ["feature", "task"], "requires_labels": ["api", "external"], "id": "rate_limits", "skip_if": {"question_ids": ["apis_call"], "answers_match": ["^(none|n\\/a|no|not applicable)$"]}},

  {"category": "Performance & Scale", "question": "What's the expected response time?", "applies_to": ["feature", "task"], "requires_labels": ["performance"]},
  {"category": "Performance & Scale", "question": "What's the expected throughput?", "applies_to": ["feature"], "requires_labels": ["performance", "scalability"]},
  {"category": "Performance & Scale", "question": "Are there caching opportunities?", "applies_to": ["feature", "task"], "requires_labels": ["performance", "caching"]},
  {"category": "Performance & Scale", "question": "What are the memory constraints?", "applies_to": ["feature"], "requires_labels": ["performance", "memory"]},
  {"category": "Performance & Scale", "question": "How does this scale?", "applies_to": ["feature"], "requires_labels": ["scalability"]},

  {"category": "Security", "question": "What authentication is required?", "applies_to": ["feature"], "requires_labels": ["auth", "security"]},
  {"category": "Security", "question": "What authorization rules apply?", "applies_to": ["feature"], "requires_labels": ["auth", "security"]},
  {"category": "Security", "question": "Is there sensitive data involved?", "applies_to": ["feature", "task"], "requires_labels": ["security", "data"]},
  {"category": "Security", "question": "What input sanitization is needed?", "applies_to": ["feature", "task"], "requires_labels": ["security", "validation"]},
  {"category": "Security", "question": "Are there rate limiting requirements?", "applies_to": ["feature"], "requires_labels": ["security", "api"]},

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

# Detect technology stack from project files
# Returns: JSON array of detected tech labels
interview_detect_tech_stack() {
    local tech_stack="[]"

    # Check for common technology indicators
    if [[ -f "package.json" ]]; then
        tech_stack=$(echo "$tech_stack" | jq '. + ["javascript", "nodejs"]')
        # Check for specific frameworks
        if grep -q "react" "package.json" 2>/dev/null; then
            tech_stack=$(echo "$tech_stack" | jq '. + ["react", "frontend"]')
        fi
        if grep -q "express" "package.json" 2>/dev/null; then
            tech_stack=$(echo "$tech_stack" | jq '. + ["express", "api", "backend"]')
        fi
        if grep -q "next" "package.json" 2>/dev/null; then
            tech_stack=$(echo "$tech_stack" | jq '. + ["nextjs", "frontend"]')
        fi
    fi

    if [[ -f "go.mod" ]]; then
        tech_stack=$(echo "$tech_stack" | jq '. + ["go", "golang"]')
    fi

    if [[ -f "requirements.txt" || -f "pyproject.toml" || -f "setup.py" ]]; then
        tech_stack=$(echo "$tech_stack" | jq '. + ["python"]')
    fi

    if [[ -f "Cargo.toml" ]]; then
        tech_stack=$(echo "$tech_stack" | jq '. + ["rust"]')
    fi

    if [[ -f "pom.xml" || -f "build.gradle" ]]; then
        tech_stack=$(echo "$tech_stack" | jq '. + ["java"]')
    fi

    # Check for databases
    if [[ -f "docker-compose.yml" ]]; then
        if grep -q "postgres" "docker-compose.yml" 2>/dev/null; then
            tech_stack=$(echo "$tech_stack" | jq '. + ["postgres", "database"]')
        fi
        if grep -q "redis" "docker-compose.yml" 2>/dev/null; then
            tech_stack=$(echo "$tech_stack" | jq '. + ["redis", "cache"]')
        fi
        if grep -q "mongodb" "docker-compose.yml" 2>/dev/null; then
            tech_stack=$(echo "$tech_stack" | jq '. + ["mongodb", "database"]')
        fi
    fi

    # Check for bash/shell projects
    if ls *.sh &>/dev/null || [[ -d "lib" && $(ls lib/*.sh 2>/dev/null | wc -l) -gt 0 ]]; then
        tech_stack=$(echo "$tech_stack" | jq '. + ["bash", "shell"]')
    fi

    echo "$tech_stack"
}

# Filter questions based on task type, labels, and tech stack
# Args: task_json all_questions
interview_filter_questions() {
    local task_json="$1"
    local all_questions="$2"

    # Extract task metadata
    local task_type
    task_type=$(echo "$task_json" | jq -r '.type // .issue_type // "task"')

    local task_labels
    task_labels=$(echo "$task_json" | jq -r '.labels // [] | @json')

    # Default to 'task' if type is not recognized
    local filter_type="$task_type"
    if [[ ! "$filter_type" =~ ^(feature|task|bugfix|epic)$ ]]; then
        filter_type="task"
    fi

    # Detect technology stack
    local tech_stack
    tech_stack=$(interview_detect_tech_stack)

    # Combine task labels with detected tech stack
    local combined_labels
    combined_labels=$(jq -n --argjson task "$task_labels" --argjson tech "$tech_stack" '$task + $tech')

    # Filter questions based on:
    # 1. Task type (applies_to)
    # 2. Labels (requires_labels) - question included if ANY label matches
    # 3. Technology stack (requires_tech) - question included if ANY tech matches
    echo "$all_questions" | jq --arg type "$filter_type" --argjson labels "$combined_labels" '
        [.[] | select(
            # Check task type filter
            (
                (.applies_to == null) or
                (.applies_to | contains([$type]))
            ) and
            # Check label filter (if question has requires_labels, at least one must match)
            # Match if: exact match OR task label contains required label (e.g., "authentication" contains "auth")
            (
                (.requires_labels == null) or
                ((.requires_labels | length) == 0) or
                ([.requires_labels[] as $rlabel | $labels[] | select(. == $rlabel or (. | contains($rlabel)))] | length > 0)
            ) and
            # Check tech filter (if question has requires_tech, at least one must match)
            (
                (.requires_tech == null) or
                ((.requires_tech | length) == 0) or
                ([.requires_tech[] as $rtech | $labels[] | select(. == $rtech or (. | contains($rtech)))] | length > 0)
            )
        )]
    '
}

# ============================================================================
# Interview Engine
# ============================================================================

# Check if a question should be skipped based on previous answers
# Args: question_obj responses_json
# Returns: 0 if should skip, 1 if should ask
interview_should_skip_question() {
    local question_obj="$1"
    local responses_json="$2"

    # Check if question has skip_if condition
    local skip_if
    skip_if=$(echo "$question_obj" | jq -r '.skip_if // "null"')

    if [[ "$skip_if" == "null" ]]; then
        return 1  # Don't skip
    fi

    # Extract skip condition
    local question_ids
    question_ids=$(echo "$skip_if" | jq -r '.question_ids[]')

    local answers_match
    answers_match=$(echo "$skip_if" | jq -r '.answers_match[]')

    # Check if any of the referenced questions have matching answers
    while read -r ref_id; do
        # Find the answer for this question ID
        local ref_answer
        ref_answer=$(echo "$responses_json" | jq -r --arg id "$ref_id" '
            .[] | select(.question_id == $id) | .answer
        ')

        # If we have an answer, check if it matches the skip pattern
        if [[ -n "$ref_answer" ]]; then
            while read -r pattern; do
                if echo "$ref_answer" | grep -qiE "$pattern"; then
                    return 0  # Skip this question
                fi
            done <<< "$answers_match"
        fi
    done <<< "$question_ids"

    return 1  # Don't skip
}

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
        # Check if we should skip this question based on previous answers
        if interview_should_skip_question "$question_obj" "$responses_json"; then
            local skipped_question
            skipped_question=$(echo "$question_obj" | jq -r '.question')
            echo -e "${BLUE}[Skipped] $skipped_question (not applicable based on previous answers)${NC}" >&2
            continue
        fi

        local category
        category=$(echo "$question_obj" | jq -r '.category')
        local question
        question=$(echo "$question_obj" | jq -r '.question')
        local question_id
        question_id=$(echo "$question_obj" | jq -r '.id // ""')

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

            # Store response with question ID if available
            if [[ -n "$question_id" ]]; then
                responses_json=$(echo "$responses_json" | jq --arg cat "$category" --arg q "$question" --arg ans "$answer" --arg qid "$question_id" \
                    '. += [{"category": $cat, "question": $q, "answer": $ans, "question_id": $qid}]')
            else
                responses_json=$(echo "$responses_json" | jq --arg cat "$category" --arg q "$question" --arg ans "$answer" \
                    '. += [{"category": $cat, "question": $q, "answer": $ans}]')
            fi
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

# Gather codebase context for AI interview
# Returns: String with relevant codebase information
interview_gather_codebase_context() {
    local context=""

    # Detect project structure
    context+="Project Structure:\n"
    if [[ -f "package.json" ]]; then
        context+="- Node.js project with package.json\n"
        if [[ -f "package-lock.json" ]]; then
            context+="- Uses npm for package management\n"
        fi
    fi
    if [[ -f "go.mod" ]]; then
        context+="- Go project\n"
    fi
    if [[ -f "requirements.txt" || -f "pyproject.toml" ]]; then
        context+="- Python project\n"
    fi
    if [[ -f "Cargo.toml" ]]; then
        context+="- Rust project\n"
    fi
    if [[ -d "tests" ]]; then
        context+="- Has tests/ directory\n"
    fi
    if [[ -f "docker-compose.yml" ]]; then
        context+="- Uses Docker Compose\n"
    fi

    # List key files (limit to avoid overwhelming the prompt)
    local key_files
    key_files=$(find . -maxdepth 2 -type f -name "*.md" -o -name "*.sh" -o -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.go" 2>/dev/null | head -20 | sed 's|^\./||')
    if [[ -n "$key_files" ]]; then
        context+="\nKey Files:\n"
        while IFS= read -r file; do
            context+="- $file\n"
        done <<< "$key_files"
    fi

    echo -e "$context"
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
    local task_type
    task_type=$(echo "$task_json" | jq -r '.type // "task"')
    local labels
    labels=$(echo "$task_json" | jq -r '.labels // [] | join(", ")')

    echo ""
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE}Auto Interview: $title${NC}"
    echo -e "${BLUE}Task ID: ${GREEN}$task_id${BLUE}${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo ""
    log_info "Analyzing codebase context..."

    # Gather codebase context
    local codebase_context
    codebase_context=$(interview_gather_codebase_context)

    log_info "Generating AI responses based on task and codebase context..."
    echo -e "${YELLOW}Processing $(echo "$questions" | jq 'length') questions with Sonnet model...${NC}"
    echo ""

    # Process questions one by one with skip logic support
    local responses_json="[]"
    local q_num=1
    local total
    total=$(echo "$questions" | jq 'length')
    local current_category=""

    while read -r question_obj; do
        # Check if we should skip this question based on previous answers
        if interview_should_skip_question "$question_obj" "$responses_json"; then
            local skipped_question
            skipped_question=$(echo "$question_obj" | jq -r '.question')
            echo -e "${BLUE}[Skipped $q_num/$total] $skipped_question${NC}" >&2
            ((q_num++))
            continue
        fi

        local category
        category=$(echo "$question_obj" | jq -r '.category')
        local question
        question=$(echo "$question_obj" | jq -r '.question')
        local question_id
        question_id=$(echo "$question_obj" | jq -r '.id // ""')

        # Print category header when it changes
        if [[ "$category" != "$current_category" ]]; then
            if [[ -n "$current_category" ]]; then
                echo ""
            fi
            echo -e "${YELLOW}## $category${NC}"
            current_category="$category"
        fi

        echo -e "${CYAN}[$q_num/$total]${NC} $question"

        # Build focused prompt for this specific question
        local prompt
        prompt="You are helping to refine a task specification by answering a specific question about it.

Task Context:
- Task ID: $task_id
- Title: $title
- Type: $task_type
- Labels: $labels
- Description: $description

Codebase Context:
$codebase_context

Question Category: $category
Question: $question

Instructions:
- Provide a concise, specific answer based on the task description and codebase context
- If the question does not apply to this task, respond with \"N/A\" or \"Not applicable\"
- Focus on practical implementation details
- Consider the project's technology stack and structure
- Be brief but comprehensive (1-3 sentences or a short list)

Answer the question directly without repeating it. Respond with just the answer text, no JSON or additional formatting."

        # Call Claude with sonnet model to generate answer
        local ai_answer
        local exit_code
        ai_answer=$(echo "$prompt" | claude --print --model sonnet 2>&1)
        exit_code=$?

        if [[ $exit_code -eq 0 && -n "$ai_answer" ]]; then
            # Clean up the answer (remove extra whitespace)
            ai_answer=$(echo "$ai_answer" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

            echo -e "${GREEN}>${NC} $ai_answer"
            echo ""

            # Store response with question ID if available
            if [[ -n "$question_id" ]]; then
                responses_json=$(echo "$responses_json" | jq --arg cat "$category" --arg q "$question" --arg ans "$ai_answer" --arg qid "$question_id" \
                    '. += [{"category": $cat, "question": $q, "answer": $ans, "question_id": $qid}]')
            else
                responses_json=$(echo "$responses_json" | jq --arg cat "$category" --arg q "$question" --arg ans "$ai_answer" \
                    '. += [{"category": $cat, "question": $q, "answer": $ans}]')
            fi
        else
            log_warn "Failed to get AI response for question (exit code: $exit_code)"
            echo -e "${RED}> [Error generating answer]${NC}"
            echo ""

            # Store error response
            if [[ -n "$question_id" ]]; then
                responses_json=$(echo "$responses_json" | jq --arg cat "$category" --arg q "$question" --arg ans "N/A" --arg qid "$question_id" \
                    '. += [{"category": $cat, "question": $q, "answer": $ans, "question_id": $qid}]')
            else
                responses_json=$(echo "$responses_json" | jq --arg cat "$category" --arg q "$question" --arg ans "N/A" \
                    '. += [{"category": $cat, "question": $q, "answer": $ans}]')
            fi
        fi

        ((q_num++))
    done < <(echo "$questions" | jq -c '.[]')

    echo ""
    echo -e "${GREEN}✓ All questions processed${NC}"
    echo ""
    echo "$responses_json"
}

# ============================================================================
# Spec Document Generation
# ============================================================================

# Extract acceptance criteria from interview responses
# Generates actionable checkbox list from various question types
# Args: responses_json
# Output: Markdown checkbox list to stdout
interview_extract_acceptance_criteria() {
    local responses_json="$1"
    local temp_file="${TMPDIR:-/tmp}/cub_criteria_$$"

    # Use temp file to collect criteria across subshells
    : > "$temp_file"

    # Extract from success criteria questions (highest priority)
    echo "$responses_json" | jq -r '
        .[] |
        select(.question | test("success criteria"; "i")) |
        .answer |
        split("\n") |
        .[] |
        select(length > 0) |
        select(. != "N/A" and . != "n/a" and . != "None" and . != "none")
    ' 2>/dev/null | while IFS= read -r line; do
        # Remove common bullet points and numbering
        line=$(echo "$line" | sed -E 's/^[[:space:]]*[-*•][[:space:]]*//' | sed -E 's/^[[:space:]]*[0-9]+\.[[:space:]]*//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        if [[ -n "$line" ]]; then
            echo "- [ ] $line" >> "$temp_file"
        fi
    done

    # Extract from testing requirements
    echo "$responses_json" | jq -r '
        .[] |
        select(.question | test("unit tests|integration tests|edge cases.*tested"; "i")) |
        .answer |
        split("\n") |
        .[] |
        select(length > 0) |
        select(. != "N/A" and . != "n/a" and . != "None" and . != "none")
    ' 2>/dev/null | while IFS= read -r line; do
        line=$(echo "$line" | sed -E 's/^[[:space:]]*[-*•][[:space:]]*//' | sed -E 's/^[[:space:]]*[0-9]+\.[[:space:]]*//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        if [[ -n "$line" ]] && ! echo "$line" | grep -q "^\- \["; then
            # Prefix with "Test:" if not already test-focused
            if ! echo "$line" | grep -qi "test"; then
                echo "- [ ] Test: $line" >> "$temp_file"
            else
                echo "- [ ] $line" >> "$temp_file"
            fi
        fi
    done

    # Extract from error handling requirements
    local error_output
    error_output=$(mktemp)
    echo "$responses_json" | jq -r '
        .[] |
        select(.question | test("error.*handled|error messages|fallback"; "i")) |
        select(.answer | test("^(N/A|n/a|None|none)$") | not) |
        .answer |
        split("\n") |
        .[] |
        select(length > 0)
    ' 2>/dev/null | while IFS= read -r line; do
        line=$(echo "$line" | sed -E 's/^[[:space:]]*[-*•][[:space:]]*//' | sed -E 's/^[[:space:]]*[0-9]+\.[[:space:]]*//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        if [[ -n "$line" ]] && ! echo "$line" | grep -q "^\- \["; then
            if ! echo "$line" | grep -qi "error"; then
                echo "- [ ] Error handling: $line" >> "$error_output"
            else
                echo "- [ ] $line" >> "$error_output"
            fi
        fi
    done

    # Add error criteria to main file and add summary if any found
    if [[ -s "$error_output" ]]; then
        cat "$error_output" >> "$temp_file"
        echo "- [ ] All error scenarios handled gracefully" >> "$temp_file"
    fi
    rm -f "$error_output"

    # Extract from data validation requirements
    echo "$responses_json" | jq -r '
        .[] |
        select(.question | test("validation rules|input.*accept"; "i")) |
        select(.answer | test("^(N/A|n/a|None|none)$") | not) |
        .answer |
        split("\n") |
        .[] |
        select(length > 0)
    ' 2>/dev/null | head -3 | while IFS= read -r line; do
        line=$(echo "$line" | sed -E 's/^[[:space:]]*[-*•][[:space:]]*//' | sed -E 's/^[[:space:]]*[0-9]+\.[[:space:]]*//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        if [[ -n "$line" ]] && ! echo "$line" | grep -q "^\- \["; then
            if ! echo "$line" | grep -qi "validat"; then
                echo "- [ ] Validate: $line" >> "$temp_file"
            else
                echo "- [ ] $line" >> "$temp_file"
            fi
        fi
    done

    # Extract from output/user feedback requirements
    echo "$responses_json" | jq -r '
        .[] |
        select(.question | test("output.*produce|feedback.*success|feedback.*failure"; "i")) |
        select(.answer | test("^(N/A|n/a|None|none)$") | not) |
        .answer |
        split("\n") |
        .[] |
        select(length > 0)
    ' 2>/dev/null | head -2 | while IFS= read -r line; do
        line=$(echo "$line" | sed -E 's/^[[:space:]]*[-*•][[:space:]]*//' | sed -E 's/^[[:space:]]*[0-9]+\.[[:space:]]*//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        if [[ -n "$line" ]] && ! echo "$line" | grep -q "^\- \["; then
            if ! echo "$line" | grep -qi "feedback\|output\|display\|show"; then
                echo "- [ ] Display: $line" >> "$temp_file"
            else
                echo "- [ ] $line" >> "$temp_file"
            fi
        fi
    done

    # Check if we found any criteria
    if [[ -s "$temp_file" ]]; then
        # Output collected criteria
        cat "$temp_file"
        # Always add test passing criterion
        echo "- [ ] All tests passing"
    else
        # No criteria found - try primary goal
        local primary_goal
        primary_goal=$(echo "$responses_json" | jq -r '
            .[] |
            select(.question | test("primary.*goal|user goal"; "i")) |
            .answer
        ' 2>/dev/null | head -1 || true)

        if [[ -n "$primary_goal" ]] && [[ "$primary_goal" != "N/A" ]] && [[ "$primary_goal" != "n/a" ]]; then
            echo "- [ ] $primary_goal"
            echo "- [ ] All tests passing"
            echo "- [ ] Error handling implemented"
        else
            # Final fallback to generic criteria
            echo "- [ ] Complete implementation as described"
            echo "- [ ] All tests passing"
            echo "- [ ] Error handling implemented"
        fi
    fi

    # Cleanup
    rm -f "$temp_file"
}

# Generate specification document from interview responses
# Args: task_json responses_json output_file mode
interview_generate_spec() {
    local task_json="$1"
    local responses_json="$2"
    local output_file="$3"
    local mode="${4:-interactive}"

    local task_id
    task_id=$(echo "$task_json" | jq -r '.id')
    local title
    title=$(echo "$task_json" | jq -r '.title')
    local description
    description=$(echo "$task_json" | jq -r '.description // ""')
    local task_type
    task_type=$(echo "$task_json" | jq -r '.type // "task"')

    # Generate markdown document header
    cat > "$output_file" <<HEADER
# Task Specification: $title

## Overview
**Task ID:** $task_id
**Type:** $task_type
**Generated:** $(date +%Y-%m-%d)
**Interview Mode:** $mode

## Original Description
$description

HEADER

    # Generate summary overview section
    echo "" >> "$output_file"
    echo "## Summary" >> "$output_file"
    echo "" >> "$output_file"

    # Extract key summary points from responses
    local primary_goal
    primary_goal=$(echo "$responses_json" | jq -r '.[] | select(.question | contains("primary") and contains("goal")) | .answer' | head -1)
    if [[ -n "$primary_goal" && "$primary_goal" != "null" ]]; then
        echo "**Primary Goal:** $primary_goal" >> "$output_file"
        echo "" >> "$output_file"
    fi

    local inputs
    inputs=$(echo "$responses_json" | jq -r '.[] | select(.question | contains("inputs") or contains("Inputs")) | .answer' | head -1)
    if [[ -n "$inputs" && "$inputs" != "null" ]]; then
        echo "**Inputs:** $inputs" >> "$output_file"
        echo "" >> "$output_file"
    fi

    local outputs
    outputs=$(echo "$responses_json" | jq -r '.[] | select(.question | contains("outputs") or contains("Outputs")) | .answer' | head -1)
    if [[ -n "$outputs" && "$outputs" != "null" ]]; then
        echo "**Outputs:** $outputs" >> "$output_file"
        echo "" >> "$output_file"
    fi

    # Count responses by category for summary
    local total_responses
    total_responses=$(echo "$responses_json" | jq 'length')
    local categories_covered
    categories_covered=$(echo "$responses_json" | jq -r '[.[].category] | unique | length')
    echo "**Coverage:** $total_responses responses across $categories_covered categories" >> "$output_file"
    echo "" >> "$output_file"

    # Define canonical category order (matches question bank order)
    local category_order=(
        "Functional Requirements"
        "Edge Cases"
        "Error Handling"
        "User Experience"
        "Data & State"
        "Integration Points"
        "Performance & Scale"
        "Security"
        "Testing"
        "Operations"
    )

    # Output categories in logical order
    for category in "${category_order[@]}"; do
        # Check if this category has responses
        local has_responses
        has_responses=$(echo "$responses_json" | jq --arg cat "$category" '[.[] | select(.category == $cat)] | length')

        if [[ "$has_responses" -gt 0 ]]; then
            echo "" >> "$output_file"
            echo "## $category" >> "$output_file"
            echo "" >> "$output_file"

            # Get all responses for this category
            echo "$responses_json" | jq -r --arg cat "$category" \
                '.[] | select(.category == $cat) | "### " + .question + "\n\n" + .answer + "\n"' >> "$output_file"
        fi
    done

    # Generate acceptance criteria from responses
    echo "" >> "$output_file"
    echo "## Acceptance Criteria (Generated)" >> "$output_file"
    echo "" >> "$output_file"
    echo "Based on interview responses:" >> "$output_file"
    echo "" >> "$output_file"

    # Extract acceptance criteria using the dedicated function
    interview_extract_acceptance_criteria "$responses_json" >> "$output_file"
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
  cub interview <task-id> --auto       AI-generated answers with review flow
  cub interview <task-id> --output FILE   Save to specific file
  cub interview --all                  Interview all open tasks (batch mode)

OPTIONS:
  --auto              Use AI to generate answers based on task context
  --skip-review       Skip review/approval flow (use auto answers as-is)
  --output FILE       Save spec to specific file (default: specs/task-{id}-spec.md)
  --update-task       Update task description with spec (not implemented)
  --all               Interview all open tasks in batch mode
  --skip-categories   Skip specific categories (comma-separated)

AUTO MODE WITH REVIEW FLOW:
  When using --auto, generated answers are presented for your review:
  - Accept answers you agree with
  - Edit answers you want to change
  - Regenerate answers you want AI to try again
  - Skip to keep answers as-is

EXAMPLES:
  # Interactive interview
  cub interview cub-h87.1

  # Auto mode with review (recommended)
  cub interview cub-h87.1 --auto

  # Auto mode, skip review phase
  cub interview cub-h87.1 --auto --skip-review

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

# ============================================================================
# Review and Approval Flow
# ============================================================================

# Display review menu for a single answer
# Args: question_num total question answer index
# Returns: User's choice (accept|edit|regenerate|skip)
interview_review_answer() {
    local question_num="$1"
    local total="$2"
    local question="$3"
    local answer="$4"

    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}Question $question_num/$total:${NC} $question"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Generated answer:"
    echo -e "${GREEN}\"$answer\"${NC}"
    echo ""
    echo "Options:"
    echo -e "  ${YELLOW}a${NC} - Accept this answer"
    echo -e "  ${YELLOW}e${NC} - Edit this answer"
    echo -e "  ${YELLOW}r${NC} - Regenerate this answer"
    echo -e "  ${YELLOW}s${NC} - Skip to next (keep as-is)"
    echo -e "  ${YELLOW}q${NC} - Quit review"
    echo ""
    echo -n -e "${GREEN}>${NC} "

    local choice=""
    read -r choice
    echo ""

    case "$choice" in
        a|A) echo "accept" ;;
        e|E) echo "edit" ;;
        r|R) echo "regenerate" ;;
        s|S) echo "skip" ;;
        q|Q) echo "quit" ;;
        *)
            echo -e "${RED}Invalid choice. Please enter a, e, r, s, or q.${NC}"
            interview_review_answer "$question_num" "$total" "$question" "$answer"
            ;;
    esac
}

# Allow user to edit an answer
# Args: original_answer
# Returns: Edited answer
interview_edit_answer() {
    local original="$1"

    echo -e "${YELLOW}Edit the answer below (press Ctrl+D to finish, Ctrl+C to cancel):${NC}"
    echo ""
    echo -e "${BLUE}Current answer:${NC}"
    echo "$original"
    echo ""
    echo -e "${BLUE}Enter new answer:${NC}"

    local edited=""
    local line=""
    while IFS= read -r line; do
        if [[ -z "$edited" ]]; then
            edited="$line"
        else
            edited="$edited"$'\n'"$line"
        fi
    done

    # Clean up newlines and return
    edited=$(echo -n "$edited" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    echo "$edited"
}

# Regenerate answer for a specific question
# Args: task_id task_json category question
# Returns: Regenerated answer
interview_regenerate_answer() {
    local task_id="$1"
    local task_json="$2"
    local category="$3"
    local question="$4"

    local title
    title=$(echo "$task_json" | jq -r '.title')
    local description
    description=$(echo "$task_json" | jq -r '.description // ""')
    local task_type
    task_type=$(echo "$task_json" | jq -r '.type // "task"')
    local labels
    labels=$(echo "$task_json" | jq -r '.labels // [] | join(", ")')

    # Gather codebase context
    local codebase_context
    codebase_context=$(interview_gather_codebase_context)

    echo -e "${YELLOW}Regenerating answer for this question...${NC}"

    # Build focused prompt for this specific question
    local prompt
    prompt="You are helping to refine a task specification by answering a specific question about it.

Task Context:
- Task ID: $task_id
- Title: $title
- Type: $task_type
- Labels: $labels
- Description: $description

Codebase Context:
$codebase_context

Question Category: $category
Question: $question

Instructions:
- Provide a concise, specific answer based on the task description and codebase context
- If the question does not apply to this task, respond with \"N/A\" or \"Not applicable\"
- Focus on practical implementation details
- Consider the project's technology stack and structure
- Be brief but comprehensive (1-3 sentences or a short list)

Answer the question directly without repeating it. Respond with just the answer text, no JSON or additional formatting."

    # Call Claude with sonnet model to generate answer
    local ai_answer
    local exit_code
    ai_answer=$(echo "$prompt" | claude --print --model sonnet 2>&1)
    exit_code=$?

    if [[ $exit_code -eq 0 && -n "$ai_answer" ]]; then
        # Clean up the answer (remove extra whitespace)
        ai_answer=$(echo "$ai_answer" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        echo "$ai_answer"
    else
        log_warn "Failed to regenerate answer (exit code: $exit_code)"
        echo "N/A"
    fi
}

# Run review flow for generated answers
# Args: task_id task_json responses_json questions
# Returns: Updated responses_json after user review
interview_run_review() {
    local task_id="$1"
    local task_json="$2"
    local responses_json="$3"
    local questions="$4"

    local title
    title=$(echo "$task_json" | jq -r '.title')

    echo ""
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE}Review Generated Answers${NC}"
    echo -e "${BLUE}Task: $title${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo ""
    echo "Review each AI-generated answer. You can accept, edit, or regenerate."
    echo ""

    local total
    total=$(echo "$responses_json" | jq 'length')

    local q_num=1
    local updated_responses="[]"

    while read -r response_obj; do
        local question
        question=$(echo "$response_obj" | jq -r '.question')
        local answer
        answer=$(echo "$response_obj" | jq -r '.answer')
        local category
        category=$(echo "$response_obj" | jq -r '.category')
        local question_id
        question_id=$(echo "$response_obj" | jq -r '.question_id // ""')

        while true; do
            local choice
            choice=$(interview_review_answer "$q_num" "$total" "$question" "$answer")

            case "$choice" in
                accept)
                    # Store unchanged
                    if [[ -n "$question_id" ]]; then
                        updated_responses=$(echo "$updated_responses" | jq --arg cat "$category" --arg q "$question" --arg ans "$answer" --arg qid "$question_id" \
                            '. += [{"category": $cat, "question": $q, "answer": $ans, "question_id": $qid}]')
                    else
                        updated_responses=$(echo "$updated_responses" | jq --arg cat "$category" --arg q "$question" --arg ans "$answer" \
                            '. += [{"category": $cat, "question": $q, "answer": $ans}]')
                    fi
                    break
                    ;;
                edit)
                    # Get edited answer from user
                    local edited_answer
                    edited_answer=$(interview_edit_answer "$answer")
                    answer="$edited_answer"
                    echo -e "${GREEN}✓ Answer updated${NC}"
                    # Continue loop to show menu again
                    ;;
                regenerate)
                    # Regenerate answer from AI
                    echo ""
                    local new_answer
                    new_answer=$(interview_regenerate_answer "$task_id" "$task_json" "$category" "$question")
                    answer="$new_answer"
                    echo -e "${GREEN}✓ New answer generated:${NC}"
                    echo "\"$new_answer\""
                    # Continue loop to show menu again
                    ;;
                skip)
                    # Keep original answer
                    if [[ -n "$question_id" ]]; then
                        updated_responses=$(echo "$updated_responses" | jq --arg cat "$category" --arg q "$question" --arg ans "$answer" --arg qid "$question_id" \
                            '. += [{"category": $cat, "question": $q, "answer": $ans, "question_id": $qid}]')
                    else
                        updated_responses=$(echo "$updated_responses" | jq --arg cat "$category" --arg q "$question" --arg ans "$answer" \
                            '. += [{"category": $cat, "question": $q, "answer": $ans}]')
                    fi
                    break
                    ;;
                quit)
                    echo -e "${YELLOW}Review cancelled. Discarding changes.${NC}"
                    return 1
                    ;;
            esac
        done

        ((q_num++))
    done < <(echo "$responses_json" | jq -c '.[]')

    echo ""
    echo -e "${GREEN}✓ Review complete!${NC}"
    echo ""
    echo "$updated_responses"
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
    local skip_review=false

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
            --skip-review)
                skip_review=true
                shift
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

    # Load and filter questions
    local all_questions
    all_questions=$(interview_load_questions)
    local questions
    questions=$(interview_filter_questions "$task_json" "$all_questions")

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

        # Run review flow unless --skip-review specified
        if [[ "$skip_review" == "false" ]]; then
            responses_json=$(interview_run_review "$task_id" "$task_json" "$responses_json" "$questions")
            if [[ $? -ne 0 ]]; then
                # User cancelled review
                return 1
            fi
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
    interview_generate_spec "$task_json" "$responses_json" "$output_file" "$mode"

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
