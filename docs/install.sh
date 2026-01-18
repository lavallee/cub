#!/usr/bin/env bash
# Cub installer script
# Usage: curl -LsSf https://docs.cub.tools/install.sh | bash
set -e

REPO="lavallee/cub"
MIN_PYTHON="3.10"

# Colors (disabled if not a tty)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    DIM='\033[2m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    BOLD=''
    DIM=''
    NC=''
fi

info() { echo -e "${BLUE}==>${NC} ${BOLD}$1${NC}"; }
success() { echo -e "${GREEN}==>${NC} ${BOLD}$1${NC}"; }
warn() { echo -e "${YELLOW}warning:${NC} $1"; }
error() { echo -e "${RED}error:${NC} $1" >&2; }
dim() { echo -e "${DIM}    $1${NC}"; }

# Detect shell config file
detect_shell_config() {
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
has() { command -v "$1" >/dev/null 2>&1; }

# Compare version strings (returns 0 if $1 >= $2)
version_gte() {
    [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

# Get Python version
python_version() {
    "$1" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null
}

# Find suitable Python
find_python() {
    for cmd in python3 python; do
        if has "$cmd"; then
            echo "$cmd"
            return 0
        fi
    done
    return 1
}

# Add path to shell config
add_to_path() {
    local path_entry="$1"
    local shell_config
    shell_config=$(detect_shell_config)
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
try_install() {
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

main() {
    echo ""
    echo -e "${BOLD}Cub Installer${NC}"
    echo -e "Work ahead of your AI agents, then let them run."
    echo ""

    # Find Python
    info "Checking for Python..."
    PYTHON=$(find_python) || {
        error "Python not found. Please install Python $MIN_PYTHON or later."
        echo ""
        echo "Install Python from: https://www.python.org/downloads/"
        exit 1
    }

    PYVER=$(python_version "$PYTHON")
    if ! version_gte "$PYVER" "$MIN_PYTHON"; then
        warn "Python $PYVER found, but cub requires $MIN_PYTHON+"
        warn "Continuing anyway, but you may encounter issues."
        echo ""
    else
        success "Found Python $PYVER"
    fi

    # Determine installation method
    INSTALL_METHOD=""
    CUB_PATH=""

    # Try 1: pipx (if already available)
    if has pipx; then
        info "Found pipx, installing cub..."
        if pipx install "git+https://github.com/$REPO.git" 2>&1 | grep -q "already seems to be installed"; then
            info "cub already installed via pipx, upgrading..."
            if pipx upgrade cub 2>/dev/null; then
                INSTALL_METHOD="pipx (upgraded)"
            else
                INSTALL_METHOD="pipx (already installed)"
            fi
            CUB_PATH="$HOME/.local/bin"
        elif try_install "pipx" "pipx install 'git+https://github.com/$REPO.git'"; then
            INSTALL_METHOD="pipx"
            CUB_PATH="$HOME/.local/bin"
        else
            dim "pipx install failed: ${LAST_ERROR%%$'\n'*}"
        fi
    fi

    # Try 2: uv tool (if available) - try this BEFORE attempting to install pipx
    if [ -z "$INSTALL_METHOD" ] && has uv; then
        info "Found uv, installing cub..."
        if try_install "uv tool" "uv tool install 'git+https://github.com/$REPO.git'"; then
            INSTALL_METHOD="uv"
            CUB_PATH="$HOME/.local/bin"
        else
            dim "uv tool install failed: ${LAST_ERROR%%$'\n'*}"
        fi
    fi

    # Try 3: Install pipx via pip, then use it
    if [ -z "$INSTALL_METHOD" ]; then
        info "Trying to install pipx..."
        if try_install "pip install pipx" "$PYTHON -m pip install --user pipx"; then
            "$PYTHON" -m pipx ensurepath 2>/dev/null || true
            # pipx is now in ~/.local/bin
            PIPX_CMD="$HOME/.local/bin/pipx"
            if [ -x "$PIPX_CMD" ]; then
                info "Installing cub via pipx..."
                if try_install "pipx (newly installed)" "$PIPX_CMD install 'git+https://github.com/$REPO.git'"; then
                    INSTALL_METHOD="pipx"
                    CUB_PATH="$HOME/.local/bin"
                else
                    dim "pipx install failed: ${LAST_ERROR%%$'\n'*}"
                fi
            else
                dim "pipx installed but not found at $PIPX_CMD"
                TRIED_METHODS+=("pipx (installed but not executable)")
            fi
        else
            dim "Could not install pipx: ${LAST_ERROR%%$'\n'*}"
        fi
    fi

    # Try 4: pip install --user (last resort)
    if [ -z "$INSTALL_METHOD" ]; then
        info "Trying pip install --user..."
        if try_install "pip install --user" "$PYTHON -m pip install --user 'git+https://github.com/$REPO.git'"; then
            INSTALL_METHOD="pip"
            CUB_PATH="$("$PYTHON" -m site --user-base)/bin"
        else
            dim "pip install failed: ${LAST_ERROR%%$'\n'*}"
        fi
    fi

    # Check if installation succeeded
    if [ -z "$INSTALL_METHOD" ]; then
        echo ""
        error "Installation failed after trying: ${TRIED_METHODS[*]}"
        echo ""
        echo "Last error: $LAST_ERROR" | head -5
        echo ""
        echo -e "${BOLD}Please try one of these manual installation methods:${NC}"
        echo ""

        # Suggest methods based on what's available
        if has pipx; then
            echo "  ${GREEN}pipx (recommended):${NC}"
            echo "    pipx install git+https://github.com/$REPO.git"
            echo ""
        fi

        if has uv; then
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

        if ! has pipx && ! has uv; then
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

    success "Installed cub via $INSTALL_METHOD"

    # Add to PATH
    PATH_ADDED=false
    if [ -n "$CUB_PATH" ]; then
        # Check if already in PATH
        if [[ ":$PATH:" != *":$CUB_PATH:"* ]]; then
            info "Adding $CUB_PATH to PATH..."
            if add_to_path "$CUB_PATH"; then
                PATH_ADDED=true
                # Also add to current session
                export PATH="$CUB_PATH:$PATH"
            else
                warn "Could not add to PATH automatically."
                echo ""
                echo "Add this line to your shell config:"
                echo ""
                echo "  export PATH=\"$CUB_PATH:\$PATH\""
                echo ""
            fi
        fi
    fi

    # Verify installation
    if ! has cub && [ -n "$CUB_PATH" ]; then
        export PATH="$CUB_PATH:$PATH"
    fi

    if ! has cub; then
        warn "cub not found in PATH after installation."
        echo ""
        echo "You may need to restart your shell, or run:"
        echo ""
        echo "  export PATH=\"$CUB_PATH:\$PATH\""
        echo ""
        exit 1
    fi

    # Run global init
    echo ""
    info "Running cub init --global..."
    if cub init --global; then
        success "Global configuration complete"
    else
        warn "Global init had issues, but cub is installed."
        echo "Run 'cub init --global' manually to complete setup."
    fi

    # Success message
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  Cub installed successfully!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. cd into your project"
    echo "  2. cub init              # Initialize project"
    echo "  3. cub prep              # Turn ideas into tasks"
    echo "  4. cub run               # Let AI execute"
    echo ""
    if [ "$PATH_ADDED" = true ]; then
        shell_config=$(detect_shell_config)
        echo -e "${YELLOW}Note:${NC} Restart your shell or run:"
        echo ""
        echo "  source $shell_config"
        echo ""
    fi
    echo "Documentation: https://github.com/$REPO"
    echo ""
}

main "$@"
