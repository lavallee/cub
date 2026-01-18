---
title: Roadmap
description: Cub's development roadmap, planned features, and how to propose new ideas.
---

# Roadmap

This page outlines Cub's development direction, from features currently in progress to ideas under research.

!!! info "Versioning"
    Features use stable IDs (e.g., `[CB]` for Circuit Breaker). Version numbers are assigned at release time, not pre-planned.

---

## Completed Features

Recent releases that are now available:

| Version | Feature | ID | Description |
|---------|---------|-----|-------------|
| v0.23 | Live Dashboard | [LD] | Real-time monitoring with `cub monitor` |
| v0.20 | Guardrails System | [GS] | Institutional memory and error patterns |
| v0.19 | Git Workflow Integration | [GWI] | Branch-epic bindings, checkpoints, PR management |
| v0.18 | Onboarding & Organization | [OPO] | Improved `cub init` and project structure |
| v0.17 | PRD Import | [PRD] | Document conversion and task import |
| v0.16 | Interview Mode | [IM] | Deep-dive task specification with `cub interview` |
| v0.15 | Plan Review | [PR] | Review generated plans before execution |
| v0.14 | Vision-to-Tasks Pipeline | [VTP] | The `cub prep` workflow |

---

## Active Development

Features currently being worked on:

| Feature | ID | Status |
|---------|-----|--------|
| Language Migration (Go + Python) | [LM] | Python CLI complete, bash delegation working |

The language migration is modernizing Cub's internals:

- **Python CLI** - Typer-based CLI with Pydantic models (complete)
- **Bash delegation** - Legacy commands delegated to bash (complete)
- **Go performance layer** - Planned for task operations and streaming

---

## Next Up

Prioritized features ready to start. Order reflects current thinking but can shift based on community feedback.

### [CB] Circuit Breaker / Stagnation Detection

**Complexity:** Medium | **Status:** Ready

Detect when the loop is stuck without making progress:

- Track meaningful changes per iteration (file diffs, task completions)
- Configurable threshold (e.g., 3 loops without progress)
- Actions: pause, alert, escalate, or auto-abort
- Stale task recovery: auto-reopen tasks stuck `in_progress` beyond timeout

```bash
# Configuration
cub run --stagnation-threshold 3 --stagnation-action pause
```

---

### [RA] Re-anchoring Mechanism

**Complexity:** Low | **Status:** Ready

Prevent task drift by re-reading context before each task:

- Reload PROMPT.md, AGENT.md, and current task spec before each iteration
- Include git status summary in task context
- Configurable anchoring sources

---

### [CHA] Codebase Health Audit

**Complexity:** Medium | **Status:** Ready

Systematic analysis to maintain codebase quality:

- **Dead Code Detection** - Unused functions, variables, orphan files
- **Documentation Freshness** - README validation, docstring coverage
- **Test Coverage Analysis** - Per-file coverage, test-code alignment
- **Consistency Analysis** - Naming conventions, pattern consistency

```bash
cub audit
cub audit --fix
cub audit --ci
```

---

### [AED] Advanced Error Detection

**Complexity:** Low | **Status:** Ready

Improved error identification in AI output:

- Two-stage filtering to eliminate false positives
- Multi-line pattern matching for complex errors
- Categorize errors (syntax, runtime, test failure, etc.)

---

### [SM] Sandbox Mode

**Complexity:** Medium | **Status:** Ready

Execute cub runs in isolated sandbox environments:

- Provider-agnostic abstraction (Docker, Sprites.dev)
- Isolated filesystem, optional network isolation
- Resource limits (CPU, memory, timeout)
- Easy diff viewing and change extraction

```bash
cub run --sandbox
cub sandbox diff
cub sandbox apply
```

---

## Backlog

Features sequenced primarily by dependencies:

| Feature | ID | Depends On | Description |
|---------|-----|------------|-------------|
| Parallel Development | [PDW] | - | Git worktrees for multi-branch work |
| Dual-Condition Exit | [DCE] | [CB] | Require indicators AND exit signal |
| Fresh Context Mode | [FCM] | [RA] | Clear context between tasks |
| Implementation Review | [IR] | [PR] | Automated post-task code review |
| Receipt-Based Gating | [RBG] | [IR] | Proof-of-work validation |
| Multi-Model Review | [MMR] | [IR] | Cross-model validation |
| Runs Analysis | [RAI] | - | Post-run insights and patterns |
| Verification Integrations | [VI] | - | External service validation |

---

## Research Ideas

Features identified from external tools analysis. These need investigation before planning.

| Feature | ID | Source | Notes |
|---------|-----|--------|-------|
| Multi-Agent Orchestration | [MAO] | Gas Town | Swarm coordination, 20-30 agents |
| Session Checkpointing | [SC] | Gas Town | Git-backed state persistence |
| Team Knowledge Base | [TKB] | Compound Eng | Cross-project knowledge |
| Agent Personas | [AP] | Gas Town | Specialized agents per task type |
| Workflow Recipes | [WR] | Gas Town | TOML-based reusable workflows |
| Standing Orders | [SO] | Gas Town | Auto-run tasks at startup |
| Convergent Review | [CR] | Original | 5-pass review for convergence |
| Heresy Detection | [HD] | Gas Town | Detect incorrect beliefs in code |

---

## Dependency Graph

```
STANDALONE (no dependencies):
[CB] Circuit Breaker
[RA] Re-anchoring
[CHA] Codebase Health Audit
[AED] Advanced Error Detection
[SM] Sandbox Mode
[PDW] Parallel Development
[RAI] Runs Analysis
[VI] Verification Integrations

DEPENDENCY CHAINS:
[DCE] Dual-Condition Exit -----> [CB] Circuit Breaker (soft)
[FCM] Fresh Context Mode ------> [RA] Re-anchoring
[IR] Implementation Review ----> [PR] Plan Review
[RBG] Receipt-Based Gating ----> [IR] Implementation Review
[MMR] Multi-Model Review ------> [IR] Implementation Review

IDEAS (dependencies TBD):
[MAO] Multi-Agent ------------> [PDW] Parallel Development
[SC] Session Checkpointing ---> [CB] Circuit Breaker (soft)
[TKB] Team Knowledge Base ----> [GS] Guardrails System
```

---

## Feature Synergies

Features that work well together:

| Combination | Benefit |
|-------------|---------|
| [SM] + [LD] | Safe execution with full visibility ("confident autonomy") |
| [CB] + [DCE] | Robust loop termination |
| [GS] + [CB] | Failures feed guardrails |
| [GS] + [RA] | Guardrails are part of anchoring context |
| [RAI] + [CHA] | Runtime + static quality signals |
| [VI] + [IR] | AI review + real-world validation |

---

## Proposing Features

Have an idea for Cub? Here's how to propose it:

### 1. Check Existing Ideas

Review this roadmap and [GitHub Issues](https://github.com/lavallee/cub/issues) to see if someone has already proposed something similar.

### 2. Start a Discussion

Open a [GitHub Discussion](https://github.com/lavallee/cub/discussions) with:

- **Problem statement** - What problem does this solve?
- **Proposed solution** - How would it work?
- **Alternatives** - What other approaches were considered?
- **Impact** - Who benefits and how?

### 3. Create an RFC (for major features)

For significant features, create a detailed RFC:

```markdown
# RFC: Feature Name [ID]

## Summary
One paragraph explanation.

## Motivation
Why are we doing this?

## Detailed Design
How will it work?

## Drawbacks
What are the downsides?

## Alternatives
What else was considered?

## Unresolved Questions
What needs more discussion?
```

### 4. Implementation

Once approved:

1. Create an issue linking to the RFC
2. Fork and implement
3. Submit PR with tests and docs
4. Address review feedback

---

## Contributing to Roadmap Features

Want to help implement a roadmap feature?

1. **Check the issue tracker** - See if someone is already working on it
2. **Comment on the issue** - Express interest and ask questions
3. **Review dependencies** - Ensure prerequisite features are complete
4. **Start small** - Consider implementing a minimal version first

!!! tip "Standalone Features"
    Features marked as "standalone" in the dependency graph are great starting points - they don't require other features to be complete first.

---

## Version Planning

Cub uses semantic versioning:

- **Major (1.0)** - Breaking changes, major milestones
- **Minor (0.27)** - New features, backwards compatible
- **Patch (0.26.3)** - Bug fixes, small improvements

Version numbers are assigned at release time based on what ships, not pre-planned.

---

## Next Steps

<div class="grid cards" markdown>

-   :material-github: **Contribute**

    ---

    Start contributing to Cub.

    [:octicons-arrow-right-24: Contributing Guide](index.md)

-   :material-code-braces: **Development Setup**

    ---

    Set up your environment.

    [:octicons-arrow-right-24: Setup Guide](setup.md)

</div>
