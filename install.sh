#!/usr/bin/env bash
#
# install.sh - Install cub (Claude Under Ralph + Beads)
#
# Usage:
#   ./install.sh              # Install to ~/.local
#   ./install.sh --global     # Install to /usr/local (requires sudo)
#   ./install.sh --prefix DIR # Install to custom directory
#
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Defaults
PREFIX="${HOME}/.local"
GLOBAL_INSTALL=false

# Save original arguments for sudo re-execution
ORIGINAL_ARGS=("$@")

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --global|-g)
            GLOBAL_INSTALL=true
            PREFIX="/usr/local"
            shift
            ;;
        --prefix|-p)
            PREFIX="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --global, -g       Install system-wide to /usr/local (requires sudo)"
            echo "  --prefix, -p DIR   Install to custom directory (default: ~/.local)"
            echo "  --help, -h         Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}" >&2
            exit 1
            ;;
    esac
done

# Derived paths
BIN_DIR="${PREFIX}/bin"
SHARE_DIR="${PREFIX}/share/cub"

# Source directory (where this script is located)
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BOLD}${BLUE}cub installer${NC}"
echo ""

# Check dependencies
echo -e "${BOLD}Checking dependencies...${NC}"

check_dep() {
    local cmd=$1
    local name=$2
    local url=$3

    if command -v "$cmd" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name - install from $url"
        return 1
    fi
}

DEPS_OK=true

# Check bash version (3.2+ required, works on macOS default bash)
BASH_VERSION_MAJOR="${BASH_VERSION%%.*}"
BASH_VERSION_MINOR="${BASH_VERSION#*.}"
BASH_VERSION_MINOR="${BASH_VERSION_MINOR%%.*}"
if [[ "$BASH_VERSION_MAJOR" -gt 3 ]] || [[ "$BASH_VERSION_MAJOR" -eq 3 && "$BASH_VERSION_MINOR" -ge 2 ]]; then
    echo -e "  ${GREEN}✓${NC} bash ${BASH_VERSION}"
else
    echo -e "  ${RED}✗${NC} bash ${BASH_VERSION} (3.2+ required)"
    DEPS_OK=false
fi

check_dep "jq" "jq" "https://jqlang.github.io/jq/download/" || DEPS_OK=false
check_dep "git" "git" "https://git-scm.com/" || DEPS_OK=false

# Check for at least one harness
HARNESS_FOUND=false
if command -v claude &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} claude (Claude Code CLI)"
    HARNESS_FOUND=true
elif command -v codex &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} codex (OpenAI Codex CLI)"
    HARNESS_FOUND=true
else
    echo -e "  ${YELLOW}!${NC} No AI harness found (claude or codex recommended)"
fi

if [[ "$DEPS_OK" != "true" ]]; then
    echo ""
    echo -e "${RED}Missing required dependencies. Please install them and try again.${NC}"
    exit 1
fi

echo ""

# Check if running from source directory
if [[ ! -f "${SOURCE_DIR}/cub" ]]; then
    echo -e "${RED}Error: cub executable not found in ${SOURCE_DIR}${NC}"
    echo "Please run this script from the cub repository root."
    exit 1
fi

# Check write permissions
if [[ "$GLOBAL_INSTALL" == "true" ]]; then
    if [[ ! -w "/usr/local" ]] && [[ $EUID -ne 0 ]]; then
        echo -e "${YELLOW}Global installation requires root privileges.${NC}"
        echo "Re-running with sudo..."
        exec sudo "$0" "${ORIGINAL_ARGS[@]}"
    fi
fi

# Create directories
echo -e "${BOLD}Installing to ${PREFIX}...${NC}"

mkdir -p "${BIN_DIR}"
mkdir -p "${SHARE_DIR}"

# Copy files
echo "  Copying files..."

# Main executables go to share dir, we'll symlink them
cp "${SOURCE_DIR}/cub" "${SHARE_DIR}/cub"
cp "${SOURCE_DIR}/cub-init" "${SHARE_DIR}/cub-init"
chmod +x "${SHARE_DIR}/cub"
chmod +x "${SHARE_DIR}/cub-init"

# Copy lib directory
cp -r "${SOURCE_DIR}/lib" "${SHARE_DIR}/"

# Copy templates
if [[ -d "${SOURCE_DIR}/templates" ]]; then
    cp -r "${SOURCE_DIR}/templates" "${SHARE_DIR}/"
fi

# Copy examples
if [[ -d "${SOURCE_DIR}/examples" ]]; then
    cp -r "${SOURCE_DIR}/examples" "${SHARE_DIR}/"
fi

# Copy docs
if [[ -d "${SOURCE_DIR}/docs" ]]; then
    cp -r "${SOURCE_DIR}/docs" "${SHARE_DIR}/"
fi

# Create symlinks
echo "  Creating symlinks..."

# Remove old symlinks if they exist
rm -f "${BIN_DIR}/cub"
rm -f "${BIN_DIR}/cub-init"

# Create new symlinks
ln -s "${SHARE_DIR}/cub" "${BIN_DIR}/cub"
ln -s "${SHARE_DIR}/cub-init" "${BIN_DIR}/cub-init"

echo ""
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo ""

# Check if bin dir is in PATH
if [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
    echo -e "${YELLOW}Note:${NC} ${BIN_DIR} is not in your PATH."
    echo ""
    echo "Add it to your shell configuration:"
    echo ""
    if [[ -f "${HOME}/.zshrc" ]]; then
        echo "  echo 'export PATH=\"\$PATH:${BIN_DIR}\"' >> ~/.zshrc"
        echo "  source ~/.zshrc"
    elif [[ -f "${HOME}/.bashrc" ]]; then
        echo "  echo 'export PATH=\"\$PATH:${BIN_DIR}\"' >> ~/.bashrc"
        echo "  source ~/.bashrc"
    else
        echo "  export PATH=\"\$PATH:${BIN_DIR}\""
    fi
    echo ""
fi

echo "Get started:"
echo ""
echo "  cub --version    # Verify installation"
echo "  cub init         # Initialize a project"
echo "  cub --help       # Show all commands"
echo ""

if [[ "$HARNESS_FOUND" != "true" ]]; then
    echo -e "${YELLOW}Reminder:${NC} Install an AI coding CLI to use cub:"
    echo "  - Claude Code: https://github.com/anthropics/claude-code"
    echo "  - OpenAI Codex: https://github.com/openai/codex"
    echo ""
fi
