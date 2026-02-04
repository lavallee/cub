---
status: complete
version: 0.14
priority: high
complexity: high
dependencies: []
created: 2026-01-05
updated: 2026-01-19
completed: 2026-01-13
implementation:
- src/cub/cli/prep.py
- src/cub/cli/triage.py
- src/cub/cli/architect.py
- src/cub/cli/plan.py
- src/cub/cli/bootstrap.py
- src/cub/core/prep/
- cub prep, cub triage, cub architect, cub plan, cub bootstrap commands
notes: |
  Full prep pipeline: triage→architect→plan→bootstrap implemented.
  Integrates chopshop planning workflow into cub.
  Foundation for vision-to-tasks transformation.
source: Integration of chopshop into cub, inspired by Shape Up
spec_id: cub-009
---
# Vision-to-Tasks Pipeline

**Dependencies:** None (foundational feature)  
**Complexity:** High  
**Supersedes/Integrates:** Interview Mode, PRD Import, Plan Review (partial)

## Overview

A complete pipeline for transforming high-level product visions into executable, AI-agent-friendly tasks. This integrates chopshop's planning workflow directly into cub, enabling end-to-end lifecycle management from idea to working code.

**Chopshop terminology retired. Artifacts move to `.cub/`.**

## The Gap This Fills

Current cub assumes tasks already exist. But where do tasks come from?

```
BEFORE (gap):
  Vision Doc ──?──> Tasks ──cub run──> Working Code

AFTER (integrated):
  Vision Doc ──cub pipeline──> Tasks ──cub run──> Working Code
```

## Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────┐
│                    CUB VISION-TO-TASKS PIPELINE                 │
└─────────────────────────────────────────────────────────────────┘

  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │  TRIAGE  │───>│ ARCHITECT│───>│  PLAN    │───>│BOOTSTRAP │
  │          │    │          │    │          │    │          │
  │ Clarify  │    │ Design   │    │ Decompose│    │ Import   │
  │ Product  │    │ Technical│    │ into     │    │ to Beads │
  │ Vision   │    │ Approach │    │ Tasks    │    │          │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘
       │               │               │               │
       ▼               ▼               ▼               ▼
  triage.md      architect.md     plan.jsonl     .beads/
                                  plan.md        PROMPT.md
                                                 AGENT.md
```

## Stage 1: Triage (Requirements Refinement)

**Purpose:** Ensure product clarity before any technical work.

**From chopshop:** `/chopshop:triage` → `cub triage`

### Interface

```bash
# Start triage from vision document
cub triage VISION.md
cub triage PRD.md
cub triage                    # Interactive, no input file

# Options
cub triage --depth light      # 5 min coherence check
cub triage --depth standard   # 15 min full review (default)
cub triage --depth deep       # 30 min + market analysis

# Resume existing session
cub triage --session <session-id>
```

### Interview Questions (from chopshop)

1. **Scope depth** - How thorough should this review be?
2. **Problem statement** - In one sentence, what problem does this solve? Who has it?
3. **Success criteria** - How will you know this project succeeded?
4. **Constraints** - Hard constraints? (timeline, budget, tech, regulations)

### Output

```
.cub/sessions/{session-id}/
└── triage.md
```

**triage.md structure:**
- Executive summary
- Problem statement (refined)
- Requirements (P0/P1/P2 prioritized)
- Constraints & assumptions
- Open questions
- Risks with mitigation strategies

### Relationship to Interview Mode

**Interview Mode spec becomes a subset of Triage:**
- Interview Mode's 40+ questions → incorporated into deep triage
- Interview Mode's per-task questioning → remains separate (task-level)
- Triage is project-level; Interview Mode is task-level

---

## Stage 2: Architect (Technical Design)

**Purpose:** Translate requirements into pragmatic technical architecture.

**From chopshop:** `/chopshop:architect` → `cub architect`

### Interface

```bash
# Design architecture for session
cub architect <session-id>
cub architect                 # Uses most recent session

# Options
cub architect --mindset prototype|mvp|production|enterprise
cub architect --scale personal|team|company|internet
```

### Mindset Framework (from chopshop)

| Mindset | Speed vs Quality | Testing | Architecture |
|---------|------------------|---------|--------------|
| **Prototype** | Speed first | Minimal | Monolith, shortcuts OK |
| **MVP** | Balanced | Critical path | Clean modules |
| **Production** | Quality first | Comprehensive | Scalable, observable |
| **Enterprise** | Maximum rigor | Full coverage | HA, security, compliance |

### Interview Questions

1. **Mindset** - Prototype → MVP → Production → Enterprise?
2. **Scale** - Personal → Team → Company → Internet-scale?
3. **Tech stack** - Preferences or constraints?
4. **Integrations** - External services to connect?

### Output

```
.cub/sessions/{session-id}/
├── triage.md
└── architect.md
```

**architect.md structure:**
- Technical summary
- Technology stack (with rationale)
- System architecture (ASCII diagram)
- Components & responsibilities
- Data model
- APIs/interfaces
- Implementation phases (logical build order)
- Technical risks
- Security considerations

### Relationship to Plan Review

**Plan Review spec validates architect output:**
- Feasibility analysis uses architect.md
- Architecture review checks consistency
- Plan Review runs after architect, before plan

---

## Stage 3: Plan (Task Decomposition)

**Purpose:** Break architecture into executable, AI-agent-friendly tasks.

**From chopshop:** `/chopshop:planner` → `cub plan`

### Interface

```bash
# Generate task plan for session
cub plan <session-id>
cub plan                      # Uses most recent session

# Options
cub plan --granularity micro|standard|macro
cub plan --prefix "proj-"     # Task ID prefix
```

### Granularity Options (from chopshop)

| Granularity | Duration | Best For |
|-------------|----------|----------|
| **Micro** | 15-30 min | AI agents (fits context window) |
| **Standard** | 1-2 hours | Human developers |
| **Macro** | Half-day+ | Milestones, checkpoints |

### Task Generation Strategy

From chopshop's proven approach:

1. **Phases → Epics** - Each implementation phase becomes an epic
2. **Vertical slices** - Features deliver end-to-end value (not horizontal layers)
3. **Micro-sizing** - Tasks fit in one AI context window
4. **Checkpoints** - Pause points for validation
5. **Dependencies** - Parent-child and blocking relationships
6. **Labels** - phase, model recommendation, complexity, domain, risk

### Task Description Template

Every generated task includes:

```markdown
## Context
{Why this task exists and how it fits}

## Implementation Hints
- Recommended Model: {opus|sonnet|haiku}
- Estimated Duration: {15m|30m|1h}
- Approach: {Actionable guidance}

## Implementation Steps
1. [Concrete step]
2. [Concrete step]

## Acceptance Criteria
- [ ] [Verifiable criterion]

## Files Likely Involved
- [path/to/file]
```

### Output

```
.cub/sessions/{session-id}/
├── triage.md
├── architect.md
├── plan.jsonl          # Beads-compatible import file
└── plan.md             # Human-readable summary
```

### Label System

| Label | Purpose |
|-------|---------|
| `phase-N` | Implementation phase |
| `model:opus\|sonnet\|haiku` | Complexity-based model recommendation |
| `complexity:high\|medium\|low` | Task complexity |
| `domain:setup\|model\|api\|ui\|test` | Work category |
| `risk:high\|medium` | Risk flag |
| `checkpoint` | Validation pause point |
| `slice:{name}` | Vertical slice grouping |

### Relationship to PRD Import

**PRD Import spec becomes a lightweight alternative:**
- PRD Import = direct document → tasks (less sophisticated)
- Plan stage = full pipeline output (triage → architect → plan)
- Both output beads-compatible JSONL
- PRD Import useful for simple cases; Plan for complex projects

---

## Stage 4: Bootstrap (Transition to Execution)

**Purpose:** Initialize beads and transition from planning to execution.

**From chopshop:** `/chopshop:bootstrap` → `cub bootstrap`

### Interface

```bash
# Bootstrap from session
cub bootstrap <session-id>
cub bootstrap                 # Uses most recent session

# Options
cub bootstrap --prefix "proj-"
cub bootstrap --skip-prompt   # Don't generate PROMPT.md
cub bootstrap --dry-run       # Preview without executing
```

### Pre-flight Checks

1. Git repository exists
2. Working directory clean (or handle uncommitted)
3. `bd` (beads) installed
4. `jq` installed
5. No existing beads state (or confirm overwrite)

### Process

1. Initialize beads: `bd init --prefix {prefix}`
2. Import plan: `bd import -i plan.jsonl`
3. Sync state: `bd sync`
4. Validate import (counts, dependencies, labels)
5. Generate PROMPT.md (from triage + architect)
6. Generate AGENT.md (build/test instructions)
7. Create atomic git commit

### Output

```
project/
├── .beads/             # Beads task database
├── PROMPT.md           # Agent system prompt
├── AGENT.md            # Build/run instructions
└── .cub.json           # Cub configuration
```

### PROMPT.md Generation

Synthesized from triage + architect:

```markdown
# {Project Name}

## Problem
{From triage: problem statement}

## Success Criteria
{From triage: success criteria}

## Technical Approach
{From architect: summary}

## Architecture
{From architect: ASCII diagram}

## Constraints
{From triage: constraints}

## Current Phase
Phase 1: {phase name}
```

---

## Unified CLI

```bash
# Full pipeline (interactive)
cub pipeline VISION.md

# Individual stages
cub triage [input.md]
cub architect [session-id]
cub plan [session-id]
cub bootstrap [session-id]

# Session management
cub sessions                  # List sessions
cub sessions show <id>        # Show session details
cub sessions delete <id>      # Delete session

# Validation
cub validate                  # Validate beads state
cub validate --fix            # Auto-fix issues
```

### Pipeline Command

`cub pipeline` runs all stages with prompts between:

```bash
$ cub pipeline VISION.md

[Triage] Starting requirements refinement...
? How thorough should this review be? (Standard)
? In one sentence, what problem does this solve? > ...
...
✓ Triage complete: .cub/sessions/myproj-20260113-160000/triage.md

[Architect] Starting technical design...
? What mindset: Prototype, MVP, Production, Enterprise? (MVP)
...
✓ Architect complete: .cub/sessions/myproj-20260113-160000/architect.md

[Plan] Generating tasks...
? Task granularity: Micro, Standard, Macro? (Micro)
...
✓ Plan complete: 47 tasks generated

[Bootstrap] Transitioning to execution...
? Initialize beads with prefix "myproj-"? (Y)
✓ Beads initialized with 47 tasks
✓ PROMPT.md generated
✓ Committed: "chore: bootstrap from cub pipeline session"

Ready to run: cub run
```

---

## Session Storage

**Retired:** `.chopshop/sessions/` → `.cub/sessions/`

```
.cub/
├── sessions/
│   └── {project}-{YYYYMMDD-HHMMSS}/
│       ├── triage.md
│       ├── architect.md
│       ├── plan.jsonl
│       └── plan.md
├── runs/                    # Existing: run artifacts
├── hooks/                   # Existing: project hooks
└── config.json              # Existing: project config
```

Sessions are gitignored (planning artifacts, not source code) but preserved locally for reference.

---

## Integration with Existing Specs

### Interview Mode

**Reconciliation:**
- **Project-level interviews** → Absorbed into Triage stage
- **Task-level interviews** → Remains as Interview Mode
- Interview Mode becomes "deep dive on a single task"
- Triage is "deep dive on the whole project"

Update Interview Mode spec:
```markdown
**Note:** For project-level requirements refinement, use `cub triage`.
Interview Mode is for deep-diving into individual tasks after planning.
```

### PRD Import

**Reconciliation:**
- PRD Import = lightweight, direct conversion
- Pipeline = full planning workflow
- Both valid, different use cases

Update PRD Import spec:
```markdown
**Note:** For complex projects, use `cub pipeline` for full
triage → architect → plan workflow. PRD Import is for quick
conversion of existing structured documents.
```

### Plan Review

**Reconciliation:**
- Plan Review validates output from architect/plan stages
- Can run automatically between stages
- Remains as quality gate

Update Plan Review spec:
```markdown
**Integration:** Plan Review can run automatically:
- After `cub architect` → validates technical design
- After `cub plan` → validates task decomposition
- Before `cub bootstrap` → final validation
```

### Implementation Review

**No change needed** - operates at task completion, after planning.

---

## Migration from Chopshop

For existing chopshop users:

```bash
# One-time migration
mv .chopshop/sessions/* .cub/sessions/

# Update gitignore
# Remove: .chopshop/
# Ensure: .cub/sessions/ is ignored

# Commands map:
# /chopshop:triage    → cub triage
# /chopshop:architect → cub architect
# /chopshop:planner   → cub plan
# /chopshop:bootstrap → cub bootstrap
```

---

## Configuration

```json
{
  "pipeline": {
    "default_depth": "standard",
    "default_mindset": "mvp",
    "default_granularity": "micro",
    "auto_review": true,
    "auto_bootstrap": false
  },
  "sessions": {
    "retention_days": 30,
    "gitignore": true
  }
}
```

---

## Acceptance Criteria

### Triage Stage
- [ ] Parse vision/PRD documents
- [ ] Interactive interview flow
- [ ] Depth options (light/standard/deep)
- [ ] Generate triage.md output

### Architect Stage
- [ ] Read triage output
- [ ] Mindset framework questions
- [ ] Generate architect.md with diagrams
- [ ] Technical risk identification

### Plan Stage
- [ ] Read architect output
- [ ] Granularity options
- [ ] Generate plan.jsonl (beads-compatible)
- [ ] Generate plan.md (human-readable)
- [ ] Proper labeling system
- [ ] Dependency wiring

### Bootstrap Stage
- [ ] Pre-flight checks
- [ ] Beads initialization
- [ ] Plan import
- [ ] PROMPT.md generation
- [ ] AGENT.md generation
- [ ] Atomic git commit

### Pipeline Command
- [ ] Run all stages in sequence
- [ ] Prompts between stages
- [ ] Session management
- [ ] Validation integration

---

## Future Enhancements

- Web UI for pipeline (visual planning)
- Template library (common project types)
- Team collaboration on planning
- Version control for plans (iterate on design)
- AI-assisted triage (auto-answer questions from codebase)
- Integration with design tools (Figma → architect)
