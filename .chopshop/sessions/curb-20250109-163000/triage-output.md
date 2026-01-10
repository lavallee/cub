# Triage Report: Curb 1.0

**Session:** curb-20250109-163000
**Date:** 2025-01-09
**Triage Depth:** Standard
**Status:** Approved

---

## Executive Summary

Curb 1.0 focuses on making the autonomous loop **reliable enough to trust**. This means: logs you can audit, clean git state after each task, cost controls before runaway spending, and a hook system for project-specific needs. Supporting 4 harnesses (Claude, Codex, Gemini, OpenCode) proves the abstraction is solid.

## Problem Statement

AI coding agents are powerful but risky to run unattended. Users need confidence that:
- They can see what happened (observability)
- The repo won't be left broken (reliability)
- Costs won't spiral (budget controls)
- They can customize behavior for their project (extensibility)

## Refined Vision

Curb 1.0 is the version you can run overnight without worrying. It logs what happened, respects your budget, leaves the repo clean, and lets you customize behavior without forking.

---

## Requirements

### P0 - Must Have

| ID | Requirement | Rationale |
|----|-------------|-----------|
| P0-1 | **Observability: Task logging** | Can't trust what you can't audit. Logs, metadata, token usage per task to disk. |
| P0-2 | **Reliability: Clean state enforcement** | Git committed after each task. Optional config: require tests pass. |
| P0-3 | **Token budgeting** | Critical for trust. Stop before spending more than allowed. Multiple modes: token count, dollar amount, session %. |
| P0-4 | **4 harnesses working** | Claude, Codex, Gemini, OpenCode. Proves the harness abstraction is solid. |
| P0-5 | **Global + project config** | Users need to set defaults (harness priority, budget, hooks) without flags every time. |

### P1 - Should Have

| ID | Requirement | Rationale |
|----|-------------|-----------|
| P1-1 | **Full lifecycle hooks** | pre-task, post-task, on-error, loop-end. Designed to grow into plugin architecture. |
| P1-2 | **Onboarding command** | Check dependencies, generate config, guide setup. Lowers barrier to entry. |
| P1-3 | **Better beads integration** | Leverage beads' built-in MCP support. Explore synergies. |

### P2 - Nice to Have

| ID | Requirement | Rationale |
|----|-------------|-----------|
| P2-1 | **Session continuation (--continue)** | Reuse context window if capacity remains. Investigate feasibility; ship if straightforward. |
| P2-2 | **Context window % threshold** | Stop if Claude Code session dips below X%. Nice cost control refinement. |

---

## Constraints

- **Language flexible**: Can rewrite parts in Go/Python if beneficial for reliability or performance
- **Backwards compatible where possible**: Existing curb users shouldn't have breaking changes without clear migration path

## Assumptions

- Gemini CLI and OpenCode CLI have similar enough interfaces to abstract into the harness layer
- Token usage is queryable from all 4 harnesses (or can be estimated)
- Hooks can be implemented without major architectural changes to the main loop
- The existing harness abstraction (lib/harness.sh) is a good foundation to build on

## Open Questions / Experiments

| Unknown | Experiment |
|---------|------------|
| Can we get token counts from all harnesses? | Spike: query each harness for usage data |
| Is session continuation reliable with Claude Code? | Test --continue, measure success rate over 20+ runs |
| Hook overhead in bash? | Prototype hooks, measure loop latency impact |
| Gemini/OpenCode CLI maturity? | Test both CLIs manually, assess feature parity |

## Out of Scope for 1.0

- Plugin marketplace / discovery
- Web UI for monitoring
- Multi-repo orchestration
- Windows support
- IDE integrations

## Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Harness APIs differ significantly | High | Medium | Abstract early, test all 4 in parallel during development |
| Token counting unavailable from some harnesses | Medium | Medium | Fall back to estimated counts from model pricing tables |
| Hook system adds loop complexity | Medium | Low | Start simple (shell scripts), prove value before expanding |
| Gemini/OpenCode CLIs are immature | Medium | Medium | Assess early, adjust scope if blockers found |

---

**Next Step:** Run `/chopshop/architect curb-20250109-163000` to proceed to technical design.
