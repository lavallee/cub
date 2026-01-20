---
status: planned
priority: medium
complexity: medium
dependencies: []
created: 2026-01-10
updated: 2026-01-19
readiness:
  score: 6
  blockers:
    - Needs workflow integration design
  questions:
    - When should context be cleared vs preserved?
    - How to integrate with workflow engine?
  decisions_needed:
    - Define context clearing triggers
    - Design workflow integration API
  tools_needed:
    - Dependency Analyzer (needs workflow integration)
    - Design Pattern Matcher (context reset patterns)
    - Trade-off Analyzer (when to clear vs keep context)
notes: |
  Needs workflow integration design.
  Depends on workflow engine being implemented.
source: ralph
---

# Fresh Context Mode

**Source:** [gmickel-claude-marketplace](https://github.com/gmickel/gmickel-claude-marketplace) (Flow-Next)
**Dependencies:** Re-anchoring Mechanism
**Complexity:** Medium

## Overview

Option to start with a fresh context window for each task iteration, preventing accumulated context pollution while trading off inter-task learning.

## Reference Implementation

From Flow-Next:
> "Fresh context per iteration (unlike session-based approaches)"
> "Context Management: Fresh context windows each iteration prevent accumulated context pollution"

This is a deliberate trade-off between session continuity and context cleanliness.

## Problem Statement

Long sessions accumulate context issues:
- Hallucinated file contents from earlier iterations
- Outdated assumptions no longer valid
- Conflicting instructions from different tasks
- "Memory" of failed approaches that biases new attempts
- Token budget consumed by irrelevant history

Benefits of context continuity:
- Learning from previous iterations
- Awareness of overall progress
- No need to re-explain project context
- Smoother task transitions

Fresh context mode lets users choose the trade-off.

## Proposed Solution

Configurable context management with options from full continuity to fresh-per-task.

## Context Modes

### 1. Continuous (Default)

Current behavior - session persists across tasks:

```
Task 1 ──────────────────────────────────>
         Context grows
                   Task 2 ───────────────>
                            Task 3 ──────>
```

### 2. Fresh Per Task

New context for each task, with anchoring:

```
Task 1 ───────────>
                   [clear]
                   Task 2 ───────────>
                                      [clear]
                                      Task 3 ───────>
```

### 3. Fresh Per Iteration

New context for each iteration within a task:

```
Task 1, Iter 1 ──>
                  [clear]
                  Task 1, Iter 2 ──>
                                    [clear]
                                    Task 1, Iter 3 ──>
```

### 4. Hybrid

Fresh context but with summarized history:

```
Task 1 ───────────>
                   [clear + summary]
                   Task 2 ──────────────>
                                         [clear + summary]
                                         Task 3 ──────────>
```

## Proposed Interface

```bash
# Enable fresh context per task
cub run --fresh-context
cub run --context-mode fresh-per-task

# Fresh per iteration (most aggressive)
cub run --context-mode fresh-per-iteration

# Hybrid with summaries
cub run --context-mode hybrid

# Configure default
cub config set context.mode "fresh-per-task"
```

## Implementation

### Session Management

```bash
# lib/context.sh

setup_context_mode() {
  local mode=${CUB_CONTEXT_MODE:-continuous}

  case "$mode" in
    continuous)
      # Default behavior, no special handling
      ;;
    fresh-per-task)
      register_hook "pre-task" "clear_context"
      ;;
    fresh-per-iteration)
      register_hook "pre-iteration" "clear_context"
      ;;
    hybrid)
      register_hook "pre-task" "clear_context_with_summary"
      ;;
  esac
}

clear_context() {
  local task_id=$1

  # Signal harness to reset session
  export CUB_HARNESS_RESET_SESSION=true

  log_event "context_cleared" "task=$task_id"
}

clear_context_with_summary() {
  local task_id=$1

  # Generate summary of previous task
  local summary
  summary=$(generate_task_summary "$previous_task_id")

  # Store summary for anchoring
  echo "$summary" > ".cub/runs/${session_id}/task_summary.md"

  # Clear context
  clear_context "$task_id"

  # Mark summary for inclusion in anchor
  export CUB_INCLUDE_PREVIOUS_SUMMARY=true
}
```

### Harness Integration

Each harness needs to support session reset:

```bash
# lib/harness_claude.sh

invoke_claude() {
  local prompt=$1
  local flags=()

  # Check for context reset
  if [[ "${CUB_HARNESS_RESET_SESSION:-false}" == "true" ]]; then
    flags+=("--no-continue")
    unset CUB_HARNESS_RESET_SESSION
  else
    flags+=("--continue")
  fi

  claude "${flags[@]}" --print "$prompt"
}
```

### Summary Generation

For hybrid mode, generate concise task summaries:

```bash
generate_task_summary() {
  local task_id=$1

  local task_json
  task_json=$(task_get "$task_id")

  local changes
  changes=$(get_task_changes "$task_id")

  local summary="## Previous Task Summary

**Task:** $(echo "$task_json" | jq -r '.title')
**Status:** $(echo "$task_json" | jq -r '.status')

### Changes Made
$(echo "$changes" | head -20)

### Key Decisions
$(extract_key_decisions "$task_id")

### Known Issues
$(get_known_issues "$task_id")
"

  echo "$summary"
}

extract_key_decisions() {
  local task_id=$1

  # Parse from progress.txt or task notes
  grep -A 5 "Decision:" "progress.txt" 2>/dev/null | tail -10 || echo "None recorded"
}
```

### Anchoring Integration

Fresh context relies heavily on re-anchoring:

```bash
# When fresh context mode is active, anchoring is mandatory
generate_fresh_context_anchor() {
  local task_id=$1

  local anchor=""

  # Always include system prompt
  anchor+="## Project Context\n"
  anchor+="$(cat PROMPT.md)\n\n"

  # Always include agent guide
  if [[ -f "AGENT.md" ]]; then
    anchor+="## Build/Test Instructions\n"
    anchor+="$(cat AGENT.md)\n\n"
  fi

  # Include task specification
  anchor+="## Current Task\n"
  anchor+="$(format_task_spec "$task_id")\n\n"

  # Include git state
  anchor+="## Git State\n"
  anchor+="$(format_git_state)\n\n"

  # Include previous summary if hybrid mode
  if [[ "${CUB_INCLUDE_PREVIOUS_SUMMARY:-false}" == "true" ]]; then
    anchor+="## Previous Work Summary\n"
    anchor+="$(cat ".cub/runs/${session_id}/task_summary.md")\n\n"
  fi

  echo -e "$anchor"
}
```

## Trade-off Analysis

### Fresh Context Pros
- No accumulated hallucinations
- Each task starts clean
- Consistent behavior
- Better for overnight/autonomous runs
- Easier debugging (reproducible)

### Fresh Context Cons
- No learning across tasks
- Must re-establish context each time
- Higher token usage (repeated anchoring)
- Loses helpful inter-task connections
- May repeat mistakes

### Recommendations

| Scenario | Recommended Mode |
|----------|------------------|
| Short interactive session | continuous |
| Long autonomous run | fresh-per-task |
| Debugging/testing | fresh-per-iteration |
| Mixed/unknown | hybrid |

## Configuration

```json
{
  "context": {
    "mode": "continuous",
    "generate_summaries": true,
    "summary_max_lines": 50,
    "include_git_state": true,
    "include_progress": true,
    "anchor_on_fresh": true
  }
}
```

## Metrics and Logging

Track context mode effectiveness:

```json
{
  "event": "task_completed",
  "context_mode": "fresh-per-task",
  "task_id": "abc123",
  "iterations": 3,
  "tokens_used": 45000,
  "context_resets": 1,
  "anchoring_tokens": 2000
}
```

## Acceptance Criteria

- [ ] Support continuous mode (default, current behavior)
- [ ] Support fresh-per-task mode (clear between tasks)
- [ ] Support fresh-per-iteration mode (clear each iteration)
- [ ] Support hybrid mode (clear with summary)
- [ ] Integration with re-anchoring mechanism
- [ ] Harness support for session reset (Claude, Codex, etc.)
- [ ] Summary generation for hybrid mode
- [ ] Configurable via CLI and config file
- [ ] Logging of context mode and resets

## Future Enhancements

- Smart context pruning (selective retention)
- Context compression (summarize don't clear)
- Per-task context mode override
- Context size monitoring and alerts
- Automatic mode selection based on session length
