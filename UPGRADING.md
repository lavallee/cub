# Upgrading Cub

This guide helps you migrate between major versions of Cub.

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
| 0.27.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Plan flow rename |
| 0.26.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Captures system |
| 0.25.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Sandbox mode |
| 0.24.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Worktrees |
| 0.23.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Hybrid CLI |
| 0.21.x  | 3.10+  | 3.2+ | 0.1+  | Latest      | Python core |
| 0.20.x  | -      | 4.0+ | 0.1+  | Latest      | Last Bash-only |
| 0.13.x  | -      | 4.0+ | 0.1+  | Latest      | Curb → Cub |
