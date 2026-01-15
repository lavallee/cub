# Cub Test Suite

Comprehensive test suite for the cub autonomous AI coding agent harness.

## Overview

Cub uses two complementary test frameworks:

### Pytest (Python Tests)
- **Framework**: [pytest](https://docs.pytest.org/) with coverage reporting
- **Target**: Python core modules (v0.21+ migration from Bash to Python)
- **Total Tests**: 254 tests
- **Coverage**: 64% (target: 80%)
- **Location**: `tests/test_*.py`

### Bats (Bash Tests)
- **Framework**: [Bats (Bash Automated Testing System)](https://github.com/bats-core/bats-core)
- **Target**: Legacy Bash scripts and end-to-end workflows
- **Total Tests**: 100+
- **Location**: `tests/*.bats`

## Python Test Suite (Pytest)

### Running Pytest Tests

```bash
# Run all Python tests
pytest

# Run with coverage report
pytest --cov=src/cub --cov-report=term-missing

# Run specific test file
pytest tests/test_tasks_beads.py

# Run specific test class or function
pytest tests/test_tasks_beads.py::TestListTasks
pytest tests/test_tasks_beads.py::TestListTasks::test_list_all_tasks

# Run with verbose output
pytest -v

# Run with extra verbose output (show all output)
pytest -vv -s
```

### Python Test Files

**Core Modules:**
- `test_config_loader.py` - Configuration loading with XDG paths, merging, env overrides
- `test_models.py` - Pydantic model validation and serialization
- `test_logging.py` - Structured JSONL logging

**Task Backends:**
- `test_tasks_backend.py` - Task backend protocol and registry
- `test_tasks_beads.py` - Beads backend (bd CLI wrapper)
- `test_tasks_json.py` - JSON file backend (prd.json)

**Harness Backends:**
- `test_harness_backend.py` - Harness backend protocol and registry
- `test_harness_claude.py` - Claude Code harness integration

**Status & Monitoring:**
- `test_status_writer.py` - RunStatus serialization and status.json management

**Utilities:**
- `test_hooks.py` - Hook execution and context passing

**Test Fixtures:**
- `conftest.py` - Shared pytest fixtures (temp dirs, sample data, mocks)

### Coverage Goals

Current coverage: **64%**

**Target coverage by module:**
- `src/cub/core/config/`: 99% ✅
- `src/cub/core/tasks/`: 85% ✅
- `src/cub/core/harness/`: 80% (currently 79%)
- `src/cub/core/status/`: 95% ✅
- `src/cub/utils/`: 90% ✅
- `src/cub/cli/`: 0% (deferred - CLI testing in progress)

**Overall target: 80%** (working towards this incrementally)

### Writing Python Tests

#### Test Structure

```python
"""
Tests for module_name.

Description of what this test file covers.
"""

import pytest
from cub.module import function_to_test


class TestFeatureName:
    """Tests for specific feature."""

    def test_happy_path(self, fixture_name):
        """Test the expected behavior."""
        # Arrange
        setup_data = ...

        # Act
        result = function_to_test(setup_data)

        # Assert
        assert result == expected_value

    def test_error_case(self, fixture_name):
        """Test error handling."""
        with pytest.raises(ValueError, match="expected error message"):
            function_to_test(invalid_data)
```

#### Using Fixtures

Available fixtures (see `conftest.py`):

```python
def test_with_fixtures(temp_dir, sample_task, sample_config):
    """Fixtures provide common test data."""
    # temp_dir: pathlib.Path to temporary directory
    # sample_task: Task object with test data
    # sample_config: CubConfig object with defaults
    pass
```

#### Mocking External Commands

```python
from unittest.mock import patch

@patch('subprocess.run')
def test_with_mock(mock_run):
    """Mock subprocess calls."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = '{"result": "success"}'

    result = function_that_calls_subprocess()
    assert result == "success"
```

### Best Practices

1. **Test Organization**: Group related tests in classes (`class TestFeatureName`)
2. **Descriptive Names**: `test_function_when_condition_then_outcome`
3. **AAA Pattern**: Arrange, Act, Assert - keep tests readable
4. **Fixtures Over Setup**: Use pytest fixtures instead of setup/teardown
5. **Mock External Deps**: Mock subprocess calls, file I/O, network requests
6. **Test Errors**: Include tests for error conditions and edge cases
7. **Fast Tests**: Tests should run in <2 seconds total
8. **Isolated Tests**: No test should depend on another test's state

## Bats Test Suite (Bash)

## Test Files

### Core Library Tests

**`tasks.bats`** (25 tests)
- Backend detection (JSON, beads)
- PRD validation
- Task retrieval and filtering
- Status updates
- Task notes and creation
- Task counting and completion
- Blocked task detection
- Task ID generation

**`harness.bats`** (17 tests)
- Harness detection (Claude Code, OpenAI Codex)
- Availability checks
- Version retrieval
- Claude stream JSON parsing
- Invocation dispatch
- Environment variable handling
- Integration with actual harnesses

### Error Handling Tests

**`error_handling.bats`** (22 tests)
- File system errors (missing files, read-only)
- Invalid input handling
- Malformed JSON
- Circular dependencies
- Special characters and edge cases
- Concurrent operations
- Large datasets (100+ tasks)
- Deep dependency chains

### Integration Tests

**`integration.bats`** (16 tests)
- Real Claude Code invocations
- Real Codex invocations
- Authentication error handling
- Network error simulation
- Timeout handling
- Empty and long prompts
- Retry logic
- UTF-8 and special characters
- Concurrent harness invocations

### End-to-End Tests

**`cub.bats`** (20+ tests)
- `cub-init` project scaffolding
- Main `cub` script execution
- Task selection logic
- Priority ordering
- Prompt generation
- Progress tracking
- Completion detection
- Flag handling (--debug, --once, --status, --ready)
- Backend selection
- Error recovery

## Test Helpers

**`test_helper.bash`**
- Common setup/teardown functions
- Fixture management
- Command mocking utilities
- JSON assertion helpers
- Sample PRD generators

**`fixtures/`**
- `valid_prd.json` - Valid project with multiple tasks
- `missing_tasks.json` - Missing tasks array
- `missing_fields.json` - Tasks with missing required fields
- `duplicate_ids.json` - Duplicate task IDs
- `bad_dependency.json` - Invalid dependency reference

## Running Tests

### All Tests
```bash
bats tests/
```

### Specific Test File
```bash
bats tests/tasks.bats
bats tests/harness.bats
bats tests/error_handling.bats
bats tests/integration.bats
bats tests/cub.bats
```

### Verbose Output
```bash
bats --verbose-run tests/
```

### TAP Output (for CI)
```bash
bats --tap tests/
```

### Count Tests
```bash
bats tests/ --count
```

### Run Specific Test
```bash
bats tests/tasks.bats --filter "validate_prd succeeds"
```

## CI Integration

Tests run automatically on:
- Push to `main` branch
- Pull requests

See `.github/workflows/test.yml` for CI configuration.

### Platforms Tested
- Ubuntu (latest)
- macOS (latest)

## Test Philosophy

### Unit Tests
- Test individual functions in isolation
- Mock external dependencies
- Fast execution (< 1 second per test)
- No network calls
- Deterministic results

### Integration Tests
- Test actual harness invocations
- Gracefully skip if harness not installed
- Handle authentication/network errors
- Test real-world scenarios

### Error Handling
- Verify graceful degradation
- Test edge cases and boundary conditions
- Ensure errors don't crash the system
- Validate error messages

### End-to-End
- Test complete workflows
- Minimal mocking
- Verify user-facing features
- Test CLI flags and options

## Writing New Tests

### Test Template
```bash
@test "description of what is being tested" {
    # Setup
    setup_test_dir
    create_sample_prd

    # Execute
    run json_get_ready_tasks "prd.json"

    # Assert
    [ "$status" -eq 0 ]
    [[ "$output" == *"expected"* ]]
}
```

### Best Practices

1. **Use descriptive test names** - Test names should clearly state what is being tested
2. **One assertion per test** - Keep tests focused on a single behavior
3. **Setup and teardown** - Always use `setup_test_dir` and `teardown_test_dir`
4. **Use fixtures** - Reuse fixture files for common test data
5. **Test error cases** - Don't just test happy paths
6. **Skip when appropriate** - Use `skip` for tests requiring specific setup
7. **Assert status codes** - Always check `[ "$status" -eq 0 ]` or `[ "$status" -ne 0 ]`
8. **Use helper functions** - Leverage `test_helper.bash` utilities

### Example: Testing a New Function

```bash
# In lib/tasks.sh
get_task_priority() {
    local prd="$1"
    local task_id="$2"
    jq -r --arg id "$task_id" '.tasks[] | select(.id == $id) | .priority // "P2"' "$prd"
}
```

```bash
# In tests/tasks.bats
@test "get_task_priority returns task priority" {
    create_sample_prd
    run get_task_priority "prd.json" "test-0001"
    [ "$status" -eq 0 ]
    [ "$output" = "P2" ]
}

@test "get_task_priority returns default for missing priority" {
    cat > prd.json << 'EOF'
{"prefix": "test", "tasks": [{"id": "t1", "title": "Task", "status": "open"}]}
EOF
    run get_task_priority "prd.json" "t1"
    [ "$output" = "P2" ]
}
```

## Debugging Failed Tests

### Run Single Test with Verbose
```bash
bats --verbose-run tests/tasks.bats --filter "test name"
```

### Add Debug Output
```bash
@test "my test" {
    echo "Debug: variable value = $my_var" >&3
    run my_function
    echo "Debug: output = $output" >&3
}
```

### Check Test Directory
```bash
@test "my test" {
    setup_test_dir
    echo "Test dir: $TEST_DIR" >&3
    ls -la >&3
    # ... rest of test
}
```

## Coverage Goals

- **Functions**: 80%+ of library functions tested
- **Error paths**: All error conditions have tests
- **Integration**: All harnesses have basic integration tests
- **CLI**: All flags and commands tested

## Dependencies

Required for running tests:
- `bats-core` (1.13.0+)
- `jq` (JSON processor)
- `bash` (3.2+)

Optional for integration tests:
- Claude Code CLI (`claude`)
- OpenAI Codex CLI (`codex`)

## Contributing

When adding new features:
1. Write tests first (TDD approach preferred)
2. Ensure all existing tests pass
3. Add integration tests for new harnesses
4. Update this README if adding new test files
5. Run full suite before submitting PR

## Test Maintenance

- Review and update fixtures quarterly
- Remove obsolete tests when removing features
- Keep test execution time under 2 minutes total
- Update integration tests when harness APIs change
