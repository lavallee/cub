#!/usr/bin/env bash
#
# uninstall.sh - Uninstall cub (Claude Under Ralph + Beads)
#
# Usage:
#   ./uninstall.sh              # Uninstall from ~/.local
#   ./uninstall.sh --global     # Uninstall from /usr/local (requires sudo)
#   ./uninstall.sh --prefix DIR # Uninstall from custom directory
#   ./uninstall.sh --purge      # Also remove config files
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
PREFIX=""
GLOBAL_UNINSTALL=false
PURGE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --global|-g)
            GLOBAL_UNINSTALL=true
            PREFIX="/usr/local"
            shift
            ;;
        --prefix|-p)
            PREFIX="$2"
            shift 2
            ;;
        --purge)
            PURGE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --global, -g       Uninstall from /usr/local (requires sudo)"
            echo "  --prefix, -p DIR   Uninstall from custom directory"
            echo "  --purge            Also remove configuration files (~/.config/cub)"
            echo "  --help, -h         Show this help message"
            echo ""
            echo "If no prefix is specified, attempts to auto-detect installation location."
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}" >&2
            exit 1
            ;;
    esac
done

# Auto-detect installation if no prefix specified
if [[ -z "$PREFIX" ]]; then
    # Check common locations
    if [[ -L "${HOME}/.local/bin/cub" ]]; then
        PREFIX="${HOME}/.local"
    elif [[ -L "/usr/local/bin/cub" ]]; then
        PREFIX="/usr/local"
        GLOBAL_UNINSTALL=true
    elif command -v cub &>/dev/null; then
        # Try to find from PATH
        CUB_PATH="$(command -v cub)"
        if [[ -L "$CUB_PATH" ]]; then
            LINK_TARGET="$(readlink "$CUB_PATH")"
            if [[ "$LINK_TARGET" == */share/cub/cub ]]; then
                PREFIX="$(dirname "$(dirname "$LINK_TARGET")")"
            fi
        fi
    fi
fi

if [[ -z "$PREFIX" ]]; then
    echo -e "${RED}Could not detect cub installation.${NC}"
    echo ""
    echo "Specify the installation prefix:"
    echo "  $0 --prefix ~/.local"
    echo "  $0 --global"
    exit 1
fi

# Derived paths
BIN_DIR="${PREFIX}/bin"
SHARE_DIR="${PREFIX}/share/cub"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cub"

echo -e "${BOLD}${BLUE}cub uninstaller${NC}"
echo ""

# Check if installed
if [[ ! -d "$SHARE_DIR" ]] && [[ ! -L "${BIN_DIR}/cub" ]]; then
    echo -e "${YELLOW}cub does not appear to be installed at ${PREFIX}${NC}"
    exit 0
fi

# Show what will be removed
echo "The following will be removed:"
echo ""
[[ -L "${BIN_DIR}/cub" ]] && echo "  ${BIN_DIR}/cub (symlink)"
[[ -L "${BIN_DIR}/cub-init" ]] && echo "  ${BIN_DIR}/cub-init (symlink)"
[[ -d "$SHARE_DIR" ]] && echo "  ${SHARE_DIR}/ (installation files)"
if [[ "$PURGE" == "true" ]] && [[ -d "$CONFIG_DIR" ]]; then
    echo "  ${CONFIG_DIR}/ (configuration files)"
fi
echo ""

# Confirm
read -p "Continue? [y/N] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Check permissions for global uninstall
if [[ "$GLOBAL_UNINSTALL" == "true" ]]; then
    if [[ ! -w "$BIN_DIR" ]] && [[ $EUID -ne 0 ]]; then
        echo -e "${YELLOW}Global uninstallation requires root privileges.${NC}"
        echo "Re-running with sudo..."
        exec sudo "$0" "$@"
    fi
fi

echo ""
echo "Removing cub..."

# Remove symlinks
if [[ -L "${BIN_DIR}/cub" ]]; then
    rm -f "${BIN_DIR}/cub"
    echo "  Removed ${BIN_DIR}/cub"
fi

if [[ -L "${BIN_DIR}/cub-init" ]]; then
    rm -f "${BIN_DIR}/cub-init"
    echo "  Removed ${BIN_DIR}/cub-init"
fi

# Remove share directory
if [[ -d "$SHARE_DIR" ]]; then
    rm -rf "$SHARE_DIR"
    echo "  Removed ${SHARE_DIR}/"
fi

# Purge config if requested
if [[ "$PURGE" == "true" ]] && [[ -d "$CONFIG_DIR" ]]; then
    rm -rf "$CONFIG_DIR"
    echo "  Removed ${CONFIG_DIR}/"
fi

echo ""
echo -e "${GREEN}${BOLD}cub has been uninstalled.${NC}"

# Note about project-level files
echo ""
echo -e "${YELLOW}Note:${NC} Project-level files (.cub/, .cub.json) were not removed."
echo "Remove them manually from your projects if desired."

# Note about data directory
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/cub"
if [[ -d "$DATA_DIR" ]]; then
    echo ""
    echo -e "${YELLOW}Note:${NC} Data directory exists at ${DATA_DIR}"
    echo "Remove it manually if you want to delete run history and logs."
fi
