# Cub — V1 Product Spec (draft)

## Product thesis (summary)
Cub is for **solo builders** who already use AI coding harnesses but feel overwhelmed keeping agents fed and burned by **LLM thrash** (redo/undo loops, drift, regressions). Cub adds structure to the **beginning** (clarify intent → plan → tasks) and the **end** (verification + packaging) so the builder can make **one confident change** and get to a **GitHub PR** reliably.

---

## Primary user + triggers

### Target user
- Solo builder shipping real software.
- Uses one or more harnesses (Codex/Claude Code/Cursor/Aider/etc.).
- Not necessarily a CLI power user, but can operate inside a repo.

### Day-0 trigger
- Overwhelmed by product complexity and the cognitive load of keeping agents supplied with coherent, bounded work.

### Never-again pitfall (north star)
- **LLM thrash**: the agent repeatedly redoes/undoes work over time and leaves adjacent components broken, reducing confidence and making progress feel illusory.

---

## V1 outcome

### The V1 win
In a short session, the user can make **one solid piece of progress** (size-independent) that feels safe to move forward with, culminating in a **GitHub PR**.

### What “confidence” means (minimum signals)
V1 should produce a PR-ready bundle that includes:
- A clear statement of **intent** (what/why)
- A **bounded plan** (what will change / what won’t)
- A reviewable **diff summary**
- **Verification results** (tests/lint/build) + what was/wasn’t run
- A short **risk surface** note (what areas likely affected)

---

## Workflow wedge (beginning + end)

### Beginning: intent → plan → tasks
- Lightweight capture of:
  - Goal / outcome
  - Constraints / non-goals
  - Acceptance criteria
  - Files/areas likely involved
- Convert to a small plan and task set.
- Allow skipping heavy planning for tiny changes, but still produce minimal intent metadata.

### End: PR packaging
- PR creation happens via a separate command: **`cub pr`**.
- V1 default: **`cub pr` creates a GitHub PR** (via `gh` under the hood), typically at epic or plan level.

---

## Anti-thrash guardrails (the core differentiator)

### Bounded change envelope (default)
- Work is performed within an explicit envelope:
  - allowed paths/files/modules
  - explicit off-limits paths (optional)
- Touching outside envelope:
  - warn/block depending on mode
  - require explicit expansion/justification to proceed

### Two-layer envelopes (non-overlapping intent)
- **Epic envelope**: the shared area of the codebase for the epic.
- **Task envelope**: intended to be disjoint per task within an epic (soft disjointness).

### Soft-disjoint task envelopes
- Default preference: tasks in the same epic should not overlap in touched areas.
- If overlap occurs:
  - warn + require explicit justification
  - do not hard-block by default

### Catch-all integration via optional INTEGRATION task
- Each epic *may* include an **INTEGRATION** task.
- Purpose: “gap filler” / seam work:
  - wiring pieces together
  - small refactors needed to connect task outputs
  - integration fixes discovered late
- Cub should suggest creating an INTEGRATION task when it detects cross-envelope touching.

---

## Out of scope for V1
- Full dashboard UI as the primary interface (CLI-first OK).
- Team coordination workflow (assignments, sprints).
- Automatic self-learning that mutates core prompts without review.
- A plugin marketplace (keep hooks minimal but extensible).

---

## Open questions (to answer soon)
1. What exact artifact format is canonical for intent/plan/tasks (and where does it live)?
2. What are the default enforcement modes (warn vs block) for envelope violations?
3. What should `cub pr` do when `gh` isn’t configured?
4. What are the default “confidence report” sections in the PR body template?
