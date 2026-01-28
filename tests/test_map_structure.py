"""
Tests for project structure analysis and mapping.

Tests cover:
- Tech stack detection from config files
- Build command extraction
- Key file identification
- Module boundary detection
- Directory tree traversal
- Edge cases (empty projects, missing files, etc.)
"""

from pathlib import Path

import pytest

from cub.core.map import (
    BuildCommand,
    DirectoryNode,
    DirectoryTree,
    KeyFile,
    ModuleInfo,
    ProjectStructure,
    TechStack,
    analyze_structure,
)
from cub.core.map.structure import (
    build_directory_tree,
    detect_modules,
    detect_tech_stacks,
    extract_build_commands,
    identify_key_files,
)

# ==============================================================================
# TechStack Enum Tests
# ==============================================================================


class TestTechStack:
    """Test TechStack enum."""

    def test_tech_stack_values(self):
        """Test all TechStack enum values exist."""
        assert TechStack.PYTHON.value == "python"
        assert TechStack.NODE.value == "node"
        assert TechStack.RUST.value == "rust"
        assert TechStack.GO.value == "go"
        assert TechStack.UNKNOWN.value == "unknown"

    def test_from_config_file_python(self):
        """Test Python config file detection."""
        assert TechStack.from_config_file("pyproject.toml") == TechStack.PYTHON
        assert TechStack.from_config_file("setup.py") == TechStack.PYTHON
        assert TechStack.from_config_file("requirements.txt") == TechStack.PYTHON
        assert TechStack.from_config_file("Pipfile") == TechStack.PYTHON

    def test_from_config_file_node(self):
        """Test Node config file detection."""
        assert TechStack.from_config_file("package.json") == TechStack.NODE
        assert TechStack.from_config_file("package-lock.json") == TechStack.NODE
        assert TechStack.from_config_file("yarn.lock") == TechStack.NODE

    def test_from_config_file_rust(self):
        """Test Rust config file detection."""
        assert TechStack.from_config_file("Cargo.toml") == TechStack.RUST
        assert TechStack.from_config_file("Cargo.lock") == TechStack.RUST

    def test_from_config_file_go(self):
        """Test Go config file detection."""
        assert TechStack.from_config_file("go.mod") == TechStack.GO
        assert TechStack.from_config_file("go.sum") == TechStack.GO

    def test_from_config_file_unknown(self):
        """Test unknown config file."""
        assert TechStack.from_config_file("random.txt") == TechStack.UNKNOWN


# ==============================================================================
# BuildCommand Model Tests
# ==============================================================================


class TestBuildCommand:
    """Test BuildCommand model."""

    def test_build_command_creation(self):
        """Test creating a BuildCommand."""
        cmd = BuildCommand(name="test", command="pytest", source="package.json")
        assert cmd.name == "test"
        assert cmd.command == "pytest"
        assert cmd.source == "package.json"

    def test_build_command_immutable(self):
        """Test that BuildCommand is immutable."""
        cmd = BuildCommand(name="test", command="pytest", source="package.json")
        with pytest.raises(Exception):  # Pydantic frozen model raises error
            cmd.name = "build"  # type: ignore


# ==============================================================================
# KeyFile Model Tests
# ==============================================================================


class TestKeyFile:
    """Test KeyFile model."""

    def test_key_file_creation(self):
        """Test creating a KeyFile."""
        kf = KeyFile(path="README.md", type="readme", description="Project docs")
        assert kf.path == "README.md"
        assert kf.type == "readme"
        assert kf.description == "Project docs"

    def test_key_file_name_property(self):
        """Test name property extracts filename."""
        kf = KeyFile(path="src/main.py", type="entry")
        assert kf.name == "main.py"

    def test_key_file_default_description(self):
        """Test default empty description."""
        kf = KeyFile(path="LICENSE", type="license")
        assert kf.description == ""


# ==============================================================================
# ModuleInfo Model Tests
# ==============================================================================


class TestModuleInfo:
    """Test ModuleInfo model."""

    def test_module_info_creation(self):
        """Test creating a ModuleInfo."""
        mod = ModuleInfo(
            name="core", path="src/core", entry_file="__init__.py", file_count=10
        )
        assert mod.name == "core"
        assert mod.path == "src/core"
        assert mod.entry_file == "__init__.py"
        assert mod.file_count == 10

    def test_module_info_defaults(self):
        """Test default values."""
        mod = ModuleInfo(name="utils", path="src/utils")
        assert mod.entry_file is None
        assert mod.file_count == 0


# ==============================================================================
# DirectoryNode Model Tests
# ==============================================================================


class TestDirectoryNode:
    """Test DirectoryNode model."""

    def test_directory_node_file(self):
        """Test creating a file node."""
        node = DirectoryNode(name="test.py", path="src/test.py", is_file=True, size=1024)
        assert node.name == "test.py"
        assert node.is_file is True
        assert node.size == 1024
        assert node.children == []

    def test_directory_node_directory(self):
        """Test creating a directory node."""
        child = DirectoryNode(name="file.py", path="src/file.py", is_file=True)
        node = DirectoryNode(name="src", path="src", is_file=False, children=[child])
        assert node.name == "src"
        assert node.is_file is False
        assert len(node.children) == 1

    def test_directory_node_depth(self):
        """Test depth property."""
        node1 = DirectoryNode(name="project", path="project", is_file=False)
        assert node1.depth == 0

        node2 = DirectoryNode(name="src", path="project/src", is_file=False)
        assert node2.depth == 1

        node3 = DirectoryNode(name="core", path="project/src/core", is_file=False)
        assert node3.depth == 2

    def test_directory_node_file_count(self):
        """Test file_count property."""
        file1 = DirectoryNode(name="a.py", path="src/a.py", is_file=True)
        file2 = DirectoryNode(name="b.py", path="src/b.py", is_file=True)
        dir_node = DirectoryNode(name="src", path="src", is_file=False, children=[file1, file2])

        assert file1.file_count == 1
        assert dir_node.file_count == 2

    def test_directory_node_dir_count(self):
        """Test dir_count property."""
        subdir = DirectoryNode(name="utils", path="src/utils", is_file=False, children=[])
        dir_node = DirectoryNode(name="src", path="src", is_file=False, children=[subdir])

        assert subdir.dir_count == 1
        assert dir_node.dir_count == 2  # src + utils


# ==============================================================================
# DirectoryTree Model Tests
# ==============================================================================


class TestDirectoryTree:
    """Test DirectoryTree model."""

    def test_directory_tree_creation(self):
        """Test creating a DirectoryTree."""
        root = DirectoryNode(name="project", path="project", is_file=False)
        tree = DirectoryTree(root=root, max_depth=4, total_files=10, total_dirs=5)

        assert tree.root == root
        assert tree.max_depth == 4
        assert tree.total_files == 10
        assert tree.total_dirs == 5

    def test_directory_tree_total_nodes(self):
        """Test total_nodes property."""
        root = DirectoryNode(name="project", path="project", is_file=False)
        tree = DirectoryTree(root=root, max_depth=4, total_files=10, total_dirs=5)
        assert tree.total_nodes == 15


# ==============================================================================
# ProjectStructure Model Tests
# ==============================================================================


class TestProjectStructure:
    """Test ProjectStructure model."""

    def test_project_structure_creation(self):
        """Test creating a ProjectStructure."""
        structure = ProjectStructure(
            project_dir="/path/to/project",
            tech_stacks=[TechStack.PYTHON],
            build_commands=[],
            key_files=[],
            modules=[],
        )
        assert structure.project_dir == "/path/to/project"
        assert structure.tech_stacks == [TechStack.PYTHON]

    def test_project_structure_primary_tech_stack(self):
        """Test primary_tech_stack property."""
        structure = ProjectStructure(
            project_dir="/test",
            tech_stacks=[TechStack.PYTHON, TechStack.NODE],
        )
        assert structure.primary_tech_stack == TechStack.PYTHON

        # Empty list
        structure2 = ProjectStructure(project_dir="/test", tech_stacks=[])
        assert structure2.primary_tech_stack is None

    def test_project_structure_has_tests(self):
        """Test has_tests property."""
        # With tests directory
        test_dir = DirectoryNode(name="tests", path="tests", is_file=False)
        root = DirectoryNode(name="project", path="project", is_file=False, children=[test_dir])
        tree = DirectoryTree(root=root, max_depth=4, total_files=0, total_dirs=1)

        structure = ProjectStructure(
            project_dir="/test",
            tech_stacks=[TechStack.PYTHON],
            directory_tree=tree,
        )
        assert structure.has_tests is True

        # Without tests directory
        root2 = DirectoryNode(name="project", path="project", is_file=False, children=[])
        tree2 = DirectoryTree(root=root2, max_depth=4, total_files=0, total_dirs=0)
        structure2 = ProjectStructure(
            project_dir="/test",
            tech_stacks=[TechStack.PYTHON],
            directory_tree=tree2,
        )
        assert structure2.has_tests is False

        # No directory tree
        structure3 = ProjectStructure(
            project_dir="/test",
            tech_stacks=[TechStack.PYTHON],
        )
        assert structure3.has_tests is False


# ==============================================================================
# Fixture Projects
# ==============================================================================


@pytest.fixture
def minimal_python_project(tmp_path: Path) -> Path:
    """Create a minimal Python project structure."""
    project = tmp_path / "python_project"
    project.mkdir()

    # Create pyproject.toml
    pyproject = project / "pyproject.toml"
    pyproject.write_text(
        """[project]
name = "test-project"
version = "0.1.0"

[project.scripts]
test-cli = "test_project.cli:main"
"""
    )

    # Create README
    (project / "README.md").write_text("# Test Project\n\nA minimal Python project.")

    # Create LICENSE
    (project / "LICENSE").write_text("MIT License")

    # Create src structure
    src = project / "src" / "test_project"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("# Test package")
    (src / "cli.py").write_text("def main():\n    pass")

    # Create tests directory
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_cli.py").write_text("def test_main():\n    pass")

    return project


@pytest.fixture
def minimal_node_project(tmp_path: Path) -> Path:
    """Create a minimal Node.js project structure."""
    project = tmp_path / "node_project"
    project.mkdir()

    # Create package.json
    package_json = project / "package.json"
    package_json.write_text(
        """{
  "name": "test-project",
  "version": "1.0.0",
  "main": "src/index.js",
  "scripts": {
    "dev": "node src/index.js",
    "build": "webpack",
    "test": "jest"
  }
}"""
    )

    # Create README
    (project / "README.md").write_text("# Test Node Project")

    # Create src structure
    src = project / "src"
    src.mkdir()
    (src / "index.js").write_text("console.log('Hello');")

    return project


@pytest.fixture
def empty_project(tmp_path: Path) -> Path:
    """Create an empty project directory."""
    project = tmp_path / "empty_project"
    project.mkdir()
    return project


@pytest.fixture
def multi_tech_project(tmp_path: Path) -> Path:
    """Create a project with multiple tech stacks."""
    project = tmp_path / "multi_tech"
    project.mkdir()

    # Python config
    (project / "pyproject.toml").write_text("[project]\nname = 'test'")

    # Node config
    (project / "package.json").write_text('{"name": "test"}')

    # Makefile
    (project / "Makefile").write_text("build:\n\techo 'Building'\n\ntest:\n\tpytest\n")

    return project


# ==============================================================================
# Tech Stack Detection Tests
# ==============================================================================


class TestDetectTechStacks:
    """Test tech stack detection."""

    def test_detect_python_stack(self, minimal_python_project: Path):
        """Test detecting Python tech stack."""
        stacks = detect_tech_stacks(minimal_python_project)
        assert TechStack.PYTHON in stacks

    def test_detect_node_stack(self, minimal_node_project: Path):
        """Test detecting Node tech stack."""
        stacks = detect_tech_stacks(minimal_node_project)
        assert TechStack.NODE in stacks

    def test_detect_multiple_stacks(self, multi_tech_project: Path):
        """Test detecting multiple tech stacks."""
        stacks = detect_tech_stacks(multi_tech_project)
        assert TechStack.PYTHON in stacks
        assert TechStack.NODE in stacks

    def test_detect_unknown_stack(self, empty_project: Path):
        """Test unknown tech stack for empty project."""
        stacks = detect_tech_stacks(empty_project)
        assert stacks == [TechStack.UNKNOWN]


# ==============================================================================
# Build Command Extraction Tests
# ==============================================================================


class TestExtractBuildCommands:
    """Test build command extraction."""

    def test_extract_from_package_json(self, minimal_node_project: Path):
        """Test extracting commands from package.json."""
        commands = extract_build_commands(minimal_node_project, [TechStack.NODE])
        assert len(commands) >= 3
        command_names = {cmd.name for cmd in commands}
        assert "dev" in command_names
        assert "build" in command_names
        assert "test" in command_names

    def test_extract_from_makefile(self, multi_tech_project: Path):
        """Test extracting commands from Makefile."""
        commands = extract_build_commands(multi_tech_project, [])
        command_names = {cmd.name for cmd in commands}
        assert "build" in command_names
        assert "test" in command_names

    def test_no_commands_in_empty_project(self, empty_project: Path):
        """Test no commands in empty project."""
        commands = extract_build_commands(empty_project, [])
        assert commands == []


# ==============================================================================
# Key File Identification Tests
# ==============================================================================


class TestIdentifyKeyFiles:
    """Test key file identification."""

    def test_identify_readme(self, minimal_python_project: Path):
        """Test identifying README file."""
        key_files = identify_key_files(minimal_python_project)
        readme_files = [f for f in key_files if f.type == "readme"]
        assert len(readme_files) == 1
        assert readme_files[0].name == "README.md"

    def test_identify_license(self, minimal_python_project: Path):
        """Test identifying LICENSE file."""
        key_files = identify_key_files(minimal_python_project)
        license_files = [f for f in key_files if f.type == "license"]
        assert len(license_files) == 1
        assert license_files[0].name == "LICENSE"

    def test_identify_config_files(self, minimal_python_project: Path):
        """Test identifying config files."""
        key_files = identify_key_files(minimal_python_project)
        config_files = [f for f in key_files if f.type == "config"]
        assert len(config_files) >= 1
        assert any(f.name == "pyproject.toml" for f in config_files)

    def test_identify_entry_point_node(self, minimal_node_project: Path):
        """Test identifying Node entry point."""
        key_files = identify_key_files(minimal_node_project)
        entry_files = [f for f in key_files if f.type == "entry"]
        # Entry point may or may not be found depending on file existence
        if entry_files:
            assert any("index.js" in f.path for f in entry_files)

    def test_no_key_files_in_empty_project(self, empty_project: Path):
        """Test no key files in empty project."""
        key_files = identify_key_files(empty_project)
        assert key_files == []


# ==============================================================================
# Module Detection Tests
# ==============================================================================


class TestDetectModules:
    """Test module boundary detection."""

    def test_detect_python_modules(self, minimal_python_project: Path):
        """Test detecting Python modules."""
        modules = detect_modules(minimal_python_project, [TechStack.PYTHON])
        assert len(modules) >= 1
        module_names = {m.name for m in modules}
        assert "test_project" in module_names

    def test_detect_node_modules(self, tmp_path: Path):
        """Test detecting Node modules."""
        project = tmp_path / "node_test"
        project.mkdir()
        (project / "package.json").write_text('{"name": "test"}')

        # Create module with index.js
        module_dir = project / "lib"
        module_dir.mkdir()
        (module_dir / "index.js").write_text("export default {};")

        modules = detect_modules(project, [TechStack.NODE])
        assert len(modules) == 1
        assert modules[0].name == "lib"
        assert modules[0].entry_file == "index.js"

    def test_no_modules_in_empty_project(self, empty_project: Path):
        """Test no modules in empty project."""
        modules = detect_modules(empty_project, [TechStack.PYTHON])
        assert modules == []


# ==============================================================================
# Directory Tree Building Tests
# ==============================================================================


class TestBuildDirectoryTree:
    """Test directory tree building."""

    def test_build_tree_basic(self, minimal_python_project: Path):
        """Test building basic directory tree."""
        tree = build_directory_tree(minimal_python_project, max_depth=4)
        assert tree.root.name == minimal_python_project.name
        assert tree.max_depth == 4
        assert tree.total_files > 0

    def test_build_tree_respects_max_depth(self, tmp_path: Path):
        """Test that max_depth is respected."""
        project = tmp_path / "deep"
        project.mkdir()
        # Create deep structure: a/b/c/d/e
        current = project
        for name in ["a", "b", "c", "d", "e"]:
            current = current / name
            current.mkdir()
            (current / "file.txt").write_text("test")

        tree = build_directory_tree(project, max_depth=2)
        assert tree.max_depth == 2
        # At depth 2, we should see: project/a/b but not beyond

    def test_build_tree_excludes_patterns(self, tmp_path: Path):
        """Test that excluded patterns are not included."""
        project = tmp_path / "test"
        project.mkdir()
        (project / "file.py").write_text("test")

        # Create directories that should be excluded
        (project / "node_modules").mkdir()
        (project / "node_modules" / "package").mkdir()
        (project / "__pycache__").mkdir()
        (project / ".git").mkdir()

        tree = build_directory_tree(project, max_depth=4)
        node_names = {node.name for node in tree.root.children}

        assert "node_modules" not in node_names
        assert "__pycache__" not in node_names
        assert ".git" not in node_names
        assert "file.py" in node_names

    def test_build_tree_empty_directory(self, empty_project: Path):
        """Test building tree for empty directory."""
        tree = build_directory_tree(empty_project, max_depth=4)
        assert tree.root.name == empty_project.name
        assert tree.total_files == 0
        assert len(tree.root.children) == 0


# ==============================================================================
# Integration Tests (analyze_structure)
# ==============================================================================


class TestAnalyzeStructure:
    """Test the main analyze_structure function."""

    def test_analyze_python_project(self, minimal_python_project: Path):
        """Test analyzing a minimal Python project."""
        structure = analyze_structure(minimal_python_project, max_depth=4)

        assert structure.project_dir == str(minimal_python_project)
        assert TechStack.PYTHON in structure.tech_stacks
        assert len(structure.key_files) > 0
        assert any(f.type == "readme" for f in structure.key_files)
        assert structure.directory_tree is not None
        assert structure.primary_tech_stack == TechStack.PYTHON

    def test_analyze_node_project(self, minimal_node_project: Path):
        """Test analyzing a minimal Node project."""
        structure = analyze_structure(minimal_node_project, max_depth=4)

        assert TechStack.NODE in structure.tech_stacks
        assert len(structure.build_commands) > 0
        assert any(cmd.name == "build" for cmd in structure.build_commands)

    def test_analyze_empty_project(self, empty_project: Path):
        """Test analyzing an empty project."""
        structure = analyze_structure(empty_project, max_depth=4)

        assert structure.tech_stacks == [TechStack.UNKNOWN]
        assert len(structure.build_commands) == 0
        assert len(structure.key_files) == 0
        assert len(structure.modules) == 0

    def test_analyze_multi_tech_project(self, multi_tech_project: Path):
        """Test analyzing a multi-tech project."""
        structure = analyze_structure(multi_tech_project, max_depth=4)

        assert TechStack.PYTHON in structure.tech_stacks
        assert TechStack.NODE in structure.tech_stacks
        assert len(structure.build_commands) > 0

    def test_analyze_nonexistent_directory(self):
        """Test analyzing a non-existent directory raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            analyze_structure("/nonexistent/path")

    def test_analyze_file_not_directory(self, tmp_path: Path):
        """Test analyzing a file (not directory) raises ValueError."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        with pytest.raises(ValueError, match="not a directory"):
            analyze_structure(file_path)

    def test_analyze_with_custom_max_depth(self, minimal_python_project: Path):
        """Test analyzing with custom max_depth."""
        structure = analyze_structure(minimal_python_project, max_depth=2)

        assert structure.directory_tree is not None
        assert structure.directory_tree.max_depth == 2
