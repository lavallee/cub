# Triage Report: Curb 1.0

**Session:** curb-20260110-143000
**Date:** 2026-01-10
**Triage Depth:** Standard
**Status:** Approved

---

## Executive Summary

Curb 1.0 is an autonomous AI coding agent harness that reliably processes structured dev tasks in batches, selecting appropriate harnesses and models for cost/speed optimization. This release focuses on observability (artifact bundles), UX polish (subcommand CLI), and production safety (guardrails, safe defaults).

## Problem Statement

Developers and small teams need to batch-process well-structured coding tasks through AI agents reliably, with flexibility in harness/model selection to optimize for speed, cost, and capability. Current workflow is manual agent invocation without structured output or batch orchestration.

## Refined Vision

Curb 1.0 delivers a polished, observable autonomous loop with:
- Structured artifact bundles for every task (diffs, plans, logs)
- Consistent subcommand CLI (`curb run`, `curb status`, etc.)
- Branch-per-run, commit-per-task git workflow
- Session identity for concurrent instance disambiguation
- Iteration and budget guardrails for autonomous safety
- Safe defaults (no auto-push, secret redaction)

## Requirements

### P0 - Must Have

- **Artifact bundle system**: Per-task output in `runs/<run-id>/tasks/<task-id>/` containing task.json, plan.md, changes.patch, commands.jsonl, summary.md - enables observability and post-hoc analysis
- **Subcommand CLI model**: Migrate to `curb init`, `curb run`, `curb status`, `curb version` for consistency and discoverability
- **Git workflow**: Branch per run, commit per task - produces reviewable changes as primary output
- **Session names**: Random animal default or `--name` flag - used for beads assignee and log disambiguation
- **Iteration guardrails**: Max iterations per task and per run - prevents runaway loops (complements existing token budget)
- **Safe defaults**: No auto-push (require explicit `--push`), basic secret redaction in logs/output

### P1 - Should Have

- **Failure handling modes**: Configurable behavior on task failure - stop, move-on (mark failed), retry, triage (LLM-assessed)
- **Acceptance criteria verification**: If task description contains acceptance criteria, verify them before marking done
- **`curb explain <task>` command**: Show why a task is blocked, skipped, or failed
- **`curb artifacts <task>` command**: Quick navigation to task's artifact folder
- **Default hooks for branch/PR**: Cut branch on epic start, request PR on epic end
- **Timestamps in logs/streams**: Add timestamps to log entries and streamed output for debugging

### P2 - Nice to Have

- **Debug mode: full command line**: Show exact flags passed to harnesses when `--debug` is enabled
- **LLM triage for failures**: Use an LLM to assess error type (transient, capability) and decide retry strategy or model upgrade

## Constraints

- None specified - flexible on timeline, budget, and tech stack

## Assumptions

- The existing harness abstraction (claude/codex/gemini/opencode) is stable enough to build on
- prd.json remains the simpler default backend; beads integration for power users
- Backwards compatibility with existing configs is desirable but not blocking if migration path is documented
- "Random animal" session names are a deliberate UX choice (friendly, memorable, easy to reference)
- Users are primarily solo developers and small teams

## Open Questions / Experiments

- **Optimal default max iterations per task** → Experiment: Start with 3, gather feedback from real usage
- **Secret patterns to redact** → Experiment: Start with common patterns (API_KEY, TOKEN, SECRET, password-like strings), expand based on false negatives
- **LLM triage cost/benefit** → Experiment: Implement as opt-in P2, measure if it actually improves task success rates vs. simple retry

## Out of Scope

- Max wall-clock time guardrail (iterations + budget sufficient for 1.0)
- Command allowlist/denylist (rely on harness sandboxing)
- Patch-only git mode (can add later if requested)
- Branch-per-task git mode (branch-per-run is sufficient)
- Plan-only mode that never edits files (can add later)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Subcommand refactor breaks existing scripts/workflows | Medium | Document migration path in UPGRADING.md, consider temporary aliases for deprecated flags |
| Artifact bundle I/O overhead slows runs | Low | Lazy writes, only persist artifacts on task completion, not during |
| LLM triage adds cost and latency to failure handling | Low | Make triage opt-in, default to simpler retry or move-on |
| Session name collisions with concurrent instances | Low | Include timestamp component in run-id, warn if collision detected |
| Secret redaction false positives/negatives | Low | Start conservative, make patterns configurable |

## Success Criteria

1. **Self-use**: The author can reliably use curb for their own development workflows
2. **Wider adoption**: Measured by downloads/installs and community contributions (harnesses, hooks, integrations)

---

**Next Step:** Run `chopshop:architect curb-20260110-143000` to proceed to technical design.
