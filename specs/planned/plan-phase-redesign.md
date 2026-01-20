---
status: draft
priority: high
complexity: high
dependencies: []
blocks: []
created: 2026-01-20
updated: 2026-01-20
readiness:
  score: 9
  blockers: []
  questions:
    - How does the SDK handle user interrupts gracefully mid-interview?
    - Should we check existing beads for epic ID collisions?
  decisions_needed: []
  tools_needed: []
decisions_made:
  - "Spec lifecycle: researching → planned → staged → implementing → released"
  - "Subcommands: cub plan orient, cub plan architect, cub plan itemize"
  - "Itemize outputs only itemized-plan.md; JSONL generated at stage time"
  - "Multiple plans per spec allowed; slug collision uses _alt_[a-z] suffix"
  - "No partial staging; task inclusion decisions happen at run time"
  - "Spec lifecycle movement should be automated"
  - "Add TaskBackend.import_tasks() for bulk import"
  - "released transition wired into scripts/cut-release.sh"
  - "plan.json stores spec filename; search specs/ subdirs to find it"
  - "SYSTEM-PLAN.md schema: YOLO, evolve organically"
  - "CRITICAL: Beads IDs use random suffix (cub-k7m), NOT sequential (cub-001)"
---

# Plan Phase Redesign

## Overview

Redesign the `cub prep` pipeline to be clearer, more integrated with the spec workflow, and implemented natively in Python. The core rename is `prep` → `plan`, with interview steps renamed for clarity: triage→orient, plan→itemize. Bootstrap becomes `stage`, serving as the explicit bridge between planning and execution.

## Goals

- **Clearer nomenclature**: Names that reflect what each step actually does
- **Spec workflow integration**: Planning moves specs through their lifecycle
- **Self-answering interviews**: Steps attempt to answer their own questions, presenting assumptions for review
- **Constitutional memory**: Learnings accumulate in `.cub/SYSTEM-PLAN.md`
- **Python-native**: Full implementation in Python using Claude Agent SDK
- **Clean separation**: Planning produces plans; staging activates them for execution

## Non-Goals

- Backward compatibility with `.cub/sessions/` (breaking change accepted)
- Supporting both bash and Python implementations (full migration)
- Automatic staging (plans should rest before becoming active work)

---

## Nomenclature Changes

| Current | New | Rationale |
|---------|-----|-----------|
| `cub prep` | `cub plan` | "Plan" is what we're doing; "prep" was vague |
| `triage` | `orient` | We're orienting ourselves to the problem space, not triaging emergencies |
| `architect` | `architect` | Still accurate - designing the technical approach |
| `plan` (stage) | `itemize` | We're itemizing work into discrete tasks |
| `bootstrap` | `stage` | Staging work for execution; bridge metaphor is clearer |
| `.cub/sessions/` | `/plans/` | Plans are first-class artifacts, not hidden sessions |

---

## Directory Structure

### Plans Directory

Plans live at project root, not hidden in `.cub/`:

```
project/
├── plans/
│   ├── user-auth/                    # Plan slug (matches spec name if from spec)
│   │   ├── plan.json                 # Plan metadata, state, and spec linkage
│   │   ├── orientation.md            # Stage 1 output
│   │   ├── architecture.md           # Stage 2 output
│   │   └── itemized-plan.md          # Stage 3 output (human-readable, single source of truth)
│   └── api-redesign/
│       └── ...
├── specs/
│   ├── researching/                  # Ideas under exploration (-ing = alive)
│   ├── planned/                      # Plan exists, not yet staged (past = at rest)
│   ├── staged/                       # Tasks in task backend, ready to build (past = at rest)
│   ├── implementing/                 # Active work happening (-ing = alive)
│   └── released/                     # Shipped, available for drift audit (past = at rest)
└── .cub/
    └── SYSTEM-PLAN.md                # Constitutional learnings
```

### Plan Slug Generation

1. **From spec**: Use spec filename without extension (`user-auth.md` → `user-auth/`)
2. **From vision doc**: Slugify the document name
3. **Interactive**: Generate from problem statement during orient phase
4. **Override**: `--slug custom-name` flag

**Collision handling**: Multiple plans can exist for the same spec (e.g., testing divergent approaches, A/B testing). If the slug already exists in `/plans/`:

```
user-auth/          # First plan
user-auth_alt_a/    # Second plan (alternative approach)
user-auth_alt_b/    # Third plan
```

Use `_alt_[a-z]` suffix rather than version numbers since successive plans aren't necessarily improvements—they may be parallel alternatives being evaluated.

### plan.json Structure

Each plan has a `plan.json` metadata file:

```json
{
  "slug": "user-auth",
  "created": "2026-01-20T10:30:00Z",
  "updated": "2026-01-20T14:45:00Z",
  "status": "complete",
  "spec_file": "user-auth.md",
  "stages": {
    "orient": "complete",
    "architect": "complete",
    "itemize": "complete"
  },
  "project": "cub"
}
```

**Spec linkage**: The `spec_file` field stores just the filename (not the full path). To find the spec, search `specs/` subdirectories:
- `specs/researching/{spec_file}`
- `specs/planned/{spec_file}`
- `specs/staged/{spec_file}`
- `specs/implementing/{spec_file}`
- `specs/released/{spec_file}`

This allows specs to move through their lifecycle without breaking plan linkage.

### Spec Workflow Stages

5 stages with intentional word-form distinction:

| Stage | Form | State | Meaning |
|-------|------|-------|---------|
| `researching` | -ing | alive | Being explored, questions being answered |
| `planned` | past | at rest | Plan exists, ready to stage |
| `staged` | past | at rest | Tasks in backend, ready to build |
| `implementing` | -ing | alive | Active work happening |
| `released` | past | at rest | Shipped, available for drift audit |

**Automated spec lifecycle transitions:**

| Trigger | Spec Movement | Automation |
|---------|---------------|------------|
| `cub plan` completes | `researching/` → `planned/` | Automatic |
| `cub stage` completes | `planned/` → `staged/` | Automatic |
| First task starts (`cub run`) | `staged/` → `implementing/` | Automatic |
| `scripts/cut-release.sh` | `implementing/` → `released/` | Hook in release script |

Spec movement should be as automated as possible—users shouldn't need to manually `git mv` spec files between directories.

**Drift detection:**
- If asked to plan a spec in `staged/` or `implementing/`, assess current implementation state
- Report drift between spec and codebase
- Option to create delta plan or re-plan from scratch

---

## Interview Steps

### Stage 1: Orient (was Triage)

**Purpose**: Get oriented to the problem space. Understand what we're solving and for whom.

**Self-answering behavior**:
1. Read the input document (spec, vision doc, or prompt)
2. Consult `.cub/SYSTEM-PLAN.md` for project patterns
3. Analyze codebase context (existing patterns, tech stack)
4. Generate answers to orient questions
5. Present assumptions for user review/correction

**Questions**:
1. **Depth**: Light (coherence check) / Standard (full review) / Deep (+ market analysis)
2. **Problem statement**: What problem does this solve? Who has it?
3. **Success criteria**: How will we know this succeeded?
4. **Constraints**: Hard limits (time, tech, budget, compliance)?
5. **MVP boundary**: What's the smallest useful version?
6. **Concerns**: What keeps you up at night about this?

**Output**: `orientation.md`
- Problem statement (refined)
- Requirements (P0/P1/P2)
- Constraints
- Open questions
- Risks with mitigations

### Stage 2: Architect

**Purpose**: Design the technical approach that satisfies the requirements.

**Self-answering behavior**:
1. Read `orientation.md`
2. Analyze codebase (CLAUDE.md, existing patterns, file structure)
3. Consult `.cub/SYSTEM-PLAN.md` for architectural patterns
4. Generate architectural decisions based on context
5. Present key decisions for user review

**Questions**:
1. **Mindset**: Prototype / MVP / Production / Enterprise
2. **Scale**: Personal / Team / Product / Internet-scale
3. **Tech stack**: Preferences or constraints beyond existing?
4. **Integrations**: External services to connect?

**Output**: `architecture.md`
- Technical summary
- Technology choices (with rationale)
- System architecture (ASCII diagram)
- Components and responsibilities
- Data model
- APIs/interfaces
- Implementation phases
- Technical risks

### Stage 3: Itemize (was Plan)

**Purpose**: Break the architecture into discrete, executable tasks.

**Self-answering behavior**:
1. Read `orientation.md` and `architecture.md`
2. Apply micro-task sizing (15-30 min per task for AI agents)
3. Wire dependencies based on implementation phases
4. Generate task descriptions with acceptance criteria
5. Present task graph for review

**Output**: `itemized-plan.md` - The single source of truth for the plan

This file is:
- **Self-contained at a high level**: Can be understood without reading all other files
- **References context**: Links to orientation.md, architecture.md, and the original spec
- **Editable**: Human can review and modify before staging
- **Parseable**: Structured markdown that `cub stage` converts to tasks

No `.jsonl` file is generated during itemize. The JSONL is generated on-the-fly by `cub stage` when the plan is activated, ensuring the editable `.md` remains the single source of truth.

**`itemized-plan.md` structure**:

```markdown
# Itemized Plan: {Plan Name}

> Source: [specs/researching/user-auth.md](../specs/researching/user-auth.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)

## Context Summary

{2-3 paragraph synthesis of problem, approach, and key constraints from orient/architect - enough to understand the plan without reading those files, but not a full duplication}

## Epic: cub-k7m - User Authentication System
Priority: 1
Labels: phase-1, core

{Epic description referencing architectural decisions}

### Task: cub-k7m.1 - Create User model
Priority: 1
Labels: model, phase-1
Blocks: cub-k7m.2, cub-k7m.3

**Context**: {Why this task, how it fits}

**Implementation Steps**:
1. Create `src/models/user.py`
2. Define User schema with email, password_hash
3. Add migration

**Acceptance Criteria**:
- [ ] User model exists with required fields
- [ ] Migration runs successfully
- [ ] mypy passes

**Files**: `src/models/user.py`, `migrations/`

### Task: cub-k7m.2 - ...
```

**Task attributes**:
- Title, description, priority
- Labels (phase, complexity, domain, risk)
- Dependencies (Blocks: task-id, task-id)
- Model recommendation (in labels: model:opus, model:sonnet, model:haiku)
- Acceptance criteria
- Files likely involved

---

## Beads ID Format (CRITICAL)

**Beads is finicky about ID format. Sequential IDs cause collisions. Use random strings.**

| Type | Format | Example | ❌ Wrong |
|------|--------|---------|----------|
| Epic | `{project}-{random 3-5 char}` | `cub-a3x` | `cub-001` |
| Task | `{epic-id}.{number}` | `cub-a3x.1` | `AUTH-001` |
| Subtask | `{epic-id}.{task}.{number}` | `cub-a3x.1.2` | `cub-001.1.2` |

**ID generation rules:**
1. Epic IDs: `{project}-{random alphanumeric 3-5 chars}` (lowercase)
2. Task IDs: `{epic-id}.{sequential within epic}`
3. Subtask IDs: `{task-id}.{sequential within task}`
4. **NEVER** use global sequential numbers like `001`, `002` - they collide across plans/sessions

**Example hierarchy:**
```
cub-k7m           # Epic: User Authentication
├── cub-k7m.1     # Task: Create User model
├── cub-k7m.2     # Task: Add password hashing
│   ├── cub-k7m.2.1  # Subtask: Choose bcrypt library
│   └── cub-k7m.2.2  # Subtask: Write hash function
└── cub-k7m.3     # Task: Create login endpoint
```

The `itemize` stage must generate IDs in this format. The `stage` command passes them through to beads.

---

## Constitutional Memory: SYSTEM-PLAN.md

Located at `.cub/SYSTEM-PLAN.md`, this file accumulates project-specific learnings that inform future planning sessions.

### Schema

```markdown
# System Plan

Project-specific patterns and decisions that inform planning.

## Architecture Patterns

- **Data layer**: SQLAlchemy models in `src/*/models/`
- **API style**: REST with FastAPI, OpenAPI docs auto-generated
- **Testing**: pytest with fixtures in `tests/conftest.py`

## Constraints

- **Python 3.10+**: Required for match statements
- **No external databases**: SQLite only for v1
- **mypy strict**: All code must pass strict type checking

## Conventions

- **Naming**: snake_case for functions, PascalCase for classes
- **Imports**: Absolute imports from package root
- **Error handling**: Custom exceptions in `core/errors.py`

## Past Decisions

### 2026-01-15: Chose Pydantic v2 over dataclasses
Rationale: Better validation, serialization, and IDE support.
Context: Evaluated for config and model layer.

### 2026-01-18: Protocol classes over ABC inheritance
Rationale: More flexible, better for testing with mocks.
Context: Harness and task backend interfaces.
```

### How It's Used

**During interviews**:
1. Agent reads SYSTEM-PLAN.md before generating answers
2. Uses patterns to pre-fill architectural decisions
3. Flags when proposed approach deviates from established patterns
4. User can override or confirm

**Updating**:
1. After user confirms/corrects assumptions, significant learnings are appended
2. Only constitutional-level decisions (not task-specific details)
3. User approves additions before they're written

---

## Stage Command (was Bootstrap)

`cub stage` is the bridge between planning and execution. It takes a completed plan and activates it in the task system.

### Interface

```bash
# Stage a specific plan
cub stage plans/user-auth

# Stage with options
cub stage plans/user-auth --prefix "auth-"    # Task ID prefix
cub stage plans/user-auth --dry-run           # Preview without executing
cub stage plans/user-auth --skip-prompt       # Don't generate PROMPT.md
```

### Process

1. **Validate plan completeness**: All three stages (orient, architect, itemize) complete
2. **Pre-flight checks**: Git repo, clean state, task backend available
3. **Parse plan**: Read `itemized-plan.md` and convert to `Task` objects
4. **Import tasks**: Call `TaskBackend.import_tasks(tasks)` (backend decides implementation)
5. **Move spec**: If plan originated from a spec, move spec from `planned/` to `staged/`
6. **Generate artifacts**: PROMPT.md, AGENT.md (optional)
7. **Sync**: Call `TaskBackend.sync()` if backend supports it

### Single Source of Truth

The `itemized-plan.md` file is the authoritative plan definition:

```
itemized-plan.md (editable) ──→ cub stage ──→ TaskBackend ──→ Tasks
                                    │              │
                                    │              ├──→ BeadsBackend (via bd import)
                                    │              └──→ JSONBackend (direct write)
                                    │
                                    └──→ (intermediate JSONL if needed by backend)
```

**Backend abstraction**: Stage works through the `TaskBackend` interface, not directly with beads. This ensures compatibility with both:
- **BeadsBackend**: May use JSONL as intermediate format for `bd import`
- **JSONBackend**: Can write tasks directly without intermediate files

The implementation should follow whatever the emerging best practice is for each backend. If beads prefers JSONL import, generate it. If direct API calls are better, use those.

If you need to modify the plan after review:
1. Edit `itemized-plan.md` directly
2. Run `cub stage` again (will warn about existing tasks, offer to replace)

### Separation of Concerns

**Planning** (`cub plan`) produces:
- Analysis documents (orientation.md, architecture.md)
- Editable task definition (itemized-plan.md)
- Plans can sit at rest, be reviewed, iterated

**Staging** (`cub stage`) activates:
- Parses itemized-plan.md into tasks
- Imports tasks to beads
- Moves spec lifecycle forward (planned → staged)
- Creates execution artifacts
- Work becomes "imminent"

---

## Claude Agent SDK Integration

The SDK enables more graceful multi-step interaction than CLI dump-and-wait.

### Current Approach (Bash)

```
User runs `cub plan spec.md`
  → Bash invokes `claude --dangerously-skip-permissions "/cub:orient"`
  → User interacts with Claude Code
  → User exits Claude Code
  → Bash detects exit, checks for orientation.md
  → Bash invokes next stage
  → Repeat...
```

Problems:
- User must manually exit between stages
- No programmatic control over conversation
- State management is fragile
- Can't pause/resume gracefully

### SDK Approach (Python)

```python
from anthropic.claude_code import query, StreamEvent

async def run_plan_pipeline(spec_path: Path) -> PlanResult:
    """Run full planning pipeline with SDK."""

    # Initialize plan
    plan = Plan.create(spec_path)

    # Stage 1: Orient
    async for event in query(
        prompt=build_orient_prompt(spec_path),
        system=load_system_plan(),
        allowed_tools=["Read", "Glob", "Grep"],
    ):
        if isinstance(event, StreamEvent.Text):
            display_streaming(event.text)
        elif isinstance(event, StreamEvent.ToolUse):
            # Agent is exploring codebase
            pass

    # Extract orientation.md from result
    orient_result = extract_orient_output(event.result)

    # Present assumptions for review
    if not await user_confirms_assumptions(orient_result.assumptions):
        # User wants to correct - re-run with corrections
        orient_result = await rerun_with_corrections(...)

    # Continue to architect stage with full context
    # SDK maintains conversation context
    ...
```

### Benefits

1. **Seamless transitions**: Stages flow without user exits
2. **Programmatic control**: Python manages the workflow
3. **Streaming output**: Real-time display with Rich
4. **Pause/resume**: Can checkpoint and resume later
5. **Assumption review**: Programmatic checkpoints for user confirmation
6. **Tool restrictions**: Each stage gets appropriate tool access

### Interaction Model

```
User: cub plan specs/researching/user-auth.md

[Orient Phase]
Analyzing spec and codebase...

Based on the spec and existing patterns, here are my assumptions:

  Problem: Users need authentication for the API
  Constraints: Must use existing SQLAlchemy models
  MVP: Email/password login, no OAuth

[Press Enter to confirm, or type corrections]
> Actually, we need OAuth for Google

Understood. Updating assumptions...
[Re-analyzes with correction]

Assumptions confirmed. Generating orientation.md...
✓ Orient complete: plans/user-auth/orientation.md

[Architect Phase]
...continues seamlessly...
```

---

## CLI Interface

### Main Commands

```bash
# Full planning pipeline
cub plan [INPUT]                      # spec, vision doc, or interactive
cub plan specs/researching/idea.md    # Plan from spec
cub plan VISION.md                    # Plan from vision doc
cub plan                              # Interactive (prompts for input)

# Individual stages (for resuming or re-running)
cub plan orient [INPUT]               # Just orient stage
cub plan architect [PLAN_DIR]         # Just architect stage
cub plan itemize [PLAN_DIR]           # Just itemize stage

# Options
cub plan --slug my-feature            # Explicit plan slug
cub plan --depth deep                 # Orient depth
cub plan --mindset production         # Architect mindset
cub plan --continue plans/user-auth   # Resume incomplete plan

# Staging (bridge to execution)
cub stage [PLAN_DIR]                  # Stage a completed plan
cub stage plans/user-auth --dry-run   # Preview staging
```

### Plan Management

```bash
# List plans
cub plans                             # List all plans
cub plans --status complete           # Filter by status

# Show plan details
cub plans show user-auth              # Show plan summary

# Delete plan
cub plans delete user-auth            # Remove plan directory
```

---

## Implementation Plan

### Module Structure

```
src/cub/
├── cli/
│   ├── plan.py                       # cub plan command (with subcommands)
│   ├── stage.py                      # cub stage command
│   └── plans.py                      # cub plans list/show/delete
├── core/
│   ├── plan/
│   │   ├── __init__.py
│   │   ├── models.py                 # Plan, PlanStage, PlanStatus
│   │   ├── pipeline.py               # SDK-based pipeline orchestration
│   │   ├── orient.py                 # Orient stage logic
│   │   ├── architect.py              # Architect stage logic
│   │   ├── itemize.py                # Itemize stage logic
│   │   ├── parser.py                 # Parse itemized-plan.md to Task objects
│   │   ├── system_plan.py            # SYSTEM-PLAN.md management
│   │   └── prompts/
│   │       ├── orientation.md        # Orient prompt template
│   │       ├── architecture.md       # Architect prompt template
│   │       └── itemized-plan.md      # Itemize prompt template
│   ├── stage/
│   │   ├── __init__.py
│   │   └── stager.py                 # Staging logic (parse plan → TaskBackend)
│   ├── specs/
│   │   ├── __init__.py
│   │   └── workflow.py               # Spec lifecycle management (move between stages)
│   └── tasks/
│       └── backend.py                # Add TaskBackend.import_tasks() to Protocol
```

### Migration from Bash

Files to retire:
- `src/cub/bash/lib/cmd_prep.sh` (1,700+ lines)
- `src/cub/cli/delegated.py` prep-related functions

Files to rename:
- `.claude/commands/cub:triage.md` → `.claude/commands/cub:orient.md`
- `.claude/commands/cub:plan.md` → `.claude/commands/cub:itemize.md`

### Artifacts to Update

**Code**:
- [ ] Remove bash prep implementation
- [ ] Create `src/cub/core/plan/` module
- [ ] Create `src/cub/core/stage/` module
- [ ] Create `src/cub/core/specs/workflow.py` for spec lifecycle management
- [ ] Create CLI commands (plan, stage, plans)
- [ ] Add `TaskBackend.import_tasks()` to Protocol
- [ ] Implement `import_tasks()` in BeadsBackend (via `bd import`)
- [ ] Implement `import_tasks()` in JsonBackend (bulk append)
- [ ] Update SDK harness for pipeline support
- [ ] Create SYSTEM-PLAN.md management

**Skills/Commands** (`.claude/commands/`):
- [ ] Rename `cub:triage.md` → `cub:orient.md` (outputs `orientation.md`)
- [ ] Rename `cub:plan.md` → `cub:itemize.md` (outputs `itemized-plan.md`)
- [ ] Update `cub:architect.md` prompts (outputs `architecture.md`)
- [ ] Create `cub:stage.md` skill (if needed)
- [ ] Update `cub:spec-to-issues.md` if it references old pipeline

**Documentation**:

*Root-level docs:*
- [ ] Update `README.md` with new workflow (prep→plan, bootstrap→stage)
- [ ] Update `CLAUDE.md` with new commands and nomenclature
- [ ] Update `UPGRADING.md` with migration guide for existing sessions
- [ ] Update `CHANGELOG.md` with breaking changes
- [ ] Update `CONTRIBUTING.md` if it references prep pipeline

*MkDocs source (`docs-src/`):*
- [ ] Rename `docs-src/content/guide/prep-pipeline/` → `plan-pipeline/`
- [ ] Rename `triage.md` → `orient.md`
- [ ] Update `architect.md` content
- [ ] Rename `plan.md` → `itemize.md`
- [ ] Rename `bootstrap.md` → `stage.md`
- [ ] Update `index.md` with new overview
- [ ] Update `mkdocs.yml` navigation structure
- [ ] Rebuild site: `mkdocs build`

*Built documentation site (`docs/`):*
- [ ] Regenerate `docs/index.html` from docs-src
- [ ] Update `docs/HOOKS.md` if it references prep/bootstrap hooks
- [ ] Update `docs/install.sh` if it installs skills

*CLI help text (Typer docstrings):*
- [ ] Update all command docstrings in `src/cub/cli/plan.py`
- [ ] Update `cub --help` output to reflect new commands
- [ ] Add deprecation warnings to old command names

*Guardrails and project docs:*
- [ ] Update `.cub/guardrails.md` if it references old commands
- [ ] Update `.cub/README.md` if it documents session structure

*Migration artifacts:*
- [ ] Create `MIGRATION-PREP-TO-PLAN.md` one-pager for users
- [ ] Document `.cub/sessions/` → `/plans/` migration path

**Tests**:
- [ ] Unit tests for plan models
- [ ] Integration tests for pipeline
- [ ] Tests for spec workflow transitions
- [ ] Tests for SYSTEM-PLAN.md management

**Configuration**:
- [ ] Update `.cub.json` schema for plan settings
- [ ] Add plan-related config options

---

## Resolved Questions

1. **Concurrent plans**: ✅ Yes, multiple plans can exist for the same spec. Slug collision handled with `_alt_[a-z]` suffix (not version numbers, since alternatives aren't necessarily improvements).

2. **Partial staging**: ✅ No partial staging. Stage imports all tasks; inclusion decisions happen at `cub run` time.

3. **Plan versioning**: ✅ Use `_alt_` suffix for alternatives, not version numbers. Parallel approaches, not iterative refinement.

4. **TaskBackend.import_tasks()**: ✅ Add this method to the Protocol (see below).

5. **Spec move automation**: ✅ All transitions should be automatic. Users shouldn't manually move spec files.

---

## TaskBackend Protocol Extension

Add `import_tasks()` method to enable efficient bulk import:

```python
def import_tasks(self, tasks: list[Task]) -> list[Task]:
    """
    Bulk import tasks.

    Args:
        tasks: List of Task objects to create (IDs may be provisional)

    Returns:
        List of created tasks with assigned IDs

    Note:
        Backends should implement this efficiently:
        - BeadsBackend: Write temp JSONL → `bd import` → return tasks
        - JsonBackend: Load once → generate IDs → append all → save once
    """
    ...
```

**Implementation guidance:**

| Backend | Strategy |
|---------|----------|
| `BeadsBackend` | Write tasks to temp JSONL file, call `bd import tempfile.jsonl`, parse output for created IDs |
| `JsonBackend` | Load `prd.json` once, generate sequential IDs, append all tasks, save atomically once |

This keeps the abstraction clean while letting each backend optimize for its storage model.

---

## Resolved Questions (Additional)

6. **Hook for `implementing/` → `released/`**: ✅ Wired into `scripts/cut-release.sh`.

7. **Plan-to-spec linkage**: ✅ `plan.json` stores spec filename; spec found by searching `specs/` subdirectories.

8. **SYSTEM-PLAN.md format**: ✅ YOLO for now - evolve the schema organically.

9. **Beads ID format**: ✅ Epic IDs use random 3-5 char suffix (e.g., `cub-k7m`), NOT sequential numbers. Tasks are `{epic}.{n}`.

---

## Open Questions

1. **ID collision detection**: Should `cub plan` check existing beads for ID collisions before generating new epic IDs?

---

## Success Criteria

- [ ] `cub plan spec.md` runs full pipeline with seamless stage transitions
- [ ] Self-answering: Agent generates assumptions, user reviews/corrects
- [ ] Constitutional: Learnings accumulate in `.cub/SYSTEM-PLAN.md`
- [ ] Plans live in `/plans/{slug}/` with clear structure
- [ ] Slug collision handled with `_alt_[a-z]` suffix
- [ ] `cub plan` automatically moves spec from `researching/` to `planned/`
- [ ] `cub stage` parses `itemized-plan.md` and imports tasks via `TaskBackend.import_tasks()`
- [ ] `cub stage` automatically moves spec from `planned/` to `staged/`
- [ ] `cub run` automatically moves spec from `staged/` to `implementing/` on first task start
- [ ] Stage works with both BeadsBackend and JSONBackend
- [ ] `TaskBackend.import_tasks()` added to Protocol and implemented in both backends
- [ ] No bash dependencies for planning workflow
- [ ] Existing bash commands (`cub prep`, etc.) show deprecation warning pointing to new commands

---

## Future Considerations

- **Plan templates**: Pre-defined patterns for common project types
- **Plan diffing**: Compare two plans for the same spec
- **Collaborative planning**: Multiple reviewers approve stages
- **Plan export**: Generate external formats (Jira, Linear, GitHub Issues)
- **Plan history**: Track how plans evolved over iterations
