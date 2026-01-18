---
title: Development Setup
description: How to set up your development environment for contributing to Cub.
---

# Development Setup

This guide walks you through setting up a development environment for contributing to Cub.

## Prerequisites

Before you begin, ensure you have:

| Requirement | Minimum Version | Check Command |
|-------------|-----------------|---------------|
| Python | 3.10+ | `python3 --version` |
| Git | 2.x | `git --version` |
| uv (recommended) | Latest | `uv --version` |

!!! tip "Why Python 3.10+?"
    Cub uses modern Python features including:

    - Match statements (`match`/`case`)
    - Type union syntax (`str | None` instead of `Optional[str]`)
    - Improved error messages

---

## Installation

### Step 1: Fork and Clone

```bash
# Fork on GitHub, then clone your fork
git clone https://github.com/YOUR-USERNAME/cub.git
cd cub
```

### Step 2: Install Dependencies

=== "uv (Recommended)"

    [uv](https://github.com/astral-sh/uv) is a fast Python package manager:

    ```bash
    # Install uv if you haven't already
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Sync dependencies (creates .venv automatically)
    uv sync

    # Activate the virtual environment
    source .venv/bin/activate
    ```

=== "pip"

    ```bash
    # Create virtual environment
    python3.10 -m venv .venv
    source .venv/bin/activate

    # Install in editable mode with dev dependencies
    pip install -e ".[dev]"
    ```

### Step 3: Verify Installation

```bash
# Run cub from source
cub --help

# Run tests
pytest tests/ -v

# Type checking
mypy src/cub

# Linting
ruff check src/ tests/
```

All commands should complete without errors.

---

## Development Tools

### Required Tools

| Tool | Purpose | Installation |
|------|---------|--------------|
| pytest | Test runner | Included in `[dev]` |
| mypy | Type checking | Included in `[dev]` |
| ruff | Linting + formatting | Included in `[dev]` |

### Optional Tools

| Tool | Purpose | Installation |
|------|---------|--------------|
| bats | Bash test runner | `brew install bats-core` |
| pre-commit | Git hooks | `pip install pre-commit` |

---

## Running Tests

### Python Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_config_loader.py -v

# Run tests matching a pattern
pytest tests/ -v -k "test_harness"

# Run with coverage report
pytest tests/ --cov=src/cub --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Bash Tests (for delegated commands)

```bash
# Install bats if needed
brew install bats-core  # macOS
# or
apt-get install bats    # Ubuntu

# Run bash tests
bats tests/
```

### Test Organization

```
tests/
+-- conftest.py           # pytest fixtures and configuration
+-- fixtures/             # Test data files
+-- test_config_loader.py # Config loading tests
+-- test_harness_*.py     # Harness backend tests
+-- test_task_*.py        # Task backend tests
+-- test_cli_*.py         # CLI command tests
+-- ...
```

---

## Type Checking

Cub uses strict mypy configuration. All code must pass type checking:

```bash
# Run type checker
mypy src/cub

# Check specific module
mypy src/cub/core/harness/
```

### Type Checking Rules

1. **Explicit types everywhere** - No implicit `Any`
2. **Use `|` for unions** - `str | None` not `Optional[str]`
3. **Protocol classes** - Use `typing.Protocol` for interfaces

```python
# Good
def process(value: str | None) -> list[str]:
    ...

# Bad
def process(value):  # Missing type hints
    ...
```

---

## Linting and Formatting

### Ruff

Cub uses [ruff](https://github.com/astral-sh/ruff) for both linting and formatting:

```bash
# Check for linting issues
ruff check src/ tests/

# Auto-fix issues
ruff check src/ tests/ --fix

# Format code
ruff format src/ tests/

# Check formatting without changing
ruff format src/ tests/ --check
```

### Code Style Guidelines

| Area | Style |
|------|-------|
| Imports | Absolute imports from `cub.core`, not relative |
| Line length | 100 characters max |
| Quotes | Double quotes for strings |
| Docstrings | Google style |
| Type hints | Required on all public functions |

```python
# Good - Absolute import
from cub.core.models import Task

# Bad - Relative import
from ..models import Task
```

---

## Project Configuration

### pyproject.toml

Key sections in `pyproject.toml`:

```toml
[project]
name = "cub"
requires-python = ">=3.10"

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-mock",
    "pytest-cov",
    "mypy>=1.0",
    "ruff>=0.1.0",
]

[tool.mypy]
strict = true
python_version = "3.10"

[tool.ruff]
line-length = 100
target-version = "py310"
```

### Test Configuration

In `conftest.py`:

```python
import pytest
from pathlib import Path

@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    project = tmp_path / "test-project"
    project.mkdir()
    return project

@pytest.fixture
def mock_harness(mocker):
    """Mock harness backend for testing."""
    # ...
```

---

## Common Development Tasks

### Adding a New Test

```python
# tests/test_my_feature.py
import pytest
from cub.core.my_module import my_function

def test_my_function_basic():
    """Test basic functionality."""
    result = my_function("input")
    assert result == "expected"

def test_my_function_edge_case():
    """Test edge case handling."""
    with pytest.raises(ValueError):
        my_function(None)
```

### Debugging

```bash
# Run with verbose pytest output
pytest tests/test_file.py -v -s

# Drop into debugger on failure
pytest tests/test_file.py --pdb

# Run cub with debug logging
CUB_DEBUG=true cub run --once
```

### Running Cub from Source

```bash
# Run commands directly
cub run --once
cub status
cub init

# Or via Python module
python -m cub run --once
```

---

## Pre-Commit Checklist

Before submitting a PR, ensure:

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Type checking passes: `mypy src/cub`
- [ ] Linting passes: `ruff check src/ tests/`
- [ ] Code is formatted: `ruff format src/ tests/`
- [ ] New features have tests
- [ ] Documentation is updated

```bash
# Run all checks at once
pytest tests/ -v && mypy src/cub && ruff check src/ tests/
```

---

## Troubleshooting

??? question "ImportError: cannot import name 'X' from 'cub'"
    Make sure you installed in editable mode:
    ```bash
    pip install -e ".[dev]"
    ```

??? question "mypy: error: Module 'cub' has no attribute 'X'"
    Check that `__init__.py` exports the module:
    ```python
    # src/cub/__init__.py
    from cub.core.my_module import X
    ```

??? question "Tests fail with 'fixture not found'"
    Ensure `conftest.py` is in the tests directory and contains the fixture.

??? question "ruff reports formatting issues in CI but not locally"
    Ensure your local ruff version matches CI:
    ```bash
    uv pip install ruff==0.1.0  # Match CI version
    ```

---

## Next Steps

<div class="grid cards" markdown>

-   :material-architecture: **Architecture**

    ---

    Understand Cub's module structure.

    [:octicons-arrow-right-24: Architecture](architecture.md)

-   :material-robot: **Adding Harnesses**

    ---

    Add support for new AI assistants.

    [:octicons-arrow-right-24: Harness Guide](harnesses.md)

-   :material-database: **Adding Backends**

    ---

    Create new task storage backends.

    [:octicons-arrow-right-24: Backend Guide](backends.md)

</div>
