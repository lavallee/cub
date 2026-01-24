"""
FastAPI application for the cub dashboard.

This module provides the REST API for the dashboard frontend,
serving data from the SQLite database populated by the sync layer.

API Endpoints:
- GET /api/board - Get full board data for Kanban visualization
- GET /api/entity/{id} - Get detailed entity with relationships
- GET /api/views - List available view configurations
- POST /api/sync - Trigger a sync operation

Usage:
    # Run the server
    uvicorn cub.core.dashboard.api.app:app --reload

    # Or from Python
    from cub.core.dashboard.api.app import app
"""

from cub.core.dashboard.api.app import app

__all__ = ["app"]
