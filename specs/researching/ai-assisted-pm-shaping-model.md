---
status: draft
priority: medium
complexity: high
dependencies:
  - capture.md
  - workflow-management.md
  - tools-registry.md
blocks:
  - pm-workbench.md
  - vision-to-tasks-pipeline.md
created: 2026-01-13
updated: 2026-01-19
readiness:
  score: 5
  blockers:
    - Needs operationalization into specific features
    - Mode transitions not defined (triggers, conditions)
    - Storage format for "idea graph" not specified
    - Integration with existing Cub commands unclear
  questions:
    - How do modes map to existing Cub commands (capture, investigate, triage)?
    - Should idea graph be files + links, or a database?
    - How to visualize idea graph for human review?
    - What's the minimal viable set of node types to start?
    - How much automation vs manual mode switching?
  decisions_needed:
    - Choose storage format for idea graph (files vs DB)
    - Define mode transition triggers and automation level
    - Decide which modes to implement first (MVP scope)
    - Pick visualization approach (CLI tree, web UI, mermaid diagrams)
  tools_needed:
    - Idea graph visualizer (show relationships between captures/frames/solutions)
    - Mode suggester (recommend which mode to enter based on current state)
    - Assumption extractor (identify implicit assumptions in specs/ideas)
    - Decision tracker (link decisions to outcomes/evidence)
    - Integration mapper (identify where this connects to existing Cub features)
---

# AI-Assisted PM Shaping: Stages, Representation, and "What Next?" Questions

## Why this doc exists

Cub already has a **capture → investigate → process** workflow for moving raw thoughts toward actionable work. This doc proposes a more general, composable **vision → pre-task → task** model that matches the messy reality of creative product work, and identifies the *smallest* set of questions that helps a PM (or agent) decide what to do next.

The goal is **not** to create a rigid waterfall or a "loop until something pops out." It's to create:

- A small set of **modes** (stages) that can be entered/exited in any order.
- A flexible **representation** for pre-task work (an "idea graph," not a single canonical doc).
- Minimal **routing questions** ("what's blocking promotion?") that reliably select the next tool/template.

## Background anchors (terminology with gravity)

Some terms are overloaded ("discovery," "requirements," "PRD"). These anchors have clearer semantics and existing mindshare:

- **Capture** / **Investigate** / **Process**: already in Cub's capture workflow.
- **Outcome → Opportunity → Solution → Assumption test**: Opportunity Solution Tree framing (Teresa Torres).
- **Shape / Bet (commit)**: Shape Up's framing for "make it buildable, then decide."
- **Agentic spectrum**: design dimension for how autonomous a step should be (proactive, plans, uses live data, takes action, self-feedback loop).

## The model: modes with entry/exit conditions (not steps)

Think of these as **modes** the work can be in, each producing a different artifact. Items can bounce between modes.

1. **Capture**
   - Output: raw signal.
   - Exit condition: it's not going to be lost; minimal tag/title.

2. **Frame** (turn signal into a shaped question)
   - Output: a "frame" that states: what are we trying to improve, for whom, and what constraints apply.
   - Exit condition: we can ask "is this true?" / "is this worth it?" precisely.

3. **Map** (keep multiple paths alive)
   - Output: a small graph of: outcomes → opportunities → candidate solutions → assumptions/tests.
   - Exit condition: at least 2 plausible paths and the key assumptions are named.

4. **Test** (reduce uncertainty cheaply)
   - Output: evidence (notes, metrics, prototype feedback, spike results).
   - Exit condition: uncertainty reduced enough to choose or to stop.

5. **Shape** (make it buildable without over-specifying)
   - Output: "rough / solved / bounded" pitch-style artifact: boundaries, appetite, risks/rabbit holes, no-gos.
   - Exit condition: an implementer can proceed without inventing scope.

6. **Commit** (promotion moment)
   - Output: decision: commit/hold/drop + rationale.
   - Exit condition: we can generate a task brief without guessing.

7. **Execute**
   - Output: tasks, code, verification artifacts.

8. **Harvest**
   - Output: new captures, updated frame/map, archived decision.

## Representation: "Idea Graph" objects

To keep this composable, store pre-task work as small typed markdown artifacts + links.

### Node types

- `Capture`: raw note (already exists)
- `Frame`: clarified question + constraints
- `Outcome`: desired business outcome
- `Opportunity`: customer need/pain/desire
- `Solution`: candidate approach
- `Assumption`: what must be true
- `Test`: how we'll learn
- `Evidence`: what we learned
- `Decision`: commit/hold/drop + why
- `TaskBrief`: execution-ready plan
- `Artifact`: research/design/audit report (Cub already generates these under `specs/investigations/`)

### Edge types (links)

- `refines` (Capture → Frame)
- `supports` (Evidence → Decision, Evidence → Assumption)
- `decomposes_into` (Outcome → Opportunity → Solution)
- `tests` (Test → Assumption)
- `promotes_to` (Decision/Frame → TaskBrief)
- `derived_tasks` (TaskBrief → tasks)

### Minimal link schema (proposal)

In any artifact's frontmatter:

```yaml
links:
  - rel: refines
    to: cap-abc123
  - rel: supports
    to: dec-xyz789
```

This is intentionally simple: it can later expand into a richer graph without breaking old data.

## The core routing question: "What's blocking promotion?"

Your proposed phrasing is close to the minimal useful thing:

> **What, if anything, prevents this from becoming an execution-ready task/epic right now?**

The key is that the answer should be forced into a small set of **blocker categories** that map to templates/tools.

### Blocker categories (small, practical)

1. **Nothing** → promote directly (quick fix / straightforward change)
2. **Clarity** (unclear/missing context) → ask clarifying questions (Frame)
3. **Evidence** (need validation/research) → create Test plan or Research brief (Test)
4. **Design** (need to choose among approaches / define boundaries) → Shape artifact (Shape)
5. **Scope/Appetite** (uncertain how big we want to make this) → explicit appetite + cutline (Shape)
6. **Dependencies** (blocked by other work/access/permissions) → dependency capture + sequencing (Map/Commit)

This works for both humans and agents because it's grounded in "blockers to promotion," not in overloaded PM jargon.

## The smallest set of questions to keep going

The goal is to be *minimal*, but still decisive.

### Question 1 (routing)

> **Can we write a TaskBrief that an implementer could execute without guessing?**

- If **yes** → create `TaskBrief` (or a task/epic) now.
- If **no** → answer Question 2.

### Question 2 (classification)

> **What's missing: clarity, evidence, or a decision?**

- **Clarity missing** → generate 3-7 clarifying questions; output a `Frame`.
- **Evidence missing** → propose cheapest tests + expected signals; output `Test`/`ResearchBrief`.
- **Decision missing** → propose 2-4 options with tradeoffs + boundaries; output a `Shape`.

### Optional Question 3 (guardrail)

> **What is the smallest next move that reduces uncertainty or produces a commitment?**

This prevents "endless elaboration." The answer must be one of:

- "Ask X" (clarify)
- "Check Y" (test)
- "Choose between A/B" (decide)
- "Cut scope to fit appetite Z" (shape)
- "Promote now" (execute)

## Examples

### Example A: simple bug fix

Capture: "CLI crashes when `--json` and `--verbose` used together."

- Q1: TaskBrief without guessing? **Yes**.
- Blocker: **Nothing**.
- Action: promote directly to task (quick).

### Example B: vision-y idea

Capture: "We need a better vision → task flow for PM work with AI."

- Q1: TaskBrief without guessing? **No**.
- Q2: What's missing? **Decision** (model + representation) and **evidence** (what best practices are emerging).
- Action: create a `Shape` doc (boundaries/risks) + a short `ResearchBrief`.

## How this maps onto current Cub capture workflow

Cub's `investigate` categories are a strong starting point:

- `quick` ↔ "nothing blocks promotion"
- `research` ↔ "evidence missing"
- `design` ↔ "decision/boundaries missing"
- `spike` ↔ "technical evidence missing, timeboxed"
- `audit` ↔ "need to search/measure before deciding"
- `unclear` ↔ "clarity missing"

The model in this doc is a superset: it describes *why* those categories exist and gives a consistent "what next?" question that routes into them.

## Near-term feature ideas (smallest first)

1. Add a capture field `blocker: none|clarity|evidence|decision|dependencies`.
2. Add `links` in frontmatter for generated artifacts.
3. Add a `Frame` artifact generator (even if stored under `specs/investigations/`).
4. Add a `promote` step that requires answering the routing questions (human or agent).

## UX: a blank-slate "PM Workbench" (no PRD-first)

A PRD is an overloaded artifact that mixes:
- "constitutional" beliefs (principles, strategy, product intent)
- situational context (constraints, target users, current state)
- execution details (acceptance criteria, tasks, edge cases)

Those pieces age differently. Treating "PRD" as the center of gravity makes the UI feel like a form you must fill out, and it nudges the system toward document production instead of forward progress.

Instead, imagine a blank slate UI where the PM starts typing anything: a sentence, a vision, pasted docs, raw notes. The system continuously routes the input into the **next most elucidating move**.

### Core UI primitives

- **Canvas (freeform input):** a single place to type/paste.
- **Working set (inputs):** the system chunks and labels sources (notes, links, docs, transcripts).
- **Unknowns ledger:** a ranked list of "biggest unknowns" (each tagged as clarity/evidence/decision/dependency).
- **Next move card:** one recommended action the system believes creates the most forward progress.
- **Artifacts drawer:** frames, maps, tests, evidence, decisions, task briefs.
- **Constitution panel:** durable principles/constraints that should apply to many downstream tasks.

### The "Next move" selection

The system proposes exactly one move (or at most 2 alternatives) and explains why:

- **Proposed move type:** ask a question, run a research task, do an audit search, run a spike, or promote to task.
- **Target unknown:** which unknown it resolves.
- **Expected signal:** what will count as "resolved enough."
- **Cost/timebox:** how much effort/time this move should consume.
- **Reversibility:** how costly it is to be wrong.

### Minimal user loop

1. PM enters anything (sentence/vision/docs).
2. System extracts/updates unknowns and proposes a next move.
3. PM accepts, edits, or overrides.
4. System runs the move (agentic where safe), produces an artifact, and updates the unknowns.
5. When "blocker=none", system offers **Promote** (generate TaskBrief/tasks).

### What makes this feel flexible

- The user never chooses "make a PRD" up front.
- The system does not require linear progression; it just keeps a ledger of unknowns and suggests the highest-leverage next step.
- Durable "constitution" stays separate from per-initiative specs so it doesn't rot as quickly.

### Mapping to Cub

- Canvas input → `cub capture` (plus `import` for docs piles)
- Next move card → `cub investigate` + suggested processor
- Unknowns ledger → capture fields + generated questions
- Artifacts drawer → `specs/investigations/*` + linked tasks

See also:
- `specs/researching/pm-workbench.md` (concrete feature spec)
- `specs/notes/repo-as-workbench.md` (repo structure proposal)
