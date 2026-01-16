"""
Slug generation for capture filenames.

Uses Claude Haiku to generate descriptive slugs from capture content.
Falls back to a simple text-based slug if AI is unavailable.
"""

import re
import subprocess
from dataclasses import dataclass


@dataclass
class SlugResult:
    """Result of slug generation containing both slug and title."""

    slug: str
    title: str


def generate_slug(content: str, max_length: int = 50) -> SlugResult | None:
    """
    Generate a descriptive slug and title from capture content using Haiku.

    Args:
        content: The capture text content
        max_length: Maximum slug length

    Returns:
        SlugResult with slug and title, or None if generation fails
    """
    # Try AI-generated slug first
    try:
        result = _generate_slug_with_haiku(content, max_length)
        if result:
            return result
    except Exception:
        pass

    return None


def generate_slug_fallback(text: str, max_length: int = 50) -> SlugResult:
    """
    Generate a simple slug from text without AI.

    Used as fallback when AI slug generation fails.

    Args:
        text: Input text to slugify
        max_length: Maximum slug length

    Returns:
        SlugResult with slugified text and title
    """
    # Take first line
    first_line = text.split("\n", 1)[0].strip()

    # Convert to lowercase and replace non-alphanumeric with hyphens
    slug = first_line.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")

    # Truncate to max length at word boundary
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]

    slug = slug or "capture"
    title = _slug_to_title(slug)

    return SlugResult(slug=slug, title=title)


def _slug_to_title(slug: str) -> str:
    """
    Convert a slug to a human-readable title.

    Args:
        slug: Hyphenated slug (e.g., "add-dark-mode-ui")

    Returns:
        Title case string (e.g., "Add Dark Mode UI")
    """
    # Replace hyphens with spaces and title case
    words = slug.replace("-", " ").split()
    # Title case each word, but keep common acronyms uppercase
    titled_words = []
    for word in words:
        if word.upper() in ("UI", "API", "CLI", "URL", "ID", "DB", "CSS", "HTML", "JS"):
            titled_words.append(word.upper())
        else:
            titled_words.append(word.capitalize())
    return " ".join(titled_words)


def _generate_slug_with_haiku(content: str, max_length: int) -> SlugResult | None:
    """
    Call Claude Haiku to generate a descriptive slug.

    Args:
        content: The capture text content
        max_length: Maximum slug length

    Returns:
        SlugResult or None if generation fails
    """
    # Truncate content for the prompt (first 500 chars is enough context)
    truncated = content[:500]

    prompt = f"""Generate a short, descriptive filename slug for this note.
Rules:
- Use lowercase letters, numbers, and hyphens only
- Maximum {max_length} characters
- No file extension
- Be descriptive but concise (3-6 words typical)
- Focus on the main topic/action

Note content:
{truncated}

Respond with ONLY the slug, nothing else. Example: add-dark-mode-toggle"""

    try:
        result = subprocess.run(
            ["claude", "--model", "haiku", "--print", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode != 0:
            return None

        # Clean and validate the response
        slug = result.stdout.strip().lower()

        # Remove any quotes or extra formatting
        slug = slug.strip("\"'`")

        # Validate: only alphanumeric and hyphens
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$", slug):
            # Try to clean it up
            slug = re.sub(r"[^a-z0-9]+", "-", slug)
            slug = slug.strip("-")

        if not slug or len(slug) < 3:
            return None

        # Truncate if too long
        if len(slug) > max_length:
            slug = slug[:max_length].rsplit("-", 1)[0]

        # Generate title from slug
        title = _slug_to_title(slug)

        return SlugResult(slug=slug, title=title)

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
