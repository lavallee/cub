# Cub Roadmap

Features inspired by adjacent homegrown tools like [chopshop](https://github.com/lavallee/chopshop), and analysis of similar efforts like [ralph-claude-code](https://github.com/frankbria/ralph-claude-code), [ralph](https://github.com/iannuttall/ralph), [gmickel-claude-marketplace](https://github.com/gmickel/gmickel-claude-marketplace), and [chopshop](https://github.com/lavallee/chopshop), plus original cub features.

---

## Point Releases

### Onboarding & Project Organization
**Source:** Original (cub)
**Dependencies:** None (foundational)
**Priority:** High (affects all users)

Improve installation, initialization, and file organization:

**File Organization:**
- Move all cub-managed files into `.cub/` directory
- Clear separation: `.cub/prompt.md`, `.cub/agent.md`, `.cub/progress.md`, etc.
- Symlinks at root for harness compatibility (`CLAUDE.md`, `AGENTS.md`)
- No more file scatter at project root

**Enhanced Installation:**
- Pre-flight dependency checks with clear feedback
- Installation verification (`cub doctor`)
- One-line curl install option
- Clear next-steps guidance

**Guided Initialization:**
- Interactive `cub init` with project type detection
- Smart templates for Node/Python/Go/Rust projects
- Quick mode for non-interactive use
- Contextual help in generated files

**Documentation:**
- `.cub/README.md` quick reference in every project
- In-file comments explaining each section
- Enhanced `cub doctor` with recommendations

Commands:
- `cub doctor` - Comprehensive health check
- `cub migrate-layout` - Migrate from old file layout
- `cub init --quick --type nextjs`

---

### Vision-to-Tasks Pipeline (chopshop integration)
**Source:** [chopshop](~/Projects/chopshop) - integrated into cub
**Dependencies:** None (foundational)
**Integrates:** Interview Mode (project-level), PRD Import (lightweight alt), Plan Review (quality gates)

Complete pipeline for transforming vision docs into executable AI-agent-friendly tasks:

```
Vision Doc ──> cub triage ──> cub architect ──> cub plan ──> cub bootstrap ──> cub run
                  │               │                │              │
                  ▼               ▼                ▼              ▼
             triage.md      architect.md      plan.jsonl      .beads/
             (requirements) (tech design)     (tasks)         PROMPT.md
```

**Stages:**
1. **Triage** - Requirements refinement, interviews about scope/success/constraints
2. **Architect** - Technical design with mindset (prototype→enterprise), scale, stack
3. **Plan** - Task decomposition into micro-sized, AI-optimal tasks with dependencies
4. **Bootstrap** - Initialize beads, import plan, generate PROMPT.md/AGENT.md

**Key concepts from chopshop:**
- **Mindset framework** - Prototype/MVP/Production/Enterprise guides rigor
- **Micro granularity** - 15-30 min tasks fit AI context windows
- **Vertical slices** - Features deliver end-to-end value, not horizontal layers
- **Rich task descriptions** - Context, hints, steps, acceptance criteria, files

Commands:
- `cub pipeline VISION.md` - Full interactive pipeline
- `cub triage|architect|plan|bootstrap` - Individual stages

**Note:** Retires chopshop as standalone tool. Artifacts move from `.chopshop/` to `.cub/sessions/`.

---

### Live Dashboard (tmux)
**Source:** Ralph
**Dependencies:** None

Real-time visual monitoring during autonomous runs:
- Loop status and iteration count
- Token/budget usage with progress bars
- Current task being executed
- Recent log entries
- Rate limit countdown timers

Implementation: `cub run --monitor` launches integrated tmux session with dashboard pane.

---

### Guardrails System (Institutional Memory)
**Source:** [ralph](https://github.com/iannuttall/ralph)
**Dependencies:** None
**Priority:** High (quick win)

Persistent file of "lessons learned" that accumulates across runs and sessions:
- `.cub/guardrails.md` stores curated lessons from failures
- Read before each task iteration to avoid repeating mistakes
- Auto-learn from failures (AI-extracted lessons)
- Persists across context window limits and sessions
- Can be imported/shared between projects

Unlike ephemeral error logs, guardrails are **curated lessons** that inform future behavior.

Commands:
- `cub guardrails show|add|learn|import|clear`

Configuration: `guardrails.enabled`, `guardrails.auto_learn`

---

### Circuit Breaker / Stagnation Detection
**Source:** Ralph
**Dependencies:** None

Detect when the loop is stuck without making progress:
- Track meaningful changes per iteration (file diffs, task completions)
- Configurable threshold (e.g., 3 loops without progress)
- Actions: pause, alert, escalate, or auto-abort
- Distinguish between "working but slow" vs "truly stuck"
- **Stale task recovery:** Auto-reopen tasks stuck `in_progress` beyond timeout

Configuration: `stagnation.threshold`, `stagnation.action`, `stagnation.stale_task_recovery`

---

### PRD Import / Document Conversion
**Source:** Ralph
**Dependencies:** None
**Related:** Vision-to-Tasks Pipeline (full planning alternative)

Lightweight conversion of existing documents into cub tasks:
- Input formats: Markdown, PDF, JSON, plain text
- Auto-generate task hierarchy with dependencies
- Extract acceptance criteria from prose
- Support for GitHub issues import

**Note:** For complex projects, use `cub pipeline` (Vision-to-Tasks) for full triage → architect → plan workflow. PRD Import is for quick conversion of already-structured documents.

Commands: `cub import requirements.md`, `cub import --from-github owner/repo`

---

### Re-anchoring Mechanism
**Source:** Flow-Next
**Dependencies:** None

Prevent task drift by re-reading context before each task:
- Reload PROMPT.md, AGENT.md, and current task spec before each iteration
- Include git status summary in task context
- Optionally include recent progress.txt entries
- Configurable anchoring sources

Configuration: `anchoring.sources`, `anchoring.include_git_state`

---

### Dual-Condition Exit Gate
**Source:** Ralph
**Dependencies:** Circuit Breaker (soft dependency for full benefit)

More sophisticated completion detection:
- Require both completion indicators AND explicit exit signal
- Configurable indicator threshold (e.g., ≥2 completion patterns)
- Respect AI's explicit "not done yet" signals
- Prevent premature exits on false positives

Current cub uses `<promise>COMPLETE</promise>` - this extends with secondary validation.

---

### Interview Mode
**Source:** Flow-Next
**Dependencies:** None
**Related:** Vision-to-Tasks Pipeline (project-level interviews in triage stage)

Deep questioning phase before **task** execution (task-level, not project-level):
- 40+ structured questions to refine task specifications
- Covers edge cases, error handling, integration points
- Generates comprehensive spec documents
- Can run interactively or with AI-generated answers

**Note:** For project-level requirements refinement, use `cub triage` (part of Vision-to-Tasks Pipeline). Interview Mode is for deep-diving into individual tasks.

Command: `cub interview <task-id>` or `cub run --interview-first`

---

### Plan Review
**Source:** Flow-Next
**Dependencies:** None
**Related:** Vision-to-Tasks Pipeline (quality gate between stages)

Automated review of task plans before execution:
- Completeness check (all requirements addressed?)
- Feasibility analysis (dependencies available?)
- Architecture review (patterns consistent?)
- Dependency validation (order correct?)

**Pipeline integration:** Can run automatically between architect → plan → bootstrap stages.

Command: `cub review --plan` or automatic via `review.auto_plan: true`

---

### Implementation Review
**Source:** Flow-Next
**Dependencies:** Plan Review (for full workflow)

Automated review after task completion:
- Correctness verification
- DRY principle adherence
- Test coverage assessment
- Security scan (OWASP basics)
- Style/lint compliance

Command: `cub review <task-id>` or automatic via `review.auto_impl: true`

---

### Receipt-Based Gating
**Source:** Flow-Next
**Dependencies:** Implementation Review

Require proof-of-work before marking tasks complete:
- Define required artifacts per task type (tests, docs, etc.)
- Validate artifacts exist and pass checks
- Block closure until receipts verified
- Configurable strictness levels

Configuration: `gating.require_tests`, `gating.require_docs`, `gating.strictness`

---

### Multi-Model Review
**Source:** Flow-Next
**Dependencies:** Implementation Review

Cross-validate work using different AI models:
- Run implementation review with secondary model
- Compare assessments for discrepancies
- Flag disagreements for human review
- Support for model rotation strategies

Configuration: `review.models: ["sonnet", "opus"]`, `review.require_consensus`

---

### Advanced Error Detection
**Source:** Ralph
**Dependencies:** None

Improved error identification in AI output:
- Two-stage filtering to eliminate false positives
- Multi-line pattern matching for complex errors
- Distinguish JSON field names from actual errors
- Categorize errors (syntax, runtime, test failure, etc.)

Enhances existing logging and failure handling.

---

### Fresh Context Mode
**Source:** Flow-Next
**Dependencies:** Re-anchoring Mechanism

Option to start fresh context each iteration:
- Clear accumulated context between tasks
- Prevent context pollution from long sessions
- Trade-off: loses inter-task learning vs gains consistency
- Useful for overnight autonomous runs

Configuration: `context.fresh_per_task: true`

---

### Sandbox Mode
**Source:** Original (cub)
**Dependencies:** None (pairs well with Live Dashboard)

Execute cub runs in isolated sandbox environments for safe "yolo mode":
- Provider-agnostic abstraction (Docker, Sprites.dev, future providers)
- Isolated filesystem (project copy)
- Optional network isolation
- Resource limits (CPU, memory, timeout)
- Real-time log streaming
- Easy diff viewing and change extraction
- One-command apply or discard

Providers:
- **Docker** (local) - Fast startup, local resources, no external deps
- **Sprites.dev** (cloud) - True VM isolation, scales beyond local, snapshots, team sharing

Commands:
- `cub run --sandbox [--provider docker|sprites]`
- `cub sandbox logs|status|diff|export|apply|clean`

Use cases: Safe autonomous runs, untrusted harness testing, CI/CD, long-running cloud jobs.

---

### Verification Integrations
**Source:** Inspired by [Ramp's Inspect](https://builders.ramp.com/post/why-we-built-our-background-agent)
**Dependencies:** Implementation Review (conceptually related, but independent)

Connect cub to external services so the AI can verify its work against real-world signals:
- **Verification Protocol** - Standard interface for verifiers
- **Built-in verifiers** - tests, build, lint (ship with cub)
- **External verifiers** - Sentry, Datadog, Lighthouse, etc. (separate tools)
- **Hook points** - Run verification at task complete, before close, on demand

Key insight from Ramp:
> "Inspect closes the loop on verifying its work by having all the context and tools needed to prove it."

Design decision: Cub defines the protocol and hooks; verification implementations are plugins/external tools. This keeps cub lean while enabling verification ecosystems.

Commands:
- `cub verify <task-id>` - Run verification
- `cub verify --list` - List available verifiers

Future: Could evolve into standalone verification service.

---

### Language Migration (Go + Python)
**Source:** Performance analysis of cub codebase
**Dependencies:** None (can be done incrementally)

Rewrite performance-critical components from Bash to Go:

**Phase 1 - Core Data (Go):** Task management + config (~400 lines Go vs 1,500 Bash)
- 10-50x faster task operations (eliminate jq subprocesses)
- In-memory caching, type safety

**Phase 2 - Harness Layer (Go):** AI backend abstraction (~350 lines)
- Proper streaming JSON parsing
- Accurate token counting
- Enables parallel harness calls

**Phase 3 - Git Operations (Go):** Using go-git library (~300 lines)
- Batch operations, fewer subprocesses
- Richer git analysis capabilities

**Phase 4 - Artifacts (Go):** File I/O and state (~250 lines)
- Structured templates, in-memory state

**Keep as Bash:** CLI dispatch, hooks (extensibility), installation
**Optional Python:** Pipeline stages (triage/architect/plan), verification plugins

Expected outcome: 10-100x performance on hot paths, 40-50% total code reduction.

---

### Codebase Health Audit
**Source:** Original feature for cub
**Dependencies:** None (can run anytime)
**Timing:** Flexible - before major work, after migrations, or as maintenance

Systematic analysis to maintain codebase quality:

**Dead Code Detection:**
- Unused functions, variables, orphan files
- Multi-language aware (Bash, Go, Python)
- Tools: shellcheck, staticcheck, vulture

**Documentation Freshness:**
- README validation (code examples work, links valid)
- Docstring coverage
- Changelog/version consistency

**Test Coverage Analysis:**
- Per-file coverage reporting
- Test-code alignment (orphan tests, missing tests)
- Coverage trend tracking

**Consistency Analysis:**
- Naming convention drift
- Pattern consistency
- API consistency

Commands:
- `cub audit` - Full audit with summary report
- `cub audit --fix` - Auto-fix safe issues
- `cub audit --ci` - CI integration with thresholds

**Design for shifting ground:** Dynamically detects languages present, adapts analysis. Useful before migrations (identify dead code), during migrations (track orphaned code), and after (verify coverage).

---

### Runs Analysis & Intelligence
**Source:** Original feature for cub
**Dependencies:** None (uses existing run artifacts)

Extract actionable insights from completed runs:

**Instruction Clarity Analysis:**
- Detect agent confusion signals ("I'll assume...", "Could you clarify...")
- Identify which PROMPT.md/task sections cause problems
- Suggest specific wording improvements

**Task Quality Analysis:**
- Correlate task structure with success/failure
- Identify patterns (tasks with "Files Involved" have less scope creep)
- Score task descriptions for completeness

**Hook Opportunity Analysis:**
- Detect recurring manual actions (agent ran tests 87% of tasks)
- Suggest hooks to automate patterns
- Identify hooks to disable (adding overhead without value)

**Delegation Gap Analysis:**
- Find where agents improvise instead of using cub commands
- Detect inconsistent progress tracking (progress.txt vs @progress.txt)
- Propose new cub subcommands (e.g., `cub progress add`)

**Spec-Implementation Skew:**
- Compare task specs to actual implementations
- Detect unmet acceptance criteria
- Identify scope creep and TODOs introduced
- Suggest tasks to revivify or create anew

Commands:
- `cub analyze` - Full analysis of recent runs
- `cub analyze --generate-tasks` - Create follow-up tasks for issues
- `cub analyze --suggest-hooks` - Generate hook scripts

---

## Dependency Graph

```
FOUNDATIONAL:
[Onboarding & Organization]         (foundational - affects all users, first impression)
[Vision-to-Tasks Pipeline]          (foundational - enables end-to-end lifecycle)
[Language Migration]                (foundational - enables performance + new features)

MAINTENANCE & INTELLIGENCE:
[Codebase Health Audit]             (run anytime - before/during/after major work)
[Runs Analysis]                     (post-run - extracts insights, suggests improvements)

STANDALONE:
[Live Dashboard]                    (standalone)
[Guardrails System]                 (standalone, quick win)
[Circuit Breaker]                   (standalone)
[PRD Import]                        (standalone, lightweight alt to Pipeline)
[Re-anchoring]                      (standalone)
[Interview Mode]                    (standalone, task-level complement to Pipeline)
[Plan Review]                       (standalone, quality gate for Pipeline)
[Advanced Error Detection]          (standalone)
[Sandbox Mode]                      (standalone, multi-provider)
[Verification Integrations]         (standalone, protocol-based)

DEPENDENCIES:
[Dual-Condition Exit] ------------> [Circuit Breaker] (soft)
[Implementation Review] ----------> [Plan Review] (for full workflow)
[Receipt-Based Gating] -----------> [Implementation Review]
[Multi-Model Review] -------------> [Implementation Review]
[Fresh Context Mode] -------------> [Re-anchoring]

SYNERGIES:
[Vision-to-Tasks] + [Plan Review] (quality gates between stages)
[Vision-to-Tasks] + [Interview Mode] (project-level + task-level depth)
[Sandbox Mode] + [Live Dashboard] (safe execution + visibility)
[Verification] + [Implementation Review] (AI review + real-world validation)
[Verification] + [Receipt-Based Gating] (verifiers can be receipts)
[Runs Analysis] + [Codebase Health Audit] (runtime + static quality signals)
[Runs Analysis] + [Vision-to-Tasks Pipeline] (feedback improves future planning)
[Guardrails] + [Circuit Breaker] (failures feed guardrails)
[Guardrails] + [Fresh Context Mode] (guardrails persist when context clears)
[Guardrails] + [Re-anchoring] (guardrails are part of anchoring context)
[Onboarding] + [Guardrails] (guardrails.md in .cub/ from start)
[Onboarding] + [Runs Analysis] (enhanced artifacts in .cub/runs/)
```

## Priority Suggestions

**Foundational (start here):**
- Onboarding & Organization (file cleanup, better init, doctor command)
- Vision-to-Tasks Pipeline (chopshop integration)
- Language Migration Phase 1 (Go core: tasks + config)

**High Value, Low Complexity (Quick Wins):**
- Guardrails System (institutional memory - low effort, high impact)
- Live Dashboard
- Circuit Breaker
- Re-anchoring Mechanism
- Advanced Error Detection

**High Value, Medium Complexity:**
- Plan Review
- Implementation Review
- Dual-Condition Exit Gate
- Sandbox Mode (Docker provider first, then Sprites)

**High Value, Higher Complexity:**
- PRD Import (or skip if Pipeline covers needs)
- Interview Mode (task-level, after Pipeline)
- Multi-Model Review
- Verification Integrations (protocol + built-in verifiers first)

**Build Last (dependent features):**
- Receipt-Based Gating
- Fresh Context Mode

**Confidence Enablers (unlock autonomous adoption):**
- Sandbox Mode (safe experimentation - Docker local, Sprites cloud)
- Circuit Breaker (prevents runaway loops)
- Live Dashboard (visibility into what's happening)
- Verification Integrations (prove the work is correct)

**End-to-End Lifecycle:**
- Vision-to-Tasks Pipeline (vision → tasks)
- cub run (tasks → code)
- Verification + Implementation Review (code → validated)

**Maintenance & Intelligence (run as needed):**
- Codebase Health Audit (before migrations, after major work, or periodically)
- Runs Analysis (after runs - extract insights, improve prompts/tasks/hooks)

---

## Notes

- Features marked "standalone" can be implemented in any order
- Dependent features should follow their prerequisites
- Consider bundling related features (e.g., Plan + Implementation Review)
- Dashboard could be delivered as MVP then enhanced incrementally
- Sandbox Mode + Live Dashboard together provide "confident autonomy" - safe execution with full visibility
- Sandbox Mode uses provider abstraction: implement Docker first, add Sprites.dev later without changing CLI
- Verification uses plugin architecture: cub defines protocol, ecosystem builds verifiers
- Key insight from Ramp: "closing the loop" on verification is what enables 30% of PRs from AI
- Circuit Breaker + Dual-Condition Exit together provide robust loop termination

**Ralph Contributions:**
- Guardrails System: Persistent "lessons learned" that accumulates across runs
- Enhanced run artifacts: rendered prompts, git state before/after, separated error logs
- Stale task recovery: Auto-reopen tasks stuck `in_progress` beyond timeout
- Agent abstraction layer: Multi-backend support (Claude, Codex, Droid, OpenCode)

**Chopshop Integration:**
- Vision-to-Tasks Pipeline absorbs chopshop functionality
- Retires chopshop as standalone tool
- Artifacts move: `.chopshop/sessions/` → `.cub/sessions/`
- Commands: `/chopshop:*` → `cub triage|architect|plan|bootstrap`
- Key concepts preserved: mindset framework, micro-granularity, vertical slices, rich task descriptions

**Language Migration Strategy:**
- Current: ~9,400 lines Bash with jq/git subprocess overhead
- Target: Go for performance-critical core (tasks, harness, config, git, artifacts)
- Keep Bash for: CLI dispatch, hooks (extensibility), installation
- Optional Python for: Pipeline stages (AI-heavy), verification plugins
- Phased approach: Separate Go binaries first, evaluate unification later
- Expected: 10-100x performance on hot paths, 40-50% code reduction
