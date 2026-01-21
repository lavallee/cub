"""
Architect stage implementation for cub plan.

The architect stage designs the technical approach based on orientation.
It reads orientation.md and produces architecture.md with:
- Technical summary
- Technology stack with rationale
- System architecture diagram
- Components and their responsibilities
- Data model
- APIs/Interfaces
- Implementation phases
- Technical risks and mitigations

Example:
    >>> from cub.core.plan.context import PlanContext
    >>> from cub.core.plan.architect import ArchitectStage
    >>> ctx = PlanContext.load(Path("plans/my-feature"))
    >>> stage = ArchitectStage(ctx)
    >>> result = stage.run()
    >>> result.output_path.exists()
    True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from cub.core.plan.models import PlanStage, StageStatus

if TYPE_CHECKING:
    from cub.core.plan.context import PlanContext


@dataclass
class TechStackChoice:
    """A technology choice in the stack."""

    layer: str  # e.g., "Language", "Framework", "Database"
    choice: str  # e.g., "Python 3.11"
    rationale: str  # e.g., "Team familiarity, rich ecosystem"


@dataclass
class Component:
    """A component in the system architecture."""

    name: str
    purpose: str
    responsibilities: list[str]
    dependencies: list[str]
    interface: str  # e.g., "REST API", "Internal Python module"


@dataclass
class ImplementationPhase:
    """A phase in the implementation plan."""

    number: int
    name: str
    goal: str
    tasks: list[str]


@dataclass
class TechnicalRisk:
    """A technical risk with mitigation."""

    risk: str
    impact: str  # "High", "Medium", "Low"
    likelihood: str  # "High", "Medium", "Low"
    mitigation: str


@dataclass
class ArchitectResult:
    """Result of running the architect stage."""

    output_path: Path
    technical_summary: str
    tech_stack: list[TechStackChoice]
    components: list[Component]
    implementation_phases: list[ImplementationPhase]
    technical_risks: list[TechnicalRisk]
    mindset: str
    scale: str
    started_at: datetime
    completed_at: datetime

    @property
    def duration_seconds(self) -> float:
        """Get the duration of the architect stage in seconds."""
        return (self.completed_at - self.started_at).total_seconds()


class ArchitectStageError(Exception):
    """Base exception for architect stage errors."""

    pass


class ArchitectInputError(ArchitectStageError):
    """Raised when architect stage input is invalid or missing."""

    pass


@dataclass
class ArchitectQuestion:
    """A question to be answered during the architect phase."""

    id: str
    question: str
    category: str
    options: list[str] = field(default_factory=list)  # Predefined options
    required: bool = True
    answer: str | None = None


# Default questions for the architect phase (based on docs-src/guide/prep-pipeline/architect.md)
DEFAULT_ARCHITECT_QUESTIONS: list[ArchitectQuestion] = [
    ArchitectQuestion(
        id="mindset",
        question="What's the context for this project?",
        category="Technical Mindset",
        options=["Prototype", "MVP", "Production", "Enterprise"],
        required=True,
    ),
    ArchitectQuestion(
        id="scale",
        question="What usage do you anticipate?",
        category="Scale Expectations",
        options=["Personal", "Team", "Product", "Internet-scale"],
        required=True,
    ),
    ArchitectQuestion(
        id="tech_stack",
        question="Any technology preferences or constraints?",
        category="Tech Stack",
        required=False,
    ),
    ArchitectQuestion(
        id="integrations",
        question="What external systems does this need to connect to?",
        category="Integrations",
        required=False,
    ),
]


class ArchitectStage:
    """
    Architect stage of the planning pipeline.

    The architect phase designs the technical approach:
    - Reviews orientation.md for requirements context
    - Explores existing codebase patterns
    - Produces architecture.md with technology choices and component design

    This stage produces architecture.md with technical summary,
    technology stack, system architecture, components, and implementation phases.

    Attributes:
        ctx: The PlanContext for this planning session.
        questions: Questions to be answered during architect.
        mindset: Technical mindset (prototype/mvp/production/enterprise).
        scale: Expected scale (personal/team/product/internet-scale).
    """

    def __init__(
        self,
        ctx: PlanContext,
        questions: list[ArchitectQuestion] | None = None,
        mindset: str = "mvp",
        scale: str = "team",
    ) -> None:
        """
        Initialize the architect stage.

        Args:
            ctx: PlanContext for this planning session.
            questions: Custom questions to ask. Defaults to standard questions.
            mindset: Technical mindset level.
            scale: Expected usage scale.
        """
        self.ctx = ctx
        self.questions = questions or DEFAULT_ARCHITECT_QUESTIONS.copy()
        self.mindset = mindset.lower()
        self.scale = scale.lower()

    def validate(self) -> None:
        """
        Validate that architect stage can run.

        Raises:
            ArchitectInputError: If prerequisites are not met.
        """
        # Check that orient stage is complete
        if self.ctx.plan.stages[PlanStage.ORIENT] != StageStatus.COMPLETE:
            raise ArchitectInputError(
                "Architect stage requires completed orientation. "
                "Run 'cub plan orient' first."
            )

        # Check that orientation.md exists
        if not self.ctx.orientation_path.exists():
            raise ArchitectInputError(
                f"Orientation file not found: {self.ctx.orientation_path}. "
                "Run 'cub plan orient' first."
            )

    def _read_orientation(self) -> str:
        """
        Read the orientation.md content.

        Returns:
            Content of orientation.md.

        Raises:
            ArchitectInputError: If file cannot be read.
        """
        try:
            return self.ctx.orientation_path.read_text()
        except OSError as e:
            raise ArchitectInputError(f"Cannot read orientation.md: {e}") from e

    def _gather_context(self) -> dict[str, str | None]:
        """
        Gather context from the project for analysis.

        Returns:
            Dictionary with context sources:
            - orientation_content: Content of orientation.md
            - spec_content: Content of the source spec (if exists)
            - system_plan: SYSTEM-PLAN.md content (if exists)
            - agent_instructions: CLAUDE.md content (if exists)
        """
        context: dict[str, str | None] = {
            "orientation_content": None,
            "spec_content": None,
            "system_plan": None,
            "agent_instructions": None,
        }

        # Read orientation content
        context["orientation_content"] = self._read_orientation()

        # Read spec content
        if self.ctx.has_spec and self.ctx.spec_path and self.ctx.spec_path.exists():
            try:
                context["spec_content"] = self.ctx.read_spec_content()
            except Exception:
                pass  # Non-fatal

        # Read SYSTEM-PLAN.md
        context["system_plan"] = self.ctx.read_system_plan()

        # Read agent instructions
        context["agent_instructions"] = self.ctx.read_agent_instructions()

        return context

    def _extract_from_orientation(self, orientation_content: str) -> dict[str, object]:
        """
        Extract information from the orientation.md content.

        Args:
            orientation_content: Content of orientation.md.

        Returns:
            Dictionary with extracted information.
        """
        import re

        extracted: dict[str, object] = {
            "title": None,
            "problem_statement": None,
            "requirements_p0": [],
            "requirements_p1": [],
            "constraints": [],
            "mvp_scope": [],
        }

        # Extract title from first heading
        title_match = re.search(r"^#\s+Orientation:\s*(.+)$", orientation_content, re.MULTILINE)
        if title_match:
            extracted["title"] = title_match.group(1).strip()

        # Extract problem statement
        problem_match = re.search(
            r"##\s+Problem Statement\s*\n([\s\S]*?)(?=\n##|\Z)",
            orientation_content,
            re.IGNORECASE,
        )
        if problem_match:
            extracted["problem_statement"] = problem_match.group(1).strip()

        # Extract P0 requirements
        p0_match = re.search(
            r"###\s+P0[^\n]*\n([\s\S]*?)(?=\n###|\n##|\Z)",
            orientation_content,
            re.IGNORECASE,
        )
        if p0_match:
            p0_content = p0_match.group(1)
            requirements = re.findall(r"^[-*]\s+\*?\*?([^*\n]+)", p0_content, re.MULTILINE)
            if requirements:
                extracted["requirements_p0"] = [r.strip() for r in requirements]

        # Extract constraints from table
        constraints_match = re.search(
            r"##\s+Constraints\s*\n([\s\S]*?)(?=\n##|\Z)",
            orientation_content,
            re.IGNORECASE,
        )
        if constraints_match:
            constraints_content = constraints_match.group(1)
            # Parse table rows
            table_rows = re.findall(
                r"^\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|",
                constraints_content,
                re.MULTILINE,
            )
            constraints = []
            for name, detail in table_rows:
                name = name.strip()
                detail = detail.strip()
                if name and name != "Constraint" and not name.startswith("-"):
                    constraints.append(f"{name}: {detail}")
            extracted["constraints"] = constraints

        # Extract MVP scope
        mvp_match = re.search(
            r"##\s+MVP Boundary\s*\n([\s\S]*?)(?=\n##|\Z)",
            orientation_content,
            re.IGNORECASE,
        )
        if mvp_match:
            mvp_content = mvp_match.group(1)
            # Look for "In scope" items
            in_scope_match = re.search(
                r"\*\*In scope[^*]*\*\*:?\s*\n([\s\S]*?)(?=\n\*\*|\Z)",
                mvp_content,
                re.IGNORECASE,
            )
            if in_scope_match:
                scope_items = re.findall(r"^[-*]\s+(.+)$", in_scope_match.group(1), re.MULTILINE)
                if scope_items:
                    extracted["mvp_scope"] = [s.strip() for s in scope_items]

        return extracted

    def _infer_tech_stack(
        self,
        context: dict[str, str | None],
        extracted: dict[str, object],
    ) -> list[TechStackChoice]:
        """
        Infer technology stack from context.

        This analyzes agent instructions and project files to recommend
        a technology stack appropriate for the mindset and scale.

        Args:
            context: Gathered project context.
            extracted: Information extracted from orientation.

        Returns:
            List of technology stack choices.
        """
        stack: list[TechStackChoice] = []
        agent_instructions = context.get("agent_instructions") or ""

        # Detect Python version from context
        if "python 3.10" in agent_instructions.lower():
            stack.append(TechStackChoice(
                layer="Language",
                choice="Python 3.10+",
                rationale="Project requirement from AGENT.md",
            ))
        elif "python" in agent_instructions.lower():
            stack.append(TechStackChoice(
                layer="Language",
                choice="Python 3.11+",
                rationale="Modern Python with type hints support",
            ))

        # Detect frameworks
        if "typer" in agent_instructions.lower():
            stack.append(TechStackChoice(
                layer="CLI Framework",
                choice="Typer",
                rationale="Type-safe CLI framework, project standard",
            ))
        if "pydantic" in agent_instructions.lower():
            stack.append(TechStackChoice(
                layer="Data Models",
                choice="Pydantic v2",
                rationale="Validation and serialization, project standard",
            ))
        if "rich" in agent_instructions.lower():
            stack.append(TechStackChoice(
                layer="Terminal UI",
                choice="Rich",
                rationale="Progress bars, tables, colored output",
            ))

        # Detect testing tools
        if "pytest" in agent_instructions.lower():
            stack.append(TechStackChoice(
                layer="Testing",
                choice="pytest",
                rationale="Standard Python testing framework",
            ))
        if "mypy" in agent_instructions.lower():
            stack.append(TechStackChoice(
                layer="Type Checking",
                choice="mypy (strict)",
                rationale="Static type checking, project requirement",
            ))

        # Add mindset-appropriate defaults if stack is minimal
        if not stack:
            if self.mindset == "prototype":
                stack = [
                    TechStackChoice("Language", "Python 3.11+", "Rapid development"),
                    TechStackChoice("Database", "SQLite or JSON files", "Simple, no setup"),
                ]
            elif self.mindset == "mvp":
                stack = [
                    TechStackChoice("Language", "Python 3.11+", "Balance of speed and quality"),
                    TechStackChoice("Framework", "FastAPI or Typer", "Quick to build, good DX"),
                    TechStackChoice("Database", "SQLite/PostgreSQL", "Depends on needs"),
                    TechStackChoice("Testing", "pytest", "Standard Python testing"),
                ]
            elif self.mindset == "production":
                stack = [
                    TechStackChoice("Language", "Python 3.11+", "Stable, well-supported"),
                    TechStackChoice("Framework", "FastAPI", "Async, OpenAPI generation"),
                    TechStackChoice("Database", "PostgreSQL", "ACID compliance, scalable"),
                    TechStackChoice("Testing", "pytest + coverage", "Comprehensive testing"),
                    TechStackChoice("Type Checking", "mypy (strict)", "Type safety"),
                ]
            elif self.mindset == "enterprise":
                stack = [
                    TechStackChoice("Language", "Python 3.11+", "Enterprise support available"),
                    TechStackChoice("Framework", "FastAPI", "Security, async, documentation"),
                    TechStackChoice("Database", "PostgreSQL", "Compliance, audit, reliability"),
                    TechStackChoice("Cache", "Redis", "Session management, rate limiting"),
                    TechStackChoice("Testing", "pytest + coverage", "High coverage required"),
                    TechStackChoice("Type Checking", "mypy (strict)", "Type safety enforced"),
                    TechStackChoice("Monitoring", "OpenTelemetry", "Observability, audit trails"),
                ]

        return stack

    def _generate_components(
        self,
        extracted: dict[str, object],
    ) -> list[Component]:
        """
        Generate component list based on requirements.

        Args:
            extracted: Information extracted from orientation.

        Returns:
            List of components.
        """
        components: list[Component] = []

        # Base component structure depends on mindset
        if self.mindset == "prototype":
            components = [
                Component(
                    name="Main Module",
                    purpose="Core application logic",
                    responsibilities=["All functionality in minimal structure"],
                    dependencies=[],
                    interface="CLI or direct import",
                ),
            ]
        else:
            # MVP and above get modular structure
            components = [
                Component(
                    name="Core Logic",
                    purpose="Business logic and domain operations",
                    responsibilities=[
                        "Domain models",
                        "Business rules",
                        "Data validation",
                    ],
                    dependencies=["Data layer"],
                    interface="Internal Python module",
                ),
                Component(
                    name="Interface Layer",
                    purpose="User-facing interface (CLI/API)",
                    responsibilities=[
                        "Command/request handling",
                        "Input validation",
                        "Output formatting",
                    ],
                    dependencies=["Core Logic"],
                    interface="CLI commands or REST API",
                ),
            ]

            if self.mindset in ("production", "enterprise"):
                components.append(
                    Component(
                        name="Data Layer",
                        purpose="Data persistence and retrieval",
                        responsibilities=[
                            "Database operations",
                            "Data migrations",
                            "Query optimization",
                        ],
                        dependencies=["Database"],
                        interface="Repository pattern",
                    )
                )

        return components

    def _generate_phases(
        self,
        extracted: dict[str, object],
    ) -> list[ImplementationPhase]:
        """
        Generate implementation phases.

        Args:
            extracted: Information extracted from orientation.

        Returns:
            List of implementation phases.
        """
        phases: list[ImplementationPhase] = []

        # Phase 1: Foundation - always needed
        phase1_tasks = [
            "Project setup and configuration",
            "Basic project structure",
        ]
        if self.mindset != "prototype":
            phase1_tasks.extend([
                "Test infrastructure setup",
                "CI/CD pipeline (if applicable)",
            ])

        phases.append(ImplementationPhase(
            number=1,
            name="Foundation",
            goal="Basic infrastructure and project setup",
            tasks=phase1_tasks,
        ))

        # Phase 2: Core Features - MVP scope
        mvp_scope = extracted.get("mvp_scope", [])
        if isinstance(mvp_scope, list) and mvp_scope:
            core_tasks = [str(item) for item in mvp_scope[:5]]
        else:
            core_tasks = ["Core functionality implementation"]

        phases.append(ImplementationPhase(
            number=2,
            name="Core Features",
            goal="Implement MVP functionality",
            tasks=core_tasks,
        ))

        # Phase 3: Polish - production and enterprise
        if self.mindset in ("mvp", "production", "enterprise"):
            polish_tasks = [
                "Error handling improvements",
                "Documentation",
            ]
            if self.mindset in ("production", "enterprise"):
                polish_tasks.extend([
                    "Performance optimization",
                    "Security hardening",
                ])
            phases.append(ImplementationPhase(
                number=3,
                name="Polish",
                goal="Production readiness",
                tasks=polish_tasks,
            ))

        return phases

    def _generate_architecture(
        self,
        context: dict[str, str | None],
        extracted: dict[str, object],
        tech_stack: list[TechStackChoice],
        components: list[Component],
        phases: list[ImplementationPhase],
    ) -> str:
        """
        Generate the architecture.md content.

        Args:
            context: Gathered project context.
            extracted: Information extracted from orientation.
            tech_stack: Technology stack choices.
            components: System components.
            phases: Implementation phases.

        Returns:
            Generated architecture.md content.
        """
        now = datetime.now(timezone.utc)
        title = extracted.get("title") or self.ctx.plan.slug
        problem = extracted.get("problem_statement") or ""

        lines = [
            f"# Architecture Design: {title}",
            "",
            f"**Date:** {now.strftime('%Y-%m-%d')}",
            f"**Mindset:** {self.mindset}",
            f"**Scale:** {self.scale}",
            "**Status:** Ready for Review",
            "",
            "---",
            "",
        ]

        # Technical Summary
        lines.extend([
            "## Technical Summary",
            "",
        ])
        if problem and isinstance(problem, str):
            # Generate summary from problem statement
            summary_lines = problem.split("\n")
            summary = " ".join(line.strip() for line in summary_lines[:3] if line.strip())
            if len(summary) > 500:
                summary = summary[:500] + "..."
            lines.append(summary)
        else:
            lines.append("*Technical summary to be determined based on requirements.*")
        lines.append("")
        lines.append(
            f"This architecture follows a **{self.mindset}** mindset targeting "
            f"**{self.scale}** scale usage."
        )
        lines.append("")

        # Technology Stack
        lines.extend([
            "## Technology Stack",
            "",
            "| Layer | Choice | Rationale |",
            "|-------|--------|-----------|",
        ])
        if tech_stack:
            for choice in tech_stack:
                lines.append(f"| {choice.layer} | {choice.choice} | {choice.rationale} |")
        else:
            lines.append("| *TBD* | *TBD* | *To be determined* |")
        lines.append("")

        # System Architecture (ASCII diagram)
        lines.extend([
            "## System Architecture",
            "",
            "```",
        ])
        if len(components) == 1:
            # Simple single-module architecture
            lines.extend([
                "+---------------------------+",
                f"|      {components[0].name:^17} |",
                "+---------------------------+",
            ])
        else:
            # Multi-component architecture
            lines.extend([
                "+---------------------------+",
                "|     Interface Layer       |",
                "|      (CLI / API)          |",
                "+-----------+---------------+",
                "            |",
                "            v",
                "+---------------------------+",
                "|      Core Logic           |",
                "|   (Business Operations)   |",
                "+---------------------------+",
            ])
            if self.mindset in ("production", "enterprise"):
                lines.extend([
                    "            |",
                    "            v",
                    "+---------------------------+",
                    "|      Data Layer           |",
                    "|    (Persistence)          |",
                    "+---------------------------+",
                ])
        lines.extend([
            "```",
            "",
        ])

        # Components
        lines.extend([
            "## Components",
            "",
        ])
        for comp in components:
            lines.extend([
                f"### {comp.name}",
                f"- **Purpose:** {comp.purpose}",
                "- **Responsibilities:**",
            ])
            for resp in comp.responsibilities:
                lines.append(f"  - {resp}")
            if comp.dependencies:
                lines.append(f"- **Dependencies:** {', '.join(comp.dependencies)}")
            lines.append(f"- **Interface:** {comp.interface}")
            lines.append("")

        # Data Model (placeholder)
        lines.extend([
            "## Data Model",
            "",
            "*Data model entities to be defined based on requirements:*",
            "",
        ])
        requirements = extracted.get("requirements_p0", [])
        if isinstance(requirements, list) and requirements:
            lines.append("Based on P0 requirements, key entities may include:")
            lines.append("")
            for req in requirements[:3]:
                # Try to extract nouns as potential entities
                entity = str(req).split()[0] if req else "Entity"
                lines.append(f"- **{entity}**: *To be specified*")
        else:
            lines.append("- *Entities to be defined*")
        lines.append("")

        # APIs / Interfaces
        lines.extend([
            "## APIs / Interfaces",
            "",
        ])
        if "cli" in str(tech_stack).lower() or "typer" in str(tech_stack).lower():
            lines.extend([
                "### CLI Commands",
                "- **Type:** Command-line interface",
                "- **Purpose:** User interaction",
                "- **Key Commands:** *To be defined based on requirements*",
                "",
            ])
        else:
            lines.extend([
                "### Primary Interface",
                "- **Type:** *TBD (CLI/REST/GraphQL)*",
                "- **Purpose:** User/system interaction",
                "- **Key Endpoints/Commands:** *To be defined*",
                "",
            ])

        # Implementation Phases
        lines.extend([
            "## Implementation Phases",
            "",
        ])
        for phase in phases:
            lines.extend([
                f"### Phase {phase.number}: {phase.name}",
                f"**Goal:** {phase.goal}",
                "",
            ])
            for task in phase.tasks:
                lines.append(f"- {task}")
            lines.append("")

        # Technical Risks
        lines.extend([
            "## Technical Risks",
            "",
            "| Risk | Impact | Likelihood | Mitigation |",
            "|------|--------|------------|------------|",
        ])
        # Generate standard risks based on mindset
        if self.mindset == "prototype":
            lines.append(
                "| Code quality debt | M | H | Acknowledge as acceptable for prototype |"
            )
        elif self.mindset in ("mvp", "production"):
            lines.extend([
                "| Scope creep | H | M | Strict MVP boundary enforcement |",
                "| Technical debt | M | M | Schedule refactoring time |",
            ])
        if self.mindset == "enterprise":
            lines.extend([
                "| Security vulnerabilities | H | M | Security review, penetration testing |",
                "| Compliance gaps | H | L | Early compliance audit |",
            ])
        lines.append("")

        # Dependencies
        lines.extend([
            "## Dependencies",
            "",
            "### External",
            "",
        ])
        external_deps = [
            choice.choice for choice in tech_stack if "database" in choice.layer.lower()
        ]
        if external_deps:
            for dep in external_deps:
                lines.append(f"- {dep}")
        else:
            lines.append("- *External dependencies to be identified*")
        lines.extend([
            "",
            "### Internal",
            "",
            "- orientation.md requirements",
            "",
        ])

        # Security Considerations (for production/enterprise)
        if self.mindset in ("production", "enterprise"):
            lines.extend([
                "## Security Considerations",
                "",
            ])
            if self.mindset == "enterprise":
                lines.extend([
                    "- Input validation on all endpoints",
                    "- Authentication and authorization",
                    "- Encryption at rest and in transit",
                    "- Audit logging for compliance",
                    "- Regular security scanning",
                ])
            else:
                lines.extend([
                    "- Input validation",
                    "- Proper error handling (no sensitive data in errors)",
                    "- HTTPS in production",
                ])
            lines.append("")

        # Future Considerations
        lines.extend([
            "## Future Considerations",
            "",
            "- *Features deferred from MVP*",
            "- *Scalability improvements*",
            "- *Additional integrations*",
            "",
            "---",
            "",
            "**Status**: Ready for Itemize phase",
            "",
        ])

        return "\n".join(lines)

    def run(self) -> ArchitectResult:
        """
        Run the architect stage.

        This method:
        1. Validates prerequisites
        2. Reads orientation.md
        3. Gathers project context
        4. Extracts information from orientation
        5. Generates technology stack recommendations
        6. Generates component design
        7. Generates implementation phases
        8. Produces architecture.md
        9. Updates plan status

        Returns:
            ArchitectResult with output path and design information.

        Raises:
            ArchitectStageError: If stage fails to run.
        """
        started_at = datetime.now(timezone.utc)

        # Validate prerequisites
        self.validate()

        # Mark stage as in progress
        self.ctx.plan.start_stage(PlanStage.ARCHITECT)
        self.ctx.ensure_plan_dir()
        self.ctx.save_plan()

        # Gather context
        context = self._gather_context()

        # Extract from orientation
        orientation_content = context.get("orientation_content") or ""
        extracted = self._extract_from_orientation(orientation_content)

        # Generate design elements
        tech_stack = self._infer_tech_stack(context, extracted)
        components = self._generate_components(extracted)
        phases = self._generate_phases(extracted)

        # Generate architecture document
        architecture_content = self._generate_architecture(
            context, extracted, tech_stack, components, phases
        )

        # Write architecture.md
        output_path = self.ctx.architecture_path
        try:
            output_path.write_text(architecture_content, encoding="utf-8")
        except OSError as e:
            raise ArchitectStageError(
                f"Cannot write architecture file {output_path}: {e}"
            ) from e

        # Mark stage as complete
        self.ctx.plan.complete_stage(PlanStage.ARCHITECT)
        try:
            self.ctx.save_plan()
        except (OSError, ValueError) as e:
            raise ArchitectStageError(
                f"Cannot save plan after architect stage: {e}"
            ) from e

        completed_at = datetime.now(timezone.utc)

        # Generate technical risks for result
        technical_risks: list[TechnicalRisk] = []
        if self.mindset == "prototype":
            technical_risks.append(TechnicalRisk(
                risk="Code quality debt",
                impact="Medium",
                likelihood="High",
                mitigation="Acceptable for prototype",
            ))
        else:
            technical_risks.append(TechnicalRisk(
                risk="Scope creep",
                impact="High",
                likelihood="Medium",
                mitigation="Strict MVP boundary",
            ))

        # Build result
        return ArchitectResult(
            output_path=output_path,
            technical_summary=str(extracted.get("problem_statement") or ""),
            tech_stack=tech_stack,
            components=components,
            implementation_phases=phases,
            technical_risks=technical_risks,
            mindset=self.mindset,
            scale=self.scale,
            started_at=started_at,
            completed_at=completed_at,
        )


def run_architect(
    ctx: PlanContext,
    mindset: str = "mvp",
    scale: str = "team",
) -> ArchitectResult:
    """
    Convenience function to run the architect stage.

    Args:
        ctx: PlanContext for this planning session.
        mindset: Technical mindset (prototype/mvp/production/enterprise).
        scale: Expected usage scale (personal/team/product/internet-scale).

    Returns:
        ArchitectResult with output path and design information.
    """
    stage = ArchitectStage(ctx, mindset=mindset, scale=scale)
    return stage.run()
