"""
Configuration loading with multi-layer merging.

Implements the configuration precedence chain:
    defaults < user config < project config < env vars

This matches the behavior of the Bash lib/config.sh implementation.
"""

import json
import os
from pathlib import Path
from typing import Any

from .models import CubConfig

# Global cache to avoid reloading config multiple times per session
_config_cache: CubConfig | None = None


def get_xdg_config_home() -> Path:
    """
    Get XDG config home directory.

    Returns:
        Path to config directory (defaults to ~/.config)
    """
    if xdg_home := os.environ.get("XDG_CONFIG_HOME"):
        return Path(xdg_home)
    return Path.home() / ".config"


def get_user_config_path() -> Path:
    """
    Get path to user configuration file.

    Returns:
        Path to ~/.config/cub/config.json (or XDG equivalent)
    """
    return get_xdg_config_home() / "cub" / "config.json"


def get_project_config_path(cwd: Path | None = None) -> Path:
    """
    Get path to project configuration file.

    Args:
        cwd: Working directory to search from (defaults to current directory)

    Returns:
        Path to .cub.json in the project root
    """
    if cwd is None:
        cwd = Path.cwd()
    return cwd / ".cub.json"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries.

    Values in `override` take precedence over values in `base`.
    This is a recursive merge - nested dicts are merged, not replaced.

    Args:
        base: Base dictionary (lower priority)
        override: Override dictionary (higher priority)

    Returns:
        Merged dictionary with override values taking precedence

    Example:
        >>> base = {"a": 1, "b": {"x": 10, "y": 20}}
        >>> override = {"b": {"y": 30, "z": 40}, "c": 3}
        >>> deep_merge(base, override)
        {"a": 1, "b": {"x": 10, "y": 30, "z": 40}, "c": 3}
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Both are dicts - recursively merge
            result[key] = deep_merge(result[key], value)
        else:
            # Override wins
            result[key] = value

    return result


def load_json_file(path: Path) -> dict[str, Any] | None:
    """
    Load a JSON file, returning None if it doesn't exist or is invalid.

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON as dict, or None if file doesn't exist or can't be parsed
    """
    if not path.exists():
        return None

    try:
        with path.open() as f:
            data = json.load(f)
            # Type narrowing for mypy - json.load can return Any
            if isinstance(data, dict):
                return data
            return None
    except (json.JSONDecodeError, OSError) as e:
        # Log warning but continue - config system should be resilient
        print(f"Warning: Failed to parse config at {path}: {e}")
        return None


def apply_env_overrides(config_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Apply environment variable overrides to configuration.

    Env vars have the highest precedence and override all config files.

    Supported env vars:
        CUB_BUDGET - overrides budget.default
        CUB_REVIEW_STRICT - overrides review.plan_strict
        CUB_CIRCUIT_BREAKER_ENABLED - overrides circuit_breaker.enabled
        CUB_CIRCUIT_BREAKER_TIMEOUT - overrides circuit_breaker.timeout_minutes

    Args:
        config_dict: Configuration dictionary to override

    Returns:
        Configuration dictionary with env var overrides applied
    """
    result = config_dict.copy()

    # CUB_BUDGET overrides budget.default
    if budget_str := os.environ.get("CUB_BUDGET"):
        try:
            budget_value = int(budget_str)
            if "budget" not in result:
                result["budget"] = {}
            result["budget"]["default"] = budget_value
        except ValueError:
            print(f"Warning: Invalid CUB_BUDGET value '{budget_str}', ignoring")

    # CUB_REVIEW_STRICT overrides review.plan_strict
    if strict_str := os.environ.get("CUB_REVIEW_STRICT"):
        strict_value = strict_str.lower() not in ("false", "0", "")
        if "review" not in result:
            result["review"] = {}
        result["review"]["plan_strict"] = strict_value

    # CUB_CIRCUIT_BREAKER_ENABLED overrides circuit_breaker.enabled
    if cb_enabled_str := os.environ.get("CUB_CIRCUIT_BREAKER_ENABLED"):
        cb_enabled = cb_enabled_str.lower() not in ("false", "0", "")
        if "circuit_breaker" not in result:
            result["circuit_breaker"] = {}
        result["circuit_breaker"]["enabled"] = cb_enabled

    # CUB_CIRCUIT_BREAKER_TIMEOUT overrides circuit_breaker.timeout_minutes
    if cb_timeout_str := os.environ.get("CUB_CIRCUIT_BREAKER_TIMEOUT"):
        try:
            cb_timeout = int(cb_timeout_str)
            if cb_timeout < 1:
                print(
                    f"Warning: CUB_CIRCUIT_BREAKER_TIMEOUT must be >= 1, got {cb_timeout}, ignoring"
                )
            else:
                if "circuit_breaker" not in result:
                    result["circuit_breaker"] = {}
                result["circuit_breaker"]["timeout_minutes"] = cb_timeout
        except ValueError:
            msg = (
                f"Warning: Invalid CUB_CIRCUIT_BREAKER_TIMEOUT "
                f"value '{cb_timeout_str}', ignoring"
            )
            print(msg)

    return result


def get_default_config() -> dict[str, Any]:
    """
    Get hardcoded default configuration.

    These defaults match the Bash implementation in lib/config.sh.

    Returns:
        Dictionary with default configuration values
    """
    return {
        "guardrails": {
            "max_task_iterations": 3,
            "max_run_iterations": 50,
            "iteration_warning_threshold": 0.8,
            "secret_patterns": [
                "api[_-]?key",
                "password",
                "token",
                "secret",
                "authorization",
                "credentials",
            ],
        },
        "review": {"plan_strict": False, "block_on_concerns": False},
    }


def load_config(project_dir: Path | None = None, use_cache: bool = True) -> CubConfig:
    """
    Load configuration with multi-layer merging.

    Configuration precedence (highest to lowest):
        1. Environment variables (CUB_*)
        2. Project config (.cub.json)
        3. User config (~/.config/cub/config.json)
        4. Hardcoded defaults

    Args:
        project_dir: Project directory to load .cub.json from (defaults to cwd)
        use_cache: If True, return cached config from previous load

    Returns:
        Validated CubConfig instance

    Raises:
        ValidationError: If the merged config fails Pydantic validation

    Example:
        >>> config = load_config()
        >>> config.guardrails.max_task_iterations
        3
        >>> config.review.plan_strict
        False
    """
    global _config_cache

    # Return cached config if available
    if use_cache and _config_cache is not None:
        return _config_cache

    # Start with defaults
    merged = get_default_config()

    # Merge user config
    user_config_path = get_user_config_path()
    if user_config := load_json_file(user_config_path):
        merged = deep_merge(merged, user_config)

    # Merge project config (higher priority than user config)
    project_config_path = get_project_config_path(project_dir)
    if project_config := load_json_file(project_config_path):
        merged = deep_merge(merged, project_config)

    # Apply environment variable overrides (highest priority)
    merged = apply_env_overrides(merged)

    # Validate with Pydantic
    config = CubConfig(**merged)

    # Cache for subsequent calls
    _config_cache = config

    return config


def clear_cache() -> None:
    """
    Clear the cached configuration.

    Useful for testing or when config files change during execution.
    """
    global _config_cache
    _config_cache = None
