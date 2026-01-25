"""
Cub CLI - Review commands.

Assess whether completed tasks, epics, or plans were fully implemented
by examining ledger entries, verification status, and spec drift.
"""

from pathlib import Path

import typer
from rich.console import Console

from cub.core.ledger.reader import LedgerReader
from cub.core.review.assessor import EpicAssessor, PlanAssessor, TaskAssessor
from cub.core.review.reporter import ReviewReporter
from cub.utils.project import get_project_root

app = typer.Typer(
    name="review",
    help="Review completed task implementations",
    no_args_is_help=True,
)

console = Console()


def _get_ledger_reader() -> LedgerReader:
    """Get ledger reader for current project."""
    project_root = get_project_root()
    ledger_dir = project_root / ".cub" / "ledger"
    return LedgerReader(ledger_dir)


def _get_plans_root() -> Path:
    """Get plans directory for current project."""
    project_root = get_project_root()
    return project_root / "plans"


@app.command()
def task(
    task_id: str = typer.Argument(..., help="Task ID to review"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output including recommendations",
    ),
    deep: bool = typer.Option(
        False,
        "--deep",
        help="Run LLM-based deep analysis of implementation vs spec",
    ),
) -> None:
    """
    Review a single task implementation.

    Assesses the task by examining its ledger entry for verification status,
    spec drift, outcome success, and commit history.

    Use --deep for LLM-based analysis comparing implementation to specification.

    Examples:
        cub review task beads-abc
        cub review task beads-abc --json
        cub review task beads-abc --verbose
        cub review task beads-abc --deep
    """
    reader = _get_ledger_reader()

    if not reader.exists():
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "Tasks have not been completed yet."
        )
        raise typer.Exit(0)

    assessor = TaskAssessor(reader)
    assessment = assessor.assess_task(task_id, deep=deep)

    if json_output:
        reporter = ReviewReporter(console, verbose=verbose)
        console.print(reporter.to_json(assessment))
        return

    # Rich formatted output
    reporter = ReviewReporter(console, verbose=verbose)
    reporter.render_task_assessment(assessment)


@app.command()
def epic(
    epic_id: str = typer.Argument(..., help="Epic ID to review"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output including recommendations",
    ),
    deep: bool = typer.Option(
        False,
        "--deep",
        help="Run LLM-based deep analysis of implementation vs spec",
    ),
) -> None:
    """
    Review all tasks in an epic.

    Assesses each task in the epic and provides an aggregate assessment
    including completion rates and overall grade.

    Use --deep for LLM-based analysis comparing implementation to specification.

    Examples:
        cub review epic cub-abc
        cub review epic cub-abc --json
        cub review epic cub-abc --verbose
        cub review epic cub-abc --deep
    """
    reader = _get_ledger_reader()

    if not reader.exists():
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "Tasks have not been completed yet."
        )
        raise typer.Exit(0)

    assessor = EpicAssessor(reader)
    assessment = assessor.assess_epic(epic_id, deep=deep)

    if json_output:
        reporter = ReviewReporter(console, verbose=verbose)
        console.print(reporter.to_json(assessment))
        return

    # Rich formatted output
    reporter = ReviewReporter(console, verbose=verbose)
    reporter.render_epic_assessment(assessment)


@app.command()
def plan(
    plan_slug: str = typer.Argument(..., help="Plan slug to review"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output including recommendations",
    ),
    deep: bool = typer.Option(
        False,
        "--deep",
        help="Run LLM-based deep analysis of implementation vs spec",
    ),
) -> None:
    """
    Review all work from a plan.

    Assesses all epics and tasks associated with a plan session,
    providing an overall assessment of plan completion.

    Use --deep for LLM-based analysis comparing implementation to specification.

    Examples:
        cub review plan unified-tracking-model
        cub review plan unified-tracking-model --json
        cub review plan unified-tracking-model --verbose
        cub review plan unified-tracking-model --deep
    """
    reader = _get_ledger_reader()
    plans_root = _get_plans_root()

    if not reader.exists():
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "Tasks have not been completed yet."
        )
        raise typer.Exit(0)

    assessor = PlanAssessor(reader, plans_root)
    assessment = assessor.assess_plan(plan_slug, deep=deep)

    if json_output:
        reporter = ReviewReporter(console, verbose=verbose)
        console.print(reporter.to_json(assessment))
        return

    # Rich formatted output
    reporter = ReviewReporter(console, verbose=verbose)
    reporter.render_plan_assessment(assessment)
