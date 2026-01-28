"""
Constitution management for cub projects.

Handles initialization and reading of the project constitution,
which provides ethical guidelines for AI-assisted development.
"""

import shutil
from pathlib import Path


def ensure_constitution(project_dir: Path, force: bool = False) -> Path:
    """
    Ensure constitution.md exists in the project's .cub/ directory.

    Copies the default constitution template from templates/constitution.md
    to .cub/constitution.md if it doesn't exist, or if force=True.

    Args:
        project_dir: Root directory of the project
        force: If True, overwrite existing constitution with template

    Returns:
        Path to the constitution file (.cub/constitution.md)

    Raises:
        FileNotFoundError: If the template file cannot be found
    """
    cub_dir = project_dir / ".cub"
    cub_dir.mkdir(exist_ok=True)

    constitution_path = cub_dir / "constitution.md"

    # Find template - it should be in the package's templates directory
    # templates/ is a sibling of src/cub/core/
    template_path = Path(__file__).parent.parent.parent.parent / "templates" / "constitution.md"

    if not template_path.exists():
        raise FileNotFoundError(f"Constitution template not found at {template_path}")

    # Copy if doesn't exist or if force=True
    if force or not constitution_path.exists():
        shutil.copy2(template_path, constitution_path)

    return constitution_path


def read_constitution(project_dir: Path) -> str | None:
    """
    Read the project's constitution if it exists.

    Args:
        project_dir: Root directory of the project

    Returns:
        Constitution content as a string, or None if not present
    """
    constitution_path = project_dir / ".cub" / "constitution.md"

    if not constitution_path.exists():
        return None

    return constitution_path.read_text()
