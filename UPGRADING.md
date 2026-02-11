# Upgrading Cub

This guide helps you migrate between major versions of Cub.

**Current version:** v0.30 (Alpha)

---

## v0.30 (Alpha)

### What Changed

This is a significant alpha release consolidating many features developed since v0.28.

- **Configuration consolidated** to `.cub/config.json` (legacy `.cub.json` still read with deprecation warning; run `cub init` to migrate)
- **New planning pipeline**: `cub plan run` executes orient, architect, itemize in sequence
- **Symbiotic workflow**: Hooks bridge direct Claude Code sessions with the ledger, enabling implicit task tracking without `cub run`
- **Dashboard (experimental)**: Kanban view across 8 workflow stages (captures, specs, planned, ready, in-progress, needs-review, complete, released)
- **Service layer architecture**: Business logic separated from CLI presentation via `core/services/` (RunService, LaunchService, LedgerService, StatusService, SuggestionService)
- **Context composition**: System prompts assembled from layered sources at runtime (runloop.md + plan context + epic/task/retry context)
- **New CLI commands**: `cub task`, `cub session`, `cub ledger`, `cub reconcile`, `cub review`, `cub suggest`, `cub verify`, `cub learn`, `cub retro`, `cub release`
- **Deprecated commands removed**: `cub prep` and `cub bootstrap` aliases (use `cub plan run` and `cub stage` instead)

### Migration Steps

#### 1. Migrate Configuration

```bash
cub init                          # Migrates .cub.json to .cub/config.json
cub doctor                        # Verify configuration health
```

#### 2. Install Hooks (for symbiotic workflow)

```bash
cub init                          # Also installs hooks to .claude/settings.json
```

#### 3. Verify Data Integrity

```bash
cub verify                        # Check ledger and ID consistency
cub verify --fix                  # Auto-fix simple issues
```

#### 4. Remove Deprecated Command References

If you have scripts or aliases using removed deprecated commands:

```bash
# Old (removed)
cub prep
cub bootstrap

# New
cub plan run
cub stage
```

### Backward Compatibility

- `.cub.json` is still read with a deprecation warning; run `cub init` to consolidate
- Old ledger structures remain readable
- The `PROMPT.md` template pattern is removed; use `.cub/runloop.md` instead

---

## v0.28.0: Ledger Consolidation & New Commands

### What Changed

The ledger system has been reorganized for better querying and consistency checks, and several new commands have been added for data integrity and learning from work.

#### New Ledger Structure

The task completion ledger now uses a multi-index organization with three access patterns:

**Old structure (if using legacy `.cub/runs/` or flat ledger):**
```
.cub/runs/{session-id}/tasks/
.cub/ledger/entries/
```

**New structure:**
```
.cub/ledger/
├── index.jsonl              # Index of all entries
├── by-task/{task-id}/       # Access by task
├── by-epic/{epic-id}/       # Access by epic
├── by-run/{run-id}/         # Access by run/session
└── forensics/{session-id}.jsonl  # Session event logs
```

#### New Commands

Four new commands have been added to complement your workflow:

1. **`cub verify`** - Check data integrity
   - Verifies ledger consistency
   - Validates ID formats
   - Checks counter synchronization
   - Can auto-fix simple issues with `--fix` flag

2. **`cub learn extract`** - Extract patterns and lessons
   - Analyzes completed work to identify patterns
   - Extracts key learnings and recommendations
   - Can update guardrails and documentation with `--apply` flag
   - Filter by date range with `--since` or `--since-date`

3. **`cub release`** - Mark plans as released
   - Updates plan status to "released"
   - Updates CHANGELOG.md automatically
   - Creates git tag for the release
   - Moves spec files to `specs/released/`

4. **`cub retro`** - Generate retrospectives
   - Creates detailed retrospective reports for epics or plans
   - Includes metrics, timeline, and lessons learned
   - Outputs to stdout or file with `--output`

### Migration Steps

#### 1. Verify Your Ledger (Recommended)

After upgrading, verify your ledger is in good shape:

```bash
cub verify                # Run all checks
cub verify --fix          # Auto-fix simple issues if needed
```

#### 2. Update Existing Ledger (If Using Old Structure)

If you have an older cub project using the legacy `.cub/runs/` artifact storage:

```bash
# Your data will still be accessible, but you may want to migrate
# Cub will automatically read from new structure
# For detailed migration, contact support or open an issue
```

#### 3. Try the New Commands

Start using the new commands to improve your workflow:

```bash
# Check data integrity
cub verify

# Extract patterns from your completed work
cub learn extract --since 30

# Generate a retro for your last completed epic
cub retro your-epic-id --epic --output retro.md

# Mark work as released
cub release epic-id v1.0
```

#### 4. Update Documentation

Update your project CLAUDÉ.md or team docs to reference the new commands:

```bash
# Instead of manual checks, use:
cub verify

# Instead of manual learning summaries, use:
cub learn extract --apply
```

### Backward Compatibility

- Old ledger locations are still supported for reading
- New data is written to the new structure
- `cub doctor` will help migrate if needed

### New ID Format

If your project hasn't migrated to the new ID format yet (like `cub-048a-5.4`), you can continue using older formats. The new format is optional and recommended for large projects with multiple epics.

---

## Upcoming: Plan Execution Unified (build-plan → run --plan)

### What Changed

The separate `cub build-plan` command has been removed. Plan execution is now integrated into `cub run --plan`.

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `cub build-plan <plan-slug>` | `cub run --plan <plan-slug>` | Unified into run command |

### Why the Change

- Reduced command fragmentation - all task execution goes through `cub run`
- Cleaner CLI interface with fewer top-level commands
- Better integration with task iteration and ledger system
- Easier for users to understand the main execution flow

### Migration Steps

If you have scripts or aliases using the old command:

```bash
# Old
cub build-plan my-feature

# New
cub run --plan my-feature
```

---

## v0.27.0: Plan Flow Rename (prep → plan)

### What Changed

The "prep pipeline" has been renamed to "plan flow" with updated command names:

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `cub prep` | `cub plan run` | Deprecated but still works with warning |
| `cub triage` | `cub plan orient` | triage now used for capture processing |
| `cub architect` | `cub plan architect` | Stage moved under plan namespace |
| `cub plan` | `cub plan itemize` | Old plan renamed to itemize |
| `cub bootstrap` | `cub stage` | Deprecated but still works with warning |

### Why the Change

The old terminology was confusing:
- "prep" didn't clearly indicate what was being prepared
- "triage" conflicted with capture triage feature
- "plan" as a verb and noun was ambiguous
- "bootstrap" wasn't intuitive for importing tasks

The new "plan flow" terminology is clearer:
- **Orient** - Research and understand the problem space
- **Architect** - Design the technical approach
- **Itemize** - Break into discrete tasks
- **Stage** - Import to task backend

### Migration Steps

#### 1. Update Scripts and Aliases

If you have scripts or aliases using old commands:

```bash
# Old
cub prep
cub triage
cub architect
cub plan
cub bootstrap

# New
cub plan run
cub plan orient
cub plan architect
cub plan itemize
cub stage
```

#### 2. Update Documentation

Update your project documentation to use new terminology:
- "prep pipeline" → "plan flow"
- "prep stage" → "planning stage"
- "triage" → "orient" (when referring to planning)

#### 3. Update Hooks

If you have custom hooks that reference these commands:

```bash
# Old
if [[ "$CUB_COMMAND" == "prep" ]]; then

# New
if [[ "$CUB_COMMAND" == "plan" ]]; then
```

### Backward Compatibility

Old commands still work but show deprecation warnings:

```bash
$ cub prep
⚠️  Warning: 'cub prep' is deprecated. Use 'cub plan run' instead.
```

```bash
$ cub bootstrap
⚠️  Warning: 'cub bootstrap' is deprecated. Use 'cub stage' instead.
```

These will be removed in v0.30.0.

### Note on `cub triage`

The standalone `cub triage` command now refers to **capture triage** (processing captured ideas/tasks), not the planning stage. For the planning workflow, use:

```bash
cub plan orient  # Replaces old 'cub triage' planning step
```

---

## v0.26.0: Captures System

### What Changed

Added a two-tier capture system for managing ideas and TODOs:

- **Inbox captures** (`~/.local/share/cub/captures/`) - Quick temporary notes
- **Archived captures** (`~/.local/share/cub/captures/archive/`) - Processed items

New commands:
- `cub capture` - Quick capture from command line
- `cub investigate` - Process captures into tasks
- `cub triage` - Triage captures (different from old triage!)

### Migration Steps

No action required. The captures system is new functionality that doesn't affect existing workflows.

---

## v0.25.0: Sandbox Mode

### What Changed

Added Docker-based sandboxing for safe autonomous execution:

```bash
cub run --sandbox              # Run in isolated container
cub sandbox status             # Check sandbox state
cub sandbox apply              # Apply changes to host
```

### Requirements

- Docker installed and running
- User in docker group (or use sudo)

### Migration Steps

No changes needed. Sandbox mode is opt-in via `--sandbox` flag.

---

## v0.24.0: Git Worktrees

### What Changed

Added worktree support for parallel development:

```bash
cub run --worktree             # Run in isolated worktree
cub run --parallel 3           # Run 3 tasks concurrently
cub worktree clean             # Cleanup stale worktrees
```

### Migration Steps

No changes needed. Worktree features are opt-in.

---

## v0.23.1: Hybrid Python/Bash CLI

### What Changed

Unified Python and Bash implementations under single `cub` command. All functionality now accessible through one CLI.

### Migration Steps

1. **Reinstall if using development setup:**

```bash
cd ~/tools/cub
git pull
uv sync
```

2. **No changes needed for normal users** - the `cub` command works the same, but now has access to all features.

---

## v0.21.0: Python Core Migration

### What Changed

Cub core rewritten in Python with backward compatibility for Bash features.

### Migration Steps

1. **Update Python version** - Requires Python 3.10+

```bash
python --version  # Must be 3.10 or higher
```

2. **Reinstall:**

```bash
# Via install script
curl -LsSf https://install.cub.tools | bash

# Or via pipx
pipx install --force git+https://github.com/lavallee/cub.git
```

3. **Update config if using Python-specific features:**

Config files remain compatible. New options available in `.cub.json`:

```json
{
  "harness": {
    "priority": ["claude", "codex"]
  },
  "budget": {
    "default": 1000000,
    "warn_at": 0.8
  }
}
```

---

## v0.13.0: Curb → Cub Rename

### What Changed

Project renamed from "Curb" to "Cub":
- All commands: `curb` → `cub`
- Config files: `.curb.json` → `.cub.json`
- Environment variables: `CURB_*` → `CUB_*`
- Config directory: `~/.config/curb/` → `~/.config/cub/`

### Migration Steps

#### 1. Reinstall

```bash
# Uninstall old version
rm -rf ~/.config/curb ~/.local/share/curb

# Install new version
curl -LsSf https://install.cub.tools | bash
cub init --global
```

#### 2. Update Projects

For each project using Cub:

```bash
cd /path/to/project

# Rename config file
mv .curb.json .cub.json

# Update config references in scripts
grep -r "curb" . --include="*.sh" --include="*.md"
# Manually replace curb → cub
```

#### 3. Update Environment Variables

```bash
# .bashrc or .zshrc
# Old
export CURB_PROJECT_DIR=/path/to/project
export CURB_DEBUG=true

# New
export CUB_PROJECT_DIR=/path/to/project
export CUB_DEBUG=true
```

#### 4. Update Git Hooks

If you have git hooks referencing `curb`:

```bash
cd .git/hooks
sed -i 's/curb/cub/g' *
```

---

## General Upgrade Tips

### Check Your Version

```bash
cub --version
```

### Backup Before Upgrading

```bash
# Backup config
cp -r ~/.config/cub ~/.config/cub.backup
cp .cub.json .cub.json.backup

# Backup tasks
cp -r .beads .beads.backup
```

### Test After Upgrading

```bash
# Verify installation
cub doctor

# Check config
cub init --global

# Run single task
cub run --once
```

### Get Help

- **Documentation**: https://cub.tools
- **Issues**: https://github.com/lavallee/cub/issues
- **Discussions**: https://github.com/lavallee/cub/discussions

---

## Version Compatibility Matrix

| Version | Python | Bash | Beads | Claude Code | Notes |
|---------|--------|------|-------|-------------|-------|
| 0.30.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Alpha: service layer, symbiotic workflow, dashboard |
| 0.27.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Plan flow rename |
| 0.26.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Captures system |
| 0.25.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Sandbox mode |
| 0.24.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Worktrees |
| 0.23.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Hybrid CLI |
| 0.21.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Python core |
| 0.20.x  | -      | 4.0+ | 0.1+  | Latest      | Last Bash-only |
| 0.13.x  | -      | 4.0+ | 0.1+  | Latest      | Curb → Cub |
