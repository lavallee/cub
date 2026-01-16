#!/usr/bin/env bats

# Test suite for lib/xdg.sh

# Load the test helper
load test_helper

# Load the xdg library
setup() {
    source "${LIB_DIR}/xdg.sh"
}

# Test xdg_config_home with default
@test "xdg_config_home returns ~/.config by default" {
    unset XDG_CONFIG_HOME
    result=$(xdg_config_home)
    [[ "$result" == "${HOME}/.config" ]]
}

# Test xdg_config_home with environment variable
@test "xdg_config_home respects XDG_CONFIG_HOME" {
    export XDG_CONFIG_HOME="/custom/config"
    result=$(xdg_config_home)
    [[ "$result" == "/custom/config" ]]
}

# Test xdg_data_home with default
@test "xdg_data_home returns ~/.local/share by default" {
    unset XDG_DATA_HOME
    result=$(xdg_data_home)
    [[ "$result" == "${HOME}/.local/share" ]]
}

# Test xdg_data_home with environment variable
@test "xdg_data_home respects XDG_DATA_HOME" {
    export XDG_DATA_HOME="/custom/data"
    result=$(xdg_data_home)
    [[ "$result" == "/custom/data" ]]
}

# Test xdg_cache_home with default
@test "xdg_cache_home returns ~/.cache by default" {
    unset XDG_CACHE_HOME
    result=$(xdg_cache_home)
    [[ "$result" == "${HOME}/.cache" ]]
}

# Test xdg_cache_home with environment variable
@test "xdg_cache_home respects XDG_CACHE_HOME" {
    export XDG_CACHE_HOME="/custom/cache"
    result=$(xdg_cache_home)
    [[ "$result" == "/custom/cache" ]]
}

# Test cub_config_dir
@test "cub_config_dir returns correct path" {
    unset XDG_CONFIG_HOME
    result=$(cub_config_dir)
    [[ "$result" == "${HOME}/.config/cub" ]]
}

# Test cub_data_dir
@test "cub_data_dir returns correct path" {
    unset XDG_DATA_HOME
    result=$(cub_data_dir)
    [[ "$result" == "${HOME}/.local/share/cub" ]]
}

# Test cub_logs_dir
@test "cub_logs_dir returns correct path" {
    unset XDG_DATA_HOME
    result=$(cub_logs_dir)
    [[ "$result" == "${HOME}/.local/share/cub/logs" ]]
}

# Test cub_cache_dir
@test "cub_cache_dir returns correct path" {
    unset XDG_CACHE_HOME
    result=$(cub_cache_dir)
    [[ "$result" == "${HOME}/.cache/cub" ]]
}

# Test cub_ensure_dirs creates directories
@test "cub_ensure_dirs creates config directory" {
    # Use temp dir for testing
    export XDG_CONFIG_HOME="${BATS_TMPDIR}/test_config"
    export XDG_DATA_HOME="${BATS_TMPDIR}/test_data"
    export XDG_CACHE_HOME="${BATS_TMPDIR}/test_cache"

    # Clean up any existing directories
    rm -rf "${BATS_TMPDIR}/test_config" "${BATS_TMPDIR}/test_data" "${BATS_TMPDIR}/test_cache"

    # Call the function
    cub_ensure_dirs

    # Verify config directory exists
    [[ -d "${BATS_TMPDIR}/test_config/cub" ]]
}

@test "cub_ensure_dirs creates data directory" {
    # Use temp dir for testing
    export XDG_CONFIG_HOME="${BATS_TMPDIR}/test_config"
    export XDG_DATA_HOME="${BATS_TMPDIR}/test_data"
    export XDG_CACHE_HOME="${BATS_TMPDIR}/test_cache"

    # Clean up any existing directories
    rm -rf "${BATS_TMPDIR}/test_config" "${BATS_TMPDIR}/test_data" "${BATS_TMPDIR}/test_cache"

    # Call the function
    cub_ensure_dirs

    # Verify data directory exists
    [[ -d "${BATS_TMPDIR}/test_data/cub" ]]
}

@test "cub_ensure_dirs creates logs directory" {
    # Use temp dir for testing
    export XDG_CONFIG_HOME="${BATS_TMPDIR}/test_config"
    export XDG_DATA_HOME="${BATS_TMPDIR}/test_data"
    export XDG_CACHE_HOME="${BATS_TMPDIR}/test_cache"

    # Clean up any existing directories
    rm -rf "${BATS_TMPDIR}/test_config" "${BATS_TMPDIR}/test_data" "${BATS_TMPDIR}/test_cache"

    # Call the function
    cub_ensure_dirs

    # Verify logs directory exists
    [[ -d "${BATS_TMPDIR}/test_data/cub/logs" ]]
}

@test "cub_ensure_dirs creates cache directory" {
    # Use temp dir for testing
    export XDG_CONFIG_HOME="${BATS_TMPDIR}/test_config"
    export XDG_DATA_HOME="${BATS_TMPDIR}/test_data"
    export XDG_CACHE_HOME="${BATS_TMPDIR}/test_cache"

    # Clean up any existing directories
    rm -rf "${BATS_TMPDIR}/test_config" "${BATS_TMPDIR}/test_data" "${BATS_TMPDIR}/test_cache"

    # Call the function
    cub_ensure_dirs

    # Verify cache directory exists
    [[ -d "${BATS_TMPDIR}/test_cache/cub" ]]
}
