"""
Unit tests for test coverage reporting module.

Tests coverage report generation, parsing, and analysis.
"""

import pytest

from cub.audit.coverage import (
    CoverageFile,
    CoverageReport,
    UncoveredLine,
    format_coverage_report,
    get_uncovered_lines,
    identify_low_coverage,
    parse_coverage_report,
)


class TestCoverageFile:
    """Test CoverageFile model."""

    def test_coverage_file_creation(self):
        """Test creating a CoverageFile."""
        file = CoverageFile(
            path="src/cub/core/config.py",
            covered_lines=150,
            total_lines=180,
            percent_covered=83.3,
        )
        assert file.path == "src/cub/core/config.py"
        assert file.covered_lines == 150
        assert file.total_lines == 180
        assert file.percent_covered == 83.3

    def test_coverage_file_validation(self):
        """Test that CoverageFile validates numeric constraints."""
        # percent_covered must be 0-100
        with pytest.raises(ValueError):
            CoverageFile(
                path="test.py",
                covered_lines=10,
                total_lines=10,
                percent_covered=105.0,  # Invalid
            )

        # covered_lines must be non-negative
        with pytest.raises(ValueError):
            CoverageFile(
                path="test.py",
                covered_lines=-1,
                total_lines=10,
                percent_covered=50.0,
            )


class TestCoverageReport:
    """Test CoverageReport model."""

    def test_empty_report(self):
        """Test creating an empty coverage report."""
        report = CoverageReport(
            files=[],
            overall_percent=0.0,
            total_statements=0,
            covered_statements=0,
        )
        assert not report.has_low_coverage
        assert len(report.files) == 0

    def test_report_with_files(self):
        """Test report with multiple files."""
        files = [
            CoverageFile(
                path="src/a.py",
                covered_lines=80,
                total_lines=100,
                percent_covered=80.0,
            ),
            CoverageFile(
                path="src/b.py",
                covered_lines=60,
                total_lines=100,
                percent_covered=60.0,
            ),
        ]
        report = CoverageReport(
            files=files,
            overall_percent=70.0,
            total_statements=200,
            covered_statements=140,
            low_coverage_files=[files[1]],
        )
        assert report.overall_percent == 70.0
        assert report.has_low_coverage
        assert len(report.low_coverage_files) == 1


class TestParseCoverageReport:
    """Test parsing coverage.py JSON output."""

    def test_parse_simple_coverage(self):
        """Test parsing simple coverage data."""
        coverage_data = {
            "meta": {"format": 3, "version": "7.13.1"},
            "files": {
                "src/test.py": {
                    "summary": {
                        "covered_lines": 10,
                        "num_statements": 10,
                        "percent_covered": 100.0,
                    },
                    "executed_lines": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                    "missing_lines": [],
                }
            },
        }

        report = parse_coverage_report(coverage_data)
        assert report.overall_percent == 100.0
        assert report.covered_statements == 10
        assert report.total_statements == 10
        assert len(report.files) == 1
        assert report.files[0].path == "src/test.py"
        assert not report.has_low_coverage

    def test_parse_with_low_coverage(self):
        """Test parsing coverage with low-coverage files."""
        coverage_data = {
            "meta": {"format": 3},
            "files": {
                "src/good.py": {
                    "summary": {
                        "covered_lines": 90,
                        "num_statements": 100,
                        "percent_covered": 90.0,
                    },
                    "executed_lines": list(range(1, 91)),
                    "missing_lines": list(range(91, 101)),
                },
                "src/bad.py": {
                    "summary": {
                        "covered_lines": 50,
                        "num_statements": 100,
                        "percent_covered": 50.0,
                    },
                    "executed_lines": list(range(1, 51)),
                    "missing_lines": list(range(51, 101)),
                },
            },
        }

        report = parse_coverage_report(coverage_data, threshold=80.0)
        assert report.overall_percent == 70.0
        assert report.has_low_coverage
        assert len(report.low_coverage_files) == 1
        assert report.low_coverage_files[0].path == "src/bad.py"

    def test_parse_empty_coverage(self):
        """Test parsing empty coverage data."""
        coverage_data = {
            "meta": {"format": 3},
            "files": {},
        }

        report = parse_coverage_report(coverage_data)
        assert report.overall_percent == 0.0
        assert report.covered_statements == 0
        assert report.total_statements == 0
        assert len(report.files) == 0

    def test_parse_with_zero_statements(self):
        """Test parsing file with zero statements."""
        coverage_data = {
            "meta": {"format": 3},
            "files": {
                "src/empty.py": {
                    "summary": {
                        "covered_lines": 0,
                        "num_statements": 0,
                        "percent_covered": 0.0,
                    },
                    "executed_lines": [],
                    "missing_lines": [],
                }
            },
        }

        report = parse_coverage_report(coverage_data)
        assert len(report.files) == 1
        assert report.files[0].percent_covered == 0.0

    def test_coverage_file_sorting(self):
        """Test that files are sorted by coverage percentage."""
        coverage_data = {
            "meta": {"format": 3},
            "files": {
                "src/a.py": {
                    "summary": {
                        "covered_lines": 90,
                        "num_statements": 100,
                    },
                },
                "src/b.py": {
                    "summary": {
                        "covered_lines": 50,
                        "num_statements": 100,
                    },
                },
                "src/c.py": {
                    "summary": {
                        "covered_lines": 75,
                        "num_statements": 100,
                    },
                },
            },
        }

        report = parse_coverage_report(coverage_data)
        percentages = [f.percent_covered for f in report.files]
        assert percentages == sorted(percentages)


class TestIdentifyLowCoverage:
    """Test identifying low-coverage files."""

    def test_identify_single_low_coverage(self):
        """Test identifying single file with low coverage."""
        report = CoverageReport(
            files=[
                CoverageFile(
                    path="src/a.py",
                    covered_lines=50,
                    total_lines=100,
                    percent_covered=50.0,
                ),
                CoverageFile(
                    path="src/b.py",
                    covered_lines=90,
                    total_lines=100,
                    percent_covered=90.0,
                ),
            ],
            overall_percent=70.0,
            total_statements=200,
            covered_statements=140,
        )

        low = identify_low_coverage(report, threshold=80.0)
        assert len(low) == 1
        assert low[0] == "src/a.py"

    def test_identify_no_low_coverage(self):
        """Test when all files meet threshold."""
        report = CoverageReport(
            files=[
                CoverageFile(
                    path="src/a.py",
                    covered_lines=85,
                    total_lines=100,
                    percent_covered=85.0,
                ),
                CoverageFile(
                    path="src/b.py",
                    covered_lines=95,
                    total_lines=100,
                    percent_covered=95.0,
                ),
            ],
            overall_percent=90.0,
            total_statements=200,
            covered_statements=180,
        )

        low = identify_low_coverage(report, threshold=80.0)
        assert len(low) == 0


class TestGetUncoveredLines:
    """Test extracting uncovered lines from coverage data."""

    def test_get_uncovered_lines(self):
        """Test retrieving uncovered lines for a file."""
        coverage_data = {
            "meta": {"format": 3},
            "files": {
                "src/test.py": {
                    "executed_lines": [1, 2, 3, 4, 5],
                    "missing_lines": [6, 7, 8],
                    "summary": {},
                }
            },
        }

        uncovered = get_uncovered_lines(coverage_data, "src/test.py")
        assert len(uncovered) == 3
        assert uncovered[0].line_number == 6
        assert uncovered[1].line_number == 7
        assert uncovered[2].line_number == 8

    def test_get_uncovered_lines_empty_file(self):
        """Test getting uncovered lines for fully covered file."""
        coverage_data = {
            "meta": {"format": 3},
            "files": {
                "src/test.py": {
                    "executed_lines": [1, 2, 3],
                    "missing_lines": [],
                    "summary": {},
                }
            },
        }

        uncovered = get_uncovered_lines(coverage_data, "src/test.py")
        assert len(uncovered) == 0

    def test_get_uncovered_lines_missing_file(self):
        """Test getting uncovered lines for non-existent file."""
        coverage_data = {
            "meta": {"format": 3},
            "files": {},
        }

        uncovered = get_uncovered_lines(coverage_data, "src/nonexistent.py")
        assert len(uncovered) == 0

    def test_uncovered_line_sorting(self):
        """Test that uncovered lines are sorted by line number."""
        coverage_data = {
            "meta": {"format": 3},
            "files": {
                "src/test.py": {
                    "executed_lines": [],
                    "missing_lines": [10, 5, 15, 3],
                    "summary": {},
                }
            },
        }

        uncovered = get_uncovered_lines(coverage_data, "src/test.py")
        line_numbers = [u.line_number for u in uncovered]
        assert line_numbers == [3, 5, 10, 15]


class TestFormatCoverageReport:
    """Test formatting coverage reports."""

    def test_format_simple_report(self):
        """Test formatting a simple coverage report."""
        report = CoverageReport(
            files=[
                CoverageFile(
                    path="src/a.py",
                    covered_lines=80,
                    total_lines=100,
                    percent_covered=80.0,
                )
            ],
            overall_percent=80.0,
            total_statements=100,
            covered_statements=80,
        )

        formatted = format_coverage_report(report)
        assert "80.0%" in formatted
        assert "80/100" in formatted
        assert "src/a.py" in formatted

    def test_format_with_low_coverage(self):
        """Test formatting report with low coverage files."""
        report = CoverageReport(
            files=[
                CoverageFile(
                    path="src/a.py",
                    covered_lines=50,
                    total_lines=100,
                    percent_covered=50.0,
                ),
                CoverageFile(
                    path="src/b.py",
                    covered_lines=90,
                    total_lines=100,
                    percent_covered=90.0,
                ),
            ],
            overall_percent=70.0,
            total_statements=200,
            covered_statements=140,
            low_coverage_files=[
                CoverageFile(
                    path="src/a.py",
                    covered_lines=50,
                    total_lines=100,
                    percent_covered=50.0,
                )
            ],
        )

        formatted = format_coverage_report(report)
        assert "Files Below Threshold" in formatted
        assert "src/a.py" in formatted
        assert "50.0%" in formatted


class TestUncoveredLine:
    """Test UncoveredLine dataclass."""

    def test_uncovered_line_creation(self):
        """Test creating an uncovered line."""
        line = UncoveredLine(line_number=42, content="x = 1")
        assert line.line_number == 42
        assert line.content == "x = 1"

    def test_uncovered_line_without_content(self):
        """Test creating uncovered line without content."""
        line = UncoveredLine(line_number=42)
        assert line.line_number == 42
        assert line.content is None
