#!/usr/bin/env python3
"""
Move specs from implementing/ to released/ during a release.

This script is called by cut-release.sh after all checks pass.
It moves all specs in specs/implementing/ to specs/released/.

Usage:
    python scripts/move_specs_released.py [--dry-run] [--verbose]

Exit codes:
    0 - Success (specs moved or no specs to move)
    1 - Error (failed to move specs)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Move specs from implementing/ to released/."""
    parser = argparse.ArgumentParser(
        description="Move specs from implementing/ to released/"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be moved without moving",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory (default: current directory)",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    specs_root = project_root / "specs"

    if not specs_root.exists():
        if args.verbose:
            print(f"No specs directory found at {specs_root}")
        return 0

    implementing_dir = specs_root / "implementing"
    if not implementing_dir.exists():
        if args.verbose:
            print("No specs/implementing/ directory found")
        return 0

    # Find all specs in implementing/
    specs = list(implementing_dir.glob("*.md"))
    if not specs:
        if args.verbose:
            print("No specs in implementing/ to move")
        return 0

    if args.dry_run:
        print(f"[DRY-RUN] Would move {len(specs)} spec(s) to released/:")
        for spec in specs:
            print(f"  - {spec.name}")
        return 0

    # Import and use the lifecycle module
    try:
        from cub.core.specs.lifecycle import SpecLifecycleError, move_specs_to_released
    except ImportError as e:
        print(f"Error: Could not import cub.core.specs.lifecycle: {e}", file=sys.stderr)
        print("Make sure cub is installed: pip install -e .", file=sys.stderr)
        return 1

    try:
        moved_paths = move_specs_to_released(specs_root, verbose=args.verbose)
        if moved_paths:
            print(f"Moved {len(moved_paths)} spec(s) to released/:")
            for path in moved_paths:
                print(f"  - {path.name}")
        else:
            if args.verbose:
                print("No specs to move")
        return 0
    except SpecLifecycleError as e:
        print(f"Error moving specs: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
