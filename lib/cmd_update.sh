#!/usr/bin/env bash
#
# cmd_update.sh - update subcommand implementation
#
# Update cub to the latest version from GitHub or a local source.
#

# Include guard
if [[ -n "${_CUB_CMD_UPDATE_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_UPDATE_SH_LOADED=1

# GitHub repository
CUB_GITHUB_REPO="lavallee/cub"
CUB_GITHUB_URL="https://github.com/${CUB_GITHUB_REPO}"

cmd_update_help() {
    cat <<'EOF'
cub update [options]

Update cub to a newer version.

USAGE:
  cub update              Update to latest tagged release
  cub update --head       Update to latest commit on main branch
  cub update --local      Update from current directory (for development)

OPTIONS:
  --head          Install from the main branch instead of latest release
  --local         Install from the current working directory
                  (must be run from a cub repository clone)
  --check         Check for updates without installing
  --force         Update even if already on the target version
  --global        Install system-wide to /usr/local (requires sudo)

EXAMPLES:
  # Update to latest stable release
  cub update

  # Check what version is available
  cub update --check

  # Install bleeding-edge from main branch
  cub update --head

  # Update from local development copy
  cd ~/Projects/cub && cub update --local

  # Force reinstall current version
  cub update --force

SEE ALSO:
  cub version     Show current version
  cub doctor      Diagnose issues
  cub --help      Show all commands
EOF
}

# Check if current directory is a cub clone
_is_cub_repo() {
    local dir="${1:-.}"

    # Must be a git repo
    if ! git -C "$dir" rev-parse --git-dir &>/dev/null; then
        return 1
    fi

    # Check for cub executable and lib directory
    if [[ ! -f "${dir}/cub" ]] || [[ ! -d "${dir}/lib" ]]; then
        return 1
    fi

    # Check for characteristic files
    if [[ ! -f "${dir}/lib/tasks.sh" ]] || [[ ! -f "${dir}/install.sh" ]]; then
        return 1
    fi

    return 0
}

# Get latest release tag from GitHub
_get_latest_release() {
    local api_url="https://api.github.com/repos/${CUB_GITHUB_REPO}/releases/latest"
    local response

    if command -v curl &>/dev/null; then
        response=$(curl -fsSL "$api_url" 2>/dev/null)
    elif command -v wget &>/dev/null; then
        response=$(wget -qO- "$api_url" 2>/dev/null)
    else
        _log_error_console "Neither curl nor wget available"
        return 1
    fi

    if [[ -z "$response" ]]; then
        return 1
    fi

    echo "$response" | jq -r '.tag_name // empty'
}

# Get the latest commit SHA from main branch
_get_latest_main_sha() {
    local api_url="https://api.github.com/repos/${CUB_GITHUB_REPO}/commits/main"
    local response

    if command -v curl &>/dev/null; then
        response=$(curl -fsSL "$api_url" 2>/dev/null)
    elif command -v wget &>/dev/null; then
        response=$(wget -qO- "$api_url" 2>/dev/null)
    else
        _log_error_console "Neither curl nor wget available"
        return 1
    fi

    if [[ -z "$response" ]]; then
        return 1
    fi

    echo "$response" | jq -r '.sha // empty' | head -c 7
}

# Download and extract release
_download_release() {
    local tag="$1"
    local temp_dir="$2"

    local tarball_url="${CUB_GITHUB_URL}/archive/refs/tags/${tag}.tar.gz"

    log_info "Downloading ${tag}..."

    if command -v curl &>/dev/null; then
        if ! curl -fsSL "$tarball_url" | tar -xz -C "$temp_dir" --strip-components=1; then
            return 1
        fi
    elif command -v wget &>/dev/null; then
        if ! wget -qO- "$tarball_url" | tar -xz -C "$temp_dir" --strip-components=1; then
            return 1
        fi
    else
        _log_error_console "Neither curl nor wget available"
        return 1
    fi

    return 0
}

# Download from main branch
_download_main() {
    local temp_dir="$1"

    local tarball_url="${CUB_GITHUB_URL}/archive/refs/heads/main.tar.gz"

    log_info "Downloading main branch..."

    if command -v curl &>/dev/null; then
        if ! curl -fsSL "$tarball_url" | tar -xz -C "$temp_dir" --strip-components=1; then
            return 1
        fi
    elif command -v wget &>/dev/null; then
        if ! wget -qO- "$tarball_url" | tar -xz -C "$temp_dir" --strip-components=1; then
            return 1
        fi
    else
        _log_error_console "Neither curl nor wget available"
        return 1
    fi

    return 0
}

# Run install.sh from a source directory
_run_install() {
    local source_dir="$1"
    local global="${2:-false}"

    if [[ ! -f "${source_dir}/install.sh" ]]; then
        _log_error_console "install.sh not found in ${source_dir}"
        return 1
    fi

    local install_args=()
    if [[ "$global" == "true" ]]; then
        install_args+=("--global")
    fi

    log_info "Running installer..."
    # Use safe array expansion to handle empty array with set -u
    if ! bash "${source_dir}/install.sh" ${install_args[@]+"${install_args[@]}"}; then
        _log_error_console "Installation failed"
        return 1
    fi

    return 0
}

# Compare version strings (returns 0 if $1 >= $2)
_version_gte() {
    local v1="$1"
    local v2="$2"

    # Strip leading 'v' if present
    v1="${v1#v}"
    v2="${v2#v}"

    # Use sort -V if available
    if printf '%s\n%s\n' "$v2" "$v1" | sort -V -C 2>/dev/null; then
        return 0
    fi

    # Fallback: simple string comparison
    [[ "$v1" == "$v2" ]] && return 0

    # Compare version components
    local IFS='.'
    read -ra v1_parts <<< "$v1"
    read -ra v2_parts <<< "$v2"

    local i
    for ((i=0; i<${#v1_parts[@]} || i<${#v2_parts[@]}; i++)); do
        local p1="${v1_parts[i]:-0}"
        local p2="${v2_parts[i]:-0}"

        # Remove any non-numeric suffix for comparison
        p1="${p1%%[!0-9]*}"
        p2="${p2%%[!0-9]*}"

        if ((p1 > p2)); then
            return 0
        elif ((p1 < p2)); then
            return 1
        fi
    done

    return 0
}

cmd_update() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_update_help
        return 0
    fi

    local use_head=false
    local use_local=false
    local check_only=false
    local force=false
    local global=false

    # Parse flags
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --head)
                use_head=true
                shift
                ;;
            --local)
                use_local=true
                shift
                ;;
            --check)
                check_only=true
                shift
                ;;
            --force)
                force=true
                shift
                ;;
            --global|-g)
                global=true
                shift
                ;;
            *)
                _log_error_console "Unknown flag: $1"
                _log_error_console "Usage: cub update [--head|--local] [--check] [--force] [--global]"
                return 1
                ;;
        esac
    done

    # Validate flag combinations
    if [[ "$use_head" == "true" && "$use_local" == "true" ]]; then
        _log_error_console "Cannot use --head and --local together"
        return 1
    fi

    local current_version="${CUB_VERSION}"
    log_info "Current version: v${current_version}"

    # Handle --local mode
    if [[ "$use_local" == "true" ]]; then
        local local_dir="${PROJECT_DIR}"

        if ! _is_cub_repo "$local_dir"; then
            _log_error_console "Current directory is not a cub repository clone"
            _log_error_console "Run this from a cloned cub repository, or omit --local"
            return 1
        fi

        # Get version from local cub script
        local local_version
        local_version=$(grep -m1 '^CUB_VERSION=' "${local_dir}/cub" 2>/dev/null | cut -d'"' -f2)

        if [[ -z "$local_version" ]]; then
            _log_error_console "Could not determine version from local cub"
            return 1
        fi

        log_info "Local version: v${local_version}"

        if [[ "$check_only" == "true" ]]; then
            if [[ "$local_version" == "$current_version" ]]; then
                log_info "Local version matches installed version"
            else
                log_info "Local version differs from installed (${local_version} vs ${current_version})"
            fi
            return 0
        fi

        if [[ "$local_version" == "$current_version" && "$force" != "true" ]]; then
            log_info "Already at version v${local_version}"
            log_info "Use --force to reinstall"
            return 0
        fi

        _run_install "$local_dir" "$global"
        local exit_code=$?

        if [[ $exit_code -eq 0 ]]; then
            log_success "Updated to v${local_version} from local source"
        fi

        return $exit_code
    fi

    # Handle --head mode (main branch)
    if [[ "$use_head" == "true" ]]; then
        local latest_sha
        latest_sha=$(_get_latest_main_sha)

        if [[ -z "$latest_sha" ]]; then
            _log_error_console "Could not fetch latest commit from main branch"
            _log_error_console "Check your internet connection or try again later"
            return 1
        fi

        log_info "Latest main: ${latest_sha}"

        if [[ "$check_only" == "true" ]]; then
            log_info "Use 'cub update --head' to install"
            return 0
        fi

        # Create temp directory
        local temp_dir
        temp_dir=$(mktemp -d)
        trap "rm -rf '$temp_dir'" EXIT

        if ! _download_main "$temp_dir"; then
            _log_error_console "Failed to download main branch"
            return 1
        fi

        _run_install "$temp_dir" "$global"
        local exit_code=$?

        if [[ $exit_code -eq 0 ]]; then
            log_success "Updated to main branch (${latest_sha})"
        fi

        return $exit_code
    fi

    # Default: latest release
    local latest_tag
    latest_tag=$(_get_latest_release)

    if [[ -z "$latest_tag" ]]; then
        _log_error_console "Could not fetch latest release"
        _log_error_console "Check your internet connection or try again later"
        return 1
    fi

    # Strip leading 'v' for comparison
    local latest_version="${latest_tag#v}"
    log_info "Latest release: ${latest_tag}"

    if [[ "$check_only" == "true" ]]; then
        if _version_gte "$current_version" "$latest_version"; then
            log_info "You're up to date!"
        else
            log_info "Update available: v${current_version} -> ${latest_tag}"
            log_info "Run 'cub update' to install"
        fi
        return 0
    fi

    if _version_gte "$current_version" "$latest_version" && [[ "$force" != "true" ]]; then
        log_info "Already at latest version (v${current_version})"
        log_info "Use --force to reinstall, or --head for bleeding-edge"
        return 0
    fi

    # Create temp directory
    local temp_dir
    temp_dir=$(mktemp -d)
    trap "rm -rf '$temp_dir'" EXIT

    if ! _download_release "$latest_tag" "$temp_dir"; then
        _log_error_console "Failed to download release ${latest_tag}"
        return 1
    fi

    _run_install "$temp_dir" "$global"
    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_success "Updated from v${current_version} to ${latest_tag}"
    fi

    return $exit_code
}
