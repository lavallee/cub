"""
Punchlist processor orchestration.

Coordinates the full punchlist workflow:
1. Parse markdown into items
2. Hydrate items with Claude
3. Generate itemized-plan.md for staging
"""

from pathlib import Path

from cub.core.captures.project_id import get_project_id
from cub.core.hydrate.engine import (
    DebugCallback,
    OnCompleteCallback,
    OnStartCallback,
    StreamCallback,
)
from cub.core.hydrate.formatter import generate_itemized_plan
from cub.core.punchlist.hydrator import hydrate_items
from cub.core.punchlist.models import PunchlistResult
from cub.core.punchlist.parser import parse_punchlist


def process_punchlist(
    path: Path,
    epic_title: str | None = None,
    labels: list[str] | None = None,
    dry_run: bool = False,
    output: Path | None = None,
    stream: bool = False,
    debug: bool = False,
    stream_callback: StreamCallback | None = None,
    debug_callback: DebugCallback | None = None,
    on_start: OnStartCallback | None = None,
    on_complete: OnCompleteCallback | None = None,
) -> PunchlistResult:
    """
    Process a punchlist file into an itemized-plan.md.

    This is the main entry point for punchlist processing. It:
    1. Parses the markdown file to extract items
    2. Hydrates each item with Claude to get structured output
    3. Generates itemized-plan.md compatible with `cub stage`
    4. Writes the plan file (unless dry_run)

    Args:
        path: Path to the punchlist markdown file.
        epic_title: Custom title for the epic. If not provided,
            derived from the filename.
        labels: Additional labels to add to the epic.
        dry_run: If True, don't write files, just return what would be generated.
        output: Custom output path. Defaults to {source_dir}/{stem}-plan.md.
        stream: If True, stream Claude's output line-by-line.
        debug: If True, emit debug information.
        stream_callback: Called with each line when streaming.
        debug_callback: Called with debug messages.
        on_start: Called before each item with (index, total, source_text).
        on_complete: Called after each item with (index, total, result).

    Returns:
        PunchlistResult with hydration results and output path.

    Raises:
        FileNotFoundError: If the punchlist file doesn't exist.
        ValueError: If the file contains no valid items.
    """
    # 1. Parse items
    items = parse_punchlist(path)
    if not items:
        raise ValueError(f"No items found in punchlist: {path}")

    # 2. Derive epic title from filename if not provided
    if not epic_title:
        epic_title = _derive_epic_title(path)

    # 3. Hydrate items with callbacks
    hydrated = hydrate_items(
        items,
        stream=stream,
        debug=debug,
        stream_callback=stream_callback,
        debug_callback=debug_callback,
        on_start=on_start,
        on_complete=on_complete,
    )

    # 4. Get project ID for plan ID generation
    project_id = get_project_id()

    # 5. Generate itemized plan markdown
    markdown = generate_itemized_plan(
        results=hydrated,
        epic_title=epic_title,
        source_path=path,
        labels=labels or [],
        project_id=project_id,
    )

    # 6. Determine output path
    output_path = output or path.parent / f"{path.stem}-plan.md"

    # 7. Write plan file (unless dry run)
    if not dry_run:
        output_path.write_text(markdown, encoding="utf-8")

    return PunchlistResult(
        epic_title=epic_title,
        items=hydrated,
        source_file=path,
        output_file=output_path,
    )


def _derive_epic_title(path: Path) -> str:
    """
    Derive an epic title from the punchlist filename.

    Converts filename patterns like:
    - v0.27.0-bugs.md -> "v0.27.0 Bug Fixes"
    - feature-requests.md -> "Feature Requests"
    - my-punchlist.md -> "My Punchlist"

    Args:
        path: Path to the punchlist file.

    Returns:
        Human-readable epic title.
    """
    stem = path.stem  # filename without extension

    # Handle common patterns
    if "-bugs" in stem.lower():
        # v0.27.0-bugs -> v0.27.0 Bug Fixes
        version = stem.lower().replace("-bugs", "").strip("-")
        if version:
            return f"{version} Bug Fixes"
        return "Bug Fixes"

    if "-features" in stem.lower() or "-feature-requests" in stem.lower():
        version = stem.lower().replace("-features", "").replace("-feature-requests", "").strip("-")
        if version:
            return f"{version} Feature Requests"
        return "Feature Requests"

    # Default: convert hyphens to spaces, title case
    words = stem.replace("-", " ").replace("_", " ").split()
    return " ".join(word.capitalize() for word in words)
