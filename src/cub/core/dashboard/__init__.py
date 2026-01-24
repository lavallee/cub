"""
Dashboard system for cub.

Provides a unified view of project state by aggregating data from multiple sources:
- Specs (specs/**/*.md)
- Plans (.cub/sessions/*/plan.jsonl)
- Tasks (beads or JSON backend)
- Ledger entries (.cub/ledger/)
- Changelog (CHANGELOG.md)

The dashboard consists of:
- Database layer (db/) - SQLite schema and connection management
- Sync layer (sync/) - Import data from various sources
- API layer (api/) - FastAPI endpoints for web UI
- Models (models.py) - Pydantic models for dashboard entities

This module follows the architectural patterns established in cub.core.specs,
cub.core.tasks, and cub.core.ledger.
"""

__all__ = []
