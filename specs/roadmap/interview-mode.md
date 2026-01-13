# Interview Mode

**Source:** [gmickel-claude-marketplace](https://github.com/gmickel/gmickel-claude-marketplace) (Flow-Next)
**Dependencies:** None
**Complexity:** Medium-High

---

## Integration Note: Vision-to-Tasks Pipeline

**Interview Mode operates at the TASK level.** For PROJECT-level requirements refinement, see the **Vision-to-Tasks Pipeline** spec (`cub triage`).

| Scope | Command | Purpose |
|-------|---------|---------|
| Project | `cub triage` | Refine overall vision, requirements, constraints |
| Task | `cub interview` | Deep-dive on individual task specs |

The pipeline's triage stage handles questions like "What problem does this solve?" while Interview Mode handles questions like "What happens when this API times out?"

---

## Overview

Deep questioning phase to refine task specifications before execution, covering edge cases, error handling, and integration points through structured interviews.

## Reference Implementation

From Flow-Next:
> "/flow-next:interview - 40+ deep questions to refine specifications"

The interview generates comprehensive spec documents by systematically probing requirements.

## Problem Statement

Tasks often start with incomplete specifications:
- Edge cases not considered
- Error handling undefined
- Integration points unclear
- User experience gaps
- Performance requirements missing
- Security considerations overlooked

This leads to:
- Mid-implementation discoveries requiring rework
- Incomplete features
- Missing error handling
- Integration failures

## Proposed Solution

Structured interview process that generates comprehensive specifications before implementation begins.

## Proposed Interface

```bash
# Interview specific task
cub interview <task-id>

# Interview all open tasks
cub interview --all

# Interview before running
cub run --interview-first

# Interview with AI-generated answers (for autonomous mode)
cub interview <task-id> --auto

# Output options
cub interview <task-id> --output specs/task-123-spec.md
cub interview <task-id> --update-task  # Add to task description
```

## Interview Structure

### Categories

1. **Functional Requirements**
2. **Edge Cases & Error Handling**
3. **User Experience**
4. **Data & State**
5. **Integration Points**
6. **Performance & Scale**
7. **Security**
8. **Testing**
9. **Deployment & Operations**

### Question Bank

```yaml
functional:
  - What is the primary user goal this feature enables?
  - What inputs does this feature accept?
  - What outputs does this feature produce?
  - What are the success criteria?
  - What existing features does this interact with?

edge_cases:
  - What happens with empty input?
  - What happens with malformed input?
  - What happens with extremely large input?
  - What happens during concurrent access?
  - What happens if a dependency is unavailable?
  - What happens on timeout?
  - What happens on partial failure?

error_handling:
  - What errors can occur?
  - How should each error be handled?
  - What error messages should users see?
  - Should errors be logged? Where?
  - Are there retry scenarios?
  - What's the fallback behavior?

user_experience:
  - What does the user see during loading?
  - What feedback indicates success?
  - What feedback indicates failure?
  - Is there a way to undo/cancel?
  - How does this work on mobile?
  - What accessibility considerations apply?

data_state:
  - What data does this feature read?
  - What data does this feature write?
  - How is state persisted?
  - What happens to existing data on upgrade?
  - Are there data validation rules?
  - What are the data retention requirements?

integration:
  - What APIs does this call?
  - What APIs does this expose?
  - What events does this emit?
  - What events does this listen for?
  - Are there rate limits to consider?
  - What authentication is required?

performance:
  - What's the expected response time?
  - What's the expected throughput?
  - Are there caching opportunities?
  - What are the memory constraints?
  - What are the storage constraints?
  - How does this scale?

security:
  - What authentication is required?
  - What authorization rules apply?
  - Is there sensitive data involved?
  - Are there audit requirements?
  - What input sanitization is needed?
  - Are there rate limiting requirements?

testing:
  - What unit tests are needed?
  - What integration tests are needed?
  - What edge cases must be tested?
  - Are there performance tests?
  - How is this manually tested?

operations:
  - How is this feature toggled?
  - What monitoring is needed?
  - What alerts should fire?
  - How is this debugged in production?
  - What rollback procedure exists?
```

## Interview Modes

### Interactive Mode (Default)

Questions presented one at a time, user provides answers:

```
$ cub interview task-123

Interview: Implement user authentication

[1/42] Functional Requirements
What is the primary user goal this feature enables?
> Allow users to securely access their personal data

[2/42] Functional Requirements
What inputs does this feature accept?
> Email and password, or OAuth tokens

[3/42] Edge Cases
What happens with empty input?
> Show validation error, highlight empty fields

...
```

### Auto Mode

AI generates answers based on context:

```bash
cub interview task-123 --auto
```

Uses codebase analysis + task description to generate reasonable answers, then presents for human review.

### Batch Mode

Interview multiple tasks, output to files:

```bash
cub interview --all --auto --output-dir specs/
```

## Output Format

Generated specification document:

```markdown
# Task Specification: Implement User Authentication

## Overview
**Task ID:** task-123
**Generated:** 2026-01-13
**Interview Mode:** interactive

## Functional Requirements

### Primary Goal
Allow users to securely access their personal data.

### Inputs
- Email address (string, valid email format)
- Password (string, 8+ characters)
- OAuth tokens (optional, for social login)

### Outputs
- Session token (JWT)
- User profile object
- Error messages on failure

### Success Criteria
- User can log in with valid credentials
- Session persists across page refresh
- Invalid credentials show clear error

## Edge Cases & Error Handling

### Empty Input
- Show validation error
- Highlight empty required fields
- Disable submit until valid

### Invalid Credentials
- Show "Invalid email or password" (don't reveal which)
- Log failed attempt for security monitoring
- Implement rate limiting after 5 failures

...

## Acceptance Criteria (Generated)

Based on interview responses:
- [ ] Login form accepts email and password
- [ ] Validation errors shown for empty/invalid input
- [ ] Invalid credentials show generic error message
- [ ] Rate limiting after 5 failed attempts
- [ ] JWT token issued on success
- [ ] Session persists across page refresh
- [ ] Logout clears session completely
...
```

## Implementation

### Interview Engine

```bash
# lib/interview.sh

run_interview() {
  local task_id=$1
  local mode=${2:-interactive}
  local output_file=$3

  local task_json
  task_json=$(task_get "$task_id")

  local title
  title=$(echo "$task_json" | jq -r '.title')

  local responses=()
  local questions
  questions=$(load_question_bank)

  echo "Interview: $title"
  echo ""

  local q_num=1
  local total
  total=$(echo "$questions" | jq 'length')

  echo "$questions" | jq -c '.[]' | while read -r q; do
    local category
    category=$(echo "$q" | jq -r '.category')
    local question
    question=$(echo "$q" | jq -r '.question')

    echo "[$q_num/$total] $category"
    echo "$question"

    local answer
    if [[ "$mode" == "auto" ]]; then
      answer=$(generate_ai_answer "$task_json" "$question")
      echo "> $answer"
      echo ""
    else
      read -r -p "> " answer
    fi

    responses+=("$(jq -n --arg c "$category" --arg q "$question" --arg a "$answer" \
      '{category: $c, question: $q, answer: $a}')")

    ((q_num++))
  done

  # Generate spec document
  generate_spec_document "$task_json" "${responses[@]}" > "$output_file"
}
```

### Question Filtering

Not all questions apply to all tasks. Filter based on:
- Task type (feature, bug, refactor)
- Task labels
- Detected technology stack
- Previous answers (skip irrelevant follow-ups)

```bash
filter_questions() {
  local task_json=$1
  local all_questions=$2

  local task_type
  task_type=$(echo "$task_json" | jq -r '.type')

  local labels
  labels=$(echo "$task_json" | jq -r '.labels[]')

  # Filter questions based on relevance
  echo "$all_questions" | jq --arg type "$task_type" '
    [.[] | select(
      (.applies_to == null) or
      (.applies_to | contains([$type]))
    )]
  '
}
```

## Configuration

```json
{
  "interview": {
    "default_mode": "interactive",
    "auto_answer_model": "sonnet",
    "question_bank": "default",
    "custom_questions": [],
    "skip_categories": [],
    "output_format": "markdown",
    "update_task": false
  }
}
```

## Acceptance Criteria

- [ ] Interactive interview mode with Q&A flow
- [ ] Auto mode with AI-generated answers
- [ ] Generates comprehensive spec document
- [ ] Covers all question categories
- [ ] Question filtering by task type
- [ ] Output to file or update task description
- [ ] Batch interview multiple tasks
- [ ] Custom question support
- [ ] Skip categories option

## Future Enhancements

- ML-based question relevance scoring
- Learn from past interviews
- Template-based question customization
- Integration with design tools (Figma)
- Voice interview mode
- Team interview collaboration
