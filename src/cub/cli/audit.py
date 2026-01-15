"""
Audit CLI command - orchestrate code health checks.

Runs dead code detection, documentation validation, and test coverage
analysis, then combines results into a unified report.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cub.audit import (
    AuditReport,
    CategoryScore,
    CoverageReport,
    DeadCodeReport,
    DocsReport,
    Grade,
    detect_unused,
    detect_unused_bash,
    parse_coverage_report,
    run_coverage,
    validate_docs,
)

app = typer.Typer(
    name="audit",
    help="Run code health audits (dead code, docs, coverage)",
    no_args_is_help=True,
)

console = Console()


# Grading thresholds
GRADE_THRESHOLDS = {
    "A": (95, 100),
    "A-": (90, 95),
    "B+": (87, 90),
    "B": (83, 87),
    "B-": (80, 83),
    "C+": (77, 80),
    "C": (73, 77),
    "C-": (70, 73),
    "D": (60, 70),
    "F": (0, 60),
}


def calculate_grade(percentage: float) -> Grade:
    """
    Calculate letter grade from percentage score.

    Args:
        percentage: Score from 0-100

    Returns:
        Letter grade (A through F)
    """
    for grade, (low, high) in GRADE_THRESHOLDS.items():
        if low <= percentage < high:
            return grade  # type: ignore[return-value]
    return "F"


def grade_dead_code(report: DeadCodeReport) -> CategoryScore:
    """
    Grade dead code findings.

    Args:
        report: Dead code detection report

    Returns:
        CategoryScore with grade and summary
    """
    if report.total_definitions == 0:
        return CategoryScore(score="A", issues=0, details="No code to analyze")

    # Calculate percentage of definitions that are NOT dead
    health_percentage = (
        (report.total_definitions - len(report.findings)) / report.total_definitions
    ) * 100

    grade = calculate_grade(health_percentage)
    details = f"{len(report.findings)} unused definitions"

    return CategoryScore(score=grade, issues=len(report.findings), details=details)


def grade_documentation(report: DocsReport) -> CategoryScore:
    """
    Grade documentation findings.

    Args:
        report: Documentation validation report

    Returns:
        CategoryScore with grade and summary
    """
    total_checked = report.links_checked + report.code_blocks_checked
    if total_checked == 0:
        return CategoryScore(score="A", issues=0, details="No documentation to check")

    # Calculate percentage of docs that are healthy
    health_percentage = ((total_checked - report.total_issues) / total_checked) * 100

    grade = calculate_grade(health_percentage)
    link_count = len(report.link_findings)
    code_count = len(report.code_findings)
    details = f"{report.total_issues} issues ({link_count} links, {code_count} code blocks)"

    return CategoryScore(score=grade, issues=report.total_issues, details=details)


def grade_coverage(report: CoverageReport) -> CategoryScore:
    """
    Grade test coverage.

    Args:
        report: Coverage report

    Returns:
        CategoryScore with grade and summary
    """
    grade = calculate_grade(report.overall_percent)
    pct = report.overall_percent
    covered = report.covered_statements
    total = report.total_statements
    details = f"{pct:.1f}% coverage ({covered}/{total} statements)"

    return CategoryScore(
        score=grade,
        issues=len(report.low_coverage_files),
        details=details,
    )


def calculate_overall_grade(
    dead_code_score: CategoryScore | None,
    docs_score: CategoryScore | None,
    coverage_score: CategoryScore | None,
) -> Grade:
    """
    Calculate overall grade from individual category scores.

    Uses weighted average with letter grade conversion:
    - A = 95, A- = 92.5, B+ = 88.5, etc.

    Args:
        dead_code_score: Dead code category score
        docs_score: Documentation category score
        coverage_score: Coverage category score

    Returns:
        Overall letter grade
    """
    grade_values = {
        "A": 97.5,
        "A-": 92.5,
        "B+": 88.5,
        "B": 85,
        "B-": 81.5,
        "C+": 78.5,
        "C": 75,
        "C-": 71.5,
        "D": 65,
        "F": 30,
    }

    scores = []
    if dead_code_score:
        scores.append(grade_values[dead_code_score.score])
    if docs_score:
        scores.append(grade_values[docs_score.score])
    if coverage_score:
        scores.append(grade_values[coverage_score.score])

    if not scores:
        return "F"

    avg_score = sum(scores) / len(scores)
    return calculate_grade(avg_score)


def format_summary_report(report: AuditReport) -> None:
    """
    Format and display summary report using Rich.

    Args:
        report: Unified audit report
    """
    # Header
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]CUB CODEBASE HEALTH AUDIT[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    # Summary table
    table = Table(show_header=True, header_style="bold magenta", show_lines=True)
    table.add_column("Category", style="cyan", width=20)
    table.add_column("Grade", justify="center", width=8)
    table.add_column("Issues", justify="right", width=8)
    table.add_column("Details", width=50)

    def get_grade_color(grade_str: str) -> str:
        """Get color for grade (green for A, yellow for B, red otherwise)."""
        if grade_str.startswith("A"):
            return "green"
        elif grade_str.startswith("B"):
            return "yellow"
        else:
            return "red"

    # Dead code row
    if report.dead_code_score:
        score = report.dead_code_score
        grade_color = get_grade_color(score.score)
        table.add_row(
            "Dead Code",
            f"[{grade_color}]{score.score}[/{grade_color}]",
            str(score.issues),
            score.details,
        )

    # Documentation row
    if report.docs_score:
        score = report.docs_score
        grade_color = get_grade_color(score.score)
        table.add_row(
            "Documentation",
            f"[{grade_color}]{score.score}[/{grade_color}]",
            str(score.issues),
            score.details,
        )

    # Coverage row
    if report.coverage_score:
        score = report.coverage_score
        grade_color = get_grade_color(score.score)
        table.add_row(
            "Test Coverage",
            f"[{grade_color}]{score.score}[/{grade_color}]",
            str(score.issues),
            score.details,
        )

    console.print(table)
    console.print()

    # Overall grade
    if report.overall_grade:
        grade_color = get_grade_color(report.overall_grade)
        console.print(
            Panel.fit(
                f"[bold {grade_color}]OVERALL HEALTH: {report.overall_grade}[/bold {grade_color}]",
                border_style=grade_color,
            )
        )
        console.print()


def format_detailed_findings(report: AuditReport, max_findings: int = 10) -> None:
    """
    Format and display detailed findings.

    Args:
        report: Unified audit report
        max_findings: Maximum findings to show per category
    """
    # Dead code findings
    if report.dead_code and report.dead_code.has_findings:
        console.print("[bold]Dead Code Findings:[/bold]")
        for finding in report.dead_code.findings[:max_findings]:
            console.print(
                f"  • {finding.file_path}:{finding.line_number} - {finding.kind} '{finding.name}'"
            )
        if len(report.dead_code.findings) > max_findings:
            remaining = len(report.dead_code.findings) - max_findings
            console.print(f"  ... and {remaining} more")
        console.print()

    # Documentation findings
    if report.documentation and report.documentation.has_findings:
        console.print("[bold]Documentation Issues:[/bold]")
        shown = 0
        for link_finding in report.documentation.link_findings:
            if shown >= max_findings:
                break
            path = link_finding.file_path
            line = link_finding.line_number
            issue = link_finding.issue
            url = link_finding.url
            console.print(f"  • {path}:{line} - {issue}: {url}")
            shown += 1
        for code_finding in report.documentation.code_findings:
            if shown >= max_findings:
                break
            path = code_finding.file_path
            line = code_finding.line_number
            lang = code_finding.language
            msg = code_finding.error_message
            console.print(f"  • {path}:{line} - {lang}: {msg}")
            shown += 1
        remaining = report.documentation.total_issues - shown
        if remaining > 0:
            console.print(f"  ... and {remaining} more")
        console.print()

    # Coverage findings
    if report.coverage and report.coverage.has_low_coverage:
        console.print("[bold]Low Coverage Files:[/bold]")
        for file_cov in report.coverage.low_coverage_files[:max_findings]:
            console.print(
                f"  • {file_cov.path} - {file_cov.percent_covered:.1f}% covered"
            )
        if len(report.coverage.low_coverage_files) > max_findings:
            remaining = len(report.coverage.low_coverage_files) - max_findings
            console.print(f"  ... and {remaining} more")
        console.print()


@app.command()
def run(
    ctx: typer.Context,
    dead_code: Annotated[
        bool,
        typer.Option("--dead-code", help="Run dead code detection"),
    ] = True,
    docs: Annotated[
        bool,
        typer.Option("--docs", help="Run documentation validation"),
    ] = True,
    coverage: Annotated[
        bool,
        typer.Option("--coverage", help="Run test coverage analysis"),
    ] = True,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output report as JSON"),
    ] = False,
    ci_mode: Annotated[
        bool,
        typer.Option("--ci", help="CI mode: exit non-zero on failures"),
    ] = False,
    threshold: Annotated[
        str,
        typer.Option("--threshold", help="Minimum grade required for CI mode (A, B, C, etc)"),
    ] = "C",
    detailed: Annotated[
        bool,
        typer.Option("--detailed", help="Show detailed findings"),
    ] = False,
) -> None:
    """
    Run code health audit.

    By default, runs all checks (dead code, docs, coverage).
    Use flags to run specific checks only.

    Examples:
        cub audit run                    # Run all checks
        cub audit run --dead-code        # Only dead code
        cub audit run --ci --threshold B # CI mode, require B or better
        cub audit run --json             # JSON output
        cub audit run --detailed         # Show detailed findings
    """
    project_root = Path.cwd()

    # Initialize report
    audit_report = AuditReport()

    # Run dead code detection
    if dead_code:
        console.print("[cyan]Running dead code detection...[/cyan]")
        try:
            # Python dead code
            python_report = detect_unused(
                project_root / "src",
                exclude_patterns=["**/test_*.py", "**/tests/**"],
            )
            # Bash dead code
            bash_report = detect_unused_bash(
                project_root,
                exclude_patterns=["**/tests/**", "**/.venv/**"],
            )

            # Combine reports
            combined_report = DeadCodeReport(
                findings=python_report.findings + bash_report.findings,
                files_scanned=python_report.files_scanned + bash_report.files_scanned,
                total_definitions=python_report.total_definitions
                + bash_report.total_definitions,
            )

            audit_report.dead_code = combined_report
            audit_report.dead_code_score = grade_dead_code(combined_report)
        except Exception as e:
            console.print(f"[yellow]Warning: Dead code detection failed: {e}[/yellow]")

    # Run documentation validation
    if docs:
        console.print("[cyan]Running documentation validation...[/cyan]")
        try:
            # Find all markdown files
            md_files = list(project_root.rglob("*.md"))
            docs_report = validate_docs(md_files, project_root, check_external_links=True)
            audit_report.documentation = docs_report
            audit_report.docs_score = grade_documentation(docs_report)
        except Exception as e:
            console.print(f"[yellow]Warning: Documentation validation failed: {e}[/yellow]")

    # Run coverage analysis
    if coverage:
        console.print("[cyan]Running test coverage analysis...[/cyan]")
        try:
            coverage_data = run_coverage()
            coverage_report = parse_coverage_report(coverage_data, threshold=80.0)
            audit_report.coverage = coverage_report
            audit_report.coverage_score = grade_coverage(coverage_report)
        except Exception as e:
            console.print(f"[yellow]Warning: Coverage analysis failed: {e}[/yellow]")

    # Calculate overall grade
    audit_report.overall_grade = calculate_overall_grade(
        audit_report.dead_code_score,
        audit_report.docs_score,
        audit_report.coverage_score,
    )

    # Output results
    if json_output:
        console.print(audit_report.model_dump_json(indent=2))
    else:
        format_summary_report(audit_report)
        if detailed:
            format_detailed_findings(audit_report)

    # CI mode: exit with appropriate code
    if ci_mode:
        grade_order = ["F", "D", "C-", "C", "C+", "B-", "B", "B+", "A-", "A"]
        required_grade = threshold.upper()

        if required_grade not in grade_order:
            console.print(f"[red]Error: Invalid threshold '{threshold}'[/red]")
            raise typer.Exit(1)

        if audit_report.overall_grade:
            actual_idx = grade_order.index(audit_report.overall_grade)
            required_idx = grade_order.index(required_grade)

            if actual_idx < required_idx:
                console.print(
                    f"[red]Audit failed: {audit_report.overall_grade} < {required_grade}[/red]"
                )
                raise typer.Exit(1)

        console.print("[green]Audit passed[/green]")
