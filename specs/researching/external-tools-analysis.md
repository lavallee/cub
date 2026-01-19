# External Tools Analysis: Loom, Gastown, and Compound Engineering

**Date:** 2026-01-15
**Purpose:** Compare external AI coding orchestration tools with cub's roadmap, identify feature parallels, techniques to extend existing specs, and potential new features.

## Executive Summary

This analysis examines three significant AI coding orchestration approaches:

1. **Loom** (ghuntley) - Server-side LLM proxy with tool execution and conversation persistence
2. **Gas Town** (steveyegge) - Multi-agent workspace manager with git-backed state persistence
3. **Compound Engineering** (Every.to) - Methodology + plugin for systematic knowledge capture

**Key Finding:** Cub already implements or has planned many core concepts from these tools. The primary gaps are in **multi-agent orchestration** and **systematic knowledge compounding**. Several techniques from these tools could significantly enhance existing specs.

---

## Part 1: Feature Parallels (What Cub Already Has)

### 1.1 Planning Pipeline

| External Tool | Their Feature | Cub Equivalent | Status |
|--------------|---------------|----------------|--------|
| Compound Engineering | `/workflows:plan` - Transform concepts into plans | `cub pipeline` / Vision-to-Tasks | Completed (0.14) |
| Every.to | 80/20 planning vs execution split | Triage → Architect → Plan stages | Completed |
| Gas Town | Formulas (TOML workflow recipes) | Session-based pipeline with stages | Completed |

**Assessment:** Cub's Vision-to-Tasks pipeline is more comprehensive than Compound Engineering's planning phase. The four-stage approach (triage → architect → plan → bootstrap) provides deeper requirements refinement.

### 1.2 Institutional Memory / Knowledge Capture

| External Tool | Their Feature | Cub Equivalent | Status |
|--------------|---------------|----------------|--------|
| Compound Engineering | `/workflows:compound` - Capture learnings | `cub guardrails` | Completed (0.20) |
| Every.to | "Each bug gets documented for future agents" | Auto-learn from failures | Spec complete |
| Gas Town | Beads ledger for task state | Beads integration | Completed |

**Assessment:** Cub's guardrails system directly parallels Compound Engineering's "compound" phase. Both capture lessons to improve future iterations. Cub's approach is more structured with categories (project-specific, failure-derived, imported).

### 1.3 Task Management & Tracking

| External Tool | Their Feature | Cub Equivalent | Status |
|--------------|---------------|----------------|--------|
| Gas Town | Convoys (bundled task collections) | Epics in beads | Completed |
| Gas Town | Work persists in git-backed hooks | `.beads/issues.jsonl` | Completed |
| Gas Town | `gt convoy list` - Track distributed work | `bd list`, `cub status` | Completed |

**Assessment:** Cub + Beads provides equivalent task persistence and tracking. The key difference is Gas Town tracks across multiple agents while cub currently tracks single-agent execution.

### 1.4 Git Workflow Integration

| External Tool | Their Feature | Cub Equivalent | Status |
|--------------|---------------|----------------|--------|
| Gas Town | Hooks as git worktrees | Branch-per-epic binding | Completed (0.19) |
| Gas Town | Rigs (project containers) | Project-level `.cub/` | Completed (0.18) |
| Compound Engineering | `/workflows:work` - Execute in worktrees | `cub branch` for epic isolation | Completed |

**Assessment:** Direct parallel. Both use git worktrees/branches for work isolation. Gas Town's "hooks" terminology maps to cub's branch-epic bindings.

### 1.5 Stagnation Detection

| External Tool | Their Feature | Cub Equivalent | Status |
|--------------|---------------|----------------|--------|
| Loom | State machine for conversation flow | Circuit Breaker state machine | Spec complete |
| Gas Town | Witnesses monitor agent health | Circuit Breaker + stale task recovery | Spec complete |

**Assessment:** Cub's circuit breaker spec covers stagnation detection. Gas Town's "Witness" role is more focused on multi-agent monitoring which cub doesn't yet have.

### 1.6 Review & Verification

| External Tool | Their Feature | Cub Equivalent | Status |
|--------------|---------------|----------------|--------|
| Compound Engineering | `/workflows:review` - Multi-agent code review | Multi-Model Review (0.34) | Spec complete |
| Every.to | "Engineers evaluate outputs" | Implementation Review (0.32) | Spec complete |

**Assessment:** Cub's review specs are more comprehensive, including plan review, implementation review, and multi-model review.

---

## Part 2: Techniques to Extend Existing Specs

### 2.1 Enhance Guardrails System (from Compound Engineering)

**Current Spec:** Guardrails capture lessons from failures.

**Enhancement from Compound Engineering:**
- Track **success patterns** not just failures
- Measure guardrail effectiveness (did lesson prevent repeat failure?)
- Auto-suggest PROMPT.md improvements from guardrails patterns

**Suggested additions to `specs/roadmap/guardrails-system.md`:**

```markdown
## Effectiveness Tracking (from Compound Engineering)

Track whether guardrails actually prevent repeat failures:

- Record task IDs where guardrail was applied
- Track if similar failures occurred after guardrail added
- Score guardrails by prevention rate
- Auto-archive ineffective guardrails (< 20% prevention rate)

## Success Pattern Capture

Extend beyond failures to capture positive patterns:

- "When this task structure was used, completion rate was 95%"
- "Tasks with 'Files Involved' section had 40% less scope creep"
- Feed successful patterns back to Vision-to-Tasks pipeline
```

### 2.2 Enhance Circuit Breaker (from Gas Town Witness Pattern)

**Current Spec:** Detect stagnation in single-agent execution.

**Enhancement from Gas Town:**
- Witness role provides external observation
- Health checks independent of the agent's self-reporting
- Multiple signal sources for stagnation

**Suggested additions to `specs/roadmap/circuit-breaker.md`:**

```markdown
## External Witness Pattern (from Gas Town)

Add independent verification beyond agent self-reporting:

### External Health Signals
- File system watcher: Are files actually changing?
- Process monitor: Is the harness process active?
- Git status polling: Are commits being made?
- Test runner polling: Are tests passing/failing?

### Implementation
```bash
# Witness runs as background process
cub run --witness &

# Witness checks independently:
# 1. Last file modification time
# 2. Harness process status
# 3. Git commit timestamps
# 4. Test result changes
```

### Benefits
- Catches silent hangs (agent process alive but stuck)
- Detects false completion claims with external validation
- Provides objective progress metrics vs agent's subjective reports
```

### 2.3 Enhance Live Dashboard (from Gas Town Dashboard)

**Current Spec:** tmux-based monitoring of single run.

**Enhancement from Gas Town:**
- Web-based dashboard for remote monitoring
- Multi-agent visibility (future-proofing)
- Convoy/batch progress tracking

**Suggested additions to `specs/roadmap/live-dashboard.md`:**

```markdown
## Web Dashboard Mode (from Gas Town)

Optional web interface for remote monitoring:

```bash
cub run --dashboard-web --port 8080
```

### Features
- Same metrics as tmux dashboard
- Accessible from any browser
- Mobile-friendly for monitoring on the go
- WebSocket updates (no polling)

### Future: Multi-Session View
When parallel development lands (0.24), dashboard shows:
- All active cub sessions
- Aggregate token/budget usage
- Cross-session progress
```

### 2.4 Enhance Sandbox Mode (from Loom Remote Execution)

**Current Spec:** Docker and Sprites.dev providers.

**Enhancement from Loom:**
- Kubernetes pod execution ("Weaver" pattern)
- Server-side credential storage
- Session persistence across container restarts

**Suggested additions to `specs/roadmap/sandbox-mode.md`:**

```markdown
## Kubernetes Provider (from Loom "Weaver")

For teams with existing k8s infrastructure:

### Configuration
```json
{
  "sandbox": {
    "provider": "kubernetes",
    "kubernetes": {
      "namespace": "cub-sandboxes",
      "image": "cub-runtime:latest",
      "resource_limits": {
        "cpu": "2",
        "memory": "4Gi"
      },
      "persistent_volume_claim": "cub-workspaces"
    }
  }
}
```

### Benefits
- Leverage existing k8s infrastructure
- Better resource management than local Docker
- Persistent volumes survive pod restarts
- Team-wide sandbox sharing

## Credential Proxy Pattern (from Loom)

Keep API keys server-side only:

### Architecture
```
Local CLI ──> Cub Proxy Server ──> AI Provider
              (stores API keys)
```

### Benefits
- API keys never stored on local machine
- Centralized key rotation
- Usage tracking and limits
- Team key sharing without exposure
```

### 2.5 Enhance Vision-to-Tasks Pipeline (from Compound Engineering Loop)

**Current Spec:** Linear pipeline (triage → architect → plan → bootstrap).

**Enhancement from Compound Engineering:**
- Explicit "compound" step that feeds back into planning
- Lessons from execution inform next planning cycle

**Suggested additions to `specs/roadmap/vision-to-tasks-pipeline.md`:**

```markdown
## Feedback Loop Integration (from Compound Engineering)

Add explicit feedback from execution back to planning:

### Post-Run Analysis
After `cub run` completes an epic:
1. Analyze which tasks were problematic
2. Identify patterns in task structure that correlated with success
3. Update pipeline templates based on learnings

### Implementation
```bash
# After epic completion
cub analyze --epic <epic-id> --suggest-pipeline-improvements

# Output: Suggested updates to:
# - Default task template
# - Granularity recommendations
# - Label usage patterns
```

### Compound Loop
```
Vision → Triage → Architect → Plan → Bootstrap → Run → Analyze
  ↑                                                      │
  └──────────────── Learnings feed back ─────────────────┘
```

This creates the "compounding" effect where each project makes subsequent projects easier.
```

---

## Part 3: New Features Not in Current Roadmap

### 3.1 Multi-Agent Orchestration

**Source:** Gas Town (primary), Loom (secondary)

**Gap:** Cub currently executes single-agent workflows. Gas Town demonstrates running 20-30 agents concurrently with structured coordination.

**Proposed Feature: `cub swarm` (v0.36)**

```markdown
# Multi-Agent Orchestration

**Source:** [Gas Town](https://github.com/steveyegge/gastown)
**Dependencies:** Parallel Development with Worktrees (0.24), Live Dashboard (0.23)
**Complexity:** High

## Overview

Coordinate multiple AI agents working on different tasks concurrently. Each agent operates in an isolated worktree, with a coordinator managing work distribution.

## Architecture (inspired by Gas Town)

```
┌─────────────────────────────────────────┐
│            COORDINATOR (Mayor)           │
│  - Work distribution                     │
│  - Progress aggregation                  │
│  - Conflict detection                    │
└─────────────────────────────────────────┘
        │           │           │
        ▼           ▼           ▼
   ┌────────┐  ┌────────┐  ┌────────┐
   │ Agent 1│  │ Agent 2│  │ Agent 3│
   │ (haiku)│  │ (sonnet)│ │ (opus) │
   │ Task A │  │ Task B │  │ Task C │
   │ Branch │  │ Branch │  │ Branch │
   │   A    │  │   B    │  │   C    │
   └────────┘  └────────┘  └────────┘
```

## Core Concepts

### Convoys (from Gas Town)
Bundle related tasks for batch assignment:
```bash
cub convoy create "auth-feature" beads-001 beads-002 beads-003
cub convoy assign "auth-feature" --agents 3
```

### Work Distribution Strategies
- **Round-robin:** Distribute evenly
- **Complexity-based:** Match task complexity to model capability
- **Domain-based:** Route by label (backend tasks → backend specialist)

### Conflict Prevention
- Each agent works in isolated worktree
- No two agents work on same file simultaneously
- Coordinator merges completed work to main

## Interface

```bash
# Start multi-agent run
cub swarm --agents 3 --epic <epic-id>

# With specific distribution
cub swarm --agents 3 --strategy complexity

# Monitor swarm
cub swarm status
cub swarm dashboard

# Stop gracefully
cub swarm stop
```

## Configuration

```json
{
  "swarm": {
    "max_agents": 5,
    "strategy": "complexity",
    "model_mapping": {
      "complexity:low": "haiku",
      "complexity:medium": "sonnet",
      "complexity:high": "opus"
    },
    "merge_strategy": "sequential",
    "conflict_action": "pause"
  }
}
```

## Implementation Phases

### Phase 1: Manual Swarm
- Human creates branches
- Human assigns tasks to branches
- `cub run` in each branch
- Human merges results

### Phase 2: Automated Distribution
- `cub swarm` creates worktrees
- Distributes tasks based on strategy
- Runs agents in parallel
- Human reviews and merges

### Phase 3: Full Orchestration
- Coordinator agent manages distribution
- Automatic conflict detection
- Auto-merge non-conflicting changes
- Human approval for conflicts

## Acceptance Criteria

- [ ] Convoy creation and management
- [ ] Worktree-per-agent isolation
- [ ] Parallel agent execution
- [ ] Progress aggregation dashboard
- [ ] Conflict detection
- [ ] Sequential merge capability
```

### 3.2 Work Persistence Across Restarts

**Source:** Gas Town "Hooks" Pattern

**Gap:** When cub run is interrupted, resuming requires manual context recovery.

**Proposed Feature: Session Checkpointing (v0.37)**

```markdown
# Session Checkpointing

**Source:** [Gas Town](https://github.com/steveyegge/gastown) hooks pattern
**Dependencies:** None
**Complexity:** Medium

## Overview

Persist session state to git so interrupted runs can resume with full context. Unlike current resume (which just continues from last task), this preserves conversation context, partial work, and in-flight changes.

## Problem

Current interruption handling:
1. Agent crashes mid-task
2. `cub run` restarts
3. New context - agent has no memory of prior work
4. May redo or conflict with partial changes

## Solution: Git-Backed Session State

```
.cub/sessions/{session-id}/
├── state.json          # Current session state
├── context.md          # Accumulated context for resume
├── partial/            # Uncommitted changes (stash-like)
│   ├── changes.patch
│   └── files/
└── checkpoints/        # Periodic snapshots
    ├── checkpoint-001.json
    └── checkpoint-002.json
```

## Checkpoint Contents

```json
{
  "session_id": "run-20260115-120000",
  "checkpoint_id": "checkpoint-003",
  "timestamp": "2026-01-15T12:30:00Z",
  "task": {
    "id": "beads-abc123",
    "status": "in_progress",
    "iteration": 5
  },
  "context": {
    "conversation_summary": "Working on auth middleware...",
    "key_decisions": ["Using JWT", "Redis for sessions"],
    "blockers_encountered": ["Rate limit hit at iteration 3"]
  },
  "partial_work": {
    "files_modified": ["src/auth.ts", "src/middleware.ts"],
    "patch_file": "partial/changes.patch"
  },
  "metrics": {
    "tokens_used": 50000,
    "budget_remaining": 150000
  }
}
```

## Interface

```bash
# Run with checkpointing (automatic)
cub run --checkpoint-interval 5m

# Resume from checkpoint
cub run --resume <session-id>

# List available checkpoints
cub checkpoints list
cub checkpoints show <checkpoint-id>

# Manual checkpoint
cub checkpoint create "before risky change"
```

## Resume Behavior

On `cub run --resume`:
1. Load checkpoint state
2. Restore partial changes (git stash pop equivalent)
3. Inject context summary into prompt
4. Continue from last task iteration

## Configuration

```json
{
  "checkpointing": {
    "enabled": true,
    "interval_minutes": 5,
    "max_checkpoints": 10,
    "include_conversation": true,
    "auto_resume": true
  }
}
```

## Acceptance Criteria

- [ ] Periodic automatic checkpointing
- [ ] Checkpoint storage in git-backed format
- [ ] Resume from specific checkpoint
- [ ] Partial work preservation (uncommitted changes)
- [ ] Context summary injection on resume
- [ ] Checkpoint cleanup/rotation
```

### 3.3 Compound Knowledge Base

**Source:** Compound Engineering methodology

**Gap:** Guardrails capture project-specific lessons, but there's no cross-project knowledge sharing.

**Proposed Feature: Team Knowledge Base (v0.38)**

```markdown
# Team Knowledge Base

**Source:** [Compound Engineering](https://every.to/chain-of-thought/compound-engineering-how-every-codes-with-agents)
**Dependencies:** Guardrails System (0.20)
**Complexity:** Medium

## Overview

Shared repository of lessons learned that compounds across projects and team members. Unlike project-specific guardrails, the knowledge base captures transferable patterns.

## The Compound Effect

From Every.to:
> "Each feature makes the next feature easier to build"

Applied to teams:
- Developer A learns pattern X in Project 1
- Pattern X gets added to team knowledge base
- Developer B on Project 2 benefits from pattern X
- Team productivity compounds over time

## Architecture

```
~/.cub/knowledge/              # Global team knowledge
├── patterns/
│   ├── auth.md               # Authentication patterns
│   ├── testing.md            # Testing patterns
│   └── error-handling.md     # Error handling patterns
├── anti-patterns/
│   └── common-mistakes.md    # Things that never work
└── index.json                # Searchable index

project/.cub/guardrails.md    # Project-specific (existing)
```

## Knowledge Entry Format

```markdown
## Pattern: JWT Token Refresh

**Context:** Web applications with authentication
**Language:** TypeScript, JavaScript
**Applicability:** Production, Enterprise mindsets

### Problem
Access tokens expire, causing auth failures mid-session.

### Solution
```typescript
// Interceptor pattern for automatic refresh
const refreshInterceptor = async (error) => {
  if (error.response?.status === 401) {
    await refreshToken();
    return retry(error.config);
  }
  throw error;
};
```

### When NOT to Use
- Prototype mindset (complexity not worth it)
- Server-to-server auth (use long-lived tokens)

### Related
- See also: `patterns/auth.md#session-management`

### Source
- Learned: Project XYZ, 2026-01-10
- Contributor: @developer
- Effectiveness: 95% (prevented 19/20 similar issues)
```

## Interface

```bash
# Search knowledge base
cub knowledge search "jwt refresh"
cub knowledge search --tag authentication

# Add to knowledge base
cub knowledge add patterns/new-pattern.md
cub knowledge promote   # Promote guardrail to knowledge base

# Sync with team
cub knowledge sync      # Push/pull from shared repo
cub knowledge import https://github.com/team/knowledge

# Use in run
cub run --include-knowledge "auth,testing"
```

## Integration Points

### With Guardrails
```bash
# Promote project guardrail to team knowledge
cub knowledge promote --guardrail "JWT refresh pattern"
```

### With Vision-to-Tasks
- Knowledge base suggests patterns during architect phase
- "Based on team knowledge, consider JWT refresh pattern for auth"

### With Runs Analysis
- Identify patterns across runs that should be promoted
- Track knowledge effectiveness (did pattern prevent issues?)

## Configuration

```json
{
  "knowledge": {
    "enabled": true,
    "path": "~/.cub/knowledge",
    "remote": "git@github.com:team/cub-knowledge.git",
    "auto_sync": true,
    "include_in_prompt": ["relevant"],
    "max_entries_per_prompt": 5
  }
}
```

## Acceptance Criteria

- [ ] Global knowledge base storage
- [ ] Pattern and anti-pattern categories
- [ ] Search functionality (text and tags)
- [ ] Promote guardrail to knowledge
- [ ] Remote sync (git-backed)
- [ ] Include relevant knowledge in prompts
- [ ] Effectiveness tracking
```

### 3.4 Agent Specialization

**Source:** Gas Town roles (Mayor, Polecats), Loom tool registry

**Gap:** Cub uses one agent type for all tasks. Different task types might benefit from specialized agents.

**Proposed Feature: Agent Personas (v0.39)**

```markdown
# Agent Personas

**Source:** [Gas Town](https://github.com/steveyegge/gastown) role system
**Dependencies:** None
**Complexity:** Medium

## Overview

Define specialized agent personas optimized for different task types. Instead of one-size-fits-all prompting, personas tune the agent's behavior for specific domains.

## Motivation

Gas Town observation:
> "Some roles are per-rig (project-specific), while others are town-level"

Different tasks need different approaches:
- **Test writing** → Conservative, thorough, edge-case focused
- **Prototyping** → Fast, hacky, minimal
- **Security review** → Paranoid, thorough, adversarial thinking
- **Refactoring** → Careful, incremental, test-preserving

## Persona Definition

```yaml
# .cub/personas/test-writer.yaml
name: test-writer
description: Specialized for writing comprehensive tests
model_preference: sonnet  # Good balance for test complexity

system_prompt_additions: |
  You are writing tests. Focus on:
  - Edge cases and boundary conditions
  - Error scenarios and exception handling
  - Clear test names that describe behavior
  - Minimal mocking, prefer integration tests
  - AAA pattern (Arrange, Act, Assert)

guardrail_tags:
  - testing
  - quality

temperature: 0.3  # Lower temperature for consistent tests
max_iterations: 10  # Tests shouldn't take many iterations
```

## Built-in Personas

### `implementer` (default)
General-purpose implementation, current behavior.

### `test-writer`
Comprehensive test generation with edge case focus.

### `refactorer`
Careful restructuring that preserves behavior.

### `reviewer`
Critical analysis, finding issues, suggesting improvements.

### `documenter`
Clear documentation, examples, and explanations.

### `security-auditor`
Adversarial thinking, vulnerability identification.

## Interface

```bash
# Run with persona
cub run --persona test-writer

# Run with auto-persona selection (based on labels)
cub run --auto-persona

# List available personas
cub personas list

# Create custom persona
cub personas create my-persona

# Test persona with single task
cub run --task beads-abc --persona security-auditor
```

## Auto-Persona Selection

Based on task labels:
```json
{
  "personas": {
    "auto_selection": {
      "label:testing": "test-writer",
      "label:refactor": "refactorer",
      "label:security": "security-auditor",
      "label:docs": "documenter",
      "default": "implementer"
    }
  }
}
```

## Integration with Multi-Agent

When swarm mode lands:
- Each agent can have different persona
- Test-writer agent runs in parallel with implementer agent
- Specialized agents for specialized tasks

## Acceptance Criteria

- [ ] Persona definition format (YAML)
- [ ] Built-in personas (5 minimum)
- [ ] `--persona` flag for cub run
- [ ] Auto-persona selection from labels
- [ ] Custom persona creation
- [ ] Persona-specific guardrail filtering
```

### 3.5 Formula/Recipe System

**Source:** Gas Town Formulas

**Gap:** Cub has individual commands but no way to define reusable multi-step workflows.

**Proposed Feature: Workflow Recipes (v0.40)**

```markdown
# Workflow Recipes

**Source:** [Gas Town](https://github.com/steveyegge/gastown) formula system
**Dependencies:** None
**Complexity:** Low

## Overview

Define reusable, parameterized workflows as TOML files. Recipes encode best practices and standard procedures that can be shared across projects and teams.

## Motivation

Gas Town observation:
> "Formulas enable repeatable processes with templated variables"

Common workflows that should be recipes:
- "Add a new API endpoint"
- "Create a React component with tests"
- "Implement a database migration"
- "Set up CI/CD for new project"

## Recipe Format

```toml
# .cub/recipes/new-api-endpoint.toml
[recipe]
name = "new-api-endpoint"
description = "Add a new REST API endpoint with tests"
version = "1.0"

[vars]
endpoint_name = { prompt = "Endpoint name (e.g., /users)", required = true }
http_method = { prompt = "HTTP method", default = "GET", options = ["GET", "POST", "PUT", "DELETE"] }
requires_auth = { prompt = "Requires authentication?", type = "bool", default = true }

[[steps]]
name = "create-route"
type = "task"
title = "Create {{endpoint_name}} route handler"
labels = ["api", "implementation"]
description = """
Create route handler for {{http_method}} {{endpoint_name}}.
{{#if requires_auth}}
Include authentication middleware.
{{/if}}
"""

[[steps]]
name = "create-tests"
type = "task"
title = "Write tests for {{endpoint_name}}"
labels = ["testing"]
depends_on = ["create-route"]
persona = "test-writer"
description = """
Write integration tests for {{endpoint_name}}:
- Happy path
- Validation errors
- {{#if requires_auth}}Authentication failures{{/if}}
"""

[[steps]]
name = "update-docs"
type = "task"
title = "Update API documentation"
labels = ["docs"]
depends_on = ["create-route"]
persona = "documenter"
```

## Interface

```bash
# List available recipes
cub recipes list

# Run a recipe
cub recipes run new-api-endpoint

# Run with pre-filled variables
cub recipes run new-api-endpoint \
  --var endpoint_name=/users \
  --var http_method=POST

# Dry-run (show what would be created)
cub recipes run new-api-endpoint --dry-run

# Create custom recipe
cub recipes create my-recipe

# Import recipes from repository
cub recipes import https://github.com/team/cub-recipes
```

## Built-in Recipes

### `new-feature`
Full feature with implementation + tests + docs.

### `bug-fix`
Bug fix with regression test.

### `refactor-module`
Safe refactoring with test preservation.

### `add-dependency`
Add dependency with documentation update.

### `release`
Version bump, changelog, tag, release notes.

## Recipe Execution

```bash
$ cub recipes run new-api-endpoint

Recipe: new-api-endpoint
Description: Add a new REST API endpoint with tests

Variables:
? Endpoint name (e.g., /users): /products
? HTTP method [GET]: POST
? Requires authentication? [Y/n]: Y

Creating tasks:
  ✓ beads-001: Create /products route handler
  ✓ beads-002: Write tests for /products (depends on beads-001)
  ✓ beads-003: Update API documentation (depends on beads-001)

Ready to run: cub run --epic <generated-epic>
```

## Acceptance Criteria

- [ ] Recipe definition format (TOML)
- [ ] Variable interpolation with Handlebars-style templates
- [ ] Step dependencies
- [ ] Built-in recipes (5 minimum)
- [ ] `cub recipes run` command
- [ ] Dry-run mode
- [ ] Recipe import from remote
```

---

## Part 4: Priority Recommendations

### Immediate Value (Low effort, high impact)

1. **Enhance Guardrails with effectiveness tracking** - Simple addition to existing system
2. **Add external witness to Circuit Breaker** - Improves reliability significantly
3. **Workflow Recipes** - Low complexity, immediate productivity gain

### Medium-Term (Moderate effort, high impact)

4. **Session Checkpointing** - Critical for long-running autonomous sessions
5. **Agent Personas** - Improves task-specific performance
6. **Web Dashboard option** - Remote monitoring capability

### Strategic (High effort, transformational)

7. **Multi-Agent Orchestration** - Major capability expansion
8. **Team Knowledge Base** - Compounds team productivity

### Dependency Graph for New Features

```
Existing Features
      │
      ├── Parallel Development (0.24)
      │         │
      │         ▼
      │   Multi-Agent Orchestration (0.36)
      │
      ├── Guardrails (0.20)
      │         │
      │         ▼
      │   Team Knowledge Base (0.38)
      │
      ├── Circuit Breaker (0.28)
      │         │
      │         ▼
      │   Session Checkpointing (0.37)
      │
      └── None (standalone)
                │
                ├── Agent Personas (0.39)
                └── Workflow Recipes (0.40)
```

---

## References

### Primary Sources
- [Loom](https://github.com/ghuntley/loom) - Rust-based AI coding agent with server-side LLM proxy
- [Gas Town](https://github.com/steveyegge/gastown) - Multi-agent workspace manager
- [Compound Engineering Plugin](https://github.com/EveryInc/compound-engineering-plugin) - Claude Code plugin
- [Compound Engineering Article](https://every.to/chain-of-thought/compound-engineering-how-every-codes-with-agents)

### Secondary Sources
- [Steve Yegge - Welcome to Gas Town](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04)
- [Steve Yegge - The Future of Coding Agents](https://steve-yegge.medium.com/the-future-of-coding-agents-e9451a84207c)
- [Justin Abrahms - Wrapping my head around Gas Town](https://justin.abrah.ms/blog/2026-01-05-wrapping-my-head-around-gas-town.html)

---

## Part 5: Steve Yegge's Specific Techniques

From Yegge's detailed articles, several specific techniques emerge that have direct applicability to cub:

### 5.1 The Rule of Five (Jeffrey Emanuel via Yegge)

> "You get the best designs, the best plans, and the best implementations, all by forcing agents to review their proposals 4-5 times, at which point it converges."

**Application to Cub:**

This directly enhances Plan Review (0.15) and Implementation Review (0.32):

```markdown
## Convergent Review Pattern

Apply 5-pass review at each stage:
1. **Design phase**: 5 passes over the technical design
2. **Planning phase**: 5 passes over the beads implementation plan
3. **Implementation phase**: Code generation + 4 reviews
4. **Testing phase**: 5 passes over tests
5. **Code health**: 5 passes for maintenance

### Implementation
```bash
cub review --passes 5 --stage design
cub review --passes 5 --stage plan
cub run --review-passes 5
```

### Configuration
```json
{
  "review": {
    "convergent_passes": 5,
    "auto_converge": true,
    "converge_signal": "I think this is as good as we can make it"
  }
}
```
```

**Cub Parallel:** The existing `review.strictness` config could be extended with `review.convergent_passes`.

### 5.2 The 40% Code Health Rule

> "If you are vibe coding, you need to spend at least 30-40% of your time, queries, and money on code health."

**Application to Cub:**

This directly informs Codebase Health Audit (0.23.3) and should be a first-class scheduling concern:

```markdown
## Code Health Cadence (from Yegge)

Integrate code health sweeps into the run loop:

### Automatic Health Checks
```bash
cub run --health-ratio 0.4  # 40% of iterations are health checks
```

### Health Sweep Tasks
- Large files needing refactoring
- Low test coverage areas
- Duplicated/redundant systems
- Legacy/dead code
- Poorly-documented code
- Files in wrong locations

### Swarm Health Pattern
1. Run swarm to file beads for all discovered problems
2. Run separate swarm to fix filed beads
3. Repeat until reviews find only nitpicks
```

**Cub Parallel:** The existing Codebase Health Audit spec covers the *what* but not the *when* or *how much*. This provides cadence guidance.

### 5.3 Agent UX / Desire Paths

> "You tell the agent what you want, watch closely what they try, and then implement the thing they tried. Make it real."

**Application to Cub:**

This is a design philosophy that should inform all cub tooling:

```markdown
## Desire Paths Pattern

When agents use cub incorrectly, adapt cub:

### Example: Argument Aliases
If agents consistently try `--body` instead of `--description`:
```bash
# Add alias instead of fighting the behavior
bd create --body "..." # Now works (alias for --description)
```

### Systematic Capture
```bash
# After each run, analyze agent errors
cub analyze --agent-ux

# Output:
# - "Agent tried 'cub task close' 12 times (correct: 'bd close')"
# - "Agent used '--verbose' 8 times (not implemented)"
# - Suggestion: Add 'cub task' alias, add --verbose flag
```
```

**Cub Parallel:** The Runs Analysis spec (0.31) includes "Delegation Gap Analysis" which is similar. This expands it to systematic UX adaptation.

### 5.4 Heresy Detection

> "Agents will often make wrong guesses about how your system is supposed to work. If that wrong guess makes it into the code, it becomes enshrined and other agents may propagate the heresy."

**Application to Cub:**

This is a new concern not currently in any spec:

```markdown
## Heresy Detection (from Gas Town)

Detect and eradicate incorrect beliefs that spread through the codebase:

### Definition
A "heresy" is a plausible-sounding but incorrect assumption that:
1. Gets encoded into code, comments, or docs
2. Spreads to other agents who see it
3. Becomes self-reinforcing

### Examples
- "Idle polecats" (Gas Town) - polecats don't idle, they terminate
- Incorrect API usage patterns
- Wrong assumptions about data flow
- Misunderstood architectural decisions

### Detection Strategies
1. **Core Principles File**: `.cub/principles.md` with architectural truths
2. **Periodic Audits**: Compare code against principles
3. **Pattern Matching**: Detect known heresy patterns in diffs

### Interface
```bash
cub audit --heresies

# Output:
# Found 3 potential heresies:
# - src/auth.ts:42: "tokens expire after 1 hour" (principle: tokens expire after 24h)
# - README.md:15: "run npm start" (principle: use npm run dev)
```

### Integration with Guardrails
When heresy detected and fixed, auto-add to guardrails:
"Do not assume tokens expire after 1 hour - they expire after 24 hours"
```

**Cub Parallel:** This is entirely new. Could be a sub-feature of Codebase Health Audit or a standalone concern.

### 5.5 Crew Cycling vs Polecats (Named vs Ephemeral Workers)

> "Polecats are ephemeral and unsupervised workers... Your Crew are your design team, and they create guzzoline for the swarms."

**Application to Cub:**

This distinction informs multi-agent architecture:

```markdown
## Worker Types (from Gas Town)

### Crew Workers (Named, Long-lived)
- Used for design work, reviews, planning
- Maintain context across sessions
- Human cycles through them for direction
- Create the work that swarms execute

### Polecat Workers (Ephemeral)
- Used for well-defined, spec'd tasks
- Self-destruct after completing work
- No human supervision needed
- Execute work created by Crew

### Cub Application
```bash
# Crew-style work (interactive, design-focused)
cub run --mode crew --workers 5
# Human cycles through workers, gives direction

# Polecat-style work (autonomous, execution-focused)
cub run --mode swarm --workers 10
# Agents work autonomously on well-spec'd beads
```
```

**Cub Parallel:** This distinction could inform how Multi-Agent Orchestration (proposed 0.36) is implemented.

### 5.6 PR Sheriff Pattern (Permanent Standing Orders)

> "One of my Beads crew has a permanent hook: PR Sheriff Standing Orders. On every session startup, the sheriff checks open PRs..."

**Application to Cub:**

This introduces the concept of automated standing orders:

```markdown
## Standing Orders (from Gas Town PR Sheriff)

Automated tasks that run on every session startup:

### Definition
A "standing order" is a bead that:
1. Runs automatically at session start
2. Has a persistent, recognizable ID (e.g., bd-pr-sheriff)
3. Performs routine maintenance or monitoring

### Examples
- **PR Sheriff**: Check and merge easy PRs, flag complex ones
- **Test Watcher**: Run tests, file beads for failures
- **Doc Freshness**: Check for stale documentation
- **Dependency Check**: Look for outdated dependencies

### Interface
```bash
# Create standing order
cub standing-order create "pr-sheriff" \
  --on startup \
  --task "Check open PRs, merge easy wins, flag others"

# List standing orders
cub standing-order list

# Disable temporarily
cub standing-order disable pr-sheriff
```

### Implementation
Standing orders are beads with:
- Special ID prefix (e.g., `bd-standing-*`)
- `hook: startup` trigger
- Auto-re-attach if accidentally unhooked
```

**Cub Parallel:** This could be a new feature that ties into hooks system. Provides automated maintenance.

### 5.7 Software is Throwaway (< 1 Year Shelf Life)

> "For all the code I write, I now expect to throw it away in about a year, to be replaced by something better."

**Application to Cub:**

This philosophical shift has practical implications:

```markdown
## Throwaway-Friendly Architecture

Design for replacement, not permanence:

### Implications for Cub
1. **Test Regeneration**: When tests break after refactoring, regenerate don't fix
   ```bash
   cub run --task "delete all tests and regenerate" --confirm
   ```

2. **Module Isolation**: Keep modules replaceable
   - Clear boundaries
   - Well-defined interfaces
   - No hidden dependencies

3. **Documentation as Code**: Generate docs, don't maintain
   ```bash
   cub run --task "regenerate all documentation from source"
   ```

### Codebase Health Implications
- Dead code deletion is safe (can regenerate if needed)
- Aggressive refactoring is encouraged
- Legacy code has ~1 year grace period before rewrite
```

**Cub Parallel:** This is a mindset shift. The Codebase Health Audit spec should include "regenerate vs repair" guidance.

### 5.8 The Merge Wall Problem

> "When you swarm a task, the workers all start from the same baseline... When the fourth agent D finishes, a rebase may no longer be feasible."

**Application to Cub:**

Critical for Multi-Agent Orchestration design:

```markdown
## Merge Wall Mitigation (from Yegge)

### Problem
Parallel agents create divergent changes that conflict at merge time.

### Strategies

#### 1. Serial Bottleneck Detection
Identify work that should NOT be parallelized:
- Directory restructuring
- Schema changes
- Core API changes

```bash
cub analyze --merge-risk beads-001 beads-002 beads-003
# Output: "beads-002 (schema change) should complete before others"
```

#### 2. Merge Queue with Rebase
```bash
cub swarm --merge-strategy sequential
# Each agent's work is rebased and merged in order
```

#### 3. Conflict Detection Before Merge
```bash
cub swarm --conflict-check
# Pauses if agent's work would conflict with already-merged work
```

#### 4. MapReduce-style Batching
```
Phase 1 (Map): All agents work in parallel
Phase 2 (Reduce): Sequential merge with conflict resolution
```

### Configuration
```json
{
  "swarm": {
    "merge_wall": {
      "pre_check": true,
      "strategy": "sequential",
      "on_conflict": "pause",
      "auto_rebase": true
    }
  }
}
```
```

**Cub Parallel:** This should be a core consideration in Multi-Agent Orchestration spec.

---

## Part 6: Key Insights Summary

### From External Analysis

1. **"Keeping it fed"** (Gas Town) - Multi-agent systems consume plans faster than humans generate them. The Vision-to-Tasks pipeline helps, but may need acceleration.

2. **"80/20 inversion"** (Compound Engineering) - 80% planning/review, 20% execution. Cub's pipeline embodies this but could make it more explicit.

3. **"Git hooks as propulsion"** (Gas Town) - Git-backed persistence enables reliable multi-agent coordination. Cub's beads integration provides similar foundation.

4. **"Compounding productivity"** (Every.to) - Each completed task should make subsequent tasks easier. Guardrails + Knowledge Base achieve this.

5. **"Plate spinning"** (Gas Town user) - Managing multiple agents creates cognitive overload. Good dashboard + coordinator pattern essential.

### From Yegge's Articles

6. **Rule of Five** - Have agents review work 5 times for convergence before trusting output.

7. **40% Code Health** - Spend 40% of time on code health or face compounding technical debt.

8. **Desire Paths** - Design agent UX by watching what agents try, then implement that.

9. **Heresy Detection** - Incorrect beliefs spread through codebases; capture principles to stamp them out.

10. **Crew vs Polecats** - Named workers for design, ephemeral workers for execution.

11. **PR Sheriff** - Standing orders that run automatically at session startup.

12. **Throwaway Software** - Expect < 1 year shelf life; regenerate rather than repair.

13. **Merge Wall** - Parallel work creates merge conflicts; plan for serial bottlenecks.
