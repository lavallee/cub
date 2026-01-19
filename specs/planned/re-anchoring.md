# Re-anchoring Mechanism

**Source:** [gmickel-claude-marketplace](https://github.com/gmickel/gmickel-claude-marketplace) (Flow-Next)
**Dependencies:** None
**Complexity:** Low-Medium

## Overview

Prevent task drift by systematically re-reading context before each task iteration, forcing the AI back to the source of truth.

## Reference Implementation

From Flow-Next:
> "Before EVERY task, re-reads epic spec, task spec, and git state from `.flow/`. This forces Claude back to the source of truth."

This addresses a common failure mode where AI agents gradually drift from requirements as context accumulates.

## Problem Statement

Current cub behavior:
1. PROMPT.md read once at session start
2. Task description provided at task start
3. As iterations continue, AI may:
   - Forget original requirements
   - Accumulate incorrect assumptions
   - Drift from acceptance criteria
   - Lose track of what's already done

## Proposed Solution

Before each task iteration, inject a "re-anchoring block" into the prompt:

```markdown
## Re-anchoring Context

### System Instructions (PROMPT.md)
{contents of PROMPT.md}

### Current Task
ID: {task_id}
Title: {task_title}
Description: {task_description}

### Acceptance Criteria
{acceptance_criteria as checklist}

### Git State
Branch: {current_branch}
Uncommitted changes: {yes/no}
Recent commits:
{last 3 commits}

### Progress Notes
{relevant entries from progress.txt}
```

## Proposed Interface

```bash
# Enable re-anchoring (default: on)
cub run --reanchor

# Disable re-anchoring
cub run --no-reanchor

# Configure what gets re-anchored
cub run --anchor-sources "prompt,task,git"
```

## Anchoring Sources

### 1. System Prompt (PROMPT.md)
Always included. Core project instructions.

### 2. Agent Guide (AGENT.md)
Build/test/run commands. Technical context.

### 3. Task Specification
- Task ID, title, description
- Acceptance criteria
- Labels and metadata
- Dependencies (what this blocks/is blocked by)

### 4. Git State
- Current branch
- Uncommitted changes summary
- Recent commits (last 3-5)
- Files changed in current task

### 5. Progress Notes (progress.txt)
- Learnings from previous tasks
- Known issues
- Decisions made

### 6. Epic Context (if applicable)
- Parent epic description
- Related tasks in epic
- Epic-level acceptance criteria

## Implementation

### Anchor Block Generator

```bash
generate_anchor_block() {
  local task_id=$1
  local sources=${CUB_ANCHOR_SOURCES:-"prompt,task,git"}

  local block=""

  if [[ "$sources" == *"prompt"* ]]; then
    block+="## System Instructions\n"
    block+="$(cat PROMPT.md)\n\n"
  fi

  if [[ "$sources" == *"agent"* ]] && [[ -f "AGENT.md" ]]; then
    block+="## Agent Guide\n"
    block+="$(cat AGENT.md)\n\n"
  fi

  if [[ "$sources" == *"task"* ]]; then
    block+="## Current Task\n"
    block+="$(format_task_spec "$task_id")\n\n"
  fi

  if [[ "$sources" == *"git"* ]]; then
    block+="## Git State\n"
    block+="$(format_git_state)\n\n"
  fi

  if [[ "$sources" == *"progress"* ]] && [[ -f "progress.txt" ]]; then
    block+="## Progress Notes\n"
    block+="$(tail -20 progress.txt)\n\n"
  fi

  echo -e "$block"
}

format_task_spec() {
  local task_id=$1
  local task_json
  task_json=$(task_get "$task_id")

  echo "ID: $task_id"
  echo "Title: $(echo "$task_json" | jq -r '.title')"
  echo "Type: $(echo "$task_json" | jq -r '.type')"
  echo "Priority: $(echo "$task_json" | jq -r '.priority')"
  echo ""
  echo "### Description"
  echo "$(echo "$task_json" | jq -r '.description')"
  echo ""
  echo "### Acceptance Criteria"
  echo "$task_json" | jq -r '.acceptanceCriteria[]' | while read -r criterion; do
    echo "- [ ] $criterion"
  done
}

format_git_state() {
  echo "Branch: $(git branch --show-current)"
  echo "Uncommitted: $(git status --porcelain | wc -l | tr -d ' ') files"
  echo ""
  echo "Recent commits:"
  git log --oneline -3
}
```

### Integration with Loop

In `lib/loop.sh`, before invoking harness:

```bash
run_task_iteration() {
  local task_id=$1

  # Generate fresh anchor block
  local anchor_block
  anchor_block=$(generate_anchor_block "$task_id")

  # Prepend to task prompt
  local full_prompt="$anchor_block\n\n---\n\n$task_prompt"

  # Invoke harness with anchored prompt
  invoke_harness --prompt "$full_prompt" ...
}
```

## Configuration

```json
{
  "anchoring": {
    "enabled": true,
    "sources": ["prompt", "task", "git", "progress"],
    "git_commits": 3,
    "progress_lines": 20,
    "include_epic": true
  }
}
```

## Token Considerations

Re-anchoring adds tokens per iteration. Mitigations:
- Truncate long PROMPT.md (keep first N lines)
- Summarize git state (not full diff)
- Limit progress.txt to recent entries
- Option to anchor every N iterations instead of every iteration

```json
{
  "anchoring": {
    "frequency": 1,
    "max_prompt_lines": 100,
    "max_progress_lines": 20
  }
}
```

## Acceptance Criteria

- [ ] Anchor block generated before each task iteration
- [ ] Includes PROMPT.md content
- [ ] Includes current task specification
- [ ] Includes git state summary
- [ ] Configurable anchor sources
- [ ] Option to disable re-anchoring
- [ ] Token-conscious truncation for long content
- [ ] Works with both task backends

## Future Enhancements

- Smart anchoring (only re-anchor when drift detected)
- Diff-based anchoring (what changed since last anchor)
- Priority-based source inclusion
- Compressed anchor format for token efficiency
