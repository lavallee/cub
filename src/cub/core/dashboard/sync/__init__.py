"""
Sync layer for the dashboard.

Provides parsers and orchestration for syncing entities from various sources
(specs, plans, tasks, ledger, changelog) into SQLite for the dashboard.

The sync layer handles:
- Parsing different data sources (specs, plans, tasks, ledger, releases)
- Computing entity stages based on type and status
- Resolving relationships via explicit markers (spec_id, plan_id, epic_id)
- Writing entities and relationships to SQLite
- Incremental sync using checksums to detect changes

Architecture:
- parsers/: Individual parsers for each data source
- orchestrator: Coordinates sync across all sources
- writer: SQLite write operations
"""

from cub.core.dashboard.sync.orchestrator import SyncOrchestrator
from cub.core.dashboard.sync.parsers.specs import SpecParser
from cub.core.dashboard.sync.writer import EntityWriter

__all__ = [
    "SyncOrchestrator",
    "SpecParser",
    "EntityWriter",
]
