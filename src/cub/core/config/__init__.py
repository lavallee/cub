"""
Configuration models and loading.

This module provides Pydantic models for cub configuration
with multi-layer merging: defaults < user < project < env vars.
"""

from .loader import (
    clear_cache,
    get_project_config_path,
    get_user_config_path,
    get_xdg_config_home,
    load_config,
)
from .models import (
    BackendConfig,
    BudgetConfig,
    CubConfig,
    GuardrailsConfig,
    HarnessConfig,
    HooksConfig,
    InterviewConfig,
    LoopConfig,
    ReviewConfig,
    StateConfig,
)

__all__ = [
    # Models
    "BackendConfig",
    "BudgetConfig",
    "CubConfig",
    "GuardrailsConfig",
    "HarnessConfig",
    "HooksConfig",
    "InterviewConfig",
    "LoopConfig",
    "ReviewConfig",
    "StateConfig",
    # Loader functions
    "clear_cache",
    "get_project_config_path",
    "get_user_config_path",
    "get_xdg_config_home",
    "load_config",
]
