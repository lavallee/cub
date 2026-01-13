# Upgrading to Curb 1.0

Curb 1.0 introduces significant new features and some breaking changes from earlier versions. This guide helps you understand what changed and how to upgrade your workflow.

## TL;DR

If you're upgrading from a pre-1.0 version:

1. **Initialize global config** (one time): `cub init --global`
2. **Update project config** (if you have `.cub.json`): Review the new options in [Configuration Schema](#configuration-schema)
3. **Review breaking changes**: See [Breaking Changes](#breaking-changes) section
4. **Test your setup**: Run `cub run --once` and verify logs are created
5. **Optional: Migrate to beads**: `cub --migrate-to-beads` (if using prd.json)
6. **Update any scripts**: Replace old flag syntax with new subcommands (see [CLI Subcommand Migration](#7-cli-subcommand-migration))

That's it! The core workflow remains the same. Old CLI syntax still works with deprecation warnings.

## What's New in 1.0

### Major Features

#### 1. **Budget Management**
Token budgets prevent runaway spending on AI API calls. Set once and curb stops automatically when budget is reached.

```bash
# Set budget via flag
cub --budget 1000000

# Or via environment variable
export CUB_BUDGET=1000000
curb

# Or in config file
# ~/.config/cub/config.json or .cub.json
{
  "budget": {
    "default": 500000,
    "warn_at": 0.8
  }
}
```

**New related flags and env vars:**
- `--budget <tokens>` - Set token budget
- `CUB_BUDGET` - Budget override
- `budget.default` in config - Default budget per run
- `budget.warn_at` in config - Warning threshold (0.0-1.0, default 0.8)

#### 2. **Hooks System**
Extend curb behavior with custom scripts at 5 lifecycle points. Use for notifications, logging, integration with external tools.

```bash
# Create a post-task hook to notify Slack
mkdir -p ~/.config/cub/hooks/post-task.d
cat > ~/.config/cub/hooks/post-task.d/10-slack.sh << 'EOF'
#!/usr/bin/env bash
curl -X POST $SLACK_WEBHOOK \
  -d "Task $CUB_TASK_ID finished with code $CUB_EXIT_CODE"
EOF
chmod +x ~/.config/cub/hooks/post-task.d/10-slack.sh
```

**Hook points:**
- `pre-loop` - Before loop starts (setup)
- `pre-task` - Before each task (prepare environment)
- `post-task` - After each task (notifications, metrics)
- `on-error` - When task fails (alerts, incident creation)
- `post-loop` - After loop completes (cleanup, reports)

**Context variables available:**
- `CUB_TASK_ID`, `CUB_TASK_TITLE` - Current task
- `CUB_EXIT_CODE` - Task exit code (0 = success)
- `CUB_HARNESS` - Harness in use (claude, codex, opencode, gemini)
- `CUB_SESSION_ID` - Unique session identifier
- `CUB_PROJECT_DIR` - Project directory

See example hooks in `examples/hooks/` directory.

#### 3. **Clean State Enforcement**
Curb now verifies the git repository is in a clean state before and after tasks. Prevents accidentally pushing broken code.

```bash
# Enable in config (default: true)
{
  "clean_state": {
    "require_commit": true,    # Require clean working directory
    "require_tests": false     # Require tests pass before task
  }
}

# Override via flags
cub --require-clean         # Force clean state requirement
cub --no-require-clean      # Disable clean state requirement
```

#### 4. **Structured Logging (JSONL)**
All task execution is logged to `~/.local/share/cub/logs/{project}/{session}.jsonl` in machine-readable JSONL format. Great for analysis and debugging.

```bash
# Query logs with jq
jq 'select(.event_type=="task_end" and .data.exit_code != 0)' logs/*.jsonl    # Failed tasks
jq '.data.tokens_used' logs/*.jsonl | jq -s 'add'                             # Total tokens
jq 'select(.data.duration > 300)' logs/*.jsonl                                # Slow tasks
```

#### 5. **New Harnesses (Gemini, OpenCode)**
Support for Google Gemini and OpenCode in addition to Claude and Codex.

```bash
# Use Gemini
cub --harness gemini

# Use OpenCode
cub --harness opencode

# Configure default priority in config
{
  "harness": {
    "priority": ["claude", "opencode", "codex", "gemini"]
  }
}
```

#### 6. **Harness Auto-Detection**
Curb now detects harness capabilities and adapts behavior accordingly. Includes capability detection for streaming, token reporting, system prompts, and auto mode.

### Minor Features

- **Per-task model selection** - Use `model:haiku`, `model:sonnet`, `model:opus-4.5` labels to optimize cost
- **Harness priority configuration** - Customize harness detection order
- **Test requirement** - Optional requirement for tests to pass before commit
- **XDG-compliant config** - Config stored in standard XDG directories
- **Improved --help output** - All flags documented with examples

## Breaking Changes

### 1. **Config File Changes**

If you have a `.cub.json` project config or `~/.config/cub/config.json` global config from before 1.0, review these changes:

**New required fields:**
- `hooks.enabled` (new) - Set to `true` to enable hooks
- `hooks.fail_fast` (new) - Set to `false` to continue if hooks fail
- `clean_state.require_commit` (new) - Set to `true` to require clean state
- `clean_state.require_tests` (new) - Set to `false` unless you want tests required

**Example old config (pre-1.0):**
```json
{
  "harness": {
    "default": "claude"
  }
}
```

**Updated config (1.0):**
```json
{
  "harness": {
    "default": "auto",
    "priority": ["claude", "codex"]
  },
  "budget": {
    "default": 1000000,
    "warn_at": 0.8
  },
  "loop": {
    "max_iterations": 100
  },
  "clean_state": {
    "require_commit": true,
    "require_tests": false
  },
  "hooks": {
    "enabled": true,
    "fail_fast": false
  }
}
```

**Migration:** If you don't have a config file, run `curb-init --global` to create one with sensible defaults. If you do have a config, add the missing sections.

### 2. **Global Configuration Location**

**Before 1.0:** No global config
**After 1.0:** `~/.config/cub/config.json`

Run `curb-init --global` to set up the new global config location.

### 3. **Log Location Changed**

**Before 1.0:** Logs (if any) location was not standardized
**After 1.0:** Logs at `~/.local/share/cub/logs/{project}/{session}.jsonl`

Logs are now machine-readable JSONL, great for querying with `jq`. Old logs won't be migrated automatically, but new runs will create properly-formatted logs.

### 4. **Hook Directory Structure (New)**

If you have custom hooks from a pre-1.0 version, they need to be moved to the new hook system:

**Before 1.0:** Hooks were project-specific, location varied
**After 1.0:**
- Global hooks: `~/.config/cub/hooks/{hook-name}.d/`
- Project hooks: `.cub/hooks/{hook-name}.d/`

If you have existing hook scripts, move them to the appropriate `hook-name.d/` directory and ensure they're executable.

### 5. **Beads Backend Migration**

If you're using `prd.json` for task management:

```bash
# Preview what would be migrated
cub --migrate-to-beads-dry-run

# Perform migration
cub --migrate-to-beads
```

The JSON backend is still fully supported, so you don't have to migrate if you don't want to.

### 7. **CLI Subcommand Migration**

The curb CLI has been updated to use subcommands for clearer organization. The old flag-based syntax still works but shows deprecation warnings.

**Command Syntax Changes:**

| Old Syntax | New Syntax | Notes |
|------------|------------|-------|
| `curb-init` | `cub init` | Initialize project |
| `curb-init --global` | `cub init --global` | Initialize global config |
| `cub --status` | `cub status` | Show task progress |
| `cub --status --json` | `cub status --json` | JSON output |
| `cub --ready` | `cub run --ready` | List ready tasks |
| `cub --once` | `cub run --once` | Single iteration |
| `cub --plan` | `cub run --plan` | Planning mode |
| `curb -s` | `cub status` | Short flag |
| `curb -r` | `cub run --ready` | Short flag |
| `curb -1` | `cub run --once` | Short flag |
| `curb -p` | `cub run --plan` | Short flag |

**Deprecation Warnings:**

When using the old syntax, curb shows a warning like:
```
[cub] DEPRECATED: --status flag is deprecated. Use 'cub status' instead.
[cub] This flag will be removed in a future release.
```

**Suppressing Warnings:**

If you have scripts using the old syntax and want to suppress warnings temporarily:
```bash
export CUB_NO_DEPRECATION_WARNINGS=1
```

**Timeline:**

- **1.0**: Old syntax works with warnings (current release)
- **1.1**: Old syntax continues to work with warnings
- **2.0**: Old syntax may be removed (announced ahead of time)

**Migration Tips:**

1. Update scripts gradually - the old syntax still works
2. Use tab completion with `curb <TAB>` to discover subcommands
3. Run `cub --help` to see the new command structure
4. Run `curb <subcommand> --help` for subcommand-specific help

**New Help System:**

Each subcommand now has its own help:
```bash
cub --help           # Main help (shows all subcommands)
cub init --help      # Init subcommand help
cub run --help       # Run subcommand help
cub status --help    # Status subcommand help
cub explain --help   # Explain subcommand help
cub artifacts --help # Artifacts subcommand help
```

### 8. **New Required Environment Variables (Mostly Optional)**

Most new environment variables have sensible defaults. The only truly required one for budget control is:

- `CUB_BUDGET` - Set if you want to override config budget

All other environment variables are optional:
- `CUB_BACKEND` - Auto-detects (beads or json)
- `CUB_EPIC`, `CUB_LABEL` - Optional filtering
- `HARNESS` - Auto-detects available harness
- `CUB_STREAM`, `CUB_DEBUG` - Optional debugging flags

## Step-by-Step Upgrade Guide

### For Existing Projects

1. **Back up your current setup** (just in case)
   ```bash
   cd your-project
   git status  # Ensure clean state
   ```

2. **Update curb itself**
   ```bash
   cd ~/tools/curb
   git pull origin main
   ```

3. **Initialize global config** (one-time, system-wide)
   ```bash
   cub init --global
   ```

4. **Review and update project config** (if you have `.cub.json`)
   ```bash
   # Check if you have a project config
   cat .cub.json

   # Add missing fields from the new schema
   # See Configuration Schema below
   ```

5. **Test your setup**
   ```bash
   # Run a single iteration to verify everything works
   cub run --once

   # Check logs were created
   ls -la ~/.local/share/cub/logs/your-project/
   ```

6. **Review new features**
   - Try `cub --help` to see new subcommands
   - Consider setting up a hook for notifications
   - Set a budget to prevent overspending

7. **Update scripts using old CLI syntax** (optional but recommended)
   ```bash
   # Find scripts using old syntax
   grep -r "cub --status\|cub --ready\|cub --once\|curb-init" scripts/

   # Update to new syntax:
   #   cub --status  ->  cub status
   #   cub --ready   ->  cub run --ready
   #   cub --once    ->  cub run --once
   #   curb-init      ->  cub init
   ```

8. **Optional: Migrate to beads**
   ```bash
   # Only if you want to switch from JSON to beads backend
   cub --migrate-to-beads
   ```

## Configuration Schema

Full reference of all config options in 1.0:

```json
{
  "harness": {
    "default": "auto",
    "priority": ["claude", "opencode", "codex", "gemini"]
  },
  "budget": {
    "default": 1000000,
    "warn_at": 0.8
  },
  "loop": {
    "max_iterations": 100
  },
  "clean_state": {
    "require_commit": true,
    "require_tests": false
  },
  "hooks": {
    "enabled": true,
    "fail_fast": false
  }
}
```

## New Environment Variables Reference

### Core

| Variable | Purpose | Example |
|----------|---------|---------|
| `CUB_PROJECT_DIR` | Project directory | `/path/to/project` |
| `CUB_MAX_ITERATIONS` | Max loop iterations | `50` |
| `HARNESS` | AI harness to use | `claude` or `gemini` |
| `CUB_BACKEND` | Task backend | `beads` or `json` |

### Budget

| Variable | Purpose | Example |
|----------|---------|---------|
| `CUB_BUDGET` | Token budget limit | `1000000` |

### Filtering

| Variable | Purpose | Example |
|----------|---------|---------|
| `CUB_EPIC` | Filter to epic | `curb-1gq` |
| `CUB_LABEL` | Filter to label | `phase-1` |

### Debugging

| Variable | Purpose | Example |
|----------|---------|---------|
| `CUB_DEBUG` | Enable verbose output | `true` |
| `CUB_STREAM` | Stream harness output | `true` |
| `CUB_MODEL` | Claude model | `opus` or `haiku` |

### Harness-Specific Flags

| Variable | Purpose | Example |
|----------|---------|---------|
| `CLAUDE_FLAGS` | Extra Claude Code flags | `--disable-confirmation` |
| `CODEX_FLAGS` | Extra Codex flags | `--api-key xxx` |
| `GEMINI_FLAGS` | Extra Gemini flags | `--api-key xxx` |
| `OPENCODE_FLAGS` | Extra OpenCode flags | `--api-key xxx` |

## New Command-Line Flags

### Budget Management

```bash
cub --budget 1000000          # Set budget limit
```

### Clean State

```bash
cub --require-clean            # Force clean state check
cub --no-require-clean         # Disable clean state check
```

### Filtering

```bash
cub --epic curb-1gq            # Only run tasks in epic
cub --label phase-1            # Only run tasks with label
cub --epic curb-1gq --label phase-1  # Combine filters
```

### Harness Selection

```bash
cub --harness gemini           # Use Gemini harness
cub --harness opencode         # Use OpenCode harness
```

### Output Control

```bash
cub --stream                   # Show real-time output
cub --debug                    # Verbose debugging
cub --dump-prompt              # Save prompts to files
```

### Other

```bash
cub --once                     # Run single iteration
cub --status                   # Show task status
cub --ready                    # Show ready tasks
cub --plan                     # Plan mode
cub --test                     # Test harness
```

## FAQ

### Q: Do I have to migrate from prd.json to beads?

**A:** No, the JSON backend is fully supported. Beads is optional. Only migrate if you prefer beads' UI or need its features.

### Q: Will my old hooks still work?

**A:** If you have hooks, you'll need to move them to the new hook directory structure:
- Global: `~/.config/cub/hooks/{hook-name}.d/`
- Project: `.cub/hooks/{hook-name}.d/`

Then verify they work by running `cub --once` and checking that hooks fire.

### Q: Do I have to set up hooks?

**A:** No, hooks are completely optional. You can use curb without any hooks. Disable them in config if you don't want any running:

```json
{
  "hooks": {
    "enabled": false
  }
}
```

### Q: What's the difference between the new harnesses?

**A:**
- **Claude Code** (default) - Best overall, supports streaming, token reporting, full capability detection
- **OpenCode** - OpenAI's alternative, good if you're in their ecosystem
- **Gemini** - Google's harness, lightweight option
- **Codex** - OpenAI's older harness, still supported for compatibility

### Q: Can I use budget without setting it up explicitly?

**A:** Yes! The default budget is 1,000,000 tokens. You only need to set it if you want a different limit.

### Q: How do I check if my setup is working?

**A:**
```bash
# Run one iteration
cub run --once

# Check logs were created
ls ~/.local/share/cub/logs/

# Query logs
jq '.' ~/.local/share/cub/logs/myproject/*.jsonl | head
```

### Q: What if I don't want clean state checking?

**A:** Disable it in config or via flag:
```bash
# Via config
echo '{"clean_state":{"require_commit":false}}' > .cub.json

# Via flag
cub --no-require-clean
```

### Q: Where's the documentation for all config options?

**A:** See the main [README.md](README.md) which has comprehensive sections on:
- Configuration
- Budget Management
- Hooks
- Environment Variables

### Q: My scripts use the old CLI flags. Do I need to update them immediately?

**A:** No! The old flag syntax still works and will continue working in 1.0 and 1.1. You'll just see deprecation warnings. Update at your convenience - there's no rush.

To suppress warnings in scripts:
```bash
export CUB_NO_DEPRECATION_WARNINGS=1
```

### Q: What are the new subcommands?

**A:** The main subcommands are:
```bash
cub init       # Initialize project or global config
cub run        # Run the main loop (default if no subcommand)
cub status     # Show task progress
cub explain    # Show task details
cub artifacts  # List task outputs
curb version    # Show version
```

## Getting Help

If you run into issues:

1. **Check README.md** - Comprehensive feature documentation
2. **Review example hooks** - See `examples/hooks/` for patterns
3. **Check logs** - `~/.local/share/cub/logs/` has detailed execution logs
4. **Test with --debug** - `cub --debug --once` shows what's happening
5. **Report issues** - https://github.com/lavallee/cub/issues

## What Stays the Same

The core workflow hasn't changed:

1. **Task management** - Still uses prd.json or beads
2. **Harness invocation** - Still works the same way
3. **Basic loop** - Find ready task → run → loop
4. **Prompt structure** - PROMPT.md and task templates unchanged
5. **Feedback loops** - Type checking, tests, linting still work

You can upgrade gradually and adopt new features at your own pace!

## Next Steps

1. Run `cub init --global` to set up global config
2. Review your project config (if you have one) and update it
3. Try `cub run --once` to verify everything works
4. Explore the new subcommand structure: `cub --help`
5. Read README.md sections on new features you're interested in
6. Set up hooks or budget management if they're useful for you

Welcome to Curb 1.0!
