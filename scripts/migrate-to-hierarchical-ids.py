#!/usr/bin/env python3
"""
Migration script: Retroactively assign hierarchical IDs to specs, plans, and tasks.

This script implements the ID system from the ledger-consolidation-and-id-system spec:
- Specs: {project_id}-{number}           → cub-054
- Plans: {spec_id}{letter}               → cub-054a
- Epics: {plan_id}{letter}               → cub-054ac
- Tasks: {epic_id}.{number}              → cub-054ac.1
- Standalone: {project_id}-s{number}     → cub-s017

Letter sequence: 0-9, a-z, A-Z (62 options per level)

Usage:
    python scripts/migrate-to-hierarchical-ids.py --dry-run    # Preview changes
    python scripts/migrate-to-hierarchical-ids.py              # Apply changes
    python scripts/migrate-to-hierarchical-ids.py --project-id myproj  # Custom project ID
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Letter sequences for different levels (62 chars each)
# Plans: A-Z, a-z, 0-9 (uppercase first for visual distinction from spec numbers)
PLAN_SEQUENCE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
# Epics/Tasks: 0-9, a-z, A-Z (numbers first, visually distinct from plan letters)
EPIC_SEQUENCE = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def get_plan_char(index: int) -> str:
    """Convert index to plan letter (A-Z, a-z, 0-9)."""
    if index < 0 or index >= len(PLAN_SEQUENCE):
        raise ValueError(f"Index {index} out of range for plan sequence (max {len(PLAN_SEQUENCE) - 1})")
    return PLAN_SEQUENCE[index]


def get_epic_char(index: int) -> str:
    """Convert index to epic letter (0-9, a-z, A-Z)."""
    if index < 0 or index >= len(EPIC_SEQUENCE):
        raise ValueError(f"Index {index} out of range for epic sequence (max {len(EPIC_SEQUENCE) - 1})")
    return EPIC_SEQUENCE[index]


def get_sequence_char(index: int) -> str:
    """Convert index to sequence character (0-9, a-z, A-Z). Legacy/default."""
    return get_epic_char(index)


def get_sequence_index(char: str) -> int:
    """Convert sequence character to index (tries epic sequence first)."""
    try:
        return EPIC_SEQUENCE.index(char)
    except ValueError:
        try:
            return PLAN_SEQUENCE.index(char)
        except ValueError:
            raise ValueError(f"Character '{char}' not in any sequence")


def parse_yaml_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content."""
    import yaml

    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}, content

    frontmatter_end = end_match.end() + 3
    frontmatter_str = content[4:end_match.start() + 3]
    body = content[frontmatter_end:]

    try:
        frontmatter = yaml.safe_load(frontmatter_str) or {}
    except yaml.YAMLError:
        frontmatter = {}

    return frontmatter, body


def write_yaml_frontmatter(frontmatter: dict[str, Any], body: str) -> str:
    """Write YAML frontmatter back to markdown content."""
    import yaml

    # Custom representer for cleaner output
    def str_representer(dumper, data):
        if '\n' in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    yaml.add_representer(str, str_representer)

    frontmatter_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return f"---\n{frontmatter_str}---\n{body}"


def get_spec_created_date(spec_path: Path) -> datetime:
    """Get creation date from spec frontmatter or file stat."""
    content = spec_path.read_text()
    frontmatter, _ = parse_yaml_frontmatter(content)

    # Try frontmatter created date
    if "created" in frontmatter:
        created = frontmatter["created"]
        if isinstance(created, datetime):
            return created
        if isinstance(created, str):
            try:
                return datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                pass

    # Fall back to file modification time
    return datetime.fromtimestamp(spec_path.stat().st_mtime)


def discover_specs(specs_dir: Path) -> list[tuple[Path, datetime]]:
    """Discover all spec files and their creation dates."""
    specs = []

    # Spec directories in workflow order (for tie-breaking)
    workflow_order = ["completed", "implementing", "staged", "planned", "researching", "investigations"]

    # Files to skip (templates, meta-docs, etc.)
    skip_files = {
        "README.md",
        "TOOLS-PRIORITY.md",
        "TOOLS-WISHLIST.md",
        "SPEC-TEMPLATE.md",
        "session-spec.md",  # Meta-spec about sessions, not a feature spec
    }

    for spec_file in specs_dir.rglob("*.md"):
        # Skip non-spec files
        if spec_file.name.startswith("_"):
            continue
        if spec_file.name in skip_files:
            continue
        # Skip files in research/notes subdirectories
        if "research" in spec_file.parts and spec_file.parent.name == "research":
            continue

        created = get_spec_created_date(spec_file)
        specs.append((spec_file, created))

    # Sort by creation date, then by workflow stage (completed first), then by name
    def sort_key(item):
        path, created = item
        # Get workflow stage from parent directory
        parent = path.parent.name
        try:
            stage_order = workflow_order.index(parent)
        except ValueError:
            stage_order = len(workflow_order)  # Unknown stages last

        return (created, stage_order, path.stem)

    specs.sort(key=sort_key)
    return specs


def discover_plans(plans_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Discover all plans and their metadata."""
    plans = []

    for plan_json in plans_dir.rglob("plan.json"):
        try:
            metadata = json.loads(plan_json.read_text())
            plans.append((plan_json.parent, metadata))
        except (json.JSONDecodeError, FileNotFoundError):
            continue

    # Sort by created date
    def sort_key(item):
        _, metadata = item
        created = metadata.get("created", "9999-99-99")
        return created

    plans.sort(key=sort_key)
    return plans


def load_tasks(tasks_file: Path) -> list[dict[str, Any]]:
    """Load tasks from JSONL file."""
    tasks = []
    if not tasks_file.exists():
        return tasks

    for line in tasks_file.read_text().splitlines():
        if line.strip():
            try:
                tasks.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return tasks


def save_tasks(tasks: list[dict[str, Any]], tasks_file: Path) -> None:
    """Save tasks to JSONL file."""
    lines = [json.dumps(task, ensure_ascii=False) for task in tasks]
    tasks_file.write_text("\n".join(lines) + "\n")


def build_spec_slug_to_id(specs: list[tuple[Path, datetime]], project_id: str) -> dict[str, str]:
    """Build mapping from spec slug to new spec ID.

    Format: {project_id}-{number:03d}
    Example: cub-054
    """
    mapping = {}

    for i, (spec_path, _) in enumerate(specs, start=1):
        slug = spec_path.stem
        spec_id = f"{project_id}-{i:03d}"
        mapping[slug] = spec_id

    return mapping


def format_plan_id(spec_id: str, plan_index: int) -> str:
    """Format plan ID as spec_id + uppercase letter.

    Format: {spec_id}{LETTER}
    Example: cub-054A (first plan for spec 054)

    Letter sequence: A-Z, a-z, 0-9 (uppercase first for visual distinction)
    """
    letter = get_plan_char(plan_index)
    return f"{spec_id}{letter}"


def format_epic_id(plan_id: str, epic_index: int) -> str:
    """Format epic ID as plan_id-number/letter.

    Format: {plan_id}-{char}
    Example: cub-054A-0 (first epic in plan 054A)
    Example: cub-054A-c (13th epic in plan 054A)

    Sequence: 0-9, a-z, A-Z (numbers first, visually distinct from plan letters)
    """
    letter = get_epic_char(epic_index)
    return f"{plan_id}-{letter}"


def format_task_id(epic_id: str, task_number: int) -> str:
    """Format task ID as epic_id.number.

    Format: {epic_id}.{number}
    Example: cub-054a-c.1
    """
    return f"{epic_id}.{task_number}"


def format_standalone_id(project_id: str, standalone_number: int) -> str:
    """Format standalone task ID.

    Format: {project_id}-s{number:03d}
    Example: cub-s017
    """
    return f"{project_id}-s{standalone_number:03d}"


def build_plan_slug_to_id(
    plans: list[tuple[Path, dict[str, Any]]],
    spec_slug_to_id: dict[str, str],
    project_id: str
) -> dict[str, str]:
    """Build mapping from plan slug to new plan ID."""
    mapping = {}

    # Group plans by spec
    spec_to_plans: dict[str, list[str]] = {}
    unlinked_plans: list[str] = []

    for plan_dir, metadata in plans:
        slug = plan_dir.name
        spec_file = metadata.get("spec_file", "")

        # Try to find matching spec
        spec_slug = None
        if spec_file:
            # spec_file might be "symbiotic-workflow.md" or just "symbiotic-workflow"
            spec_slug = spec_file.replace(".md", "")

        # Also try matching by plan slug
        if not spec_slug or spec_slug not in spec_slug_to_id:
            # Check if plan slug matches a spec slug
            if slug in spec_slug_to_id:
                spec_slug = slug

        if spec_slug and spec_slug in spec_slug_to_id:
            if spec_slug not in spec_to_plans:
                spec_to_plans[spec_slug] = []
            spec_to_plans[spec_slug].append(slug)
        else:
            unlinked_plans.append(slug)

    # Assign plan IDs (spec_id + letter)
    for spec_slug, plan_slugs in spec_to_plans.items():
        spec_id = spec_slug_to_id[spec_slug]
        for i, plan_slug in enumerate(plan_slugs):
            plan_id = format_plan_id(spec_id, i)
            mapping[plan_slug] = plan_id

    # Handle unlinked plans - create synthetic spec IDs for them
    # (These will need manual linking later)
    if unlinked_plans:
        print(f"WARNING: {len(unlinked_plans)} plans not linked to specs: {unlinked_plans}")
        print("         These plans will be assigned temporary IDs.")
        # For now, use the plan slug as-is (migration can be refined later)
        for plan_slug in unlinked_plans:
            mapping[plan_slug] = f"{project_id}-unlinked-{plan_slug}"

    return mapping


def build_old_to_new_task_id(
    tasks: list[dict[str, Any]],
    plan_slug_to_id: dict[str, str],
    project_id: str
) -> dict[str, str]:
    """Build mapping from old task IDs to new task IDs."""
    mapping = {}

    # First, identify epics and their plans
    epic_to_plan: dict[str, str] = {}
    epic_tasks: dict[str, list[dict[str, Any]]] = {}
    standalone_tasks: list[dict[str, Any]] = []

    for task in tasks:
        task_id = task.get("id", "")
        issue_type = task.get("issue_type", "task")
        parent = task.get("parent")

        if issue_type == "epic":
            # Try to find the plan this epic belongs to
            # Convention: epics might have labels like "plan:symbiotic-workflow"
            labels = task.get("labels", [])
            plan_slug = None

            for label in labels:
                if label.startswith("plan:"):
                    plan_slug = label.replace("plan:", "")
                    break

            # Also check if epic ID prefix matches a plan slug
            if not plan_slug:
                for slug in plan_slug_to_id:
                    if task_id.startswith(f"{project_id}-") and slug in task_id:
                        plan_slug = slug
                        break

            if plan_slug and plan_slug in plan_slug_to_id:
                epic_to_plan[task_id] = plan_slug_to_id[plan_slug]

            epic_tasks[task_id] = []

        elif parent:
            # Task with parent epic
            if parent not in epic_tasks:
                epic_tasks[parent] = []
            epic_tasks[parent].append(task)
        else:
            # Standalone task (no epic)
            standalone_tasks.append(task)

    # Assign new epic IDs within each plan
    plan_epic_counts: dict[str, int] = {}
    for old_epic_id, plan_id in epic_to_plan.items():
        if plan_id not in plan_epic_counts:
            plan_epic_counts[plan_id] = 0

        new_epic_id = format_epic_id(plan_id, plan_epic_counts[plan_id])
        mapping[old_epic_id] = new_epic_id
        plan_epic_counts[plan_id] += 1

    # Handle epics not linked to plans (assign from project level)
    unlinked_epic_count = 0
    for old_epic_id in epic_tasks:
        if old_epic_id not in mapping:
            # Unlinked epic - use a synthetic ID that flags manual review needed
            mapping[old_epic_id] = f"{project_id}-orphan-{unlinked_epic_count:02d}"
            unlinked_epic_count += 1

    if unlinked_epic_count > 0:
        print(f"WARNING: {unlinked_epic_count} epics not linked to plans (flagged as orphan)")
        print("         These need manual linking to specs/plans")

    # Assign task IDs within each epic
    for old_epic_id, tasks_in_epic in epic_tasks.items():
        new_epic_id = mapping.get(old_epic_id, old_epic_id)

        # Sort tasks by their original numbering if possible
        def task_sort_key(t):
            tid = t.get("id", "")
            # Extract number from ID like "cub-k7m.3"
            match = re.search(r"\.(\d+)$", tid)
            if match:
                return int(match.group(1))
            return 999

        tasks_in_epic.sort(key=task_sort_key)

        for i, task in enumerate(tasks_in_epic, start=1):
            old_task_id = task.get("id", "")
            new_task_id = format_task_id(new_epic_id, i)
            mapping[old_task_id] = new_task_id

    # Assign standalone task IDs
    for i, task in enumerate(standalone_tasks, start=1):
        old_task_id = task.get("id", "")
        new_task_id = format_standalone_id(project_id, i)
        mapping[old_task_id] = new_task_id

    return mapping


def update_spec_files(
    specs: list[tuple[Path, datetime]],
    spec_slug_to_id: dict[str, str],
    dry_run: bool
) -> None:
    """Update spec files with new spec_id in frontmatter."""
    for spec_path, _ in specs:
        slug = spec_path.stem
        spec_id = spec_slug_to_id.get(slug)

        if not spec_id:
            continue

        content = spec_path.read_text()
        frontmatter, body = parse_yaml_frontmatter(content)

        # Add spec_id to frontmatter
        if frontmatter.get("spec_id") == spec_id:
            continue  # Already has correct ID

        frontmatter["spec_id"] = spec_id

        new_content = write_yaml_frontmatter(frontmatter, body)

        if dry_run:
            print(f"  [DRY RUN] Would update {spec_path}: spec_id={spec_id}")
        else:
            spec_path.write_text(new_content)
            print(f"  Updated {spec_path}: spec_id={spec_id}")


def update_plan_files(
    plans: list[tuple[Path, dict[str, Any]]],
    plan_slug_to_id: dict[str, str],
    old_to_new_task_id: dict[str, str],
    dry_run: bool
) -> None:
    """Update plan.json and itemized-plan.md with new IDs."""
    for plan_dir, metadata in plans:
        slug = plan_dir.name
        plan_id = plan_slug_to_id.get(slug)

        if not plan_id:
            continue

        # Update plan.json
        plan_json = plan_dir / "plan.json"
        if plan_json.exists():
            metadata["plan_id"] = plan_id

            if dry_run:
                print(f"  [DRY RUN] Would update {plan_json}: plan_id={plan_id}")
            else:
                plan_json.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
                print(f"  Updated {plan_json}: plan_id={plan_id}")

        # Update itemized-plan.md (replace old task IDs with new ones)
        itemized = plan_dir / "itemized-plan.md"
        if itemized.exists():
            content = itemized.read_text()
            updated_content = content

            for old_id, new_id in old_to_new_task_id.items():
                # Replace task ID references
                updated_content = re.sub(
                    rf"\b{re.escape(old_id)}\b",
                    new_id,
                    updated_content
                )

            if updated_content != content:
                if dry_run:
                    print(f"  [DRY RUN] Would update task IDs in {itemized}")
                else:
                    itemized.write_text(updated_content)
                    print(f"  Updated task IDs in {itemized}")


def update_tasks_file(
    tasks: list[dict[str, Any]],
    old_to_new_task_id: dict[str, str],
    tasks_file: Path,
    dry_run: bool
) -> list[dict[str, Any]]:
    """Update tasks with new IDs."""
    updated_tasks = []

    for task in tasks:
        old_id = task.get("id", "")
        new_id = old_to_new_task_id.get(old_id, old_id)

        updated_task = task.copy()

        if new_id != old_id:
            updated_task["id"] = new_id
            updated_task["_old_id"] = old_id  # Preserve for reference

        # Update parent reference
        if "parent" in updated_task and updated_task["parent"]:
            old_parent = updated_task["parent"]
            new_parent = old_to_new_task_id.get(old_parent, old_parent)
            if new_parent != old_parent:
                updated_task["parent"] = new_parent

        # Update dependsOn references
        if "dependsOn" in updated_task:
            updated_task["dependsOn"] = [
                old_to_new_task_id.get(dep, dep)
                for dep in updated_task["dependsOn"]
            ]

        # Update blocks references
        if "blocks" in updated_task:
            updated_task["blocks"] = [
                old_to_new_task_id.get(blk, blk)
                for blk in updated_task["blocks"]
            ]

        updated_tasks.append(updated_task)

    if dry_run:
        changes = sum(1 for t in updated_tasks if t.get("_old_id"))
        print(f"  [DRY RUN] Would update {changes} task IDs in {tasks_file}")
    else:
        save_tasks(updated_tasks, tasks_file)
        changes = sum(1 for t in updated_tasks if t.get("_old_id"))
        print(f"  Updated {changes} task IDs in {tasks_file}")

    return updated_tasks


def initialize_counters(
    specs: list[tuple[Path, datetime]],
    standalone_count: int,
    counters_file: Path,
    dry_run: bool
) -> None:
    """Initialize counters.json with current max values."""
    counters = {
        "spec_number": len(specs),
        "standalone_task_number": standalone_count,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    if dry_run:
        print(f"  [DRY RUN] Would create {counters_file}: {json.dumps(counters)}")
    else:
        counters_file.parent.mkdir(parents=True, exist_ok=True)
        counters_file.write_text(json.dumps(counters, indent=2) + "\n")
        print(f"  Created {counters_file}: {json.dumps(counters)}")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate to hierarchical ID system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Project ID (default: from .cub/config.json)"
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Project directory (default: current directory)"
    )

    args = parser.parse_args()

    project_dir = args.project_dir.resolve()
    cub_dir = project_dir / ".cub"
    specs_dir = project_dir / "specs"
    plans_dir = project_dir / "plans"
    tasks_file = cub_dir / "tasks.jsonl"
    counters_file = cub_dir / "counters.json"
    config_file = cub_dir / "config.json"

    # Get project ID
    project_id = args.project_id
    if not project_id and config_file.exists():
        config = json.loads(config_file.read_text())
        project_id = config.get("project_id", "cub")
    if not project_id:
        project_id = "cub"

    print(f"Migrating to hierarchical IDs (project_id={project_id})")
    print(f"  Project dir: {project_dir}")
    print(f"  Dry run: {args.dry_run}")
    print()

    # Discover specs
    print("Step 1: Discovering specs...")
    if specs_dir.exists():
        specs = discover_specs(specs_dir)
        print(f"  Found {len(specs)} specs")
    else:
        specs = []
        print("  No specs directory found")

    # Build spec slug to ID mapping
    spec_slug_to_id = build_spec_slug_to_id(specs, project_id)

    # Discover plans
    print("\nStep 2: Discovering plans...")
    if plans_dir.exists():
        plans = discover_plans(plans_dir)
        print(f"  Found {len(plans)} plans")
    else:
        plans = []
        print("  No plans directory found")

    # Build plan slug to ID mapping
    plan_slug_to_id = build_plan_slug_to_id(plans, spec_slug_to_id, project_id)

    # Load tasks
    print("\nStep 3: Loading tasks...")
    tasks = load_tasks(tasks_file)
    print(f"  Found {len(tasks)} tasks")

    # Build task ID mapping
    old_to_new_task_id = build_old_to_new_task_id(tasks, plan_slug_to_id, project_id)

    # Count standalone tasks
    standalone_count = sum(1 for new_id in old_to_new_task_id.values() if "-s" in new_id)

    # Print mapping summary
    print("\nID Mappings:")
    print(f"  Specs: {len(spec_slug_to_id)}")
    print(f"  Plans: {len(plan_slug_to_id)}")
    print(f"  Tasks: {len(old_to_new_task_id)}")
    print(f"  Standalone tasks: {standalone_count}")

    # Show some example mappings
    if spec_slug_to_id:
        print("\n  Example spec mappings:")
        for i, (slug, spec_id) in enumerate(list(spec_slug_to_id.items())[:5]):
            print(f"    {slug} -> {spec_id}")
        if len(spec_slug_to_id) > 5:
            print(f"    ... and {len(spec_slug_to_id) - 5} more")

    if old_to_new_task_id:
        print("\n  Example task mappings:")
        for i, (old_id, new_id) in enumerate(list(old_to_new_task_id.items())[:5]):
            print(f"    {old_id} -> {new_id}")
        if len(old_to_new_task_id) > 5:
            print(f"    ... and {len(old_to_new_task_id) - 5} more")

    # Apply updates
    print("\nStep 4: Updating spec files...")
    update_spec_files(specs, spec_slug_to_id, args.dry_run)

    print("\nStep 5: Updating plan files...")
    update_plan_files(plans, plan_slug_to_id, old_to_new_task_id, args.dry_run)

    print("\nStep 6: Updating tasks file...")
    update_tasks_file(tasks, old_to_new_task_id, tasks_file, args.dry_run)

    print("\nStep 7: Initializing counters...")
    initialize_counters(specs, standalone_count, counters_file, args.dry_run)

    print("\n" + "=" * 60)
    if args.dry_run:
        print("DRY RUN COMPLETE - No files were modified")
        print("Run without --dry-run to apply changes")
    else:
        print("MIGRATION COMPLETE")
        print("\nNext steps:")
        print("  1. Review the changes: git diff")
        print("  2. Commit the changes: git add -A && git commit -m 'chore: migrate to hierarchical ID system'")
        print("  3. Push counters to sync branch: cub sync --push")


if __name__ == "__main__":
    main()
