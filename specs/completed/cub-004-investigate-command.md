---
spec_id: cub-004
---
# cub investigate - Intelligent Capture Processing

## Overview

The `cub investigate` command processes captures (ideas, notes, observations) and moves them forward by determining what action each needs and taking it.

## The Problem

Captures accumulate over time but need different handling:
- Some are quick fixes that could be done immediately
- Some need research before we know what to do
- Some need design work and user feedback
- Some are too vague to act on

Without a system to process them, captures become a graveyard of ideas.

## Proposed Solution

An intelligent command that:
1. Analyzes each capture to determine its category
2. Takes appropriate action based on category
3. Tracks progress and produces actionable outcomes
4. When a captured idea moves to a logical state post-capture, the specific capture element is archived

## Capture Categories

### 1. Quick Fix (`quick`)
Small, well-defined changes that can be executed immediately.

**Examples:**
- "remove curb reference in CHANGELOG.md"
- "fix typo in README"
- "update copyright year"

**Action:** Create beads task → optionally auto-execute, archive capture

### 2. Code Audit (`audit`)
Need to search/explore the codebase to understand scope.

**Examples:**
- "track all places using claude models directly"
- "find all hardcoded paths"
- "audit error handling patterns"

**Action:** Run code analysis → produce report → propose changes

### 3. Research (`research`)
Need external investigation - web search, docs, examples.

**Examples:**
- "check out julia from google for inspiration"
- "research best practices for CLI help"
- "compare to similar tools"

**Action:** Web search + doc reading → summarize findings → recommend actions

### 4. Design (`design`)
Need thinking, planning, architecture decisions, user feedback.

**Examples:**
- "think through investigate command workflow"
- "design plugin system"
- "plan v2.0 architecture"

**Action:** Produce design doc → present for feedback → create tasks when approved

### 5. Spike (`spike`)
Produce some software on a spike/ branch that explore one or more possible approaches
**Examples:**
- "test whether this new tool can help triage issues"
- "try a skill for prioritizing features"

### 6. Clarification Needed (`unclear`)
Too vague or ambiguous to act on.

**Examples:**
- "make it better"
- "fix the thing"
- "consider alternatives"

**Action:** Ask user clarifying questions → update capture → re-categorize

## CLI Interface

```bash
# Investigate a single capture
cub investigate cap-abc123

# Investigate all active captures
cub investigate --all

# Investigate with specific mode
cub investigate cap-abc123 --mode=research

# Batch quick fixes together
cub investigate --all --batch-quick-fixes

# Dry run - show what would be done
cub investigate --all --dry-run

# Interactive mode - confirm each action
cub investigate --all --interactive
```

## Workflow

```
┌─────────────┐
│   Capture   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Categorize │ ← AI analyzes content, tags, context
└──────┬──────┘
       │
       ├─── quick ────► Create task → Execute → Close
       │
       ├─── audit ────► Explore codebase → Report → Tasks
       │
       ├─── research ──► Web search → Summarize → Recommend
       │
       ├─── design ───► Design doc → Feedback → Tasks
       |
       |--- spike ----> Develop some ideas on a branch -> Feedback -> Tasks
       │
       └─── unclear ──► Ask questions → Update → Re-categorize
       |
       |

|-------------|
|   Trigger   |
|-------------|
      |
      |---- if the capture isn't moved out of this stage, append research/findings and add metadata to the frontmatter indicating a need for human review.
```

## Output Artifacts

Each investigation produces artifacts stored in `specs/investigations/`:

```
specs/investigations/
├── cap-abc123-audit.md      # Code audit report
├── cap-def456-research.md   # Research findings
├── cap-ghi789-design.md     # Design document
└── cap-jkl012-questions.md  # Clarification questions
```

## Integration Points

### With Captures System
- Reads from global/project capture stores
- Updates capture status (active → investigated)
- Links captures to resulting tasks/artifacts

### With Beads
- Creates tasks for actionable items
- Links tasks back to source captures
- Can batch multiple quick fixes into one task

### With Prep Pipeline
- Design outcomes feed into triage/architect
- Large features go through full prep pipeline
- Small fixes bypass prep, go straight to execution

## Implementation Phases

### Phase 1: Categorization
- AI-powered analysis of capture content
- Manual override via `--mode` flag
- Store category in capture metadata

### Phase 2: Quick Fixes
- Auto-create beads tasks
- Optional auto-execution with `cub run`
- Batch mode for multiple small fixes

### Phase 3: Code Audit
- Integration with grep/glob tools
- Pattern matching for common audits
- Structured report generation

### Phase 4: Research
- Web search integration
- Documentation fetching
- Findings summarization

### Phase 5: Design Mode
- Design document templates
- Feedback collection workflow
- Task generation from approved designs

## Example Session

```
$ cub investigate --all

Analyzing 4 captures...

cap-1eq4cf: "remove curb reference in CHANGELOG"
  Category: quick
  Action: Creating task beads-xyz...

cap-lvu73k: "track all places using claude models"
  Category: audit
  Action: Running code analysis...
  Found 5 files with direct claude usage
  Report: specs/investigations/cap-lvu73k-audit.md

cap-001: "check out julia from google for inspiration"
  Category: research
  Action: Searching for "julia google AI coding assistant"...
  Summary: specs/investigations/cap-001-research.md

cap-b04hr9: "think through investigate command workflow"
  Category: design
  Action: This capture is about the investigate command itself!
  Skipping (meta-investigation)

Summary:
  - 1 quick fix task created
  - 1 code audit completed
  - 1 research summary generated
  - 1 skipped (self-referential)
```

## Open Questions

1. **Automation level**: How much should be auto-executed vs. requiring confirmation?

we should err on the side of execution, especially when we can leverage the existing codebase, tools like web search, prior .cub runs and other documentation, and the ability to put work on branches.

2. **AI model choice**: Use Haiku for categorization (fast/cheap) or Sonnet for better understanding?

right now, use sonnet.

3. **Batch semantics**: How to group quick fixes? By file? By topic? By tag?

by tag

4. **Research depth**: How deep should web research go? Single search or iterative?

on a case-by-case basis. we should do shallow research (10 searches/turns or less) inline, and queue up deeper research as needed. we can build successive tasks/stages for the latter 

5. **Design feedback**: How to collect feedback? Interactive? PR-based? Slack integration?

tbd. for now, let's write to files and communicate like this. not ideal but a start.

## Success Metrics

- Captures processed per session
- Time from capture to actionable task
- Accuracy of auto-categorization
- User override rate (indicates categorization quality)
