"""
Test coverage reporting and analysis.

Executes pytest with coverage, parses coverage.py output, and identifies
files with insufficient coverage.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field


class CoverageFile(BaseModel):
    """Coverage information for a single file."""

    path: str = Field(description="Path to the file")
    covered_lines: int = Field(ge=0, description="Number of executed lines")
    total_lines: int = Field(ge=0, description="Total number of statements")
    percent_covered: float = Field(ge=0.0, le=100.0, description="Coverage percentage")


class CoverageReport(BaseModel):
    """Report of test coverage across the project."""

    files: list[CoverageFile] = Field(default_factory=list, description="Per-file coverage")
    overall_percent: float = Field(
        ge=0.0, le=100.0, description="Overall project coverage percentage"
    )
    total_statements: int = Field(ge=0, description="Total statements in project")
    covered_statements: int = Field(ge=0, description="Total covered statements")
    low_coverage_files: list[CoverageFile] = Field(
        default_factory=list, description="Files below threshold"
    )

    @property
    def has_low_coverage(self) -> bool:
        """Return True if there are files with low coverage."""
        return len(self.low_coverage_files) > 0


@dataclass
class UncoveredLine:
    """A line that is not covered by tests."""

    line_number: int
    content: str | None = None


def run_coverage(
    test_dir: str | None = None,
    cov_dir: str | None = None,
) -> dict[str, object]:
    """
    Run pytest with coverage and return the coverage data.

    Args:
        test_dir: Directory containing tests (default: tests/)
        cov_dir: Directory to measure coverage on (default: src/)

    Returns:
        Coverage report dictionary (parsed from coverage.json)

    Raises:
        subprocess.CalledProcessError: If pytest fails
        ImportError: If pytest-cov is not installed
    """
    test_dir = test_dir or "tests"
    cov_dir = cov_dir or "src"

    # Check if coverage.py is available
    try:
        import coverage  # noqa: F401
    except ImportError as e:
        raise ImportError("pytest-cov is required for coverage reporting") from e

    # Run pytest with coverage
    cmd = [
        "pytest",
        test_dir,
        "--cov",
        cov_dir,
        "--cov-report=json",
        "--cov-report=term",
        "-q",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    # Even if tests fail, we can still get coverage data
    # Only raise if pytest couldn't run at all
    if "No module named pytest" in result.stderr or "No module named 'pytest'" in result.stderr:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)

    # Parse coverage.json (coverage.py creates it in current dir)
    coverage_json_path = (
        Path(".coverage")
        if (Path(".coverage").exists())
        else Path("coverage.json")
    )

    if not coverage_json_path.exists():
        # Try with json extension
        coverage_json_path = Path("coverage.json")

    if not coverage_json_path.exists():
        raise FileNotFoundError("coverage.json not found after running coverage")

    with coverage_json_path.open() as f:
        return cast(dict[str, object], json.load(f))


def parse_coverage_report(
    coverage_data: dict[str, object],
    threshold: float = 80.0,
) -> CoverageReport:
    """
    Parse coverage.py JSON output into a CoverageReport.

    Args:
        coverage_data: Coverage data dictionary (from coverage.json)
        threshold: Minimum coverage percentage (default: 80%)

    Returns:
        CoverageReport with overall and per-file coverage
    """
    files_data: list[CoverageFile] = []
    total_covered = 0
    total_statements = 0

    # Parse each file's coverage
    files_dict = coverage_data.get("files")
    if not isinstance(files_dict, dict):
        files_dict = {}

    for file_path, file_info in files_dict.items():
        if not isinstance(file_info, dict):
            continue

        summary = file_info.get("summary")
        if not isinstance(summary, dict):
            summary = {}

        covered = int(summary.get("covered_lines", 0))
        num_statements = int(summary.get("num_statements", 0))

        # Calculate percentage
        if num_statements > 0:
            percent = (covered / num_statements) * 100.0
        else:
            percent = 0.0 if covered == 0 else 100.0

        files_data.append(
            CoverageFile(
                path=str(file_path),
                covered_lines=covered,
                total_lines=num_statements,
                percent_covered=round(percent, 1),
            )
        )

        total_covered += covered
        total_statements += num_statements

    # Calculate overall coverage
    if total_statements > 0:
        overall_percent = round((total_covered / total_statements) * 100.0, 1)
    else:
        overall_percent = 0.0

    # Find low coverage files
    low_coverage = [f for f in files_data if f.percent_covered < threshold]

    return CoverageReport(
        files=sorted(files_data, key=lambda f: f.percent_covered),
        overall_percent=overall_percent,
        total_statements=total_statements,
        covered_statements=total_covered,
        low_coverage_files=sorted(low_coverage, key=lambda f: f.percent_covered),
    )


def identify_low_coverage(
    report: CoverageReport,
    threshold: float = 80.0,
) -> list[str]:
    """
    Identify files with coverage below threshold.

    Args:
        report: CoverageReport to analyze
        threshold: Minimum coverage percentage

    Returns:
        List of file paths with low coverage
    """
    return [
        f.path for f in report.files if f.percent_covered < threshold
    ]


def get_uncovered_lines(
    coverage_data: dict[str, object],
    file_path: str,
) -> list[UncoveredLine]:
    """
    Get the specific uncovered lines for a file.

    Args:
        coverage_data: Coverage data dictionary (from coverage.json)
        file_path: Path to the file to analyze

    Returns:
        List of uncovered lines with their line numbers
    """
    files_dict = coverage_data.get("files")
    if not isinstance(files_dict, dict) or file_path not in files_dict:
        return []

    file_info = files_dict[file_path]
    if not isinstance(file_info, dict):
        return []

    missing = file_info.get("missing_lines")
    if not isinstance(missing, list):
        return []

    # Build list of uncovered lines
    uncovered = []
    for line_num in missing:
        if isinstance(line_num, int):
            uncovered.append(UncoveredLine(line_number=line_num))

    return sorted(uncovered, key=lambda u: u.line_number)


def format_coverage_report(report: CoverageReport) -> str:
    """
    Format a CoverageReport as human-readable text.

    Args:
        report: CoverageReport to format

    Returns:
        Formatted report string
    """
    lines = [
        f"Overall Coverage: {report.overall_percent}%",
        f"Covered Statements: {report.covered_statements}/{report.total_statements}",
        "",
    ]

    if report.has_low_coverage:
        lines.append("Files Below Threshold:")
        for f in report.low_coverage_files:
            lines.append(f"  {f.path}: {f.percent_covered}% ({f.covered_lines}/{f.total_lines})")
        lines.append("")

    lines.append("All Files:")
    for f in report.files[-10:]:  # Show top 10 by coverage
        lines.append(f"  {f.path}: {f.percent_covered}%")

    return "\n".join(lines)
