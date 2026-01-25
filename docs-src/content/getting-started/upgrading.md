# Upgrading Cub

This guide covers major version upgrades and migration paths.

---

## Upgrading to Cub 0.24+ (Harness Abstraction)

Cub 0.24 introduces a new async harness architecture with support for hooks, custom tools, and the Claude Agent SDK.

### TL;DR

!!! success "Quick Upgrade"

    1. Update cub: `git pull && uv sync`
    2. The default `claude` harness now uses the SDK backend
    3. Use `--harness claude-cli` for the previous behavior
    4. Install `claude-agent-sdk` for hook support (optional)

### What Changed

**New Harness Architecture:**

- All harnesses now use an async interface (`run_task`, `stream_task`)
- Claude backend split into `claude` (SDK) and `claude-cli` (shell-out)
- New capabilities: hooks, custom_tools, sessions

**New Capabilities (Claude SDK only):**

| Capability | Description |
|------------|-------------|
| **hooks** | Event interception for guardrails and circuit breakers |
| **custom_tools** | Register project-specific tools |
| **sessions** | Stateful multi-turn conversations |

### Migration Steps

**1. Update your installation:**

```bash
cd ~/tools/cub
git pull origin main
uv sync
```

**2. (Optional) Install SDK for hooks:**

```bash
pip install claude-agent-sdk
```

**3. Test the new backend:**

```bash
# Uses new SDK backend by default
cub run --once

# Fall back to legacy if needed
cub run --once --harness claude-cli
```

### Breaking Changes

**Harness detection order changed:**

=== "Before (v0.23)"

    ```
    claude > opencode > codex > gemini
    ```

=== "After (v0.24)"

    ```
    claude (SDK) > claude-cli > codex > gemini > opencode
    ```

**Python API changes:**

=== "Before (v0.23)"

    ```python
    from cub.core.harness import get_backend, detect_harness

    backend = get_backend("claude")
    result = backend.invoke(prompt, system)
    ```

=== "After (v0.24)"

    ```python
    from cub.core.harness import get_async_backend, detect_async_harness

    backend = get_async_backend("claude")
    result = await backend.run_task(task_input)
    ```

### Troubleshooting

**"Claude SDK not available"**

Install the SDK or use legacy mode:

```bash
pip install claude-agent-sdk
# or
cub run --harness claude-cli
```

**Hooks not working**

Hooks only work with the SDK backend. Verify you're using `claude`, not `claude-cli`:

```bash
cub run --harness claude  # SDK with hooks
```

---

## Upgrading to Cub 0.21+ (Bash to Python)

Cub 0.21 is a major architectural rewrite that migrates from Bash to Python while maintaining the existing feature set and workflow. This guide explains what changed, why, and how to upgrade.

---

## TL;DR

!!! success "Quick Upgrade"

    If you're upgrading from Bash (v0.20 or earlier):

    1. Ensure you have **Python 3.10+** installed
    2. Install cub: `uv sync` or `pip install -e .`
    3. Update shell PATH: Add `.venv/bin` to your PATH
    4. Test installation: Run `cub --help` to verify
    5. Migrate configuration (if needed): Review `.cub.json` against new schema
    6. **Your tasks remain unchanged**: beads and prd.json continue to work

The core workflow remains identical - the main change is the implementation language and improved performance.

---

## What Changed

### Why Python?

Cub v0.20 (Bash) had limitations:

| Issue | Impact |
|-------|--------|
| **Performance** | Each JSON operation with `jq` spawned a subprocess (~10-50ms overhead) |
| **Maintainability** | Bash is harder to maintain at scale (9,400+ lines) |
| **Features** | Advanced features (dashboards, parallel execution) are difficult in Bash |
| **Ecosystem** | Python has better libraries for CLI, data validation, and testing |

Cub v0.21 (Python) provides:

- **10-50x faster** JSON operations (in-process vs subprocess)
- **Type safety**: Pydantic v2 models with automatic validation
- **Better testing**: pytest framework with comprehensive test suite
- **Modern CLI**: Typer for clean subcommand structure
- **Foundation for future**: Live dashboards, parallel execution, Docker sandboxing

### What Stays the Same

!!! tip "No Learning Curve"

    If you're already using cub, the workflow is unchanged:

1. **Task management**: beads and prd.json backends work identically
2. **Configuration**: `.cub.json` and `~/.config/cub/` still work
3. **Harnesses**: Claude Code, Codex, Gemini, OpenCode all supported
4. **Hooks**: `~/.config/cub/hooks/` directory structure unchanged
5. **Core loop**: Task selection -> prompt generation -> harness execution -> commit
6. **Workflow**: `cub run`, `cub status`, `cub init --global` all work the same

### What's New

- **Python 3.10+ requirement**: No more Bash 3.2
- **Faster performance**: Eliminates jq subprocess overhead
- **Better error messages**: Pydantic validation catches config errors early
- **Improved CLI help**: Subcommand structure with auto-generated help
- **Type safety**: Full type hints and mypy strict mode
- **Better testing**: 100+ pytest tests with >80% coverage
- **Foundation for future**: Architecture designed for dashboards and parallel execution

---

## Breaking Changes

### 1. Bash Compatibility No Longer Available

=== "Before (v0.20)"

    ```bash
    ./cub --once
    ```

=== "After (v0.21)"

    ```bash
    cub run --once  # Python-based, must use `cub` command
    ```

!!! note "Need the Bash version?"

    You can still access it:
    ```bash
    git checkout bash-legacy  # Switch to Bash version
    git checkout main         # Switch back to Python version
    ```

### 2. Python 3.10+ Required

The new version requires Python 3.10 or higher.

**Check your version:**

```bash
python3 --version
```

**Install Python 3.10+:**

=== "macOS"

    ```bash
    brew install python@3.10
    ```

=== "Ubuntu/Debian"

    ```bash
    sudo apt-get install python3.10
    ```

=== "pyenv"

    ```bash
    pyenv install 3.10
    pyenv global 3.10
    ```

### 3. Virtual Environment Required

Python version requires a virtual environment in the project.

**Initialize:**

```bash
cd ~/tools/cub
uv sync  # Creates .venv automatically
```

**Add to shell config:**

```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/tools/cub/.venv/bin:$PATH"
```

### 4. No More Bash Dependencies

!!! success "Simplified Dependencies"

    **No longer needed:**

    - `jq` (JSON processing now in-process)
    - `bash` 3.2 compatibility concerns

    **Still required:**

    - `git` (for repository operations)
    - Claude Code, Codex, or another harness CLI

### 5. Configuration Format

Config files (`.cub.json`, `~/.config/cub/config.json`) remain compatible, but new fields are available:

=== "Old config (still works)"

    ```json
    {
      "harness": {
        "default": "claude"
      }
    }
    ```

=== "New recommended config"

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

---

## Step-by-Step Upgrade Guide

### 1. Backup (Optional)

```bash
cd ~/tools/cub
git status  # Ensure clean state
git branch backup/v0.20  # Create backup branch
```

### 2. Update Cub

```bash
cd ~/tools/cub
git pull origin main
```

### 3. Install Python Dependencies

=== "Using uv (recommended)"

    ```bash
    uv sync
    ```

=== "Using pip"

    ```bash
    python3.10 -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    ```

### 4. Update Shell Configuration

Add to `~/.bashrc`, `~/.zshrc`, or equivalent:

```bash
# Cub Python CLI
export PATH="$HOME/tools/cub/.venv/bin:$PATH"
```

Then reload:

```bash
source ~/.bashrc  # or ~/.zshrc
```

### 5. Verify Installation

```bash
# Should show Python version and subcommands
cub --version
cub --help

# Should work as before
cd your-project
cub run --once
```

### 6. Run Quality Checks (Optional)

```bash
# Type checking
mypy src/cub

# Tests
pytest tests/ -v

# Linting
ruff check src/
```

### 7. Update Documentation Files

Review your project's `CLAUDE.md` or `AGENT.md`:

- Update build/test commands to use Python tools
- Update prerequisite documentation
- Update example commands

---

## Common Migration Issues

### "cub: command not found"

!!! failure "Cause"
    Virtual environment not on PATH

!!! success "Fix"
    ```bash
    # Check if .venv exists
    ls ~/tools/cub/.venv

    # Add to PATH
    export PATH="$HOME/tools/cub/.venv/bin:$PATH"

    # Reload shell
    source ~/.bashrc
    ```

### "Python 3.10+ required"

!!! failure "Cause"
    Python version too old

!!! success "Fix"
    ```bash
    # Check version
    python3 --version

    # Install newer version
    brew install python@3.10  # macOS
    # or
    sudo apt-get install python3.10  # Ubuntu
    ```

### Configuration validation error

!!! failure "Cause"
    Invalid configuration format in `.cub.json`

!!! success "Fix"
    ```bash
    # Remove or fix .cub.json
    rm .cub.json

    # Run init to generate valid config
    cub init --global
    ```

### Harness not found

!!! failure "Cause"
    Claude Code or other harness not installed

!!! success "Fix"
    ```bash
    # Check if Claude Code is installed
    which claude

    # Install Claude Code
    # Follow https://github.com/anthropics/claude-code

    # Or specify different harness
    cub run --harness opencode
    ```

---

## Rollback

If you need to revert to Bash version:

```bash
cd ~/tools/cub
git checkout bash-legacy
git checkout v0.20  # Or specific tag

# Remove Python virtual environment if desired
rm -rf .venv
```

---

## Performance Improvements

Python v0.21 is significantly faster than Bash v0.20:

| Operation | Bash v0.20 | Python v0.21 | Improvement |
|-----------|-----------|--------------|-------------|
| Task selection | ~50ms | ~1ms | **50x faster** |
| Config loading | ~200ms | ~5ms | **40x faster** |
| Status display | ~100ms | ~2ms | **50x faster** |
| Single iteration | ~500ms | ~50ms | **10x faster** |

**Real-world impact:**

- **100 tasks**: v0.20 (50s setup) -> v0.21 (5s setup)
- **Loop of 10**: v0.20 (5s overhead) -> v0.21 (50ms overhead)

---

## FAQ

### Will my beads tasks be migrated automatically?

No migration needed! Your `.beads/issues.jsonl` works exactly as before. Both Bash and Python versions read the same task format.

### Can I still use prd.json?

Yes, JSON backend is still supported. Beads is now recommended for new projects.

### Do I need to update my configuration?

No, old configs still work. New fields have sensible defaults. Only update if you want new features like budget management or hooks.

### Will my hooks still work?

Yes! Hook location (`~/.config/cub/hooks/`) and format are unchanged. Just verify they're executable:

```bash
chmod +x ~/.config/cub/hooks/post-task.d/*.sh
```

### What if I have custom hooks or scripts?

Update any references from `cub` command to use new Python version. Main changes:

| Old Command | New Command |
|-------------|-------------|
| `cub --status` | `cub status` |
| `cub --once` | `cub run --once` |
| `./cub-init` | `cub init` |

### Is the core loop the same?

Yes, completely identical. Task selection, prompt generation, harness execution, and commit workflow are unchanged.

### Is there a performance regression?

No, quite the opposite! v0.21 is 10-50x faster due to eliminating jq subprocess overhead.

---

## Getting Help

If you run into issues:

1. **Check error message**: Python errors are usually more descriptive than Bash
2. **Run in debug mode**: `cub run --debug` shows what's happening
3. **Check logs**: `~/.local/share/cub/logs/` has detailed execution logs
4. **Report issue**: [GitHub Issues](https://github.com/lavallee/cub/issues)

---

## What's Next

After v0.21, planned releases include:

| Version | Feature |
|---------|---------|
| v0.22 | Live dashboard with progress visualization |
| v0.23 | Hybrid CLI (Python + Bash delegation) |
| v0.24 | Git worktrees for parallel development |
| v0.25 | Docker-based sandboxing |
| v0.26 | Captures system for idea management |

All of these build on v0.21's Python foundation!
