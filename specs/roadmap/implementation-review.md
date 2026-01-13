# Implementation Review

**Source:** [gmickel-claude-marketplace](https://github.com/gmickel/gmickel-claude-marketplace) (Flow-Next)
**Dependencies:** Plan Review (for full workflow, but can work standalone)
**Complexity:** Medium-High

## Overview

Automated review after task completion to validate correctness, DRY adherence, test coverage, and code quality before marking tasks complete.

## Reference Implementation

From Flow-Next:
> "Implementation reviews evaluating correctness, DRY principles, test coverage"

Reviews occur after implementation, validating work meets quality standards.

## Problem Statement

Completed tasks may have issues:
- Logic errors not caught by tests
- Code duplication introduced
- Missing or inadequate tests
- Security vulnerabilities
- Style inconsistencies
- Performance regressions

Without review, these accumulate as technical debt.

## Proposed Solution

Automated implementation review that validates completed work before task closure.

## Proposed Interface

```bash
# Review specific task implementation
cub review <task-id>
cub review --impl <task-id>

# Review all completed (unclosed) tasks
cub review --impl --all

# Review during run (automatic)
cub run --review-impl

# Review options
cub review <task-id> --fix        # Auto-fix issues found
cub review <task-id> --strict     # Block on any issues
cub review <task-id> --model opus # Use specific model
```

## Review Dimensions

### 1. Correctness

Does the implementation correctly address requirements?

```yaml
correctness:
  checks:
    - acceptance_criteria_met: true
    - logic_correct: true
    - edge_cases_handled: true
    - error_handling_present: true

  methods:
    - Parse acceptance criteria from task
    - Check each criterion against implementation
    - Run tests and verify passage
    - AI review of logic
```

### 2. DRY Principles

Is code duplication minimized?

```yaml
dry:
  checks:
    - no_copy_paste_code: true
    - shared_logic_extracted: true
    - consistent_patterns: true

  methods:
    - Static analysis for duplicate blocks
    - AI review for semantic duplication
    - Check against existing utilities
```

### 3. Test Coverage

Are changes adequately tested?

```yaml
test_coverage:
  checks:
    - new_code_tested: true
    - edge_cases_tested: true
    - coverage_threshold_met: true

  methods:
    - Run coverage tool on changed files
    - Compare before/after coverage
    - Check for test file additions
```

### 4. Security

Are there security concerns?

```yaml
security:
  checks:
    - no_hardcoded_secrets: true
    - input_validated: true
    - output_escaped: true
    - no_sql_injection: true
    - no_xss_vectors: true

  methods:
    - Pattern matching for secrets
    - AI review for vulnerabilities
    - Static analysis tools
```

### 5. Code Quality

Does code meet quality standards?

```yaml
quality:
  checks:
    - lint_passing: true
    - style_consistent: true
    - naming_conventions: true
    - documentation_adequate: true

  methods:
    - Run linter on changed files
    - Check naming patterns
    - Verify comments on complex logic
```

## Review Process

### Identify Changes

```bash
get_task_changes() {
  local task_id=$1

  # Find commits for this task
  local commits
  commits=$(git log --oneline --grep="$task_id" --format="%H")

  if [[ -z "$commits" ]]; then
    # Fallback: uncommitted changes
    git diff --name-only
  else
    # Changes across all task commits
    local first_commit
    first_commit=$(echo "$commits" | tail -1)
    git diff --name-only "${first_commit}^" HEAD
  fi
}

get_task_diff() {
  local task_id=$1

  local commits
  commits=$(git log --oneline --grep="$task_id" --format="%H")

  if [[ -z "$commits" ]]; then
    git diff
  else
    local first_commit
    first_commit=$(echo "$commits" | tail -1)
    git diff "${first_commit}^" HEAD
  fi
}
```

### Run Automated Checks

```bash
run_impl_review() {
  local task_id=$1
  local results=()

  # Get changed files
  local changed_files
  changed_files=$(get_task_changes "$task_id")

  # Get diff
  local diff
  diff=$(get_task_diff "$task_id")

  # Correctness (AI-assisted)
  results+=("$(check_correctness "$task_id" "$diff")")

  # DRY analysis
  results+=("$(check_dry "$changed_files" "$diff")")

  # Test coverage
  results+=("$(check_test_coverage "$changed_files")")

  # Security scan
  results+=("$(check_security "$changed_files" "$diff")")

  # Code quality
  results+=("$(check_quality "$changed_files")")

  # Aggregate
  aggregate_review_results "${results[@]}"
}
```

### AI-Assisted Review

```bash
ai_impl_review() {
  local task_id=$1
  local diff=$2

  local task_json
  task_json=$(task_get "$task_id")

  local prompt="You are reviewing an implementation for quality and correctness.

## Task
Title: $(echo "$task_json" | jq -r '.title')
Description: $(echo "$task_json" | jq -r '.description')

## Acceptance Criteria
$(echo "$task_json" | jq -r '.acceptanceCriteria[]' | sed 's/^/- /')

## Implementation Diff
\`\`\`diff
$diff
\`\`\`

## Review Checklist
1. CORRECTNESS: Does implementation meet all acceptance criteria?
2. DRY: Is there code duplication that should be extracted?
3. SECURITY: Are there any security concerns (injection, XSS, secrets)?
4. QUALITY: Is code readable, well-named, appropriately commented?
5. EDGE CASES: Are error conditions and edge cases handled?

## Output Format
VERDICT: APPROVE | REQUEST_CHANGES | BLOCK
CORRECTNESS_SCORE: 1-5
ISSUES:
- [severity:high|medium|low] [category] description
SUGGESTIONS:
- suggestion
APPROVE_WITH_NOTES: true|false"

  invoke_harness --prompt "$prompt" --model sonnet
}
```

### Test Coverage Check

```bash
check_test_coverage() {
  local changed_files=$1
  local issues=()

  # Check if test files added for new source files
  for file in $changed_files; do
    if [[ "$file" == *.sh && "$file" != *test* && "$file" != *spec* ]]; then
      local test_file="${file%.sh}.bats"
      if [[ ! -f "$test_file" ]]; then
        # Check tests/ directory
        local base
        base=$(basename "$file" .sh)
        if ! find tests -name "*${base}*" -type f 2>/dev/null | grep -q .; then
          issues+=("[medium] Missing tests for $file")
        fi
      fi
    fi
  done

  # Run coverage if available
  if command -v bats &>/dev/null; then
    # Run tests, capture coverage
    # (Implementation depends on coverage tooling)
    :
  fi

  echo "${issues[@]}"
}
```

## Review Output

### Summary Format

```
Implementation Review: task-123 "Implement user authentication"

✓ Correctness: 5/5
  - All 5 acceptance criteria addressed
  - Logic verified correct

⚠ DRY: CONCERNS
  - [medium] Password hashing logic duplicated in login.sh:45 and register.sh:67
  - Consider extracting to lib/auth_utils.sh

✓ Test Coverage: PASS
  - New tests added: tests/auth.bats
  - 3 test cases covering happy path and errors

✓ Security: PASS
  - No hardcoded secrets
  - Input validation present

⚠ Quality: CONCERNS
  - [low] Function `validate_user` could use more descriptive name

VERDICT: APPROVE WITH NOTES
ISSUES: 2 medium, 1 low
```

### Auto-Fix Mode

When `--fix` is specified:

```bash
auto_fix_issues() {
  local task_id=$1
  local issues=$2

  # Filter fixable issues
  local fixable
  fixable=$(echo "$issues" | jq '[.[] | select(.auto_fixable == true)]')

  if [[ $(echo "$fixable" | jq 'length') -gt 0 ]]; then
    local fix_prompt="Fix these issues in the codebase:

$(echo "$fixable" | jq -r '.[] | "- \(.description)"')

Make minimal changes to address each issue."

    invoke_harness --prompt "$fix_prompt" --auto-approve

    # Re-run review after fixes
    run_impl_review "$task_id"
  fi
}
```

## Integration with Run Loop

```bash
# In lib/loop.sh
after_task_complete() {
  local task_id=$1

  if [[ "${CUB_REVIEW_IMPL:-false}" == "true" ]]; then
    local review
    review=$(run_impl_review "$task_id")

    local verdict
    verdict=$(echo "$review" | jq -r '.verdict')

    case "$verdict" in
      "approve")
        log_event "impl_review_approved" "$task_id"
        close_task "$task_id"
        ;;
      "approve_with_notes")
        log_event "impl_review_approved_with_notes" "$task_id"
        # Add notes to task
        close_task "$task_id"
        ;;
      "request_changes")
        log_event "impl_review_changes_requested" "$task_id"
        if [[ "${CUB_REVIEW_AUTO_FIX:-false}" == "true" ]]; then
          auto_fix_issues "$task_id" "$review"
        else
          # Keep task open for next iteration
          add_review_feedback_to_task "$task_id" "$review"
        fi
        ;;
      "block")
        log_event "impl_review_blocked" "$task_id"
        mark_task_blocked "$task_id" "Implementation review blocked"
        ;;
    esac
  else
    close_task "$task_id"
  fi
}
```

## Configuration

```json
{
  "review": {
    "auto_impl": false,
    "impl_model": "sonnet",
    "impl_strict": false,
    "auto_fix": false,
    "dimensions": {
      "correctness": true,
      "dry": true,
      "test_coverage": true,
      "security": true,
      "quality": true
    },
    "severity_threshold": "medium",
    "block_on_high": true
  }
}
```

## Acceptance Criteria

- [ ] Identify changes for task (git-based)
- [ ] Correctness review against acceptance criteria
- [ ] DRY analysis for code duplication
- [ ] Test coverage verification
- [ ] Security scan for common vulnerabilities
- [ ] Code quality checks (lint, style)
- [ ] AI-assisted comprehensive review
- [ ] Auto-fix mode for simple issues
- [ ] Integration with run loop
- [ ] Configurable strictness levels

## Future Enhancements

- Integration with static analysis tools (semgrep, etc.)
- Historical quality trend tracking
- Team review assignments
- PR-style review comments
- Integration with CI/CD pipelines
- Custom review rules per project
