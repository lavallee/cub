---
status: researching
priority: medium
complexity: high
dependencies:
  - runs-analysis.md (related)
  - guardrails-system.md (related)
created: 2026-01-18
updated: 2026-01-19
readiness:
  score: 5
  blockers:
    - Storage format not defined
    - Integration points unclear
  questions:
    - File-based vs database storage?
    - How to integrate with existing systems?
  decisions_needed:
    - Choose storage approach (files, DB, hybrid)
    - Define ledger format
    - Design API for querying completed work
  tools_needed:
    - Competitive Analysis Tool (how others compound knowledge: Letta, Compound Engineering)
    - Design Pattern Matcher (knowledge base patterns)
    - API Design Validator (ledger format and query API)
    - Trade-off Analyzer (storage approaches: files vs DB)
notes: |
  Research doc for cross-run knowledge compounding.
  Proposes Completed Work Ledger between beads and git.
  Needs concrete design and implementation plan.
---

# Knowledge Retention System Research

**Date:** 2026-01-18
**Purpose:** Design a comprehensive knowledge retention system for cub that enables human visibility into agentic work, detects plan/implementation drift, and provides agents with fast context recovery.

## Executive Summary

Cub needs a post-task memory system that bridges the gap between in-progress work (beads) and permanent record (git commits). This research proposes a **Completed Work Ledger** that captures task intent, execution trace, and outcomes—serving both human auditing needs and agent context recovery.

**Key Finding:** Simple file-based approaches consistently outperform complex systems. Letta's filesystem-based memory scored 74% on the LoCoMo benchmark, beating sophisticated vector-based solutions.

**Recommendation:** A three-layer memory architecture:
1. **Run Logs** - Detailed audit trail for debugging and cost tracking
2. **Completed Work Ledger** - What was built, why, and outcomes (the missing piece)
3. **Codebase Context** - Regenerated map for fast agent orientation

---

## Part 1: Problem Analysis

### 1.1 The Kanban Mental Model

Cub's workflow maps to a kanban board with distinct handoffs:

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  BACKLOG    │ → │  IN PROGRESS │ → │  COMPLETED  │ → │  ACCEPTED   │
│             │   │              │   │             │   │             │
│ • Capture   │   │ • beads/json │   │ • ???       │   │ • git log   │
│ • Triage    │   │ • cub run    │   │ • (gap!)    │   │ • releases  │
│ • Architect │   │              │   │             │   │             │
│ • Plan      │   │              │   │             │   │             │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

**The Gap:** When a task transitions from "in progress" to "completed," we lose critical information:
- What was the original intent?
- What approach did the agent take?
- What actually changed in the codebase?
- How much did it cost (tokens, time)?
- What lessons were learned?

Beads intentionally forgets (to keep context windows small). Git commits capture *what* changed but not *why* or *how*. The completed work ledger fills this gap.

### 1.2 Current State Analysis

Based on codebase exploration, here's what exists today:

#### Run Logs (`.cub/runs/`)
**What exists:**
- Per-session directories with `run.json` metadata
- Per-task subdirectories with `task.json`
- Status tracking via `status.json`

**What's broken:**
- Token/cost data extracted during runs but **not persisted** to run records
- Harness output logs not captured in runs directory
- No linking between JSONL logs (`~/.local/share/cub/logs/`) and run artifacts
- Iteration counts tracked but not outcomes

#### Guardrails (`.cub/guardrails.md`)
**What exists:**
- Well-designed lesson capture system
- AI-assisted extraction from failures (`guardrails_learn_from_failure`)
- Curation support (`guardrails_curate_ai`)

**What's missing:**
- Not wired into prompt injection during runs
- No effectiveness tracking (did lesson prevent repeat failure?)
- No connection to specific tasks/runs

#### Specs & Progress Tracking
**What exists:**
- Prep pipeline produces structured artifacts (triage.md, architect.md, plan.jsonl)
- Session tracking in `.cub/sessions/`
- Capture system for ideas with frontmatter

**What's broken:**
- `progress.txt` format is unstructured, agent-driven, inconsistent
- No machine-readable progress tracking
- Specs and actual implementation drift without detection

#### Codebase Context
**What exists:**
- CLAUDE.md with project overview and conventions
- No automated generation

**What's missing:**
- No llms.txt or codebase map generation
- Agents must re-explore on each session

### 1.3 Pain Points by Audience

**For Humans (Trust & Verify):**
| Pain Point | Current Workaround | Severity |
|------------|-------------------|----------|
| Can't see what tasks cost | Manual token counting | High |
| Don't know if specs match code | Manual review | High |
| Hard to audit what agent did | Read conversation logs | Medium |
| No aggregate cost view | Spreadsheets | Medium |

**For Agents (Context Recovery):**
| Pain Point | Current Workaround | Severity |
|------------|-------------------|----------|
| Don't know what exists | Re-explore codebase | Medium |
| Repeat past mistakes | None (no memory) | Medium |
| Miss architectural decisions | Read all files | Low |

---

## Part 2: External Research (2025-2026)

### 2.1 Agent Memory Systems

#### Mem0
**GitHub:** https://github.com/mem0ai/mem0

Scalable memory-centric architecture with graph-based representations.
- 26% improvement over OpenAI in LLM-as-a-Judge metrics
- 91% lower p95 latency
- 90%+ token cost savings

**Relevance:** Potentially adoptable for long-term pattern extraction.

#### Letta (formerly MemGPT)
**GitHub:** https://github.com/letta-ai/letta

Key finding from their benchmarking research:
> "Simple filesystem-based memory can outperform complex memory systems."

Letta's filesystem agent achieved **74% on LoCoMo benchmark** using:
- Hierarchical file organization
- Self-managed memory directories
- No external database

**Relevance:** Strong validation for file-based approach. Cub should lean into markdown/JSONL files rather than adding database dependencies.

#### LangMem
**GitHub:** https://github.com/langchain-ai/langmem

Three-memory-type model:
1. **Episodic** - Past interactions, few-shot examples
2. **Procedural** - Generalized skills as prompt rules
3. **Semantic** - Facts and grounding information

**Relevance:** Useful taxonomy for organizing cub's memory layers.

### 2.2 Codebase Context Approaches

#### llms.txt Convention
**Specification:** https://llmstxt.org/

Markdown file at `/llms.txt` providing LLM-friendly content:
- Brief background
- Links to detailed docs
- Optional `/llms-full.txt` for complete content

Adopted by Mintlify across thousands of docs sites including Anthropic and Cursor.

**Relevance:** Directly applicable. Cub could generate llms.txt from prep artifacts.

#### Aider's Repository Map
**Docs:** https://aider.chat/docs/repomap.html

Uses tree-sitter to parse AST, applies PageRank-style ranking:
- Defaults to 1k tokens
- Ranks by cross-file reference frequency
- Supports Python, JS, TS, Java, C/C++, Go, Rust

**Relevance:** Could integrate repomapper for codebase context generation.

#### AGENTS.md Convention
**Specification:** https://agents.md

Cross-tool standard supported by Cursor, Zed, GitHub Copilot, OpenCode.

Best practices:
- Keep under 300 lines
- Use task-specific instruction files
- Let it grow organically from corrections

**Relevance:** Cub's CLAUDE.md approach aligns. Consider AGENTS.md compatibility.

### 2.3 Observability Standards

#### OpenTelemetry GenAI Semantic Conventions
**Spec:** https://opentelemetry.io/docs/specs/semconv/gen-ai/

Emerging standard capturing:
- Prompt tokens, completion tokens, reasoning tokens
- Tool calls, errors, latency
- Time to first token, estimated cost

Agent span conventions:
- `gen_ai.operation.name`: "invoke_agent"
- `gen_ai.agent.name` for span naming

Supported by: IBM Bee Stack, CrewAI, AutoGen, LangGraph

**Relevance:** Could standardize cub's logging format for interoperability.

#### Langfuse
**License:** MIT (fully open source)
**GitHub:** github.com/langfuse/langfuse

Open source LLM observability with:
- Tracing for multi-step workflows
- Self-hostable
- Python SDK

**Relevance:** Potentially adoptable for richer observability without vendor lock-in.

### 2.4 Spec-Driven Development

#### GitHub Spec Kit
**GitHub:** https://github.com/github/spec-kit

Workflow: Constitution → Specify → Plan → Tasks → Implement → PR

Philosophy:
> "Makes specification the center of the engineering process."

Community feedback: Drift between initial spec and result remains a challenge.

**Relevance:** Validates cub's prep pipeline approach. Drift detection is industry-wide problem.

### 2.5 Key Insight Summary

| Source | Insight | Application |
|--------|---------|-------------|
| Letta | Simple file-based beats complex | Stay with markdown/JSONL |
| LangMem | Three memory types | Organize layers by purpose |
| llms.txt | Convention gaining adoption | Generate for agent context |
| OTel GenAI | Standard schema emerging | Adopt for interoperability |
| Spec Kit | Drift is universal problem | Build detection, not prevention |

---

## Part 3: Proposed Architecture

### 3.1 Three-Layer Memory System

```
┌────────────────────────────────────────────────────────────────────┐
│                     CODEBASE CONTEXT                                │
│  Purpose: Fast agent orientation                                    │
│  Audience: Agents                                                   │
│  Retention: Regenerated frequently                                  │
│  Format: llms.txt, codebase-map.md                                 │
└────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ references
                              │
┌────────────────────────────────────────────────────────────────────┐
│                   COMPLETED WORK LEDGER                             │
│  Purpose: What was built, why, outcomes                             │
│  Audience: Both humans and agents                                   │
│  Retention: Permanent, queryable                                    │
│  Format: .cub/ledger/{task-id}.md + index.jsonl                    │
└────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ summarizes
                              │
┌────────────────────────────────────────────────────────────────────┐
│                        RUN LOGS                                     │
│  Purpose: Detailed audit trail                                      │
│  Audience: Humans (debugging, compliance)                           │
│  Retention: Per-session, archivable                                 │
│  Format: .cub/runs/{session}/... + JSONL events                    │
└────────────────────────────────────────────────────────────────────┘
```

### 3.2 Layer 1: Run Logs (Enhanced)

**Location:** `.cub/runs/{session}/`

**Current structure (keep):**
```
.cub/runs/{session}/
├── run.json           # Run metadata
├── status.json        # Real-time status
└── tasks/{task-id}/
    └── task.json      # Task metadata
```

**Additions:**
```
.cub/runs/{session}/
├── run.json           # Enhanced with cost totals
├── status.json
├── events.jsonl       # Structured event log (move from ~/.local/share)
└── tasks/{task-id}/
    ├── task.json      # Enhanced with token/cost data
    ├── harness.log    # Raw harness output (NEW)
    ├── prompt.md      # Rendered prompt sent to harness (NEW)
    └── changes.patch  # Git diff of changes (NEW)
```

**Enhanced task.json schema:**
```json
{
  "id": "beads-abc123",
  "title": "Implement user authentication",
  "started_at": "2026-01-18T10:00:00Z",
  "completed_at": "2026-01-18T10:45:00Z",
  "status": "completed",
  "iterations": 3,
  "exit_code": 0,
  "harness": {
    "name": "claude",
    "model": "sonnet",
    "flags": ["--allowedTools", "Bash,Read,Write"]
  },
  "tokens": {
    "input": 45000,
    "output": 12000,
    "cache_read": 8000,
    "cache_creation": 2000,
    "total": 67000
  },
  "cost_usd": 0.0892,
  "duration_seconds": 2700,
  "files_changed": [
    "src/auth/middleware.ts",
    "src/auth/jwt.ts",
    "tests/auth.test.ts"
  ],
  "commit_hash": "abc123f"
}
```

### 3.3 Layer 2: Completed Work Ledger (New)

**Location:** `.cub/ledger/`

**Purpose:** Persistent record of completed work that survives beads cleanup.

**Structure:**
```
.cub/ledger/
├── index.jsonl        # Quick-lookup index of all completed tasks
├── by-task/
│   ├── beads-abc.md   # Individual task completion records
│   └── beads-def.md
└── by-epic/
    └── epic-001.md    # Epic summary (aggregates tasks)
```

**index.jsonl schema (one line per completed task):**
```json
{"id":"beads-abc","title":"Implement auth","completed":"2026-01-18","cost_usd":0.09,"files":["src/auth/"],"commit":"abc123f","spec":"specs/planned/auth.md"}
```

**Individual task record (beads-abc.md):**
```markdown
# beads-abc: Implement User Authentication

**Completed:** 2026-01-18 10:45:00 UTC
**Duration:** 45 minutes
**Cost:** $0.09 (67,000 tokens)
**Commit:** abc123f

## Original Intent
From spec: Enable users to log in with email/password and receive JWT tokens.

## Approach Taken
- Created JWT middleware with refresh token support
- Used bcrypt for password hashing
- Added Redis session storage

## Files Changed
- `src/auth/middleware.ts` (created)
- `src/auth/jwt.ts` (created)
- `tests/auth.test.ts` (created)
- `src/config.ts` (modified - added JWT secret config)

## Key Decisions
1. Chose JWT over session cookies for stateless scaling
2. Used 24-hour token expiry (not 1-hour per initial spec discussion)
3. Added refresh token rotation for security

## Lessons Learned
- Need to add rate limiting (filed as beads-xyz)
- bcrypt.compare is async - caught by tests

## Verification
- [x] Tests pass (14 new tests)
- [x] Manual verification: login flow works
- [ ] Security review pending

## References
- Spec: `specs/planned/auth.md`
- Run log: `.cub/runs/fox-20260118-100000/tasks/beads-abc/`
- Commit: `abc123f` - "feat: implement user authentication"
```

**Epic summary (epic-001.md):**
```markdown
# Epic: User Authentication System

**Status:** Completed
**Tasks:** 5 of 5 complete
**Total Cost:** $0.47
**Duration:** 4 hours 20 minutes
**Commits:** abc123f..def789a

## Tasks Completed
| ID | Title | Cost | Duration |
|----|-------|------|----------|
| beads-abc | Implement auth middleware | $0.09 | 45m |
| beads-def | Add password reset | $0.12 | 60m |
| beads-ghi | Write auth tests | $0.08 | 35m |
| beads-jkl | Add rate limiting | $0.11 | 55m |
| beads-mno | Update API docs | $0.07 | 25m |

## Spec Drift Analysis
### Matches Spec
- JWT-based authentication
- Email/password login
- Password reset flow

### Diverged from Spec
- Token expiry: 24h (spec said 1h) - decision documented in beads-abc
- Added refresh token rotation (not in original spec)

### Not Implemented
- OAuth social login (descoped to future epic)
```

### 3.4 Layer 3: Codebase Context (New)

**Location:** Project root

**Purpose:** Fast agent orientation without full codebase exploration.

**Files:**
```
project/
├── llms.txt           # LLM-friendly project overview
├── CLAUDE.md          # Existing (enhanced)
└── .cub/
    └── codebase-map.md  # Auto-generated structure map
```

**llms.txt (generated):**
```markdown
# Cub - AI Coding Assistant Orchestrator

## Overview
Cub wraps AI coding assistants (Claude Code, Codex, Gemini) to provide a reliable autonomous coding loop with task management, budget tracking, and structured logging.

## Key Concepts
- **Tasks** managed via beads (`bd` CLI) in `.beads/issues.jsonl`
- **Runs** tracked in `.cub/runs/` with per-task artifacts
- **Guardrails** in `.cub/guardrails.md` capture lessons learned

## Quick Start
- Run tasks: `cub run --once`
- Check status: `cub status`
- View tasks: `bd list --status open`

## Detailed Documentation
- [Architecture](specs/researching/knowledge-retention-system.md)
- [CLI Reference](README.md)
- [Development Guide](CLAUDE.md)

## Recent Changes
See `.cub/ledger/index.jsonl` for completed work history.

## Project Insights from Interactive Sessions
Recent insights extracted from .claude files (last surveyed: 2026-01-18):
- [Key insights from interactive development sessions would appear here]
```

**Surveying .claude Files for Insights:**

Projects often accumulate .claude directories from interactive coding sessions (Claude Code, Codex, etc.). These contain valuable context about:
- Design decisions made during exploration
- Approaches tried and abandoned
- Insights about the codebase that emerged during work

**Proposed approach:**
1. Periodic survey of `.claude/**/*` files (weekly or on-demand)
2. Extract key insights using LLM summarization
3. Update llms.txt with distilled learnings
4. Optionally promote insights to CLAUDE.md or guardrails

This creates a feedback loop where interactive sessions inform future autonomous work.

**codebase-map.md (auto-generated, repomapper style):**
```markdown
# Codebase Map
Generated: 2026-01-18T12:00:00Z

## Structure
```
src/cub/
├── cli/           # Typer CLI commands
├── core/          # Business logic
│   ├── config/    # Configuration loading
│   ├── harness/   # AI harness backends
│   └── tasks/     # Task backends (beads, json)
└── utils/         # Shared utilities
```

## Key Entry Points
- `src/cub/cli/app.py:main` - CLI entry
- `src/cub/core/runner.py:Runner.run` - Main execution loop
- `src/cub/core/harness/claude.py:ClaudeHarness.execute` - Claude integration

## Important Patterns
- Config precedence: CLI > env > project > global > defaults
- All harnesses implement `HarnessProtocol` (src/cub/core/harness/backend.py)
- Task backends implement `TaskBackend` protocol

## Known Pitfalls
From `.cub/guardrails.md`:
- Always use `bd close` not `cub close-task` for task completion
- Token counts require parsing Claude JSON output
```

### 3.5 Integration Points

#### On Task Close
When `bd close <task-id>` is called:
1. Capture task metadata from beads
2. Extract run data from `.cub/runs/`
3. Generate ledger entry (`.cub/ledger/by-task/{task-id}.md`)
4. Update ledger index
5. Optionally extract guardrail from experience

#### On Session End
When `cub run` completes:
1. Finalize run logs with totals
2. Update epic summaries if applicable
3. Regenerate codebase context files
4. Run drift detection against specs

#### On Session Start (Agent)
When agent begins work:
1. Load `llms.txt` for orientation
2. Load `codebase-map.md` for navigation
3. Load relevant ledger entries for context
4. Load guardrails for pitfall avoidance

### 3.6 Drift Detection

**Approach:** Compare specs to ledger entries, not to code directly.

```
specs/planned/auth.md     ←──compare──→   .cub/ledger/by-epic/auth.md
     (intent)                                    (what was built)
```

**Detection triggers:**
- Epic completion
- Manual `cub drift check <spec>`
- Pre-PR review

**Output:**
```markdown
## Drift Report: auth.md

### Implemented as Specified
- [x] JWT-based authentication
- [x] Email/password login

### Diverged (documented)
- Token expiry: 24h vs spec's 1h (see beads-abc decision)

### Diverged (undocumented) ⚠️
- Rate limiting implementation differs from spec

### Not Implemented
- OAuth social login (marked as descoped)

### Action Required
- [ ] Update spec to reflect 24h expiry decision
- [ ] Document rate limiting approach in spec
```

---

## Part 4: Migration Path

### Phase 1: Fix Token Persistence (Quick Win)
**Effort:** Low
**Impact:** High (enables cost tracking)

Changes:
1. Persist `TokenUsage` to `task.json` in run artifacts
2. Aggregate totals in `run.json`
3. Display in `cub status`

Files:
- `src/cub/core/harness/claude.py` - Already extracts tokens
- `src/cub/core/runner.py` - Persist to task record
- `src/cub/core/status/writer.py` - Include in status

### Phase 2: Implement Completed Work Ledger
**Effort:** Medium
**Impact:** High (central missing piece)

Changes:
1. Create ledger directory structure
2. Hook into task close to generate entries
3. Build index.jsonl writer
4. Add `cub ledger` commands for querying

New files:
- `src/cub/core/ledger/writer.py`
- `src/cub/core/ledger/models.py`
- `src/cub/cli/ledger.py`

### Phase 3: Wire Guardrails into Prompts
**Effort:** Low-Medium
**Impact:** Medium (prevents repeat mistakes)

Changes:
1. Load guardrails in harness setup
2. Inject relevant guardrails into task prompt
3. Filter by tags/task type
4. Track which guardrails were applied

Files:
- `src/cub/core/harness/base.py` - Add guardrails loading
- Existing `guardrails.sh` functions (port to Python)

### Phase 4: Add Codebase Context Generation
**Effort:** Medium
**Impact:** Medium (faster agent orientation)

Changes:
1. Generate `llms.txt` from CLAUDE.md + recent activity
2. Integrate repomapper or build simple tree-sitter map
3. Regenerate on session end

Options:
- Use `repomapper` MCP server (external dependency)
- Build minimal Python implementation using tree-sitter
- Start with simple file tree + key function extraction

### Phase 5: Implement Drift Detection
**Effort:** Medium-High
**Impact:** Medium (catches divergence)

Changes:
1. Parse spec markdown for requirements
2. Compare against ledger entries
3. Generate drift reports
4. Integrate with PR workflow

This phase may benefit from LLM assistance for semantic comparison.

### Phase 6: Analysis Scripts
**Effort:** Medium
**Impact:** High (compounds learnings)

Build scripts to analyze:
- Cost trends across releases
- Common failure patterns
- Guardrail effectiveness
- Prompt improvement suggestions

Example:
```bash
cub analyze --last 100 commits
# Output: "Pattern: tasks touching src/auth/ cost 40% more than average"
# Suggestion: Add guardrail about auth complexity
```

---

## Part 5: Design Decisions

### D1: Ledger Granularity
**Decision:** Per-task

Per-task is the right atomic unit for visibility. Tasks may span multiple commits (especially if work is reviewed and sent back). The relationship to commits should be maintained where possible but without over-engineering edge cases.

**Implementation:**
- Ledger entries are keyed by task ID
- Commits should reference task IDs (via trailers or message body)
- Ledger stores commit hashes but doesn't require 1:1 mapping
- Rework on a task (post-review) stays associated with original task

### D2: Storage Location
**Decision:** In `.cub/ledger/`

Consistent with other cub artifacts. Can be gitignored if desired, though recommended to commit for team visibility.

### D3: Direct Harness Use & Interactive Session Recording
**Decision:** Git hooks as safety net + AGENTS.md instructions + CLI session logging

When users run harnesses directly (not through `cub run`):
1. **Instructions in AGENTS.md** - Guide agents to create ledger entries
2. **Git post-commit hook** - Catch-all that creates minimal entries
3. **Hook validation** - Can check if agent followed instructions properly
4. **CLI session recording** - Capture interactive work in ledger format

The hook provides deterministic capture even if instructions aren't followed.

**Hook behavior:**
```bash
# .git/hooks/post-commit (installed by cub init)
# 1. Check if commit message contains Task-Id trailer
# 2. If yes, create/update ledger entry
# 3. If no, create orphan entry with warning
```

**Interactive Session Recording:**

For direct CLI usage (claude, codex, gemini, pi, etc.), add commands/skills to record sessions in a format similar to cub run logs:

```bash
# Start recording a session
claude --record beads-abc123 ...

# Or post-hoc recording
cub ledger record-session \
  --task beads-abc123 \
  --session-dir ~/.claude/sessions/20260118-120000 \
  --approach "Explored authentication patterns" \
  --decisions "Chose JWT over sessions"
```

**Benefits:**
- Captures ad-hoc exploration work that doesn't go through `cub run`
- Preserves design rationale from interactive sessions
- Enables cost tracking for all work (not just orchestrated runs)
- Provides consistent ledger format regardless of workflow

**Implementation considerations:**
- Each CLI (claude, codex, etc.) could support `--record` flag
- Falls back to post-hoc recording via `cub ledger record-session`
- Session directories already exist for most CLIs (e.g., ~/.claude/sessions/)
- Extract token usage from session logs if available

### D4: Git Commit Integration
**Decision:** Task IDs in commit messages (structured trailers)

Commits should reference task IDs where possible:
```
feat: implement user authentication

- Add JWT middleware
- Create password hashing utilities

Task-Id: beads-abc123
```

This provides enough audit trail without heavy tooling. The ledger entry references commit hashes; commits reference task IDs. Full bidirectional mapping not required.

### D5: llms.txt Generation Scope
**Decision:** Start minimal, expand based on feedback

Initial scope:
- Project overview
- Key commands
- Links to docs

Expansion candidates (later):
- Recent changes summary
- Active work from beads
- Known issues

### D6: External Dependencies
**Decision:** Defer most, keep file-based

| Tool | Decision | Rationale |
|------|----------|-----------|
| repomapper | Optional later | File-based map sufficient for now |
| langfuse | Defer | OTel conventions first, then evaluate |
| mem0 | Defer | Letta research shows file-based wins |

---

## Part 6: Cost/Benefit Analysis

### Benefits

| Benefit | Audience | Quantifiable? |
|---------|----------|---------------|
| Cost visibility | Humans | Yes - $/task, $/epic |
| Audit trail | Humans | Yes - query time |
| Faster orientation | Agents | Partial - tokens saved |
| Fewer repeat mistakes | Both | Yes - guardrail effectiveness |
| Drift detection | Humans | Yes - drift rate |

### Costs

| Cost | Type | Mitigation |
|------|------|------------|
| Storage overhead | Disk | Minimal - markdown files |
| Processing overhead | CPU | Regenerate async, cache |
| Complexity | Maintenance | File-based simplicity |
| Migration effort | Engineering | Phased approach |

### ROI Estimate

Assuming:
- Average task costs $0.10 in tokens
- 10% of tasks repeat avoidable mistakes
- 100 tasks/week

Savings from guardrails alone: ~$1/week × 52 = $52/year per project
Plus: Engineer time saved on debugging, cost tracking, context recovery

---

## Part 7: Recommendations

### Immediate (This Sprint)
1. **Fix token persistence** - Store TokenUsage in task.json
2. **Create ledger directory structure** - Even empty, establishes convention
3. **Wire guardrails into prompts** - Leverage existing system

### Short-Term (Next Month)
4. **Implement ledger writer** - Generate entries on task close
5. **Add `cub ledger` CLI** - Query completed work
6. **Generate basic llms.txt** - From CLAUDE.md template

### Medium-Term (Next Quarter)
7. **Drift detection** - Compare specs to ledger
8. **Codebase mapping** - Tree-sitter or repomapper integration
9. **Analysis scripts** - Pattern extraction from history
10. **.claude file surveying** - Regular extraction of insights from interactive sessions
11. **Interactive session recording** - Add `--record` flags to CLIs (claude, codex, etc.) to capture sessions in ledger format

### Deferred
12. **External observability integration** - Wait for OTel GenAI maturity
13. **Cross-project knowledge base** - After single-project works well

---

## Part 8: Templates & Examples

### 8.1 AGENTS.md Template Additions

When `cub init` sets up a project, AGENTS.md should include instructions for direct harness use:

```markdown
## Working with Cub (for AI Agents)

This project uses cub for task orchestration. If you're working directly with a harness
(Claude, Codex, etc.) rather than through `cub run`, please follow these conventions:

### Before Starting Work
1. Check for an assigned task: `bd list --status in_progress --assignee me`
2. If no task assigned, create one: `bd create --title "Your task description"`
3. Note the task ID (e.g., `beads-abc123`)

### During Work
1. Make atomic commits with clear messages
2. Reference task ID in commits using trailers:
   ```
   feat: implement feature X

   - Details of changes

   Task-Id: beads-abc123
   ```

### After Completing Work
1. Create or update ledger entry:
   ```bash
   cub ledger update beads-abc123 \
     --approach "Brief description of approach taken" \
     --decisions "Key decisions made" \
     --lessons "Any lessons learned"
   ```
2. Close the task: `bd close beads-abc123 -r "reason"`
3. If you learned something worth remembering: `cub guardrails add "lesson"`

### If Work Spans Multiple Sessions
- Commit frequently with task ID trailers
- Update ledger entry with progress notes
- Don't close task until fully complete
```

### 8.2 Git Hook Template

Post-commit hook installed by `cub init`:

```bash
#!/usr/bin/env bash
# .git/hooks/post-commit
# Cub Knowledge Retention - Post-Commit Hook
#
# Ensures all commits are captured in the knowledge ledger,
# even when agents work directly with harnesses.

set -e

# Skip if not in a cub-managed project
[[ -d ".cub" ]] || exit 0

# Get commit info
COMMIT_HASH=$(git rev-parse HEAD)
COMMIT_MSG=$(git log -1 --pretty=%B)
COMMIT_AUTHOR=$(git log -1 --pretty=%an)
COMMIT_DATE=$(git log -1 --pretty=%ci)
FILES_CHANGED=$(git diff-tree --no-commit-id --name-only -r HEAD | tr '\n' ',')

# Extract Task-Id from commit message (trailer or body)
TASK_ID=""
if [[ "$COMMIT_MSG" =~ Task-Id:[[:space:]]*([a-zA-Z0-9_-]+) ]]; then
    TASK_ID="${BASH_REMATCH[1]}"
elif [[ "$COMMIT_MSG" =~ (beads-[a-zA-Z0-9]+) ]]; then
    # Fallback: look for beads ID anywhere in message
    TASK_ID="${BASH_REMATCH[1]}"
fi

# Determine ledger entry path
LEDGER_DIR=".cub/ledger/by-commit"
mkdir -p "$LEDGER_DIR"

if [[ -n "$TASK_ID" ]]; then
    # Task-linked commit - update task ledger entry
    TASK_LEDGER=".cub/ledger/by-task/${TASK_ID}.md"

    if [[ -f "$TASK_LEDGER" ]]; then
        # Append commit to existing entry
        cat >> "$TASK_LEDGER" << EOF

### Commit: ${COMMIT_HASH:0:7}
**Date:** $COMMIT_DATE
**Files:** $FILES_CHANGED
EOF
    else
        # Create stub entry (agent should fill in details)
        mkdir -p ".cub/ledger/by-task"
        cat > "$TASK_LEDGER" << EOF
# $TASK_ID

**Status:** In Progress
**First Commit:** $COMMIT_DATE

## Commits
### ${COMMIT_HASH:0:7}
**Date:** $COMMIT_DATE
**Files:** $FILES_CHANGED

---
*Note: This entry was auto-generated by git hook. Please update with:*
- Approach taken
- Key decisions
- Lessons learned
EOF
        echo "cub: Created ledger stub for $TASK_ID - please update with details"
    fi
else
    # Orphan commit - no task ID found
    ORPHAN_LOG=".cub/ledger/orphan-commits.jsonl"

    # Append to orphan log
    cat >> "$ORPHAN_LOG" << EOF
{"commit":"$COMMIT_HASH","date":"$COMMIT_DATE","author":"$COMMIT_AUTHOR","files":"$FILES_CHANGED","message":"${COMMIT_MSG%%$'\n'*}"}
EOF

    echo "cub: Commit $COMMIT_HASH has no Task-Id - logged as orphan"
    echo "     Consider: git commit --amend to add 'Task-Id: beads-xxx' trailer"
fi

# Update ledger index
cub ledger index --quiet 2>/dev/null || true
```

### 8.3 Integration with Existing Specs

This knowledge retention system connects to several existing specs:

#### Connection to Runs Analysis (specs/planned/runs-analysis.md)

The runs-analysis spec defines intelligence extraction from runs. The knowledge retention system provides the data it analyzes:

```
Run Logs (.cub/runs/)          →  Runs Analysis extracts patterns
Completed Work Ledger          →  Runs Analysis correlates with outcomes
Guardrails                     →  Runs Analysis measures effectiveness
```

**Runs Analysis dependencies on this system:**
- Token/cost data in task.json (Phase 1 of migration)
- Structured harness logs (Phase 1)
- Ledger entries with approach/decisions (Phase 2)

**Output from Runs Analysis into this system:**
- Pattern-based guardrail suggestions
- Codebase map updates (areas of frequent change)
- Constitutional principles extraction

#### Connection to Guardrails System (specs/completed/guardrails-system.md)

Guardrails are one layer of institutional memory. The ledger provides context for why guardrails exist:

```
Ledger Entry (lesson learned)  →  Guardrail (preventive rule)
Guardrail (applied in run)     →  Ledger Entry (notes effectiveness)
```

**Enhancements from this system:**
- Track which tasks led to which guardrails
- Measure guardrail effectiveness via ledger outcomes
- Auto-suggest guardrails from repeated ledger lessons

#### Connection to Vision-to-Tasks Pipeline

The prep pipeline (triage→architect→plan→bootstrap) creates specs. The ledger closes the loop:

```
Spec (intent)                  →  Tasks (work items)
Tasks                          →  Ledger (what was built)
Ledger                         →  Drift Report (spec vs reality)
Drift Report                   →  Updated Spec (or new tasks)
```

### 8.4 Example Session Walkthrough

A complete session showing all three layers in action:

#### 1. Session Start (Agent Orientation via Codebase Context)

```bash
# Agent reads context files for fast orientation
cat llms.txt
# → Project overview, key commands, recent changes

cat .cub/codebase-map.md
# → Structure, entry points, known pitfalls

cat .cub/guardrails.md
# → Lessons to avoid repeating
```

#### 2. Work Execution (Run Logs Capture)

```bash
cub run --once

# Behind the scenes:
# - Creates .cub/runs/session-20260118-120000/
# - Writes run.json with config
# - For each task:
#   - Writes task.json with metadata
#   - Captures harness.log (raw output)
#   - Records prompt.md (what was sent)
#   - Tracks tokens in real-time
#   - On completion: writes changes.patch
```

#### 3. Task Completion (Ledger Entry Creation)

```bash
# When bd close beads-abc123 is called:
cub ledger finalize beads-abc123

# Creates .cub/ledger/by-task/beads-abc123.md with:
# - Original intent (from beads task description)
# - Approach taken (from harness log summary)
# - Files changed (from git)
# - Cost/tokens (from run log)
# - Commit references (from git log)

# Updates .cub/ledger/index.jsonl with quick-lookup entry
```

#### 4. Session End (Context Regeneration)

```bash
# Automatic on cub run completion:
cub context regenerate

# Updates:
# - llms.txt with recent activity
# - codebase-map.md if structure changed
# - Runs drift check if epic completed
```

#### 5. Human Review (Audit Trail)

```bash
# Cost analysis
cub ledger stats --since 2026-01-01
# → Total: $47.32 across 156 tasks
# → Average: $0.30/task
# → Most expensive: beads-xyz ($3.20)

# Drift check
cub drift check specs/planned/auth.md
# → 2 items diverged (documented)
# → 1 item diverged (undocumented) ⚠️

# Find what changed
cub ledger show beads-abc123
# → Full details of what was built and why
```

### 8.5 Constitutional Principles (Future)

Some lessons should become "constitutional principles" - high-level rules that shape all work:

```markdown
# .cub/constitution.md

## Architectural Principles
1. **Stateless services**: All services must be horizontally scalable
2. **No ORM**: Use raw SQL with query builders
3. **Test-first**: No PR without tests

## Code Style Principles
4. **No abbreviations**: Variables must have full, descriptive names
5. **Explicit over implicit**: Prefer verbose clarity over clever brevity

## Process Principles
6. **Tasks under 2 hours**: Split larger work into sub-tasks
7. **Commit per logical change**: One commit = one reviewable unit
```

Constitution is loaded alongside guardrails but represents immutable rules rather than learned lessons. Future work could auto-detect when a ledger lesson should be promoted to constitutional status.

---

## References

### Primary Sources
- [Letta Benchmarking Research](https://www.letta.com/blog/benchmarking-ai-agent-memory)
- [llms.txt Specification](https://llmstxt.org/)
- [OpenTelemetry GenAI Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [GitHub Spec Kit](https://github.com/github/spec-kit)
- [Aider Repository Map](https://aider.chat/docs/repomap.html)

### Internal References
- Current run logs: `src/cub/core/status/writer.py`
- Guardrails system: `src/cub/bash/lib/guardrails.sh`
- Token tracking: `src/cub/core/harness/models.py`
- Existing research: `specs/researching/external-tools-analysis.md`
