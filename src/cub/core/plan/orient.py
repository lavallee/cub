"""
Orient stage implementation for cub plan.

The orient stage gathers requirements and understands the problem space.
It invokes Claude Code with the /cub:orient command to conduct an interactive
interview, analyze the spec, and produce orientation.md with:
- Problem statement (refined)
- Requirements (P0/P1/P2)
- Constraints
- Open questions
- Risks with mitigations

Example:
    >>> from cub.core.plan.context import PlanContext
    >>> from cub.core.plan.orient import OrientStage
    >>> ctx = PlanContext.create(
    ...     project_root=Path("."),
    ...     spec_path=Path("specs/researching/my-feature.md"),
    ...     project="cub",
    ... )
    >>> stage = OrientStage(ctx)
    >>> result = stage.run()
    >>> result.output_path.exists()
    True
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from cub.core.plan.claude import (
    ClaudeNotFoundError,
    invoke_claude_command,
)
from cub.core.plan.models import PlanStage

if TYPE_CHECKING:
    from cub.core.plan.context import PlanContext


@dataclass
class OrientQuestion:
    """A question to be answered during the orient phase."""

    id: str
    question: str
    category: str
    required: bool = True
    answer: str | None = None


@dataclass
class OrientResult:
    """Result of running the orient stage."""

    output_path: Path
    problem_statement: str
    requirements_p0: list[str]
    requirements_p1: list[str]
    requirements_p2: list[str]
    constraints: list[str]
    open_questions: list[str]
    risks: list[tuple[str, str]]  # (risk, mitigation)
    mvp_boundary: str
    success_criteria: list[str]
    started_at: datetime
    completed_at: datetime

    @property
    def duration_seconds(self) -> float:
        """Get the duration of the orient stage in seconds."""
        return (self.completed_at - self.started_at).total_seconds()


class OrientStageError(Exception):
    """Base exception for orient stage errors."""

    pass


class OrientInputError(OrientStageError):
    """Raised when orient stage input is invalid or missing."""

    pass


# Default questions for the orient phase
DEFAULT_ORIENT_QUESTIONS: list[OrientQuestion] = [
    OrientQuestion(
        id="problem",
        question="What problem does this solve? Who has it?",
        category="Problem Statement",
        required=True,
    ),
    OrientQuestion(
        id="success",
        question="How will we know this succeeded?",
        category="Success Criteria",
        required=True,
    ),
    OrientQuestion(
        id="constraints",
        question="What are the hard limits (time, tech, budget, compliance)?",
        category="Constraints",
        required=True,
    ),
    OrientQuestion(
        id="mvp",
        question="What's the smallest useful version?",
        category="MVP Boundary",
        required=True,
    ),
    OrientQuestion(
        id="concerns",
        question="What keeps you up at night about this?",
        category="Concerns",
        required=False,
    ),
]


class OrientStage:
    """
    Orient stage of the planning pipeline.

    The orient phase gathers context about the project:
    - Analyzes captures and existing documentation
    - Identifies key concepts and constraints
    - Surfaces questions that need answers

    This stage produces orientation.md with problem understanding,
    requirements, constraints, open questions, and risks.

    Attributes:
        ctx: The PlanContext for this planning session.
        questions: Questions to be answered during orient.
    """

    def __init__(
        self,
        ctx: PlanContext,
        questions: list[OrientQuestion] | None = None,
    ) -> None:
        """
        Initialize the orient stage.

        Args:
            ctx: PlanContext for this planning session.
            questions: Custom questions to ask. Defaults to standard questions.
        """
        self.ctx = ctx
        self.questions = questions or DEFAULT_ORIENT_QUESTIONS.copy()

    def validate(self) -> None:
        """
        Validate that orient stage can run.

        Raises:
            OrientInputError: If prerequisites are not met.
        """
        # Orient is the first stage, so no prerequisite stages needed
        # Just need either a spec or interactive mode
        if not self.ctx.has_spec:
            # For now, require a spec. Interactive mode can be added later.
            raise OrientInputError(
                "Orient stage requires a spec file. "
                "Interactive mode without spec is not yet implemented."
            )

        if self.ctx.spec_path and not self.ctx.spec_path.exists():
            raise OrientInputError(f"Spec file not found: {self.ctx.spec_path}")

    def _gather_context(self) -> dict[str, str | None]:
        """
        Gather context from the project for analysis.

        Returns:
            Dictionary with context sources:
            - spec_content: Content of the source spec
            - system_plan: SYSTEM-PLAN.md content (if exists)
            - agent_instructions: CLAUDE.md content (if exists)
        """
        context: dict[str, str | None] = {
            "spec_content": None,
            "system_plan": None,
            "agent_instructions": None,
        }

        # Read spec content
        if self.ctx.has_spec:
            try:
                context["spec_content"] = self.ctx.read_spec_content()
            except Exception:
                pass  # Will be caught in validate()

        # Read SYSTEM-PLAN.md
        context["system_plan"] = self.ctx.read_system_plan()

        # Read agent instructions
        context["agent_instructions"] = self.ctx.read_agent_instructions()

        return context

    def _extract_from_spec(self, spec_content: str) -> dict[str, object]:
        """
        Extract information from the spec content.

        This is a simple extraction that looks for common patterns in specs.
        More sophisticated extraction would use an LLM.

        Args:
            spec_content: Content of the spec file.

        Returns:
            Dictionary with extracted information.
        """
        import re

        extracted: dict[str, object] = {
            "title": None,
            "overview": None,
            "goals": [],
            "non_goals": [],
            "constraints": [],
            "decisions_made": [],
            "open_questions": [],
        }

        # Extract title from first heading
        title_match = re.search(r"^#\s+(.+)$", spec_content, re.MULTILINE)
        if title_match:
            extracted["title"] = title_match.group(1).strip()

        # Extract overview section
        overview_match = re.search(
            r"##\s+Overview\s*\n([\s\S]*?)(?=\n##|\Z)",
            spec_content,
            re.IGNORECASE,
        )
        if overview_match:
            extracted["overview"] = overview_match.group(1).strip()

        # Extract goals section
        goals_match = re.search(
            r"##\s+Goals\s*\n([\s\S]*?)(?=\n##|\Z)",
            spec_content,
            re.IGNORECASE,
        )
        if goals_match:
            goals_content = goals_match.group(1)
            # Extract bullet points
            goals = re.findall(r"^[-*]\s+\*?\*?(.+?)\*?\*?:", goals_content, re.MULTILINE)
            if goals:
                extracted["goals"] = [g.strip() for g in goals]

        # Extract non-goals section
        non_goals_match = re.search(
            r"##\s+Non-Goals\s*\n([\s\S]*?)(?=\n##|\Z)",
            spec_content,
            re.IGNORECASE,
        )
        if non_goals_match:
            non_goals_content = non_goals_match.group(1)
            non_goals = re.findall(r"^[-*]\s+(.+)$", non_goals_content, re.MULTILINE)
            if non_goals:
                extracted["non_goals"] = [ng.strip() for ng in non_goals]

        # Extract decisions made from frontmatter
        decisions_match = re.search(
            r"decisions_made:\s*\n((?:\s+-\s+.+\n?)+)",
            spec_content,
        )
        if decisions_match:
            decisions_content = decisions_match.group(1)
            decisions = re.findall(r'^\s+-\s+"?(.+?)"?\s*$', decisions_content, re.MULTILINE)
            if decisions:
                extracted["decisions_made"] = [d.strip().strip('"') for d in decisions]

        # Extract open questions from readiness section
        questions_match = re.search(
            r"questions:\s*\n((?:\s+-\s+.+\n?)+)",
            spec_content,
        )
        if questions_match:
            questions_content = questions_match.group(1)
            questions = re.findall(r"^\s+-\s+(.+)$", questions_content, re.MULTILINE)
            if questions:
                extracted["open_questions"] = [q.strip() for q in questions]

        return extracted

    def _generate_orientation(
        self,
        context: dict[str, str | None],
        extracted: dict[str, object],
    ) -> str:
        """
        Generate the orientation.md content.

        Args:
            context: Gathered project context.
            extracted: Information extracted from spec.

        Returns:
            Generated orientation.md content.
        """
        now = datetime.now(timezone.utc)
        spec_path = self.ctx.spec_path

        # Build header
        lines = [
            f"# Orientation: {extracted.get('title', self.ctx.plan.slug)}",
            "",
            f"> Source: [{spec_path.name if spec_path else 'interactive'}]"
            f"({self._relative_spec_path() or 'N/A'})",
            f"> Generated: {now.strftime('%Y-%m-%d')}",
            f"> Depth: {self.ctx.depth.title()}",
            "",
        ]

        # Problem Statement
        lines.extend([
            "## Problem Statement",
            "",
        ])
        overview = extracted.get("overview")
        if overview:
            lines.append(str(overview))
        else:
            lines.append("*Problem statement to be refined during interview.*")
        lines.append("")

        # Requirements
        lines.extend([
            "## Requirements",
            "",
            "### P0 (Must Have)",
            "",
        ])
        goals = extracted.get("goals", [])
        if isinstance(goals, list) and goals:
            for goal in goals:
                lines.append(f"- **{goal}**")
        else:
            lines.append("- *Requirements to be gathered during interview.*")
        lines.append("")

        lines.extend([
            "### P1 (Should Have)",
            "",
            "- *To be determined during interview.*",
            "",
            "### P2 (Nice to Have)",
            "",
            "- *To be determined during interview.*",
            "",
        ])

        # Constraints
        lines.extend([
            "## Constraints",
            "",
            "| Constraint | Detail |",
            "|------------|--------|",
        ])

        # Add standard constraints from context
        agent_instructions = context.get("agent_instructions")
        if agent_instructions:
            # Try to extract tech stack info
            if "python 3.10" in agent_instructions.lower():
                lines.append("| Python version | 3.10+ |")
            if "mypy" in agent_instructions.lower():
                lines.append("| Type checking | mypy strict mode |")

        decisions = extracted.get("decisions_made", [])
        if isinstance(decisions, list) and decisions:
            for decision in decisions[:5]:  # Limit to first 5
                # Truncate long decisions
                short = decision[:50] + "..." if len(decision) > 50 else decision
                lines.append(f"| Decision | {short} |")

        if len(lines) == lines.index("| Constraint | Detail |") + 2:
            # No constraints added, add placeholder
            lines.append("| *Constraints* | *To be determined* |")
        lines.append("")

        # Open Questions
        lines.extend([
            "## Open Questions",
            "",
        ])
        questions = extracted.get("open_questions", [])
        if isinstance(questions, list) and questions:
            for i, q in enumerate(questions, 1):
                lines.append(f"{i}. {q}")
        else:
            lines.append("1. *Questions to be surfaced during interview.*")
        lines.append("")

        # Risks & Mitigations
        lines.extend([
            "## Risks & Mitigations",
            "",
            "| Risk | Impact | Likelihood | Mitigation |",
            "|------|--------|------------|------------|",
            "| *Risks* | *TBD* | *TBD* | *To be determined during interview* |",
            "",
        ])

        # MVP Boundary
        lines.extend([
            "## MVP Boundary",
            "",
            "**In scope for MVP:**",
        ])
        if isinstance(goals, list) and goals:
            for goal in goals[:3]:
                lines.append(f"- {goal}")
        else:
            lines.append("- *To be determined during interview.*")
        lines.extend([
            "",
            "**Explicitly deferred:**",
        ])
        non_goals = extracted.get("non_goals", [])
        if isinstance(non_goals, list) and non_goals:
            for ng in non_goals[:3]:
                lines.append(f"- {ng}")
        else:
            lines.append("- *To be determined during interview.*")
        lines.extend([
            "",
            "---",
            "",
            "**Status**: Ready for Architect phase",
            "",
        ])

        return "\n".join(lines)

    def _relative_spec_path(self) -> str | None:
        """Get the relative path from plan dir to spec file."""
        if not self.ctx.spec_path:
            return None

        try:
            # Calculate relative path from plan directory to spec
            spec_path = self.ctx.spec_path
            return str(Path("../..") / spec_path.relative_to(self.ctx.project_root))
        except ValueError:
            return str(self.ctx.spec_path)

    def run(self, non_interactive: bool = False) -> OrientResult:
        """
        Run the orient stage.

        This method invokes Claude Code with the /cub:orient command to conduct
        an interactive interview and generate orientation.md.

        In non-interactive mode, it uses claude -p for best-effort generation.
        If Claude Code is not available, falls back to template-based generation.

        Args:
            non_interactive: If True, use claude -p for non-interactive mode.

        Returns:
            OrientResult with output path and extracted information.

        Raises:
            OrientStageError: If stage fails to run.
        """
        started_at = datetime.now(timezone.utc)

        # Validate prerequisites
        self.validate()

        # Mark stage as in progress
        self.ctx.plan.start_stage(PlanStage.ORIENT)
        self.ctx.ensure_plan_dir()
        self.ctx.save_plan()

        output_path = self.ctx.orientation_path

        # Build arguments for Claude command
        # Pass the spec path and plan slug for Claude to use
        args = str(self.ctx.spec_path) if self.ctx.spec_path else ""
        args = f"{args} {self.ctx.plan.slug}".strip()

        try:
            # Invoke Claude Code with /cub:orient
            result = invoke_claude_command(
                command="cub:orient",
                args=args,
                working_dir=self.ctx.project_root,
                output_path=output_path,
                non_interactive=non_interactive,
            )

            if result.needs_human_input:
                # Stage is blocked on human input
                raise OrientStageError(
                    "Orient stage needs human input:\n"
                    + "\n".join(f"  - {q}" for q in (result.human_input_questions or []))
                )

            if not result.success:
                # Claude command failed - fall back to template generation
                self._run_template_fallback(output_path)

        except ClaudeNotFoundError:
            # Fall back to template-based generation
            self._run_template_fallback(output_path)

        # Verify output was created
        if not output_path.exists():
            raise OrientStageError(
                f"Orient output file not created: {output_path}. "
                "Claude session may have been interrupted."
            )

        # Mark stage as complete
        self.ctx.plan.complete_stage(PlanStage.ORIENT)
        try:
            self.ctx.save_plan()
        except (OSError, ValueError) as e:
            raise OrientStageError(f"Cannot save plan after orient stage: {e}") from e

        completed_at = datetime.now(timezone.utc)

        # Parse the original spec for the result
        # (The generated orientation.md has different section names)
        spec_content = ""
        if self.ctx.has_spec and self.ctx.spec_path and self.ctx.spec_path.exists():
            try:
                spec_content = self.ctx.read_spec_content()
            except Exception:
                pass
        extracted = self._extract_from_spec(spec_content)
        goals = extracted.get("goals", [])
        questions = extracted.get("open_questions", [])

        return OrientResult(
            output_path=output_path,
            problem_statement=str(extracted.get("overview") or ""),
            requirements_p0=list(goals) if isinstance(goals, list) else [],
            requirements_p1=[],
            requirements_p2=[],
            constraints=[],
            open_questions=list(questions) if isinstance(questions, list) else [],
            risks=[],
            mvp_boundary="",
            success_criteria=[],
            started_at=started_at,
            completed_at=completed_at,
        )

    def _run_template_fallback(self, output_path: Path) -> None:
        """
        Fall back to template-based generation when Claude is not available.

        Args:
            output_path: Path to write the orientation file.
        """
        # Gather context
        context = self._gather_context()

        # Extract from spec
        spec_content = context.get("spec_content") or ""
        extracted = self._extract_from_spec(spec_content)

        # Generate orientation
        orientation_content = self._generate_orientation(context, extracted)

        # Write orientation.md
        try:
            output_path.write_text(orientation_content, encoding="utf-8")
        except OSError as e:
            raise OrientStageError(
                f"Cannot write orientation file {output_path}: {e}"
            ) from e


def run_orient(ctx: PlanContext, non_interactive: bool = False) -> OrientResult:
    """
    Convenience function to run the orient stage.

    Args:
        ctx: PlanContext for this planning session.
        non_interactive: If True, use claude -p for non-interactive mode.

    Returns:
        OrientResult with output path and extracted information.
    """
    stage = OrientStage(ctx)
    return stage.run(non_interactive=non_interactive)
