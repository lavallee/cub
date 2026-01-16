"""
Auto-tagging for captures based on content analysis.

Provides keyword extraction to suggest tags based on capture content.
"""


def suggest_tags(content: str) -> list[str]:
    """
    Suggest tags based on capture content using keyword matching.

    Performs simple case-insensitive keyword matching against a vocabulary
    of common technical terms and project-specific tags.

    Args:
        content: Capture text content to analyze

    Returns:
        List of suggested tag strings

    Example:
        >>> suggest_tags("Fix git merge conflict in API")
        ['git', 'api']

        >>> suggest_tags("UI bug: button doesn't respond to clicks")
        ['ui', 'bug']
    """
    # Define common tag vocabulary with keywords that trigger them
    tag_keywords: dict[str, list[str]] = {
        "git": ["git", "commit", "push", "pull", "merge", "rebase", "branch", "clone"],
        "ui": [
            "ui",
            "button",
            "component",
            "design",
            "layout",
            "css",
            "theme",
            "dark mode",
            "light mode",
        ],
        "api": [
            "api",
            "endpoint",
            "rest",
            "graphql",
            "http",
            "request",
            "response",
            "json",
        ],
        "database": ["database", "db", "sql", "postgres", "mysql", "schema", "migration"],
        "auth": ["auth", "login", "password", "session", "token", "jwt", "oauth"],
        "performance": ["performance", "slow", "optimize", "cache", "memory", "speed"],
        "security": ["security", "vulnerability", "encrypt", "xss", "injection", "csrf"],
        "test": ["test", "unit", "integration", "pytest", "mock", "coverage"],
        "docs": ["documentation", "docs", "readme", "guide", "tutorial"],
        "bug": ["bug", "fix", "broken", "error", "crash", "fail"],
        "feature": ["feature", "new", "add", "implement", "enhance"],
        "refactor": ["refactor", "clean", "improve", "reorganize", "simplify"],
        "docker": ["docker", "container", "image", "compose", "kubernetes"],
        "python": ["python", "py", "pip", "venv", "requirements"],
    }

    # Normalize content to lowercase for matching
    content_lower = content.lower()

    # Find matching tags
    suggested: list[str] = []
    for tag, keywords in tag_keywords.items():
        for keyword in keywords:
            if keyword in content_lower:
                if tag not in suggested:
                    suggested.append(tag)
                break  # Only match each tag once

    return suggested
