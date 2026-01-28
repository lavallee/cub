"""
Service layer for cub.

Services are stateless orchestrators that compose domain operations into clean
API surfaces. Any interface (CLI, API, skills, future UIs) calls service methods
instead of reaching into core packages directly.

Design principles:
- Every user-facing action maps to a service method.
- Methods accept typed inputs, return typed outputs, raise typed exceptions.
- No Rich, no sys.exit, no print statements—presentation is the caller's job.
- Services are created via factory methods that accept configuration.

Modules:
    run: RunService wraps core/run/ to provide run loop orchestration.
    launch: LaunchService handles environment detection and harness launching.
    ledger: LedgerService provides ledger queries and stats.
    status: StatusService aggregates project state from multiple sources.
    models: Data models used across services (ProjectStats, EpicProgress, etc.)
"""

from cub.core.services.launch import (
    HarnessNotFoundError,
    LaunchService,
    LaunchServiceError,
)
from cub.core.services.ledger import (
    LedgerQuery,
    LedgerService,
    LedgerServiceError,
    StatsQuery,
)
from cub.core.services.models import EpicProgress, LedgerStats, ProjectStats
from cub.core.services.run import RunService
from cub.core.services.status import StatusService, StatusServiceError

__all__ = [
    # Run service
    "RunService",
    # Launch service
    "LaunchService",
    "LaunchServiceError",
    "HarnessNotFoundError",
    # Ledger service
    "LedgerService",
    "LedgerServiceError",
    "LedgerQuery",
    "StatsQuery",
    # Status service
    "StatusService",
    "StatusServiceError",
    # Models
    "ProjectStats",
    "EpicProgress",
    "LedgerStats",
]
