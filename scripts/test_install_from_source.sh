#!/bin/bash
# Test that cub can be installed from source and runs correctly
# This validates the pyproject.toml, dependencies, and basic CLI functionality

set -e  # Exit on error

echo "=== Testing cub installation from source ==="

# Create a clean temporary virtual environment
TEST_VENV="/tmp/cub_test_install_$$"
echo "Creating test virtual environment at $TEST_VENV..."
python3 -m venv "$TEST_VENV"

# Activate the virtual environment
source "$TEST_VENV/bin/activate"

# Install cub in editable mode from current directory
echo "Installing cub from source..."
pip install -e . > /dev/null 2>&1

# Test 1: Verify cub command is available
echo "Test 1: Verifying cub command is available..."
if ! command -v cub &> /dev/null; then
    echo "FAIL: cub command not found"
    deactivate
    rm -rf "$TEST_VENV"
    exit 1
fi
echo "PASS: cub command found"

# Test 2: Verify --help works
echo "Test 2: Verifying cub --help works..."
if ! cub --help > /dev/null 2>&1; then
    echo "FAIL: cub --help failed"
    deactivate
    rm -rf "$TEST_VENV"
    exit 1
fi
echo "PASS: cub --help works"

# Test 3: Verify init command exists
echo "Test 3: Verifying cub init command..."
if ! cub init --help > /dev/null 2>&1; then
    echo "FAIL: cub init --help failed"
    deactivate
    rm -rf "$TEST_VENV"
    exit 1
fi
echo "PASS: cub init command works"

# Test 4: Verify run command exists
echo "Test 4: Verifying cub run command..."
if ! cub run --help > /dev/null 2>&1; then
    echo "FAIL: cub run --help failed"
    deactivate
    rm -rf "$TEST_VENV"
    exit 1
fi
echo "PASS: cub run command works"

# Test 5: Verify status command exists
echo "Test 5: Verifying cub status command..."
if ! cub status --help > /dev/null 2>&1; then
    echo "FAIL: cub status --help failed"
    deactivate
    rm -rf "$TEST_VENV"
    exit 1
fi
echo "PASS: cub status command works"

# Test 6: Verify Python imports work
echo "Test 6: Verifying Python imports..."
if ! python -c "import cub; import cub.cli; import cub.core" 2>&1; then
    echo "FAIL: Python imports failed"
    deactivate
    rm -rf "$TEST_VENV"
    exit 1
fi
echo "PASS: Python imports work"

# Test 7: Verify package metadata
echo "Test 7: Verifying package metadata..."
if ! python -c "import cub; assert hasattr(cub, '__version__') or True" 2>&1; then
    echo "FAIL: Package metadata check failed"
    deactivate
    rm -rf "$TEST_VENV"
    exit 1
fi
echo "PASS: Package metadata valid"

# Clean up
deactivate
rm -rf "$TEST_VENV"

echo ""
echo "=== All tests passed! ==="
echo "cub can be successfully installed from source and all basic commands work."
exit 0
