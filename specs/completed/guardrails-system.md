---
status: complete
version: 0.20
priority: high
complexity: low
dependencies: []
created: 2026-01-10
updated: 2026-01-19
completed: 2026-01-17
implementation:
  - src/cub/bash/lib/guardrails.sh
  - src/cub/bash/lib/cmd_guardrails.sh
  - src/cub/bash/templates/guardrails.md
  - cub guardrails command
notes: |
  Core implementation complete. CLI and bash library working.
  Auto-learning feature and curation tools remain pending (future enhancement).
source: ralph (https://github.com/iannuttall/ralph)
---

# Guardrails System (Institutional Memory)

**Dependencies:** None  
**Complexity:** Low  
**Priority:** High (quick win, high value)

## Overview

Persistent file of "lessons learned" that accumulates across runs and sessions. Before each task iteration, the agent reads this file to avoid repeating past mistakes.

## Reference Implementation

From Ralph's implementation:
- `guardrails.md` lives in `.ralph/` and persists across runs
- Before each iteration, the rendered prompt includes guardrails content
- After failures, relevant lessons are appended to guardrails
- Acts as "institutional memory" that survives context window limits

Key insight: Unlike ephemeral error logs, guardrails are **curated lessons** that inform future behavior, not just a record of what went wrong.

## Problem Statement

Current cub failure patterns:
1. Agent makes same mistake across different runs
2. Context window clears between sessions, losing learned patterns
3. Error logs capture what failed, not what to do differently
4. Teams manually maintain tribal knowledge about "don't do X"

Guardrails provide persistent, machine-readable guidance that grows over time.

## Proposed Interface

```bash
# View current guardrails
cub guardrails show

# Add a guardrail manually
cub guardrails add "Always run 'npm install' before 'npm test' in this project"

# Add from recent failure (interactive)
cub guardrails learn

# Import guardrails from another project
cub guardrails import /path/to/.cub/guardrails.md

# Clear guardrails (with confirmation)
cub guardrails clear
```

## File Format

Location: `.cub/guardrails.md`

```markdown
# Cub Guardrails

Lessons learned from previous runs. Read before each task iteration.

---

## Project-Specific

### Testing
- Always run `npm install` before `npm test` - dependencies may have changed
- The test suite requires `DATABASE_URL` env var to be set

### Build
- Use `npm run build:dev` for local testing, not `npm run build`
- TypeScript strict mode is enabled - no implicit any

### Git
- This project uses conventional commits - prefix with feat/fix/chore/docs

---

## Learned from Failures

### 2026-01-10 - beads-abc123
**Error:** Tests failed because database wasn't initialized
**Lesson:** Run `npm run db:setup` before running tests on fresh checkout

### 2026-01-12 - beads-def456
**Error:** Import failed due to circular dependency
**Lesson:** In this codebase, avoid importing from `lib/index.ts` - import specific files

### 2026-01-13 - beads-ghi789
**Error:** Rate limit hit during API calls
**Lesson:** Use mocked API responses in tests - real calls are rate-limited
```

## Auto-Learning from Failures

When a task fails after retries, cub can automatically extract lessons:

```bash
auto_learn_guardrail() {
  local task_id=$1
  local error_log=$2

  # Use AI to extract actionable lesson from failure
  local lesson=$(invoke_harness --prompt "
    Analyze this task failure and extract a reusable lesson.

    Task: $task_id
    Error log: $error_log

    Output a single sentence lesson in the format:
    'When X, do Y instead of Z'

    Focus on project-specific patterns, not general programming advice.
  " --model haiku)

  # Append to guardrails
  echo -e "\n### $(date +%Y-%m-%d) - $task_id" >> .cub/guardrails.md
  echo "**Error:** $(extract_error_summary "$error_log")" >> .cub/guardrails.md
  echo "**Lesson:** $lesson" >> .cub/guardrails.md
}
```

## Integration with Prompt

Guardrails are injected into the task prompt:

```bash
render_task_prompt() {
  local task_spec=$1

  cat <<EOF
## Guardrails (Lessons from Previous Runs)

$(cat .cub/guardrails.md 2>/dev/null || echo "No guardrails yet.")

---

## Current Task

$task_spec
EOF
}
```

## Configuration

```json
{
  "guardrails": {
    "enabled": true,
    "file": ".cub/guardrails.md",
    "auto_learn": {
      "enabled": true,
      "on_failure": true,
      "on_retry": false,
      "model": "haiku"
    },
    "include_in_prompt": true,
    "max_size_kb": 50
  }
}
```

## Guardrail Categories

### 1. Project-Specific
Things unique to this codebase:
- Build commands and quirks
- Test setup requirements
- Naming conventions
- File organization patterns

### 2. Failure-Derived
Lessons learned from actual failures:
- Error patterns and solutions
- Common pitfalls in this project
- Workarounds for known issues

### 3. Imported
Guardrails from templates or other projects:
- Team-wide best practices
- Organization standards
- Framework-specific patterns

## Size Management

Guardrails should stay focused and relevant:

```bash
manage_guardrails_size() {
  local max_kb=${CUB_GUARDRAILS_MAX_KB:-50}
  local current_kb=$(du -k .cub/guardrails.md | cut -f1)

  if [[ $current_kb -gt $max_kb ]]; then
    # Prompt for curation
    echo "Guardrails file is ${current_kb}KB (limit: ${max_kb}KB)"
    echo "Consider running 'cub guardrails curate' to consolidate"
  fi
}

# AI-assisted curation
cub_guardrails_curate() {
  invoke_harness --prompt "
    Consolidate these guardrails, removing duplicates and outdated entries.
    Keep the most actionable, project-specific lessons.
    Target: under 50 entries.

    Current guardrails:
    $(cat .cub/guardrails.md)
  " --model sonnet
}
```

## Relationship to Other Features

| Feature | Relationship |
|---------|--------------|
| Runs Analysis | Can identify patterns that become guardrails |
| Re-anchoring | Guardrails are part of re-anchoring context |
| Circuit Breaker | Failures that trip circuit breaker should generate guardrails |
| Fresh Context Mode | Guardrails persist even when context is cleared |

## Implementation Notes

### New Files
- `lib/guardrails.sh` - Guardrails management functions
- `lib/cmd_guardrails.sh` - CLI subcommand

### Integration Points
1. **lib/cmd_run.sh**: Include guardrails in prompt rendering
2. **lib/failure.sh**: Auto-learn on failure (if enabled)
3. **lib/artifacts.sh**: Store guardrails snapshot in run artifacts

### Templates
Add default guardrails template:
```
templates/guardrails.md
```

## Acceptance Criteria

### Phase 1: Core
- [ ] `.cub/guardrails.md` file support
- [ ] `cub guardrails show` command
- [ ] `cub guardrails add` command
- [ ] Include guardrails in task prompts
- [ ] `cub init` creates empty guardrails file

### Phase 2: Learning
- [ ] Auto-learn from failures (AI-extracted lessons)
- [ ] `cub guardrails learn` interactive command
- [ ] Link guardrails to source tasks/failures

### Phase 3: Management
- [ ] Size monitoring and curation warnings
- [ ] `cub guardrails curate` AI-assisted cleanup
- [ ] Import/export between projects
- [ ] Guardrails in run artifacts for debugging

## Future Enhancements

- Guardrails effectiveness tracking (did the lesson prevent repeat failures?)
- Team-shared guardrails repository
- Guardrails validation (test that lessons are still relevant)
- Guardrails versioning and history
- Integration with PROMPT.md (auto-suggest prompt improvements from guardrails)
