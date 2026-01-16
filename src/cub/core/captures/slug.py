"""
Slug generation for capture filenames.

Uses Claude Haiku to generate descriptive slugs from capture content.
Falls back to a simple text-based slug if AI is unavailable.
"""

import re
import subprocess


def generate_slug(content: str, max_length: int = 50) -> str | None:
    """
    Generate a descriptive slug from capture content using Haiku.

    Args:
        content: The capture text content
        max_length: Maximum slug length

    Returns:
        Slug string (e.g., "add-dark-mode-ui") or None if generation fails
    """
    # Try AI-generated slug first
    try:
        slug = _generate_slug_with_haiku(content, max_length)
        if slug:
            return slug
    except Exception:
        pass

    return None


def generate_slug_fallback(text: str, max_length: int = 50) -> str:
    """
    Generate a simple slug from text without AI.

    Used as fallback when AI slug generation fails.

    Args:
        text: Input text to slugify
        max_length: Maximum slug length

    Returns:
        Slugified text suitable for filenames
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

    return slug or "capture"


def _generate_slug_with_haiku(content: str, max_length: int) -> str | None:
    """
    Call Claude Haiku to generate a descriptive slug.

    Args:
        content: The capture text content
        max_length: Maximum slug length

    Returns:
        Slug string or None if generation fails
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

        return slug

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
