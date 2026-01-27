"""
Claude Code statusline installer for cub projects.

Installs a standalone Python script into .cub/scripts/statusline.py and
configures .claude/settings.json to point to it. The script is self-contained
(no cub imports) so it starts in ~10ms instead of ~1s.

The statusline reads Claude Code's JSON from stdin and outputs a single-line
status string with ANSI colors showing: task counts, active run info,
context window usage, and session cost.
"""

import json
from pathlib import Path
from typing import Any

# Type alias for JSON dicts
JsonDict = dict[str, Any]

CLAUDE_SETTINGS: JsonDict = {
    "statusLine": {
        "type": "command",
        "command": "python3 .cub/scripts/statusline.py",
        "padding": 0,
    }
}


def get_statusline_script() -> str:
    """Read the statusline script from templates."""
    from cub.cli.update import get_templates_dir

    script_path = get_templates_dir() / "scripts" / "statusline.py"
    return script_path.read_text()


def install_statusline(project_dir: Path, force: bool = False) -> bool:
    """
    Install Claude Code statusline into a cub project.

    Writes two files:
    1. .cub/scripts/statusline.py  — standalone script (no cub imports)
    2. .claude/settings.json       — points Claude Code at the script

    Returns True if files were written, False if skipped.
    Merges with existing .claude/settings.json, preserving other keys.
    """
    script_content = get_statusline_script()

    # Install the script
    scripts_dir = project_dir / ".cub" / "scripts"
    script_file = scripts_dir / "statusline.py"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    if script_file.exists() and not force:
        # Check if it's outdated by comparing content
        if script_file.read_text() == script_content:
            # Script is current, just ensure settings.json exists
            return _install_settings(project_dir, force)
    script_file.write_text(script_content)
    script_file.chmod(0o755)

    # Install the settings
    _install_settings(project_dir, force)
    return True


def _install_settings(project_dir: Path, force: bool = False) -> bool:
    """Write .claude/settings.json with statusline config."""
    settings_dir = project_dir / ".claude"
    settings_file = settings_dir / "settings.json"

    existing: JsonDict = {}
    if settings_file.exists():
        if not force and "statusLine" in settings_file.read_text():
            return False
        try:
            existing = json.loads(settings_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    existing.update(CLAUDE_SETTINGS)

    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(existing, indent=2) + "\n")
    return True
