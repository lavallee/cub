"""
Pytest configuration and shared fixtures.

Provides fixtures for temp directories, sample tasks/config, mock bd CLI responses,
and other test utilities used across the test suite.
"""

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from cub.core.config.models import (
    BudgetConfig,
    CleanupConfig,
    CubConfig,
    GuardrailsConfig,
    HarnessConfig,
    LoopConfig,
    ReviewConfig,
    StateConfig,
)
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType

# ==============================================================================
# Directory Fixtures
# ==============================================================================


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def project_dir(tmp_path):
    """
    Provide a temporary project directory with common structure.

    Creates:
    - .beads/issues.jsonl
    - .cub.json
    - .git/ directory
    """
    project = tmp_path / "project"
    project.mkdir()

    # Create .beads directory
    beads_dir = project / ".beads"
    beads_dir.mkdir()
    (beads_dir / "issues.jsonl").write_text("")

    # Create minimal .cub.json
    cub_config = {"harness": "claude", "budget": {"default": 500000}}
    (project / ".cub.json").write_text(json.dumps(cub_config, indent=2))

    # Create .git directory
    git_dir = project / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("")

    return project


@pytest.fixture
def user_config_dir(tmp_path):
    """Provide a temporary XDG_CONFIG_HOME/cub directory."""
    config_dir = tmp_path / "config" / "cub"
    config_dir.mkdir(parents=True)
    return config_dir


# ==============================================================================
# Sample Data Fixtures
# ==============================================================================


@pytest.fixture
def sample_task():
    """Provide a sample Task object for testing."""
    return Task(
        id="cub-001",
        title="Sample task",
        description="A sample task for testing",
        status=TaskStatus.OPEN,
        priority=TaskPriority.P2,
        type=TaskType.TASK,
    )


@pytest.fixture
def sample_tasks():
    """Provide a list of sample Task objects with various states."""
    return [
        Task(
            id="cub-001",
            title="Ready task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.FEATURE,
        ),
        Task(
            id="cub-002",
            title="In progress task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P0,
            type=TaskType.BUG,
            assignee="alice",
        ),
        Task(
            id="cub-003",
            title="Blocked task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            depends_on=["cub-001"],
        ),
        Task(
            id="cub-004",
            title="Completed task",
            status=TaskStatus.CLOSED,
            priority=TaskPriority.P3,
            type=TaskType.TASK,
        ),
    ]


@pytest.fixture
def sample_beads_jsonl():
    """Provide sample JSONL data matching beads format."""
    tasks = [
        {
            "id": "cub-001",
            "title": "Implement feature X",
            "description": "Feature description",
            "status": "open",
            "priority": 1,
            "issue_type": "feature",
            "labels": ["model:sonnet"],
            "blocks": ["cub-002"],
        },
        {
            "id": "cub-002",
            "title": "Test feature X",
            "description": "Test description",
            "status": "open",
            "priority": 2,
            "issue_type": "task",
            "dependsOn": ["cub-001"],
        },
        {
            "id": "cub-003",
            "title": "Bug fix",
            "description": "Fix bug",
            "status": "closed",
            "priority": 0,
            "issue_type": "bugfix",
        },
    ]
    return "\n".join(json.dumps(task) for task in tasks)


@pytest.fixture
def sample_config():
    """Provide a sample CubConfig object for testing."""
    return CubConfig(
        harness=HarnessConfig(name="claude"),
        budget=BudgetConfig(max_tokens_per_task=500000, max_total_cost=50.0),
        state=StateConfig(require_clean=True, run_tests=True),
        loop=LoopConfig(max_iterations=50, on_task_failure="stop"),
        guardrails=GuardrailsConfig(max_task_iterations=3, max_run_iterations=50),
        review=ReviewConfig(plan_strict=False),
    )


@pytest.fixture
def sample_config_dict():
    """Provide a sample config dict matching .cub.json format."""
    return {
        "harness": "claude",
        "budget": {
            "max_tokens_per_task": 500000,
            "max_tasks_per_session": None,
            "max_total_cost": 50.0,
        },
        "state": {
            "require_clean": True,
            "run_tests": True,
            "run_typecheck": False,
            "run_lint": False,
        },
        "loop": {"max_iterations": 50, "on_task_failure": "stop"},
        "guardrails": {
            "max_task_iterations": 3,
            "max_run_iterations": 50,
            "iteration_warning_threshold": 0.8,
            "secret_patterns": [],
        },
        "review": {"plan_strict": False, "block_on_concerns": False},
    }


# ==============================================================================
# Mock Fixtures
# ==============================================================================


@pytest.fixture
def mock_subprocess_run(monkeypatch):
    """
    Provide a mock for subprocess.run that can be configured per test.

    Usage:
        def test_something(mock_subprocess_run):
            mock_subprocess_run.configure(
                stdout='{"id": "cub-001"}',
                returncode=0
            )
    """
    mock = Mock()
    mock.stdout = ""
    mock.stderr = ""
    mock.returncode = 0

    def configure(stdout="", stderr="", returncode=0):
        mock.stdout = stdout
        mock.stderr = stderr
        mock.returncode = returncode
        return mock

    mock.configure = configure

    import subprocess

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock)

    return mock


@pytest.fixture
def mock_bd_list(mock_subprocess_run, sample_beads_jsonl):
    """
    Mock 'bd list --json' to return sample tasks.

    Usage:
        def test_something(mock_bd_list):
            # bd list --json will return sample tasks
            pass
    """
    tasks_json = json.dumps(
        [
            {
                "id": "cub-001",
                "title": "Task 1",
                "status": "open",
                "priority": 1,
                "issue_type": "task",
            },
            {
                "id": "cub-002",
                "title": "Task 2",
                "status": "in_progress",
                "priority": 0,
                "issue_type": "feature",
            },
        ]
    )

    def configure_bd_response(command, **kwargs):
        if "list" in command and "--json" in command:
            mock_subprocess_run.stdout = tasks_json
            mock_subprocess_run.returncode = 0
        elif "show" in command:
            mock_subprocess_run.stdout = json.dumps(
                {
                    "id": "cub-001",
                    "title": "Task 1",
                    "status": "open",
                    "priority": 1,
                    "issue_type": "task",
                }
            )
            mock_subprocess_run.returncode = 0
        else:
            mock_subprocess_run.stdout = ""
            mock_subprocess_run.returncode = 0
        return mock_subprocess_run

    import subprocess

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(subprocess, "run", configure_bd_response)

    return mock_subprocess_run


@pytest.fixture
def mock_git_commands(monkeypatch):
    """
    Mock common git commands for testing.

    Provides:
    - git status: clean working directory
    - git rev-parse --show-toplevel: project root
    - git log: empty commit history
    """
    responses = {
        "git status --porcelain": "",
        "git rev-parse --show-toplevel": "/tmp/project",
        "git log": "",
        "git diff": "",
    }

    def mock_run(command, *args, **kwargs):
        cmd_str = " ".join(command) if isinstance(command, list) else command
        mock = Mock()
        mock.returncode = 0
        mock.stdout = responses.get(cmd_str, "")
        mock.stderr = ""
        return mock

    import subprocess

    monkeypatch.setattr(subprocess, "run", mock_run)

    return responses


# ==============================================================================
# Environment Fixtures
# ==============================================================================


@pytest.fixture
def clean_env(monkeypatch):
    """
    Provide a clean environment without CUB_* env vars.

    Removes all CUB_* environment variables to ensure tests
    don't inherit configuration from the system.
    """
    # Remove all CUB_* env vars
    for key in list(os.environ.keys()):
        if key.startswith("CUB_"):
            monkeypatch.delenv(key, raising=False)

    # Set XDG_CONFIG_HOME to temp location
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/test-config")

    return monkeypatch


@pytest.fixture
def isolated_config(clean_env, tmp_path, monkeypatch):
    """
    Provide completely isolated config environment.

    Sets XDG_CONFIG_HOME and project directory to temporary locations
    to prevent tests from loading system or user configs.
    """
    config_home = tmp_path / "config"
    config_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    # Also clear the config cache if it exists
    try:
        from cub.core.config import clear_cache

        clear_cache()
    except ImportError:
        pass

    return config_home


# ==============================================================================
# File Fixtures
# ==============================================================================


@pytest.fixture
def beads_issues_file(project_dir, sample_beads_jsonl):
    """Create a .beads/issues.jsonl file with sample data."""
    issues_file = project_dir / ".beads" / "issues.jsonl"
    issues_file.write_text(sample_beads_jsonl)
    return issues_file


@pytest.fixture
def project_config_file(project_dir, sample_config_dict):
    """Create a .cub.json file with sample config."""
    config_file = project_dir / ".cub.json"
    config_file.write_text(json.dumps(sample_config_dict, indent=2))
    return config_file


@pytest.fixture
def user_config_file(user_config_dir):
    """Create a user config.json file with sample config."""
    config_file = user_config_dir / "config.json"
    config_data = {"guardrails": {"max_task_iterations": 5}}
    config_file.write_text(json.dumps(config_data, indent=2))
    return config_file


# ==============================================================================
# Utility Functions
# ==============================================================================


def write_jsonl(path: Path, data: list[dict[str, Any]]) -> None:
    """Helper to write JSONL data to a file."""
    with open(path, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Helper to read JSONL data from a file."""
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


# Make helpers available to tests
pytest.write_jsonl = write_jsonl
pytest.read_jsonl = read_jsonl
