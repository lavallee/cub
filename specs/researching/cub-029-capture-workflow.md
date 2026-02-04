---
status: researching
priority: medium
complexity: medium
dependencies:
- workflow-management.md
- capture.md
created: 2026-01-15
updated: 2026-01-19
readiness:
  score: 4
  blockers:
  - Depends on workflow engine
  - Capture feature needs completion
  questions:
  - How much automation vs manual transition?
  - What triggers workflow progression?
  decisions_needed:
  - Define workflow stages and transitions
  - Choose automation level
  tools_needed:
  - Dependency Analyzer (needs workflow engine + capture)
  - Design Pattern Matcher (workflow patterns for progressive refinement)
  - 'Trade-off Analyzer (automation level: manual, assisted, automatic)'
notes: |-
  Depends on workflow engine and capture feature.
  Progressive refinement from idea to task.
spec_id: cub-029
---
# Capture-to-Task Workflow

## Overview

Captures are lightweight, low-friction ways to record ideas, thoughts, and observations during development. The capture workflow moves these raw inputs through progressive refinement until they become actionable tasks or documented decisions.

## Capture Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Capture   │────▶│ Investigate │────▶│   Process   │────▶│   Archive   │
│   (raw)     │     │ (categorize)│     │  (action)   │     │  (done)     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Unclear   │
                    │ (needs human│
                    │   review)   │
                    └─────────────┘
```

## Stage 1: Capture

**Command:** `cub capture "your idea here"`

Captures are stored with:
- Random 6-char alphanumeric ID (e.g., `cap-a7x3m2`)
- AI-generated slug for human-readable filename
- Timestamp and source metadata
- Optional tags for organization

**Storage:** Global by default (`~/.local/share/cub/captures/{project}/`), safe from branch deletion.

## Stage 2: Investigate

**Command:** `cub investigate [capture-id]` or `cub investigate --all`

The investigate command analyzes captures and categorizes them:

| Category | Indicators | Action |
|----------|------------|--------|
| **quick** | "fix typo", "add option", "should take", short & specific | Create task immediately |
| **audit** | "track all", "find all", "where do we" | Run code search, generate report |
| **research** | "check out", "look at", "compare", "best practice" | Create research template |
| **design** | "think through", "architect", "plan", "how should" | Create design doc template |
| **spike** | "try", "experiment", "prototype", "proof of concept" | Create spike task with branch name |
| **unclear** | Short, missing context, no clear action | Mark for human review with questions |

## Stage 3: Process

Each category has a processor that moves the capture forward:

### Quick Fix Processor
- Creates a task via TaskService with:
  - Low complexity rating
  - 15m estimated duration
  - `quick-fix` label
- Archives the capture immediately

### Audit Processor
- Extracts search patterns from capture content
- Runs `rg` (ripgrep) across codebase
- Generates report at `specs/investigations/{id}-audit.md`
- Links report back to capture

### Research Processor
- Creates research template at `specs/investigations/{id}-research.md`
- Includes suggested search queries
- Marks capture as `needs_human_review`
- Ready for web search and AI-assisted research

### Design Processor
- Creates design doc template at `specs/investigations/{id}-design.md`
- Includes sections: Problem, Goals, Non-Goals, Proposed Solution, Alternatives
- Marks capture as `needs_human_review`

### Spike Processor
- Creates task via TaskService with:
  - Suggested branch name (`spike/{slug}`)
  - Time-box guidelines (2-4 hours)
  - Success criteria (validate/invalidate, document learnings)
  - `spike` label
- Archives the capture immediately

### Unclear Processor
- Generates clarifying questions based on what's missing
- Appends questions to capture
- Marks capture as `needs_human_review`
- User answers questions, then re-runs investigate

## Stage 4: Archive

When a capture is fully processed:
1. Status updated to `archived` in frontmatter
2. File moved to `archived/` subdirectory
3. Original capture preserved for reference

Captures stay active (not archived) when:
- Marked `needs_human_review`
- Created artifacts that need completion (research, design docs)

## Batching

For efficiency, quick fixes can be batched:

```bash
cub investigate --all --batch-quick-fixes
```

This creates a single task containing multiple quick fixes, useful when many small changes accumulate.

## Human Review Flag

The `needs_human_review` flag indicates:
- Capture couldn't be fully automated
- Generated artifact needs human input
- Questions need answering before proceeding

View captures needing review:
```bash
cub captures --needs-review
```

## Integration with Task System

All task creation flows through `TaskService`:
- Consistent task structure across all sources
- Proper acceptance criteria
- Complexity and model recommendations
- Routes through configured backend (beads/json)

## Example Workflows

### Quick Enhancement
```
capture: "the CLI should accept --verbose flag"
    ↓ investigate
category: quick (matches "should accept")
    ↓ process
task created: beads-abc123
capture archived
```

### Research Topic
```
capture: "check out how Rust handles error propagation"
    ↓ investigate
category: research (matches "check out")
    ↓ process
template created: specs/investigations/cap-xyz-research.md
capture marked needs_human_review
    ↓ human completes research
    ↓ creates tasks from findings
capture archived manually
```

### Unclear Idea
```
capture: "make it faster"
    ↓ investigate
category: unclear (too short, no specifics)
    ↓ process
questions added:
  - What specifically is slow?
  - Which part of the codebase?
  - What's the target performance?
capture marked needs_human_review
    ↓ human answers questions
    ↓ re-run investigate
category: audit (now has specifics)
    ↓ continues...
```

## Future Enhancements

- **AI-assisted categorization:** Use LLM for ambiguous captures
- **Deeper research:** Queue for multi-turn AI research sessions
- **Auto-batching by tag:** Group related captures automatically
- **Feedback loop:** Learn from human corrections to categorization
