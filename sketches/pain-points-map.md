# Cub pain points map (power users → casual users)

> Draft captured from chat (2026-01-26). This is a first-pass “pain point → Cub coverage” matrix based on Cub’s README framing + ROADMAP. It should be reconciled against the canonical pain-point list once we have it verbatim.

## Power-user pain points → how Cub tackles them

### 1) “Agents are either too hands-on or too hands-off”
- **Cub today:** `cub prep` pipeline (triage → architect → plan → bootstrap) to front-load clarity; `cub run` executes autonomously once tasks are well-formed.
- **Planned/ideas:** improved human-handoff UX (roadmap callout under workflow management).
- **Potential gap:** *fast* “good enough” mode for when you don’t want an interview/planning session.

### 2) “Vague instructions → agents run amok / do the wrong thing”
- **Cub today:** guardrails system + deterministic control layer (task selection/state transitions), plus structured tasks with acceptance criteria.
- **Planned/ideas:** **Receipt-based gating** (planned) to require explicit evidence before moving on.
- **Potential gap:** stronger definition + enforcement of “done” per repo (tests? screenshots? CLI output?)—implied by “Verification Integrations” but not fully solved end-to-end yet.

### 3) “Context drift / losing the thread mid-run”
- **Cub today:** sessions + artifact bundles per task; structured logging; plan review / interview modes.
- **Planned/ideas:** **Re-anchoring mechanism** (planned), **Fresh Context Mode** (planned).
- **Potential gap:** a quick, human-readable “what does the agent currently believe?” snapshot to sanity-check.

### 4) “Long runs waste time when stuck (stagnation / loops)”
- **Cub today:** iteration limits; failure handling modes (stop/move-on/retry/triage).
- **Planned/ideas:** **Circuit breaker / stagnation detection** (planned), **Dual-condition exit** (planned), **Advanced error detection** (planned).
- **Potential gap:** good default heuristics for “stuck” that work across harnesses (and are explainable).

### 5) “Routing the right model/tool to the right task is tedious”
- **Cub today:** per-task model selection (labels); multi-harness flexibility.
- **Planned/ideas:** harness abstraction is a critical dependency; **Multi-model review** (planned, but blocked on harness work).
- **Potential gap:** auto-routing recommendations (“this looks like haiku/sonnet/opus”) with a simple override.

### 6) “Hard to observe what’s happening across multiple agent sessions”
- **Cub today:** dashboard (kanban across captures/specs/planned/ready/in-progress/review/complete/released); structured JSONL logs; streaming mode.
- **Planned/ideas:** **Runs analysis** (planned).
- **Potential gap:** “manager view” summaries: what changed since last check-in, what’s blocked, what needs human review now (without reading logs).

### 7) “Git gets messy (branches, commits, dirty state)”
- **Cub today:** git workflow integration (auto-branching, commit per task, clean state enforcement).
- **Planned/ideas:** could be extended via verification + review gates.
- **Potential gap:** opinionated PR assembly / stacking strategy, plus smoother integration with GitHub/GitLab review flows.

### 8) “Budget anxiety (token/cost runaway)”
- **Cub today:** budget management with limits/warnings; predictable stop conditions; dashboard can show cost (configurable).
- **Planned/ideas:** runs analysis could help attribute cost to value.
- **Potential gap:** proactive budgeting (“this epic will likely cost $X; want to proceed?”) + smarter mid-run cost/benefit decisions.

### 9) “Capturing ideas is scattered; turning notes into work is friction”
- **Cub today:** captures exist conceptually in the workflow + dashboard aggregation; “Investigate” command shipped.
- **Planned/ideas:** **Capture System** (planned, medium); capture workflow spec(s) researching.
- **Potential gap:** dead-simple capture intake (1 command, from anywhere) + effortless promotion: capture → spec → plan → tasks.

## Explicit gaps / candidates to name

- **Verification as a first-class gate** across harnesses (planned: verification integrations; still a gap in practice).
- **Stagnation detection + “stuck” diagnosis** defaults (planned circuit breaker + advanced error detection).
- **Human handoff UX** that’s minimal-friction but reliable.
- **Harness abstraction** as the keystone for consistent behavior across Claude/Codex/Gemini/OpenCode.

## Pain points for more casual / developer-adjacent users

Casual users often hit friction *before* they benefit from multi-agent orchestration:

1) **“I don’t know what to ask for / how to describe the work”**
   - Need: guided prompts, examples, templates, “choose a goal” flows.

2) **“Setup is intimidating (CLI, env, API keys, harness choice)”**
   - Need: frictionless onboarding; fewer concepts exposed up front; a “single default harness” happy path.

3) **“I can’t evaluate code quality / I don’t trust what it produced”**
   - Need: opinionated verification + explainability + safe defaults.

4) **“I don’t have a mental model for tasks/epics/dependencies”**
   - Need: lightweight mode that doesn’t require PM sophistication.

5) **“I just want small wins (rename thing, fix bug, add a button)”**
   - Need: a “one task” workflow that can skip the full prep pipeline.

6) **“Fear of breaking my repo / messing up git”**
   - Need: stronger safety rails, rollback, dry-run previews, and “nothing touches main.”
