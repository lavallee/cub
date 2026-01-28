# Orient Report: Context Restructure

**Date:** 2026-01-28
**Orient Depth:** Standard
**Status:** Approved

---

## Executive Summary

Restructure cub's prompt context system to achieve parity between interactive and autonomous sessions. Replace seven fragmented, overlapping context files with a clean stack: demarcated managed sections in CLAUDE.md/AGENTS.md, an auto-generated tree-sitter-powered project map, a shipped constitution with journalistic principles, a focused runloop prompt, and enriched task prompts with epic/retry awareness. Eliminate progress.txt, guardrails.md, and fix_plan.md.

## Problem Statement

AI agents working on cub-managed projects get inconsistent, incomplete context depending on whether they run interactively or via `cub run`. New projects start cold with no auto-generated codebase understanding. Seven context-adjacent files have unclear ownership and overlapping roles, including 750KB+ of append-only progress dumps nobody reads. `cub init` is destructive to existing user content.

## Refined Vision

Any AI coding session -- interactive or autonomous -- on a cub-initialized project gets the same foundational context: project understanding (auto-generated map), operating principles (constitution), and cub integration (task workflow). Autonomous sessions add a focused runloop prompt and enriched task context. Users know exactly where to customize each layer.

## Requirements

### P0 - Must Have

- **Demarcated managed sections** in CLAUDE.md and AGENTS.md with version markers; non-destructive to user content
- **`cub map` command** generating `.cub/map.md` with directory tree, tech stack detection, build command extraction, and tree-sitter code intelligence (signatures, reference graph, PageRank ranking)
- **Tree-sitter grammar management**: detect project languages from config files, install grammars on first `cub map` run; graceful fallback to structural-only output if parsing fails
- **`.cub/constitution.md`** shipped with default journalistic principles; not overwritten on update
- **`.cub/runloop.md`** containing pure ralph-loop autonomous behavior (replaces PROMPT.md)
- **Enriched task prompts**: `generate_task_prompt()` includes epic context (description, completed siblings, remaining siblings)
- **Previous-attempt injection** on retry: `error_category` + `error_summary` + tail of harness log from ledger
- **`cub update` command** that refreshes managed sections and regenerates map
- **Elimination of progress.txt** references from all templates and prompts
- **Context composition documentation** so users know where to make changes

### P1 - Should Have

- Configurable token budget for map generation (`cub map --tokens N`, default ~1500)
- Ledger stats (task completion rates, attempt counts) included in map for existing projects
- `cub init` detects old-format cub-generated CLAUDE.md/AGENTS.md and migrates to demarcated format
- Elimination of guardrails.md and fix_plan.md templates

### P2 - Nice to Have

- `cub map --watch` for auto-regeneration on file changes
- Constitution variants (healthcare, financial) beyond the default
- `.github/copilot-instructions.md` generation

## Constraints

- **No ledger restructuring**: the ledger schema is stable; retry injection reads existing data
- **No LLM in map generation**: tree-sitter static analysis only; LLM-assisted descriptions are future work
- **Python 3.10+**: must work with cub's minimum supported Python version
- **py-tree-sitter compatibility**: must handle missing or failed grammars gracefully
- **Blocks symbiotic workflow**: that spec depends on this context stack being clean

## Assumptions

- `@` references resolve in Claude Code pipe mode for `.cub/` paths (verified by testing)
- CLAUDE.md is auto-read by Claude Code in both interactive and pipe modes (verified)
- AGENTS.md is read by other harnesses (Codex, OpenCode, Gemini CLI) per the AAIF standard
- Existing hand-written AGENT.md files are left alone; `.cub/map.md` is a separate artifact
- Progress.txt content (750KB+) is not worth migrating -- it's append-only noise

## Open Questions / Experiments

1. **Token budget tuning** -- 1500 tokens is a starting guess. Need to test across projects of different sizes (10-file script vs. 500-file monorepo) and measure whether agents actually use the map effectively. Experiment: generate maps for 5 real projects, measure token counts, gather qualitative feedback.
2. **Grammar installation UX** -- First `cub map` run needs to download grammars. What's the latency? Does it need a progress indicator? Experiment: time the first-run grammar installation for Python + JS/TS projects.
3. **Managed section placement** -- Should the cub section go at the top or bottom of CLAUDE.md/AGENTS.md? Top means agents see it first; bottom means user content takes priority. Start with bottom (append), revisit if agents consistently miss it.
4. **`cub update` auto-apply** -- When the managed section version changes, should `cub update` auto-apply or warn first? Start with auto-apply (it's the managed section, cub owns it), add `--dry-run` flag.

## Out of Scope

- Hook-based tracking (symbiotic workflow)
- LLM-powered map descriptions
- Migrating existing progress.txt content
- Restructuring the ledger
- Generating .cursorrules or copilot-instructions.md
- Real-time context injection

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tree-sitter grammar install fails on some platforms | M | Graceful fallback to structural-only map; clear error message |
| Map is too large / too small for varying project sizes | M | Configurable token budget; test across project sizes before shipping |
| Users don't notice managed section markers and edit inside them | L | Clear comments in markers; `cub update` detects and warns about manual edits |
| Removing progress.txt breaks workflows that depend on it | L | The files are append-only dumps; nothing reads them meaningfully |
| Constitution is ignored as boilerplate | L | Keep it short and opinionated; reference it from managed section so agents actually read it |

## MVP Definition

All four phases ship together. The phases are implementation order, not release gates. The smallest useful unit is the complete context stack -- demarcation without a map to reference, or a map without a place to reference it from, doesn't achieve the parity goal.

---

**Next Step:** Run `cub architect` to proceed to technical design.
