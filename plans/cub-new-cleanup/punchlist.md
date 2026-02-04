# cub new Cleanup Punchlist

Issues identified during `cub new` testing that need to be addressed.

---

## 1. AGENTS.md and CLAUDE.md Issues

**Problem**: These files are too minimal and should include more instructions on using cub. They should also be the same file (symlinks or identical content).

**Current State**:
- `templates/agent.md` has basic cub commands but is copied to `AGENTS.md` and `CLAUDE.md` separately
- Content is reasonable but could be richer

**Fix**:
- [ ] Enhance `templates/agent.md` with more comprehensive cub workflow instructions
- [ ] Make AGENTS.md and CLAUDE.md symlinks to the same source (or generate identical content)
- [ ] Include: quick start, common workflows, troubleshooting

---

## 2. constitution.md Needs More Heft

**Problem**: The constitution.md file is too sparse.

**Current State**: Basic principles exist but lack depth.

**Fix**:
- [ ] Add more detailed principles and guidelines
- [ ] Include examples of good/bad patterns
- [ ] Add project-specific customization guidance

---

## 3. prompt.md vs runloop.md Confusion

**Problem**: Unclear what the difference is between `.cub/prompt.md` and `.cub/runloop.md`.

**Current State**:
- `runloop.md` - Core Ralph Loop instructions (57 lines, lean)
- `PROMPT.md` - Full template with customization comments (150+ lines)
- `cub init` copies `runloop.md` to `.cub/runloop.md`
- `cub stage` generates `.cub/prompt.md` from `PROMPT.md` template

**Analysis**:
- `runloop.md` = minimal core loop instructions for `cub run`
- `prompt.md` = user-customizable system prompt (PROMPT.md is the template)
- This is confusing - should be consolidated or clearly documented

**Fix**:
- [ ] Consolidate to single file OR clearly document the difference
- [ ] If keeping both: runloop.md = system-managed, prompt.md = user-customizable
- [ ] Update `cub init` to explain the purpose of each

---

## 4. Beads Installation and Statusline Dependency

**Problem**: Why is beads being installed? Why is statusline reliant on beads?

**Current State**:
- `templates/scripts/statusline.py` line 35: reads from `.beads/issues.jsonl`
- Does NOT check `.cub/tasks.jsonl` for JSONL backend
- Backend detection (line 715-718 in backend.py) checks for `.beads/` directory

**Fix**:
- [ ] Update `statusline.py` to check BOTH `.beads/issues.jsonl` AND `.cub/tasks.jsonl`
- [ ] Use same backend detection logic as `get_backend()`
- [ ] Don't require beads for statusline to work

---

## 5. Hook Log Data Location

**Problem**: Where does hook log data go?

**Current State**: Hooks write to `.cub/ledger/forensics/{session_id}.jsonl`

**Fix**:
- [ ] Document this location in `cub init` output
- [ ] Add to AGENTS.md/CLAUDE.md
- [ ] Consider adding `cub hooks log` command to view recent hook activity

---

## 6. Planning Commands and plan.json

**Problem**: Planning commands need to generate and update the appropriate plan.json.

**Current State**: plan.json generation/updates are incomplete or missing.

**Fix**:
- [ ] Audit `cub plan orient`, `cub plan architect`, `cub plan itemize` commands
- [ ] Ensure each phase writes to plan.json correctly
- [ ] Add validation that plan.json is properly structured

---

## 7. Need cub:stage Skill

**Problem**: Missing `cub:stage` skill for staging plans.

**Current State**: `cub stage` command exists but no skill wrapper.

**Fix**:
- [ ] Create `templates/commands/cub:stage.md` skill
- [ ] Register in skill system
- [ ] Test skill invocation

---

## 8. Two Config Files Confusion

**Problem**: There are two config files: `.cub.json` (root) and `.cub/config.json`.

**Current State**:
- `.cub.json` - Main project config (harness, budget, state, etc.)
- `.cub/config.json` - Internal state (dev_mode, etc.)
- Templates include both

**Fix**:
- [ ] Consolidate into single location OR clearly document difference
- [ ] Option A: Move everything to `.cub/config.json`
- [ ] Option B: Keep `.cub.json` for user settings, `.cub/config.json` for internal state
- [ ] Document the canonical location in AGENTS.md

---

## 9. Defaulting to Beads

**Problem**: Why is the system defaulting to beads backend?

**Current State** (backend.py:712-718):
```python
# Detection order:
# 1. CUB_BACKEND environment variable
# 2. .cub.json config file backend.mode setting
# 3. Presence of .beads/ directory (beads backend)
# 4. Presence of .cub/tasks.jsonl (jsonl backend)
# 5. Presence of prd.json file (jsonl backend with migration)
# 6. Default to jsonl backend
```

**Analysis**: Default IS jsonl, but beads is detected before jsonl if `.beads/` exists.

**Fix**:
- [ ] If `.beads/` detection is unintentional, remove or deprioritize
- [ ] `cub init` should set explicit backend in `.cub.json`
- [ ] Consider removing beads auto-detection (require explicit config)

---

## 10. Generating/Updating .cub/prompt.md

**Problem**: Why is prompt.md being generated/updated during init?

**Current State**: `cub init` runs `_copy_prompt_template()` which creates `.cub/prompt.md`.

**Fix**:
- [ ] Clarify whether prompt.md is user-editable or system-managed
- [ ] If user-editable: don't overwrite on init (only create if missing)
- [ ] If system-managed: rename to avoid confusion with runloop.md

---

## 11. Project ID / Epic Naming Prefix

**Problem**: roundabout project is using "cub" for epic naming instead of project-specific prefix.

**Current State** (jsonl.py:564-575):
```python
def _get_prefix(self) -> str:
    prefix = self.project_dir.name[:3].lower()
    return prefix if prefix else "cub"
```

**Analysis**: Uses first 3 chars of directory name. If project is named "cub-something", prefix would be "cub".

**Fix**:
- [ ] Add explicit `project_id` or `prefix` setting to `.cub.json`
- [ ] `cub init` should prompt for or generate a unique prefix
- [ ] Use this prefix for all task/epic IDs

---

## 12. plan.json Structure and Flow

**Problem**: Still need to get the plan.json file right and going.

**Current State**: plan.json structure and workflow needs audit.

**Fix**:
- [ ] Define canonical plan.json schema
- [ ] Ensure `cub plan orient` creates initial plan.json
- [ ] Ensure `cub plan architect` updates plan.json
- [ ] Ensure `cub plan itemize` adds tasks to plan.json
- [ ] Ensure `cub stage` reads plan.json correctly
- [ ] Add validation and error messages for malformed plan.json

---

## Priority Order

1. **High** (Blocking new project setup):
   - #9 Defaulting to beads
   - #4 Statusline beads dependency
   - #11 Project ID prefix

2. **Medium** (Quality of life):
   - #3 prompt.md vs runloop.md confusion
   - #8 Two config files
   - #1 AGENTS.md/CLAUDE.md enhancement
   - #6 plan.json generation

3. **Low** (Nice to have):
   - #2 constitution.md heft
   - #5 Hook log documentation
   - #7 cub:stage skill
   - #10 prompt.md generation clarification
   - #12 plan.json structure
