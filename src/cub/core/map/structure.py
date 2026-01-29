"""
Project structure analysis implementation.

Provides functions for analyzing project structure, detecting tech stacks,
extracting build commands, and identifying key files and module boundaries.
"""

import json
from pathlib import Path

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]

from cub.core.map.models import (
    BuildCommand,
    DirectoryNode,
    DirectoryTree,
    KeyFile,
    ModuleInfo,
    ProjectStructure,
    TechStack,
)


def analyze_structure(project_dir: Path | str, max_depth: int = 4) -> ProjectStructure:
    """Analyze project structure and extract metadata.

    This is the main entry point for structure analysis. It performs:
    - Tech stack detection from config files
    - Build command extraction
    - Key file identification
    - Module boundary detection
    - Directory tree traversal

    Args:
        project_dir: Path to project root directory
        max_depth: Maximum directory depth to traverse (default: 4)

    Returns:
        ProjectStructure containing all structural analysis results

    Raises:
        ValueError: If project_dir does not exist or is not a directory
    """
    project_path = Path(project_dir).resolve()
    if not project_path.exists():
        raise ValueError(f"Project directory does not exist: {project_dir}")
    if not project_path.is_dir():
        raise ValueError(f"Project path is not a directory: {project_dir}")

    # Detect tech stacks
    tech_stacks = detect_tech_stacks(project_path)

    # Extract build commands
    build_commands = extract_build_commands(project_path, tech_stacks)

    # Identify key files
    key_files = identify_key_files(project_path)

    # Detect module boundaries
    modules = detect_modules(project_path, tech_stacks)

    # Build directory tree
    directory_tree = build_directory_tree(project_path, max_depth)

    return ProjectStructure(
        project_dir=str(project_path),
        tech_stacks=tech_stacks,
        build_commands=build_commands,
        key_files=key_files,
        modules=modules,
        directory_tree=directory_tree,
    )


def detect_tech_stacks(project_dir: Path) -> list[TechStack]:
    """Detect technology stacks from config files.

    Args:
        project_dir: Path to project root

    Returns:
        List of detected TechStack enum values, ordered by detection
    """
    stacks_found: set[TechStack] = set()
    config_files = [
        # Python
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "Pipfile",
        "poetry.lock",
        # Node
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        # Rust
        "Cargo.toml",
        "Cargo.lock",
        # Go
        "go.mod",
        "go.sum",
        # Ruby
        "Gemfile",
        "Gemfile.lock",
        # Java
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
    ]

    for config_file in config_files:
        if (project_dir / config_file).exists():
            stack = TechStack.from_config_file(config_file)
            if stack != TechStack.UNKNOWN:
                stacks_found.add(stack)

    # Return in consistent order (most common first)
    ordered_stacks = [TechStack.PYTHON, TechStack.NODE, TechStack.RUST, TechStack.GO]
    result = [stack for stack in ordered_stacks if stack in stacks_found]

    # Add any others not in the ordered list
    result.extend(stack for stack in stacks_found if stack not in result)

    return result if result else [TechStack.UNKNOWN]


def extract_build_commands(
    project_dir: Path, tech_stacks: list[TechStack]
) -> list[BuildCommand]:
    """Extract build and development commands from config files.

    Args:
        project_dir: Path to project root
        tech_stacks: List of detected tech stacks

    Returns:
        List of BuildCommand objects
    """
    commands: list[BuildCommand] = []

    # Extract from package.json (Node)
    if TechStack.NODE in tech_stacks:
        commands.extend(_extract_from_package_json(project_dir))

    # Extract from pyproject.toml (Python)
    if TechStack.PYTHON in tech_stacks:
        commands.extend(_extract_from_pyproject(project_dir))

    # Extract from Makefile (any stack)
    commands.extend(_extract_from_makefile(project_dir))

    return commands


def _extract_from_package_json(project_dir: Path) -> list[BuildCommand]:
    """Extract scripts from package.json."""
    package_json = project_dir / "package.json"
    if not package_json.exists():
        return []

    try:
        data = json.loads(package_json.read_text())
        scripts = data.get("scripts", {})
        return [
            BuildCommand(name=name, command=cmd, source="package.json")
            for name, cmd in scripts.items()
        ]
    except (json.JSONDecodeError, OSError):
        return []


def _extract_from_pyproject(project_dir: Path) -> list[BuildCommand]:
    """Extract scripts from pyproject.toml."""
    pyproject = project_dir / "pyproject.toml"
    if not pyproject.exists():
        return []

    try:
        data = tomllib.loads(pyproject.read_text())
        scripts = data.get("project", {}).get("scripts", {})
        commands = [
            BuildCommand(name=name, command=cmd, source="pyproject.toml")
            for name, cmd in scripts.items()
        ]

        # Also check for tool.poetry.scripts
        poetry_scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
        commands.extend(
            BuildCommand(name=name, command=cmd, source="pyproject.toml")
            for name, cmd in poetry_scripts.items()
        )

        return commands
    except (tomllib.TOMLDecodeError, OSError):
        return []


def _extract_from_makefile(project_dir: Path) -> list[BuildCommand]:
    """Extract targets from Makefile."""
    makefile_names = ["Makefile", "makefile", "GNUmakefile"]
    makefile = None
    for name in makefile_names:
        candidate = project_dir / name
        if candidate.exists():
            makefile = candidate
            break

    if not makefile:
        return []

    try:
        content = makefile.read_text()
        commands = []
        for line in content.splitlines():
            # Match target definitions (simple heuristic)
            # Target lines start with word chars and contain ':' not inside a recipe
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", "\t", " ")):
                if ":" in stripped and not stripped.startswith("."):
                    # Extract target name (before first colon)
                    target = stripped.split(":")[0].strip()
                    if target and not any(c in target for c in ["$", "=", " "]):
                        commands.append(
                            BuildCommand(
                                name=target,
                                command=f"make {target}",
                                source=makefile.name,
                            )
                        )
        return commands
    except OSError:
        return []


def identify_key_files(project_dir: Path) -> list[KeyFile]:
    """Identify important files in the project.

    Looks for README, LICENSE, and other key files.

    Args:
        project_dir: Path to project root

    Returns:
        List of KeyFile objects
    """
    key_files: list[KeyFile] = []

    # README files
    readme_patterns = ["README.md", "README.rst", "README.txt", "README"]
    for pattern in readme_patterns:
        readme = project_dir / pattern
        if readme.exists():
            rel_path = str(readme.relative_to(project_dir))
            key_files.append(
                KeyFile(path=rel_path, type="readme", description="Project documentation")
            )
            break  # Only add first README found

    # LICENSE files
    license_patterns = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]
    for pattern in license_patterns:
        license_file = project_dir / pattern
        if license_file.exists():
            rel_path = str(license_file.relative_to(project_dir))
            key_files.append(KeyFile(path=rel_path, type="license", description="Project license"))
            break  # Only add first LICENSE found

    # Configuration files
    config_files = [
        ("pyproject.toml", "Python project configuration"),
        ("package.json", "Node.js project configuration"),
        ("Cargo.toml", "Rust project configuration"),
        ("go.mod", "Go module configuration"),
    ]
    for filename, description in config_files:
        config_file = project_dir / filename
        if config_file.exists():
            rel_path = str(config_file.relative_to(project_dir))
            key_files.append(KeyFile(path=rel_path, type="config", description=description))

    # Entry points from package.json
    package_json = project_dir / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text())
            main_file = data.get("main")
            if main_file:
                entry_path = project_dir / main_file
                if entry_path.exists():
                    rel_path = str(entry_path.relative_to(project_dir))
                    key_files.append(
                        KeyFile(path=rel_path, type="entry", description="Main entry point")
                    )
        except (json.JSONDecodeError, OSError):
            pass

    # Entry points from pyproject.toml
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text())
            scripts = data.get("project", {}).get("scripts", {})
            if scripts:
                # First script is often the main entry point
                first_script = next(iter(scripts.values()), None)
                if first_script and ":" in first_script:
                    # Format: "module:function"
                    module_path = first_script.split(":")[0].replace(".", "/")
                    entry_path = project_dir / "src" / f"{module_path}.py"
                    if entry_path.exists():
                        rel_path = str(entry_path.relative_to(project_dir))
                        key_files.append(
                            KeyFile(
                                path=rel_path,
                                type="entry",
                                description="Main entry point",
                            )
                        )
        except (tomllib.TOMLDecodeError, OSError):
            pass

    return key_files


def detect_modules(project_dir: Path, tech_stacks: list[TechStack]) -> list[ModuleInfo]:
    """Detect module boundaries in the project.

    For Python: directories with __init__.py
    For Node: directories with index.js or index.ts

    Args:
        project_dir: Path to project root
        tech_stacks: List of detected tech stacks

    Returns:
        List of ModuleInfo objects
    """
    modules: list[ModuleInfo] = []

    # Check for src/ directory
    src_dir = project_dir / "src"
    search_roots = [src_dir] if src_dir.exists() and src_dir.is_dir() else [project_dir]

    for root in search_roots:
        if TechStack.PYTHON in tech_stacks:
            modules.extend(_detect_python_modules(root, project_dir))

        if TechStack.NODE in tech_stacks:
            modules.extend(_detect_node_modules(root, project_dir))

    return modules


def _detect_python_modules(search_root: Path, project_dir: Path) -> list[ModuleInfo]:
    """Detect Python modules (directories with __init__.py)."""
    modules: list[ModuleInfo] = []

    # Only look at top-level directories
    for item in search_root.iterdir():
        if not item.is_dir():
            continue
        if item.name.startswith(".") or item.name == "__pycache__":
            continue

        init_file = item / "__init__.py"
        if init_file.exists():
            rel_path = str(item.relative_to(project_dir))
            # Count Python files in module
            try:
                file_count = len(list(item.rglob("*.py")))
            except OSError:
                file_count = 0
            modules.append(
                ModuleInfo(
                    name=item.name,
                    path=rel_path,
                    entry_file="__init__.py",
                    file_count=file_count,
                )
            )

    return modules


def _detect_node_modules(search_root: Path, project_dir: Path) -> list[ModuleInfo]:
    """Detect Node modules (directories with index.js or index.ts)."""
    modules: list[ModuleInfo] = []

    # Only look at top-level directories
    for item in search_root.iterdir():
        if not item.is_dir():
            continue
        if item.name.startswith(".") or item.name == "node_modules":
            continue

        # Look for index files
        entry_file = None
        for pattern in ["index.ts", "index.js", "index.tsx", "index.jsx"]:
            if (item / pattern).exists():
                entry_file = pattern
                break

        if entry_file:
            rel_path = str(item.relative_to(project_dir))
            # Count JS/TS files in module
            try:
                file_count = len(
                    list(item.rglob("*.js"))
                    + list(item.rglob("*.ts"))
                    + list(item.rglob("*.jsx"))
                    + list(item.rglob("*.tsx"))
                )
            except OSError:
                file_count = 0
            modules.append(
                ModuleInfo(
                    name=item.name,
                    path=rel_path,
                    entry_file=entry_file,
                    file_count=file_count,
                )
            )

    return modules


def build_directory_tree(project_dir: Path, max_depth: int = 4) -> DirectoryTree:
    """Build directory tree structure up to max_depth.

    Args:
        project_dir: Path to project root
        max_depth: Maximum depth to traverse

    Returns:
        DirectoryTree object representing the project structure
    """
    # Exclude patterns (matching MapConfig defaults)
    exclude_patterns = {
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
        ".tox",
        "coverage",
        "htmlcov",
        ".DS_Store",
    }

    def should_exclude(path: Path) -> bool:
        """Check if path should be excluded."""
        return any(part in exclude_patterns for part in path.parts)

    def build_node(path: Path, current_depth: int) -> DirectoryNode:
        """Recursively build directory nodes."""
        rel_path = str(path.relative_to(project_dir))
        if rel_path == ".":
            rel_path = project_dir.name

        if path.is_file():
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            return DirectoryNode(
                name=path.name,
                path=rel_path,
                is_file=True,
                children=[],
                size=size,
            )

        # Skip non-file, non-directory entries (sockets, pipes, etc.)
        if not path.is_dir():
            return DirectoryNode(
                name=path.name,
                path=rel_path,
                is_file=True,
                children=[],
                size=0,
            )

        # Directory node
        children: list[DirectoryNode] = []
        if current_depth < max_depth:
            try:
                for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
                    if should_exclude(item):
                        continue
                    child_node = build_node(item, current_depth + 1)
                    children.append(child_node)
            except OSError:
                # Skip directories we can't read (PermissionError, NotADirectoryError, etc.)
                pass

        return DirectoryNode(
            name=path.name,
            path=rel_path,
            is_file=False,
            children=children,
        )

    root_node = build_node(project_dir, 0)
    total_files = root_node.file_count
    total_dirs = root_node.dir_count - 1  # Don't count root itself

    return DirectoryTree(
        root=root_node,
        max_depth=max_depth,
        total_files=total_files,
        total_dirs=total_dirs,
    )
