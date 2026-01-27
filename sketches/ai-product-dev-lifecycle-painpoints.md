# Cub as salve for AI product development challenges (lifecycle pain points map)

Draft captured from chat: 2026-01-26

This doc reframes Cub beyond “autonomous coding loop” and toward **end-to-end AI-assisted product development**: from feature deliberation → planning → implementation → verification/review → release → maintenance.

For each lifecycle stage:
- **Pain points when using LLMs/agents** (patterns we see across teams)
- **Cub today** (existing commands/features)
- **Cub planned / ideas** (from ROADMAP/specs)
- **Open gaps** (no clear solution yet)

---

## 0) Intake / signal collection (ideas, customer feedback, bug reports)

### Pain points
- Drowning in raw inputs: bug reports, support tickets, meeting notes, “random Slack messages”.
- Hard to preserve context: why something matters; links; reproduction steps; user impact.
- LLMs are good at summarizing, but you lose provenance and can’t trace back.

### Cub today
- `cub capture` / `cub captures ...` as an intake surface.
- `cub organize-captures` to normalize/clean capture metadata.
- Dashboard CAPTURES column aggregates captures.

### Planned / ideas
- Planned: **Capture System** (`specs/planned/capture.md`).
- Researching: capture workflow (`specs/researching/capture-workflow.md`).

### Gaps
- Native integrations with ticketing/feedback systems (GitHub Issues is a partial bridge via `cub run --gh-issue`; deeper “import + dedupe + cluster” is missing).
- First-class “bug report hydration”: standardizing repro steps, environment, expected/actual, severity, impact.

---

## 1) Deliberation / discovery (deciding what to build)

### Pain points
- LLMs can generate plausible strategies but don’t reliably surface trade-offs.
- Teams oscillate between analysis paralysis and shipping the wrong thing.
- Hard to externalize “unknowns ledger” and make progress on open questions.

### Cub today
- `cub spec` (AI-guided interview) to force articulation of goals, constraints, open questions.
- `cub investigate` (completed feature) as a research/audit tool (codebase + context gathering).
- Dashboard SPECS / PLANNED to visualize flow.

### Planned / ideas
- Researching: **PM workbench** (`specs/researching/pm-workbench.md`) + **AI-assisted PM shaping model**.
- Researching: **Toolsmith** + tools registry/marketplace to bring external research tools into Cub.

### Gaps
- Decision quality tooling: explicit “trade-off analyzer”, “risk scoring”, “readiness scoring” as first-class commands (currently in TOOLS-WISHLIST but not implemented).
- Better “argumentation record”: storing competing options + rationale in a structured way.

---

## 2) Shaping → plan quality (turning a concept into executable tasks)

### Pain points
- LLMs are strong at decomposition but often produce:
  - tasks that are too big/vague,
  - missing dependencies,
  - no verification criteria.
- Humans struggle to review giant plans.

### Cub today
- Prep/plan flow (historically: triage→architect→plan→bootstrap; currently: `cub plan orient/architect/itemize/run`, plus plan review features).
- `cub stage` to import plan → task backend.

### Planned / ideas
- Planned: **Implementation Review**, **Receipt-based gating**, **Verification integrations**.

### Gaps
- Automated “plan linting” (smoke tests for plans): missing AC, missing deps, inconsistent IDs, etc.
- A “lite planning” mode for casual users that still preserves quality.

---

## 3) Execution (writing code with agents)

### Pain points
- Context drift; agents forget constraints.
- Stagnation loops and wasted spend.
- Harness fragmentation: different CLIs, different capabilities.

### Cub today
- `cub run` loop: dependency ordering, budgets, sessions, structured logs, git integration.
- Guardrails system.
- Multi-harness support.

### Planned / ideas
- Planned: **Circuit breaker**, **Advanced error detection**, **Dual-condition exit**, **Fresh context mode**, **Re-anchoring**.
- Researching: harness abstraction (still a keystone dependency for many features).

### Gaps
- “Explain what you’re doing right now” snapshots for humans.
- Safer autonomous operation for less technical users (sandboxing defaults; strong rollback).

---

## 4) Verification / review (ensuring reliability)

### Pain points
- LLMs generate code that *looks* right; humans need confidence.
- Test gaps; flakiness; “it passes locally” problems.
- Review debt: too many PRs, too hard to assess.

### Cub today
- `cub review ...` with `--deep` (LLM-based) + deterministic checks.
- Ledger captures outcomes; dashboard surfaces NEEDS_REVIEW.

### Planned / ideas
- Planned: **Verification integrations**, **Implementation review**, **Receipt-based gating**.

### Gaps
- Repository-specific “Definition of Done” as a configurable contract.
- CI integration that produces machine-checkable receipts and blocks progression.

---

## 5) Release / rollout

### Pain points
- Release checklists are brittle; LLMs forget steps.
- Hard to connect shipped changes back to original intent.

### Cub today
- Workflow stages + ledger + changelog integration (dashboard COMPLETE/RELEASED).
- Git workflow integration, PR tooling.

### Planned / ideas
- Planned: codebase health audit; runs analysis.

### Gaps
- “Release assistant” that composes release notes from ledger + validates checklist.
- Monitoring/observability hooks post-release.

---

## 6) Maintenance (bugs, regression, tech debt)

### Pain points
- Bug backlog triage is exhausting; LLMs help summarize but not prioritize correctly.
- Regression hunting: reproducing + isolating changes is tedious.

### Cub today
- `cub audit` (local health checks), `cub investigate`.
- Punchlist processing (turn lists into actionable epics/tasks).

### Planned / ideas
- Planned: runs analysis; verification integrations.

### Gaps
- “Bug report ingestion at scale”: cluster similar issues, dedupe, infer likely root causes, propose minimal reproductions.
- Linking production incidents to the exact ledger entries and decision context.

---

## Cross-cutting: meta-pain points Cub can own

1) **Provenance + traceability**: every artifact should link to inputs, decisions, and code changes.
2) **Deterministic gating**: LLM output must be backed by receipts (tests, commands, files).
3) **Human attention routing**: the system should page the human only when it’s genuinely worth their time.
4) **Tooling portability**: avoid lock-in to a single harness; degrade gracefully.

---

## Candidate framing

> Cub is an operating system for AI-assisted product development: it turns messy inputs into structured work, runs agents with guardrails, and preserves provenance so teams can ship reliable software.
