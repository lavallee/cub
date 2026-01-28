"""
Data models for project structure mapping.

Defines models for representing project structure, tech stack detection,
build commands, and directory trees. These models form the foundation
of the codebase map feature.
"""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class TechStack(str, Enum):
    """Detected technology stacks and languages.

    Identifies the primary languages and frameworks used in the project
    based on config files and directory structure.
    """

    PYTHON = "python"
    NODE = "node"
    RUST = "rust"
    GO = "go"
    RUBY = "ruby"
    JAVA = "java"
    UNKNOWN = "unknown"

    @classmethod
    def from_config_file(cls, filename: str) -> "TechStack":
        """Detect tech stack from config filename.

        Args:
            filename: Name of the configuration file

        Returns:
            TechStack enum value based on the config file
        """
        python_configs = {
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
            "Pipfile",
            "poetry.lock",
        }
        node_configs = {"package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
        rust_configs = {"Cargo.toml", "Cargo.lock"}
        go_configs = {"go.mod", "go.sum"}
        ruby_configs = {"Gemfile", "Gemfile.lock"}
        java_configs = {"pom.xml", "build.gradle", "build.gradle.kts"}

        if filename in python_configs:
            return cls.PYTHON
        elif filename in node_configs:
            return cls.NODE
        elif filename in rust_configs:
            return cls.RUST
        elif filename in go_configs:
            return cls.GO
        elif filename in ruby_configs:
            return cls.RUBY
        elif filename in java_configs:
            return cls.JAVA
        return cls.UNKNOWN


class BuildCommand(BaseModel):
    """Represents a build or development command from project config.

    Extracted from package.json scripts, pyproject.toml scripts,
    Makefile targets, etc.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Command name (e.g., 'build', 'test', 'dev')")
    command: str = Field(..., description="Full command to execute")
    source: str = Field(..., description="Config file where command was found")


class KeyFile(BaseModel):
    """Represents an important file in the project structure.

    Key files include README, LICENSE, main entry points,
    and configuration files.
    """

    model_config = ConfigDict(frozen=True)

    path: str = Field(..., description="Relative path from project root")
    type: str = Field(..., description="File type (readme, license, config, entry)")
    description: str = Field(default="", description="Brief description of the file's purpose")

    @property
    def name(self) -> str:
        """Get the filename without path."""
        return Path(self.path).name


class ModuleInfo(BaseModel):
    """Information about a module or package boundary.

    Modules are top-level directories containing __init__.py (Python)
    or index.{js,ts} (JavaScript/TypeScript).
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Module name")
    path: str = Field(..., description="Relative path from project root")
    entry_file: str | None = Field(
        default=None, description="Entry point file (__init__.py, index.js, etc.)"
    )
    file_count: int = Field(default=0, ge=0, description="Number of files in this module")


class DirectoryNode(BaseModel):
    """Represents a node in the directory tree.

    Each node can contain files and subdirectories, forming
    a recursive tree structure.
    """

    name: str = Field(..., description="Directory or file name")
    path: str = Field(..., description="Relative path from project root")
    is_file: bool = Field(default=False, description="True if this is a file, False if directory")
    children: list["DirectoryNode"] = Field(
        default_factory=list, description="Subdirectories or files"
    )
    size: int | None = Field(default=None, ge=0, description="File size in bytes (files only)")

    @property
    def depth(self) -> int:
        """Calculate depth in the tree (0 = root)."""
        return len(Path(self.path).parts) - 1

    @property
    def file_count(self) -> int:
        """Count total files in this node and all children."""
        if self.is_file:
            return 1
        return sum(child.file_count for child in self.children)

    @property
    def dir_count(self) -> int:
        """Count total directories in this node and all children."""
        if self.is_file:
            return 0
        # Count self + all child directories
        return 1 + sum(child.dir_count for child in self.children)


class DirectoryTree(BaseModel):
    """Complete directory tree for the project.

    Represents the hierarchical structure of directories and files
    up to a specified depth.
    """

    root: DirectoryNode = Field(..., description="Root directory node")
    max_depth: int = Field(default=4, ge=1, description="Maximum depth traversed")
    total_files: int = Field(default=0, ge=0, description="Total files in tree")
    total_dirs: int = Field(default=0, ge=0, description="Total directories in tree")

    @property
    def total_nodes(self) -> int:
        """Total number of nodes (files + directories)."""
        return self.total_files + self.total_dirs


class ProjectStructure(BaseModel):
    """Complete structural analysis of a project.

    This is the top-level model returned by analyze_structure(),
    containing all structural information about the project without
    code intelligence (imports, exports, etc.).
    """

    project_dir: str = Field(..., description="Absolute path to project root")
    tech_stacks: list[TechStack] = Field(
        default_factory=list, description="Detected technology stacks"
    )
    build_commands: list[BuildCommand] = Field(
        default_factory=list, description="Available build/dev commands"
    )
    key_files: list[KeyFile] = Field(
        default_factory=list, description="Important files (README, LICENSE, etc.)"
    )
    modules: list[ModuleInfo] = Field(
        default_factory=list, description="Detected modules/packages"
    )
    directory_tree: DirectoryTree | None = Field(
        default=None, description="Directory tree structure"
    )

    @property
    def primary_tech_stack(self) -> TechStack | None:
        """Get the primary/first detected tech stack."""
        return self.tech_stacks[0] if self.tech_stacks else None

    @property
    def has_tests(self) -> bool:
        """Check if project has test directories."""
        if not self.directory_tree:
            return False
        # Look for common test directory names
        test_dirs = {"tests", "test", "__tests__", "spec"}
        return any(
            node.name in test_dirs
            for node in self.directory_tree.root.children
            if not node.is_file
        )
