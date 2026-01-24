"""
Punchlist processor orchestration.

Coordinates the full punchlist workflow:
1. Parse markdown into items
2. Hydrate items with Claude
3. Create epic and child tasks
"""

from collections.abc import Callable
from pathlib import Path

from cub.core.punchlist.hydrator import hydrate_and_write_back, hydrate_item
from cub.core.punchlist.models import HydratedItem, PunchlistResult
from cub.core.punchlist.parser import parse_punchlist
from cub.core.tasks.backend import get_backend
from cub.core.tasks.models import Task


def process_punchlist(
    path: Path,
    epic_title: str | None = None,
    labels: list[str] | None = None,
    dry_run: bool = False,
    write_back: bool = True,
    on_item_hydrated: Callable[[int, int, HydratedItem], None] | None = None,
) -> PunchlistResult:
    """
    Process a punchlist file into an epic with child tasks.

    This is the main entry point for punchlist processing. It:
    1. Parses the markdown file to extract items
    2. Hydrates each item with Claude to get titles/descriptions
    3. Creates an epic for the punchlist
    4. Creates child tasks under the epic

    Args:
        path: Path to the punchlist markdown file.
        epic_title: Custom title for the epic. If not provided,
            derived from the filename (e.g., "v0.27.0 Bug Fixes").
        labels: Additional labels to add to the epic.
        dry_run: If True, don't create tasks, just return what would be created.
        write_back: If True, rewrite the punchlist file with structured format.
        on_item_hydrated: Optional callback called after each item is hydrated.
            Receives (current_index, total_count, hydrated_item).

    Returns:
        PunchlistResult with the created epic and tasks.

    Raises:
        FileNotFoundError: If the punchlist file doesn't exist.
        ValueError: If the file contains no valid items.
    """
    # 1. Parse items
    items = parse_punchlist(path)
    if not items:
        raise ValueError(f"No items found in punchlist: {path}")

    # 2. Hydrate items with progress callback
    total = len(items)
    hydrated: list[HydratedItem] = []

    if write_back:
        # Hydrate and write back in one pass
        hydrated = hydrate_and_write_back(path, items)
        if on_item_hydrated:
            for i, h in enumerate(hydrated):
                on_item_hydrated(i, total, h)
    else:
        # Hydrate without writing back
        for i, item in enumerate(items):
            h = hydrate_item(item)
            hydrated.append(h)
            if on_item_hydrated:
                on_item_hydrated(i, total, h)

    # 3. Derive epic title from filename if not provided
    if not epic_title:
        epic_title = _derive_epic_title(path)

    # For dry run, create mock tasks
    if dry_run:
        mock_epic = Task(
            id="<dry-run>",
            title=epic_title,
            description=f"Epic for punchlist: {path.name}",
        )
        mock_tasks = [
            Task(
                id=f"<dry-run-{i}>",
                title=h.title,
                description=h.description,
            )
            for i, h in enumerate(hydrated)
        ]
        return PunchlistResult(
            epic=mock_epic,
            tasks=mock_tasks,
            source_file=path,
        )

    # 4. Get task backend and create epic
    backend = get_backend()

    epic_labels = ["punchlist", f"punchlist:{path.stem}"]
    if labels:
        epic_labels.extend(labels)

    epic = backend.create_task(
        title=epic_title,
        description=f"Punchlist tasks from: {path.name}\n\nSource: {path}",
        task_type="epic",
        priority=2,
        labels=epic_labels,
    )

    # 5. Create child tasks under epic
    # Note: We use labels instead of parent to associate tasks with the epic.
    # Using --parent in beads creates a hierarchical ID (epic.1, epic.2) AND adds
    # a dependency from child to parent, which blocks tasks until the epic closes.
    # We use "epic:{id}" label format for consistency with plan-based task creation.
    tasks: list[Task] = []
    for h in hydrated:
        task = backend.create_task(
            title=h.title,
            description=h.description,
            task_type="task",
            priority=2,
            labels=["punchlist", f"epic:{epic.id}"],
        )
        tasks.append(task)

    return PunchlistResult(
        epic=epic,
        tasks=tasks,
        source_file=path,
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

    # Default: convert hypens to spaces, title case
    words = stem.replace("-", " ").replace("_", " ").split()
    return " ".join(word.capitalize() for word in words)
