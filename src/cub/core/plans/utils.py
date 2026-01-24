"""
Utility functions for working with plan directories.

Provides functions to:
- Extract epic IDs from itemized-plan.md
- Update plan.json with epic IDs

This mirrors the extraction logic from scripts/build-plan.sh for DRY compliance.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def get_epic_ids(plan_dir: Path) -> list[str]:
    """
    Extract epic IDs from a plan directory.

    Checks sources in order:
    1. plan.json epic_ids field (if already computed)
    2. itemized-plan.md headers (canonical source)

    The itemized-plan.md format supports two header styles:
    - "## Epic: cub-xxx - title"  (colon-space after Epic)
    - "## Epic cub-xxx: title"    (space after Epic, colon after ID)

    Args:
        plan_dir: Path to plan directory (e.g., plans/unified-tracking-model)

    Returns:
        List of epic IDs found in the plan

    Example:
        >>> epic_ids = get_epic_ids(Path("plans/unified-tracking-model"))
        >>> print(epic_ids)
        ['cub-r4n', 'cub-l7e', 'cub-e2p', 'cub-c5i', 'cub-d8b', 'cub-x3s']
    """
    epic_ids: list[str] = []

    # Check plan.json first for cached epic_ids
    plan_json = plan_dir / "plan.json"
    if plan_json.exists():
        try:
            with open(plan_json, encoding="utf-8") as f:
                plan_data = json.load(f)
                if "epic_ids" in plan_data and plan_data["epic_ids"]:
                    return list(plan_data["epic_ids"])
        except (json.JSONDecodeError, KeyError):
            pass

    # Parse from itemized-plan.md
    itemized_plan = plan_dir / "itemized-plan.md"
    if not itemized_plan.exists():
        return epic_ids

    # Pattern matches both formats:
    # - "## Epic: cub-xxx - title"
    # - "## Epic cub-xxx: title"
    # Mirrors: grep -E "^## Epic[: ]" | sed | cut -d' ' -f1 | cut -d':' -f1
    epic_pattern = re.compile(r"^## Epic[: ](.+)$")

    try:
        with open(itemized_plan, encoding="utf-8") as f:
            for line in f:
                match = epic_pattern.match(line.strip())
                if match:
                    # Extract the rest after "## Epic:" or "## Epic "
                    rest = match.group(1).strip()
                    # Get first space-separated word
                    first_word = rest.split()[0] if rest.split() else ""
                    # Remove any trailing colon
                    epic_id = first_word.rstrip(":")
                    if epic_id:
                        epic_ids.append(epic_id)
    except (OSError, UnicodeDecodeError):
        pass

    return epic_ids


def update_plan_epic_ids(plan_dir: Path) -> list[str]:
    """
    Update plan.json with epic IDs extracted from itemized-plan.md.

    This function:
    1. Extracts epic IDs from itemized-plan.md
    2. Updates plan.json with the epic_ids field
    3. Returns the list of epic IDs

    Args:
        plan_dir: Path to plan directory

    Returns:
        List of epic IDs that were written to plan.json

    Example:
        >>> epic_ids = update_plan_epic_ids(Path("plans/unified-tracking-model"))
        >>> print(f"Updated plan.json with {len(epic_ids)} epics")
    """
    # Parse from itemized-plan.md directly (bypass cached plan.json)
    itemized_plan = plan_dir / "itemized-plan.md"
    if not itemized_plan.exists():
        return []

    epic_ids: list[str] = []
    epic_pattern = re.compile(r"^## Epic[: ](.+)$")

    try:
        with open(itemized_plan, encoding="utf-8") as f:
            for line in f:
                match = epic_pattern.match(line.strip())
                if match:
                    rest = match.group(1).strip()
                    first_word = rest.split()[0] if rest.split() else ""
                    epic_id = first_word.rstrip(":")
                    if epic_id:
                        epic_ids.append(epic_id)
    except (OSError, UnicodeDecodeError):
        return []

    # Update plan.json
    plan_json = plan_dir / "plan.json"
    plan_data: dict[str, object] = {}

    if plan_json.exists():
        try:
            with open(plan_json, encoding="utf-8") as f:
                plan_data = json.load(f)
        except json.JSONDecodeError:
            plan_data = {}

    plan_data["epic_ids"] = epic_ids

    try:
        with open(plan_json, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, indent=2)
            f.write("\n")
    except OSError:
        pass

    return epic_ids
