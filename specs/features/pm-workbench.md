# Feature Spec: PM Workbench (Unknowns Ledger + Next Move)

## Summary

Build a **blank-slate PM interface** (CLI-first, UI later) that accepts *any* input (sentence, vision, pasted docs) and continuously suggests the **next most elucidating move**.

This is explicitly **not PRD-first**. The primary output is a ranked list of unknowns + a recommended next move that reduces the biggest unknown with the lowest cost.

## Goals

- **Works from messy input**: a sentence, a paragraph, or a pile of docs.
- **Always proposes a next move**: ask a question, run research, run audit, run spike, or promote.
- **Composable**: the system doesn’t force a linear workflow; it maintains state and lets the user jump.
- **Promote when ready**: when nothing blocks execution-ready tasks, generate a TaskBrief/tasks.
- **Co-located artifacts**: generated outputs live in-repo (or are importable) and link to each other.

## Non-goals (v1)

- Perfect prioritization. Start with simple heuristics + user overrides.
- A full GUI. V1 can be CLI + markdown artifacts.
- Automatic “betting table”/portfolio management.

## Concepts

### Unknown

An **Unknown** is a named gap preventing promotion to an execution-ready task/epic.

Types (small, practical):
- `clarity`: missing context, ambiguous scope, unclear desired change
- `evidence`: needs validation/research/measurement
- `decision`: multiple plausible paths; needs boundaries/tradeoffs
- `dependency`: blocked on access, people, sequencing, external systems

### Next Move

A **Next Move** is a single recommended action that resolves one unknown.

Move types:
- `question`: ask the user (or stakeholders) a clarifying question
- `research`: create a research brief + suggested queries; optionally run web research
- `audit`: run code search/analysis; produce a report
- `spike`: timeboxed technical experiment; produce learnings
- `promote`: generate TaskBrief/tasks now

## User experience (CLI-first)

### Primary interaction

1. User runs: `cub workbench` (or `cub next`) and starts typing/pasting.
2. Cub updates:
   - **Working set** (chunked inputs)
   - **Unknowns Ledger** (ranked)
   - **Next Move** (single recommendation)
3. User chooses: accept / edit / override.
4. Cub runs the move and writes a durable artifact.

### Example output (terminal)

- NEXT MOVE: Ask 2 clarifying questions (targets: clarity)
- WHY: Cannot write TaskBrief without guessing about X
- DONE WHEN: user answers Q1/Q2
- TIMEBOX: 2 minutes

Unknowns:
1) clarity: Which user journey is affected?
2) decision: Should we optimize latency or cost first?

## Data model (minimal)

Store state as markdown artifacts + frontmatter (consistent with captures).

### Workbench Session (proposal)

Location: `specs/workbench/sessions/<id>.md`

Frontmatter:
```yaml
id: wb-2026-01-17-001
created: 2026-01-17T13:00:00Z
status: active
inputs:
  - kind: capture
    ref: cap-123
  - kind: file
    path: docs/vision.md
unknowns:
  - id: unk-001
    type: clarity
    title: "What is the user-facing change?"
    score: 0.72
    rationale: "Without this, task scope is guessy"
  - id: unk-002
    type: decision
    title: "Choose approach A vs B"
    score: 0.55
next_move:
  kind: question
  target_unknown_id: unk-001
  prompt:
    - "Which user segment is impacted?"
    - "What does success look like?"
  timebox_minutes: 2
links: []
```

### Unknown scoring (v1 heuristic)

Score = weighted sum of:
- `blockingness`: does it prevent TaskBrief?
- `expected_value`: would resolving it unlock multiple downstream decisions?
- `cost`: lower cost → higher score
- `reversibility`: less reversible → prioritize uncertainty reduction

User can override ordering.

## Mapping to existing Cub primitives

- Inputs are created via:
  - `cub capture` (sentence/notes)
  - `cub import` (docs pile)
- Routing uses:
  - `cub investigate` categories (`quick|audit|research|design|spike|unclear`)
- Artifacts are written to:
  - `specs/investigations/*` (research/design/audit)
  - `specs/workbench/sessions/*` (session state)

## Promotion rule (minimal)

Promotion is allowed when:
- There is at least one candidate scope boundary
- Acceptance criteria can be written without guessing
- Verification approach exists (even if minimal)

If “nothing blocks promotion,” Next Move becomes `promote`.

## Implementation notes (later)

- V1 can be pure CLI: generate markdown artifacts and print next move.
- Add an option to run `research` moves using configured web search.
- Integrate with TaskService for `promote`.
