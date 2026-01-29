"""
Tests for doctor command.

Tests the DiagnosticResult model and data collection functions.
"""



from cub.cli.doctor import (
    DiagnosticResult,
    collect_environment_checks,
)


def test_diagnostic_result_model() -> None:
    """Test DiagnosticResult model."""
    result = DiagnosticResult(
        category="Environment",
        name="git",
        status="pass",
        message="git 2.39.0",
    )

    assert result.category == "Environment"
    assert result.name == "git"
    assert result.status == "pass"
    assert result.message == "git 2.39.0"
    assert result.details == []
    assert result.fix_command is None


def test_diagnostic_result_with_details() -> None:
    """Test DiagnosticResult with details and fix_command."""
    result = DiagnosticResult(
        category="Task State",
        name="Stale Epics",
        status="warn",
        message="Found 2 stale epics",
        details=["epic-1", "epic-2"],
        fix_command="cub doctor --fix",
    )

    assert result.details == ["epic-1", "epic-2"]
    assert result.fix_command == "cub doctor --fix"


def test_collect_environment_checks() -> None:
    """Test collect_environment_checks returns list of results."""
    results = collect_environment_checks()

    assert isinstance(results, list)
    assert len(results) > 0

    # Should have at least git, harness, and beads checks
    categories = [r.category for r in results]
    names = [r.name for r in results]

    assert "Environment" in categories
    assert "git" in names

    # All results should have required fields
    for result in results:
        assert result.category
        assert result.name
        assert result.status in ("pass", "fail", "warn", "info")
        assert result.message


def test_collect_environment_checks_git_status() -> None:
    """Test that git check returns expected status."""
    results = collect_environment_checks()

    git_check = next((r for r in results if r.name == "git"), None)
    assert git_check is not None

    # git should be available (pass) or missing (fail)
    assert git_check.status in ("pass", "fail")

    if git_check.status == "fail":
        assert git_check.fix_command is not None


def test_collect_environment_checks_harness_status() -> None:
    """Test that AI harness check returns expected status."""
    results = collect_environment_checks()

    harness_check = next((r for r in results if r.name == "AI Harness"), None)
    assert harness_check is not None

    # Harness should be available (pass) or missing (fail)
    assert harness_check.status in ("pass", "fail")

    if harness_check.status == "pass":
        # Should have details about which harness was found
        assert len(harness_check.details) > 0


def test_collect_environment_checks_beads_optional() -> None:
    """Test that beads check is marked as optional (info)."""
    results = collect_environment_checks()

    beads_check = next((r for r in results if r.name == "beads (bd)"), None)
    assert beads_check is not None

    # Beads is optional, so status should be info
    assert beads_check.status == "info"
