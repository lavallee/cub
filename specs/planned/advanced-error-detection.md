---
status: planned
priority: medium
complexity: medium
dependencies: []
created: 2026-01-10
updated: 2026-01-19
readiness:
  score: 6
  blockers: []
  questions: []
  decisions_needed: []
notes: |
  Needs error taxonomy definition.
source: See spec for details
---

# Advanced Error Detection

**Source:** [ralph-claude-code](https://github.com/frankbria/ralph-claude-code)
**Dependencies:** None
**Complexity:** Medium

## Overview

Improved error identification in AI output using two-stage filtering and multi-line matching to eliminate false positives and accurately categorize errors.

## Reference Implementation

From Ralph:
> "Advanced error detection using two-stage filtering and multi-line matching"
> "Distinguish JSON field names containing 'error' from actual errors"

This addresses the problem of false positive error detection.

## Problem Statement

Current error detection challenges:
1. JSON output with "error" field names triggers false positives
2. Multi-line error messages not captured completely
3. Stack traces partially matched
4. Warning vs error distinction unclear
5. Build errors vs runtime errors not categorized
6. Context around errors lost

## Proposed Solution

Two-stage error detection pipeline with context preservation and categorization.

## Error Detection Pipeline

```
┌─────────────────┐
│   Raw Output    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Stage 1: Fast  │
│   Pre-filter    │
│ (Pattern match) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Stage 2: Deep   │
│   Analysis      │
│ (Context-aware) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Categorized    │
│    Errors       │
└─────────────────┘
```

## Stage 1: Fast Pre-filter

Quick pattern matching to identify potential errors:

```bash
ERROR_PATTERNS=(
  # Generic errors
  'error:'
  'Error:'
  'ERROR:'
  'failed:'
  'Failed:'
  'FAILED:'
  'exception:'
  'Exception:'

  # Test failures
  'FAIL:'
  'not ok'
  'AssertionError'
  'assertion failed'

  # Build errors
  'Build failed'
  'Compilation error'
  'syntax error'
  'SyntaxError'

  # Runtime errors
  'TypeError'
  'ReferenceError'
  'undefined is not'
  'null pointer'
  'segmentation fault'

  # Shell errors
  'command not found'
  'No such file'
  'Permission denied'
)

stage1_prefilter() {
  local output=$1
  local potential_errors=()

  # Line-by-line scan
  local line_num=0
  while IFS= read -r line; do
    ((line_num++))

    for pattern in "${ERROR_PATTERNS[@]}"; do
      if [[ "$line" == *"$pattern"* ]]; then
        potential_errors+=("$line_num:$line")
        break
      fi
    done
  done <<< "$output"

  printf '%s\n' "${potential_errors[@]}"
}
```

## Stage 2: Deep Analysis

Context-aware filtering to eliminate false positives:

```bash
# False positive patterns to exclude
FALSE_POSITIVE_PATTERNS=(
  # JSON field names
  '"error":'
  '"error_code":'
  '"error_message":'
  "'error':"

  # Documentation/comments
  '# error'
  '// error'
  '/* error'
  '* @throws Error'

  # String literals (in code)
  'console.log.*error'
  'log.*error'
  'print.*error'

  # Environment variables
  'ERROR_'
  '_ERROR='

  # Function/variable names
  'handleError'
  'onError'
  'errorHandler'
  'isError'
  'hasError'
)

stage2_deep_analysis() {
  local potential_errors=$1
  local output=$2
  local confirmed_errors=()

  while IFS= read -r entry; do
    local line_num="${entry%%:*}"
    local line="${entry#*:}"

    local is_false_positive=false

    # Check against false positive patterns
    for fp_pattern in "${FALSE_POSITIVE_PATTERNS[@]}"; do
      if [[ "$line" =~ $fp_pattern ]]; then
        is_false_positive=true
        break
      fi
    done

    if [[ "$is_false_positive" == "false" ]]; then
      # Get context (lines before and after)
      local context
      context=$(get_line_context "$output" "$line_num" 3)

      confirmed_errors+=("$(jq -n \
        --arg line "$line" \
        --arg line_num "$line_num" \
        --arg context "$context" \
        '{line: $line, line_num: $line_num, context: $context}')")
    fi
  done <<< "$potential_errors"

  printf '%s\n' "${confirmed_errors[@]}" | jq -s '.'
}
```

## Multi-line Error Capture

Capture complete stack traces and multi-line errors:

```bash
capture_multiline_error() {
  local output=$1
  local start_line=$2
  local error_lines=()

  local in_stack_trace=false
  local line_num=0

  while IFS= read -r line; do
    ((line_num++))

    if [[ $line_num -lt $start_line ]]; then
      continue
    fi

    # Detect stack trace start
    if [[ "$line" =~ ^[[:space:]]*(at|in|from|File|Traceback) ]]; then
      in_stack_trace=true
    fi

    # Detect stack trace end
    if [[ "$in_stack_trace" == "true" && ! "$line" =~ ^[[:space:]] && ${#line} -gt 0 ]]; then
      break
    fi

    # Continue capturing if in error block
    if [[ $line_num -eq $start_line ]] || [[ "$in_stack_trace" == "true" ]]; then
      error_lines+=("$line")
    fi

    # Stop if we hit a clear boundary
    if [[ ${#error_lines[@]} -gt 50 ]]; then
      break  # Sanity limit
    fi
  done <<< "$output"

  printf '%s\n' "${error_lines[@]}"
}
```

## Error Categorization

```bash
categorize_error() {
  local error_text=$1

  # Test failure
  if [[ "$error_text" =~ (FAIL|not\ ok|AssertionError|assertion\ failed) ]]; then
    echo "test_failure"
    return
  fi

  # Syntax error
  if [[ "$error_text" =~ (SyntaxError|syntax\ error|parse\ error|unexpected\ token) ]]; then
    echo "syntax_error"
    return
  fi

  # Type error
  if [[ "$error_text" =~ (TypeError|type\ error|undefined\ is\ not|null\ is\ not) ]]; then
    echo "type_error"
    return
  fi

  # Reference error
  if [[ "$error_text" =~ (ReferenceError|is\ not\ defined|undefined\ variable) ]]; then
    echo "reference_error"
    return
  fi

  # File system error
  if [[ "$error_text" =~ (No\ such\ file|ENOENT|file\ not\ found|Permission\ denied) ]]; then
    echo "filesystem_error"
    return
  fi

  # Network error
  if [[ "$error_text" =~ (ECONNREFUSED|timeout|connection\ refused|network\ error) ]]; then
    echo "network_error"
    return
  fi

  # Build error
  if [[ "$error_text" =~ (Build\ failed|Compilation\ error|linker\ error) ]]; then
    echo "build_error"
    return
  fi

  # Generic
  echo "unknown_error"
}
```

## Error Severity Classification

```bash
classify_severity() {
  local error_category=$1
  local error_text=$2

  case "$error_category" in
    "syntax_error"|"build_error")
      echo "blocking"  # Cannot proceed
      ;;
    "test_failure")
      echo "high"  # Should fix before continuing
      ;;
    "type_error"|"reference_error")
      echo "high"
      ;;
    "filesystem_error")
      # Context-dependent
      if [[ "$error_text" =~ (test|spec|mock) ]]; then
        echo "medium"
      else
        echo "high"
      fi
      ;;
    "network_error")
      echo "medium"  # Often transient
      ;;
    *)
      echo "medium"
      ;;
  esac
}
```

## Integration

### With Loop

```bash
# In lib/loop.sh
process_harness_output() {
  local output=$1
  local task_id=$2

  # Run error detection
  local errors
  errors=$(detect_errors "$output")

  local error_count
  error_count=$(echo "$errors" | jq 'length')

  if [[ $error_count -gt 0 ]]; then
    log_event "errors_detected" "task=$task_id count=$error_count"

    # Check for blocking errors
    local blocking
    blocking=$(echo "$errors" | jq '[.[] | select(.severity == "blocking")] | length')

    if [[ $blocking -gt 0 ]]; then
      handle_blocking_error "$task_id" "$errors"
    fi

    # Store for circuit breaker
    store_iteration_errors "$task_id" "$errors"
  fi
}
```

### With Circuit Breaker

```bash
# Check for repeated errors
check_repeated_errors() {
  local task_id=$1
  local current_errors=$2

  local history
  history=$(get_error_history "$task_id")

  # Compare error signatures
  local current_signatures
  current_signatures=$(echo "$current_errors" | jq -r '.[].signature')

  local repeated=0
  while IFS= read -r sig; do
    if echo "$history" | grep -q "$sig"; then
      ((repeated++))
    fi
  done <<< "$current_signatures"

  echo "$repeated"
}
```

## Error Signature Generation

Create normalized signatures for error comparison:

```bash
generate_error_signature() {
  local error_text=$1

  # Normalize:
  # - Remove line numbers
  # - Remove file paths (keep filename only)
  # - Remove timestamps
  # - Remove memory addresses

  echo "$error_text" | \
    sed 's/:[0-9]\+:/:N:/g' | \
    sed 's/line [0-9]\+/line N/g' | \
    sed 's|/[^:]*\/||g' | \
    sed 's/0x[0-9a-f]\+/0xN/g' | \
    sed 's/[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}/DATE/g' | \
    md5sum | cut -d' ' -f1
}
```

## Output Format

```json
{
  "errors": [
    {
      "line_num": 42,
      "text": "TypeError: undefined is not a function",
      "category": "type_error",
      "severity": "high",
      "signature": "abc123...",
      "context": [
        "40: const result = process(data);",
        "41: if (result) {",
        "42:   result.callback();  // TypeError here",
        "43: }",
        "44: return result;"
      ],
      "multiline": [
        "TypeError: undefined is not a function",
        "    at Object.process (/src/handler.js:42:10)",
        "    at main (/src/index.js:15:5)"
      ]
    }
  ],
  "summary": {
    "total": 1,
    "blocking": 0,
    "high": 1,
    "medium": 0,
    "low": 0
  }
}
```

## Configuration

```json
{
  "error_detection": {
    "enabled": true,
    "two_stage": true,
    "capture_multiline": true,
    "max_context_lines": 5,
    "max_stack_depth": 20,
    "custom_patterns": [],
    "custom_false_positives": [],
    "severity_overrides": {}
  }
}
```

## Acceptance Criteria

- [ ] Two-stage detection pipeline
- [ ] False positive filtering (JSON fields, comments, etc.)
- [ ] Multi-line error capture (stack traces)
- [ ] Error categorization (syntax, type, test, etc.)
- [ ] Severity classification
- [ ] Error signature generation for comparison
- [ ] Context preservation (lines before/after)
- [ ] Integration with loop and circuit breaker
- [ ] Configurable patterns

## Future Enhancements

- ML-based false positive detection
- Language-specific error parsers
- IDE integration for error navigation
- Error trend analysis
- Suggested fixes based on error category
