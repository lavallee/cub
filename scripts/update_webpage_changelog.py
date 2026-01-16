#!/usr/bin/env python3
"""
Update the webpage's Recent Updates section from CHANGELOG.md.

This script parses the changelog and generates HTML for the Recent Updates
section of the landing page. It can be run as part of the deploy process.

Usage:
    python scripts/update_webpage_changelog.py
    python scripts/update_webpage_changelog.py --dry-run
    python scripts/update_webpage_changelog.py --count 5
"""

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Release:
    """A parsed release from the changelog."""

    version: str
    date: str
    title: str
    description: str
    highlights: list[str]


def parse_changelog(changelog_path: Path, max_releases: int = 3) -> list[Release]:
    """Parse the changelog and extract recent releases."""
    content = changelog_path.read_text()

    # Pattern to match release headers: ## [0.25.0] - 2026-01-16
    release_pattern = re.compile(
        r"^## \[(\d+\.\d+(?:\.\d+)?)\] - (\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE
    )

    releases = []
    matches = list(release_pattern.finditer(content))

    for i, match in enumerate(matches[:max_releases]):
        version = match.group(1)
        date = match.group(2)

        # Get content until next release or end of file
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section = content[start:end].strip()

        # Extract title from first ### Added line or summary
        title = extract_title(section)
        description = extract_description(section)
        highlights = extract_highlights(section)

        releases.append(
            Release(
                version=version,
                date=date,
                title=title,
                description=description,
                highlights=highlights[:3],  # Limit to 3 highlights
            )
        )

    return releases


def extract_title(section: str) -> str:
    """Extract the release title from the section."""
    # Look for ### Added - Title pattern
    title_match = re.search(r"^### Added - (.+)$", section, re.MULTILINE)
    if title_match:
        return title_match.group(1).strip()

    # Look for ### Changed - Title pattern
    title_match = re.search(r"^### Changed - (.+)$", section, re.MULTILINE)
    if title_match:
        return title_match.group(1).strip()

    # Fallback: first ### header
    header_match = re.search(r"^### (.+)$", section, re.MULTILINE)
    if header_match:
        return header_match.group(1).strip()

    return "Updates"


def extract_description(section: str) -> str:
    """Extract a brief description from the section."""
    lines = section.split("\n")

    # Strategy 1: Find first paragraph after ### header (non-bullet text)
    in_header_section = False
    paragraph_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if paragraph_lines:
                break
            continue
        if stripped.startswith("###"):
            in_header_section = True
            continue
        if in_header_section:
            # Skip bullet points and sub-headers
            if stripped.startswith(("-", "*", "#")):
                if paragraph_lines:
                    break
                continue
            paragraph_lines.append(stripped)

    if paragraph_lines:
        desc = " ".join(paragraph_lines)
    else:
        # Strategy 2: Extract from first few bullet points
        bullet_items = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- **") or stripped.startswith("* **"):
                # Extract the bold part as a feature name
                match = re.match(r"[-*]\s+\*\*([^*]+)\*\*", stripped)
                if match:
                    bullet_items.append(match.group(1))
                    if len(bullet_items) >= 3:
                        break

        if bullet_items:
            desc = ". ".join(bullet_items) + "."
        else:
            return "Various improvements and bug fixes."

    # Clean up markdown formatting
    desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", desc)
    desc = re.sub(r"\*([^*]+)\*", r"\1", desc)
    desc = re.sub(r"`([^`]+)`", r"\1", desc)
    desc = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", desc)  # Links

    # Clean up trailing punctuation issues
    desc = desc.rstrip(":")

    # Truncate if too long
    if len(desc) > 200:
        desc = desc[:197] + "..."

    return desc


def extract_highlights(section: str) -> list[str]:
    """Extract key highlights (commands, flags) from the section."""
    highlights = []

    # Look for code/command patterns
    # `cub sandbox` style
    code_matches = re.findall(r"`(cub \w+)`", section)
    highlights.extend(code_matches)

    # `--flag` style
    flag_matches = re.findall(r"`(--\w+(?:\s+\w+)?)`", section)
    highlights.extend(flag_matches)

    # **`command`** style from bullet points
    bullet_matches = re.findall(r"\*\*`([^`]+)`\*\*", section)
    highlights.extend(bullet_matches)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for h in highlights:
        if h not in seen:
            seen.add(h)
            unique.append(h)

    return unique


def generate_html(releases: list[Release]) -> str:
    """Generate HTML for the Recent Updates section."""
    items = []

    for release in releases:
        highlights_html = "\n                    ".join(
            f'<span class="update-highlight">{h}</span>' for h in release.highlights
        )

        item = f"""<div class="update-item">
                    <div class="update-header">
                        <span class="update-version">v{release.version}</span>
                        <span class="update-date">{release.date}</span>
                    </div>
                    <div class="update-title">{release.title}</div>
                    <div class="update-desc">{release.description}</div>
                    <div class="update-highlights">
                        {highlights_html}
                    </div>
                </div>"""
        items.append(item)

    return "\n                ".join(items)


def update_webpage(
    webpage_path: Path, releases: list[Release], dry_run: bool = False
) -> bool:
    """Update the webpage with new release content."""
    content = webpage_path.read_text()

    # Find the markers
    start_marker = "<!-- BEGIN_UPDATES -->"
    end_marker = "<!-- END_UPDATES -->"

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        print("Error: Could not find update markers in webpage")
        return False

    # Generate new content
    new_html = generate_html(releases)

    # Build the new content
    new_content = (
        content[: start_idx + len(start_marker)]
        + "\n                "
        + new_html
        + "\n                "
        + content[end_idx:]
    )

    if dry_run:
        print("=== Dry run - would update with: ===")
        print(new_html)
        return True

    # Write updated content
    webpage_path.write_text(new_content)
    print(f"Updated {webpage_path}")
    return True


def update_version_badge(webpage_path: Path, version: str, dry_run: bool = False) -> bool:
    """Update the version badge in the install box."""
    content = webpage_path.read_text()

    # Find and replace version badge
    old_pattern = r'<span class="version-badge">v[\d.]+</span>'
    new_badge = f'<span class="version-badge">v{version}</span>'

    new_content, count = re.subn(old_pattern, new_badge, content)

    if count == 0:
        print("Warning: Could not find version badge to update")
        return False

    if dry_run:
        print(f"=== Dry run - would update version badge to v{version} ===")
        return True

    webpage_path.write_text(new_content)
    print(f"Updated version badge to v{version}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Update webpage Recent Updates from CHANGELOG.md"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=3,
        help="Number of releases to show (default: 3)",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="Path to changelog file",
    )
    parser.add_argument(
        "--webpage",
        type=Path,
        default=Path("docs/index.html"),
        help="Path to webpage file",
    )
    args = parser.parse_args()

    # Resolve paths relative to project root
    project_root = Path(__file__).parent.parent
    changelog_path = project_root / args.changelog
    webpage_path = project_root / args.webpage

    if not changelog_path.exists():
        print(f"Error: Changelog not found at {changelog_path}")
        return 1

    if not webpage_path.exists():
        print(f"Error: Webpage not found at {webpage_path}")
        return 1

    # Parse changelog
    print(f"Parsing {changelog_path}...")
    releases = parse_changelog(changelog_path, args.count)

    if not releases:
        print("Error: No releases found in changelog")
        return 1

    print(f"Found {len(releases)} releases:")
    for r in releases:
        print(f"  - v{r.version} ({r.date}): {r.title}")

    # Update webpage
    print(f"\nUpdating {webpage_path}...")
    if not update_webpage(webpage_path, releases, args.dry_run):
        return 1

    # Update version badge with latest version
    if releases:
        update_version_badge(webpage_path, releases[0].version, args.dry_run)

    print("\nDone!")
    return 0


if __name__ == "__main__":
    exit(main())
