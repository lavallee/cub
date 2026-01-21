"""
Tests for the cub plan CLI command.

The plan command provides a three-phase workflow:
- orient: Research and understand the problem space
- architect: Design the solution architecture
- itemize: Break down into actionable tasks
"""

from typer.testing import CliRunner

from cub.cli import app

runner = CliRunner()


class TestPlanCommandStructure:
    """Test that plan command has the correct structure."""

    def test_plan_requires_subcommand(self) -> None:
        """Test that 'cub plan' without subcommand shows help."""
        result = runner.invoke(app, ["plan"])
        # no_args_is_help=True returns exit code 2
        assert result.exit_code == 2
        assert "orient" in result.output
        assert "architect" in result.output
        assert "itemize" in result.output

    def test_plan_help_shows_subcommands(self) -> None:
        """Test that 'cub plan --help' shows all subcommands."""
        result = runner.invoke(app, ["plan", "--help"])
        assert result.exit_code == 0
        assert "orient" in result.output
        assert "architect" in result.output
        assert "itemize" in result.output
        # Check help text descriptions are present
        assert "Research" in result.output or "problem space" in result.output
        assert "Design" in result.output or "architecture" in result.output
        assert "Break down" in result.output or "tasks" in result.output


class TestPlanOrientSubcommand:
    """Test the 'cub plan orient' subcommand."""

    def test_orient_help(self) -> None:
        """Test that orient subcommand shows help."""
        result = runner.invoke(app, ["plan", "orient", "--help"])
        assert result.exit_code == 0
        assert "orient" in result.output.lower() or "research" in result.output.lower()
        # Should show spec argument
        assert "spec" in result.output.lower()

    def test_orient_requires_spec(self) -> None:
        """Test that orient without spec shows appropriate message."""
        result = runner.invoke(app, ["plan", "orient"])
        assert result.exit_code == 1
        # Now implemented - requires a spec
        assert "no spec provided" in result.output.lower()

    def test_orient_with_nonexistent_spec(self) -> None:
        """Test that orient with non-existent spec shows error."""
        result = runner.invoke(app, ["plan", "orient", "spec-abc123"])
        assert result.exit_code == 1
        # Should report spec not found
        assert "spec not found" in result.output.lower()

    def test_orient_verbose_flag(self) -> None:
        """Test that orient accepts --verbose flag."""
        result = runner.invoke(app, ["plan", "orient", "-v"])
        assert result.exit_code == 1
        # Verbose mode should be accepted (still errors without spec)


class TestPlanArchitectSubcommand:
    """Test the 'cub plan architect' subcommand."""

    def test_architect_help(self) -> None:
        """Test that architect subcommand shows help."""
        result = runner.invoke(app, ["plan", "architect", "--help"])
        assert result.exit_code == 0
        assert "architect" in result.output.lower() or "design" in result.output.lower()

    def test_architect_requires_plan(self) -> None:
        """Test that architect without existing plan shows appropriate error."""
        # Use isolated filesystem to avoid picking up existing plans
        with runner.isolated_filesystem():
            result = runner.invoke(app, ["plan", "architect"])
            # Now implemented - requires existing plan
            assert result.exit_code == 1
            assert "no plans found" in result.output.lower()

    def test_architect_with_nonexistent_plan(self) -> None:
        """Test that architect with non-existent plan shows error."""
        result = runner.invoke(app, ["plan", "architect", "spec-abc123"])
        assert result.exit_code == 1
        assert "plan not found" in result.output.lower()


class TestPlanItemizeSubcommand:
    """Test the 'cub plan itemize' subcommand."""

    def test_itemize_help(self) -> None:
        """Test that itemize subcommand shows help."""
        result = runner.invoke(app, ["plan", "itemize", "--help"])
        assert result.exit_code == 0
        # Should mention itemize, tasks, or breakdown
        output_lower = result.output.lower()
        assert "itemize" in output_lower or "task" in output_lower or "break" in output_lower

    def test_itemize_requires_plan(self) -> None:
        """Test that itemize without existing plan shows appropriate error."""
        # Use isolated filesystem to avoid picking up existing plans
        with runner.isolated_filesystem():
            result = runner.invoke(app, ["plan", "itemize"])
            # Now implemented - requires existing plan
            assert result.exit_code == 1
            assert "no plans found" in result.output.lower()

    def test_itemize_with_nonexistent_plan(self) -> None:
        """Test that itemize with non-existent plan shows error."""
        result = runner.invoke(app, ["plan", "itemize", "spec-abc123"])
        assert result.exit_code == 1
        assert "plan not found" in result.output.lower()


class TestPlanCommandIntegration:
    """Integration tests for plan command."""

    def test_plan_in_main_help(self) -> None:
        """Test that plan command appears in main cub help."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "plan" in result.output

    def test_plan_subcommands_consistent_interface(self) -> None:
        """Test that all plan subcommands have consistent interface."""
        subcommands = ["orient", "architect", "itemize"]
        for subcmd in subcommands:
            result = runner.invoke(app, ["plan", subcmd, "--help"])
            assert result.exit_code == 0, f"Failed for {subcmd}"
            # All should accept spec argument
            assert "spec" in result.output.lower(), f"No spec arg for {subcmd}"
            # All should accept verbose flag
            assert "--verbose" in result.output or "-v" in result.output, (
                f"No verbose flag for {subcmd}"
            )
