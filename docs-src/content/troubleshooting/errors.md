---
title: Error Reference
description: Complete reference of Cub error messages with causes and solutions.
---

# Error Reference

This page provides a comprehensive reference of error messages you may encounter when using Cub, organized by category.

---

## Installation Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `jq: command not found` | jq is not installed | Install jq: `brew install jq` (macOS) or `apt-get install jq` (Ubuntu) |
| `Permission denied` | Script not executable | Run `chmod +x cub cub-init` |
| `cub: command not found` | Cub not in PATH | Add to PATH or create symlinks in `/usr/local/bin/` |
| `Bash 3.2+ required` | Bash version too old | Install newer Bash: `brew install bash` |
| `Python 3.10+ required` | Python version too old | Install Python 3.10+ from python.org or via pyenv |

---

## Harness Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `No harness available` | No AI CLI installed | Install at least one: claude, codex, gemini, or opencode |
| `harness not found: <name>` | Specific harness not installed | Install the harness or use a different one: `--harness <other>` |
| `Harness invocation failed` | Authentication or network error | Check credentials and network; run with `--debug` for details |
| `Harness timeout` | Response took too long | Increase timeout in config or check harness status |
| `Invalid harness response` | Harness returned unexpected output | Update harness to latest version; report as bug if persists |

---

## Task File Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `prd.json not found` | Task file missing | Run `cub init` or create prd.json manually |
| `prd.json missing 'tasks' array` | Invalid task file structure | Ensure file has `{"tasks": [...]}` structure |
| `Invalid/Duplicate task IDs found` | Multiple tasks with same ID | Make each task `id` unique |
| `Invalid dependency references` | Dependency references missing ID | Verify all dependency IDs exist in tasks array |
| `Task file permission denied` | Cannot read task file | Run `chmod 644 prd.json` |
| `Invalid JSON in task file` | Malformed JSON | Validate with `jq . prd.json` and fix syntax |

---

## Beads Backend Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `beads not installed` | bd CLI not found | Install with `npm install -g @steveyegge/beads` |
| `.beads/ not found` | Beads not initialized | Run `bd init` in project directory |
| `Run 'bd init' first` | Missing beads directory | Run `bd init` |
| `Invalid JSON in issues.jsonl` | Corrupted task database | Backup and reinitialize: `cp .beads/issues.jsonl .bak && rm -rf .beads && bd init` |
| `bd command failed` | General beads error | Check `bd` output directly; may need to update beads |

---

## Configuration Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Failed to parse user config` | Invalid JSON in global config | Validate `~/.config/cub/config.json` with `jq` |
| `Failed to parse project config` | Invalid JSON in project config | Validate `.cub.json` with `jq` |
| `unknown CUB_BACKEND` | Invalid backend name | Use `beads` or `json` |
| `unknown harness` | Invalid harness name | Use `claude`, `codex`, `gemini`, or `opencode` |
| `Config key deprecated` | Using old config format | Check [Upgrading](../getting-started/upgrading.md) for migration |
| `Missing required config` | Required field not set | Add missing field to config file |

---

## Git and State Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Not in a git repository` | Working outside git repo | Run `git init && git add . && git commit -m "init"` |
| `Repository has uncommitted changes` | Dirty git state | Commit or stash changes before running |
| `Branch already exists` | Work branch name conflict | Delete old branch or use `--name <unique-name>` |
| `Cannot create branch` | Git branch operation failed | Check `git status` and resolve conflicts |
| `Merge conflict detected` | Conflicting changes | Resolve conflicts manually, then commit |
| `Remote not found` | Git remote not configured | Run `git remote add origin <url>` |
| `Push failed` | Cannot push to remote | Check remote permissions and authentication |

---

## Clean State Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Tests failed with exit code X` | Test suite failing | Run tests manually and fix failures |
| `Build failed` | Build command failed | Run build manually and fix errors |
| `Lint errors detected` | Code style issues | Run linter and fix issues |
| `Type check failed` | Type errors in code | Run type checker and fix issues |

!!! tip "Disabling Clean State Checks"
    You can disable individual checks in `.cub.json`:
    ```json
    {
      "clean_state": {
        "require_commit": false,
        "require_tests": false,
        "require_build": false
      }
    }
    ```
    Use with caution - these checks exist to prevent issues.

---

## Budget and Performance Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Budget exceeded` | Token limit reached | Increase budget: `--budget <amount>` or in config |
| `Budget warning at X%` | Approaching limit | Monitor usage; consider increasing limit |
| `Iteration limit reached` | Max iterations hit | Increase with `--iterations <n>` |
| `Timeout exceeded` | Task ran too long | Increase `iteration_timeout` in config |

---

## Symlink Errors (Legacy Layout)

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Cannot resolve symlinks` | Broken symlinks | Recreate symlinks to `.cub/` files |
| `AGENT.md not found` | Missing agent file | Create `.cub/agent.md` and symlink |
| `PROMPT.md not found` | Missing prompt file | Create `.cub/prompt.md` and symlink |
| `Symlink target missing` | `.cub/` file deleted | Recreate the target file |

---

## Migration Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Cannot migrate: prd.json not found` | No task file to migrate | Create prd.json first |
| `Migration failed: invalid task` | Task format incompatible | Fix task format issues before migrating |
| `Migration incomplete` | Partial migration | Check logs and retry |

---

## Hook Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Hook script not found` | Missing hook file | Create the hook script or remove from config |
| `Hook script not executable` | Permission issue | Run `chmod +x <hook-script>` |
| `Hook failed with exit code X` | Hook script error | Debug hook script; check logs |
| `Hook timeout` | Hook ran too long | Optimize hook or increase timeout |

---

## Exit Codes

Cub uses standard exit codes to indicate different outcomes:

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| `0` | Success | No action needed |
| `1` | General error | Check error message for details |
| `2` | Configuration error | Fix config files |
| `3` | Task file error | Fix task file issues |
| `4` | Harness error | Check harness installation and auth |
| `5` | Git state error | Fix git state (commit, resolve conflicts) |
| `6` | Budget exceeded | Increase budget or wait for reset |
| `7` | Clean state failed | Fix tests, build, or lint issues |
| `130` | Interrupted (Ctrl+C) | User cancelled - no action needed |

---

## Debugging Tips

When you encounter an error, follow these steps:

### 1. Enable Debug Mode

```bash
cub run --debug --once 2>&1 | tee debug.log
```

### 2. Run Doctor

```bash
cub doctor
```

### 3. Check Logs

```bash
# View recent logs
tail -100 .cub/logs/session-*.jsonl | jq .

# Find errors
jq 'select(.level == "error")' .cub/logs/session-*.jsonl
```

### 4. Validate Files

```bash
# Check config
jq . .cub.json

# Check tasks (JSON backend)
jq . prd.json

# Check tasks (beads backend)
bd list
```

### 5. Report Issue

If the error persists, [open an issue](https://github.com/lavallee/cub/issues/new) with:

- Full error message
- Output from `cub doctor`
- Debug logs
- Steps to reproduce
