"""
Template freshness checking for cub plan commands.

Ensures that planning skill templates (.claude/commands/cub:*.md) are
up-to-date with the bundled versions from the cub package. This prevents
template skew where a project has stale templates that miss critical
fixes (like ensure/complete-stage calls).

The sync logic:
- If project template is missing → copy from bundled
- If project matches bundled → no-op
- If project matches a PREVIOUS bundled hash → safe to auto-update
- If project was manually customized → warn but don't overwrite

Template hashes are tracked in .cub/template-hashes.json.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Templates that are part of the planning pipeline
PLANNING_TEMPLATES = [
    "cub:orient.md",
    "cub:architect.md",
    "cub:itemize.md",
    "cub:spec.md",
    "cub:stage.md",
]

HASHES_FILE = "template-hashes.json"


def _file_hash(path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_hashes(cub_dir: Path) -> dict[str, str]:
    """Load template hash tracking file."""
    hashes_path = cub_dir / HASHES_FILE
    if not hashes_path.exists():
        return {}
    try:
        data = json.loads(hashes_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        return {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_hashes(cub_dir: Path, hashes: dict[str, str]) -> None:
    """Save template hash tracking file."""
    hashes_path = cub_dir / HASHES_FILE
    cub_dir.mkdir(parents=True, exist_ok=True)
    hashes_path.write_text(
        json.dumps(hashes, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_fresh_templates(project_root: Path) -> list[str]:
    """
    Ensure planning templates in .claude/commands/ are fresh.

    Compares project-local templates against bundled versions and
    updates them when safe to do so.

    Args:
        project_root: Project root directory.

    Returns:
        List of warning messages for templates that couldn't be updated
        (i.e., user has custom modifications).
    """
    try:
        from cub.cli.update import get_templates_dir
        bundled_dir = get_templates_dir() / "commands"
    except (FileNotFoundError, ImportError):
        logger.debug("Could not locate bundled templates directory")
        return []

    if not bundled_dir.is_dir():
        return []

    project_commands_dir = project_root / ".claude" / "commands"
    cub_dir = project_root / ".cub"
    hashes = _load_hashes(cub_dir)
    warnings: list[str] = []
    hashes_changed = False

    for template_name in PLANNING_TEMPLATES:
        bundled_path = bundled_dir / template_name
        if not bundled_path.exists():
            continue

        project_path = project_commands_dir / template_name
        bundled_hash = _file_hash(bundled_path)
        previous_bundled_hash = hashes.get(template_name)

        if not project_path.exists():
            # Missing → copy from bundled
            project_commands_dir.mkdir(parents=True, exist_ok=True)
            project_path.write_bytes(bundled_path.read_bytes())
            hashes[template_name] = bundled_hash
            hashes_changed = True
            logger.debug("Installed missing template: %s", template_name)
            continue

        project_hash = _file_hash(project_path)

        if project_hash == bundled_hash:
            # Already up to date
            hashes[template_name] = bundled_hash
            if previous_bundled_hash != bundled_hash:
                hashes_changed = True
            continue

        if previous_bundled_hash is not None and project_hash == previous_bundled_hash:
            # Project matches the old bundled hash → safe to auto-update
            project_path.write_bytes(bundled_path.read_bytes())
            hashes[template_name] = bundled_hash
            hashes_changed = True
            logger.debug("Auto-updated template: %s", template_name)
            continue

        if previous_bundled_hash is None:
            # First time tracking — project template exists but we have no baseline.
            # Record the current bundled hash for future comparisons.
            # If project doesn't match bundled, it may be customized — warn.
            hashes[template_name] = bundled_hash
            hashes_changed = True

            if project_hash != bundled_hash:
                warnings.append(
                    f"{template_name}: project template differs from bundled "
                    f"(may be customized). Run `cub update` to force-update."
                )
            continue

        # Project has been manually customized (doesn't match old or new bundled)
        warnings.append(
            f"{template_name}: project template has custom modifications. "
            f"Run `cub update` to force-update."
        )
        # Still update the hash tracking so we know about the new bundled version
        hashes[template_name] = bundled_hash
        hashes_changed = True

    if hashes_changed:
        _save_hashes(cub_dir, hashes)

    return warnings
