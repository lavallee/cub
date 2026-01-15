# Cub Roadmap

Features inspired by adjacent tools like [chopshop](https://github.com/lavallee/chopshop), [ralph](https://github.com/iannuttall/ralph), [Gas Town](https://github.com/steveyegge/gastown), [Compound Engineering](https://every.to/chain-of-thought/compound-engineering-how-every-codes-with-agents), and original cub features.

**Versioning:** Features use stable IDs (e.g., `[CB]`). Version numbers are assigned at release time, not pre-planned.

---

## Completed

| Version | Feature | ID |
|---------|---------|-----|
| 0.14 | Vision-to-Tasks Pipeline | [VTP] |
| 0.15 | Plan Review | [PR] |
| 0.16 | Interview Mode | [IM] |
| 0.17 | PRD Import / Document Conversion | [PRD] |
| 0.18 | Onboarding & Project Organization | [OPO] |
| 0.19 | Git Workflow Integration | [GWI] |
| 0.20 | Guardrails System | [GS] |
| 0.23 | Live Dashboard | [LD] |

---

## Now (Active Development)

Features currently being worked on.

| Feature | ID | Notes |
|---------|-----|-------|
| Language Migration (Go + Python) | [LM] | Python CLI complete, bash delegation working |

---

## Next (Ready to Start)

Prioritized features ready to pick up. Order reflects current thinking but can shift.

| Feature | ID | Complexity | Notes |
|---------|-----|------------|-------|
| Circuit Breaker / Stagnation | [CB] | Medium | Standalone, high value |
| Re-anchoring Mechanism | [RA] | Low | Standalone |
| Codebase Health Audit | [CHA] | Medium | Useful during/after migration |
| Advanced Error Detection | [AED] | Low | Enhances existing logging |
| Sandbox Mode | [SM] | Medium | Docker first, then Sprites |

---

## Later (Backlog)

Sequenced primarily by dependencies. Items without dependencies can be reordered freely.

| Feature | ID | Depends On | Notes |
|---------|-----|------------|-------|
| Parallel Development with Worktrees | [PDW] | — | Enables multi-branch work |
| Dual-Condition Exit Gate | [DCE] | [CB] soft | More robust completion detection |
| Fresh Context Mode | [FCM] | [RA] | Prevents context pollution |
| Implementation Review | [IR] | [PR] for full workflow | Post-task code review |
| Receipt-Based Gating | [RBG] | [IR] | Proof-of-work validation |
| Multi-Model Review | [MMR] | [IR] | Cross-model validation |
| Runs Analysis & Intelligence | [RAI] | — | Post-run insights |
| Verification Integrations | [VI] | — | Protocol + plugins |

---

## Ideas (Research Needed)

New features identified from external tools analysis. Need investigation before planning.

| Feature | ID | Source | Notes |
|---------|-----|--------|-------|
| Multi-Agent Orchestration | [MAO] | Gas Town | Swarm coordination, 20-30 agents |
| Session Checkpointing | [SC] | Gas Town | Git-backed state persistence across restarts |
| Team Knowledge Base | [TKB] | Compound Eng | Cross-project knowledge compounding |
| Agent Personas | [AP] | Gas Town | Specialized agents for different task types |
| Workflow Recipes | [WR] | Gas Town | TOML-based reusable workflow templates |
| Standing Orders | [SO] | Gas Town | Auto-run tasks at session startup |
| Convergent Review (Rule of 5) | [CR] | Yegge | 5-pass review for convergence |
| Heresy Detection | [HD] | Gas Town | Detect incorrect beliefs spreading in code |

---

## Dependencies

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

## Synergies

Features that work well together:

- **[SM] + [LD]** — Safe execution with full visibility ("confident autonomy")
- **[CB] + [DCE]** — Robust loop termination
- **[GS] + [CB]** — Failures feed guardrails
- **[GS] + [RA]** — Guardrails are part of anchoring context
- **[RAI] + [CHA]** — Runtime + static quality signals
- **[VI] + [IR]** — AI review + real-world validation

---

## Feature Details

### [LM] Language Migration (Go + Python)

**Source:** Performance analysis
**Status:** In progress

Rewrite performance-critical components from Bash to Go:

**Phase 1 - Core Data (Go):** Task management + config
- 10-50x faster task operations (eliminate jq subprocesses)
- In-memory caching, type safety

**Phase 2 - Harness Layer (Go):** AI backend abstraction
- Proper streaming JSON parsing
- Accurate token counting

**Phase 3 - Git Operations (Go):** Using go-git library
- Batch operations, fewer subprocesses

**Phase 4 - Artifacts (Go):** File I/O and state

**Keep as Bash:** CLI dispatch, hooks, installation
**Keep as Python:** CLI (Typer), pipeline stages, verification plugins

---

### [CB] Circuit Breaker / Stagnation Detection

**Source:** Ralph
**Complexity:** Medium

Detect when the loop is stuck without making progress:
- Track meaningful changes per iteration (file diffs, task completions)
- Configurable threshold (e.g., 3 loops without progress)
- Actions: pause, alert, escalate, or auto-abort
- **Stale task recovery:** Auto-reopen tasks stuck `in_progress` beyond timeout

Configuration: `stagnation.threshold`, `stagnation.action`

---

### [RA] Re-anchoring Mechanism

**Source:** Flow-Next
**Complexity:** Low

Prevent task drift by re-reading context before each task:
- Reload PROMPT.md, AGENT.md, and current task spec before each iteration
- Include git status summary in task context
- Configurable anchoring sources

Configuration: `anchoring.sources`, `anchoring.include_git_state`

---

### [CHA] Codebase Health Audit

**Source:** Original
**Complexity:** Medium

Systematic analysis to maintain codebase quality:

- **Dead Code Detection** — Unused functions, variables, orphan files
- **Documentation Freshness** — README validation, docstring coverage
- **Test Coverage Analysis** — Per-file coverage, test-code alignment
- **Consistency Analysis** — Naming conventions, pattern consistency

Commands: `cub audit`, `cub audit --fix`, `cub audit --ci`

---

### [AED] Advanced Error Detection

**Source:** Ralph
**Complexity:** Low

Improved error identification in AI output:
- Two-stage filtering to eliminate false positives
- Multi-line pattern matching for complex errors
- Categorize errors (syntax, runtime, test failure, etc.)

---

### [SM] Sandbox Mode

**Source:** Original
**Complexity:** Medium

Execute cub runs in isolated sandbox environments:
- Provider-agnostic abstraction (Docker, Sprites.dev)
- Isolated filesystem, optional network isolation
- Resource limits (CPU, memory, timeout)
- Easy diff viewing and change extraction

Commands: `cub run --sandbox`, `cub sandbox diff|apply|clean`

---

### [PDW] Parallel Development with Worktrees

**Source:** Original
**Complexity:** Medium

Safe testing of multiple approaches using git worktrees:
- Isolate experimental work
- Run multiple cub sessions on different branches
- Foundation for multi-agent orchestration

---

### [DCE] Dual-Condition Exit Gate

**Source:** Ralph
**Depends on:** [CB] (soft)
**Complexity:** Low

More sophisticated completion detection:
- Require both completion indicators AND explicit exit signal
- Configurable indicator threshold
- Prevent premature exits on false positives

---

### [FCM] Fresh Context Mode

**Source:** Flow-Next
**Depends on:** [RA]
**Complexity:** Low

Option to start fresh context each iteration:
- Clear accumulated context between tasks
- Trade-off: loses inter-task learning vs gains consistency
- Useful for overnight autonomous runs

Configuration: `context.fresh_per_task: true`

---

### [IR] Implementation Review

**Source:** Flow-Next
**Depends on:** [PR] for full workflow
**Complexity:** Medium

Automated review after task completion:
- Correctness verification
- DRY principle adherence
- Test coverage assessment
- Security scan (OWASP basics)

Command: `cub review <task-id>`

---

### [RBG] Receipt-Based Gating

**Source:** Flow-Next
**Depends on:** [IR]
**Complexity:** Medium

Require proof-of-work before marking tasks complete:
- Define required artifacts per task type
- Validate artifacts exist and pass checks
- Configurable strictness levels

---

### [MMR] Multi-Model Review

**Source:** Flow-Next
**Depends on:** [IR]
**Complexity:** Medium

Cross-validate work using different AI models:
- Run implementation review with secondary model
- Compare assessments for discrepancies
- Flag disagreements for human review

---

### [RAI] Runs Analysis & Intelligence

**Source:** Original
**Complexity:** Medium

Extract actionable insights from completed runs:
- **Instruction Clarity** — Detect agent confusion signals
- **Task Quality** — Correlate structure with success/failure
- **Hook Opportunities** — Suggest automation patterns
- **Delegation Gaps** — Find improvisation vs cub commands

Commands: `cub analyze`, `cub analyze --suggest-hooks`

---

### [VI] Verification Integrations

**Source:** Ramp's Inspect
**Complexity:** High

Connect cub to external services for real-world validation:
- **Verification Protocol** — Standard interface for verifiers
- **Built-in verifiers** — tests, build, lint
- **External verifiers** — Sentry, Datadog, Lighthouse (plugins)

Commands: `cub verify <task-id>`, `cub verify --list`

---

### [MAO] Multi-Agent Orchestration

**Source:** Gas Town
**Complexity:** High
**Status:** Research

Coordinate multiple AI agents working concurrently:
- Convoy system for bundling related tasks
- Worktree-per-agent isolation
- Merge queue for conflict resolution
- Scale to 20-30 agents

See: `specs/research/external-tools-analysis.md`

---

### [SC] Session Checkpointing

**Source:** Gas Town
**Complexity:** Medium
**Status:** Research

Persist session state to git for resume after interrupts:
- Periodic automatic checkpoints
- Preserve conversation context and partial work
- Resume from specific checkpoint

---

### [TKB] Team Knowledge Base

**Source:** Compound Engineering
**Complexity:** Medium
**Status:** Research

Cross-project knowledge that compounds over time:
- Patterns and anti-patterns library
- Promote guardrails to team knowledge
- Git-backed sync across team

---

### [AP] Agent Personas

**Source:** Gas Town
**Complexity:** Medium
**Status:** Research

Specialized agent configurations for different task types:
- `test-writer` — Edge cases, thorough coverage
- `refactorer` — Careful, test-preserving changes
- `security-auditor` — Adversarial thinking

---

### [WR] Workflow Recipes

**Source:** Gas Town
**Complexity:** Low
**Status:** Research

TOML-based reusable workflow templates:
- Parameterized multi-step workflows
- Built-in recipes for common patterns
- Shareable across projects

---

## Notes

- Features marked standalone can be implemented in any order
- Dependent features should follow their prerequisites
- Version numbers are assigned at release time based on what ships
- The "Next" section reflects current priorities but isn't a commitment
- Move features between sections freely as priorities evolve
