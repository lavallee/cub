# Cub — V1 Scope (draft)

V1 is optimized to deliver a single repeatable outcome:
> **One confident change → PR-ready**

It targets solo builders already using AI coding harnesses, and it is explicitly designed to reduce **LLM thrash** and review anxiety.

---

## V1 principles
- **Progress over perfection:** size-independent, but must feel *solid*.
- **Boundedness:** prevent runaway changes and rework loops.
- **Traceability by default:** intent and decisions stay attached to the change.
- **Coexistence:** works *around* existing harness workflows.

---

## Must-have capabilities (V1)

> Note: PR creation is handled by a separate `cub pr` command (often run at epic/plan level). V1 scope assumes `cub pr` **creates a GitHub PR by default**.

### 1) Intent → Plan → Tasks (lightweight)
- A minimal structured capture for:
  - Goal / user-visible outcome
  - Constraints (what must not change)
  - Acceptance checks
- Convert to a small plan and 1–N tasks.
- Explicitly allow “skip planning” for tiny changes, but still produce a stub intent artifact.

### 2) Anti-thrash guardrails
- Enforce a **bounded change envelope** (default):
  - Declare allowed target area up front (directories/files/modules)
  - Warn/block when touching new areas unless explicitly expanded
- **Soft-disjoint task envelopes within an epic**:
  - Prefer task envelopes that don’t overlap
  - If a task touches another task’s envelope: warn + require explicit justification (don’t hard-block)
  - Provide a first-class escape hatch: an **INTEGRATION** task
- **Epic catch-all via INTEGRATION task (optional)**:
  - Each epic *may* include a dedicated INTEGRATION task whose envelope is the epic “gap filler” area
  - Cub should suggest creating it when it detects cross-envelope touching or other seam work
  - Use it for wiring, seam fixes, small refactors needed to connect task outputs
- Detect and surface “redo/undo” patterns:
  - Large churn in the same files across attempts
  - Repeated changes to tests without corresponding behavior changes
- Budgeting:
  - Wall-time and/or token budget per run
  - Stop + summarize partial progress at budget hit

### 3) Confidence report (the “end of process” wedge)
Generate a PR-ready bundle:
- What changed (high-level summary)
- Why it changed (intent link)
- What was verified (tests/lint/build status)
- Risk surface area (what modules/APIs likely affected)
- Known gaps / follow-ups

### 4) Clean handoff to PR
- Provide a consistent path to:
  - Branch naming conventions
  - Commit message conventions
  - A PR description template that includes the confidence report

---

## Nice-to-have (if cheap)
- Model routing presets (cheap model for planning, stronger for implementation).
- “Review buddy” mode: a second-pass critique of the diff.
- Local sandbox runner (Docker/VM) if it’s already close.

---

## Explicitly out of scope (V1)
- Full dashboard UI (CLI-first is fine).
- Team workflow features (assignments, sprint planning, permissions).
- Long-term self-learning that mutates prompts automatically.
- Deep plugin marketplace—just enough hooks to not paint us into a corner.

---

## Open questions (to resolve early)
1. What is the minimal artifact format for intent/plan/tasks?
2. What are the 2–3 “confidence signals” that matter most to Marc’s target user?
3. What are the hard budget defaults (time/tokens) that prevent surprises without being annoying?
4. What’s the exact PR automation behavior (default: **create GitHub PR** via `gh`), and what are the fallbacks if `gh` isn’t configured?
