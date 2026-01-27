"""Tests for the argv preprocessor."""

from cub.cli.argv import preprocess_argv


class TestVersionRewrite:
    """Rule 1: --version / -V → version subcommand."""

    def test_double_dash_version(self) -> None:
        assert preprocess_argv(["--version"]) == ["version"]

    def test_short_version_flag(self) -> None:
        assert preprocess_argv(["-V"]) == ["version"]

    def test_version_flag_not_rewritten_after_subcommand(self) -> None:
        result = preprocess_argv(["run", "--version"])
        assert result[0] == "run"
        assert "--version" in result


class TestHelpRewrite:
    """Rule 2: help pseudo-command → --help."""

    def test_bare_help(self) -> None:
        assert preprocess_argv(["help"]) == ["--help"]

    def test_help_with_subcommand(self) -> None:
        assert preprocess_argv(["help", "run"]) == ["run", "--help"]

    def test_help_with_two_subcommands(self) -> None:
        assert preprocess_argv(["help", "task", "create"]) == [
            "task",
            "create",
            "--help",
        ]

    def test_help_ignores_third_subcommand(self) -> None:
        result = preprocess_argv(["help", "task", "create", "extra"])
        assert result == ["task", "create", "--help"]

    def test_help_help(self) -> None:
        assert preprocess_argv(["help", "help"]) == ["--help"]

    def test_help_ignores_flags(self) -> None:
        assert preprocess_argv(["help", "--debug"]) == ["--help"]

    def test_help_with_flag_and_subcommand(self) -> None:
        assert preprocess_argv(["help", "--debug", "run"]) == ["run", "--help"]

    def test_help_with_subcommand_then_flag(self) -> None:
        assert preprocess_argv(["help", "run", "--verbose"]) == ["run", "--help"]


class TestGlobalFlagHoisting:
    """Rule 3: global flags hoisted before the subcommand."""

    def test_debug_after_subcommand(self) -> None:
        assert preprocess_argv(["run", "--debug", "--once"]) == [
            "--debug",
            "run",
            "--once",
        ]

    def test_debug_already_first(self) -> None:
        assert preprocess_argv(["--debug", "run"]) == ["--debug", "run"]

    def test_debug_at_end(self) -> None:
        assert preprocess_argv(["branch", "cub-123", "--debug"]) == [
            "--debug",
            "branch",
            "cub-123",
        ]

    def test_no_global_flags(self) -> None:
        assert preprocess_argv(["run", "--once"]) == ["run", "--once"]

    def test_debug_not_duplicated(self) -> None:
        result = preprocess_argv(["--debug", "run", "--debug"])
        assert result.count("--debug") == 1
        assert result == ["--debug", "run"]


class TestEdgeCases:
    """Edge cases and passthrough behavior."""

    def test_empty_argv(self) -> None:
        assert preprocess_argv([]) == []

    def test_single_subcommand(self) -> None:
        assert preprocess_argv(["status"]) == ["status"]

    def test_normal_args_unchanged(self) -> None:
        argv = ["run", "--once", "--harness", "claude"]
        assert preprocess_argv(argv) == ["run", "--once", "--harness", "claude"]

    def test_version_flag_only_at_position_zero(self) -> None:
        """--version after a subcommand should not be rewritten."""
        result = preprocess_argv(["doctor", "--version"])
        assert "version" not in result or result[0] != "version"
