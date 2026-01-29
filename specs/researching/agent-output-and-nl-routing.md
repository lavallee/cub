---
status: draft
priority: high
complexity: medium
dependencies: []
blocks: []
created: 2026-01-29
updated: 2026-01-29
readiness:
  score: 6
  blockers:
    - Need to validate --agent output format with real Claude sessions
    - Route optimizer storage/retrieval mechanism needs design
  questions:
    - Should learned routes live in .cub/ or .claude/ ?
    - What's the right threshold for "learned" vs one-off routing?
    - Should the route optimizer feed back into the skill file or stay external?
    - How do we handle route conflicts (user A learns different routes than user B)?
  decisions_needed:
    - Storage format for learned routes (JSONL vs YAML vs JSON)
    - Whether route learning is per-project or global
    - Truncation defaults for --agent output (10 items? 20?)
---

# Agent Output and Natural Language Routing

## Overview

Make cub's CLI output optimized for LLM consumption via an `--agent` flag, and make the `/cub` natural language router self-improving by learning from successful routing patterns. Together, these turn `/cub <natural language>` into a reliable, efficient, and progressively smarter interface to cub's full command surface.

## Goals

- Add `--agent` flag to key CLI commands that produces structured markdown optimized for LLM consumption (token-efficient, pre-analyzed, truncated)
- Create thin passthrough skill files (`.claude/commands/cub:*.md`) for CLI commands that lack skill parity
- Make the `/cub` router invoke commands with `--agent` for better output
- Build a lightweight route learning system so `/cub` gets better at mapping natural language to commands over time
- Keep Claude's ability to interpret and add insight — `--agent` provides structured data, not final prose

## Non-Goals

- Replacing `--json` flag — that's for scripts/APIs, `--agent` is for LLM consumption
- Building an MCP server for cub (future consideration, separate spec)
- Full NLU/intent classification system — routing stays prompt-based with learned examples
- Making `--agent` output human-facing — it's optimized for Claude, humans use default Rich output

## Design / Approach

### Part 1: `--agent` Output Flag

**What it does**: Signals "this output is for an LLM agent." Internally:
1. Computes analysis hints (dependency chains, impact scores, recommendations)
2. Truncates to actionable size (default: 10 items with counts)
3. Renders as structured markdown (headers, tables, bullet analysis)
4. Includes explicit "what's not shown" notices

**Why markdown, not JSON**: Research shows markdown is 34-38% more token-efficient than JSON while maintaining comprehension. It's also what Claude natively reasons about. Tables in markdown are compact and parseable.

**Output structure** (consistent across commands):

```markdown
# <command name>

<one-line summary with key numbers>

## <data section>

| col | col | col |
|-----|-----|-----|
| ... | ... | ... |

<truncation notice if applicable>

## Analysis

- **<insight label>**: <pre-computed insight>
- **Recommendation**: <actionable suggestion>
```

**Commands to support initially**:

| Command | Key analysis hints |
|---------|-------------------|
| `cub task ready` | Impact scores (what each task unblocks), priority ordering |
| `cub task list` | Status distribution, epic grouping |
| `cub task show <id>` | Dependency context, related tasks, epic progress |
| `cub task blocked` | Root blocker identification, chain lengths |
| `cub status` | Trajectory, bottlenecks, quick wins |
| `cub suggest` | Already structured — add compact format |
| `cub ledger show` | Recent completion velocity, cost summary |
| `cub doctor` | Severity classification, fix commands |

**Implementation approach**:

```python
# In each CLI command module
@app.command()
def ready(
    agent: bool = typer.Option(False, "--agent", help="Output optimized for LLM agent"),
    # ...existing flags...
):
    tasks = backend.list_ready_tasks()
    if agent:
        console.print(AgentFormatter.format_ready(tasks, backend))
        return
    # ...existing Rich output...
```

An `AgentFormatter` class (or module) in `cub.core.services` handles:
- Field selection (not full model_dump, just decision-relevant fields)
- Analysis computation (graph traversal for dependencies, impact scoring)
- Markdown rendering with consistent structure
- Truncation with notices

### Part 2: Skill Parity (Passthrough Skills)

Thin `.claude/commands/cub:<name>.md` files for commands that don't have skills yet. Each file:
- Is 10-20 lines
- Maps a small set of NL inputs to subcommand variants
- Runs the command via Bash with `--agent` flag
- Presents results

**Already created on `feature/cub-nl-router` branch**:
- `cub:tasks.md`, `cub:status.md`, `cub:doctor.md`, `cub:suggest.md`
- `cub:ledger.md`, `cub:run.md`, `cub:audit.md`

**Update needed**: These should invoke commands with `--agent` once the flag exists.

### Part 3: `/cub` Router with Route Learning

**Current state**: The `/cub` router (`.claude/commands/cub.md`) uses a static intent routing table. Works for clear matches, but can't improve from experience.

**Route learning mechanism**:

1. **Logging**: After the router executes a command, it appends to `.cub/route-log.jsonl`:
   ```json
   {"ts": "2026-01-29T10:30:00Z", "input": "what are my important tasks", "routed_to": "cub task ready", "type": "cli"}
   {"ts": "2026-01-29T10:31:00Z", "input": "write up a spec on caching", "routed_to": "cub:spec", "type": "skill", "args": "caching"}
   ```

2. **Aggregation**: A periodic step (triggered by `cub update` or a hook) reads the log and produces `.cub/learned-routes.md`:
   ```markdown
   # Learned Routes

   These routes have been used successfully in past sessions.
   Prefer these mappings when the user's input is similar.

   | Phrase pattern | Routed to | Times used |
   |---------------|-----------|------------|
   | "important tasks" / "priority tasks" | `cub task ready` | 12 |
   | "how's the project" / "how are we doing" | `cub status` | 8 |
   | "what did we finish" | `cub ledger show` | 5 |
   ```

3. **Injection**: The router skill file references this learned routes file:
   ```markdown
   ## Learned Routes

   Check @.cub/learned-routes.md for routes that have worked
   in past sessions. Prefer these over the default table when
   the user's phrasing is similar.
   ```

4. **Feedback signal**: The key question is how to know a route was "successful." Options:
   - **Implicit**: If the user doesn't re-invoke `/cub` with a different phrasing within 2 messages, the route was probably right
   - **Explicit**: The router asks "Was that what you were looking for?" (noisy, bad UX)
   - **Conservative**: Just log everything, weight by frequency. Frequently-used routes are probably correct.

   **Recommendation**: Start with frequency-based (option 3). Simple, no UX friction, self-correcting over time since bad routes won't be repeated.

**Where learning lives**:
- `.cub/route-log.jsonl` — raw log (append-only, gitignored)
- `.cub/learned-routes.md` — aggregated patterns (committed, shared with team)

This means team members benefit from each other's routing patterns when they pull.

### How the pieces connect

```
User: /cub what are my important tasks?
  │
  ▼
Router skill loads (.claude/commands/cub.md)
  │
  ├─ Checks learned routes (@.cub/learned-routes.md)
  │   → "important tasks" maps to `cub task ready` (used 12x)
  │
  ├─ Falls back to static routing table if no learned match
  │
  ▼
Executes: cub task ready --agent
  │
  ▼
CLI produces structured markdown with analysis
  │
  ▼
Claude interprets, adds insight, presents to user
  │
  ▼
Router logs: {"input": "important tasks", "routed_to": "cub task ready"}
```

## Implementation Notes

### AgentFormatter location

`src/cub/core/services/agent_format.py` — a new module in the service layer.

Key methods:
- `format_tasks(tasks, context)` — for task list commands
- `format_status(stats)` — for status command
- `format_suggestions(suggestions)` — for suggest command
- `format_diagnostic(results)` — for doctor command

Each method:
1. Selects relevant fields from the Pydantic models
2. Computes analysis (using existing service layer data — dependency graphs, completion stats)
3. Renders markdown string
4. Applies truncation with notices

### Route logging

The router skill instructs Claude to log routes via a simple Bash append:

```markdown
After executing a command, log the route:
echo '{"ts":"<now>","input":"<user input>","routed_to":"<command>"}' >> .cub/route-log.jsonl
```

This is zero-infrastructure — no Python needed, no daemon, just a file append.

### Route aggregation

`cub routes compile` (new command) reads `route-log.jsonl`, groups by `routed_to`, extracts common phrases, and writes `learned-routes.md`. Could run as part of `cub update` or on a hook.

### Token budget

Target: `--agent` output should be under 500 tokens for typical commands. This leaves room for Claude to add 200-300 tokens of interpretation without bloating context.

Measurement approach: use `tiktoken` or character-count heuristic (1 token ≈ 4 chars) during development to validate.

## Open Questions

1. **Should learned routes be per-project or global?** Per-project means each project develops its own vocabulary. Global means cross-project learning. Recommendation: per-project (in `.cub/`), but could support global later (in `~/.cub/`).

2. **Route conflict resolution**: If two users on the same team learn different routes for the same phrase, frequency wins. The aggregation step merges by highest count.

3. **Route decay**: Should old routes lose weight over time? Probably not initially — keep it simple, revisit if stale routes become a problem.

4. **How to handle the logging step in the skill**: The router needs to append to the log after execution. This means the skill file instructs Claude to do a Bash echo append. This is reliable but depends on Claude following the instruction. Alternative: a PostToolUse hook that detects `/cub` invocations and logs automatically.

## Future Considerations

- **MCP server**: Expose `--agent` formatted output as MCP tool results with `structuredContent` for richer client integration
- **LLM-assisted aggregation**: Use an LLM call during `cub routes compile` to cluster similar phrases and generate canonical patterns
- **A/B route testing**: When multiple routes seem plausible, try the most common one and track whether the user re-routes
- **Skill auto-generation**: Generate passthrough skill files from Typer command metadata during `cub update`

---

**Status**: draft
**Last Updated**: 2026-01-29
