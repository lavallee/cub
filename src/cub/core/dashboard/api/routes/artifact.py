"""
Artifact API routes for the dashboard.

Provides endpoints for fetching raw file content:
- GET /api/artifact - Fetch content of specs, plans, and other project files

Supports multiple source types:
- File paths: Direct file access with security validation
- Beads tasks: Fetches task details via `bd show <id>`

Security is critical: validates paths to prevent directory traversal attacks.
"""

import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


def fetch_beads_task(task_id: str) -> str:
    """
    Fetch task content from beads backend using `bd show`.

    Args:
        task_id: The beads task ID (e.g., "cub-abc")

    Returns:
        Human-readable task content from `bd show`

    Raises:
        HTTPException: 404 if task not found, 500 if bd command fails
    """
    # Check if bd is available
    if not shutil.which("bd"):
        raise HTTPException(
            status_code=500,
            detail="beads CLI (bd) is not installed",
        )

    try:
        result = subprocess.run(
            ["bd", "show", task_id],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or "Task not found"
            if "not found" in error_msg.lower() or result.returncode == 1:
                raise HTTPException(
                    status_code=404,
                    detail=f"Task not found: {task_id}",
                )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch task: {error_msg}",
            )

        return result.stdout

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=500,
            detail="Timeout fetching task from beads",
        )
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run bd command: {e}",
        )


def get_project_root() -> Path:
    """
    Get the project root directory.

    The project root is the current working directory, which should be
    the root of the project where specs/, .cub/, etc. are located.

    Returns:
        Path to project root
    """
    return Path.cwd()


def validate_artifact_path(path: str, project_root: Path) -> Path:
    """
    Validate that a path is safe to serve as an artifact.

    Security checks:
    1. Path must not be empty
    2. Resolved path must be within project root (prevents ../../../etc/passwd)
    3. Path must not contain null bytes
    4. File must exist and be a regular file

    Args:
        path: The requested file path (relative or absolute)
        project_root: The project root directory

    Returns:
        Resolved absolute Path to the file

    Raises:
        HTTPException: 400 for invalid paths, 404 for missing files
    """
    # Check for empty path
    if not path or not path.strip():
        raise HTTPException(
            status_code=400,
            detail="Path parameter is required",
        )

    # Check for null bytes (common attack vector)
    if "\x00" in path:
        raise HTTPException(
            status_code=400,
            detail="Invalid path: contains null bytes",
        )

    # Convert to Path and resolve to absolute path
    # This handles .., ., symlinks, etc.
    try:
        requested_path = Path(path)

        # If relative path, make it relative to project root
        if not requested_path.is_absolute():
            requested_path = project_root / requested_path

        # Resolve to canonical absolute path (follows symlinks, resolves ..)
        resolved_path = requested_path.resolve()

    except (OSError, ValueError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid path format: {e}",
        ) from e

    # Security check: ensure resolved path is within project root
    # This is the critical check that prevents directory traversal
    project_root_resolved = project_root.resolve()

    try:
        resolved_path.relative_to(project_root_resolved)
    except ValueError:
        # Path is outside project root - this is a security violation
        raise HTTPException(
            status_code=400,
            detail="Path must be within project directory",
        )

    # Check that file exists
    try:
        exists = resolved_path.exists()
    except OSError as e:
        # Handle OS-level errors (e.g., path too long)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid path: {e}",
        ) from e

    if not exists:
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {path}",
        )

    # Check that it's a regular file (not directory, device, etc.)
    if not resolved_path.is_file():
        raise HTTPException(
            status_code=400,
            detail="Path must be a regular file",
        )

    return resolved_path


@router.get("/artifact")
async def get_artifact(
    path: str = Query(..., description="Path to the artifact file or backend:id format"),
) -> dict[str, str | int]:
    """
    Get raw file content for an artifact.

    Supports multiple source types:
    - File paths: specs/my-feature.md (relative or absolute)
    - Beads tasks: beads:cub-abc (fetches via bd show)

    Args:
        path: Path to the file or backend:id format

    Returns:
        Dict with path and content

    Raises:
        HTTPException: 400 for invalid/unsafe paths, 404 for missing files

    Example requests:
        GET /api/artifact?path=specs/my-feature.md
        GET /api/artifact?path=beads:cub-abc

    Example response:
        {
          "path": "specs/my-feature.md",
          "content": "# My Feature\\n\\nThis spec describes...",
          "size": 1234
        }

    Security notes:
        - Paths outside project directory are rejected with 400
        - Directory traversal attempts (../) are blocked
        - Null bytes and other injection attempts are blocked
    """
    # Handle beads backend format: beads:<task_id>
    if path.startswith("beads:"):
        task_id = path[6:]  # Remove "beads:" prefix
        if not task_id:
            raise HTTPException(
                status_code=400,
                detail="Task ID is required after 'beads:'",
            )
        content = fetch_beads_task(task_id)
        return {
            "path": path,
            "content": content,
            "size": len(content),
        }

    # Handle file-based artifacts
    project_root = get_project_root()

    # Validate path (raises HTTPException on failure)
    resolved_path = validate_artifact_path(path, project_root)

    try:
        content = resolved_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # File is binary - return error (we only serve text files)
        raise HTTPException(
            status_code=400,
            detail="Cannot read binary files",
        )
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read file: {e}",
        ) from e

    # Return relative path for cleaner response
    try:
        relative_path = resolved_path.relative_to(project_root.resolve())
        display_path = str(relative_path)
    except ValueError:
        display_path = str(resolved_path)

    return {
        "path": display_path,
        "content": content,
        "size": len(content),
    }
