#!/usr/bin/env bash
# Cub installer script
# Usage: curl -LsSf https://docs.cub.tools/install.sh | bash
#
# Environment variables:
#   CUB_INSTALL_QUIET=1   - Suppress non-essential output
#   CI=true               - Auto-detected; suppresses prompts
#
# Flags:
#   --quiet               - Same as CUB_INSTALL_QUIET=1
#   --help                - Show usage information

set -u

REPO="lavallee/cub"
MIN_PYTHON="3.10"
CUB_INSTALL_SUCCESS=false

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
CUB_INSTALL_QUIET="${CUB_INSTALL_QUIET:-0}"
for arg in "$@"; do
    case "$arg" in
        --quiet) CUB_INSTALL_QUIET=1 ;;
        --help)
            echo "Usage: curl -LsSf https://docs.cub.tools/install.sh | bash"
            echo ""
            echo "Options:"
            echo "  --quiet   Suppress non-essential output"
            echo "  --help    Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  CUB_INSTALL_QUIET=1   Same as --quiet"
            echo "  CI=true               Suppress interactive prompts"
            exit 0
            ;;
    esac
done

# CI detection — suppress prompts in CI environments
CUB_CI="${CI:-}"

# ---------------------------------------------------------------------------
# Colors via tput (more portable than raw ANSI)
# ---------------------------------------------------------------------------
if [ -t 1 ] && command -v tput >/dev/null 2>&1; then
    RED=$(tput setaf 1 2>/dev/null || true)
    GREEN=$(tput setaf 2 2>/dev/null || true)
    YELLOW=$(tput setaf 3 2>/dev/null || true)
    BLUE=$(tput setaf 4 2>/dev/null || true)
    BOLD=$(tput bold 2>/dev/null || true)
    DIM=$(tput dim 2>/dev/null || true)
    NC=$(tput sgr0 2>/dev/null || true)
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    BOLD=''
    DIM=''
    NC=''
fi

# ---------------------------------------------------------------------------
# Output helpers (prefixed to avoid namespace collisions)
# ---------------------------------------------------------------------------
cub_info()    { echo "${BLUE}==>${NC} ${BOLD}$1${NC}"; }
cub_success() { echo "${GREEN}==>${NC} ${BOLD}$1${NC}"; }
cub_warn()    { echo "${YELLOW}warning:${NC} $1"; }
cub_error()   { echo "${RED}error:${NC} $1" >&2; }
cub_dim()     { [ "$CUB_INSTALL_QUIET" = "1" ] && return; echo "${DIM}    $1${NC}"; }

# ---------------------------------------------------------------------------
# ensure / ignore — replacements for set -e
#
# ensure() runs a command and exits on failure with a clear message.
# ignore() runs a command and swallows failures (for cleanup).
# ---------------------------------------------------------------------------
cub_ensure() {
    if ! "$@"; then
        cub_error "command failed: $*"
        exit 1
    fi
}

cub_ignore() {
    "$@" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Cleanup trap
# ---------------------------------------------------------------------------
cub_cleanup() {
    if [ "$CUB_INSTALL_SUCCESS" = false ]; then
        echo "" >&2
        cub_error "Installation did not complete successfully."
        if [ -n "${LAST_ERROR:-}" ]; then
            echo "Last error: ${LAST_ERROR%%$'\n'*}" >&2
        fi
        echo "See https://github.com/$REPO#installation for manual install instructions." >&2
    fi
}
trap cub_cleanup EXIT

# ---------------------------------------------------------------------------
# Snap curl detection
# Snap-packaged curl has broken HTTPS certificate handling.
# Both rustup and uv detect and reject it.
# ---------------------------------------------------------------------------
cub_check_snap_curl() {
    if command -v curl >/dev/null 2>&1; then
        local curl_path
        curl_path=$(command -v curl)
        if [ -n "${curl_path:-}" ] && [[ "$curl_path" == */snap/* ]]; then
            cub_warn "Detected snap-packaged curl, which may have broken HTTPS support."
            cub_warn "If you encounter TLS errors, install curl via your system package manager:"
            cub_warn "  sudo apt install curl   # or equivalent for your distro"
        fi
    fi
}

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

# Detect shell config file
cub_detect_shell_config() {
    case "$SHELL" in
        */zsh) echo "${ZDOTDIR:-$HOME}/.zshrc" ;;
        */bash)
            if [ -f "$HOME/.bash_profile" ]; then
                echo "$HOME/.bash_profile"
            else
                echo "$HOME/.bashrc"
            fi
            ;;
        */fish) echo "$HOME/.config/fish/config.fish" ;;
        *) echo "$HOME/.profile" ;;
    esac
}

# Check if a command exists
cub_has() { command -v "$1" >/dev/null 2>&1; }

# Compare version strings (returns 0 if $1 >= $2)
cub_version_gte() {
    [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

# Get Python version
cub_python_version() {
    "$1" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null
}

# Find suitable Python
cub_find_python() {
    for cmd in python3 python; do
        if cub_has "$cmd"; then
            echo "$cmd"
            return 0
        fi
    done
    return 1
}

# Add path to shell config
cub_add_to_path() {
    local path_entry="$1"
    local shell_config
    shell_config=$(cub_detect_shell_config)
    local export_line

    # Fish uses different syntax
    if [[ "$shell_config" == *"fish"* ]]; then
        export_line="fish_add_path $path_entry"
    else
        export_line="export PATH=\"$path_entry:\$PATH\""
    fi

    # Check if already in config
    if grep -qF "$path_entry" "$shell_config" 2>/dev/null; then
        return 0
    fi

    # Try to add to config
    if [ -w "$shell_config" ] || [ ! -e "$shell_config" ]; then
        echo "" >> "$shell_config"
        echo "# Added by cub installer" >> "$shell_config"
        echo "$export_line" >> "$shell_config"
        return 0
    else
        return 1
    fi
}

# Track what we tried for error reporting
TRIED_METHODS=()
LAST_ERROR=""

# Try an installation method and capture errors
cub_try_install() {
    local method="$1"
    local cmd="$2"

    TRIED_METHODS+=("$method")

    # Capture both stdout and stderr
    local output
    local exit_code
    output=$(eval "$cmd" 2>&1) && exit_code=0 || exit_code=$?

    if [ $exit_code -eq 0 ]; then
        return 0
    else
        LAST_ERROR="$output"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Existing installation detection
# ---------------------------------------------------------------------------
cub_check_existing() {
    if cub_has cub; then
        local existing_version
        existing_version=$(cub --version 2>/dev/null || echo "unknown")
        cub_info "cub is already installed (${existing_version})"

        if [ -n "$CUB_CI" ]; then
            # In CI, always upgrade without prompting
            cub_info "CI detected, upgrading..."
            return 1  # signal to proceed with install (upgrade)
        fi

        echo ""
        echo "Would you like to upgrade? [Y/n] "
        local reply
        read -r reply < /dev/tty 2>/dev/null || reply="y"
        case "$reply" in
            [nN]*)
                cub_success "Keeping existing installation."
                CUB_INSTALL_SUCCESS=true
                exit 0
                ;;
            *)
                cub_info "Upgrading..."
                return 1  # signal to proceed with install
                ;;
        esac
    fi
    return 1  # not installed, proceed
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
cub_main() {
    echo ""
    echo "${BOLD}Cub Installer${NC}"
    echo "Work ahead of your AI agents, then let them run."
    echo ""

    # Check for snap curl
    cub_check_snap_curl

    # Check for existing installation
    cub_check_existing || true

    # Find Python
    cub_info "Checking for Python..."
    local PYTHON
    PYTHON=$(cub_find_python) || {
        cub_error "Python not found. Please install Python $MIN_PYTHON or later."
        echo ""
        echo "Install Python from: https://www.python.org/downloads/"
        exit 1
    }

    local PYVER
    PYVER=$(cub_python_version "$PYTHON")
    if ! cub_version_gte "$PYVER" "$MIN_PYTHON"; then
        cub_warn "Python $PYVER found, but cub requires $MIN_PYTHON+"
        cub_warn "Continuing anyway, but you may encounter issues."
        echo ""
    else
        cub_success "Found Python $PYVER"
    fi

    # Determine installation method
    local INSTALL_METHOD=""
    local CUB_PATH=""

    # Try 1: pipx (if already available)
    if cub_has pipx; then
        cub_info "Found pipx, installing cub..."
        if pipx install "git+https://github.com/$REPO.git" 2>&1 | grep -q "already seems to be installed"; then
            cub_info "cub already installed via pipx, upgrading..."
            if pipx upgrade cub 2>/dev/null; then
                INSTALL_METHOD="pipx (upgraded)"
            else
                INSTALL_METHOD="pipx (already installed)"
            fi
            CUB_PATH="$HOME/.local/bin"
        elif cub_try_install "pipx" "pipx install 'git+https://github.com/$REPO.git'"; then
            INSTALL_METHOD="pipx"
            CUB_PATH="$HOME/.local/bin"
        else
            cub_dim "pipx install failed: ${LAST_ERROR%%$'\n'*}"
        fi
    fi

    # Try 2: uv tool (if available) - try this BEFORE attempting to install pipx
    if [ -z "$INSTALL_METHOD" ] && cub_has uv; then
        cub_info "Found uv, installing cub..."
        if cub_try_install "uv tool" "uv tool install 'git+https://github.com/$REPO.git'"; then
            INSTALL_METHOD="uv"
            CUB_PATH="$HOME/.local/bin"
        else
            cub_dim "uv tool install failed: ${LAST_ERROR%%$'\n'*}"
        fi
    fi

    # Try 3: Install pipx via pip, then use it
    if [ -z "$INSTALL_METHOD" ]; then
        cub_info "Trying to install pipx..."
        if cub_try_install "pip install pipx" "$PYTHON -m pip install --user pipx"; then
            cub_ignore "$PYTHON" -m pipx ensurepath
            # pipx is now in ~/.local/bin
            local PIPX_CMD="$HOME/.local/bin/pipx"
            if [ -x "$PIPX_CMD" ]; then
                cub_info "Installing cub via pipx..."
                if cub_try_install "pipx (newly installed)" "$PIPX_CMD install 'git+https://github.com/$REPO.git'"; then
                    INSTALL_METHOD="pipx"
                    CUB_PATH="$HOME/.local/bin"
                else
                    cub_dim "pipx install failed: ${LAST_ERROR%%$'\n'*}"
                fi
            else
                cub_dim "pipx installed but not found at $PIPX_CMD"
                TRIED_METHODS+=("pipx (installed but not executable)")
            fi
        else
            cub_dim "Could not install pipx: ${LAST_ERROR%%$'\n'*}"
        fi
    fi

    # Try 4: pip install --user (last resort)
    if [ -z "$INSTALL_METHOD" ]; then
        cub_info "Trying pip install --user..."
        if cub_try_install "pip install --user" "$PYTHON -m pip install --user 'git+https://github.com/$REPO.git'"; then
            INSTALL_METHOD="pip"
            CUB_PATH="$("$PYTHON" -m site --user-base)/bin"
        else
            cub_dim "pip install failed: ${LAST_ERROR%%$'\n'*}"
        fi
    fi

    # Check if installation succeeded
    if [ -z "$INSTALL_METHOD" ]; then
        echo ""
        cub_error "Installation failed after trying: ${TRIED_METHODS[*]}"
        echo ""
        echo "Last error: $LAST_ERROR" | head -5
        echo ""
        echo "${BOLD}Please try one of these manual installation methods:${NC}"
        echo ""

        # Suggest methods based on what's available
        if cub_has pipx; then
            echo "  ${GREEN}pipx (recommended):${NC}"
            echo "    pipx install git+https://github.com/$REPO.git"
            echo ""
        fi

        if cub_has uv; then
            echo "  ${GREEN}uv:${NC}"
            echo "    uv tool install git+https://github.com/$REPO.git"
            echo ""
        fi

        echo "  ${GREEN}pip (in a virtual environment):${NC}"
        echo "    python3 -m venv ~/.cub-venv"
        echo "    ~/.cub-venv/bin/pip install git+https://github.com/$REPO.git"
        echo "    # Then add ~/.cub-venv/bin to your PATH"
        echo ""

        echo "  ${GREEN}pip --user:${NC}"
        echo "    $PYTHON -m pip install --user git+https://github.com/$REPO.git"
        echo ""

        if ! cub_has pipx && ! cub_has uv; then
            echo "  ${GREEN}Install pipx first (recommended):${NC}"
            echo "    # On Ubuntu/Debian:"
            echo "    sudo apt install pipx"
            echo "    pipx ensurepath"
            echo ""
            echo "    # On macOS:"
            echo "    brew install pipx"
            echo "    pipx ensurepath"
            echo ""
            echo "    # Then install cub:"
            echo "    pipx install git+https://github.com/$REPO.git"
            echo ""
        fi

        echo "See: https://github.com/$REPO#installation"
        exit 1
    fi

    cub_success "Installed cub via $INSTALL_METHOD"

    # Add to PATH
    local PATH_ADDED=false
    if [ -n "$CUB_PATH" ]; then
        # Check if already in PATH
        if [[ ":$PATH:" != *":$CUB_PATH:"* ]]; then
            cub_info "Adding $CUB_PATH to PATH..."
            if cub_add_to_path "$CUB_PATH"; then
                PATH_ADDED=true
                # Also add to current session
                export PATH="$CUB_PATH:$PATH"
            else
                cub_warn "Could not add to PATH automatically."
                echo ""
                echo "Add this line to your shell config:"
                echo ""
                echo "  export PATH=\"$CUB_PATH:\$PATH\""
                echo ""
            fi
        fi
    fi

    # Verify installation
    if ! cub_has cub && [ -n "$CUB_PATH" ]; then
        export PATH="$CUB_PATH:$PATH"
    fi

    if ! cub_has cub; then
        cub_warn "cub not found in PATH after installation."
        echo ""
        echo "You may need to restart your shell, or run:"
        echo ""
        echo "  export PATH=\"$CUB_PATH:\$PATH\""
        echo ""
        exit 1
    fi

    # Run global init
    echo ""
    cub_info "Running cub init --global..."
    if cub init --global; then
        cub_success "Global configuration complete"
    else
        cub_warn "Global init had issues, but cub is installed."
        echo "Run 'cub init --global' manually to complete setup."
    fi

    # Mark success before printing final message
    CUB_INSTALL_SUCCESS=true

    # Success message
    echo ""
    echo "${GREEN}============================================${NC}"
    echo "${GREEN}  Cub installed successfully!${NC}"
    echo "${GREEN}============================================${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. cub new my-project     # Create a new project"
    echo "  2. cd my-project"
    echo "  3. cub plan               # Turn ideas into tasks"
    echo "  4. cub run                # Let AI execute"
    echo ""
    if [ "$PATH_ADDED" = true ]; then
        local shell_config
        shell_config=$(cub_detect_shell_config)
        echo "${YELLOW}Note:${NC} Restart your shell or run:"
        echo ""
        echo "  source $shell_config"
        echo ""
    fi
    echo "Documentation: https://github.com/$REPO"
    echo ""
}

cub_main "$@"
