"""Environment loading helpers.

Cub supports layered configuration:
- OS environment (highest precedence)
- Project environment files (e.g. .env)
- User environment files (e.g. ~/.config/cub/.env)

We intentionally do *not* let .env override variables that are already present
in the process environment (e.g. exported in the shell).

Precedence implemented here:
  os.environ (pre-existing) > project .env > user .env

This provides:
- per-user defaults (user .env)
- per-project overrides (project .env)
- easy CI/shell overrides (exported env)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from dotenv import dotenv_values


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values = dotenv_values(path)
    out: dict[str, str] = {}
    for k, v in values.items():
        if k is None or v is None:
            continue
        out[str(k)] = str(v)
    return out


def load_layered_env(
    *,
    project_dir: Path | None = None,
    user_env_paths: Iterable[Path] | None = None,
    project_env_paths: Iterable[Path] | None = None,
) -> None:
    """Load environment variables from user + project .env files.

    Args:
        project_dir: base directory for project env paths (defaults to cwd)
        user_env_paths: explicit user env file paths
        project_env_paths: explicit project env file paths

    Notes:
        We track which keys came from user env so that project env can override
        those keys while still never overriding pre-existing OS environment.
    """
    if project_dir is None:
        project_dir = Path.cwd()

    # Default paths
    if user_env_paths is None:
        xdg_home = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        user_env_paths = [xdg_home / "cub" / ".env"]

    if project_env_paths is None:
        project_env_paths = [project_dir / ".env", project_dir / ".env.local"]

    # Load user env (lowest priority)
    user_set_keys: set[str] = set()
    for p in user_env_paths:
        for k, v in _read_env(Path(p)).items():
            if k not in os.environ:
                os.environ[k] = v
                user_set_keys.add(k)

    # Load project env (overrides user-set values, but never overrides OS env)
    for p in project_env_paths:
        for k, v in _read_env(Path(p)).items():
            if k not in os.environ or k in user_set_keys:
                os.environ[k] = v
