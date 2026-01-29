"""
PR monitoring service — check polling, failure detection, and retry logic.

Provides automated monitoring of PR CI check status via `gh pr checks`,
with configurable retry logic for transient failures (flaky tests,
rate limits, temporary service issues).

Usage:
    >>> from cub.core.services.pr_monitor import PRMonitorService
    >>> monitor = PRMonitorService(poll_interval=30, retry_timeout=600, max_retries=3)
    >>> result = monitor.poll_checks(pr_number=42)
    >>> if result.needs_retry:
    ...     monitor.trigger_retry(pr_number=42)

State Machine:
    poll → detect failure → wait → retry → repeat or succeed
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and constants
# ============================================================================


class CheckState(str, Enum):
    """State of a CI check."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ERROR = "error"

    @property
    def is_terminal(self) -> bool:
        """Whether this state is final (no further transitions expected)."""
        return self in (
            CheckState.SUCCESS,
            CheckState.FAILURE,
            CheckState.CANCELLED,
            CheckState.TIMED_OUT,
            CheckState.ERROR,
        )

    @property
    def is_retriable(self) -> bool:
        """Whether this state is eligible for retry."""
        return self in (
            CheckState.FAILURE,
            CheckState.TIMED_OUT,
            CheckState.ERROR,
        )


class MonitorState(str, Enum):
    """State machine states for PR monitoring."""

    POLLING = "polling"
    DETECTING = "detecting"
    WAITING = "waiting"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    EXHAUSTED = "exhausted"
    TIMED_OUT = "timed_out"


class RetryReason(str, Enum):
    """Reason for triggering a retry."""

    FLAKY_TEST = "flaky_test"
    RATE_LIMIT = "rate_limit"
    SERVICE_ERROR = "service_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


# ============================================================================
# Data models
# ============================================================================


@dataclass
class CheckResult:
    """Result of a single CI check."""

    name: str
    state: CheckState
    conclusion: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    url: str | None = None


@dataclass
class CheckSummary:
    """Summary of all checks for a PR."""

    checks: list[CheckResult] = field(default_factory=list)
    polled_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @property
    def all_passed(self) -> bool:
        """Whether all checks have passed."""
        return bool(self.checks) and all(c.state == CheckState.SUCCESS for c in self.checks)

    @property
    def has_failures(self) -> bool:
        """Whether any checks have failed."""
        return any(c.state.is_retriable for c in self.checks)

    @property
    def is_pending(self) -> bool:
        """Whether any checks are still in progress."""
        return any(not c.state.is_terminal for c in self.checks)

    @property
    def failed_checks(self) -> list[CheckResult]:
        """Get all failed checks."""
        return [c for c in self.checks if c.state.is_retriable]

    @property
    def pending_checks(self) -> list[CheckResult]:
        """Get all pending/running checks."""
        return [c for c in self.checks if not c.state.is_terminal]


@dataclass
class RetryAttempt:
    """Record of a single retry attempt."""

    attempt_number: int
    reason: RetryReason
    triggered_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    failed_checks: list[str] = field(default_factory=list)
    success: bool = False
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Duration of the retry attempt in seconds."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.triggered_at).total_seconds()


@dataclass
class MonitorResult:
    """Final result of the PR monitoring session."""

    state: MonitorState
    check_summary: CheckSummary | None = None
    retry_attempts: list[RetryAttempt] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    completed_at: datetime | None = None
    error_message: str | None = None

    @property
    def total_retries(self) -> int:
        """Total number of retries attempted."""
        return len(self.retry_attempts)

    @property
    def succeeded(self) -> bool:
        """Whether monitoring ended with success."""
        return self.state == MonitorState.SUCCEEDED

    @property
    def duration_seconds(self) -> float | None:
        """Total monitoring duration in seconds."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()


# ============================================================================
# Exceptions
# ============================================================================


class PRMonitorError(Exception):
    """Base exception for PR monitoring errors."""


class CheckPollError(PRMonitorError):
    """Error polling check status."""


class RetryError(PRMonitorError):
    """Error triggering a retry."""


# ============================================================================
# PR Monitor Service
# ============================================================================


class PRMonitorService:
    """
    Service for monitoring PR CI checks and triggering retries.

    Implements a poll → detect → wait → retry state machine for
    handling transient CI failures in pull requests.

    Example:
        >>> monitor = PRMonitorService(
        ...     poll_interval=30,
        ...     retry_timeout=600,
        ...     max_retries=3,
        ... )
        >>> result = monitor.monitor_pr(pr_number=42)
        >>> if result.succeeded:
        ...     print("All checks passed!")
        >>> else:
        ...     print(f"Failed after {result.total_retries} retries")
    """

    def __init__(
        self,
        *,
        poll_interval: int = 30,
        retry_timeout: int = 600,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize monitor with configuration.

        Args:
            poll_interval: Seconds between check polls
            retry_timeout: Total timeout in seconds for all retries
            max_retries: Maximum number of retry attempts
        """
        self._poll_interval = poll_interval
        self._retry_timeout = retry_timeout
        self._max_retries = max_retries

    @property
    def poll_interval(self) -> int:
        """Seconds between check polls."""
        return self._poll_interval

    @property
    def retry_timeout(self) -> int:
        """Total timeout for retry operations in seconds."""
        return self._retry_timeout

    @property
    def max_retries(self) -> int:
        """Maximum number of retry attempts."""
        return self._max_retries

    # ============================================================================
    # Check polling
    # ============================================================================

    def poll_checks(self, pr_number: int) -> CheckSummary:
        """
        Poll CI check status for a PR.

        Uses `gh pr checks` to get current check states.

        Args:
            pr_number: The PR number to check

        Returns:
            CheckSummary with current check states

        Raises:
            CheckPollError: If polling fails
        """
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "checks",
                    str(pr_number),
                    "--json",
                    "name,state,startedAt,completedAt,detailsUrl",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            if result.returncode != 0:
                stderr = result.stderr.strip() if result.stderr else "unknown error"
                raise CheckPollError(f"gh pr checks failed: {stderr}")

            checks_data = json.loads(result.stdout) if result.stdout.strip() else []
            checks: list[CheckResult] = []

            for check_data in checks_data:
                state = self._parse_check_state(check_data)
                checks.append(
                    CheckResult(
                        name=check_data.get("name", "unknown"),
                        state=state,
                        conclusion=check_data.get("state"),
                        started_at=self._parse_datetime(check_data.get("startedAt")),
                        completed_at=self._parse_datetime(check_data.get("completedAt")),
                        url=check_data.get("detailsUrl"),
                    )
                )

            return CheckSummary(checks=checks)

        except subprocess.TimeoutExpired as e:
            raise CheckPollError("gh pr checks timed out") from e
        except json.JSONDecodeError as e:
            raise CheckPollError(f"Failed to parse check results: {e}") from e
        except FileNotFoundError as e:
            raise CheckPollError("gh CLI not found") from e

    def _parse_check_state(self, check_data: dict[str, str | None]) -> CheckState:
        """Parse check state from gh CLI output."""
        state_str = (check_data.get("state") or "").upper()

        state_map: dict[str, CheckState] = {
            "SUCCESS": CheckState.SUCCESS,
            "PASS": CheckState.SUCCESS,
            "FAILURE": CheckState.FAILURE,
            "FAIL": CheckState.FAILURE,
            "CANCELLED": CheckState.CANCELLED,
            "TIMED_OUT": CheckState.TIMED_OUT,
            "ERROR": CheckState.ERROR,
            "PENDING": CheckState.PENDING,
            "QUEUED": CheckState.PENDING,
            "IN_PROGRESS": CheckState.RUNNING,
            "RUNNING": CheckState.RUNNING,
            "REQUESTED": CheckState.PENDING,
            "WAITING": CheckState.PENDING,
            "STARTUP_FAILURE": CheckState.ERROR,
            "STALE": CheckState.ERROR,
            "SKIPPED": CheckState.SUCCESS,
            "NEUTRAL": CheckState.SUCCESS,
        }

        return state_map.get(state_str, CheckState.PENDING)

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        """Parse ISO datetime string to datetime object."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    # ============================================================================
    # Failure detection
    # ============================================================================

    def detect_failure_reason(self, summary: CheckSummary) -> RetryReason:
        """
        Analyze check failures to determine the likely cause.

        Args:
            summary: The check summary to analyze

        Returns:
            RetryReason indicating the most likely cause
        """
        failed = summary.failed_checks
        if not failed:
            return RetryReason.UNKNOWN

        failure_names = [c.name.lower() for c in failed]

        # Check for rate limit indicators
        rate_limit_indicators = ["rate", "limit", "throttl", "429", "quota"]
        if any(
            indicator in name for name in failure_names for indicator in rate_limit_indicators
        ):
            return RetryReason.RATE_LIMIT

        # Check for service/infrastructure errors
        service_indicators = ["infra", "service", "deploy", "provision", "setup"]
        if any(
            indicator in name for name in failure_names for indicator in service_indicators
        ):
            return RetryReason.SERVICE_ERROR

        # Check for timeout
        timed_out = [c for c in failed if c.state == CheckState.TIMED_OUT]
        if timed_out:
            return RetryReason.TIMEOUT

        # Default to flaky test (most common transient failure)
        return RetryReason.FLAKY_TEST

    # ============================================================================
    # Retry triggering
    # ============================================================================

    def trigger_retry(self, pr_number: int) -> bool:
        """
        Trigger a CI retry for a PR by re-requesting checks.

        Uses `gh pr checks --watch --fail-fast` to re-trigger checks
        by closing/reopening or pushing an empty commit.

        Args:
            pr_number: The PR number to retry

        Returns:
            True if retry was triggered successfully

        Raises:
            RetryError: If retry triggering fails
        """
        try:
            # Use gh api to re-run failed checks via the check-suite re-request endpoint
            # First get the head SHA
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr_number),
                    "--json",
                    "headRefOid",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            if result.returncode != 0:
                raise RetryError(f"Failed to get PR head SHA: {result.stderr}")

            pr_data = json.loads(result.stdout)
            head_sha = pr_data.get("headRefOid")

            if not head_sha:
                raise RetryError("Could not determine PR head commit SHA")

            # Re-run failed checks via GitHub API
            rerun_result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{{owner}}/{{repo}}/commits/{head_sha}/check-suites",
                    "--method",
                    "GET",
                    "--jq",
                    ".check_suites[].id",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            if rerun_result.returncode != 0:
                # Fallback: push an empty commit to re-trigger
                logger.info("Check suite API failed, falling back to empty commit retrigger")
                return self._retrigger_via_comment(pr_number)

            # Re-request each check suite
            suite_ids = rerun_result.stdout.strip().split("\n")
            any_success = False
            for suite_id in suite_ids:
                if not suite_id.strip():
                    continue
                rerequest = subprocess.run(
                    [
                        "gh",
                        "api",
                        f"repos/{{owner}}/{{repo}}/check-suites/{suite_id.strip()}/rerequest",
                        "--method",
                        "POST",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                if rerequest.returncode == 0:
                    any_success = True

            if any_success:
                logger.info("Successfully re-requested check suites for PR #%d", pr_number)
                return True

            # Fallback if no suite re-requests worked
            return self._retrigger_via_comment(pr_number)

        except subprocess.TimeoutExpired as e:
            raise RetryError("Retry trigger timed out") from e
        except json.JSONDecodeError as e:
            raise RetryError(f"Failed to parse PR data: {e}") from e
        except FileNotFoundError as e:
            raise RetryError("gh CLI not found") from e

    def _retrigger_via_comment(self, pr_number: int) -> bool:
        """
        Fallback retry mechanism: add a comment requesting re-run.

        Args:
            pr_number: The PR number

        Returns:
            True if comment was added
        """
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "comment",
                    str(pr_number),
                    "--body",
                    "🔄 Retrying failed checks (automated by cub pr monitor)",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    # ============================================================================
    # Monitor loop (state machine)
    # ============================================================================

    def monitor_pr(
        self,
        pr_number: int,
        *,
        on_poll: Callable[[CheckSummary], Any] | None = None,
        on_retry: Callable[[RetryAttempt], Any] | None = None,
    ) -> MonitorResult:
        """
        Run the full monitoring state machine for a PR.

        State machine: poll → detect failure → wait → retry → repeat or succeed.

        Args:
            pr_number: The PR number to monitor
            on_poll: Optional callback(CheckSummary) called after each poll
            on_retry: Optional callback(RetryAttempt) called after each retry

        Returns:
            MonitorResult with final state and retry history
        """
        result = MonitorResult(state=MonitorState.POLLING)
        start_time = time.monotonic()
        retry_count = 0

        while True:
            # Check timeout
            elapsed = time.monotonic() - start_time
            if elapsed >= self._retry_timeout:
                result.state = MonitorState.TIMED_OUT
                result.completed_at = datetime.now(tz=timezone.utc)
                result.error_message = (
                    f"Monitoring timed out after {elapsed:.0f}s "
                    f"({retry_count} retries attempted)"
                )
                logger.warning(
                    "PR #%d monitoring timed out after %.0fs", pr_number, elapsed
                )
                break

            # Poll checks
            try:
                summary = self.poll_checks(pr_number)
                result.check_summary = summary
            except CheckPollError as e:
                logger.warning("Poll error for PR #%d: %s", pr_number, e)
                # Wait and try again
                time.sleep(self._poll_interval)
                continue

            if on_poll is not None:
                on_poll(summary)

            # Check if all passed
            if summary.all_passed:
                result.state = MonitorState.SUCCEEDED
                result.completed_at = datetime.now(tz=timezone.utc)
                logger.info("All checks passed for PR #%d", pr_number)
                break

            # If still pending, wait and re-poll
            if summary.is_pending:
                result.state = MonitorState.POLLING
                time.sleep(self._poll_interval)
                continue

            # Failure detected
            result.state = MonitorState.DETECTING
            reason = self.detect_failure_reason(summary)

            # Check if we've exhausted retries
            if retry_count >= self._max_retries:
                result.state = MonitorState.EXHAUSTED
                result.completed_at = datetime.now(tz=timezone.utc)
                failed_names = [c.name for c in summary.failed_checks]
                result.error_message = (
                    f"Exhausted {self._max_retries} retries. "
                    f"Still failing: {', '.join(failed_names[:5])}"
                )
                logger.warning(
                    "PR #%d exhausted %d retries", pr_number, self._max_retries
                )
                break

            # Wait before retry
            result.state = MonitorState.WAITING
            wait_time = min(self._poll_interval * (retry_count + 1), 120)
            logger.info(
                "PR #%d: waiting %ds before retry %d/%d (reason: %s)",
                pr_number,
                wait_time,
                retry_count + 1,
                self._max_retries,
                reason.value,
            )
            time.sleep(wait_time)

            # Trigger retry
            result.state = MonitorState.RETRYING
            retry_count += 1
            attempt = RetryAttempt(
                attempt_number=retry_count,
                reason=reason,
                failed_checks=[c.name for c in summary.failed_checks],
            )

            try:
                self.trigger_retry(pr_number)
                logger.info("Retry %d triggered for PR #%d", retry_count, pr_number)
            except RetryError as e:
                logger.warning("Retry trigger failed for PR #%d: %s", pr_number, e)
                attempt.success = False
                attempt.completed_at = datetime.now(tz=timezone.utc)
                result.retry_attempts.append(attempt)
                if on_retry is not None:
                    on_retry(attempt)
                continue

            result.retry_attempts.append(attempt)
            if on_retry is not None:
                on_retry(attempt)

            # Wait for checks to start again
            time.sleep(self._poll_interval)

        return result

    # ============================================================================
    # Single-shot check
    # ============================================================================

    def check_once(self, pr_number: int) -> CheckSummary:
        """
        Poll checks once without monitoring loop.

        Convenience method for one-shot status checks.

        Args:
            pr_number: The PR number to check

        Returns:
            CheckSummary with current state
        """
        return self.poll_checks(pr_number)


__all__ = [
    "CheckResult",
    "CheckState",
    "CheckSummary",
    "CheckPollError",
    "MonitorResult",
    "MonitorState",
    "PRMonitorError",
    "PRMonitorService",
    "RetryAttempt",
    "RetryError",
    "RetryReason",
]
