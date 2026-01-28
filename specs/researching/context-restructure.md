---
status: researching
priority: high
complexity: high
dependencies:
  - Ledger system (existing, used for retry context)
blocks:
  - symbiotic-workflow (hooks depend on clean context stack)
created: 2026-01-28
updated: 2026-01-28
readiness:
  score: 7
  blockers:
    - cub map static analysis heuristics need design
    - Demarcation edge cases (partial marker deletion, format migration)
  questions:
    - Should cub map include ledger/forensics data for existing projects?
    - What token budget should map.md target?
    - Should we generate copilot-instructions.md alongside AGENTS.md?
  decisions_needed:
    - Final naming for the runloop prompt file
    - What content from existing progress.txt files (if any) is worth preserving
  tools_needed:
    - py-tree-sitter (Python bindings for tree-sitter)
    - tree-sitter language grammars (Python, JS/TS, Rust, Go, etc.)
---

# Context Restructure: Prompt Composition and Delivery

## Overview

Restructure how cub composes and delivers context to AI coding agents across
both interactive sessions and autonomous (`cub run`) operation. The goal is
context parity between modes, clean separation of concerns, and clear
documentation so users know where to make changes to agent behavior.

Today, cub's context system has overlapping files with unclear ownership
(PROMPT.md, AGENT.md, AGENTS.md, CLAUDE.md, progress.txt, guardrails.md,
fix_plan.md), no auto-generated project understanding, no operating principles,
and a destructive init that can't coexist with user-authored content. This spec
addresses all of these.

## Problem

### Fragmented context files

Cub currently generates or templates seven context-adjacent files with unclear
boundaries:

| File | Role | Problem |
|------|------|---------|
| `templates/PROMPT.md` | System prompt for `cub run` | Mixes ralph-loop behavior with project references and generic coding advice |
| `templates/AGENT.md` | Project build/test instructions | 100% placeholder; no auto-generation |
| `AGENTS.md` (generated) | Cub workflow for direct sessions | 90+ lines, mostly task management commands |
| `CLAUDE.md` (generated) | Claude-specific additions | Mostly "see AGENTS.md" |
| `progress.txt` | Session learnings | Append-only dump; 750KB+ across 3 copies in this repo |
| `.cub/guardrails.md` | Institutional memory | Mostly empty; unclear relationship to progress.txt |
| `templates/fix_plan.md` | Tech debt tracker | Confused role: project-level debt vs. task-retry context |

### No project understanding

No auto-generated map of the codebase. Every session starts cold unless someone
hand-wrote an AGENT.md. The symbiotic workflow spec envisions SessionStart hooks
injecting project context, but there's nothing to inject.

### No operating principles

Nothing guides *how* to think about changes. Agents get workflow commands (how
to close a task) but no philosophical framework (what makes a change good).

### Destructive init

`cub init` either overwrites AGENTS.md/CLAUDE.md entirely or skips them. It
can't merge with existing user content. This is hostile to projects that already
have their own CLAUDE.md.

### No task context enrichment

`generate_task_prompt()` includes only the single task. An agent working on task
3 of 12 has no idea what tasks 1-2 accomplished or what 4-12 will need. Failed
task retries have no memory of what went wrong.

## Goals

- **Context parity** between interactive sessions and `cub run` sessions: both
  modes get project understanding, operating principles, and cub integration
- **Clear file ownership**: every file has one purpose, one owner, and one place
  to make changes; documented so users understand the composition
- **Non-destructive init**: cub manages a demarcated region within AGENTS.md and
  CLAUDE.md without touching user content
- **Auto-generated project map** via `cub map` (static analysis, no LLM)
- **Shipped default constitution** with journalistic principles for product
  development
- **Enriched task prompts** with epic context, sibling awareness, and
  previous-attempt failure context
- **Elimination of file sprawl**: consolidate progress.txt, guardrails.md, and
  fix_plan.md into the ledger and constitution

## Non-Goals

- **Hook-based tracking** from the symbiotic workflow spec (this spec is a
  prerequisite for that work, not an implementation of it)
- **LLM-powered map generation** (tree-sitter static analysis + PageRank is
  in scope; LLM-assisted descriptions are not)
- **Migrating existing progress.txt content** into the ledger (delete, don't
  migrate; the content is too noisy to be useful)
- **Restructuring the ledger itself** (this spec uses the ledger for retry
  context but doesn't change how it works)
- **Generating copilot-instructions.md or .cursorrules** (future consideration)
- **Real-time context injection** (that's symbiotic workflow Phase 1)

## Design / Approach

### New File Architecture

```
project/
  AGENTS.md              # Shared space (user + cub managed section)
  CLAUDE.md              # Shared space (user + cub managed section)
  .cub/
    map.md               # Auto-generated project map (cub map)
    constitution.md      # Operating principles (shipped default, user-customizable)
    runloop.md           # Ralph-loop system prompt (cub run only)
```

### Layer 1: Demarcated Managed Sections

AGENTS.md and CLAUDE.md become shared spaces. Cub owns a clearly marked region:

```markdown
(user's existing content, untouched)

<!-- BEGIN CUB MANAGED SECTION v1 -->
<!-- Do not edit this section. Run `cub update` to refresh. -->
<!-- To customize cub behavior, add your overrides OUTSIDE this section. -->

## Cub Integration

(condensed task workflow: find, claim, complete)
(references to .cub/map.md and .cub/constitution.md)

<!-- END CUB MANAGED SECTION -->
```

**Behavior:**
- `cub init`: if file exists, append managed section (or replace existing
  managed section). If file doesn't exist, create with managed section only.
- `cub update`: find and replace content between markers. Bump version if
  template changed.
- User content outside markers is never touched.
- Version in marker (`v1`) tracks template format, enabling `cub update` to
  know when regeneration is needed.

**AGENTS.md** gets the vendor-neutral content (task commands, project map
reference, constitution reference). This aligns with the AGENTS.md standard
(Linux Foundation / AAIF, 60k+ repos, supported by all major coding tools).

**CLAUDE.md** gets the same managed section plus Claude-specific additions
(plan mode integration, skills references if applicable).

### Layer 2: `.cub/map.md` (Auto-Generated Project Map)

New command: `cub map`

**What it generates (static analysis):**
- Directory tree with annotations (depth-limited, respects .gitignore)
- Tech stack detection from config files (pyproject.toml, package.json,
  Cargo.toml, go.mod, etc.)
- Entry points and build/test/lint commands (extracted from config)
- Key files listing (by convention: README, main entry points, config files)
- Module structure (top-level packages/directories with brief descriptions)

**What it reads:**
- File system structure
- Package manager config files
- Existing .cub/ metadata (ledger stats, task counts) for project health context

**Called by:**
- `cub init` (initial generation)
- `cub update` (refresh)
- `cub map` (manual invocation)

**Referenced from** the managed section of AGENTS.md/CLAUDE.md so any session
(interactive or `cub run`) can read it via `@.cub/map.md`.

**Token budget target:** ~1500 tokens (configurable via `cub map --tokens N`).
Enough to orient with meaningful code intelligence, not enough to overwhelm.

**Code intelligence via tree-sitter:** Following Aider's repo map approach,
`cub map` uses tree-sitter to parse source files and extract structural
information:

1. **Parse**: tree-sitter parses all source files into ASTs
2. **Extract**: Pull function, class, and method signatures (definitions only,
   no implementation bodies)
3. **Graph**: Build a dependency graph where files are nodes and cross-file
   references (imports, calls) are edges
4. **Rank**: Apply PageRank to identify the most structurally important symbols
   (the "hub" files and functions everything depends on)
5. **Budget**: Select top-ranked symbols that fit within the token budget

This gives every session a ranked view of "here are the 50 most important
functions/classes in your codebase and how they relate" — dramatically more
useful than a directory tree alone.

**Dependencies:** `py-tree-sitter` plus language grammar packages
(tree-sitter-python, tree-sitter-javascript, tree-sitter-typescript, etc.).
These are well-maintained and widely used (Aider, Repomix, various MCP servers
all use tree-sitter).

**Graceful degradation:** If tree-sitter parsing fails for a language (missing
grammar, parse error), fall back to the structural layer (directory tree +
config detection). The map should always produce useful output.

**Future enhancement path:** Repomix `--compress` integration as an alternative
extraction backend, LLM-assisted module descriptions, dynamic token budgeting
based on context window size.

### Layer 3: `.cub/constitution.md` (Operating Principles)

Shipped with a default constitution (already drafted in `templates/constitution.md`)
focused on journalistic principles for product development:
- Serve, don't extract
- Earn attention, never manipulate it
- Verify before you ship
- Be honest about what you don't know
- Build for the person who can't afford to get it wrong

**Behavior:**
- `cub init`: copies default to `.cub/constitution.md` if it doesn't exist
- `cub update`: does NOT overwrite (user may have customized)
- Referenced from managed section so all sessions pick it up

This is distinct from code style or architectural rules (which belong in
AGENTS.md directly). The constitution guides *product thinking*, not syntax.

### Layer 4: `.cub/runloop.md` (Autonomous Operation Prompt)

Renamed from `PROMPT.md`. Moved to `.cub/`. Stripped to pure ralph-loop behavior:

- Work on one task at a time
- Understand → search → implement → validate → complete cycle
- Signal `<stuck>` when blocked
- Signal `<promise>COMPLETE</promise>` when all tasks done
- Run feedback loops before closing
- Escape hatch semantics

**Removed from this file:**
- Project context references (`@AGENT.md`, `@specs/*`) — now in CLAUDE.md
  managed section
- Generic coding advice (search before writing, no placeholders) — now in
  constitution
- Progress.txt references — eliminated

This file is unlikely to need human editing. It's the behavioral contract
between cub's run loop and the harness.

### Layer 5: Enriched Task Prompts

`generate_task_prompt()` gains epic and sibling context:

```markdown
## CURRENT TASK

Task ID: {id}
Type: {type}
Title: {title}

Description:
{description}

Acceptance Criteria:
- {criteria}

## EPIC CONTEXT

Epic: {epic_id} - {epic_title}
{epic_description, truncated to ~200 words}

Completed tasks in this epic:
- {id}: {title} (one line each, most recent first)

Remaining tasks after this one:
- {id}: {title} (titles only, for awareness)

## PREVIOUS ATTEMPT (only present on retry)

This task was attempted before and did not succeed.
Failure reason: {from ledger entry}
Key observations: {from ledger entry}
Avoid repeating: {specific mistakes extracted from previous attempt}

## Task Management

{backend-specific close instructions}

## When Complete

1. Run feedback loops (typecheck, test, lint)
2. Mark the task complete
3. Commit: `{type}({task_id}): {title}`
```

The epic context section is curated, not dumped. Completed siblings tell the
agent what's already done (don't repeat). Remaining siblings provide directional
awareness (don't paint into a corner). The current task stays front and center.

**Previous attempt context** replaces the durable `fix_plan.md`. When a task
fails, the ledger captures what happened. On retry, `generate_task_prompt()`
pulls failure context from the ledger and injects it directly. This is
ephemeral (per-task, per-attempt), not a project-level file.

### Layer 6: Eliminations

**progress.txt**: Eliminated. The instruction "append learnings to progress.txt"
is removed from all templates and prompts. Task-specific learnings are captured
in ledger entries. Durable project insights are promoted to the constitution by
humans. The existing 750KB+ files are deleted (no migration — the content is
append-only noise, not curated knowledge).

**guardrails.md**: Eliminated. Its intended role (institutional memory from
failures) is served by the constitution (curated principles) + ledger (failure
records) + previous-attempt injection (retry context).

**fix_plan.md**: Eliminated as a durable template. Its tech debt tracking role
is served by beads issues with appropriate labels. Its task-repair role is
served by previous-attempt injection from the ledger.

**AGENT.md template**: Replaced by auto-generated `.cub/map.md`. The template's
placeholder-heavy approach is replaced by actual static analysis.

### Context Composition Summary

```
Interactive session (Claude Code, Codex, etc.):
  CLAUDE.md / AGENTS.md (auto-read by harness)
    └── managed section references:
        ├── .cub/map.md (project understanding)
        └── .cub/constitution.md (operating principles)
    └── inline: cub task workflow (condensed)

cub run session:
  CLAUDE.md / AGENTS.md (auto-read by Claude Code)
    └── (same as above)
  + --append-system-prompt: .cub/runloop.md
    └── ralph-loop behavior only
  + stdin: task prompt
    └── task details + acceptance criteria
    └── epic context + sibling awareness
    └── previous attempt context (if retry)
    └── task closure instructions
```

Both modes get project understanding, operating principles, and cub integration.
The `cub run` mode adds autonomous behavior instructions and task-specific
context.

### Verified Assumptions

- **`@` references resolve in pipe mode**: Tested and confirmed. `claude -p
  --append-system-prompt "Read @file.md..."` correctly resolves `@` references.
  This means the managed section's references to `.cub/map.md` and
  `.cub/constitution.md` work in both interactive and `cub run` contexts.

- **CLAUDE.md is auto-read in both modes**: Claude Code reads CLAUDE.md from
  the working directory regardless of how it's invoked. This is the foundation
  for context parity.

## Implementation Notes

### Phase 1: Foundation (demarcation + runloop + constitution)

- Implement marker-based section management in `instructions.py`
  - Find markers, replace between them, preserve surrounding content
  - Handle missing markers (first init), partial markers (error + recover),
    version mismatches (warn + replace)
- Rename PROMPT.md to `.cub/runloop.md`, strip non-loop content
- Ship `templates/constitution.md` as default (already drafted)
- Update `cub init` to use demarcated sections
- Add `cub update` command for refreshing managed sections

### Phase 2: Project Map

- Implement `cub map` command
- **Structural layer** (always available):
  - Directory tree with annotations (depth-limited, respects .gitignore)
  - Tech stack detection from config files (pyproject.toml, package.json,
    Cargo.toml, go.mod, Makefile, Dockerfile, etc.)
  - Build/test/lint command extraction from config
  - Key file listing (README, main entry points, test directories)
  - Module structure (top-level packages with brief descriptions)
- **Code intelligence layer** (tree-sitter):
  - Parse source files using py-tree-sitter with language grammar packs
  - Extract function, class, and method signatures (definitions without bodies)
  - Build cross-file reference graph (what imports/calls what)
  - Apply PageRank to surface the most structurally important symbols
  - Budget output to a configurable token limit (default ~1500 tokens)
  - Include ranked symbols in map with file locations
- **Existing project enrichment**:
  - Ledger stats (task completion rates, attempt counts) if available
  - Common patterns and conventions detected from code
- Wire into `cub init` and `cub update`
- Add `py-tree-sitter` and language grammar packages to dependencies

### Phase 3: Task Prompt Enrichment

- Add epic context to `generate_task_prompt()` in `run.py`
- Add sibling task awareness (completed + remaining)
- Add previous-attempt injection from ledger
- Remove fix_plan.md references from prompt generation

### Phase 4: Cleanup

- Remove progress.txt references from all templates and prompts
- Remove guardrails.md template
- Remove fix_plan.md template
- Remove AGENT.md template (replaced by map)
- Delete stale progress.txt / progress.md files from cub repo
- Update CLAUDE.md in cub repo to use demarcated format
- Document context composition in cub's own CLAUDE.md
- Update tests

## Open Questions

1. Should `cub map` include ledger/forensics data (task completion rates,
   common failure patterns) for existing projects, or keep it purely structural?
2. What token budget should map.md target? 500-1000 tokens is a guess; needs
   testing across project sizes.
3. Should we generate `.github/copilot-instructions.md` alongside AGENTS.md?
   Same content, different location for GitHub Copilot users.
4. When the managed section version changes, should `cub update` auto-apply or
   prompt the user? Auto-apply is simpler but less transparent.

## Future Considerations

- **Repomix integration**: Use Repomix's `--compress` mode as an alternative
  extraction backend alongside the native tree-sitter pipeline.
- **Dynamic token budgeting**: Size the map dynamically based on the harness's
  context window (a la Aider's approach of expanding/contracting the repo map
  based on chat state).
- **Context7 MCP integration**: Recommend a documentation-fetching MCP server
  in `cub init` for projects using third-party libraries.
- **copilot-instructions.md generation**: Same managed section content at
  `.github/copilot-instructions.md` for GitHub Copilot users.
- **Cursor .mdc generation**: If AGENTS.md scoping evolves to support
  glob-based conditional loading, generate cursor-compatible rules.
- **LLM-assisted map descriptions**: Use an LLM to generate module descriptions
  from code, rather than relying on heuristics.
- **Constitution evolution**: Support for project-specific constitution variants
  (e.g., healthcare compliance, financial accuracy) beyond the default
  journalistic principles.

---

**Status**: researching
**Last Updated**: 2026-01-28
