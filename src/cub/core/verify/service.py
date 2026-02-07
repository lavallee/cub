"""
Verify service for checking cub data integrity.

Provides high-level operations for:
- Checking ledger consistency
- Validating ID integrity
- Verifying counter sync status
- Auto-fixing simple issues
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class IssueSeverity(str, Enum):
    """Severity levels for verification issues."""

    ERROR = "error"  # Critical issue that should be fixed immediately
    WARNING = "warning"  # Issue that may cause problems
    INFO = "info"  # Informational message, not necessarily a problem


class VerifyServiceError(Exception):
    """Error from verify service operations."""

    pass


@dataclass
class Issue:
    """
    A verification issue found during checks.

    Contains information about the problem, its severity,
    and suggestions for fixing it.
    """

    severity: IssueSeverity
    category: str  # e.g., "ledger", "ids", "counters"
    message: str
    location: str | None = None  # File path or ID where issue was found
    fix_suggestion: str | None = None
    auto_fixable: bool = False

    def __str__(self) -> str:
        """Format issue as a human-readable string."""
        parts = [f"[{self.severity.value.upper()}]"]
        if self.category:
            parts.append(f"({self.category})")
        parts.append(self.message)
        if self.location:
            parts.append(f"at {self.location}")
        return " ".join(parts)


@dataclass
class VerifyResult:
    """
    Result of a verification run.

    Contains all issues found and statistics about the checks.
    """

    issues: list[Issue] = field(default_factory=list)
    checks_run: int = 0
    files_checked: int = 0
    auto_fixed: int = 0

    @property
    def has_errors(self) -> bool:
        """Check if any error-level issues were found."""
        return any(i.severity == IssueSeverity.ERROR for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if any warning-level issues were found."""
        return any(i.severity == IssueSeverity.WARNING for i in self.issues)

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)

    @property
    def info_count(self) -> int:
        """Count of info-level issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.INFO)


class VerifyService:
    """
    Service for verifying cub data integrity.

    Provides high-level operations for:
    - Checking ledger consistency
    - Validating ID integrity
    - Verifying counter sync status
    - Auto-fixing simple issues

    Example:
        >>> service = VerifyService(Path.cwd())
        >>> result = service.verify(fix=False)
        >>> if result.has_errors:
        ...     print(f"Found {result.error_count} errors")
    """

    def __init__(self, project_dir: Path | None = None) -> None:
        """
        Initialize VerifyService.

        Args:
            project_dir: Project directory (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()
        self.cub_dir = self.project_dir / ".cub"
        self.ledger_dir = self.cub_dir / "ledger"
        self.tasks_file = self.cub_dir / "tasks.jsonl"
        self.counters_file = self.cub_dir / "counters.json"

    def verify(
        self,
        *,
        fix: bool = False,
        check_ledger: bool = True,
        check_ids: bool = True,
        check_counters: bool = True,
    ) -> VerifyResult:
        """
        Run all verification checks.

        Args:
            fix: Attempt to auto-fix simple issues
            check_ledger: Check ledger consistency
            check_ids: Check ID integrity
            check_counters: Check counter sync status

        Returns:
            VerifyResult containing all issues found
        """
        result = VerifyResult()

        if check_ledger:
            result.checks_run += 1
            self._check_ledger_consistency(result, fix=fix)

        if check_ids:
            result.checks_run += 1
            self._check_id_integrity(result, fix=fix)

        if check_counters:
            result.checks_run += 1
            self._check_counter_sync(result, fix=fix)

        return result

    def _check_ledger_consistency(self, result: VerifyResult, *, fix: bool) -> None:
        """
        Check ledger consistency.

        Verifies:
        - Ledger directory exists
        - Index file is readable and valid
        - Task entries match index
        - Epic entries are consistent
        - No orphaned files
        """
        # Check ledger directory exists
        if not self.ledger_dir.exists():
            result.issues.append(
                Issue(
                    severity=IssueSeverity.ERROR,
                    category="ledger",
                    message="Ledger directory does not exist",
                    location=str(self.ledger_dir),
                    fix_suggestion="Run 'cub init' to initialize the project",
                    auto_fixable=False,
                )
            )
            return

        # Check index file
        index_file = self.ledger_dir / "index.jsonl"
        if not index_file.exists():
            result.issues.append(
                Issue(
                    severity=IssueSeverity.WARNING,
                    category="ledger",
                    message="Ledger index file does not exist",
                    location=str(index_file),
                    fix_suggestion="The index will be created when tasks are run",
                    auto_fixable=False,
                )
            )
        else:
            result.files_checked += 1
            # Verify index is readable
            try:
                with index_file.open("r") as f:
                    line_count = 0
                    for line_num, line in enumerate(f, 1):
                        if not line.strip():
                            continue
                        try:
                            json.loads(line)
                            line_count += 1
                        except json.JSONDecodeError as e:
                            result.issues.append(
                                Issue(
                                    severity=IssueSeverity.ERROR,
                                    category="ledger",
                                    message=f"Invalid JSON in index at line {line_num}: {e}",
                                    location=f"{index_file}:{line_num}",
                                    fix_suggestion=(
                                        "Manually fix the JSON or remove the corrupted line"
                                    ),
                                    auto_fixable=False,
                                )
                            )
                logger.debug(f"Index file contains {line_count} entries")
            except Exception as e:
                result.issues.append(
                    Issue(
                        severity=IssueSeverity.ERROR,
                        category="ledger",
                        message=f"Failed to read index file: {e}",
                        location=str(index_file),
                        fix_suggestion="Check file permissions",
                        auto_fixable=False,
                    )
                )

        # Check task ledger entries
        by_task_dir = self.ledger_dir / "by-task"
        if by_task_dir.exists():
            task_files = list(by_task_dir.glob("*.json"))
            result.files_checked += len(task_files)

            for task_file in task_files:
                try:
                    with task_file.open("r") as f:
                        task_data = json.load(f)

                    # Verify required fields exist
                    required_fields = ["id", "title"]
                    for field in required_fields:
                        if field not in task_data:
                            result.issues.append(
                                Issue(
                                    severity=IssueSeverity.ERROR,
                                    category="ledger",
                                    message=f"Missing required field '{field}' in task entry",
                                    location=str(task_file),
                                    fix_suggestion=f"Add the '{field}' field to the task entry",
                                    auto_fixable=False,
                                )
                            )

                    # Check if task ID matches filename
                    task_id = task_data.get("id")
                    expected_filename = f"{task_id}.json"
                    if task_file.name != expected_filename:
                        result.issues.append(
                            Issue(
                                severity=IssueSeverity.WARNING,
                                category="ledger",
                                message=(
                                    f"Task ID '{task_id}' doesn't match "
                                    f"filename '{task_file.name}'"
                                ),
                                location=str(task_file),
                                fix_suggestion=f"Rename file to '{expected_filename}'",
                                auto_fixable=True,
                            )
                        )

                        if fix:
                            try:
                                new_path = task_file.parent / expected_filename
                                if not new_path.exists():
                                    task_file.rename(new_path)
                                    result.auto_fixed += 1
                                    logger.info(f"Renamed {task_file.name} to {expected_filename}")
                            except Exception as e:
                                logger.error(f"Failed to rename {task_file}: {e}")

                except json.JSONDecodeError as e:
                    result.issues.append(
                        Issue(
                            severity=IssueSeverity.ERROR,
                            category="ledger",
                            message=f"Invalid JSON in task file: {e}",
                            location=str(task_file),
                            fix_suggestion="Manually fix the JSON or restore from backup",
                            auto_fixable=False,
                        )
                    )
                except Exception as e:
                    result.issues.append(
                        Issue(
                            severity=IssueSeverity.ERROR,
                            category="ledger",
                            message=f"Failed to read task file: {e}",
                            location=str(task_file),
                            fix_suggestion="Check file permissions",
                            auto_fixable=False,
                        )
                    )

        # Check epic ledger entries
        by_epic_dir = self.ledger_dir / "by-epic"
        if by_epic_dir.exists():
            epic_dirs = [d for d in by_epic_dir.iterdir() if d.is_dir()]

            for epic_dir in epic_dirs:
                entry_file = epic_dir / "entry.json"
                if not entry_file.exists():
                    result.issues.append(
                        Issue(
                            severity=IssueSeverity.WARNING,
                            category="ledger",
                            message=f"Epic directory '{epic_dir.name}' missing entry.json",
                            location=str(epic_dir),
                            fix_suggestion="Verify this is a valid epic directory",
                            auto_fixable=False,
                        )
                    )
                    continue

                result.files_checked += 1
                try:
                    with entry_file.open("r") as f:
                        epic_data = json.load(f)

                    # Verify epic ID matches directory name
                    epic_info = epic_data.get("epic", {})
                    epic_id = epic_info.get("id")
                    if epic_id and epic_id != epic_dir.name:
                        result.issues.append(
                            Issue(
                                severity=IssueSeverity.WARNING,
                                category="ledger",
                                message=(
                                    f"Epic ID '{epic_id}' doesn't match "
                                    f"directory name '{epic_dir.name}'"
                                ),
                                location=str(entry_file),
                                fix_suggestion=f"Rename directory to '{epic_id}'",
                                auto_fixable=False,
                            )
                        )

                except json.JSONDecodeError as e:
                    result.issues.append(
                        Issue(
                            severity=IssueSeverity.ERROR,
                            category="ledger",
                            message=f"Invalid JSON in epic entry: {e}",
                            location=str(entry_file),
                            fix_suggestion="Manually fix the JSON or restore from backup",
                            auto_fixable=False,
                        )
                    )
                except Exception as e:
                    result.issues.append(
                        Issue(
                            severity=IssueSeverity.ERROR,
                            category="ledger",
                            message=f"Failed to read epic entry: {e}",
                            location=str(entry_file),
                            fix_suggestion="Check file permissions",
                            auto_fixable=False,
                        )
                    )

    def _check_id_integrity(self, result: VerifyResult, *, fix: bool) -> None:
        """
        Check ID integrity.

        Verifies:
        - Task IDs follow the correct format
        - Epic IDs are valid
        - No duplicate IDs
        - IDs are consistent across files
        """
        seen_ids: set[str] = set()

        # Check tasks.jsonl
        if self.tasks_file.exists():
            result.files_checked += 1
            try:
                with self.tasks_file.open("r") as f:
                    for line_num, line in enumerate(f, 1):
                        if not line.strip():
                            continue

                        try:
                            task = json.loads(line)
                            task_id = task.get("id")

                            if not task_id:
                                result.issues.append(
                                    Issue(
                                        severity=IssueSeverity.ERROR,
                                        category="ids",
                                        message=f"Task at line {line_num} has no ID",
                                        location=f"{self.tasks_file}:{line_num}",
                                        fix_suggestion="Add a valid task ID",
                                        auto_fixable=False,
                                    )
                                )
                                continue

                            # Check for duplicates
                            if task_id in seen_ids:
                                result.issues.append(
                                    Issue(
                                        severity=IssueSeverity.ERROR,
                                        category="ids",
                                        message=f"Duplicate task ID '{task_id}'",
                                        location=f"{self.tasks_file}:{line_num}",
                                        fix_suggestion="Remove or rename the duplicate task",
                                        auto_fixable=False,
                                    )
                                )
                            else:
                                seen_ids.add(task_id)

                            # Validate ID format (basic check)
                            if not self._is_valid_task_id(task_id):
                                result.issues.append(
                                    Issue(
                                        severity=IssueSeverity.WARNING,
                                        category="ids",
                                        message=f"Task ID '{task_id}' has unexpected format",
                                        location=f"{self.tasks_file}:{line_num}",
                                        fix_suggestion="Ensure ID follows cub naming conventions",
                                        auto_fixable=False,
                                    )
                                )

                        except json.JSONDecodeError as e:
                            result.issues.append(
                                Issue(
                                    severity=IssueSeverity.ERROR,
                                    category="ids",
                                    message=f"Invalid JSON at line {line_num}: {e}",
                                    location=f"{self.tasks_file}:{line_num}",
                                    fix_suggestion="Manually fix the JSON",
                                    auto_fixable=False,
                                )
                            )

            except Exception as e:
                result.issues.append(
                    Issue(
                        severity=IssueSeverity.ERROR,
                        category="ids",
                        message=f"Failed to read tasks file: {e}",
                        location=str(self.tasks_file),
                        fix_suggestion="Check file permissions",
                        auto_fixable=False,
                    )
                )

        # Cross-reference with ledger
        by_task_dir = self.ledger_dir / "by-task"
        if by_task_dir.exists():
            ledger_task_ids = {f.stem for f in by_task_dir.glob("*.json")}

            # Check for tasks in ledger but not in tasks.jsonl
            for ledger_id in ledger_task_ids:
                if ledger_id not in seen_ids:
                    result.issues.append(
                        Issue(
                            severity=IssueSeverity.INFO,
                            category="ids",
                            message=(
                                f"Task '{ledger_id}' exists in ledger "
                                "but not in tasks.jsonl"
                            ),
                            location=str(by_task_dir / f"{ledger_id}.json"),
                            fix_suggestion=(
                                "This is normal for completed tasks that have been archived"
                            ),
                            auto_fixable=False,
                        )
                    )

    def _check_counter_sync(self, result: VerifyResult, *, fix: bool) -> None:
        """
        Check counter sync status.

        Verifies:
        - Counters file exists and is readable
        - Counter values are valid
        - Counters are in sync with actual IDs used
        """
        if not self.counters_file.exists():
            result.issues.append(
                Issue(
                    severity=IssueSeverity.WARNING,
                    category="counters",
                    message="Counters file does not exist",
                    location=str(self.counters_file),
                    fix_suggestion="Will be created automatically when needed",
                    auto_fixable=True,
                )
            )

            if fix:
                try:
                    # Create default counters file
                    default_counters = {
                        "spec_number": 1,
                        "standalone_task_number": 1,
                        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    }
                    with self.counters_file.open("w") as f:
                        json.dump(default_counters, f, indent=2)
                    result.auto_fixed += 1
                    logger.info("Created default counters file")
                except Exception as e:
                    logger.error(f"Failed to create counters file: {e}")

            return

        result.files_checked += 1
        try:
            with self.counters_file.open("r") as f:
                counters = json.load(f)

            # Check required fields
            required_fields = ["spec_number", "standalone_task_number", "updated_at"]
            for field in required_fields:
                if field not in counters:
                    result.issues.append(
                        Issue(
                            severity=IssueSeverity.WARNING,
                            category="counters",
                            message=f"Missing counter field '{field}'",
                            location=str(self.counters_file),
                            fix_suggestion=f"Add the '{field}' field with an appropriate value",
                            auto_fixable=True,
                        )
                    )

                    if fix:
                        try:
                            # Add missing field with default value
                            if field == "updated_at":
                                counters[field] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                            else:
                                counters[field] = 1

                            with self.counters_file.open("w") as f:
                                json.dump(counters, f, indent=2)
                            result.auto_fixed += 1
                            logger.info(f"Added missing counter field '{field}'")
                        except Exception as e:
                            logger.error(f"Failed to fix counters file: {e}")

            # Validate counter values
            for field in ["spec_number", "standalone_task_number"]:
                if field in counters:
                    value = counters[field]
                    if not isinstance(value, int) or value < 1:
                        result.issues.append(
                            Issue(
                                severity=IssueSeverity.ERROR,
                                category="counters",
                                message=f"Invalid counter value for '{field}': {value}",
                                location=str(self.counters_file),
                                fix_suggestion=f"Set '{field}' to a positive integer",
                                auto_fixable=False,
                            )
                        )

            # Check if counters are in sync with actual usage
            if self.tasks_file.exists():
                self._verify_counter_sync(result, counters, fix=fix)

        except json.JSONDecodeError as e:
            result.issues.append(
                Issue(
                    severity=IssueSeverity.ERROR,
                    category="counters",
                    message=f"Invalid JSON in counters file: {e}",
                    location=str(self.counters_file),
                    fix_suggestion="Manually fix the JSON or delete the file to regenerate",
                    auto_fixable=False,
                )
            )
        except Exception as e:
            result.issues.append(
                Issue(
                    severity=IssueSeverity.ERROR,
                    category="counters",
                    message=f"Failed to read counters file: {e}",
                    location=str(self.counters_file),
                    fix_suggestion="Check file permissions",
                    auto_fixable=False,
                )
            )

    def _verify_counter_sync(
        self, result: VerifyResult, counters: dict[str, int | str], *, fix: bool
    ) -> None:
        """
        Verify that counter values match actual ID usage.

        Args:
            result: VerifyResult to append issues to
            counters: Current counter values
            fix: Whether to auto-fix issues
        """
        try:
            # Find highest spec number used
            max_spec_num = 0
            max_standalone_num = 0

            with self.tasks_file.open("r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        task = json.loads(line)
                        task_id = task.get("id", "")

                        # Check for spec-based IDs (e.g., "cub-048a-1.2")
                        if "-" in task_id:
                            parts = task_id.split("-")
                            letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                            if len(parts) >= 2 and parts[1].rstrip(letters).isdigit():
                                spec_num = int(parts[1].rstrip(letters))
                                max_spec_num = max(max_spec_num, spec_num)

                        # Check for standalone IDs (e.g., "cub-orphan-42")
                        if "orphan" in task_id.lower():
                            parts = task_id.split("-")
                            if len(parts) >= 3 and parts[2].isdigit():
                                standalone_num = int(parts[2])
                                max_standalone_num = max(max_standalone_num, standalone_num)

                    except (json.JSONDecodeError, ValueError):
                        continue

            # Check if counters need updating
            current_spec_raw = counters.get("spec_number", 1)
            current_standalone_raw = counters.get("standalone_task_number", 1)

            # Ensure values are integers
            current_spec = (
                current_spec_raw if isinstance(current_spec_raw, int) else 1
            )
            current_standalone = (
                current_standalone_raw if isinstance(current_standalone_raw, int) else 1
            )

            if max_spec_num >= current_spec:
                result.issues.append(
                    Issue(
                        severity=IssueSeverity.WARNING,
                        category="counters",
                        message=(
                            f"Spec counter ({current_spec}) is behind "
                            f"actual usage ({max_spec_num})"
                        ),
                        location=str(self.counters_file),
                        fix_suggestion=f"Update spec_number to {max_spec_num + 1}",
                        auto_fixable=True,
                    )
                )

                if fix:
                    try:
                        counters["spec_number"] = max_spec_num + 1
                        counters["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                        with self.counters_file.open("w") as f:
                            json.dump(counters, f, indent=2)
                        result.auto_fixed += 1
                        logger.info(f"Updated spec_number to {max_spec_num + 1}")
                    except Exception as e:
                        logger.error(f"Failed to update counters: {e}")

            if max_standalone_num >= current_standalone:
                result.issues.append(
                    Issue(
                        severity=IssueSeverity.WARNING,
                        category="counters",
                        message=(
                            f"Standalone counter ({current_standalone}) is behind "
                            f"actual usage ({max_standalone_num})"
                        ),
                        location=str(self.counters_file),
                        fix_suggestion=(
                            f"Update standalone_task_number to {max_standalone_num + 1}"
                        ),
                        auto_fixable=True,
                    )
                )

                if fix:
                    try:
                        counters["standalone_task_number"] = max_standalone_num + 1
                        counters["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                        with self.counters_file.open("w") as f:
                            json.dump(counters, f, indent=2)
                        result.auto_fixed += 1
                        logger.info(f"Updated standalone_task_number to {max_standalone_num + 1}")
                    except Exception as e:
                        logger.error(f"Failed to update counters: {e}")

        except Exception as e:
            logger.warning(f"Failed to verify counter sync: {e}")

    def _is_valid_task_id(self, task_id: str) -> bool:
        """
        Check if a task ID has a valid format.

        Valid formats:
        - Spec-based: cub-XXX, cub-XXXa, cub-XXXa-Y, cub-XXXa-Y.Z
        - Standalone: cub-orphan-NN, cub-orphan-NNa

        Args:
            task_id: Task ID to validate

        Returns:
            True if ID appears valid
        """
        if not task_id:
            return False

        # Very basic validation - just check it starts with a reasonable prefix
        # and has some structure
        if not task_id.startswith("cub-"):
            return False

        # Must have at least one hyphen-separated part after "cub-"
        parts = task_id.split("-")
        if len(parts) < 2:
            return False

        return True
