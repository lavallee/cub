"""
Ledger package for cub.

The ledger provides persistent tracking of completed work, bridging the gap
between in-progress tasks (beads) and permanent record (git commits). It
captures task intent, execution trace, costs, and outcomes for both human
auditing and agent context recovery.

See specs/researching/knowledge-retention-system.md for design details.

Public API:
    # Data models
    LedgerEntry: Individual task completion record
    LedgerIndex: Quick-lookup index entry (for index.jsonl)
    CommitRef: Git commit reference
    EpicSummary: Aggregated epic metrics
    TokenUsage: Token consumption tracking
    VerificationStatus: Verification check status enum
    LedgerStats: Aggregate statistics across ledger

Example:
    >>> from cub.core.ledger import LedgerEntry, TokenUsage, VerificationStatus
    >>> entry = LedgerEntry(
    ...     id="beads-abc",
    ...     title="Implement auth",
    ...     cost_usd=0.09,
    ...     tokens=TokenUsage(input_tokens=45000, output_tokens=12000),
    ...     verification_status=VerificationStatus.PASS
    ... )
    >>> entry.duration_minutes
    0.0
    >>> entry.tokens.total_tokens
    57000
"""

from cub.core.ledger.models import (
    CommitRef,
    EpicSummary,
    LedgerEntry,
    LedgerIndex,
    LedgerStats,
    TokenUsage,
    VerificationStatus,
)

__all__ = [
    # Core models
    "LedgerEntry",
    "LedgerIndex",
    "CommitRef",
    "EpicSummary",
    "LedgerStats",
    # Supporting models
    "TokenUsage",
    "VerificationStatus",
]
