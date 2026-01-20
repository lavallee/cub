---
status: complete
version: 0.15
priority: high
complexity: medium
dependencies: []
created: 2026-01-08
updated: 2026-01-19
completed: 2026-01-14
implementation:
  - src/cub/cli/review.py
  - cub review command
notes: |
  Implemented as quality gate in prep pipeline. Reviews architect and plan outputs.
source: gmickel-claude-marketplace (Flow-Next)
---

# Plan Review

**Dependencies:** None  
**Complexity:** Medium

---

## Integration Note: Vision-to-Tasks Pipeline

Plan Review integrates with the Vision-to-Tasks Pipeline as a **quality gate between stages**:

```
cub triage ──> cub architect ──[PLAN REVIEW]──> cub plan ──[PLAN REVIEW]──> cub bootstrap
                     │                               │
                     ▼                               ▼
              Validates:                      Validates:
              - Technical design              - Task completeness
              - Architecture coherence        - Dependency ordering
              - Risk identification           - Label correctness
              - Feasibility                   - Acceptance criteria
```

**Automatic integration:**
```bash
cub pipeline --auto-review    # Run plan review between stages
cub architect --review        # Review architect output before proceeding
cub plan --review             # Review plan output before bootstrap
```

Plan Review can also run standalone on individual tasks (original use case).

---

## Overview

Automated review of task plans before execution to validate completeness, feasibility, architecture alignment, and dependency correctness.

## Reference Implementation

From Flow-Next:
> "Plan reviews checking completeness, feasibility, architecture, dependencies"

Reviews occur before execution begins, catching issues early.

## Problem Statement

Plans fail for predictable reasons:
- Missing requirements not addressed
- Infeasible given current codebase state
- Architectural inconsistency with existing patterns
- Incorrect dependency ordering
- Underestimated scope

Early detection saves significant rework.

## Proposed Solution

Automated plan review that validates tasks before execution begins.

## Proposed Interface

```bash
# Review specific task
cub review --plan <task-id>

# Review all ready tasks
cub review --plan --all

# Review during run (automatic)
cub run --review-plans

# Review verbosity
cub review --plan <task-id> --verbose
cub review --plan <task-id> --json
```

## Review Dimensions

### 1. Completeness Check

Does the task address all stated requirements?

```yaml
completeness:
  checks:
    - title_describes_work: true
    - description_present: true
    - acceptance_criteria_defined: true
    - type_appropriate: true

  questions:
    - Are all requirements from the description addressable?
    - Are acceptance criteria measurable and verifiable?
    - Is scope clearly bounded?
```

### 2. Feasibility Analysis

Can this task be completed given current state?

```yaml
feasibility:
  checks:
    - dependencies_exist: true
    - dependencies_completed: true
    - required_files_present: true
    - required_apis_available: true

  questions:
    - Are all referenced files/modules present?
    - Are external dependencies available?
    - Is the technology stack compatible?
    - Are there blocking issues?
```

### 3. Architecture Review

Does this align with existing patterns?

```yaml
architecture:
  checks:
    - follows_existing_patterns: true
    - consistent_with_conventions: true
    - appropriate_location: true

  questions:
    - Where should new code live based on existing structure?
    - What existing patterns should be followed?
    - Are there similar implementations to reference?
    - Does this introduce new dependencies appropriately?
```

### 4. Dependency Validation

Are dependencies correctly specified?

```yaml
dependencies:
  checks:
    - all_dependencies_exist: true
    - no_circular_dependencies: true
    - order_is_correct: true
    - blocked_tasks_identified: true

  questions:
    - Are all prerequisites listed?
    - Can this task start now or is it blocked?
    - What tasks depend on this one?
```

## Review Process

### Automated Checks

```bash
run_plan_review() {
  local task_id=$1
  local results=()

  # Completeness
  results+=("$(check_completeness "$task_id")")

  # Feasibility
  results+=("$(check_feasibility "$task_id")")

  # Architecture
  results+=("$(check_architecture "$task_id")")

  # Dependencies
  results+=("$(check_dependencies "$task_id")")

  # Aggregate results
  aggregate_review_results "${results[@]}"
}

check_completeness() {
  local task_id=$1
  local task_json
  task_json=$(task_get "$task_id")

  local issues=()

  # Title present and descriptive
  local title
  title=$(echo "$task_json" | jq -r '.title')
  if [[ -z "$title" || ${#title} -lt 10 ]]; then
    issues+=("Title missing or too short")
  fi

  # Description present
  local desc
  desc=$(echo "$task_json" | jq -r '.description')
  if [[ -z "$desc" ]]; then
    issues+=("Description missing")
  fi

  # Acceptance criteria defined
  local criteria_count
  criteria_count=$(echo "$task_json" | jq '.acceptanceCriteria | length')
  if [[ $criteria_count -eq 0 ]]; then
    issues+=("No acceptance criteria defined")
  fi

  echo "${issues[@]}"
}

check_feasibility() {
  local task_id=$1
  local issues=()

  # Check dependencies are complete
  local deps
  deps=$(task_get_dependencies "$task_id")

  for dep in $deps; do
    local status
    status=$(task_get_status "$dep")
    if [[ "$status" != "closed" ]]; then
      issues+=("Dependency $dep not complete (status: $status)")
    fi
  done

  # Check referenced files exist
  # (Would need NLP to extract file references from description)

  echo "${issues[@]}"
}

check_architecture() {
  local task_id=$1
  local task_json
  task_json=$(task_get "$task_id")

  # Use AI to assess architectural fit
  local prompt="Review this task for architectural consistency with the codebase:

Task: $(echo "$task_json" | jq -r '.title')
Description: $(echo "$task_json" | jq -r '.description')

Project structure:
$(find . -type f -name "*.sh" | head -20)

Identify any architectural concerns or suggestions."

  invoke_harness --prompt "$prompt" --model haiku
}
```

### AI-Assisted Review

For deeper analysis, use AI:

```bash
ai_plan_review() {
  local task_id=$1
  local task_json
  task_json=$(task_get "$task_id")

  local prompt="You are reviewing a task plan before implementation.

## Task
$(echo "$task_json" | jq '.')

## Codebase Context
$(get_relevant_context "$task_json")

## Review Checklist
1. COMPLETENESS: Are all requirements addressed? Are acceptance criteria clear and measurable?
2. FEASIBILITY: Can this be implemented with current codebase? Are there blockers?
3. ARCHITECTURE: Does this fit existing patterns? Where should code live?
4. DEPENDENCIES: Are prerequisites complete? Is ordering correct?

## Output Format
VERDICT: PASS | CONCERNS | BLOCK
ISSUES:
- [category] issue description
SUGGESTIONS:
- suggestion
READY_TO_IMPLEMENT: true | false"

  invoke_harness --prompt "$prompt" --model sonnet
}
```

## Review Output

### Summary Format

```
Plan Review: task-123 "Implement user authentication"

✓ Completeness: PASS
  - Title descriptive
  - Description present
  - 5 acceptance criteria defined

✓ Feasibility: PASS
  - All dependencies complete
  - Required modules present

⚠ Architecture: CONCERNS
  - Consider using existing AuthService pattern
  - Session storage should use Redis (see config/database.js)

✓ Dependencies: PASS
  - No blocking dependencies
  - No circular dependencies

VERDICT: READY WITH SUGGESTIONS
```

### JSON Format

```json
{
  "task_id": "task-123",
  "verdict": "ready_with_suggestions",
  "dimensions": {
    "completeness": {"status": "pass", "issues": []},
    "feasibility": {"status": "pass", "issues": []},
    "architecture": {
      "status": "concerns",
      "issues": ["Consider using existing AuthService pattern"],
      "suggestions": ["Session storage should use Redis"]
    },
    "dependencies": {"status": "pass", "issues": []}
  },
  "ready_to_implement": true,
  "reviewed_at": "2026-01-13T10:30:00Z"
}
```

## Integration with Run Loop

```bash
# In lib/loop.sh
before_task() {
  local task_id=$1

  if [[ "${CUB_REVIEW_PLANS:-false}" == "true" ]]; then
    local review
    review=$(run_plan_review "$task_id")

    local verdict
    verdict=$(echo "$review" | jq -r '.verdict')

    case "$verdict" in
      "pass"|"ready_with_suggestions")
        log_event "plan_review_passed" "$task_id"
        ;;
      "concerns")
        log_event "plan_review_concerns" "$task_id"
        if [[ "${CUB_REVIEW_STRICT:-false}" == "true" ]]; then
          pause_for_review "$task_id" "$review"
        fi
        ;;
      "block")
        log_event "plan_review_blocked" "$task_id"
        skip_task "$task_id" "Plan review blocked"
        return 1
        ;;
    esac
  fi
}
```

## Configuration

```json
{
  "review": {
    "auto_plan": false,
    "plan_strict": false,
    "plan_model": "haiku",
    "dimensions": {
      "completeness": true,
      "feasibility": true,
      "architecture": true,
      "dependencies": true
    },
    "block_on_concerns": false,
    "output_format": "summary"
  }
}
```

## Acceptance Criteria

- [ ] Completeness checks (title, description, criteria)
- [ ] Feasibility checks (dependencies, files)
- [ ] Architecture review (AI-assisted)
- [ ] Dependency validation
- [ ] Summary and JSON output formats
- [ ] Integration with run loop (--review-plans)
- [ ] Configurable strictness levels
- [ ] Review results logged

## Future Enhancements

- Historical review accuracy tracking
- Team review assignments
- Review templates per task type
- Integration with PR review
- Automated issue creation for blocked plans
