# Dual-Condition Exit Gate

**Source:** [ralph-claude-code](https://github.com/frankbria/ralph-claude-code)
**Dependencies:** Circuit Breaker (soft dependency - works better together)
**Complexity:** Medium

## Overview

More sophisticated completion detection requiring both completion indicators AND explicit exit signals from the AI, preventing premature exits on false positives.

## Reference Implementation

From Ralph:
> "Dual-condition exit mechanism requiring both completion indicators AND explicit EXIT_SIGNAL from Claude"

Key aspects:
- Completion indicators threshold (>=2 required)
- Explicit `EXIT_SIGNAL: true` from Claude
- All @fix_plan.md tasks marked complete
- Multiple consecutive "done" signals
- Respects AI's explicit "not done yet" intent

## Problem Statement

Current cub uses single signal: `<promise>COMPLETE</promise>`

Failure modes:
1. AI outputs completion signal but work isn't done
2. AI says "done" but tests are failing
3. Premature exit on partial completion
4. False positive from similar text patterns

## Proposed Solution

Require multiple independent signals before exiting:

```
EXIT = (completion_indicators >= threshold) AND (explicit_exit_signal == true)
```

Where:
- **completion_indicators**: Count of completion patterns detected
- **threshold**: Configurable minimum (default: 2)
- **explicit_exit_signal**: AI explicitly confirms readiness to exit

## Completion Indicators

### Pattern Detection

```bash
COMPLETION_PATTERNS=(
  "<promise>COMPLETE</promise>"
  "all tasks.*completed"
  "implementation.*finished"
  "ready for review"
  "no remaining work"
  "all acceptance criteria.*met"
)

count_completion_indicators() {
  local output=$1
  local count=0

  for pattern in "${COMPLETION_PATTERNS[@]}"; do
    if echo "$output" | grep -qiE "$pattern"; then
      ((count++))
    fi
  done

  echo $count
}
```

### Evidence-Based Indicators

Beyond text patterns, check actual state:

```bash
check_evidence_indicators() {
  local task_id=$1
  local indicators=0

  # Tests passing?
  if run_tests_quietly; then
    ((indicators++))
  fi

  # All acceptance criteria addressed?
  if check_acceptance_criteria "$task_id"; then
    ((indicators++))
  fi

  # No uncommitted changes?
  if git diff --quiet; then
    ((indicators++))
  fi

  # Build succeeds?
  if run_build_quietly; then
    ((indicators++))
  fi

  echo $indicators
}
```

## Explicit Exit Signal

Request explicit confirmation from AI:

### Prompt Addition

```markdown
## Completion Protocol

When you believe the task is complete:
1. Verify all acceptance criteria are met
2. Ensure tests pass
3. Confirm no remaining work
4. Output your completion status as:

EXIT_STATUS: {COMPLETE|CONTINUE}
EXIT_REASON: {explanation}
REMAINING_WORK: {none|description of what's left}
```

### Signal Parsing

```bash
parse_exit_signal() {
  local output=$1

  local status
  status=$(echo "$output" | grep -oP 'EXIT_STATUS:\s*\K\w+')

  local reason
  reason=$(echo "$output" | grep -oP 'EXIT_REASON:\s*\K.*')

  if [[ "$status" == "COMPLETE" ]]; then
    echo "true"
  else
    echo "false"
  fi
}
```

## Exit Gate Logic

```bash
check_exit_gate() {
  local output=$1
  local task_id=$2

  # Count completion indicators
  local pattern_indicators
  pattern_indicators=$(count_completion_indicators "$output")

  local evidence_indicators
  evidence_indicators=$(check_evidence_indicators "$task_id")

  local total_indicators=$((pattern_indicators + evidence_indicators))

  # Check explicit exit signal
  local explicit_exit
  explicit_exit=$(parse_exit_signal "$output")

  # Apply gate logic
  local threshold=${CUB_EXIT_THRESHOLD:-2}

  if [[ $total_indicators -ge $threshold ]] && [[ "$explicit_exit" == "true" ]]; then
    log_event "exit_gate_passed" "indicators=$total_indicators explicit=$explicit_exit"
    return 0  # OK to exit
  else
    log_event "exit_gate_blocked" "indicators=$total_indicators explicit=$explicit_exit threshold=$threshold"
    return 1  # Continue
  fi
}
```

## Override Mechanisms

### Force Exit

When human intervention is needed:

```bash
# Skip gate for current task
cub run --force-complete

# Lower threshold temporarily
cub run --exit-threshold 1
```

### AI Override

Allow AI to express strong completion confidence:

```markdown
EXIT_STATUS: COMPLETE
EXIT_CONFIDENCE: HIGH
EXIT_OVERRIDE: true  # Request to bypass threshold
EXIT_REASON: All criteria verified, tests passing, ready for review
```

## Integration with Circuit Breaker

When combined with Circuit Breaker:

1. **Exit gate prevents premature exit** - AI must explicitly confirm
2. **Circuit breaker prevents stuck loops** - If gate never passes after N iterations, circuit breaker trips
3. **Together**: Balanced approach to completion detection

```bash
# In loop iteration
if check_exit_gate "$output" "$task_id"; then
  complete_task "$task_id"
else
  increment_no_exit_counter
  if [[ $no_exit_counter -ge $stagnation_threshold ]]; then
    trip_circuit_breaker "Exit gate not passing"
  fi
fi
```

## Configuration

```json
{
  "exit_gate": {
    "enabled": true,
    "indicator_threshold": 2,
    "require_explicit_signal": true,
    "evidence_checks": {
      "tests": true,
      "build": false,
      "acceptance_criteria": true,
      "clean_git": false
    },
    "patterns": [
      "<promise>COMPLETE</promise>",
      "all tasks completed",
      "ready for review"
    ]
  }
}
```

## Acceptance Criteria

- [ ] Count completion pattern indicators
- [ ] Parse explicit EXIT_STATUS signal
- [ ] Require threshold + explicit signal for exit
- [ ] Configurable indicator threshold
- [ ] Optional evidence-based indicators
- [ ] Force-complete override flag
- [ ] Logs exit gate decisions
- [ ] Works with circuit breaker

## Future Enhancements

- Confidence scoring for indicators
- Learning from past exit decisions
- Per-task type thresholds
- Integration with implementation review
