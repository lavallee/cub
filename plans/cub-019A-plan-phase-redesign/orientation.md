# Orientation: Plan Phase Redesign

> Source: [specs/researching/plan-phase-redesign.md](../../specs/researching/plan-phase-redesign.md)
> Generated: 2026-01-20
> Depth: Standard

## Problem Statement

The current `cub prep` pipeline has unclear nomenclature ("prep" and "bootstrap" don't convey meaning), generates artifacts in hidden directories (`.cub/sessions/`), and relies on 1,700+ lines of bash that's difficult to extend or test. Planning output isn't easily editable before becoming tasks, and there's no integration between spec lifecycle and planning stages.

**Who has this problem**: Cub users going from idea → executable tasks who need planning artifacts that are clear, reviewable, editable, and properly tracked through their lifecycle.

## Requirements

### P0 (Must Have)

- **Rename commands**: `prep` → `plan`, `triage` → `orient`, `plan` (stage) → `itemize`, `bootstrap` → `stage`
- **Visible plans directory**: `/plans/{slug}/` at project root, not hidden in `.cub/sessions/`
- **Python implementation**: Full pipeline in Python using Claude Agent SDK (flagged for future refactoring to be harness-configurable)
- **Editable source of truth**: `itemized-plan.md` is the single editable plan; JSONL generated at stage time by `cub stage`
- **TaskBackend integration**: `cub stage` imports via `TaskBackend.import_tasks()`, works with both Beads and JSON backends
- **Spec lifecycle automation**: All 5 stages automated:
  - `cub plan` completes → spec moves `researching/` → `planned/`
  - `cub stage` completes → spec moves `planned/` → `staged/`
  - First task starts → spec moves `staged/` → `implementing/`
  - Release cut → spec moves `implementing/` → `released/`
- **Beads ID format**: Epic IDs use random 3-5 char suffix (`cub-k7m`), NOT sequential numbers

### P1 (Should Have)

- **Self-answering interviews**: Orient/Architect/Itemize stages seek answers in codebase, existing plans, specs, CLAUDE.md before asking user. Present assumptions for confirmation. **Do not invent answers** - surface unknowns rather than fabricate.
- **Plan metadata**: `plan.json` stores spec filename; spec found by searching `specs/` subdirectories
- **Slug collision handling**: Multiple plans per spec allowed; use `_alt_[a-z]` suffix for alternatives
- **Deprecation warnings**: Old commands (`cub prep`, etc.) warn and point to new commands

### P2 (Nice to Have)

- **SYSTEM-PLAN.md**: Constitutional memory for project patterns (YOLO schema for now, evolve organically)
- **Plan management commands**: `cub plans list/show/delete`
- **Migration tooling**: Script to migrate existing `.cub/sessions/` to `/plans/`

## Constraints

| Constraint | Detail |
|------------|--------|
| Python version | 3.10+ (match statements, type unions) |
| Breaking changes | Acceptable - not maintaining `.cub/sessions/` compatibility |
| SDK dependency | Claude Agent SDK for interview orchestration (flag for future configurability) |
| Task backend | Must use `TaskBackend` Protocol, not beads-specific code |
| Beads IDs | Random suffix format required; sequential IDs cause collisions |
| mypy | Strict mode compliance required |

## Open Questions

1. **SDK interrupts**: How do we gracefully handle user interrupts mid-interview? Can we checkpoint and resume?
2. **ID collision checking**: Should `cub plan` check existing beads for epic ID collisions before generating new IDs?
3. **Spec search at scale**: Searching all `specs/` subdirectories by filename - acceptable performance for large projects?

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| SDK interaction model doesn't support graceful interrupts | High | Medium | Investigate SDK capabilities early; design checkpoint system if needed |
| Self-answering generates poor assumptions | Medium | Medium | Be precise: seek in codebase, don't invent. User corrects rather than confirms = regression |
| Beads import edge cases | Medium | Low | Test with both backends; use existing `bd import` for beads path |
| Large refactor scope creep | High | Medium | Clear MVP boundary; defer SYSTEM-PLAN.md, plan management, migration tooling |

## MVP Boundary

**In scope for MVP:**
- `cub plan` command with orient/architect/itemize subcommands
- `cub stage` command importing via TaskBackend
- All 5 spec lifecycle transitions automated
- Plans in `/plans/{slug}/` with orientation.md, architecture.md, itemized-plan.md
- Works with BeadsBackend and JsonBackend
- Deprecation warnings on old commands

**Explicitly deferred:**
- SYSTEM-PLAN.md constitutional memory (YOLO)
- `cub plans` management commands
- `.cub/sessions/` migration tooling
- Harness-agnostic SDK abstraction (use Claude SDK directly for now)

---

**Status**: Ready for Architect phase
