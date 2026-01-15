# Cub Troubleshooting Guide

This guide covers common issues you may encounter when using Cub and how to resolve them.

## Table of Contents

- [Installation Problems](#installation-problems)
- [Harness Issues](#harness-issues)
- [Task File Errors](#task-file-errors)
- [Symlink Issues](#symlink-issues)
- [Migration Problems](#migration-problems)
- [Configuration Issues](#configuration-issues)
- [Git and State Issues](#git-and-state-issues)
- [Performance and Budget](#performance-and-budget)
- [Diagnostic Tools](#diagnostic-tools)

---

## Installation Problems

### Problem: "jq not found" or "jq: command not found"

**Symptoms**: Cub fails to start with an error mentioning jq.

**Solution**:
jq is a required dependency for JSON processing. Install it:

```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq

# Other Linux distributions
# Visit https://jqlang.github.io/jq/download/
```

Verify installation:
```bash
jq --version
```

### Problem: "Permission denied" when running cub or cub-init

**Symptoms**: You get a permission error when trying to run `./cub` or `cub` command.

**Solution**:
Make the scripts executable:

```bash
chmod +x cub cub-init
```

If using symlinks in `/usr/local/bin/`, ensure the target files are executable:

```bash
chmod +x ~/tools/cub/cub ~/tools/cub/cub-init
```

### Problem: "cub: command not found" after installation

**Symptoms**: You've installed Cub but can't run it from the command line.

**Solution**:
Ensure Cub is in your PATH. There are two options:

**Option 1: Add to PATH (recommended)**
```bash
export PATH="$PATH:$HOME/tools/cub"
```
Add this line to your `~/.bashrc`, `~/.zshrc`, or equivalent shell config file.

**Option 2: Create symlinks**
```bash
ln -s $HOME/tools/cub/cub /usr/local/bin/cub
ln -s $HOME/tools/cub/cub-init /usr/local/bin/cub-init
```

Verify Cub is accessible:
```bash
cub --version
```

### Problem: "Bash 3.2+" requirement not met

**Symptoms**: Cub exits with an error about Bash version.

**Solution**:
Cub requires Bash 3.2 or later. Check your version:

```bash
bash --version
```

**On macOS**: macOS ships with older Bash due to licensing. Install a newer version:

```bash
brew install bash
```

Then update your shell:
```bash
sudo chsh -s /usr/local/bin/bash $USER
```

---

## Harness Issues

### Problem: "No harness available" or "Error: No harness available"

**Symptoms**: Cub starts but can't find an AI harness to use.

**Solution**:
You need at least one harness installed. Options are:

1. **Claude Code (recommended)**
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

2. **OpenAI Codex**
   ```bash
   npm install -g openai-codex-cli
   ```

3. **Google Gemini**
   ```bash
   npm install -g @google/gemini-cli
   ```

4. **OpenCode**
   ```bash
   npm install -g opencode
   ```

Verify installation:
```bash
which claude          # for Claude Code
which codex           # for Codex
which gemini-cli      # for Gemini
which opencode        # for OpenCode
```

### Problem: "harness not found: claude" (or other harness)

**Symptoms**: Cub can't find a specific harness you've configured.

**Diagnosis**:
Run the doctor command to check harness availability:

```bash
cub doctor
```

This will show which harnesses are installed and which are missing.

**Solution**:

1. **Install the missing harness** (see options above)
2. **Or change the configured harness** in `.cub.json`:
   ```bash
   # View current config
   cat .cub.json
   ```

3. **Or use a different harness at runtime**:
   ```bash
   cub run --harness codex
   ```

### Problem: Harness invocation fails or times out

**Symptoms**: Cub starts but the harness (Claude Code, etc.) fails or doesn't respond.

**Diagnosis**:
Enable debug logging to see what's happening:

```bash
cub run --debug
```

This will show:
- The exact command being invoked
- Environment variables
- Harness output and errors

**Common causes**:

1. **Authentication issues**: Ensure your harness has valid credentials
   - For Claude Code: Check `.anthropic.json` or environment variables
   - For other harnesses: Check their documentation for auth setup

2. **Network issues**: Harnesses need internet access. Check your connection.

3. **Rate limiting**: If running many iterations, you may hit rate limits. Add a delay:
   ```bash
   cub run --once
   # Wait a bit
   cub run --once
   ```

---

## Task File Errors

### Problem: "prd.json missing 'tasks' array"

**Symptoms**: Cub fails with an error about your task file format.

**Solution**:
Your `prd.json` must have a `tasks` array. Minimal valid format:

```json
{
  "tasks": [
    {
      "id": "task-1",
      "title": "First task",
      "description": "What to do",
      "status": "open"
    }
  ]
}
```

Complete task structure:
```json
{
  "id": "task-1",
  "title": "Task title",
  "description": "Detailed description",
  "status": "open",              // open, in_progress, completed, blocked
  "priority": 2,                 // 0-4 (0=critical, 4=backlog)
  "epic": "epic-id",            // optional
  "labels": ["label1"],         // optional
  "dependencies": [],           // optional
  "acceptance_criteria": []     // optional
}
```

### Problem: "Invalid/Duplicate task IDs found"

**Symptoms**: Error about duplicate IDs in your task file.

**Solution**:
Each task must have a unique `id`. Fix duplicates:

```bash
# Find duplicates
jq '.tasks | group_by(.id) | map(select(length > 1))' prd.json
```

Then rename conflicting IDs to be unique.

### Problem: "Invalid dependency references"

**Symptoms**: Error about tasks referencing non-existent dependencies.

**Solution**:
Each dependency must reference an existing task ID. Check your dependencies:

```bash
# List all task IDs
jq '.tasks[].id' prd.json

# Check dependencies
jq '.tasks[] | select(.dependencies) | {id, dependencies}' prd.json
```

Ensure all referenced IDs exist and match exactly (case-sensitive).

### Problem: Task file not found or can't be read

**Symptoms**: "prd.json not found" or "Permission denied"

**Solution**:

1. **Verify file exists**:
   ```bash
   ls -la prd.json
   ```

2. **If missing, initialize a project**:
   ```bash
   cub init
   ```

3. **If permission denied**, fix permissions:
   ```bash
   chmod 644 prd.json
   ```

---

## Symlink Issues

### Problem: "Cannot resolve symlinks" or AGENT.md/PROMPT.md not found

**Symptoms**: Cub can't find configuration files in legacy layout.

**Background**: Cub supports two layouts:
- **New**: `.cub/agent.md`, `.cub/prompt.md`, `.cub/progress.txt`
- **Legacy**: `AGENT.md` (symlink to `.cub/agent.md`), `PROMPT.md` symlink, etc.

**Solution**:

1. **Check what layout you have**:
   ```bash
   ls -la AGENT.md PROMPT.md
   ```
   - If symlinks (shows `->` in output), you're using legacy layout
   - If files or missing, you're using new layout

2. **For legacy layout**, create symlinks:
   ```bash
   cd /your/project
   ln -s .cub/agent.md AGENT.md
   ln -s .cub/prompt.md PROMPT.md
   ln -s .cub/progress.txt progress.txt
   ln -s .cub/fix_plan.md fix_plan.md
   ```

3. **Verify symlinks point to correct targets**:
   ```bash
   # Should show: AGENT.md -> .cub/agent.md
   ls -la AGENT.md
   ```

4. **If symlinks are broken**, regenerate them:
   ```bash
   rm -f AGENT.md PROMPT.md progress.txt fix_plan.md
   # Then recreate symlinks from step 2
   ```

5. **Run doctor to validate**:
   ```bash
   cub doctor
   ```
   Will show: `[OK] Symlinks` or `[XX] Broken symlinks`

---

## Migration Problems

### Problem: "Cannot migrate: prd.json not found"

**Symptoms**: You want to migrate from prd.json to beads but get an error.

**Solution**:
You need a valid `prd.json` to migrate. If you don't have one:

```bash
# Create a minimal prd.json
cat > prd.json << 'EOF'
{
  "tasks": [
    {
      "id": "task-1",
      "title": "Example task",
      "description": "A task to migrate",
      "status": "open"
    }
  ]
}
EOF
```

Then attempt migration:
```bash
cub --migrate-to-beads-dry-run  # Preview changes
cub --migrate-to-beads           # Execute migration
```

### Problem: Beads backend errors after migration

**Symptoms**: After migrating to beads, you get "beads not installed" errors.

**Solution**:
Beads CLI is required for the beads backend. Install it:

```bash
# Using npm
npm install -g @steveyegge/beads

# Or download from GitHub
# https://github.com/steveyegge/beads
```

Verify installation:
```bash
bd --version
```

If beads isn't available, Cub will automatically fall back to JSON backend with a warning.

### Problem: ".beads/ directory missing" or "Run 'bd init' first"

**Symptoms**: You're using beads backend but the `.beads/` directory wasn't initialized.

**Solution**:
Initialize beads in your project:

```bash
bd init
```

This creates:
- `.beads/` directory
- `.beads/issues.jsonl` task database
- `.beads/.gitignore` to exclude internal files

### Problem: Corrupted .beads/issues.jsonl

**Symptoms**: Beads errors about invalid JSON or corrupted data.

**Diagnosis**:
Validate the file:

```bash
# Check if it's valid JSON lines
cat .beads/issues.jsonl | jq . 2>&1 | head -20
```

**Solution**:

1. **Backup the corrupted file**:
   ```bash
   cp .beads/issues.jsonl .beads/issues.jsonl.bak
   ```

2. **Reinitialize beads** (this may lose data):
   ```bash
   rm -rf .beads
   bd init
   ```

3. **Or manually repair** (advanced):
   - Edit `.beads/issues.jsonl` to fix invalid JSON
   - Ensure each line is a valid JSON object
   - No trailing commas
   - Properly escaped strings

---

## Configuration Issues

### Problem: "Failed to parse user config" or "Failed to parse project config"

**Symptoms**: Cub warns about invalid configuration files.

**Cause**: Your `.cub.json` or `~/.config/cub/config.json` has invalid JSON.

**Solution**:

1. **Validate JSON syntax**:
   ```bash
   # Project config
   jq . .cub.json

   # Global config
   jq . ~/.config/cub/config.json
   ```

2. **Fix errors** (common issues):
   - Trailing commas: `{"key": "value",}` → `{"key": "value"}`
   - Unquoted keys: `{key: "value"}` → `{"key": "value"}`
   - Single quotes: `{'key': 'value'}` → `{"key": "value"}`

3. **Use an online JSON validator** if unsure:
   - https://jsonlint.com/

### Problem: "unknown CUB_BACKEND" or invalid backend

**Symptoms**: Error about unrecognized backend option.

**Solution**:
Valid backends are:
- `beads` - Use beads CLI (.beads/issues.jsonl)
- `json` - Use prd.json file

Set backend in config or CLI:

```bash
# CLI override
cub run --backend json

# Or in .cub.json
{
  "backend": "json"
}
```

### Problem: Budget limit exceeded

**Symptoms**: Cub stops with "Budget exceeded" message.

**Solution**:

1. **Check current budget usage**:
   ```bash
   cub status
   ```
   Shows token usage so far.

2. **Increase budget** for next run:
   ```bash
   cub run --budget 1000000
   ```

3. **Or set in config** (~/.config/cub/config.json):
   ```json
   {
     "budget": {
       "limit": 5000000,
       "warn_at": 80
     }
   }
   ```

---

## Git and State Issues

### Problem: "Repository has uncommitted changes"

**Symptoms**: Cub refuses to proceed because you have modified files.

**Diagnosis**:
See what's changed:

```bash
git status
git diff
```

**Solution**:

1. **Commit changes**:
   ```bash
   git add .
   git commit -m "Save work"
   ```

2. **Or stash them**:
   ```bash
   git stash
   ```

3. **Or disable clean state check** in `.cub.json`:
   ```json
   {
     "clean_state": {
       "require_commit": false
     }
   }
   ```

### Problem: "Not in a git repository"

**Symptoms**: Error about git operations failing.

**Solution**:
Initialize git in your project:

```bash
git init
git add .
git commit -m "Initial commit"
```

### Problem: Branch creation fails or "branch already exists"

**Symptoms**: Cub can't create a work branch.

**Solution**:

1. **Check existing branches**:
   ```bash
   git branch -a
   ```

2. **Delete old branches** if needed:
   ```bash
   git branch -D old-branch-name
   ```

3. **Or use a different session name**:
   ```bash
   cub run --name my-session-name
   ```

### Problem: "Tests failed with exit code X"

**Symptoms**: Clean state verification detects test failures.

**Solution**:

1. **Run tests manually** to see errors:
   ```bash
   npm test        # or yarn test, make test, pytest, etc.
   ```

2. **Fix the failures** in your source code.

3. **Or disable test requirement** in `.cub.json`:
   ```json
   {
     "clean_state": {
       "require_tests": false
     }
   }
   ```

---

## Performance and Budget

### Problem: Cub is slow or tasks take too long

**Symptoms**: Iterations take much longer than expected.

**Diagnosis**:
Enable debug logging to see timing:

```bash
cub run --once --debug
```

Look for timing information in `.cub/logs/` or console output.

**Solutions**:

1. **Run single iterations**:
   ```bash
   cub run --once
   ```
   Instead of looping until completion.

2. **Target specific work**:
   ```bash
   cub run --epic specific-epic
   cub run --label phase-1
   ```

3. **Reduce iteration time** in config:
   ```json
   {
     "iteration_timeout": 300
   }
   ```

### Problem: Token budget warnings or limits hit early

**Symptoms**: "Budget low" warnings or tasks fail due to budget.

**Solution**:

1. **Check budget usage**:
   ```bash
   cub status
   ```

2. **Review large tasks** that consume tokens:
   ```bash
   cub explain task-id
   ```

3. **Split large tasks** into smaller ones.

4. **Increase budget** as needed:
   ```bash
   cub run --budget 10000000
   ```

---

## Diagnostic Tools

### Running cub doctor for comprehensive diagnostics

The `cub doctor` command checks your system configuration and provides detailed diagnostics:

```bash
cub doctor
```

Checks include:
- **System**: Bash version, required tools (jq, git)
- **Harnesses**: Availability of claude, codex, gemini, opencode
- **Configuration**: JSON validity, deprecated options
- **Project Structure**: prd.json or .beads/, agent.md, prompt.md
- **Symlinks**: Correct targets in legacy layout
- **Git State**: Uncommitted changes, branches, merges
- **Tasks**: State validation, stuck tasks, recommendations

### Enabling debug logging

Get detailed information about what Cub is doing:

```bash
cub run --debug
```

Debug output includes:
- Configuration loading
- Harness invocation details
- Task selection logic
- API calls and responses
- File operations

### Checking logs

Structured logs are saved in `.cub/logs/`:

```bash
ls -la .cub/logs/
tail -f .cub/logs/session-*.jsonl
```

Each log line is valid JSON with:
- timestamp
- event_type (task_start, task_end, error, etc.)
- task_id and task_title
- duration_sec
- exit_code (for task_end events)

### Examining task artifacts

Each completed task saves output to `.cub/artifacts/`:

```bash
ls -la .cub/artifacts/
cat .cub/artifacts/task-id/output.txt
```

To list artifacts:

```bash
cub artifacts
cub artifacts task-id
```

---

## Common Error Messages Reference

| Error | Cause | Solution |
|-------|-------|----------|
| `jq: command not found` | jq not installed | Install jq (brew, apt-get, or from jqlang.github.io) |
| `No harness available` | No AI harness installed | Install claude, codex, gemini, or opencode |
| `Not in a git repository` | Working outside git repo | Run `git init && git add . && git commit -m "init"` |
| `prd.json missing 'tasks'` | Invalid task file format | Ensure prd.json has `{"tasks": [...]}` structure |
| `Invalid/Duplicate task IDs` | Duplicate task IDs | Make each task.id unique |
| `Invalid dependency references` | Task references non-existent ID | Verify all dependency IDs exist in tasks array |
| `beads not installed` | Beads CLI missing | Install with `npm install -g @steveyegge/beads` |
| `.beads/ not found` | Not initialized | Run `bd init` in project directory |
| `Repository has uncommitted changes` | Dirty git state | Run `git add . && git commit -m "message"` |
| `Tests failed with exit code X` | Test suite failing | Run tests manually and fix issues |

---

## Getting More Help

If you can't find a solution here:

1. **Run comprehensive diagnostics**:
   ```bash
   cub doctor
   ```

2. **Check structured logs**:
   ```bash
   ls .cub/logs/
   jq . .cub/logs/session-*.jsonl | head -100
   ```

3. **Enable debug mode** for detailed output:
   ```bash
   cub run --debug --once
   ```

4. **Report an issue** on GitHub:
   - https://github.com/anthropics/claude-code/issues
   - Include output from `cub doctor`
   - Include relevant log excerpts
   - Describe steps to reproduce

