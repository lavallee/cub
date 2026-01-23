"""
Artifact API routes for the dashboard.

Provides endpoints for fetching raw file content:
- GET /api/artifact - Fetch content of specs, plans, and other project files

Security is critical: validates paths to prevent directory traversal attacks.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


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
    path: str = Query(..., description="Path to the artifact file (relative or absolute)"),
) -> dict[str, str | int]:
    """
    Get raw file content for an artifact.

    Returns the content of project files like specs, plans, and other
    documentation. The path is validated to prevent directory traversal
    attacks - only files within the project directory can be accessed.

    Args:
        path: Path to the file (relative to project root or absolute)

    Returns:
        Dict with path and content

    Raises:
        HTTPException: 400 for invalid/unsafe paths, 404 for missing files

    Example request:
        GET /api/artifact?path=specs/my-feature.md

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
