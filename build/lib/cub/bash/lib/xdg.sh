#!/usr/bin/env bash
#
# xdg.sh - XDG Base Directory Specification helpers
#
# Provides functions to respect the XDG Base Directory Specification
# (https://specifications.freedesktop.org/basedir-spec/latest/)
# with sensible fallbacks for macOS and other systems.
#
# Environment Variables:
#   XDG_CONFIG_HOME    - User config directory (default: ~/.config)
#   XDG_DATA_HOME      - User data directory (default: ~/.local/share)
#   XDG_CACHE_HOME     - User cache directory (default: ~/.cache)
#

# Get XDG config home directory
# Returns: path to config directory (defaults to ~/.config)
xdg_config_home() {
    if [[ -n "${XDG_CONFIG_HOME:-}" ]]; then
        echo "$XDG_CONFIG_HOME"
    else
        echo "${HOME}/.config"
    fi
}

# Get XDG data home directory
# Returns: path to data directory (defaults to ~/.local/share)
xdg_data_home() {
    if [[ -n "${XDG_DATA_HOME:-}" ]]; then
        echo "$XDG_DATA_HOME"
    else
        echo "${HOME}/.local/share"
    fi
}

# Get XDG cache home directory
# Returns: path to cache directory (defaults to ~/.cache)
xdg_cache_home() {
    if [[ -n "${XDG_CACHE_HOME:-}" ]]; then
        echo "$XDG_CACHE_HOME"
    else
        echo "${HOME}/.cache"
    fi
}

# Ensure cub directories exist
# Creates standard cub directories:
#   - config: $(xdg_config_home)/cub
#   - data: $(xdg_data_home)/cub
#   - logs: $(xdg_data_home)/cub/logs
#   - cache: $(xdg_cache_home)/cub
cub_ensure_dirs() {
    local config_dir
    local data_dir
    local logs_dir
    local cache_dir

    config_dir="$(xdg_config_home)/cub"
    data_dir="$(xdg_data_home)/cub"
    logs_dir="${data_dir}/logs"
    cache_dir="$(xdg_cache_home)/cub"

    # Create directories if they don't exist
    mkdir -p "$config_dir"
    mkdir -p "$logs_dir"
    mkdir -p "$cache_dir"
}

# Get cub config directory
# Returns: path to cub config directory
cub_config_dir() {
    echo "$(xdg_config_home)/cub"
}

# Get cub data directory
# Returns: path to cub data directory
cub_data_dir() {
    echo "$(xdg_data_home)/cub"
}

# Get cub logs directory
# Returns: path to cub logs directory
cub_logs_dir() {
    echo "$(xdg_data_home)/cub/logs"
}

# Get cub cache directory
# Returns: path to cub cache directory
cub_cache_dir() {
    echo "$(xdg_cache_home)/cub"
}
