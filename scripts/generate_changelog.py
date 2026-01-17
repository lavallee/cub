#!/usr/bin/env python3
"""
Generate CHANGELOG.md entry from git commits since last release.

Parses conventional commit messages and groups them by type:
- feat: -> Added
- fix: -> Fixed
- chore:, docs:, refactor:, test: -> Changed
- BREAKING CHANGE or !: -> Breaking Changes

Usage:
    python scripts/generate_changelog.py 0.25.2
    python scripts/generate_changelog.py 0.25.2 --dry-run
    python scripts/generate_changelog.py 0.25.2 --prepend  # Update CHANGELOG.md
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Commit:
    """A parsed git commit."""

    hash: str
    type: str
    scope: str | None
    description: str
    body: str
    breaking: bool
    raw_message: str


@dataclass
class ChangelogEntry:
    """A changelog entry for a version."""

    version: str
    date: str
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    breaking: list[str] = field(default_factory=list)


def get_previous_tag() -> str | None:
    """Get the most recent version tag."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_commits_since_tag(tag: str | None) -> list[str]:
    """Get all commit hashes since a tag (or all commits if no tag)."""
    if tag:
        range_spec = f"{tag}..HEAD"
    else:
        range_spec = "HEAD"

    try:
        result = subprocess.run(
            ["git", "log", range_spec, "--format=%H"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [h for h in result.stdout.strip().split("\n") if h]
    except subprocess.CalledProcessError:
        return []


def get_commit_message(commit_hash: str) -> str:
    """Get the full commit message for a hash."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B", commit_hash],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def parse_conventional_commit(message: str, commit_hash: str) -> Commit:
    """Parse a conventional commit message."""
    lines = message.split("\n")
    first_line = lines[0] if lines else ""
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

    # Pattern: type(scope)!: description or type!: description or type: description
    pattern = r"^(\w+)(?:\(([^)]+)\))?(!)?\s*:\s*(.+)$"
    match = re.match(pattern, first_line)

    if match:
        commit_type = match.group(1).lower()
        scope = match.group(2)
        breaking_mark = match.group(3) == "!"
        description = match.group(4)
    else:
        # Non-conventional commit - treat as "other"
        commit_type = "other"
        scope = None
        breaking_mark = False
        description = first_line

    # Check for BREAKING CHANGE in body
    breaking = breaking_mark or "BREAKING CHANGE" in body.upper()

    return Commit(
        hash=commit_hash[:8],
        type=commit_type,
        scope=scope,
        description=description,
        body=body,
        breaking=breaking,
        raw_message=message,
    )


def format_commit_line(commit: Commit) -> str:
    """Format a commit as a changelog line."""
    desc = commit.description

    # Capitalize first letter
    if desc:
        desc = desc[0].upper() + desc[1:]

    # Add scope if present
    if commit.scope:
        return f"**{commit.scope}**: {desc}"
    else:
        return desc


def should_skip_commit(commit: Commit) -> bool:
    """Determine if a commit should be skipped from the changelog."""
    desc_lower = commit.description.lower()

    # Skip merge commits
    if desc_lower.startswith("merge "):
        return True

    # Skip version bumps
    if "bump version" in desc_lower:
        return True

    # Skip release-related chores
    if commit.type == "chore" and "release" in desc_lower:
        return True

    # Skip beads sync commits
    if desc_lower.startswith("bd sync"):
        return True

    # Skip WIP commits
    if desc_lower.startswith("wip"):
        return True

    # Skip revert of sync commits
    if "revert" in desc_lower and "sync" in desc_lower:
        return True

    # Skip generic sync/update commits
    if desc_lower in ("sync", "update", "updates", "wip"):
        return True

    # Skip commits that are just file additions without context
    if desc_lower.startswith("adding ") and len(desc_lower) < 50:
        return True

    # Skip lock file updates
    if "uv.lock" in desc_lower or "lock file" in desc_lower:
        return True

    # Skip generic "specs and beads" type commits
    if desc_lower in ("specs and beads updates", "specs updates", "beads updates"):
        return True

    # Skip learnings/progress updates (internal docs)
    if "learnings" in desc_lower and "progress" in desc_lower:
        return True

    return False


def generate_changelog_entry(version: str, commits: list[Commit]) -> ChangelogEntry:
    """Generate a changelog entry from commits."""
    entry = ChangelogEntry(version=version, date=date.today().isoformat())

    for commit in commits:
        line = format_commit_line(commit)

        # Skip noise commits
        if should_skip_commit(commit):
            continue

        # Handle breaking changes
        if commit.breaking:
            entry.breaking.append(line)

        # Categorize by type
        if commit.type == "feat":
            entry.added.append(line)
        elif commit.type == "fix":
            entry.fixed.append(line)
        elif commit.type in ("docs", "refactor", "perf", "test", "build", "ci"):
            entry.changed.append(line)
        elif commit.type == "chore":
            # Only include significant chores
            if any(
                kw in commit.description.lower()
                for kw in ("upgrade", "update", "migrate", "remove", "delete", "drop")
            ):
                entry.changed.append(line)
        elif commit.type == "revert":
            entry.removed.append(line)
        elif commit.type == "other":
            # Non-conventional commits go to Changed
            if line and not line.lower().startswith("wip"):
                entry.changed.append(line)

    return entry


def format_changelog_section(entry: ChangelogEntry) -> str:
    """Format a changelog entry as markdown."""
    lines = [f"## [{entry.version}] - {entry.date}", ""]

    if entry.breaking:
        lines.append("### Breaking Changes")
        lines.append("")
        for item in entry.breaking:
            lines.append(f"- {item}")
        lines.append("")

    if entry.added:
        lines.append("### Added")
        lines.append("")
        for item in entry.added:
            lines.append(f"- {item}")
        lines.append("")

    if entry.changed:
        lines.append("### Changed")
        lines.append("")
        for item in entry.changed:
            lines.append(f"- {item}")
        lines.append("")

    if entry.fixed:
        lines.append("### Fixed")
        lines.append("")
        for item in entry.fixed:
            lines.append(f"- {item}")
        lines.append("")

    if entry.removed:
        lines.append("### Removed")
        lines.append("")
        for item in entry.removed:
            lines.append(f"- {item}")
        lines.append("")

    # If no categorized changes, add a placeholder
    if not any([entry.added, entry.changed, entry.fixed, entry.removed, entry.breaking]):
        lines.append("### Changed")
        lines.append("")
        lines.append("- Various improvements and updates")
        lines.append("")

    return "\n".join(lines)


def prepend_to_changelog(changelog_path: Path, new_section: str) -> bool:
    """Prepend a new section to the changelog file."""
    if not changelog_path.exists():
        print(f"Error: Changelog not found at {changelog_path}")
        return False

    content = changelog_path.read_text()

    # Find the first ## header (first version entry)
    match = re.search(r"^## \[", content, re.MULTILINE)

    if match:
        # Insert before the first version entry
        insert_pos = match.start()
        new_content = content[:insert_pos] + new_section + "\n---\n\n" + content[insert_pos:]
    else:
        # No existing entries, append after the header
        # Find end of header section (after the format note)
        header_end = content.find("---")
        if header_end != -1:
            # Find the next --- or end
            next_sep = content.find("---", header_end + 3)
            if next_sep != -1:
                insert_pos = next_sep + 3
                new_content = content[:insert_pos] + "\n\n" + new_section + content[insert_pos:]
            else:
                new_content = content + "\n\n" + new_section
        else:
            new_content = content + "\n\n" + new_section

    changelog_path.write_text(new_content)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate CHANGELOG.md entry from git commits"
    )
    parser.add_argument("version", help="Version number (e.g., 0.25.2)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the changelog entry without modifying files",
    )
    parser.add_argument(
        "--prepend",
        action="store_true",
        help="Prepend the entry to CHANGELOG.md",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="Path to changelog file (default: CHANGELOG.md)",
    )
    args = parser.parse_args()

    # Resolve changelog path relative to project root
    project_root = Path(__file__).parent.parent
    changelog_path = project_root / args.changelog

    # Get previous tag
    prev_tag = get_previous_tag()
    if prev_tag:
        print(f"Previous tag: {prev_tag}")
    else:
        print("No previous tag found, using all commits")

    # Get commits since last tag
    commit_hashes = get_commits_since_tag(prev_tag)
    print(f"Found {len(commit_hashes)} commits since {prev_tag or 'beginning'}")

    if not commit_hashes:
        print("No new commits found")
        return 1

    # Parse commits
    commits = []
    for h in commit_hashes:
        message = get_commit_message(h)
        commit = parse_conventional_commit(message, h)
        commits.append(commit)

    # Generate changelog entry
    entry = generate_changelog_entry(args.version, commits)
    section = format_changelog_section(entry)

    print("\n" + "=" * 60)
    print(section)
    print("=" * 60 + "\n")

    if args.dry_run:
        print("[DRY RUN] Would prepend above to CHANGELOG.md")
        return 0

    if args.prepend:
        if prepend_to_changelog(changelog_path, section):
            print(f"Updated {changelog_path}")
            return 0
        else:
            return 1
    else:
        print("Use --prepend to update CHANGELOG.md")
        return 0


if __name__ == "__main__":
    sys.exit(main())
