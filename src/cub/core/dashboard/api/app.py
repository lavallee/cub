"""
FastAPI application setup for the cub dashboard.

Creates the FastAPI app instance and registers routes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cub.core.dashboard.api.routes import board, entity

# Create FastAPI app
app = FastAPI(
    title="Cub Dashboard API",
    description="REST API for the cub project management dashboard",
    version="0.1.0",
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(board.router, prefix="/api", tags=["board"])
app.include_router(entity.router, prefix="/api", tags=["entity"])


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint - API health check."""
    return {"status": "ok", "message": "Cub Dashboard API"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
