# Upgrading to Curb 1.0

Curb 1.0 introduces significant new features and some breaking changes from earlier versions. This guide helps you understand what changed and how to upgrade your workflow.

## TL;DR

If you're upgrading from a pre-1.0 version:

1. **Initialize global config** (one time): `curb init --global`
2. **Update project config** (if you have `.curb.json`): Review the new options in [Configuration Schema](#configuration-schema)
3. **Review breaking changes**: See [Breaking Changes](#breaking-changes) section
4. **Test your setup**: Run `curb run --once` and verify logs are created
5. **Optional: Migrate to beads**: `curb --migrate-to-beads` (if using prd.json)
6. **Update any scripts**: Replace old flag syntax with new subcommands (see [CLI Subcommand Migration](#7-cli-subcommand-migration))

That's it! The core workflow remains the same. Old CLI syntax still works with deprecation warnings.

## What's New in 1.0

### Major Features

#### 1. **Budget Management**
Token budgets prevent runaway spending on AI API calls. Set once and curb stops automatically when budget is reached.

```bash
# Set budget via flag
curb --budget 1000000

# Or via environment variable
export CURB_BUDGET=1000000
curb

# Or in config file
# ~/.config/curb/config.json or .curb.json
{
  "budget": {
    "default": 500000,
    "warn_at": 0.8
  }
}
```

**New related flags and env vars:**
- `--budget <tokens>` - Set token budget
- `CURB_BUDGET` - Budget override
- `budget.default` in config - Default budget per run
- `budget.warn_at` in config - Warning threshold (0.0-1.0, default 0.8)

#### 2. **Hooks System**
Extend curb behavior with custom scripts at 5 lifecycle points. Use for notifications, logging, integration with external tools.

```bash
# Create a post-task hook to notify Slack
mkdir -p ~/.config/curb/hooks/post-task.d
cat > ~/.config/curb/hooks/post-task.d/10-slack.sh << 'EOF'
#!/usr/bin/env bash
curl -X POST $SLACK_WEBHOOK \
  -d "Task $CURB_TASK_ID finished with code $CURB_EXIT_CODE"
EOF
chmod +x ~/.config/curb/hooks/post-task.d/10-slack.sh
```

**Hook points:**
- `pre-loop` - Before loop starts (setup)
- `pre-task` - Before each task (prepare environment)
- `post-task` - After each task (notifications, metrics)
- `on-error` - When task fails (alerts, incident creation)
- `post-loop` - After loop completes (cleanup, reports)

**Context variables available:**
- `CURB_TASK_ID`, `CURB_TASK_TITLE` - Current task
- `CURB_EXIT_CODE` - Task exit code (0 = success)
- `CURB_HARNESS` - Harness in use (claude, codex, opencode, gemini)
- `CURB_SESSION_ID` - Unique session identifier
- `CURB_PROJECT_DIR` - Project directory

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
curb --require-clean         # Force clean state requirement
curb --no-require-clean      # Disable clean state requirement
```

#### 4. **Structured Logging (JSONL)**
All task execution is logged to `~/.local/share/curb/logs/{project}/{session}.jsonl` in machine-readable JSONL format. Great for analysis and debugging.

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
curb --harness gemini

# Use OpenCode
curb --harness opencode

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

If you have a `.curb.json` project config or `~/.config/curb/config.json` global config from before 1.0, review these changes:

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
**After 1.0:** `~/.config/curb/config.json`

Run `curb-init --global` to set up the new global config location.

### 3. **Log Location Changed**

**Before 1.0:** Logs (if any) location was not standardized
**After 1.0:** Logs at `~/.local/share/curb/logs/{project}/{session}.jsonl`

Logs are now machine-readable JSONL, great for querying with `jq`. Old logs won't be migrated automatically, but new runs will create properly-formatted logs.

### 4. **Hook Directory Structure (New)**

If you have custom hooks from a pre-1.0 version, they need to be moved to the new hook system:

**Before 1.0:** Hooks were project-specific, location varied
**After 1.0:**
- Global hooks: `~/.config/curb/hooks/{hook-name}.d/`
- Project hooks: `.curb/hooks/{hook-name}.d/`

If you have existing hook scripts, move them to the appropriate `hook-name.d/` directory and ensure they're executable.

### 5. **Beads Backend Migration**

If you're using `prd.json` for task management:

```bash
# Preview what would be migrated
curb --migrate-to-beads-dry-run

# Perform migration
curb --migrate-to-beads
```

The JSON backend is still fully supported, so you don't have to migrate if you don't want to.

### 7. **CLI Subcommand Migration**

The curb CLI has been updated to use subcommands for clearer organization. The old flag-based syntax still works but shows deprecation warnings.

**Command Syntax Changes:**

| Old Syntax | New Syntax | Notes |
|------------|------------|-------|
| `curb-init` | `curb init` | Initialize project |
| `curb-init --global` | `curb init --global` | Initialize global config |
| `curb --status` | `curb status` | Show task progress |
| `curb --status --json` | `curb status --json` | JSON output |
| `curb --ready` | `curb run --ready` | List ready tasks |
| `curb --once` | `curb run --once` | Single iteration |
| `curb --plan` | `curb run --plan` | Planning mode |
| `curb -s` | `curb status` | Short flag |
| `curb -r` | `curb run --ready` | Short flag |
| `curb -1` | `curb run --once` | Short flag |
| `curb -p` | `curb run --plan` | Short flag |

**Deprecation Warnings:**

When using the old syntax, curb shows a warning like:
```
[curb] DEPRECATED: --status flag is deprecated. Use 'curb status' instead.
[curb] This flag will be removed in a future release.
```

**Suppressing Warnings:**

If you have scripts using the old syntax and want to suppress warnings temporarily:
```bash
export CURB_NO_DEPRECATION_WARNINGS=1
```

**Timeline:**

- **1.0**: Old syntax works with warnings (current release)
- **1.1**: Old syntax continues to work with warnings
- **2.0**: Old syntax may be removed (announced ahead of time)

**Migration Tips:**

1. Update scripts gradually - the old syntax still works
2. Use tab completion with `curb <TAB>` to discover subcommands
3. Run `curb --help` to see the new command structure
4. Run `curb <subcommand> --help` for subcommand-specific help

**New Help System:**

Each subcommand now has its own help:
```bash
curb --help           # Main help (shows all subcommands)
curb init --help      # Init subcommand help
curb run --help       # Run subcommand help
curb status --help    # Status subcommand help
curb explain --help   # Explain subcommand help
curb artifacts --help # Artifacts subcommand help
```

### 8. **New Required Environment Variables (Mostly Optional)**

Most new environment variables have sensible defaults. The only truly required one for budget control is:

- `CURB_BUDGET` - Set if you want to override config budget

All other environment variables are optional:
- `CURB_BACKEND` - Auto-detects (beads or json)
- `CURB_EPIC`, `CURB_LABEL` - Optional filtering
- `HARNESS` - Auto-detects available harness
- `CURB_STREAM`, `CURB_DEBUG` - Optional debugging flags

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
   curb init --global
   ```

4. **Review and update project config** (if you have `.curb.json`)
   ```bash
   # Check if you have a project config
   cat .curb.json

   # Add missing fields from the new schema
   # See Configuration Schema below
   ```

5. **Test your setup**
   ```bash
   # Run a single iteration to verify everything works
   curb run --once

   # Check logs were created
   ls -la ~/.local/share/curb/logs/your-project/
   ```

6. **Review new features**
   - Try `curb --help` to see new subcommands
   - Consider setting up a hook for notifications
   - Set a budget to prevent overspending

7. **Update scripts using old CLI syntax** (optional but recommended)
   ```bash
   # Find scripts using old syntax
   grep -r "curb --status\|curb --ready\|curb --once\|curb-init" scripts/

   # Update to new syntax:
   #   curb --status  ->  curb status
   #   curb --ready   ->  curb run --ready
   #   curb --once    ->  curb run --once
   #   curb-init      ->  curb init
   ```

8. **Optional: Migrate to beads**
   ```bash
   # Only if you want to switch from JSON to beads backend
   curb --migrate-to-beads
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
| `CURB_PROJECT_DIR` | Project directory | `/path/to/project` |
| `CURB_MAX_ITERATIONS` | Max loop iterations | `50` |
| `HARNESS` | AI harness to use | `claude` or `gemini` |
| `CURB_BACKEND` | Task backend | `beads` or `json` |

### Budget

| Variable | Purpose | Example |
|----------|---------|---------|
| `CURB_BUDGET` | Token budget limit | `1000000` |

### Filtering

| Variable | Purpose | Example |
|----------|---------|---------|
| `CURB_EPIC` | Filter to epic | `curb-1gq` |
| `CURB_LABEL` | Filter to label | `phase-1` |

### Debugging

| Variable | Purpose | Example |
|----------|---------|---------|
| `CURB_DEBUG` | Enable verbose output | `true` |
| `CURB_STREAM` | Stream harness output | `true` |
| `CURB_MODEL` | Claude model | `opus` or `haiku` |

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
curb --budget 1000000          # Set budget limit
```

### Clean State

```bash
curb --require-clean            # Force clean state check
curb --no-require-clean         # Disable clean state check
```

### Filtering

```bash
curb --epic curb-1gq            # Only run tasks in epic
curb --label phase-1            # Only run tasks with label
curb --epic curb-1gq --label phase-1  # Combine filters
```

### Harness Selection

```bash
curb --harness gemini           # Use Gemini harness
curb --harness opencode         # Use OpenCode harness
```

### Output Control

```bash
curb --stream                   # Show real-time output
curb --debug                    # Verbose debugging
curb --dump-prompt              # Save prompts to files
```

### Other

```bash
curb --once                     # Run single iteration
curb --status                   # Show task status
curb --ready                    # Show ready tasks
curb --plan                     # Plan mode
curb --test                     # Test harness
```

## FAQ

### Q: Do I have to migrate from prd.json to beads?

**A:** No, the JSON backend is fully supported. Beads is optional. Only migrate if you prefer beads' UI or need its features.

### Q: Will my old hooks still work?

**A:** If you have hooks, you'll need to move them to the new hook directory structure:
- Global: `~/.config/curb/hooks/{hook-name}.d/`
- Project: `.curb/hooks/{hook-name}.d/`

Then verify they work by running `curb --once` and checking that hooks fire.

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
curb run --once

# Check logs were created
ls ~/.local/share/curb/logs/

# Query logs
jq '.' ~/.local/share/curb/logs/myproject/*.jsonl | head
```

### Q: What if I don't want clean state checking?

**A:** Disable it in config or via flag:
```bash
# Via config
echo '{"clean_state":{"require_commit":false}}' > .curb.json

# Via flag
curb --no-require-clean
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
export CURB_NO_DEPRECATION_WARNINGS=1
```

### Q: What are the new subcommands?

**A:** The main subcommands are:
```bash
curb init       # Initialize project or global config
curb run        # Run the main loop (default if no subcommand)
curb status     # Show task progress
curb explain    # Show task details
curb artifacts  # List task outputs
curb version    # Show version
```

## Getting Help

If you run into issues:

1. **Check README.md** - Comprehensive feature documentation
2. **Review example hooks** - See `examples/hooks/` for patterns
3. **Check logs** - `~/.local/share/curb/logs/` has detailed execution logs
4. **Test with --debug** - `curb --debug --once` shows what's happening
5. **Report issues** - https://github.com/lavallee/curb/issues

## What Stays the Same

The core workflow hasn't changed:

1. **Task management** - Still uses prd.json or beads
2. **Harness invocation** - Still works the same way
3. **Basic loop** - Find ready task → run → loop
4. **Prompt structure** - PROMPT.md and task templates unchanged
5. **Feedback loops** - Type checking, tests, linting still work

You can upgrade gradually and adopt new features at your own pace!

## Next Steps

1. Run `curb init --global` to set up global config
2. Review your project config (if you have one) and update it
3. Try `curb run --once` to verify everything works
4. Explore the new subcommand structure: `curb --help`
5. Read README.md sections on new features you're interested in
6. Set up hooks or budget management if they're useful for you

Welcome to Curb 1.0!
