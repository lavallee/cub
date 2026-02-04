---
status: planned
priority: high
complexity: low
dependencies: []
created: 2026-01-10
updated: 2026-01-19
readiness:
  score: 8
  blockers: []
  questions:
  - What format should receipts use (JSON, markdown, structured)?
  - Should receipts be versioned or immutable?
  decisions_needed:
  - Choose receipt storage format and location
  - Define receipt validation rules
  tools_needed:
  - API Design Validator (design receipt format/interface)
  - Design Pattern Matcher (find similar proof-of-work patterns)
  - Test Coverage Planner (how to test receipt validation)
notes: |
  Ready to implement. Similar to guardrails system.
  Receipt format and validation rules are main decisions.
source: ralph
spec_id: cub-021
---
# Receipt-Based Gating

**Source:** [gmickel-claude-marketplace](https://github.com/gmickel/gmickel-claude-marketplace) (Flow-Next)
**Dependencies:** Implementation Review
**Complexity:** Medium

## Overview

Require proof-of-work artifacts before marking tasks complete, ensuring deliverables meet defined requirements.

## Reference Implementation

From Flow-Next:
> "Receipt-based gating requiring proof-of-work for review completion"

Tasks cannot close until required "receipts" (artifacts proving completion) are verified.

## Problem Statement

Tasks may be marked complete without:
- Tests written or passing
- Documentation updated
- Required files created
- Build succeeding
- Specific deliverables present

Gating ensures concrete evidence of completion.

## Proposed Solution

Define required receipts per task type and verify their presence before allowing task closure.

## Proposed Interface

```bash
# Check receipts for task
cub receipts <task-id>
cub receipts <task-id> --verify

# Configure required receipts
cub receipts config --type feature --require tests,docs

# Gate task closure
cub close <task-id>  # Fails if receipts missing
cub close <task-id> --skip-receipts  # Override

# List receipt status
cub receipts --all
```

## Receipt Types

### 1. Tests
New or updated test files covering the implementation.

```yaml
tests:
  name: "Test Coverage"
  verify:
    - test_files_added_or_modified: true
    - tests_pass: true
    - coverage_threshold: 80%

  detection:
    - "tests/**/*.bats" modified
    - "**/*_test.sh" modified
    - "**/test_*.sh" modified
```

### 2. Documentation
Updated documentation reflecting changes.

```yaml
docs:
  name: "Documentation"
  verify:
    - readme_updated: conditional  # If public API changed
    - inline_comments: conditional  # If complex logic added
    - changelog_entry: conditional  # If user-facing change

  detection:
    - "README.md" modified (if applicable)
    - "CHANGELOG.md" entry added
    - "docs/**/*" modified
```

### 3. Build Artifacts
Successful build output.

```yaml
build:
  name: "Successful Build"
  verify:
    - build_succeeds: true
    - no_warnings: optional

  detection:
    - Run build command
    - Check exit code
```

### 4. Type Definitions
Updated type/interface definitions.

```yaml
types:
  name: "Type Definitions"
  verify:
    - types_updated: conditional
    - no_type_errors: true

  detection:
    - "types/**/*" modified (if applicable)
    - Type check passes
```

### 5. Migration
Database or config migrations if schema changed.

```yaml
migration:
  name: "Migration Scripts"
  verify:
    - migration_added: conditional
    - migration_reversible: optional

  detection:
    - "migrations/**/*" added
    - Schema changes detected
```

### 6. Custom Receipts
Project-specific requirements.

```yaml
custom:
  name: "Custom Receipt"
  verify:
    - command: "npm run custom-check"
    - expected_exit_code: 0
```

## Receipt Configuration

### Per Task Type

```json
{
  "gating": {
    "receipts": {
      "feature": {
        "required": ["tests", "build"],
        "recommended": ["docs"],
        "optional": ["types"]
      },
      "bug": {
        "required": ["tests", "build"],
        "recommended": [],
        "optional": ["docs"]
      },
      "refactor": {
        "required": ["tests", "build"],
        "recommended": [],
        "optional": []
      },
      "docs": {
        "required": ["build"],
        "recommended": [],
        "optional": []
      }
    }
  }
}
```

### Per Task Override

Tasks can specify custom receipt requirements:

```json
{
  "id": "task-123",
  "title": "Implement authentication",
  "receipts": {
    "required": ["tests", "docs", "security-review"],
    "skip": ["types"]
  }
}
```

## Verification Logic

```bash
verify_receipts() {
  local task_id=$1
  local task_json
  task_json=$(task_get "$task_id")

  local task_type
  task_type=$(echo "$task_json" | jq -r '.type')

  # Get required receipts for this task type
  local required
  required=$(get_required_receipts "$task_type" "$task_json")

  local results=()
  local all_pass=true

  for receipt in $required; do
    local status
    status=$(verify_receipt "$receipt" "$task_id")

    results+=("$(jq -n --arg r "$receipt" --arg s "$status" \
      '{receipt: $r, status: $s}')")

    if [[ "$status" != "pass" ]]; then
      all_pass=false
    fi
  done

  # Return verification result
  jq -n \
    --argjson results "$(printf '%s\n' "${results[@]}" | jq -s '.')" \
    --arg pass "$all_pass" \
    '{receipts: $results, all_pass: ($pass == "true")}'
}

verify_receipt() {
  local receipt_type=$1
  local task_id=$2

  case "$receipt_type" in
    tests)
      verify_tests_receipt "$task_id"
      ;;
    build)
      verify_build_receipt "$task_id"
      ;;
    docs)
      verify_docs_receipt "$task_id"
      ;;
    *)
      verify_custom_receipt "$receipt_type" "$task_id"
      ;;
  esac
}

verify_tests_receipt() {
  local task_id=$1

  # Check if test files modified
  local changed_tests
  changed_tests=$(get_task_changes "$task_id" | grep -E "(test|spec|bats)" || true)

  if [[ -z "$changed_tests" ]]; then
    echo "missing"
    return
  fi

  # Check if tests pass
  if run_tests_quietly; then
    echo "pass"
  else
    echo "failing"
  fi
}

verify_build_receipt() {
  local task_id=$1

  if run_build_quietly; then
    echo "pass"
  else
    echo "failing"
  fi
}
```

## Gating Enforcement

### In Task Closure

```bash
close_task() {
  local task_id=$1
  local skip_receipts=${2:-false}

  if [[ "$skip_receipts" != "true" ]] && [[ "${CUB_GATING_ENABLED:-true}" == "true" ]]; then
    local verification
    verification=$(verify_receipts "$task_id")

    local all_pass
    all_pass=$(echo "$verification" | jq -r '.all_pass')

    if [[ "$all_pass" != "true" ]]; then
      echo "Receipt verification failed:"
      echo "$verification" | jq -r '.receipts[] | select(.status != "pass") | "  ✗ \(.receipt): \(.status)"'

      case "${CUB_GATING_STRICTNESS:-warn}" in
        strict)
          echo "Cannot close task without required receipts."
          return 1
          ;;
        warn)
          echo "Warning: Closing task without all receipts."
          ;;
        skip)
          # Silent continue
          ;;
      esac
    else
      echo "All receipts verified:"
      echo "$verification" | jq -r '.receipts[] | "  ✓ \(.receipt)"'
    fi
  fi

  # Proceed with closure
  task_update_status "$task_id" "closed"
}
```

### Strictness Levels

```json
{
  "gating": {
    "strictness": "warn",  // strict | warn | skip
    "allow_override": true,
    "log_skipped": true
  }
}
```

- **strict**: Block closure if any required receipt missing
- **warn**: Log warning but allow closure
- **skip**: No receipt checking (not recommended)

## Receipt Status Display

```
$ cub receipts task-123

Receipt Status: task-123 "Implement authentication"
Type: feature

Required:
  ✓ tests     - 3 test files added, all passing
  ✓ build     - Build succeeds

Recommended:
  ⚠ docs      - No documentation changes detected

Optional:
  ○ types     - Not checked

Overall: PASS (2/2 required, 0/1 recommended)
```

## Integration with Implementation Review

When used with Implementation Review:

1. Implementation Review checks code quality
2. Receipt Gating checks deliverable presence
3. Both must pass for task closure (in strict mode)

```bash
after_task_complete() {
  local task_id=$1

  # Run implementation review
  if ! run_impl_review "$task_id"; then
    return 1
  fi

  # Verify receipts
  if ! verify_receipts "$task_id"; then
    return 1
  fi

  # Both passed, close task
  close_task "$task_id"
}
```

## Configuration

```json
{
  "gating": {
    "enabled": true,
    "strictness": "warn",
    "allow_override": true,
    "receipts": {
      "feature": {
        "required": ["tests", "build"],
        "recommended": ["docs"]
      },
      "bug": {
        "required": ["tests", "build"]
      },
      "refactor": {
        "required": ["tests", "build"]
      }
    },
    "custom_receipts": {
      "security-review": {
        "command": "./scripts/security-check.sh",
        "expected_exit_code": 0
      }
    }
  }
}
```

## Acceptance Criteria

- [ ] Define receipt types (tests, build, docs, etc.)
- [ ] Configure required receipts per task type
- [ ] Verify receipt presence before task closure
- [ ] Support strictness levels (strict/warn/skip)
- [ ] Override flag to skip gating
- [ ] Receipt status display command
- [ ] Custom receipt definitions
- [ ] Integration with implementation review
- [ ] Per-task receipt overrides

## Future Enhancements

- Receipt templates for common patterns
- Historical receipt compliance tracking
- Team receipt requirements
- CI/CD receipt integration
- Automated receipt generation suggestions
