#!/usr/bin/env python3
"""Check per-file coverage against stability tier thresholds.

This script reads coverage data from coverage.json and checks each file
against its tier-specific threshold defined in STABILITY.md.

Usage:
    # Generate coverage JSON first
    pytest --cov=src/cub --cov-report=json

    # Then check thresholds
    python scripts/check_coverage_tiers.py

    # Verbose output
    python scripts/check_coverage_tiers.py --verbose

    # Strict mode (fail on any threshold violation)
    python scripts/check_coverage_tiers.py --strict
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Tier thresholds from STABILITY.md
SOLID_THRESHOLD = 80
MODERATE_THRESHOLD = 60
EXPERIMENTAL_THRESHOLD = 40

# File patterns for each tier
SOLID_PATTERNS = [
    r"^src/cub/core/config/.*\.py$",
    r"^src/cub/core/tasks/backend\.py$",
    r"^src/cub/core/tasks/models\.py$",
    r"^src/cub/core/harness/backend\.py$",
    r"^src/cub/core/harness/models\.py$",
    r"^src/cub/core/captures/models\.py$",
    r"^src/cub/core/branches/models\.py$",
    r"^src/cub/core/worktree/manager\.py$",
    r"^src/cub/dashboard/renderer\.py$",
    r"^src/cub/utils/logging\.py$",
]

MODERATE_PATTERNS = [
    r"^src/cub/cli/run\.py$",
    r"^src/cub/core/tasks/beads\.py$",
    r"^src/cub/core/tasks/json\.py$",
    r"^src/cub/core/harness/claude\.py$",
    r"^src/cub/core/captures/store\.py$",
    r"^src/cub/core/sandbox/docker\.py$",
    r"^src/cub/utils/hooks\.py$",
    r"^src/cub/core/github/client\.py$",
    r"^src/cub/core/pr/service\.py$",
]

EXPERIMENTAL_PATTERNS = [
    r"^src/cub/audit/.*\.py$",
    r"^src/cub/core/sandbox/provider\.py$",
    r"^src/cub/core/sandbox/state\.py$",
    r"^src/cub/core/captures/project_id\.py$",
    r"^src/cub/core/github/issue_mode\.py$",
    r"^src/cub/core/worktree/parallel\.py$",
    r"^src/cub/cli/captures\.py$",
    r"^src/cub/cli/organize_captures\.py$",
]

# UI/Delegated files have no threshold
UI_DELEGATED_PATTERNS = [
    r"^src/cub/cli/status\.py$",
    r"^src/cub/cli/monitor\.py$",
    r"^src/cub/cli/sandbox\.py$",
    r"^src/cub/cli/upgrade\.py$",
    r"^src/cub/cli/uninstall\.py$",
    r"^src/cub/cli/worktree\.py$",
    r"^src/cub/cli/delegated\.py$",
    r"^src/cub/cli/audit\.py$",
    r"^src/cub/cli/investigate\.py$",
    r"^src/cub/cli/merge\.py$",
    r"^src/cub/cli/pr\.py$",
    r"^src/cub/dashboard/tmux\.py$",
    r"^src/cub/core/prep/plan_markdown\.py$",
]


@dataclass
class FileResult:
    """Coverage result for a single file."""

    path: str
    coverage: float
    tier: str
    threshold: int | None
    passes: bool


def get_tier(filepath: str) -> tuple[str, int | None]:
    """Determine the stability tier and threshold for a file."""
    for pattern in SOLID_PATTERNS:
        if re.match(pattern, filepath):
            return ("solid", SOLID_THRESHOLD)

    for pattern in MODERATE_PATTERNS:
        if re.match(pattern, filepath):
            return ("moderate", MODERATE_THRESHOLD)

    for pattern in EXPERIMENTAL_PATTERNS:
        if re.match(pattern, filepath):
            return ("experimental", EXPERIMENTAL_THRESHOLD)

    for pattern in UI_DELEGATED_PATTERNS:
        if re.match(pattern, filepath):
            return ("ui/delegated", None)

    # Default to experimental for unclassified files
    return ("unclassified", None)


def check_coverage(coverage_file: Path, verbose: bool = False) -> list[FileResult]:
    """Check coverage against tier thresholds."""
    if not coverage_file.exists():
        print(f"Error: Coverage file not found: {coverage_file}", file=sys.stderr)
        print("Run: pytest --cov=src/cub --cov-report=json", file=sys.stderr)
        sys.exit(1)

    with open(coverage_file) as f:
        data = json.load(f)

    results: list[FileResult] = []

    for filepath, file_data in data.get("files", {}).items():
        coverage_pct = file_data.get("summary", {}).get("percent_covered", 0)
        tier, threshold = get_tier(filepath)

        if threshold is not None:
            passes = coverage_pct >= threshold
        else:
            passes = True  # No threshold for ui/delegated

        results.append(
            FileResult(
                path=filepath,
                coverage=coverage_pct,
                tier=tier,
                threshold=threshold,
                passes=passes,
            )
        )

    return results


def print_results(results: list[FileResult], verbose: bool = False) -> tuple[int, int]:
    """Print coverage results and return (passed, failed) counts."""
    # Group by tier
    by_tier: dict[str, list[FileResult]] = {}
    for r in results:
        by_tier.setdefault(r.tier, []).append(r)

    passed = 0
    failed = 0

    tier_order = ["solid", "moderate", "experimental", "ui/delegated", "unclassified"]

    for tier in tier_order:
        tier_results = by_tier.get(tier, [])
        if not tier_results:
            continue

        tier_results.sort(key=lambda x: x.path)
        threshold = tier_results[0].threshold

        print(f"\n{'=' * 60}")
        if threshold:
            print(f"{tier.upper()} TIER (threshold: {threshold}%)")
        else:
            print(f"{tier.upper()} TIER (no threshold)")
        print("=" * 60)

        for r in tier_results:
            if r.passes:
                passed += 1
                status = "PASS" if r.threshold else "----"
                color = "\033[92m" if r.threshold else "\033[90m"  # green or gray
            else:
                failed += 1
                status = "FAIL"
                color = "\033[91m"  # red

            reset = "\033[0m"

            if verbose or not r.passes:
                threshold_str = f"/{r.threshold}%" if r.threshold else ""
                print(f"  {color}[{status}]{reset} {r.path}: {r.coverage:.1f}%{threshold_str}")
            elif r.threshold:
                print(f"  {color}[{status}]{reset} {r.path}: {r.coverage:.1f}%")

    return passed, failed


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check per-file coverage against stability tier thresholds"
    )
    parser.add_argument(
        "--coverage-file",
        type=Path,
        default=Path("coverage.json"),
        help="Path to coverage.json (default: coverage.json)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show all files, not just failures",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code if any thresholds are violated",
    )
    args = parser.parse_args()

    results = check_coverage(args.coverage_file, args.verbose)
    passed, failed = print_results(results, args.verbose)

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print("\nFiles below their tier threshold:")
        for r in results:
            if not r.passes and r.threshold:
                gap = r.threshold - r.coverage
                print(f"  - {r.path}: {r.coverage:.1f}% (needs +{gap:.1f}%)")

    if args.strict and failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
