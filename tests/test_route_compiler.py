"""
Tests for route compiler and normalization.

Tests cover:
- Command normalization (task IDs, paths, messages, numbers, URLs)
- Route compilation (parsing JSONL, aggregating, filtering)
- Markdown rendering
"""

import json
from pathlib import Path

import pytest

from cub.core.routes.compiler import (
    compile_and_write_routes,
    compile_routes,
    normalize_command,
    render_learned_routes,
)


class TestNormalizeCommand:
    """Test command normalization patterns."""

    def test_normalize_task_id_basic(self) -> None:
        """Normalize basic task ID format (cub-123)."""
        assert normalize_command("cub run --task cub-123") == "cub run --task <TASK_ID>"

    def test_normalize_task_id_with_dots(self) -> None:
        """Normalize task ID with dots (cub-a3r.2)."""
        assert normalize_command("bd close cub-a3r.2") == "bd close <TASK_ID>"

    def test_normalize_task_id_uppercase(self) -> None:
        """Normalize uppercase task IDs (TASK-456)."""
        assert normalize_command("bd show TASK-456") == "bd show <TASK_ID>"

    def test_normalize_quoted_messages_double(self) -> None:
        """Normalize double-quoted strings."""
        cmd = 'git commit -m "Fix authentication bug"'
        expected = "git commit -m <MESSAGE>"
        assert normalize_command(cmd) == expected

    def test_normalize_quoted_messages_single(self) -> None:
        """Normalize single-quoted strings."""
        cmd = "bd close cub-123 -r 'Task completed successfully'"
        expected = "bd close <TASK_ID> -r <MESSAGE>"
        assert normalize_command(cmd) == expected

    def test_normalize_file_paths_absolute(self) -> None:
        """Normalize absolute file paths."""
        cmd = "cat /home/user/project/src/main.py"
        expected = "cat <PATH>"
        assert normalize_command(cmd) == expected

    def test_normalize_file_paths_relative(self) -> None:
        """Normalize relative file paths."""
        cmd = "pytest tests/test_compiler.py"
        expected = "pytest <PATH>"
        assert normalize_command(cmd) == expected

    def test_normalize_file_paths_windows(self) -> None:
        """Normalize Windows-style paths."""
        cmd = r"type C:\Users\dev\project\README.md"
        expected = "type <PATH>"
        assert normalize_command(cmd) == expected

    def test_normalize_numbers_standalone(self) -> None:
        """Normalize standalone numbers."""
        cmd = "bd show 123"
        expected = "bd show <NUM>"
        assert normalize_command(cmd) == expected

    def test_preserve_flags_with_numbers(self) -> None:
        """Preserve flags with numeric values."""
        # This is a limitation - we can't perfectly distinguish flags from args
        # But the pattern should still be recognizable
        cmd = "pytest --timeout 30"
        # The number gets normalized but the flag is preserved
        normalized = normalize_command(cmd)
        assert "pytest" in normalized
        assert "--timeout" in normalized

    def test_normalize_urls(self) -> None:
        """Normalize URLs."""
        cmd = "curl https://api.example.com/v1/users"
        expected = "curl <URL>"
        assert normalize_command(cmd) == expected

    def test_normalize_complex_command(self) -> None:
        """Normalize complex command with multiple patterns."""
        cmd = 'git commit -m "task(cub-a3r.2): Build route compiler" && git push'
        normalized = normalize_command(cmd)
        # The quoted string gets replaced first, so task ID inside it is also replaced
        assert "<MESSAGE>" in normalized
        assert "git commit" in normalized
        assert "git push" in normalized

    def test_normalize_preserves_structure(self) -> None:
        """Ensure basic command structure is preserved."""
        cmd = "cub run --once --task cub-123"
        normalized = normalize_command(cmd)
        assert "cub run" in normalized
        assert "--once" in normalized
        assert "--task" in normalized
        assert "<TASK_ID>" in normalized

    def test_normalize_empty_command(self) -> None:
        """Handle empty command."""
        assert normalize_command("") == ""
        assert normalize_command("   ") == ""

    def test_normalize_whitespace(self) -> None:
        """Normalize multiple spaces to single space."""
        cmd = "cub    run    --task    cub-123"
        normalized = normalize_command(cmd)
        # Should not have multiple consecutive spaces
        assert "    " not in normalized
        assert "cub run --task <TASK_ID>" == normalized


class TestCompileRoutes:
    """Test route compilation from JSONL logs."""

    def test_compile_routes_basic(self, tmp_path: Path) -> None:
        """Compile routes from basic JSONL log."""
        log_file = tmp_path / "route-log.jsonl"

        # Create sample log
        commands = [
            "cub run --task cub-123",
            "cub run --task cub-456",
            "cub run --task cub-789",
            "bd show cub-123",
            "bd show cub-456",
            "git status",
        ]

        with open(log_file, 'w') as f:
            for cmd in commands:
                f.write(json.dumps({"timestamp": "2024-01-01T00:00:00Z", "command": cmd}) + "\n")

        routes = compile_routes(log_file, min_frequency=2)

        # Should have 2 routes (cub run x3, bd show x2)
        # git status appears only once, below threshold
        assert len(routes) == 2

        # Check normalized commands and counts
        route_dict = dict(routes)
        assert route_dict["cub run --task <TASK_ID>"] == 3
        assert route_dict["bd show <TASK_ID>"] == 2

    def test_compile_routes_filters_low_frequency(self, tmp_path: Path) -> None:
        """Filter out commands below frequency threshold."""
        log_file = tmp_path / "route-log.jsonl"

        commands = [
            "cub run --task cub-123",
            "cub run --task cub-456",
            "cub run --task cub-789",
            "bd show cub-123",
            "git status",
            "git diff",
        ]

        with open(log_file, 'w') as f:
            for cmd in commands:
                f.write(json.dumps({"command": cmd}) + "\n")

        routes = compile_routes(log_file, min_frequency=3)

        # Only "cub run --task <TASK_ID>" should remain (appears 3 times)
        assert len(routes) == 1
        assert routes[0][0] == "cub run --task <TASK_ID>"
        assert routes[0][1] == 3

    def test_compile_routes_sorts_by_frequency(self, tmp_path: Path) -> None:
        """Routes should be sorted by frequency descending."""
        log_file = tmp_path / "route-log.jsonl"

        # Create commands with different frequencies
        commands = (
            ["git status"] * 10
            + ["cub run --task cub-123"] * 5
            + ["bd show cub-456"] * 3
        )

        with open(log_file, 'w') as f:
            for cmd in commands:
                f.write(json.dumps({"command": cmd}) + "\n")

        routes = compile_routes(log_file, min_frequency=3)

        # Should be sorted: git status (10), cub run (5), bd show (3)
        assert len(routes) == 3
        assert routes[0] == ("git status", 10)
        assert routes[1] == ("cub run --task <TASK_ID>", 5)
        assert routes[2] == ("bd show <TASK_ID>", 3)

    def test_compile_routes_empty_log(self, tmp_path: Path) -> None:
        """Handle empty log file."""
        log_file = tmp_path / "route-log.jsonl"
        log_file.touch()

        routes = compile_routes(log_file, min_frequency=1)
        assert routes == []

    def test_compile_routes_malformed_json(self, tmp_path: Path) -> None:
        """Skip malformed JSON lines."""
        log_file = tmp_path / "route-log.jsonl"

        with open(log_file, 'w') as f:
            f.write('{"command": "git status"}\n')
            f.write('malformed json line\n')  # Should be skipped
            f.write('{"command": "git status"}\n')
            f.write('{"command": "git status"}\n')

        routes = compile_routes(log_file, min_frequency=3)

        # Should still get git status x3 (malformed line skipped)
        assert len(routes) == 1
        assert routes[0] == ("git status", 3)

    def test_compile_routes_missing_command_field(self, tmp_path: Path) -> None:
        """Skip entries without 'command' field."""
        log_file = tmp_path / "route-log.jsonl"

        with open(log_file, 'w') as f:
            f.write('{"command": "git status"}\n')
            f.write('{"timestamp": "2024-01-01T00:00:00Z"}\n')  # No command field
            f.write('{"command": "git status"}\n')
            f.write('{"command": "git status"}\n')

        routes = compile_routes(log_file, min_frequency=3)

        assert len(routes) == 1
        assert routes[0] == ("git status", 3)

    def test_compile_routes_file_not_found(self, tmp_path: Path) -> None:
        """Raise FileNotFoundError for missing log file."""
        log_file = tmp_path / "nonexistent.jsonl"

        with pytest.raises(FileNotFoundError, match="Route log file not found"):
            compile_routes(log_file)


class TestRenderLearnedRoutes:
    """Test markdown rendering of learned routes."""

    def test_render_learned_routes_basic(self) -> None:
        """Render basic markdown table."""
        routes = [
            ("cub run --task <TASK_ID>", 10),
            ("bd show <TASK_ID>", 5),
            ("git status", 3),
        ]

        markdown = render_learned_routes(routes)

        # Check structure
        assert "# Learned Routes" in markdown
        assert "| Command | Frequency |" in markdown
        assert "|---------|-----------|" in markdown

        # Check each route
        assert "| `cub run --task <TASK_ID>` | 10 |" in markdown
        assert "| `bd show <TASK_ID>` | 5 |" in markdown
        assert "| `git status` | 3 |" in markdown

    def test_render_learned_routes_empty(self) -> None:
        """Render message for empty routes."""
        routes: list[tuple[str, int]] = []
        markdown = render_learned_routes(routes)

        assert "# Learned Routes" in markdown
        assert "No routes found" in markdown

    def test_render_learned_routes_escapes_pipes(self) -> None:
        """Escape pipe characters in commands."""
        # Use an already-normalized command with pipe
        routes = [
            ("grep pattern file.txt | head -n 10", 5),
        ]

        markdown = render_learned_routes(routes)

        # Pipe should be escaped for markdown table
        assert "\\|" in markdown
        # The actual command is not normalized by render function, just escaped
        assert "\\|" in markdown


class TestCompileAndWriteRoutes:
    """Test end-to-end compilation and file writing."""

    def test_compile_and_write_routes(self, tmp_path: Path) -> None:
        """Compile routes and write to markdown file."""
        log_file = tmp_path / "route-log.jsonl"
        output_file = tmp_path / "learned-routes.md"

        # Create sample log
        commands = [
            "cub run --task cub-123",
            "cub run --task cub-456",
            "cub run --task cub-789",
            "bd show cub-123",
        ]

        with open(log_file, 'w') as f:
            for cmd in commands:
                f.write(json.dumps({"command": cmd}) + "\n")

        # Compile and write
        compile_and_write_routes(log_file, output_file, min_frequency=3)

        # Check output file exists
        assert output_file.exists()

        # Check content
        content = output_file.read_text()
        assert "# Learned Routes" in content
        assert "cub run --task <TASK_ID>" in content
        assert "| 3 |" in content

    def test_compile_and_write_routes_creates_parent_dir(self, tmp_path: Path) -> None:
        """Create parent directory if it doesn't exist."""
        log_file = tmp_path / "route-log.jsonl"
        output_file = tmp_path / "nested" / "dir" / "learned-routes.md"

        # Create sample log
        with open(log_file, 'w') as f:
            for i in range(3):
                f.write(json.dumps({"command": "git status"}) + "\n")

        # Compile and write (should create nested/dir/)
        compile_and_write_routes(log_file, output_file, min_frequency=3)

        assert output_file.exists()
        assert output_file.parent.exists()
