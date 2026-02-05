"""
Learn service for extracting patterns and lessons from ledger data.

Provides high-level operations for:
- Analyzing ledger entries for patterns
- Identifying repeated failures, cost outliers, and lessons learned
- Suggesting updates to guardrails and agent instructions
"""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PatternCategory(str, Enum):
    """Categories of patterns that can be detected."""

    REPEATED_FAILURE = "repeated_failure"  # Same error category appearing multiple times
    COST_OUTLIER = "cost_outlier"  # Tasks with unusually high costs
    DURATION_OUTLIER = "duration_outlier"  # Tasks taking unusually long
    ESCALATION_PATTERN = "escalation_pattern"  # Frequent escalations
    SUCCESS_PATTERN = "success_pattern"  # Patterns in successful tasks
    LESSON_LEARNED = "lesson_learned"  # Explicit lessons from task outcomes


class SuggestionTarget(str, Enum):
    """Where a suggestion should be applied."""

    GUARDRAILS = "guardrails"  # .cub/guardrails.md or similar
    CLAUDE_MD = "claude_md"  # CLAUDE.md / agent.md
    CONSTITUTION = "constitution"  # .cub/constitution.md


class LearnServiceError(Exception):
    """Error from learn service operations."""

    pass


@dataclass
class Pattern:
    """
    A detected pattern from ledger analysis.

    Represents a recurring theme, issue, or insight discovered
    by analyzing task execution history.
    """

    category: PatternCategory
    description: str
    evidence: list[str]  # Task IDs or specific examples
    frequency: int  # How many times observed
    confidence: float  # 0.0-1.0, how confident we are in this pattern
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)

    def __str__(self) -> str:
        """Format pattern as human-readable string."""
        return f"[{self.category.value}] {self.description} (seen {self.frequency}x)"


@dataclass
class Suggestion:
    """
    A suggested update based on pattern analysis.

    Represents an actionable change that could improve future task execution.
    """

    target: SuggestionTarget
    section: str  # Where in the target file to add this
    content: str  # The actual content to add
    rationale: str  # Why this is suggested
    patterns: list[Pattern]  # Patterns that led to this suggestion
    priority: int = 1  # 1 = high, 2 = medium, 3 = low

    def __str__(self) -> str:
        """Format suggestion as human-readable string."""
        return f"[{self.target.value}:{self.section}] {self.content[:50]}..."


@dataclass
class LearnResult:
    """
    Result of a learn extraction operation.

    Contains detected patterns and suggested updates.
    """

    patterns: list[Pattern] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)
    entries_analyzed: int = 0
    time_range_days: int = 0

    # Applied changes tracking
    changes_applied: int = 0
    files_modified: list[str] = field(default_factory=list)

    @property
    def has_patterns(self) -> bool:
        """Check if any patterns were detected."""
        return len(self.patterns) > 0

    @property
    def has_suggestions(self) -> bool:
        """Check if any suggestions were generated."""
        return len(self.suggestions) > 0

    def to_markdown(self) -> str:
        """
        Generate markdown representation of the result.

        Returns:
            Formatted markdown string
        """
        lines: list[str] = []

        # Header
        lines.append("# Learn Extract Results")
        lines.append("")
        lines.append(f"**Entries Analyzed:** {self.entries_analyzed}")
        lines.append(f"**Time Range:** {self.time_range_days} days")
        lines.append("")

        # Patterns
        if self.patterns:
            lines.append("## Detected Patterns")
            lines.append("")

            # Group by category
            by_category: dict[PatternCategory, list[Pattern]] = {}
            for pattern in self.patterns:
                if pattern.category not in by_category:
                    by_category[pattern.category] = []
                by_category[pattern.category].append(pattern)

            for category, patterns in by_category.items():
                lines.append(f"### {category.value.replace('_', ' ').title()}")
                lines.append("")
                for pattern in patterns:
                    lines.append(f"- **{pattern.description}**")
                    lines.append(f"  - Frequency: {pattern.frequency}")
                    lines.append(f"  - Confidence: {pattern.confidence:.0%}")
                    if pattern.evidence:
                        evidence_str = ", ".join(pattern.evidence[:5])
                        if len(pattern.evidence) > 5:
                            evidence_str += f" (+{len(pattern.evidence) - 5} more)"
                        lines.append(f"  - Evidence: {evidence_str}")
                lines.append("")
        else:
            lines.append("## Detected Patterns")
            lines.append("")
            lines.append("No significant patterns detected.")
            lines.append("")

        # Suggestions
        if self.suggestions:
            lines.append("## Suggested Updates")
            lines.append("")
            for i, suggestion in enumerate(self.suggestions, 1):
                priority_label = {1: "High", 2: "Medium", 3: "Low"}.get(
                    suggestion.priority, "Medium"
                )
                lines.append(f"### {i}. [{priority_label}] {suggestion.target.value}")
                lines.append("")
                lines.append(f"**Section:** {suggestion.section}")
                lines.append("")
                lines.append("**Suggested content:**")
                lines.append("```")
                lines.append(suggestion.content)
                lines.append("```")
                lines.append("")
                lines.append(f"**Rationale:** {suggestion.rationale}")
                lines.append("")
        else:
            lines.append("## Suggested Updates")
            lines.append("")
            lines.append("No suggestions at this time.")
            lines.append("")

        # Applied changes
        if self.changes_applied > 0:
            lines.append("## Applied Changes")
            lines.append("")
            lines.append(f"**Changes Applied:** {self.changes_applied}")
            if self.files_modified:
                lines.append("**Files Modified:**")
                for file_path in self.files_modified:
                    lines.append(f"- {file_path}")
            lines.append("")

        return "\n".join(lines)


class LearnService:
    """
    Service for extracting patterns and lessons from ledger data.

    Provides high-level operations for:
    - Analyzing ledger entries for patterns
    - Identifying repeated failures, cost outliers, and lessons learned
    - Suggesting updates to guardrails and agent instructions

    Example:
        >>> service = LearnService(Path.cwd())
        >>> result = service.extract(since_days=30, dry_run=True)
        >>> print(result.to_markdown())
    """

    # Thresholds for pattern detection
    MIN_PATTERN_FREQUENCY = 2  # Minimum occurrences to consider a pattern
    COST_OUTLIER_STDDEV = 2.0  # Standard deviations above mean for cost outliers
    DURATION_OUTLIER_STDDEV = 2.0  # Standard deviations above mean for duration outliers
    MIN_CONFIDENCE = 0.6  # Minimum confidence to report a pattern

    def __init__(self, project_dir: Path | None = None) -> None:
        """
        Initialize LearnService.

        Args:
            project_dir: Project directory (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()
        self.cub_dir = self.project_dir / ".cub"
        self.ledger_dir = self.cub_dir / "ledger"
        self.agent_md = self.cub_dir / "agent.md"
        self.guardrails_md = self.cub_dir / "guardrails.md"
        self.constitution_md = self.cub_dir / "constitution.md"

    def extract(
        self,
        *,
        since_days: int | None = None,
        since_date: datetime | None = None,
        dry_run: bool = True,
    ) -> LearnResult:
        """
        Extract patterns and lessons from ledger entries.

        Args:
            since_days: Only analyze entries from the last N days
            since_date: Only analyze entries since this date
            dry_run: If True, don't modify any files (default)

        Returns:
            LearnResult containing patterns and suggestions

        Raises:
            LearnServiceError: If extraction fails
        """
        logger.info("Starting learn extraction")

        # Determine cutoff date
        cutoff_date: datetime | None = None
        if since_date:
            cutoff_date = since_date
        elif since_days:
            cutoff_date = datetime.utcnow() - timedelta(days=since_days)

        # Load ledger entries
        entries = self._load_entries(cutoff_date)
        if not entries:
            logger.info("No entries found for analysis")
            return LearnResult(
                entries_analyzed=0,
                time_range_days=since_days or 0,
            )

        # Calculate time range
        time_range_days = self._calculate_time_range(entries)

        # Detect patterns
        patterns: list[Pattern] = []
        patterns.extend(self._detect_failure_patterns(entries))
        patterns.extend(self._detect_cost_outliers(entries))
        patterns.extend(self._detect_duration_outliers(entries))
        patterns.extend(self._detect_escalation_patterns(entries))
        patterns.extend(self._extract_lessons_learned(entries))

        # Generate suggestions
        suggestions = self._generate_suggestions(patterns)

        # Create result
        result = LearnResult(
            patterns=patterns,
            suggestions=suggestions,
            entries_analyzed=len(entries),
            time_range_days=time_range_days,
        )

        # Apply changes if not dry run
        if not dry_run and suggestions:
            self._apply_suggestions(result, suggestions)

        return result

    def _load_entries(
        self, cutoff_date: datetime | None
    ) -> list[dict[str, str | int | float | list[str] | dict[str, str | int | float]]]:
        """
        Load ledger entries, optionally filtered by date.

        Args:
            cutoff_date: Only include entries after this date

        Returns:
            List of ledger entry dictionaries
        """
        entries: list[dict[str, str | int | float | list[str] | dict[str, str | int | float]]] = []

        # Load from by-task directory
        by_task_dir = self.ledger_dir / "by-task"
        if not by_task_dir.exists():
            logger.warning(f"Ledger by-task directory not found: {by_task_dir}")
            return entries

        for task_file in by_task_dir.glob("*.json"):
            try:
                with task_file.open("r") as f:
                    entry = json.load(f)

                # Filter by date if specified
                if cutoff_date:
                    completed_at = entry.get("completed_at")
                    if completed_at:
                        try:
                            entry_date = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                            # Make cutoff_date timezone-aware for comparison
                            cutoff_aware = cutoff_date.replace(tzinfo=entry_date.tzinfo)
                            if entry_date < cutoff_aware:
                                continue
                        except (ValueError, AttributeError):
                            pass

                entries.append(entry)

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse {task_file}: {e}")
            except Exception as e:
                logger.warning(f"Failed to load {task_file}: {e}")

        logger.info(f"Loaded {len(entries)} ledger entries")
        return entries

    def _calculate_time_range(
        self,
        entries: list[dict[str, str | int | float | list[str] | dict[str, str | int | float]]],
    ) -> int:
        """Calculate the time range covered by entries in days."""
        dates: list[datetime] = []

        for entry in entries:
            completed_at = entry.get("completed_at")
            if completed_at and isinstance(completed_at, str):
                try:
                    parsed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                    # Normalize to naive UTC for consistent comparison
                    if parsed.tzinfo is not None:
                        parsed = parsed.replace(tzinfo=None)
                    dates.append(parsed)
                except (ValueError, AttributeError):
                    pass

        if not dates:
            return 0

        min_date = min(dates)
        max_date = max(dates)
        return (max_date - min_date).days + 1

    def _detect_failure_patterns(
        self,
        entries: list[dict[str, str | int | float | list[str] | dict[str, str | int | float]]],
    ) -> list[Pattern]:
        """
        Detect repeated failure patterns.

        Looks for:
        - Same error categories appearing multiple times
        - Common failure modes across tasks
        """
        patterns: list[Pattern] = []

        # Collect error categories
        error_counts: dict[str, list[str]] = {}  # category -> task IDs

        for entry in entries:
            # Check attempts for failures
            attempts = entry.get("attempts", [])
            if isinstance(attempts, list):
                for attempt in attempts:
                    if isinstance(attempt, dict) and not attempt.get("success", True):
                        error_cat = attempt.get("error_category", "unknown")
                        if isinstance(error_cat, str):
                            task_id = entry.get("id", "unknown")
                            if isinstance(task_id, str):
                                if error_cat not in error_counts:
                                    error_counts[error_cat] = []
                                error_counts[error_cat].append(task_id)

        # Create patterns for repeated failures
        for error_cat, task_ids in error_counts.items():
            if len(task_ids) >= self.MIN_PATTERN_FREQUENCY:
                confidence = min(1.0, len(task_ids) / 10)  # Higher frequency = more confident
                patterns.append(
                    Pattern(
                        category=PatternCategory.REPEATED_FAILURE,
                        description=f"Repeated '{error_cat}' errors",
                        evidence=task_ids,
                        frequency=len(task_ids),
                        confidence=confidence,
                        metadata={"error_category": error_cat},
                    )
                )

        return patterns

    def _detect_cost_outliers(
        self,
        entries: list[dict[str, str | int | float | list[str] | dict[str, str | int | float]]],
    ) -> list[Pattern]:
        """
        Detect tasks with unusually high costs.

        Uses standard deviation to identify outliers.
        """
        patterns: list[Pattern] = []

        # Collect costs
        costs: list[tuple[str, float]] = []  # (task_id, cost)

        for entry in entries:
            cost = entry.get("cost_usd", 0.0)
            task_id = entry.get("id", "unknown")
            if isinstance(cost, (int, float)) and isinstance(task_id, str) and cost > 0:
                costs.append((task_id, float(cost)))

        if len(costs) < 3:  # Need enough data points
            return patterns

        # Calculate statistics
        cost_values = [c[1] for c in costs]
        mean_cost = statistics.mean(cost_values)
        try:
            stddev_cost = statistics.stdev(cost_values)
        except statistics.StatisticsError:
            return patterns

        if stddev_cost == 0:
            return patterns

        # Find outliers
        threshold = mean_cost + (self.COST_OUTLIER_STDDEV * stddev_cost)
        outliers = [(tid, c) for tid, c in costs if c > threshold]

        if outliers:
            patterns.append(
                Pattern(
                    category=PatternCategory.COST_OUTLIER,
                    description=f"Tasks with costs above ${threshold:.2f} (mean: ${mean_cost:.2f})",
                    evidence=[tid for tid, _ in outliers],
                    frequency=len(outliers),
                    confidence=0.8,
                    metadata={
                        "mean_cost": mean_cost,
                        "threshold": threshold,
                        "max_cost": max(c for _, c in outliers),
                    },
                )
            )

        return patterns

    def _detect_duration_outliers(
        self,
        entries: list[dict[str, str | int | float | list[str] | dict[str, str | int | float]]],
    ) -> list[Pattern]:
        """
        Detect tasks with unusually long durations.

        Uses standard deviation to identify outliers.
        """
        patterns: list[Pattern] = []

        # Collect durations
        durations: list[tuple[str, int]] = []  # (task_id, duration_seconds)

        for entry in entries:
            duration = entry.get("duration_seconds", 0)
            task_id = entry.get("id", "unknown")
            if isinstance(duration, int) and isinstance(task_id, str) and duration > 0:
                durations.append((task_id, duration))

        if len(durations) < 3:  # Need enough data points
            return patterns

        # Calculate statistics
        duration_values = [d[1] for d in durations]
        mean_duration = statistics.mean(duration_values)
        try:
            stddev_duration = statistics.stdev(duration_values)
        except statistics.StatisticsError:
            return patterns

        if stddev_duration == 0:
            return patterns

        # Find outliers
        threshold = mean_duration + (self.DURATION_OUTLIER_STDDEV * stddev_duration)
        outliers = [(tid, d) for tid, d in durations if d > threshold]

        if outliers:
            threshold_minutes = int(threshold / 60)
            mean_minutes = int(mean_duration / 60)
            desc = f"Tasks taking longer than {threshold_minutes}min (mean: {mean_minutes}min)"
            patterns.append(
                Pattern(
                    category=PatternCategory.DURATION_OUTLIER,
                    description=desc,
                    evidence=[tid for tid, _ in outliers],
                    frequency=len(outliers),
                    confidence=0.8,
                    metadata={
                        "mean_duration_seconds": mean_duration,
                        "threshold_seconds": threshold,
                        "max_duration_seconds": max(d for _, d in outliers),
                    },
                )
            )

        return patterns

    def _detect_escalation_patterns(
        self,
        entries: list[dict[str, str | int | float | list[str] | dict[str, str | int | float]]],
    ) -> list[Pattern]:
        """
        Detect patterns in task escalations.

        Looks for frequent escalations and common escalation triggers.
        """
        patterns: list[Pattern] = []

        # Collect escalation data
        escalated_tasks: list[str] = []
        total_tasks = len(entries)

        for entry in entries:
            outcome = entry.get("outcome", {})
            if isinstance(outcome, dict):
                if outcome.get("escalated", False):
                    task_id = entry.get("id", "unknown")
                    if isinstance(task_id, str):
                        escalated_tasks.append(task_id)

        if escalated_tasks and total_tasks > 0:
            escalation_rate = len(escalated_tasks) / total_tasks
            if escalation_rate > 0.1:  # More than 10% escalation rate
                desc = f"High escalation rate: {escalation_rate:.0%} of tasks escalated"
                patterns.append(
                    Pattern(
                        category=PatternCategory.ESCALATION_PATTERN,
                        description=desc,
                        evidence=escalated_tasks,
                        frequency=len(escalated_tasks),
                        confidence=min(1.0, escalation_rate * 2),
                        metadata={
                            "escalation_rate": escalation_rate,
                            "total_tasks": total_tasks,
                        },
                    )
                )

        return patterns

    def _extract_lessons_learned(
        self,
        entries: list[dict[str, str | int | float | list[str] | dict[str, str | int | float]]],
    ) -> list[Pattern]:
        """
        Extract explicit lessons learned from task outcomes.

        Collects and deduplicates lessons_learned fields from entries.
        """
        patterns: list[Pattern] = []

        # Collect all lessons
        lessons: dict[str, list[str]] = {}  # lesson -> task IDs

        for entry in entries:
            task_id = entry.get("id", "unknown")
            if not isinstance(task_id, str):
                task_id = "unknown"

            entry_lessons = entry.get("lessons_learned", [])
            if isinstance(entry_lessons, list):
                for lesson in entry_lessons:
                    if isinstance(lesson, str) and lesson.strip():
                        # Normalize lesson text for grouping
                        normalized = lesson.strip().lower()
                        if normalized not in lessons:
                            lessons[normalized] = []
                        lessons[normalized].append(task_id)

        # Create patterns for recurring lessons
        for lesson_text, task_ids in lessons.items():
            if len(task_ids) >= self.MIN_PATTERN_FREQUENCY:
                # Get original casing from first occurrence
                original = lesson_text
                for entry in entries:
                    entry_lessons = entry.get("lessons_learned", [])
                    if isinstance(entry_lessons, list):
                        for les in entry_lessons:
                            if isinstance(les, str) and les.strip().lower() == lesson_text:
                                original = les.strip()
                                break

                patterns.append(
                    Pattern(
                        category=PatternCategory.LESSON_LEARNED,
                        description=original,
                        evidence=task_ids,
                        frequency=len(task_ids),
                        confidence=min(1.0, len(task_ids) / 5),
                    )
                )

        return patterns

    def _generate_suggestions(self, patterns: list[Pattern]) -> list[Suggestion]:
        """
        Generate actionable suggestions from detected patterns.

        Converts patterns into specific updates for guardrails and agent docs.
        """
        suggestions: list[Suggestion] = []

        for pattern in patterns:
            if pattern.confidence < self.MIN_CONFIDENCE:
                continue

            if pattern.category == PatternCategory.REPEATED_FAILURE:
                error_cat = pattern.metadata.get("error_category", "unknown")
                suggestions.append(
                    Suggestion(
                        target=SuggestionTarget.GUARDRAILS,
                        section="Error Prevention",
                        content=f"- Avoid {error_cat} errors by validating inputs before execution",
                        rationale=f"'{error_cat}' errors occurred {pattern.frequency} times",
                        patterns=[pattern],
                        priority=1,
                    )
                )

            elif pattern.category == PatternCategory.COST_OUTLIER:
                threshold_raw = pattern.metadata.get("threshold", 0)
                threshold_cost = (
                    float(threshold_raw) if isinstance(threshold_raw, (int, float)) else 0
                )
                content = f"- Consider breaking down tasks that might exceed ${threshold_cost:.2f}"
                suggestions.append(
                    Suggestion(
                        target=SuggestionTarget.GUARDRAILS,
                        section="Cost Management",
                        content=content,
                        rationale=f"{pattern.frequency} tasks had unusually high costs",
                        patterns=[pattern],
                        priority=2,
                    )
                )

            elif pattern.category == PatternCategory.DURATION_OUTLIER:
                threshold_val = pattern.metadata.get("threshold_seconds", 0)
                threshold_min = (
                    float(threshold_val) / 60 if isinstance(threshold_val, (int, float)) else 0
                )
                content = (
                    f"- Break down tasks expected to take longer than {int(threshold_min)} minutes"
                )
                suggestions.append(
                    Suggestion(
                        target=SuggestionTarget.GUARDRAILS,
                        section="Task Complexity",
                        content=content,
                        rationale=f"{pattern.frequency} tasks took unusually long to complete",
                        patterns=[pattern],
                        priority=2,
                    )
                )

            elif pattern.category == PatternCategory.ESCALATION_PATTERN:
                rate_raw = pattern.metadata.get("escalation_rate", 0)
                rate = float(rate_raw) if isinstance(rate_raw, (int, float)) else 0
                content = (
                    f"- Note: {rate:.0%} of tasks have required escalation. "
                    "Consider starting complex tasks with a simpler model to reduce costs."
                )
                rationale = (
                    f"High escalation rate ({rate:.0%}) indicates tasks may be under-specified"
                )
                suggestions.append(
                    Suggestion(
                        target=SuggestionTarget.CLAUDE_MD,
                        section="Task Guidelines",
                        content=content,
                        rationale=rationale,
                        patterns=[pattern],
                        priority=1,
                    )
                )

            elif pattern.category == PatternCategory.LESSON_LEARNED:
                if pattern.frequency >= 3:  # Only suggest for frequently observed lessons
                    rationale = f"This lesson appeared in {pattern.frequency} task completions"
                    suggestions.append(
                        Suggestion(
                            target=SuggestionTarget.CLAUDE_MD,
                            section="Gotchas & Learnings",
                            content=f"- {pattern.description}",
                            rationale=rationale,
                            patterns=[pattern],
                            priority=3,
                        )
                    )

        # Sort by priority
        suggestions.sort(key=lambda s: s.priority)

        return suggestions

    def _apply_suggestions(self, result: LearnResult, suggestions: list[Suggestion]) -> None:
        """
        Apply suggestions to target files.

        Modifies guardrails.md and/or agent.md with suggested content.
        """
        # Group suggestions by target
        by_target: dict[SuggestionTarget, list[Suggestion]] = {}
        for suggestion in suggestions:
            if suggestion.target not in by_target:
                by_target[suggestion.target] = []
            by_target[suggestion.target].append(suggestion)

        # Apply to each target file
        for target, target_suggestions in by_target.items():
            target_file = self._get_target_file(target)
            if not target_file:
                continue

            try:
                if target_file.exists():
                    content = target_file.read_text()
                else:
                    content = self._create_initial_content(target)

                # Add suggestions
                new_content = self._merge_suggestions(content, target_suggestions)

                # Write if changed
                if new_content != content:
                    target_file.write_text(new_content)
                    result.changes_applied += len(target_suggestions)
                    result.files_modified.append(str(target_file))
                    logger.info(f"Applied {len(target_suggestions)} suggestions to {target_file}")

            except Exception as e:
                logger.error(f"Failed to apply suggestions to {target_file}: {e}")

    def _get_target_file(self, target: SuggestionTarget) -> Path | None:
        """Get the file path for a suggestion target."""
        if target == SuggestionTarget.GUARDRAILS:
            return self.guardrails_md
        elif target == SuggestionTarget.CLAUDE_MD:
            return self.agent_md
        elif target == SuggestionTarget.CONSTITUTION:
            return self.constitution_md
        return None

    def _create_initial_content(self, target: SuggestionTarget) -> str:
        """Create initial content for a new target file."""
        if target == SuggestionTarget.GUARDRAILS:
            return """# Guardrails

Guidelines and constraints for AI task execution.

## Error Prevention

## Cost Management

## Task Complexity

"""
        elif target == SuggestionTarget.CLAUDE_MD:
            return """# Agent Instructions

Guidelines for AI agents working on this project.

## Task Guidelines

## Gotchas & Learnings

"""
        return ""

    def _merge_suggestions(self, content: str, suggestions: list[Suggestion]) -> str:
        """
        Merge suggestions into existing content.

        Appends suggestions to appropriate sections, creating sections if needed.
        """
        lines = content.split("\n")

        # Group suggestions by section
        by_section: dict[str, list[Suggestion]] = {}
        for suggestion in suggestions:
            if suggestion.section not in by_section:
                by_section[suggestion.section] = []
            by_section[suggestion.section].append(suggestion)

        # Find or create sections and add suggestions
        result_lines = lines.copy()

        for section_name, section_suggestions in by_section.items():
            section_header = f"## {section_name}"
            section_idx = None

            # Find existing section
            for i, line in enumerate(result_lines):
                if line.strip() == section_header:
                    section_idx = i
                    break

            if section_idx is not None:
                # Find end of section (next ## or end of file)
                end_idx = len(result_lines)
                for i in range(section_idx + 1, len(result_lines)):
                    if result_lines[i].startswith("## "):
                        end_idx = i
                        break

                # Insert suggestions before next section
                insert_lines = [
                    "",
                    f"<!-- Added by learn extract on {datetime.utcnow().strftime('%Y-%m-%d')} -->",
                ]
                for suggestion in section_suggestions:
                    insert_lines.append(suggestion.content)

                result_lines = result_lines[:end_idx] + insert_lines + result_lines[end_idx:]
            else:
                # Create new section at end
                new_section = [
                    "",
                    section_header,
                    "",
                    f"<!-- Added by learn extract on {datetime.utcnow().strftime('%Y-%m-%d')} -->",
                ]
                for suggestion in section_suggestions:
                    new_section.append(suggestion.content)
                new_section.append("")

                result_lines.extend(new_section)

        return "\n".join(result_lines)
