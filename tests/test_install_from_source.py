"""Test that cub can be installed from source and runs correctly.

This test validates:
- Package structure is correct (pyproject.toml, src layout)
- All dependencies are properly declared
- CLI entry points are correctly configured
- Basic commands work after installation
"""

import subprocess
import sys
import tempfile
from pathlib import Path


def test_installation_from_source() -> None:
    """Test installing cub from source in a clean venv."""
    # Create a temporary directory for the venv
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_path = Path(tmpdir) / "test_venv"

        # Create virtual environment
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            check=True,
            capture_output=True,
        )

        # Get the path to the venv's pip
        if sys.platform == "win32":
            pip_path = venv_path / "Scripts" / "pip"
            python_path = venv_path / "Scripts" / "python"
        else:
            pip_path = venv_path / "bin" / "pip"
            python_path = venv_path / "bin" / "python"

        # Install cub in editable mode
        project_root = Path(__file__).parent.parent
        subprocess.run(
            [str(pip_path), "install", "-e", str(project_root)],
            check=True,
            capture_output=True,
        )

        # Test that we can import cub
        result = subprocess.run(
            [str(python_path), "-c", "import cub; import cub.cli; import cub.core"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"


def test_cli_entry_points() -> None:
    """Test that CLI entry points are correctly configured."""
    # This test runs in the current environment, so cub should already be installed
    result = subprocess.run(
        ["cub", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cub --help failed: {result.stderr}"
    assert "AI Coding Assistant Loop" in result.stdout


def test_basic_commands_available() -> None:
    """Test that basic cub commands are available."""
    commands = ["init", "run", "status"]

    for cmd in commands:
        result = subprocess.run(
            ["cub", cmd, "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"cub {cmd} --help failed: {result.stderr}"


def test_package_structure() -> None:
    """Test that package structure matches pyproject.toml configuration."""
    project_root = Path(__file__).parent.parent

    # Verify key files and directories exist
    assert (project_root / "pyproject.toml").exists()
    assert (project_root / "src" / "cub").exists()
    assert (project_root / "src" / "cub" / "cli").is_dir()
    assert (project_root / "src" / "cub" / "core").is_dir()
    assert (project_root / "src" / "cub" / "__init__.py").exists()


def test_dependencies_installable() -> None:
    """Test that all dependencies can be resolved and installed."""
    # This is implicitly tested by test_installation_from_source
    # If dependencies are broken, pip install will fail
    project_root = Path(__file__).parent.parent
    pyproject = project_root / "pyproject.toml"
    assert pyproject.exists()

    # Read and verify pyproject.toml has dependencies section
    content = pyproject.read_text()
    assert "dependencies" in content
    assert "pydantic" in content
    assert "typer" in content
    assert "claude-agent-sdk" in content
