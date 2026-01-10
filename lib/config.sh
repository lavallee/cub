#!/usr/bin/env bash
#
# config.sh - Configuration Management Interface
#
# Provides functions to read and manage configuration values from JSON config files.
# Supports dot-notation keys for nested values (e.g., "harness.priority").
#
# Config file locations (in priority order):
#   1. ./.curb.json (project-specific)
#   2. $(curb_config_dir)/config.json (user config)
#   3. Built-in defaults
#
# Usage:
#   config_load                              # Load config files
#   config_get "harness.priority"            # Get value by dot-path
#   config_get_or "budget.default" "100"     # Get with fallback
#

# Cache file for loaded configuration
# Using a file instead of variable because bash command substitution creates subshells
_CONFIG_CACHE_FILE="${TMPDIR:-/tmp}/curb_config_cache_$$"

# Source xdg.sh for directory helpers
# This allows us to find the config directory
if [[ -z "$(type -t curb_config_dir)" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "${SCRIPT_DIR}/xdg.sh"
fi

# Clean up cache file on exit
trap 'rm -f "$_CONFIG_CACHE_FILE" 2>/dev/null' EXIT

# Load and merge configuration files
# Merges configs in priority order: project > user > defaults
# Returns: 0 on success, 1 if no configs found
config_load() {
    local project_config="./.curb.json"
    local user_config="$(curb_config_dir)/config.json"
    local merged_config="{}"

    # Start with empty config
    merged_config="{}"

    # Merge user config if it exists
    if [[ -f "$user_config" ]]; then
        merged_config=$(jq -s '.[0] * .[1]' <(echo "$merged_config") "$user_config" 2>/dev/null)
        if [[ $? -ne 0 ]]; then
            echo "Warning: Failed to parse user config at $user_config" >&2
            merged_config="{}"
        fi
    fi

    # Merge project config if it exists (takes priority)
    if [[ -f "$project_config" ]]; then
        merged_config=$(jq -s '.[0] * .[1]' <(echo "$merged_config") "$project_config" 2>/dev/null)
        if [[ $? -ne 0 ]]; then
            echo "Warning: Failed to parse project config at $project_config" >&2
            # Keep the user config if project config failed
        fi
    fi

    # Cache the merged config to file
    echo "$merged_config" > "$_CONFIG_CACHE_FILE"

    return 0
}

# Get configuration value by dot-notation key
# Args:
#   $1 - dot-notation key (e.g., "harness.priority", "budget.default")
# Returns: value from config, empty string if not found
# Exit code: 0 if found, 1 if not found
config_get() {
    local key="$1"

    # Load config if not already cached
    if [[ ! -f "$_CONFIG_CACHE_FILE" ]]; then
        config_load
    fi

    # Read cached config from file
    local cached_config
    cached_config=$(cat "$_CONFIG_CACHE_FILE" 2>/dev/null)
    if [[ -z "$cached_config" ]]; then
        cached_config="{}"
    fi

    # Use jq to extract the value by dot-path
    # For arrays and objects, use -c (compact) instead of -r (raw) to preserve JSON structure
    local value
    local jq_result
    value=$(echo "$cached_config" | jq ".$key // empty" 2>/dev/null)
    jq_result=$?

    # If jq failed, return error
    if [[ $jq_result -ne 0 ]]; then
        return 1
    fi

    # Check if we got a value (jq returns empty string for missing keys when using // empty)
    if [[ -z "$value" || "$value" == "null" ]]; then
        return 1
    fi

    # For strings, remove the JSON quotes; for arrays/objects/numbers/booleans, keep as-is
    # Check if it's a string by seeing if it starts with a quote
    if [[ "$value" =~ ^\".*\"$ ]]; then
        # It's a JSON string, use jq -r to get raw value
        value=$(echo "$cached_config" | jq -r ".$key" 2>/dev/null)
    fi

    echo "$value"
    return 0
}

# Get configuration value with fallback default
# Args:
#   $1 - dot-notation key (e.g., "harness.priority", "budget.default")
#   $2 - default value to return if key not found
# Returns: value from config, or default if not found
config_get_or() {
    local key="$1"
    local default="$2"

    # Try to get the value
    local value
    value=$(config_get "$key")

    # Return value if found, otherwise return default
    if [[ $? -eq 0 && -n "$value" ]]; then
        echo "$value"
    else
        echo "$default"
    fi

    return 0
}

# Clear the configuration cache
# Useful for testing or when config files change
config_clear_cache() {
    rm -f "$_CONFIG_CACHE_FILE" 2>/dev/null
}

# Get the raw cached config (for debugging)
# Returns: the entire cached config as JSON
config_dump() {
    if [[ ! -f "$_CONFIG_CACHE_FILE" ]]; then
        config_load
    fi
    cat "$_CONFIG_CACHE_FILE" 2>/dev/null || echo "{}"
}
