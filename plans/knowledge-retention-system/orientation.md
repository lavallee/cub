# Orient Report: Knowledge Retention System

**Date:** 2026-01-22
**Orient Depth:** Standard
**Status:** Approved

---

## Executive Summary

Cub needs a post-task memory system that bridges the gap between in-progress work (beads) and permanent record (git commits). This system will capture task intent, execution trace, and outcomes—serving both human auditing needs (cost visibility, drift detection) and agent context recovery.

## Problem Statement

When tasks transition from "in progress" to "completed," critical information is lost:
- **What was the original intent?** (beads forgets to keep context small)
- **What approach did the agent take?** (not recorded)
- **How much did it cost?** (tokens extracted but not persisted)
- **What lessons were learned?** (scattered in progress.txt)

This affects:
- **Humans** who need audit trails, cost visibility, and spec drift detection
- **Agents** who waste tokens re-exploring codebases and repeat past mistakes

## Refined Vision

Build a three-layer memory architecture for cub:

1. **Run Logs (Enhanced)** - Detailed audit trail with token/cost persistence
2. **Completed Work Ledger (New)** - Permanent record of what was built, why, and outcomes
3. **Codebase Context (New)** - Generated orientation docs (llms.txt, codebase-map.md)

Plus tooling for:
- **Drift detection** using LLM-assisted semantic comparison
- **Session surveying** to extract insights from interactive work
- **Git hooks** to capture direct harness usage

## Requirements

### P0 - Must Have

- **Token/cost persistence** - Store TokenUsage in task.json, aggregate in run.json, display in cub status
  - *Rationale: Enables all downstream cost analysis; currently extracted but not saved*

- **Ledger writer** - Create `.cub/ledger/by-task/{id}.md` entries on task close
  - *Rationale: The core missing piece between beads (in-progress) and git (permanent record)*

- **Ledger index** - Maintain `.cub/ledger/index.jsonl` for fast queries
  - *Rationale: Enables `cub ledger stats`, `cub ledger search` without parsing all markdown*

- **LLM-assisted drift detection** - Compare specs to ledger entries semantically
  - *Rationale: Primary success criteria; text diff is insufficient for meaningful comparison*

- **Ledger CLI** - `cub ledger show`, `cub ledger stats`, `cub ledger search` with --json support
  - *Rationale: Query interface for both humans and scripts*

### P1 - Should Have

- **Context generation** - Generate `llms.txt` and `.cub/codebase-map.md` for agent orientation
  - *Rationale: Reduces tokens spent on codebase exploration*

- **Git post-commit hook** - Capture commits to ledger even when agents bypass `cub run`
  - *Rationale: Safety net for direct harness usage; installed by default*

- **Epic summaries** - Aggregate task entries into `.cub/ledger/by-epic/{epic-id}.md`
  - *Rationale: Enables cost tracking and drift detection at epic level*

- **Harness log capture** - Save raw harness output to `.cub/runs/{session}/tasks/{id}/harness.log`
  - *Rationale: Audit trail for debugging; enables approach extraction*

### P2 - Nice to Have

- **Session surveying** - `cub survey` to extract insights from `.claude/` directories
  - *Rationale: Captures design rationale from interactive work; on-demand only*

- **Guardrails integration** - Auto-suggest guardrails from repeated ledger lessons
  - *Rationale: Closes the learning loop; depends on pattern detection*

- **Constitutional principles** - Promote high-confidence lessons to `.cub/constitution.md`
  - *Rationale: Long-term institutional memory; requires human curation*

- **External observability export** - OpenTelemetry GenAI format for Langfuse/Grafana
  - *Rationale: Interoperability; deferred until standards mature*

## Constraints

- **File-based storage preferred** - Per Letta research, simple filesystem approaches outperform complex systems (74% on LoCoMo benchmark)
- **Python preferred** - Must integrate with existing codebase; new languages acceptable if necessary
- **Breaking changes acceptable** - Does not need to be backward compatible with existing `.cub/` structure
- **Open to new dependencies** - If they are logical drop-ins, not opposed; but default to rolling our own

## Assumptions

- Specs exist and are meaningful - Drift detection assumes specs are written and capture intent
- Harness logs contain extractable information - Approach/decisions can be summarized from logs
- LLM-assisted comparison is cost-effective - Drift detection cost << value of catching drift
- Task IDs are stable - Ledger entries keyed by task ID; IDs don't change after creation

## Open Questions / Experiments

| Unknown | Experiment |
|---------|------------|
| Drift detection quality | Build prototype with 5 real spec/ledger pairs and evaluate accuracy |
| Approach extraction accuracy | Test LLM summarization of 10 harness logs for quality |
| Codebase map usefulness | Measure token savings with vs. without context files |
| Hook adoption friction | Monitor orphan commit rate after deployment |

## Out of Scope

- **Cross-project knowledge base** - Focus on single-project first
- **Real-time dashboards** - CLI and JSON export sufficient for v1
- **External database storage** - Stay file-based per design decision
- **Automatic spec updates** - Drift reports inform humans; don't auto-modify specs
- **OAuth/authentication** - No multi-user or access control requirements

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Drift detection produces false positives/negatives | Medium | Require human review; tune prompts; position as advisory not blocking |
| Ledger entries become stale/unmaintained | Medium | Auto-generate from structured data; minimize manual fields |
| Token cost of drift detection exceeds value | Low | Use fast models (Haiku); cache results; run on-demand not every commit |
| Git hooks conflict with existing workflows | Low | Make hooks safe (no-op on error); provide disable flag |
| Agents ignore AGENTS.md instructions | Medium | Git hooks as safety net; validate in CI/CD |

## MVP Definition

**All three phases**, implemented iteratively:

**Phase 1: Token Persistence** (~1 week)
- Persist TokenUsage to task.json
- Aggregate totals in run.json
- Display in `cub status`

**Phase 2: Ledger Writer** (~2 weeks)
- Create ledger directory structure
- Generate entries on task close
- Build index.jsonl
- Implement `cub ledger` CLI commands

**Phase 3: Context + Drift** (~2 weeks)
- Generate llms.txt from CLAUDE.md + activity
- Generate codebase-map.md
- Implement LLM-assisted drift detection
- Install git hooks on `cub init`

---

## Appendix: Key Design Decisions

### D1: Ledger storage format
**Decision:** Markdown files + JSONL index

Per-task markdown files (`.cub/ledger/by-task/{id}.md`) are human-readable and diff-friendly. JSONL index (`index.jsonl`) enables fast queries without parsing markdown.

### D2: Drift detection approach
**Decision:** LLM-assisted semantic comparison

Specs and implementations express the same intent in different ways. Text diff is insufficient. An LLM can understand "24h token expiry (spec said 1h)" is a documented divergence, not a failure.

### D3: Git hook strategy
**Decision:** Install by default, safe failure

Post-commit hook creates minimal ledger entries for commits without Task-Id trailers. Hook is no-op if cub not initialized. User can disable with `cub init --no-hooks`.

### D4: Session surveying frequency
**Decision:** On-demand only

`cub survey` extracts insights when user requests. Avoids overhead and gives user control over what gets promoted to llms.txt or guardrails.

---

**Next Step:** Run `cub plan architect` to design the technical architecture.
