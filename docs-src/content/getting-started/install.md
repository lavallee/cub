---
title: Installation
description: Install Cub using the one-liner installer, pipx, uv, or from source. Complete setup guide with verification steps.
---

# Installation

Get Cub installed and configured on your system.

## Prerequisites

Before installing Cub, ensure you have:

### Python 3.10+

Cub requires Python 3.10 or later.

```bash
# Check your Python version
python3 --version
```

If you need to install or upgrade Python:

=== "macOS"
    ```bash
    brew install python@3.12
    ```

=== "Ubuntu/Debian"
    ```bash
    sudo apt update
    sudo apt install python3.12 python3.12-venv
    ```

=== "Windows"
    Download from [python.org](https://www.python.org/downloads/) or use:
    ```powershell
    winget install Python.Python.3.12
    ```

### At Least One AI Harness

Cub orchestrates AI coding CLIs but doesn't include them. Install at least one:

| Harness | Install Command | Notes |
|---------|-----------------|-------|
| [Claude Code](https://github.com/anthropics/claude-code) | `npm install -g @anthropic-ai/claude-code` | **Recommended.** Required for `cub prep` |
| [OpenAI Codex](https://github.com/openai/codex) | `npm install -g @openai/codex` | Good for OpenAI ecosystem |
| [Google Gemini](https://github.com/google-gemini-cli) | `npm install -g @google/gemini-cli` | Alternative perspective |
| [OpenCode](https://github.com/opencode) | See project docs | Open-source option |

!!! tip "Claude Code is Required for Prep"
    The `cub prep` pipeline (triage, architect, plan, bootstrap) requires Claude Code. For `cub run`, any harness works.

---

## One-Liner Install (Recommended)

The fastest way to get started:

```bash
curl -LsSf https://docs.cub.tools/install.sh | bash
```

This script will:

1. Install [pipx](https://pypa.github.io/pipx/) if not already present
2. Install Cub via pipx
3. Add Cub to your PATH
4. Run `cub init --global` to set up config directories

After installation, **restart your shell** (or open a new terminal):

```bash
# Verify installation
cub --version
```

!!! info "Upgrading"
    Already have Cub installed? Upgrade with:
    ```bash
    pipx upgrade cub
    ```
    Or simply re-run the installer script.

---

## Alternative Installation Methods

=== "Using pipx (Manual)"

    [pipx](https://pypa.github.io/pipx/) installs Python applications in isolated environments:

    ```bash
    # Install pipx if needed
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath

    # Install Cub
    pipx install git+https://github.com/lavallee/cub.git

    # Set up global config
    cub init --global
    ```

=== "Using uv"

    [uv](https://github.com/astral-sh/uv) is a fast Python package manager:

    ```bash
    # Install uv if needed
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Install Cub as a tool
    uv tool install git+https://github.com/lavallee/cub.git

    # Set up global config
    cub init --global
    ```

=== "From Source (Development)"

    For contributing or running the latest code:

    ```bash
    # Clone the repository
    git clone https://github.com/lavallee/cub ~/tools/cub
    cd ~/tools/cub

    # Install dependencies (using uv)
    uv sync

    # Or using pip
    python3.10 -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"

    # Add to PATH
    export PATH="$HOME/tools/cub/.venv/bin:$PATH"

    # Set up global config
    cub init --global
    ```

    Add the PATH export to your `~/.bashrc` or `~/.zshrc` for persistence.

---

## Verifying Installation

After installation, verify everything is working:

```bash
# Check Cub version
cub --version

# Check available commands
cub --help

# Run diagnostics
cub doctor
```

The `cub doctor` command checks:

- Python version compatibility
- Available harnesses (claude, codex, gemini, opencode)
- Configuration file locations
- Common issues and fixes

!!! warning "Common Issue: Command Not Found"
    If `cub` is not found after installation:

    1. Restart your shell or run `source ~/.bashrc` (or `~/.zshrc`)
    2. Check that `~/.local/bin` is in your PATH
    3. For pipx: run `pipx ensurepath` and restart

---

## Global Setup

After installing Cub, run the global initialization:

```bash
cub init --global
```

This creates:

| Path | Purpose |
|------|---------|
| `~/.config/cub/config.json` | Global configuration |
| `~/.config/cub/hooks/` | Global hook directories |
| `~/.local/share/cub/logs/` | Log storage |
| `~/.cache/cub/` | Cache directory |

### Default Global Configuration

The global config file (`~/.config/cub/config.json`) contains default settings:

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
  "hooks": {
    "enabled": true
  }
}
```

You can edit this file to change defaults for all projects.

---

## Optional: Task Backend

Cub supports two task management backends:

### JSON Backend (Default)

No additional setup needed. Tasks are stored in `prd.json` in your project.

### Beads Backend (Recommended)

For advanced task management with the [beads](https://github.com/steveyegge/beads) CLI:

=== "macOS"
    ```bash
    brew install steveyegge/beads/bd
    ```

=== "Other Platforms"
    See the [beads installation docs](https://github.com/steveyegge/beads#installation)

Cub auto-detects the beads backend when `.beads/` directory exists in your project.

---

## Next Steps

Now that Cub is installed:

1. **[Quick Start](quickstart.md)** - Run your first autonomous session
2. **[Core Concepts](concepts.md)** - Understand prep, run, and task backends
3. **[Configuration](../guide/configuration/index.md)** - Customize Cub for your workflow

---

## Uninstalling

If you need to remove Cub:

=== "pipx"
    ```bash
    pipx uninstall cub
    ```

=== "uv"
    ```bash
    uv tool uninstall cub
    ```

=== "From Source"
    ```bash
    rm -rf ~/tools/cub
    # Remove the PATH entry from your shell config
    ```

To also remove configuration and data:

```bash
rm -rf ~/.config/cub
rm -rf ~/.local/share/cub
rm -rf ~/.cache/cub
```
