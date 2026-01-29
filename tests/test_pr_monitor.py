"""
Tests for PR monitoring service — check polling, failure detection, and retry logic.

Tests the PRMonitorService check state machine, failure detection heuristics,
and retry triggering. All subprocess calls are mocked.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from cub.core.services.pr_monitor import (
    CheckPollError,
    CheckResult,
    CheckState,
    CheckSummary,
    MonitorResult,
    MonitorState,
    PRMonitorService,
    RetryAttempt,
    RetryError,
    RetryReason,
)

# ============================================================================
# CheckState enum tests
# ============================================================================


class TestCheckState:
    """Tests for CheckState enum."""

    def test_terminal_states(self) -> None:
        """Terminal states are success, failure, cancelled, timed_out, error."""
        assert CheckState.SUCCESS.is_terminal
        assert CheckState.FAILURE.is_terminal
        assert CheckState.CANCELLED.is_terminal
        assert CheckState.TIMED_OUT.is_terminal
        assert CheckState.ERROR.is_terminal

    def test_non_terminal_states(self) -> None:
        """Pending and running are not terminal."""
        assert not CheckState.PENDING.is_terminal
        assert not CheckState.RUNNING.is_terminal

    def test_retriable_states(self) -> None:
        """Failure, timed_out, and error are retriable."""
        assert CheckState.FAILURE.is_retriable
        assert CheckState.TIMED_OUT.is_retriable
        assert CheckState.ERROR.is_retriable

    def test_non_retriable_states(self) -> None:
        """Success, pending, running, cancelled are not retriable."""
        assert not CheckState.SUCCESS.is_retriable
        assert not CheckState.PENDING.is_retriable
        assert not CheckState.RUNNING.is_retriable
        assert not CheckState.CANCELLED.is_retriable


# ============================================================================
# CheckSummary tests
# ============================================================================


class TestCheckSummary:
    """Tests for CheckSummary data model."""

    def test_all_passed(self) -> None:
        """All checks passing."""
        summary = CheckSummary(
            checks=[
                CheckResult(name="tests", state=CheckState.SUCCESS),
                CheckResult(name="lint", state=CheckState.SUCCESS),
            ]
        )
        assert summary.all_passed
        assert not summary.has_failures
        assert not summary.is_pending

    def test_has_failures(self) -> None:
        """Summary detects failures."""
        summary = CheckSummary(
            checks=[
                CheckResult(name="tests", state=CheckState.FAILURE),
                CheckResult(name="lint", state=CheckState.SUCCESS),
            ]
        )
        assert not summary.all_passed
        assert summary.has_failures
        assert len(summary.failed_checks) == 1
        assert summary.failed_checks[0].name == "tests"

    def test_is_pending(self) -> None:
        """Summary detects pending checks."""
        summary = CheckSummary(
            checks=[
                CheckResult(name="tests", state=CheckState.RUNNING),
                CheckResult(name="lint", state=CheckState.SUCCESS),
            ]
        )
        assert not summary.all_passed
        assert summary.is_pending
        assert len(summary.pending_checks) == 1

    def test_empty_summary(self) -> None:
        """Empty summary is not all_passed."""
        summary = CheckSummary(checks=[])
        assert not summary.all_passed
        assert not summary.has_failures
        assert not summary.is_pending


# ============================================================================
# RetryAttempt tests
# ============================================================================


class TestRetryAttempt:
    """Tests for RetryAttempt data model."""

    def test_duration_calculation(self) -> None:
        """Duration is calculated from triggered_at to completed_at."""
        triggered = datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc)
        completed = datetime(2026, 1, 28, 10, 5, 0, tzinfo=timezone.utc)
        attempt = RetryAttempt(
            attempt_number=1,
            reason=RetryReason.FLAKY_TEST,
            triggered_at=triggered,
            completed_at=completed,
        )
        assert attempt.duration_seconds == 300.0

    def test_duration_none_when_incomplete(self) -> None:
        """Duration is None when not completed."""
        attempt = RetryAttempt(
            attempt_number=1,
            reason=RetryReason.FLAKY_TEST,
        )
        assert attempt.duration_seconds is None


# ============================================================================
# MonitorResult tests
# ============================================================================


class TestMonitorResult:
    """Tests for MonitorResult data model."""

    def test_succeeded(self) -> None:
        """Result reports success when state is SUCCEEDED."""
        result = MonitorResult(state=MonitorState.SUCCEEDED)
        assert result.succeeded
        assert result.total_retries == 0

    def test_not_succeeded(self) -> None:
        """Result reports non-success for other states."""
        result = MonitorResult(state=MonitorState.EXHAUSTED)
        assert not result.succeeded

    def test_total_retries(self) -> None:
        """Total retries counts retry attempts."""
        result = MonitorResult(
            state=MonitorState.EXHAUSTED,
            retry_attempts=[
                RetryAttempt(attempt_number=1, reason=RetryReason.FLAKY_TEST),
                RetryAttempt(attempt_number=2, reason=RetryReason.FLAKY_TEST),
            ],
        )
        assert result.total_retries == 2

    def test_duration(self) -> None:
        """Duration calculated from start to completion."""
        started = datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc)
        completed = datetime(2026, 1, 28, 10, 10, 0, tzinfo=timezone.utc)
        result = MonitorResult(
            state=MonitorState.SUCCEEDED,
            started_at=started,
            completed_at=completed,
        )
        assert result.duration_seconds == 600.0


# ============================================================================
# PRMonitorService — poll_checks tests
# ============================================================================


class TestPollChecks:
    """Tests for PRMonitorService.poll_checks."""

    def test_successful_poll(self) -> None:
        """Polling returns check summary from gh output."""
        checks_json = json.dumps([
            {"name": "tests", "state": "SUCCESS", "startedAt": None, "completedAt": None},
            {"name": "lint", "state": "FAILURE", "startedAt": None, "completedAt": None},
        ])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = checks_json

        monitor = PRMonitorService(poll_interval=1, retry_timeout=10, max_retries=1)

        with patch("subprocess.run", return_value=mock_result):
            summary = monitor.poll_checks(42)

        assert len(summary.checks) == 2
        assert summary.checks[0].state == CheckState.SUCCESS
        assert summary.checks[1].state == CheckState.FAILURE

    def test_poll_gh_failure(self) -> None:
        """Polling raises CheckPollError when gh fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "not found"

        monitor = PRMonitorService()

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(CheckPollError, match="gh pr checks failed"):
                monitor.poll_checks(42)

    def test_poll_timeout(self) -> None:
        """Polling raises CheckPollError on timeout."""
        monitor = PRMonitorService()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            with pytest.raises(CheckPollError, match="timed out"):
                monitor.poll_checks(42)

    def test_poll_gh_not_found(self) -> None:
        """Polling raises CheckPollError when gh CLI not found."""
        monitor = PRMonitorService()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(CheckPollError, match="gh CLI not found"):
                monitor.poll_checks(42)

    def test_poll_invalid_json(self) -> None:
        """Polling raises CheckPollError on invalid JSON."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"

        monitor = PRMonitorService()

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(CheckPollError, match="Failed to parse"):
                monitor.poll_checks(42)

    def test_poll_empty_output(self) -> None:
        """Polling handles empty output gracefully."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        monitor = PRMonitorService()

        with patch("subprocess.run", return_value=mock_result):
            summary = monitor.poll_checks(42)

        assert len(summary.checks) == 0

    def test_state_parsing_variants(self) -> None:
        """Various check state strings are parsed correctly."""
        monitor = PRMonitorService()

        test_cases = [
            ("SUCCESS", CheckState.SUCCESS),
            ("PASS", CheckState.SUCCESS),
            ("FAILURE", CheckState.FAILURE),
            ("FAIL", CheckState.FAILURE),
            ("PENDING", CheckState.PENDING),
            ("IN_PROGRESS", CheckState.RUNNING),
            ("QUEUED", CheckState.PENDING),
            ("CANCELLED", CheckState.CANCELLED),
            ("TIMED_OUT", CheckState.TIMED_OUT),
            ("ERROR", CheckState.ERROR),
            ("SKIPPED", CheckState.SUCCESS),
            ("NEUTRAL", CheckState.SUCCESS),
            ("UNKNOWN_STATE", CheckState.PENDING),
        ]

        for state_str, expected in test_cases:
            result = monitor._parse_check_state({"state": state_str})
            assert result == expected, f"Expected {expected} for '{state_str}', got {result}"


# ============================================================================
# PRMonitorService — detect_failure_reason tests
# ============================================================================


class TestDetectFailureReason:
    """Tests for failure reason detection heuristics."""

    def test_flaky_test_default(self) -> None:
        """Default failure reason is flaky_test."""
        monitor = PRMonitorService()
        summary = CheckSummary(
            checks=[CheckResult(name="unit-tests", state=CheckState.FAILURE)]
        )
        assert monitor.detect_failure_reason(summary) == RetryReason.FLAKY_TEST

    def test_rate_limit_detection(self) -> None:
        """Rate limit keywords trigger RATE_LIMIT reason."""
        monitor = PRMonitorService()
        summary = CheckSummary(
            checks=[CheckResult(name="api-rate-limit-check", state=CheckState.FAILURE)]
        )
        assert monitor.detect_failure_reason(summary) == RetryReason.RATE_LIMIT

    def test_service_error_detection(self) -> None:
        """Service keywords trigger SERVICE_ERROR reason."""
        monitor = PRMonitorService()
        summary = CheckSummary(
            checks=[CheckResult(name="deploy-infra-check", state=CheckState.FAILURE)]
        )
        assert monitor.detect_failure_reason(summary) == RetryReason.SERVICE_ERROR

    def test_timeout_detection(self) -> None:
        """Timed out checks trigger TIMEOUT reason."""
        monitor = PRMonitorService()
        summary = CheckSummary(
            checks=[CheckResult(name="integration-tests", state=CheckState.TIMED_OUT)]
        )
        assert monitor.detect_failure_reason(summary) == RetryReason.TIMEOUT

    def test_no_failures(self) -> None:
        """No failures returns UNKNOWN."""
        monitor = PRMonitorService()
        summary = CheckSummary(
            checks=[CheckResult(name="tests", state=CheckState.SUCCESS)]
        )
        assert monitor.detect_failure_reason(summary) == RetryReason.UNKNOWN


# ============================================================================
# PRMonitorService — trigger_retry tests
# ============================================================================


class TestTriggerRetry:
    """Tests for retry triggering."""

    def test_retry_via_check_suites(self) -> None:
        """Retry works via check suite re-request API."""
        monitor = PRMonitorService()

        # Mock gh pr view (get SHA)
        view_result = MagicMock()
        view_result.returncode = 0
        view_result.stdout = json.dumps({"headRefOid": "abc123"})

        # Mock gh api (get check suites)
        suites_result = MagicMock()
        suites_result.returncode = 0
        suites_result.stdout = "12345\n67890\n"

        # Mock gh api (re-request)
        rerequest_result = MagicMock()
        rerequest_result.returncode = 0

        effects = [view_result, suites_result, rerequest_result, rerequest_result]
        with patch("subprocess.run", side_effect=effects):
            result = monitor.trigger_retry(42)

        assert result is True

    def test_retry_fallback_to_comment(self) -> None:
        """Retry falls back to comment when API fails."""
        monitor = PRMonitorService()

        view_result = MagicMock()
        view_result.returncode = 0
        view_result.stdout = json.dumps({"headRefOid": "abc123"})

        suites_result = MagicMock()
        suites_result.returncode = 1
        suites_result.stderr = "API error"

        comment_result = MagicMock()
        comment_result.returncode = 0

        with patch("subprocess.run", side_effect=[view_result, suites_result, comment_result]):
            result = monitor.trigger_retry(42)

        assert result is True

    def test_retry_fails_on_sha_error(self) -> None:
        """Retry raises RetryError when can't get SHA."""
        monitor = PRMonitorService()

        view_result = MagicMock()
        view_result.returncode = 1
        view_result.stderr = "not found"

        with patch("subprocess.run", return_value=view_result):
            with pytest.raises(RetryError, match="Failed to get PR head SHA"):
                monitor.trigger_retry(42)

    def test_retry_timeout(self) -> None:
        """Retry raises RetryError on timeout."""
        monitor = PRMonitorService()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            with pytest.raises(RetryError, match="timed out"):
                monitor.trigger_retry(42)

    def test_retry_gh_not_found(self) -> None:
        """Retry raises RetryError when gh not found."""
        monitor = PRMonitorService()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RetryError, match="gh CLI not found"):
                monitor.trigger_retry(42)


# ============================================================================
# PRMonitorService — monitor_pr state machine tests
# ============================================================================


class TestMonitorPR:
    """Tests for the full monitoring state machine."""

    def test_immediate_success(self) -> None:
        """Monitor returns SUCCEEDED when all checks pass immediately."""
        monitor = PRMonitorService(poll_interval=0, retry_timeout=10, max_retries=3)

        checks_json = json.dumps([
            {"name": "tests", "state": "SUCCESS"},
            {"name": "lint", "state": "SUCCESS"},
        ])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = checks_json

        with patch("subprocess.run", return_value=mock_result):
            with patch("time.sleep"):
                result = monitor.monitor_pr(42)

        assert result.state == MonitorState.SUCCEEDED
        assert result.succeeded
        assert result.total_retries == 0

    def test_exhausted_retries(self) -> None:
        """Monitor returns EXHAUSTED when max retries exceeded."""
        monitor = PRMonitorService(poll_interval=0, retry_timeout=600, max_retries=1)

        # First poll: failure
        checks_json = json.dumps([
            {"name": "tests", "state": "FAILURE"},
        ])
        poll_result = MagicMock()
        poll_result.returncode = 0
        poll_result.stdout = checks_json

        # Retry trigger calls
        view_result = MagicMock()
        view_result.returncode = 0
        view_result.stdout = json.dumps({"headRefOid": "abc123"})

        suites_result = MagicMock()
        suites_result.returncode = 1
        suites_result.stderr = "error"

        comment_result = MagicMock()
        comment_result.returncode = 0

        # After retry, still failing
        with patch("subprocess.run", side_effect=[
            poll_result,    # initial poll
            view_result,    # retry - get SHA
            suites_result,  # retry - get suites (fails)
            comment_result, # retry - fallback comment
            poll_result,    # second poll (still failing)
        ]):
            with patch("time.sleep"):
                result = monitor.monitor_pr(42)

        assert result.state == MonitorState.EXHAUSTED
        assert not result.succeeded
        assert result.total_retries == 1

    def test_timeout(self) -> None:
        """Monitor returns TIMED_OUT when timeout exceeded."""
        monitor = PRMonitorService(poll_interval=0, retry_timeout=0, max_retries=3)

        checks_json = json.dumps([
            {"name": "tests", "state": "FAILURE"},
        ])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = checks_json

        with patch("subprocess.run", return_value=mock_result):
            with patch("time.sleep"):
                result = monitor.monitor_pr(42)

        assert result.state == MonitorState.TIMED_OUT

    def test_on_poll_callback(self) -> None:
        """on_poll callback is called after each poll."""
        monitor = PRMonitorService(poll_interval=0, retry_timeout=10, max_retries=0)

        checks_json = json.dumps([
            {"name": "tests", "state": "SUCCESS"},
        ])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = checks_json

        on_poll = MagicMock()

        with patch("subprocess.run", return_value=mock_result):
            with patch("time.sleep"):
                monitor.monitor_pr(42, on_poll=on_poll)

        on_poll.assert_called_once()

    def test_check_once(self) -> None:
        """check_once returns single poll result."""
        monitor = PRMonitorService()

        checks_json = json.dumps([
            {"name": "tests", "state": "SUCCESS"},
        ])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = checks_json

        with patch("subprocess.run", return_value=mock_result):
            summary = monitor.check_once(42)

        assert summary.all_passed


# ============================================================================
# PRMonitorService — configuration tests
# ============================================================================


class TestPRMonitorConfiguration:
    """Tests for monitor configuration."""

    def test_default_configuration(self) -> None:
        """Default configuration values."""
        monitor = PRMonitorService()
        assert monitor.poll_interval == 30
        assert monitor.retry_timeout == 600
        assert monitor.max_retries == 3

    def test_custom_configuration(self) -> None:
        """Custom configuration values."""
        monitor = PRMonitorService(
            poll_interval=10,
            retry_timeout=300,
            max_retries=5,
        )
        assert monitor.poll_interval == 10
        assert monitor.retry_timeout == 300
        assert monitor.max_retries == 5


# ============================================================================
# Config model tests
# ============================================================================


class TestPRRetryConfig:
    """Tests for PRRetryConfig model."""

    def test_default_values(self) -> None:
        """Default PRRetryConfig values."""
        from cub.core.config.models import PRRetryConfig

        config = PRRetryConfig()
        assert config.enabled is True
        assert config.retry_timeout == 600
        assert config.max_retries == 3
        assert config.poll_interval == 30

    def test_custom_values(self) -> None:
        """Custom PRRetryConfig values."""
        from cub.core.config.models import PRRetryConfig

        config = PRRetryConfig(
            enabled=False,
            retry_timeout=300,
            max_retries=5,
            poll_interval=10,
        )
        assert config.enabled is False
        assert config.retry_timeout == 300
        assert config.max_retries == 5
        assert config.poll_interval == 10

    def test_validation_constraints(self) -> None:
        """PRRetryConfig validates constraints."""
        from cub.core.config.models import PRRetryConfig

        with pytest.raises(Exception):  # pydantic ValidationError
            PRRetryConfig(retry_timeout=10)  # min 30

        with pytest.raises(Exception):
            PRRetryConfig(max_retries=15)  # max 10

        with pytest.raises(Exception):
            PRRetryConfig(poll_interval=2)  # min 5

    def test_cub_config_has_pr_retry(self) -> None:
        """CubConfig includes pr_retry field."""
        from cub.core.config.models import CubConfig

        config = CubConfig()
        assert hasattr(config, "pr_retry")
        assert config.pr_retry.enabled is True
        assert config.pr_retry.retry_timeout == 600


# ============================================================================
# Ledger model tests
# ============================================================================


class TestCILedgerModels:
    """Tests for CI monitoring ledger models."""

    def test_ci_check_record(self) -> None:
        """CICheckRecord creation."""
        from cub.core.ledger.models import CICheckRecord

        record = CICheckRecord(
            name="tests",
            state="failure",
            url="https://example.com/check/1",
        )
        assert record.name == "tests"
        assert record.state == "failure"

    def test_ci_retry_record(self) -> None:
        """CIRetryRecord creation."""
        from cub.core.ledger.models import CIRetryRecord

        record = CIRetryRecord(
            attempt_number=1,
            reason="flaky_test",
            failed_checks=["tests", "lint"],
            success=True,
        )
        assert record.attempt_number == 1
        assert record.reason == "flaky_test"
        assert len(record.failed_checks) == 2

    def test_ci_monitor_summary(self) -> None:
        """CIMonitorSummary creation with nested records."""
        from cub.core.ledger.models import CICheckRecord, CIMonitorSummary, CIRetryRecord

        summary = CIMonitorSummary(
            pr_number=42,
            final_state="succeeded",
            total_retries=2,
            retry_records=[
                CIRetryRecord(
                    attempt_number=1,
                    reason="flaky_test",
                    failed_checks=["tests"],
                ),
                CIRetryRecord(
                    attempt_number=2,
                    reason="flaky_test",
                    failed_checks=["tests"],
                    success=True,
                ),
            ],
            check_records=[
                CICheckRecord(name="tests", state="success"),
                CICheckRecord(name="lint", state="success"),
            ],
            duration_seconds=120.5,
        )
        assert summary.pr_number == 42
        assert summary.total_retries == 2
        assert len(summary.retry_records) == 2
        assert len(summary.check_records) == 2

    def test_ledger_entry_has_ci_monitor(self) -> None:
        """LedgerEntry includes ci_monitor field."""
        from cub.core.ledger.models import CIMonitorSummary, LedgerEntry

        entry = LedgerEntry(
            id="test-123",
            title="Test task",
        )
        assert entry.ci_monitor is None

        entry_with_ci = LedgerEntry(
            id="test-456",
            title="Test task with CI",
            ci_monitor=CIMonitorSummary(
                pr_number=42,
                final_state="succeeded",
                total_retries=1,
            ),
        )
        assert entry_with_ci.ci_monitor is not None
        assert entry_with_ci.ci_monitor.pr_number == 42


# ============================================================================
# Rate limit handling tests
# ============================================================================


class TestRateLimitHandling:
    """Tests for rate limit detection and handling."""

    def test_rate_limit_in_check_name(self) -> None:
        """Rate limit detected from check name."""
        monitor = PRMonitorService()
        summary = CheckSummary(
            checks=[CheckResult(name="api-rate-limit-exceeded", state=CheckState.FAILURE)]
        )
        assert monitor.detect_failure_reason(summary) == RetryReason.RATE_LIMIT

    def test_throttle_in_check_name(self) -> None:
        """Throttle keyword detected from check name."""
        monitor = PRMonitorService()
        summary = CheckSummary(
            checks=[CheckResult(name="throttled-request-handler", state=CheckState.FAILURE)]
        )
        assert monitor.detect_failure_reason(summary) == RetryReason.RATE_LIMIT

    def test_quota_in_check_name(self) -> None:
        """Quota keyword detected from check name."""
        monitor = PRMonitorService()
        summary = CheckSummary(
            checks=[CheckResult(name="quota-check", state=CheckState.FAILURE)]
        )
        assert monitor.detect_failure_reason(summary) == RetryReason.RATE_LIMIT


# ============================================================================
# Datetime parsing tests
# ============================================================================


class TestDatetimeParsing:
    """Tests for datetime parsing in monitor service."""

    def test_parse_valid_iso_datetime(self) -> None:
        """Valid ISO datetime is parsed correctly."""
        monitor = PRMonitorService()
        result = monitor._parse_datetime("2026-01-28T10:00:00Z")
        assert result is not None
        assert result.year == 2026

    def test_parse_none_datetime(self) -> None:
        """None input returns None."""
        monitor = PRMonitorService()
        assert monitor._parse_datetime(None) is None

    def test_parse_empty_datetime(self) -> None:
        """Empty string returns None."""
        monitor = PRMonitorService()
        assert monitor._parse_datetime("") is None

    def test_parse_invalid_datetime(self) -> None:
        """Invalid datetime string returns None."""
        monitor = PRMonitorService()
        assert monitor._parse_datetime("not-a-date") is None
