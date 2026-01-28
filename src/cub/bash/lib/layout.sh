#!/usr/bin/env bash
#
# layout.sh - Project layout detection and file resolution
#
# Supports two layouts:
#   1. New layout (.cub/ subdirectory) - PREFERRED
#   2. Legacy layout (root-level files) - Deprecated, supported via symlinks
#
# Layout detection:
#   - CUB_LAYOUT=new|legacy  - explicit selection
#   - Auto-detect: checks for .cub/prompt.md, falls back to PROMPT.md symlink
#

# Include guard to prevent re-sourcing
if [[ -n "${_CUB_LAYOUT_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_LAYOUT_SH_LOADED=1

# Layout state (set by detect_layout)
_PROJECT_LAYOUT=""

# Detect which layout the project uses
# Returns: "new" for .cub/ subdirectory, "legacy" for root-level symlinks
# Parameters:
#   $1 - project directory (defaults to current directory)
# Echoes: "new" or "legacy"
detect_layout() {
    local project_dir="${1:-.}"

    # Check for explicit override
    if [[ -n "${CUB_LAYOUT:-}" ]]; then
        case "$CUB_LAYOUT" in
            new)
                _PROJECT_LAYOUT="new"
                ;;
            legacy)
                _PROJECT_LAYOUT="legacy"
                ;;
            auto)
                # Will be handled in auto-detect below
                ;;
            *)
                # Default to auto-detect
                ;;
        esac
    fi

    # Auto-detect if not explicitly set
    if [[ -z "$_PROJECT_LAYOUT" ]]; then
        # Prefer new layout if .cub/prompt.md exists
        if [[ -f "${project_dir}/.cub/prompt.md" ]]; then
            _PROJECT_LAYOUT="new"
        # Fall back to legacy layout if root symlinks exist
        elif [[ -L "${project_dir}/PROMPT.md" ]] || [[ -f "${project_dir}/PROMPT.md" ]]; then
            _PROJECT_LAYOUT="legacy"
        else
            # Default to new layout (preferred)
            _PROJECT_LAYOUT="new"
        fi
    fi

    echo "$_PROJECT_LAYOUT"
}

# Get the current layout
# Optional parameter: project_dir (defaults to current directory)
# Echoes: "new" or "legacy"
get_layout() {
    local project_dir="${1:-.}"
    if [[ -z "$_PROJECT_LAYOUT" ]]; then
        detect_layout "$project_dir" >/dev/null
    fi
    echo "$_PROJECT_LAYOUT"
}

# Get the root directory for layout files
# Returns either PROJECT_DIR/.cub for new layout or PROJECT_DIR for legacy
# Parameters:
#   $1 - project directory (defaults to current directory)
# Echoes: path to layout root
get_layout_root() {
    local project_dir="${1:-.}"
    local layout
    layout=$(get_layout "$project_dir")

    if [[ "$layout" == "new" ]]; then
        echo "${project_dir}/.cub"
    else
        echo "$project_dir"
    fi
}

# Get the path to prompt.md
# Parameters:
#   $1 - project directory (defaults to current directory)
# Echoes: absolute path to prompt.md
get_prompt_file() {
    local project_dir="${1:-.}"
    local layout_root
    layout_root=$(get_layout_root "$project_dir")
    echo "${layout_root}/prompt.md"
}

# Get the path to agent.md
# Parameters:
#   $1 - project directory (defaults to current directory)
# Echoes: absolute path to agent.md
get_agent_file() {
    local project_dir="${1:-.}"
    local layout_root
    layout_root=$(get_layout_root "$project_dir")
    echo "${layout_root}/agent.md"
}

# Get the path to fix_plan.md
# Parameters:
#   $1 - project directory (defaults to current directory)
# Echoes: absolute path to fix_plan.md
get_fix_plan_file() {
    local project_dir="${1:-.}"
    local layout_root
    layout_root=$(get_layout_root "$project_dir")
    echo "${layout_root}/fix_plan.md"
}

# Check if project uses new layout
# Parameters:
#   $1 - project directory (defaults to current directory)
# Returns: 0 if new layout, 1 if legacy
is_new_layout() {
    local project_dir="${1:-.}"
    local layout
    layout=$(get_layout "$project_dir")
    [[ "$layout" == "new" ]]
}

# Check if project uses legacy layout
# Parameters:
#   $1 - project directory (defaults to current directory)
# Returns: 0 if legacy, 1 if new
is_legacy_layout() {
    local project_dir="${1:-.}"
    local layout
    layout=$(get_layout "$project_dir")
    [[ "$layout" == "legacy" ]]
}
