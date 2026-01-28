"""
Tests for map renderer with token budgeting.

Tests cover:
- Token estimation using word count heuristic
- Budget allocation (structure 40%, symbols 60%, ledger 10%)
- Section rendering with and without budget constraints
- Graceful handling of empty data
- Ledger stats integration
"""

from unittest.mock import MagicMock

import pytest

from cub.core.ledger.models import LedgerStats
from cub.core.ledger.reader import LedgerReader
from cub.core.map.code_intel import RankedSymbol
from cub.core.map.models import (
    BuildCommand,
    DirectoryNode,
    DirectoryTree,
    KeyFile,
    ModuleInfo,
    ProjectStructure,
    TechStack,
)
from cub.core.map.renderer import estimate_tokens, render_map

# ==============================================================================
# Token Estimation Tests
# ==============================================================================


class TestEstimateTokens:
    """Test token estimation heuristic."""

    def test_empty_string(self):
        """Test empty string returns 0 tokens."""
        assert estimate_tokens("") == 0

    def test_single_word(self):
        """Test single word estimation."""
        # "hello" = 1 word → 1 / 0.75 ≈ 1.33 → 2 tokens
        assert estimate_tokens("hello") >= 1

    def test_multiple_words(self):
        """Test multiple words estimation."""
        # 10 words → 10 / 0.75 ≈ 13.33 → 14 tokens
        text = "one two three four five six seven eight nine ten"
        tokens = estimate_tokens(text)
        assert tokens >= 10  # Should be ~13-14

    def test_with_punctuation(self):
        """Test that punctuation doesn't break word counting."""
        text = "Hello, world! This is a test."
        tokens = estimate_tokens(text)
        # 6 words → 6 / 0.75 = 8 tokens
        assert tokens >= 6

    def test_with_newlines(self):
        """Test multiline text."""
        text = "Line one\nLine two\nLine three"
        tokens = estimate_tokens(text)
        # 6 words → 8 tokens
        assert tokens >= 6

    def test_with_code(self):
        """Test code snippet estimation."""
        code = """
        def hello_world():
            print("Hello, world!")
            return 42
        """
        tokens = estimate_tokens(code)
        # Should estimate based on word count
        assert tokens > 0


# ==============================================================================
# Render Map Tests
# ==============================================================================


class TestRenderMap:
    """Test full map rendering."""

    @pytest.fixture
    def minimal_structure(self) -> ProjectStructure:
        """Minimal project structure for testing."""
        return ProjectStructure(
            project_dir="/test/project",
            tech_stacks=[TechStack.PYTHON],
            build_commands=[
                BuildCommand(name="test", command="pytest", source="Makefile")
            ],
            key_files=[
                KeyFile(path="README.md", type="readme", description="Project README")
            ],
            modules=[
                ModuleInfo(
                    name="myapp",
                    path="src/myapp",
                    entry_file="__init__.py",
                    file_count=10,
                )
            ],
            directory_tree=DirectoryTree(
                root=DirectoryNode(
                    name="project",
                    path="/test/project",
                    is_file=False,
                    children=[
                        DirectoryNode(
                            name="README.md",
                            path="/test/project/README.md",
                            is_file=True,
                        ),
                        DirectoryNode(
                            name="src",
                            path="/test/project/src",
                            is_file=False,
                            children=[
                                DirectoryNode(
                                    name="main.py",
                                    path="/test/project/src/main.py",
                                    is_file=True,
                                )
                            ],
                        ),
                    ],
                ),
                max_depth=4,
                total_files=2,
                total_dirs=1,
            ),
        )

    @pytest.fixture
    def ranked_symbols(self) -> list[RankedSymbol]:
        """Sample ranked symbols."""
        return [
            RankedSymbol(
                rel_path="src/main.py",
                name="main",
                kind="def",
                line=10,
                score=0.95,
            ),
            RankedSymbol(
                rel_path="src/main.py",
                name="helper",
                kind="def",
                line=20,
                score=0.75,
            ),
            RankedSymbol(
                rel_path="src/utils.py",
                name="util_func",
                kind="def",
                line=5,
                score=0.60,
            ),
        ]

    def test_render_basic_map(self, minimal_structure, ranked_symbols):
        """Test basic map rendering without budget constraints."""
        result = render_map(
            structure=minimal_structure,
            ranked_symbols=ranked_symbols,
            token_budget=10000,  # Large budget
        )

        # Check all sections are present
        assert "# Project Map: project" in result
        assert "## Tech Stacks" in result
        assert "- python" in result
        assert "## Build Commands" in result
        assert "pytest" in result
        assert "## Key Files" in result
        assert "README.md" in result
        assert "## Modules" in result
        assert "myapp" in result
        assert "## Directory Structure" in result
        assert "## Ranked Symbols" in result
        assert "main" in result
        assert "helper" in result
        assert "util_func" in result

    def test_render_with_tight_budget(self, minimal_structure, ranked_symbols):
        """Test rendering with very tight token budget."""
        result = render_map(
            structure=minimal_structure,
            ranked_symbols=ranked_symbols,
            token_budget=500,  # Very tight budget
        )

        # Should still have basic structure
        assert "# Project Map" in result
        # But symbols or tree might be truncated
        assert "## Ranked Symbols" in result or "## Directory Structure" in result

    def test_render_with_empty_symbols(self, minimal_structure):
        """Test rendering with empty symbols list."""
        result = render_map(
            structure=minimal_structure,
            ranked_symbols=[],
            token_budget=5000,
        )

        # All structure sections should be present
        assert "# Project Map" in result
        assert "## Tech Stacks" in result
        # Ranked Symbols section should not be present when empty
        assert "## Ranked Symbols" not in result

    def test_render_with_empty_structure(self, ranked_symbols):
        """Test rendering with minimal structure."""
        empty_structure = ProjectStructure(
            project_dir="/test/empty",
            tech_stacks=[],
            build_commands=[],
            key_files=[],
            modules=[],
            directory_tree=None,
        )

        result = render_map(
            structure=empty_structure,
            ranked_symbols=ranked_symbols,
            token_budget=5000,
        )

        # Should have header and symbols
        assert "# Project Map: empty" in result
        assert "## Ranked Symbols" in result
        # Empty sections should not appear
        assert "## Tech Stacks" not in result
        assert "## Build Commands" not in result

    def test_budget_respects_limits(self, minimal_structure, ranked_symbols):
        """Test that rendered content respects token budget."""
        budget = 1000
        result = render_map(
            structure=minimal_structure,
            ranked_symbols=ranked_symbols,
            token_budget=budget,
        )

        # Estimate tokens in result
        actual_tokens = estimate_tokens(result)

        # Should be within budget (allow 10% margin for rounding)
        assert actual_tokens <= budget * 1.1

    def test_section_ordering(self, minimal_structure, ranked_symbols):
        """Test that sections appear in correct order."""
        result = render_map(
            structure=minimal_structure,
            ranked_symbols=ranked_symbols,
            token_budget=10000,
        )

        # Find section positions
        sections = [
            "# Project Map",
            "## Tech Stacks",
            "## Build Commands",
            "## Key Files",
            "## Modules",
            "## Directory Structure",
            "## Ranked Symbols",
        ]

        positions = [result.find(section) for section in sections]

        # All sections should be found
        assert all(pos != -1 for pos in positions)

        # Positions should be in ascending order
        assert positions == sorted(positions)

    def test_symbols_grouped_by_file(self, minimal_structure, ranked_symbols):
        """Test that symbols are grouped by file path."""
        result = render_map(
            structure=minimal_structure,
            ranked_symbols=ranked_symbols,
            token_budget=10000,
        )

        # Should have file headers
        assert "### src/main.py" in result
        assert "### src/utils.py" in result

        # Symbols should appear after their file header
        main_pos = result.find("### src/main.py")
        helper_pos = result.find("**helper**")
        utils_pos = result.find("### src/utils.py")
        util_func_pos = result.find("**util_func**")

        assert main_pos < helper_pos
        assert utils_pos < util_func_pos


# ==============================================================================
# Ledger Stats Tests
# ==============================================================================


class TestLedgerStatsRendering:
    """Test ledger statistics rendering."""

    @pytest.fixture
    def mock_ledger_reader(self) -> LedgerReader:
        """Mock ledger reader with sample stats."""
        mock_reader = MagicMock(spec=LedgerReader)
        mock_reader.exists.return_value = True
        mock_reader.get_stats.return_value = LedgerStats(
            total_tasks=50,
            total_epics=5,
            total_cost_usd=12.50,
            average_cost_per_task=0.25,
            min_cost_usd=0.05,
            max_cost_usd=2.00,
            total_tokens=500000,
            average_tokens_per_task=10000,
            total_duration_seconds=3600,
        )
        return mock_reader

    @pytest.fixture
    def minimal_structure(self) -> ProjectStructure:
        """Minimal project structure."""
        return ProjectStructure(
            project_dir="/test/project",
            tech_stacks=[],
            build_commands=[],
            key_files=[],
            modules=[],
            directory_tree=None,
        )

    def test_render_with_ledger_stats(self, minimal_structure, mock_ledger_reader):
        """Test rendering with ledger statistics enabled."""
        result = render_map(
            structure=minimal_structure,
            ranked_symbols=[],
            token_budget=5000,
            include_ledger_stats=True,
            ledger_reader=mock_ledger_reader,
        )

        # Should include ledger stats section
        assert "## Ledger Statistics" in result
        assert "**Total Tasks**: 50" in result
        assert "**Total Cost**: $12.50" in result
        assert "**Total Tokens**: 500,000" in result
        assert "**Average Cost/Task**: $0.25" in result

    def test_render_without_ledger_stats(self, minimal_structure):
        """Test rendering without ledger statistics."""
        result = render_map(
            structure=minimal_structure,
            ranked_symbols=[],
            token_budget=5000,
            include_ledger_stats=False,
        )

        # Should not include ledger stats section
        assert "## Ledger Statistics" not in result

    def test_ledger_stats_requires_reader(self, minimal_structure):
        """Test that ledger stats requires a reader."""
        with pytest.raises(ValueError, match="ledger_reader is required"):
            render_map(
                structure=minimal_structure,
                ranked_symbols=[],
                token_budget=5000,
                include_ledger_stats=True,
                ledger_reader=None,
            )

    def test_ledger_stats_when_ledger_missing(self, minimal_structure):
        """Test ledger stats section when ledger doesn't exist."""
        mock_reader = MagicMock(spec=LedgerReader)
        mock_reader.exists.return_value = False

        result = render_map(
            structure=minimal_structure,
            ranked_symbols=[],
            token_budget=5000,
            include_ledger_stats=True,
            ledger_reader=mock_reader,
        )

        # Should not include ledger stats section when ledger doesn't exist
        assert "## Ledger Statistics" not in result


# ==============================================================================
# Directory Tree Rendering Tests
# ==============================================================================


class TestDirectoryTreeRendering:
    """Test directory tree rendering."""

    def test_render_simple_tree(self):
        """Test rendering a simple directory tree."""
        tree = DirectoryTree(
            root=DirectoryNode(
                name="root",
                path="/root",
                is_file=False,
                children=[
                    DirectoryNode(name="file1.txt", path="/root/file1.txt", is_file=True),
                    DirectoryNode(name="file2.txt", path="/root/file2.txt", is_file=True),
                ],
            ),
            max_depth=2,
            total_files=2,
            total_dirs=0,
        )

        structure = ProjectStructure(
            project_dir="/root",
            tech_stacks=[],
            build_commands=[],
            key_files=[],
            modules=[],
            directory_tree=tree,
        )

        result = render_map(
            structure=structure,
            ranked_symbols=[],
            token_budget=5000,
        )

        assert "## Directory Structure" in result
        assert "root/" in result
        assert "file1.txt" in result
        assert "file2.txt" in result
        # Check tree drawing characters
        assert "├──" in result or "└──" in result

    def test_render_nested_tree(self):
        """Test rendering a nested directory tree."""
        tree = DirectoryTree(
            root=DirectoryNode(
                name="root",
                path="/root",
                is_file=False,
                children=[
                    DirectoryNode(
                        name="src",
                        path="/root/src",
                        is_file=False,
                        children=[
                            DirectoryNode(
                                name="main.py",
                                path="/root/src/main.py",
                                is_file=True,
                            )
                        ],
                    ),
                    DirectoryNode(name="README.md", path="/root/README.md", is_file=True),
                ],
            ),
            max_depth=3,
            total_files=2,
            total_dirs=1,
        )

        structure = ProjectStructure(
            project_dir="/root",
            tech_stacks=[],
            build_commands=[],
            key_files=[],
            modules=[],
            directory_tree=tree,
        )

        result = render_map(
            structure=structure,
            ranked_symbols=[],
            token_budget=5000,
        )

        assert "src/" in result
        assert "main.py" in result
        assert "README.md" in result

    def test_tree_truncation_with_tight_budget(self):
        """Test tree truncation when budget is tight."""
        # Create a large tree
        children = [
            DirectoryNode(name=f"file{i}.txt", path=f"/root/file{i}.txt", is_file=True)
            for i in range(100)
        ]
        tree = DirectoryTree(
            root=DirectoryNode(
                name="root",
                path="/root",
                is_file=False,
                children=children,
            ),
            max_depth=2,
            total_files=100,
            total_dirs=0,
        )

        structure = ProjectStructure(
            project_dir="/root",
            tech_stacks=[],
            build_commands=[],
            key_files=[],
            modules=[],
            directory_tree=tree,
        )

        result = render_map(
            structure=structure,
            ranked_symbols=[],
            token_budget=200,  # Very tight budget
        )

        # Should have truncation message
        assert "... (truncated to fit budget)" in result


# ==============================================================================
# Symbol Budget Tests
# ==============================================================================


class TestSymbolBudgeting:
    """Test symbol rendering with budget constraints."""

    def test_many_symbols_with_limited_budget(self):
        """Test that many symbols are truncated to fit budget."""
        # Create 100 symbols
        symbols = [
            RankedSymbol(
                rel_path=f"file{i // 10}.py",
                name=f"symbol_{i}",
                kind="def",
                line=i,
                score=1.0 - (i * 0.01),
            )
            for i in range(100)
        ]

        structure = ProjectStructure(
            project_dir="/test",
            tech_stacks=[],
            build_commands=[],
            key_files=[],
            modules=[],
            directory_tree=None,
        )

        result = render_map(
            structure=structure,
            ranked_symbols=symbols,
            token_budget=500,  # Limited budget
        )

        # Should have truncation message
        assert "more symbols omitted" in result

    def test_symbols_respect_ranking(self):
        """Test that higher-ranked symbols appear first."""
        symbols = [
            RankedSymbol(
                rel_path="file.py",
                name="low_score",
                kind="def",
                line=1,
                score=0.1,
            ),
            RankedSymbol(
                rel_path="file.py",
                name="high_score",
                kind="def",
                line=2,
                score=0.9,
            ),
            RankedSymbol(
                rel_path="file.py",
                name="mid_score",
                kind="def",
                line=3,
                score=0.5,
            ),
        ]

        # Sort by score descending (as they should come in)
        symbols_sorted = sorted(symbols, key=lambda s: s.score, reverse=True)

        structure = ProjectStructure(
            project_dir="/test",
            tech_stacks=[],
            build_commands=[],
            key_files=[],
            modules=[],
            directory_tree=None,
        )

        result = render_map(
            structure=structure,
            ranked_symbols=symbols_sorted,
            token_budget=5000,
        )

        # Find positions
        high_pos = result.find("high_score")
        mid_pos = result.find("mid_score")
        low_pos = result.find("low_score")

        # Should appear in score order
        assert high_pos < mid_pos < low_pos
