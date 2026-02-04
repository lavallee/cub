# Orient Report: 0.30 Foundation Phase

**Date:** 2026-01-26
**Orient Depth:** Standard
**Status:** Approved

---

## Executive Summary

Cub needs a simpler, self-contained task backend for its 0.30 public alpha. Beads has been overkill for the small/medium projects cub targets, creating maintenance burden and onboarding friction. This foundation phase adopts beads' JSONL schema as cub's native format, adds Python-native git sync, and polishes docs/CLI for alpha quality.

## Problem Statement

The current dual-backend situation (beads vs JSON) confuses users and creates maintenance burden. Beads is a complex, actively-developed tool that's been more distraction than aid for cub's target use case. New users hit friction with beads dependency, and task state doesn't persist across git clones without external tooling.

**Who has this problem:** Developers who want to try cub's autonomous coding workflow but get blocked by beads setup or confused by backend options.

## Refined Vision

Unify cub's task management on a single, robust JSONL format that:
1. Uses beads' proven schema (compatibility, future interop)
2. Lives in `.cub/tasks.jsonl` (self-contained, no external deps)
3. Syncs via git branch (persistence across machines)
4. Validates against beads during transition ("both" mode)

Bundle with documentation audit and CLI polish to create a solid foundation for public alpha.

## Requirements

### P0 - Must Have

- **JSONL Backend**: New `JsonlBackend` class implementing full `TaskBackend` protocol with beads-compatible schema
- **Sync Branch**: Git-based persistence using `cub-sync` branch, Python-native implementation (no `bd` dependency)
- **"Both" Mode**: Dual read/write to beads + JSONL as default, with divergence detection and warnings
- **Documentation Audit**: README matches `cub --help`, Quick Start works end-to-end, alpha disclaimer prominent
- **CLI Polish**: Helpful `--help` text, actionable error messages, consistent exit codes

### P1 - Should Have

- **Migration Tooling**: Automatic migration from old `prd.json` format on first access
- **Comparison Script**: `./scripts/compare-backends.py` for manual validation during transition
- **`cub docs` Command**: Opens documentation in browser
- **Auto-sync During Run**: Task mutations sync automatically during `cub run`

### P2 - Nice to Have

- **Conflict Detection**: Warn when conflicting edits detected during sync (apply last-write-wins but alert user)
- **Configurable Sync Branch Name**: Allow override in `.cub/config.toml`
- **`cub sync --status`**: Show sync state without syncing

## Constraints

- No hard constraints identified
- Beads backend will remain available as optional component post-release
- Timeline is flexible but aiming for ~2 weeks to maintain momentum

## Assumptions

- Users of existing `prd.json` format are few and can be migrated automatically
- Git plumbing operations (`write-tree`, `commit-tree`, `update-ref`) are stable and well-documented
- "Both" mode as default provides sufficient safety net during transition
- Small/medium projects are the primary target; enterprise-scale task management is out of scope

## Open Questions / Experiments

- **Sync branch performance at scale** -> Experiment: If >1000 tasks causes issues, consider chunked writes
- **Multi-machine concurrent edits** -> Experiment: Document as known limitation, gather feedback from alpha users
- **Daemon mode necessity** -> Experiment: Deferred to post-alpha; assess if sync latency becomes pain point

## Out of Scope

- Removing beads backend support (remains available for advanced users)
- Full beads feature parity (daemon, multi-repo, worktrees beyond sync)
- Speccing E4-E10 (deferred until after task cutover validated)
- Building a web UI for task management
- Supporting multiple simultaneous task files
- Auto-pull from remote sync branch (manual `cub sync --pull` for alpha)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Git plumbing bugs | High | Comprehensive integration tests, fallback to manual sync if needed |
| Migration edge cases | Medium | "Both" mode catches divergence before full cutover |
| Scope expansion | Medium | Strict adherence to spec, defer nice-to-haves to 0.31 |
| Documentation drift | Low | Doc audit is explicit component with acceptance criteria |
| Sync branch complexity | High | Start with simplest working implementation, defer advanced features |

## MVP Definition

Full spec as written: all 5 components (JSONL backend, sync branch, "both" mode, docs audit, CLI polish). This is achievable because:
- JSONL backend is straightforward (4-6h)
- Sync branch uses proven git plumbing patterns (6-8h, primary risk)
- "Both" mode is wrapper logic (4-6h)
- Docs and CLI are bounded by existing command surface

If sync branch proves too complex, fallback MVP is JSONL backend + docs + CLI polish, with sync deferred.

## Key Decisions

| Decision | Resolution | Rationale |
|----------|------------|-----------|
| Sync branch conflicts | Detect and warn, apply last-write-wins | Balance simplicity with user awareness |
| Auto-sync default | On during `cub run` only | Automation where it matters, manual control elsewhere |
| "Both" mode default | Enabled for all users | Safety net during transition |
| Sync branch name | `cub-sync` | Generic, allows expansion beyond tasks |

## Success Criteria

1. **Quick Start works**: New user follows Quick Start with JSON backend, completes a task without hitting beads
2. **Friends test clean**: 2-3 friends/colleagues install, init, and run cub without debugging help
3. **Self-hosting stable**: Cub reliably manages its own development using new JSONL backend and sync branch

---

**Next Step:** Run `cub architect` to proceed to technical design.
