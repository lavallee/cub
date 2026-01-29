---
status: draft
priority: high
complexity: medium
dependencies:
  - cub-task-parity
blocks: []
created: 2026-01-29
updated: 2026-01-29
readiness:
  score: 7
  blockers:
    - DependencyGraph class does not exist yet — needed for analysis hints on task commands
  questions:
    - Should route learning be a separate spec/phase to keep this shippable?
  decisions_needed:
    - Truncation defaults for --agent output (10 items recommended based on research)
    - Whether to ship analysis hints as a fast-follow or gate on them
---

# Agent Output and Natural Language Routing

## Overview

Make cub's CLI output optimized for LLM consumption via an `--agent` flag, and upgrade the `/cub` natural language router to use this output. The `--agent` flag produces structured markdown that is 34-38% more token-efficient than JSON, includes pre-computed analysis hints so Claude doesn't have to derive insights from raw data, and truncates to actionable size.

This spec covers three separable pieces that can ship incrementally:
1. **`--agent` output flag** — Python engineering, core value
2. **Passthrough skills** — already done on `feature/cub-nl-router`
3. **Route learning** — research/UX, can ship independently

## Goals

- Add `--agent` flag to key CLI commands producing structured markdown optimized for LLM consumption
- Pre-compute analysis hints (dependency impact, bottlenecks, recommendations) so Claude echoes accurate insights rather than guessing
- Keep output under ~500 tokens per command to leave room for Claude's interpretation
- Make the `/cub` router invoke commands with `--agent` for better output
- Maintain Claude's role as interpreter — `--agent` provides structured data and hints, not final prose

## Non-Goals

- Replacing `--json` flag — that serves scripts/APIs, `--agent` serves LLM consumption
- Building an MCP server for cub (future consideration, separate spec)
- Full NLU/intent classification — routing stays prompt-based with learned examples
- Velocity/trajectory/ETA computation — requires time-series data we don't collect yet
- Effort estimation for tasks — no complexity signal exists in task data currently

## Design / Approach

### Part 1: `--agent` Output Flag

#### Why markdown, not JSON

Research findings (sources: Improving Agents, Axiom MCP, Checksum.ai):
- Markdown uses 34-38% fewer tokens than JSON for equivalent data
- Claude comprehends markdown tables natively without parsing overhead
- CSV/TSV tables are 29% more compact than JSON arrays of objects
- Deep JSON nesting causes parsing issues; markdown tables are flat

#### Output structure (consistent envelope)

Every `--agent` output follows this template:

```
# <command name>

<one-line summary with key numbers>

## <primary data section>

| col | col | col |
|-----|-----|-----|
| ... | ... | ... |

Showing N of M. Use --all for complete list.

## Analysis

- **<insight label>**: <pre-computed insight>
- **Recommendation**: <actionable suggestion>
```

Properties:
- **Summary line first**: Claude can echo this directly as a response opener
- **Tables for lists**: Compact, parseable, scannable
- **Truncation notice**: Explicit about what's hidden (research shows this prevents confabulation)
- **Analysis section**: Pre-computed insights Claude should treat as informational, not authoritative. Claude adds its own interpretation.

#### Concrete output examples

**`cub task ready --agent`** (~180 tokens):
```
# cub task ready

3 tasks ready to work on. 18 blocked across 5 dependency chains.

## Ready Tasks

| ID | Title | Pri | Blocks |
|----|-------|-----|--------|
| cub-r6s.1 | Define InstructionConfig model | P1 | 3 tasks |
| cub-r4h.1 | Implement clean exit handler | P0 | 2 tasks |
| cub-iyk | Foundation: test isolation fixes | P1 | 1 task |

## Analysis

- **Highest impact**: cub-r6s.1 unblocks 3 downstream tasks (r6s.2, r6s.3, r6s.6)
- **Highest priority**: cub-r4h.1 is P0, unblocks r4h.2 then r4h.3
- **Recommendation**: Start with cub-r6s.1 — unblocks the most work
```

**`cub status --agent`** (~200 tokens):
```
# cub status

42 tasks: 24 closed (57%), 3 in progress, 15 open. 18 blocked, 3 ready.

## Breakdown

| Status | Count | Pct |
|--------|-------|-----|
| Closed | 24 | 57% |
| In Progress | 3 | 7% |
| Ready | 3 | 7% |
| Blocked | 18 | 43% |

## Epics

| Epic | Progress | Ready | Blocked |
|------|----------|-------|---------|
| cub-r4h | 0/3 | 1 | 2 |
| cub-r5c | 0/3 | 1 | 2 |
| cub-r6s | 0/6 | 1 | 3 |

## Analysis

- **Bottleneck**: 3 root blockers (cub-r4h.1, cub-r5c.1, cub-r6s.1) gate all 18 blocked tasks
- **Quick win**: cub-r6s.1 is P1, ready, and unblocks the longest chain (3 tasks)
```

**`cub task show cub-r6s.1 --agent`** (~250 tokens):
```
# cub task show cub-r6s.1

## Define InstructionConfig model

- **Priority**: P1
- **Status**: open
- **Epic**: cub-r6s (Instruction Generation)
- **Type**: task

## Description

Define the Pydantic model for instruction configuration...
(first 500 chars of description, truncated if longer)

## Dependencies

- **Blocks**: cub-r6s.2 (Implement InstructionGenerator), cub-r6s.3, cub-r6s.6
- **Blocked by**: none (ready to work)
- **Epic progress**: 0/6 tasks complete

## Analysis

- **Context**: This is the foundation task for the instruction generation epic. All other tasks in cub-r6s depend on it.
- **Recommendation**: Claim and start — nothing blocks this.
```

**`cub task blocked --agent`** (~300 tokens for 18 tasks):
```
# cub task blocked

18 tasks blocked. 3 root blockers control all dependency chains.

## Root Blockers (resolve these to unblock the most work)

| Blocker | Title | Pri | Unblocks |
|---------|-------|-----|----------|
| cub-r6s.1 | Define InstructionConfig model | P1 | 3 tasks |
| cub-r4h.1 | Implement clean exit handler | P0 | 2 tasks |
| cub-r5c.1 | Define stagnation detection interface | P0 | 2 tasks |

## Dependency Chains

- cub-r6s.1 -> r6s.2 -> r6s.3, also r6s.6
- cub-r4h.1 -> r4h.2 -> r4h.3
- cub-r5c.1 -> r5c.2 -> r5c.3
- cub-iyk -> 6jpc -> e2h9 -> ck1z -> i8b6

Showing 4 longest chains of 5 total.

## Analysis

- **Critical path**: cub-iyk chain is 5 tasks deep — longest in the project
- **Recommendation**: Resolve cub-r6s.1 (unblocks most) and cub-r4h.1 (highest priority) first
```

**`cub doctor --agent`** (~150 tokens):
```
# cub doctor

2 issues found: 1 warning, 1 info.

## Issues

| Severity | Check | Status | Fix |
|----------|-------|--------|-----|
| warning | Hooks installed | cub-hook.sh not executable | `chmod +x .cub/scripts/hooks/cub-hook.sh` |
| info | Beads migration | Legacy database detected | `bd migrate --update-repo-id` |

## Analysis

- **Action needed**: Run the chmod command to fix hook execution. The beads migration is optional but recommended.
```

**`cub suggest --agent`** (~150 tokens):
```
# cub suggest

3 recommendations based on current project state.

## Suggestions

| Priority | Action | Target | Rationale |
|----------|--------|--------|-----------|
| 1 | Unblock work | cub-r6s.1 | P1, unblocks 3 tasks in instruction generation epic |
| 2 | Unblock work | cub-r4h.1 | P0, unblocks exit scenario chain |
| 3 | Fix config | hooks | cub-hook.sh not executable, hooks won't fire |
```

**`cub ledger show --agent`** (~200 tokens):
```
# cub ledger show

12 ledger entries. Last completion: 2026-01-28.

## Recent Completions

| Date | Task | Title | Cost |
|------|------|-------|------|
| Jan 28 | cub-k41.3 | Migrate legacy harnesses to async | $0.42 |
| Jan 27 | cub-k41.2 | Add async backend protocol | $0.31 |
| Jan 27 | cub-k41.1 | Define async harness interface | $0.18 |

Showing 3 most recent of 12 total.

## Analysis

- **Recent velocity**: 3 tasks in 2 days (cub-k41 epic)
- **Total cost**: $4.82 across 12 completions
- **Average cost per task**: $0.40
```

#### Service layer data availability

Audit of what exists vs. what's needed for the analysis hints above:

| Analysis hint | Data source | Exists? | Gap |
|---------------|-------------|---------|-----|
| Direct blocks count | `Task.blocks` field | Yes | None |
| Transitive unblock count | Dependency graph traversal | **No** | Need `DependencyGraph` class |
| Root blocker identification | Reverse dependency index | **No** | Need `DependencyGraph` class |
| Dependency chain listing | Graph walk | **No** | Need `DependencyGraph` class |
| Task counts by status | `StatusService.summary()` | Yes | None |
| Epic progress | `StatusService.progress()` | Yes | None |
| Suggestion ranking | `SuggestionService` | Yes | Minor: needs `--agent` format |
| Ledger recent entries | `LedgerService.query()` | Yes | None |
| Ledger cost/stats | `LedgerService.stats()` | Yes | None |
| Doctor diagnostics | `doctor` command output | Yes | Needs structured return, not just prints |
| Velocity/trajectory | Time-series data | **No** | Out of scope — would need historical snapshots |

**The critical gap is `DependencyGraph`**: a class that builds a bidirectional graph from the task list and answers "what does closing this task unblock?" This is needed for the most valuable analysis hints (impact scoring, root blockers, chain listing).

#### DependencyGraph design

New module: `src/cub/core/tasks/graph.py`

```python
class DependencyGraph:
    """Bidirectional dependency graph built from a task list."""

    def __init__(self, tasks: list[Task]) -> None:
        """Build forward (depends_on) and reverse (blocks) edges."""

    def direct_unblocks(self, task_id: str) -> list[str]:
        """Tasks that would become unblocked if this task closes."""

    def transitive_unblocks(self, task_id: str) -> set[str]:
        """All tasks transitively unblocked (recursive)."""

    def root_blockers(self, limit: int = 5) -> list[tuple[str, int]]:
        """Tasks that transitively block the most work, sorted desc.
        Returns (task_id, unblock_count) tuples."""

    def chains(self, limit: int = 5) -> list[list[str]]:
        """Longest dependency chains, sorted by length desc."""

    def would_become_ready(self, task_id: str) -> list[str]:
        """Tasks that would become ready (all deps satisfied) if this closes.
        More precise than transitive_unblocks — checks ALL deps, not just this one."""
```

This is a pure function over the task list — no persistence, no side effects, no backend coupling. Build it once per `--agent` invocation (task lists are small, <500 items).

#### AgentFormatter design

New module: `src/cub/core/services/agent_format.py`

```python
class AgentFormatter:
    """Renders command output as structured markdown for LLM consumption.

    Design principles:
    - Summary line first (Claude can echo directly)
    - Tables for lists (compact, parseable)
    - Truncation with explicit notices
    - Analysis section with pre-computed hints
    - Target: <500 tokens per output
    """

    @staticmethod
    def format_ready(tasks: list[Task], graph: DependencyGraph) -> str: ...

    @staticmethod
    def format_blocked(tasks: list[Task], graph: DependencyGraph) -> str: ...

    @staticmethod
    def format_task_detail(task: Task, graph: DependencyGraph, epic_progress: EpicProgress | None) -> str: ...

    @staticmethod
    def format_status(stats: ProjectStats) -> str: ...

    @staticmethod
    def format_suggestions(suggestions: list[Suggestion]) -> str: ...

    @staticmethod
    def format_ledger(entries: list[LedgerEntry], stats: LedgerStats) -> str: ...

    @staticmethod
    def format_doctor(checks: list[DiagnosticCheck]) -> str: ...
```

Each method:
1. Selects decision-relevant fields (not full model_dump)
2. Receives pre-built `DependencyGraph` when dependency analysis is relevant
3. Renders markdown string following the envelope template
4. Applies truncation (default: 10 items) with "Showing N of M" notice

#### How Claude should treat analysis hints

The `## Analysis` section is informational, not authoritative. The skill files should instruct Claude:

```
Present the data from the command output. The Analysis section contains
pre-computed insights — use them as a starting point for your response,
but apply your own judgment. If the recommendation doesn't make sense
given what the user asked, say so.
```

This prevents Claude from blindly echoing a bad recommendation (e.g., "start with cub-r6s.1" when the user just asked about a different epic).

#### Commands to support (phased)

**Phase 1** (core value, ship first):
- `cub task ready --agent`
- `cub task show <id> --agent`
- `cub status --agent`
- `cub suggest --agent`

These four cover the most common `/cub` routing targets and have all data available today (task ready and show need DependencyGraph; status and suggest use existing services).

**Phase 2** (requires `cub task blocked` from parity spec):
- `cub task blocked --agent`
- `cub task list --agent`
- `cub ledger show --agent`

**Phase 3** (needs doctor refactor):
- `cub doctor --agent` (currently prints directly, needs structured return)
- `cub audit --agent`

### Part 2: Skill Parity (Passthrough Skills)

**Done.** Seven passthrough skills created on `feature/cub-nl-router`:
`cub:tasks`, `cub:status`, `cub:doctor`, `cub:suggest`, `cub:ledger`, `cub:run`, `cub:audit`

**Pending update**: Once `--agent` flag exists, update these skills to include `--agent` in their Bash invocations. Example change in `cub:tasks.md`:

```diff
- | (empty) / "ready" | `cub task ready` |
+ | (empty) / "ready" | `cub task ready --agent` |
```

### Part 3: Route Learning

**This is separable and should ship after Parts 1 and 2 are validated.**

The core question: how does `/cub` get better at routing over time?

#### Mechanism

1. **Logging**: After the router executes a command, append to `.cub/route-log.jsonl`:
   ```json
   {"ts": "2026-01-29T10:30:00Z", "input": "what are my important tasks", "routed_to": "cub task ready", "type": "cli"}
   ```

2. **Aggregation**: `cub routes compile` (or a hook) reads the log, groups by `routed_to`, extracts common phrases, writes `.cub/learned-routes.md`:
   ```markdown
   # Learned Routes
   Prefer these mappings when the user's input is similar.

   | Phrase pattern | Routed to | Times used |
   |---------------|-----------|------------|
   | "important tasks" / "priority tasks" | `cub task ready` | 12 |
   | "how's the project" | `cub status` | 8 |
   ```

3. **Injection**: The router skill references `@.cub/learned-routes.md` and prefers learned routes over the static table when phrasing is similar.

#### Reliability concern

The logging step depends on Claude following a skill instruction to run a Bash echo append. Research shows skill instruction adherence is 50-84%. Two mitigations:

- **Primary**: Use a `PostToolUse` hook on Bash that detects `cub task|cub status|cub suggest|...` invocations originating from a `/cub` session and logs automatically. This is deterministic — no LLM adherence needed.
- **Fallback**: Instruct Claude in the skill to log. If it sometimes doesn't, the data is incomplete but not wrong (frequency counts are lower bounds).

**Decision**: Use the hook-based approach. The existing symbiotic workflow hook infrastructure (`cub-hook.sh`) already detects Bash tool uses and can be extended to recognize `/cub`-originated commands.

#### Feedback signal

How do we know a route was "successful"?

**Chosen approach**: Frequency-based (conservative). Log every route, weight by count. Rationale:
- No UX friction (no "was that right?" prompts)
- Self-correcting: bad routes won't be repeated, so their counts stay low
- Simple: no implicit signal detection needed

Routes with count < 3 are excluded from `learned-routes.md` to avoid noise from one-off queries.

#### Where learning lives

| File | Purpose | Git tracked? |
|------|---------|-------------|
| `.cub/route-log.jsonl` | Raw append-only log | No (gitignored) |
| `.cub/learned-routes.md` | Aggregated patterns | Yes (shared with team) |

Team members benefit from each other's routing patterns when they pull. The raw log stays local since it's high-volume and user-specific.

## Implementation Notes

### Token budget

Target: `--agent` output should be under 500 tokens for typical commands (~2000 chars). This leaves room for Claude to add 200-300 tokens of interpretation without bloating the conversation context.

Measurement: use character count heuristic (1 token ≈ 4 chars for English/markdown) during development. The concrete examples above range from 150-300 tokens, well within budget.

### Interaction with existing --json flag

`--agent` and `--json` are mutually exclusive. If both are passed, `--agent` wins (it's a superset: structured + analyzed). Implementation:

```python
if agent:
    console.print(AgentFormatter.format_ready(tasks, graph))
    return
if json_output:
    console.print(json.dumps([t.model_dump(mode="json") for t in tasks]))
    return
# default Rich output...
```

### Testing strategy

1. **Unit tests for AgentFormatter**: Each format method gets snapshot tests comparing output against expected markdown strings. Test with 0, 1, 10, and 50+ items to verify truncation.
2. **Unit tests for DependencyGraph**: Test with known graph topologies (linear chain, diamond, forest, cycle).
3. **Integration test**: Run `cub task ready --agent` end-to-end and verify output matches the envelope template.
4. **Token budget test**: Assert character count < 2000 for representative inputs.

### Validation plan

Before shipping, validate with 10+ real `/cub` invocations in Claude Code:
1. Does Claude parse the markdown correctly?
2. Does Claude echo the summary and add its own insight (not just parrot)?
3. Does Claude respect the analysis hints without blindly trusting them?
4. Is the output compact enough that follow-up conversation doesn't feel bloated?

Document results in a validation log. If Claude struggles with any format element, adjust before merging.

## Open Questions

1. **Should route learning be a separate spec?** It's separable and has different risk profile (UX/research vs engineering). Could be its own spec to keep this one shippable.

2. **Truncation defaults**: Research suggests 10 items with counts. But some commands (like `task blocked` with 18 items) might benefit from showing all if under 20. Threshold: show all if ≤ 15, truncate to 10 with notice if > 15?

## Future Considerations

- **MCP server**: Expose `--agent` formatted output as MCP tool results with `structuredContent` for richer client integration
- **Velocity/trajectory analysis**: Once we collect time-series data (historical snapshots of task counts), add to status `--agent` output
- **Skill auto-generation**: Generate passthrough skill files from Typer command metadata during `cub update`
- **LLM-assisted route aggregation**: Use an LLM call during `cub routes compile` to cluster similar phrases into canonical patterns

---

**Status**: draft
**Last Updated**: 2026-01-29
