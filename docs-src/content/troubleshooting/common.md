---
title: Common Issues
description: Solutions to frequent problems with Cub installation, harnesses, tasks, and git.
---

# Common Issues

This page covers the most frequent issues users encounter and how to resolve them.

---

## Installation Problems

### jq not found

??? failure "Error: `jq: command not found`"

    **Symptoms**: Cub fails to start with an error mentioning jq.

    **Cause**: jq is a required dependency for JSON processing but isn't installed.

    **Solution**: Install jq for your platform:

    === "macOS"
        ```bash
        brew install jq
        ```

    === "Ubuntu/Debian"
        ```bash
        sudo apt-get install jq
        ```

    === "Fedora/RHEL"
        ```bash
        sudo dnf install jq
        ```

    === "Windows"
        ```powershell
        choco install jq
        # Or download from jqlang.github.io/jq/download/
        ```

    Verify installation:
    ```bash
    jq --version
    ```

### Permission denied

??? failure "Error: `Permission denied` when running cub"

    **Symptoms**: You get a permission error when trying to run `cub` or `cub-init`.

    **Cause**: The script files don't have execute permissions.

    **Solution**: Make the scripts executable:

    ```bash
    chmod +x cub cub-init
    ```

    If using symlinks in `/usr/local/bin/`, ensure the target files are executable:

    ```bash
    chmod +x ~/tools/cub/cub ~/tools/cub/cub-init
    ```

### Command not found after installation

??? failure "Error: `cub: command not found`"

    **Symptoms**: You've installed Cub but can't run it from the command line.

    **Cause**: Cub isn't in your PATH.

    **Solution**: Choose one of these options:

    === "Add to PATH (recommended)"
        Add this line to your shell config (`~/.bashrc`, `~/.zshrc`, etc.):
        ```bash
        export PATH="$PATH:$HOME/tools/cub"
        ```
        Then reload your shell:
        ```bash
        source ~/.bashrc  # or ~/.zshrc
        ```

    === "Create symlinks"
        ```bash
        sudo ln -s $HOME/tools/cub/cub /usr/local/bin/cub
        sudo ln -s $HOME/tools/cub/cub-init /usr/local/bin/cub-init
        ```

    Verify Cub is accessible:
    ```bash
    cub --version
    ```

### Bash version requirement

??? failure "Error: Bash 3.2+ requirement not met"

    **Symptoms**: Cub exits with an error about Bash version.

    **Cause**: Your system has an older version of Bash.

    **Solution**: Check your Bash version:

    ```bash
    bash --version
    ```

    On macOS (which ships with older Bash due to licensing):

    ```bash
    # Install newer Bash
    brew install bash

    # Optionally set as default shell
    sudo chsh -s /usr/local/bin/bash $USER
    ```

---

## Harness Issues

### No harness available

??? failure "Error: `No harness available`"

    **Symptoms**: Cub starts but can't find an AI harness to use.

    **Cause**: No AI coding CLI is installed on your system.

    **Solution**: Install at least one harness:

    === "Claude Code (recommended)"
        ```bash
        npm install -g @anthropic-ai/claude-code
        ```

    === "OpenAI Codex"
        ```bash
        npm install -g openai-codex-cli
        ```

    === "Google Gemini"
        ```bash
        npm install -g @google/gemini-cli
        ```

    === "OpenCode"
        ```bash
        npm install -g opencode
        ```

    Verify installation:
    ```bash
    which claude codex gemini-cli opencode
    ```

### Specific harness not found

??? failure "Error: `harness not found: claude` (or other harness name)"

    **Symptoms**: Cub can't find a specific harness you've configured.

    **Cause**: The configured harness isn't installed or not in PATH.

    **Solution**:

    1. **Diagnose with doctor**:
       ```bash
       cub doctor
       ```
       This shows which harnesses are installed and which are missing.

    2. **Install the missing harness** (see options above)

    3. **Or change the configured harness** in `.cub.json`:
       ```json
       {
         "harness": {
           "priority": ["codex", "claude"]
         }
       }
       ```

    4. **Or use a different harness at runtime**:
       ```bash
       cub run --harness codex
       ```

### Harness invocation fails or times out

??? failure "Harness fails silently or times out"

    **Symptoms**: Cub starts but the harness doesn't respond or fails.

    **Cause**: Various - authentication, network, or rate limiting issues.

    **Solution**:

    Enable debug logging to see what's happening:
    ```bash
    cub run --debug
    ```

    **Common causes and fixes**:

    === "Authentication"
        Ensure your harness has valid credentials:

        - **Claude Code**: Check `~/.anthropic/credentials` or `ANTHROPIC_API_KEY`
        - **Codex**: Check `OPENAI_API_KEY` environment variable
        - **Gemini**: Check Google Cloud authentication
        - **OpenCode**: Check your configured provider's credentials

    === "Network Issues"
        Harnesses need internet access:
        ```bash
        # Test connectivity
        curl -I https://api.anthropic.com
        ```

    === "Rate Limiting"
        If running many iterations, you may hit rate limits:
        ```bash
        # Run single iterations with breaks
        cub run --once
        # Wait a bit between iterations
        ```

---

## Task File Errors

### Missing tasks array

??? failure "Error: `prd.json missing 'tasks' array`"

    **Symptoms**: Cub fails with an error about task file format.

    **Cause**: Your `prd.json` doesn't have the required structure.

    **Solution**: Ensure your `prd.json` has a `tasks` array:

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
      "epic": "epic-id",             // optional
      "labels": ["label1"],          // optional
      "dependencies": [],            // optional
      "acceptance_criteria": []      // optional
    }
    ```

### Duplicate task IDs

??? failure "Error: `Invalid/Duplicate task IDs found`"

    **Symptoms**: Error about duplicate IDs in your task file.

    **Cause**: Multiple tasks have the same `id` value.

    **Solution**: Find and fix duplicates:

    ```bash
    # Find duplicate IDs
    jq '.tasks | group_by(.id) | map(select(length > 1)) | .[].id' prd.json
    ```

    Then edit `prd.json` to make each ID unique.

### Invalid dependency references

??? failure "Error: `Invalid dependency references`"

    **Symptoms**: Error about tasks referencing non-existent dependencies.

    **Cause**: A task's `dependencies` array references an ID that doesn't exist.

    **Solution**: Verify all dependency IDs exist:

    ```bash
    # List all task IDs
    jq '.tasks[].id' prd.json

    # Show tasks with dependencies
    jq '.tasks[] | select(.dependencies) | {id, dependencies}' prd.json
    ```

    Ensure all referenced IDs exist and match exactly (case-sensitive).

### Task file not found

??? failure "Error: `prd.json not found` or `Permission denied`"

    **Symptoms**: Cub can't find or read your task file.

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

## Beads Backend Issues

### Beads not installed

??? failure "Error: `beads not installed`"

    **Symptoms**: After configuring beads backend, you get errors about beads not being installed.

    **Cause**: The Beads CLI isn't installed on your system.

    **Solution**: Install Beads:

    ```bash
    npm install -g @steveyegge/beads
    ```

    Verify installation:
    ```bash
    bd --version
    ```

    !!! note
        If beads isn't available, Cub automatically falls back to the JSON backend with a warning.

### Beads directory missing

??? failure "Error: `.beads/ not found` or `Run 'bd init' first`"

    **Symptoms**: Using beads backend but the `.beads/` directory doesn't exist.

    **Cause**: Beads hasn't been initialized in the project.

    **Solution**: Initialize beads:

    ```bash
    bd init
    ```

    This creates:

    - `.beads/` directory
    - `.beads/issues.jsonl` task database
    - `.beads/.gitignore` to exclude internal files

### Corrupted issues.jsonl

??? failure "Beads errors about invalid JSON or corrupted data"

    **Symptoms**: Beads can't parse the task database.

    **Cause**: The `.beads/issues.jsonl` file has invalid JSON.

    **Solution**:

    1. **Diagnose the issue**:
       ```bash
       # Validate JSON lines format
       cat .beads/issues.jsonl | while read line; do
         echo "$line" | jq . > /dev/null 2>&1 || echo "Invalid: $line"
       done
       ```

    2. **Backup and reinitialize** (may lose data):
       ```bash
       cp .beads/issues.jsonl .beads/issues.jsonl.bak
       rm -rf .beads
       bd init
       ```

    3. **Or manually repair** (advanced):
       - Edit `.beads/issues.jsonl`
       - Ensure each line is valid JSON
       - Remove trailing commas
       - Fix improperly escaped strings

---

## Git and State Issues

### Uncommitted changes

??? failure "Error: `Repository has uncommitted changes`"

    **Symptoms**: Cub refuses to proceed because you have modified files.

    **Cause**: Cub requires a clean git state by default for safety.

    **Solution**:

    === "Commit changes"
        ```bash
        git add .
        git commit -m "Save work before cub run"
        ```

    === "Stash changes"
        ```bash
        git stash
        # Later: git stash pop
        ```

    === "Disable check"
        In `.cub.json`:
        ```json
        {
          "clean_state": {
            "require_commit": false
          }
        }
        ```

    !!! warning
        Disabling the clean state check is not recommended as it can lead to lost work.

### Not in a git repository

??? failure "Error: `Not in a git repository`"

    **Symptoms**: Git operations fail because directory isn't a git repo.

    **Solution**: Initialize git:

    ```bash
    git init
    git add .
    git commit -m "Initial commit"
    ```

### Branch already exists

??? failure "Error: `branch already exists`"

    **Symptoms**: Cub can't create a work branch because it exists.

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
       cub run --name my-unique-session
       ```

### Tests failed

??? failure "Error: `Tests failed with exit code X`"

    **Symptoms**: Clean state verification detects test failures.

    **Cause**: Your test suite is failing.

    **Solution**:

    1. **Run tests manually** to see errors:
       ```bash
       npm test        # or pytest, make test, etc.
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

## Configuration Issues

### Invalid config JSON

??? failure "Error: `Failed to parse user config` or `Failed to parse project config`"

    **Symptoms**: Cub warns about invalid configuration files.

    **Cause**: Your `.cub.json` or global config has invalid JSON.

    **Solution**:

    1. **Validate JSON syntax**:
       ```bash
       # Project config
       jq . .cub.json

       # Global config
       jq . ~/.config/cub/config.json
       ```

    2. **Fix common errors**:

       | Error | Wrong | Correct |
       |-------|-------|---------|
       | Trailing commas | `{"key": "value",}` | `{"key": "value"}` |
       | Unquoted keys | `{key: "value"}` | `{"key": "value"}` |
       | Single quotes | `{'key': 'value'}` | `{"key": "value"}` |

### Unknown backend

??? failure "Error: `unknown CUB_BACKEND`"

    **Symptoms**: Error about unrecognized backend option.

    **Cause**: Invalid backend specified in config or environment.

    **Solution**: Use a valid backend:

    - `beads` - Beads CLI (`.beads/issues.jsonl`)
    - `json` - JSON file (`prd.json`)

    ```bash
    # CLI override
    cub run --backend json

    # Or in .cub.json
    {
      "backend": "json"
    }
    ```

---

## Performance and Budget

### Slow task execution

??? warning "Tasks take much longer than expected"

    **Symptoms**: Iterations take too long.

    **Diagnosis**: Enable debug logging:
    ```bash
    cub run --once --debug
    ```

    **Solutions**:

    1. **Run single iterations**:
       ```bash
       cub run --once
       ```

    2. **Target specific work**:
       ```bash
       cub run --epic specific-epic
       cub run --label phase-1
       ```

    3. **Reduce iteration timeout** in config:
       ```json
       {
         "iteration_timeout": 300
       }
       ```

### Budget exceeded

??? warning "Error: `Budget exceeded`"

    **Symptoms**: Cub stops because token budget was exceeded.

    **Solution**:

    1. **Check current usage**:
       ```bash
       cub status
       ```

    2. **Increase budget** for the run:
       ```bash
       cub run --budget 1000000
       ```

    3. **Or set in config** (`~/.config/cub/config.json`):
       ```json
       {
         "budget": {
           "limit": 5000000,
           "warn_at": 80
         }
       }
       ```

    4. **Split large tasks** to reduce per-task token usage.

---

## Symlink Issues (Legacy Layout)

??? warning "Symlinks to .cub/ files not working"

    **Background**: Cub supports two layouts:

    - **New**: `.cub/agent.md`, `.cub/prompt.md`, `.cub/progress.txt`
    - **Legacy**: `AGENT.md` (symlink to `.cub/agent.md`), etc.

    **Diagnosis**:
    ```bash
    ls -la AGENT.md PROMPT.md
    # Symlinks show: AGENT.md -> .cub/agent.md
    ```

    **Solution**:

    1. **For legacy layout**, create symlinks:
       ```bash
       ln -s .cub/agent.md AGENT.md
       ln -s .cub/prompt.md PROMPT.md
       ln -s .cub/progress.txt progress.txt
       ln -s .cub/fix_plan.md fix_plan.md
       ```

    2. **If symlinks are broken**, recreate them:
       ```bash
       rm -f AGENT.md PROMPT.md progress.txt fix_plan.md
       # Then recreate as above
       ```

    3. **Run doctor to validate**:
       ```bash
       cub doctor
       ```

---

## Migration Problems

### Cannot migrate to beads

??? failure "Error: `Cannot migrate: prd.json not found`"

    **Symptoms**: You want to migrate from prd.json to beads but get an error.

    **Solution**: Create a minimal prd.json first:

    ```bash
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

    Then migrate:
    ```bash
    cub --migrate-to-beads-dry-run  # Preview changes
    cub --migrate-to-beads          # Execute migration
    ```
