"""
FastAPI application setup for the cub dashboard.

Creates the FastAPI app instance and registers routes.
"""

import logging
import traceback
from enum import Enum

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cub.core.dashboard.api.routes import artifact, board, entity, stats, views

# Configure logging
logger = logging.getLogger(__name__)


# Error codes for consistent error responses
class ErrorCode(str, Enum):
    """Standard error codes for API responses."""

    # Client errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INVALID_PATH = "INVALID_PATH"
    INVALID_REQUEST = "INVALID_REQUEST"

    # Server errors (5xx)
    DATABASE_ERROR = "DATABASE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    FILE_READ_ERROR = "FILE_READ_ERROR"


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error_code: ErrorCode
    message: str
    detail: str | None = None
    request_id: str | None = None

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
app.include_router(artifact.router, prefix="/api", tags=["artifact"])
app.include_router(board.router, prefix="/api", tags=["board"])
app.include_router(entity.router, prefix="/api", tags=["entity"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(views.router, prefix="/api", tags=["views"])


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint - API health check."""
    return {"status": "ok", "message": "Cub Dashboard API"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


# Exception handlers for consistent error responses
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTPException with consistent error response format.

    Converts HTTPException to our standard error response format with error codes.
    Logs errors for debugging without exposing stack traces to clients.
    """
    # Determine error code based on status code and message
    error_code = ErrorCode.INTERNAL_ERROR
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        error_code = ErrorCode.NOT_FOUND
    elif exc.status_code == status.HTTP_400_BAD_REQUEST:
        # Check message for more specific error codes
        detail_lower = str(exc.detail).lower()
        if "path" in detail_lower:
            error_code = ErrorCode.INVALID_PATH
        else:
            error_code = ErrorCode.INVALID_REQUEST
    elif exc.status_code >= 500:
        # Server errors - determine type from message
        detail_lower = str(exc.detail).lower()
        if "database" in detail_lower:
            error_code = ErrorCode.DATABASE_ERROR
        elif "file" in detail_lower:
            error_code = ErrorCode.FILE_READ_ERROR
        else:
            error_code = ErrorCode.INTERNAL_ERROR

    # Log based on severity
    if exc.status_code >= 500:
        logger.error(
            "HTTP %d on %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
            extra={"request_id": id(request)},
        )
    else:
        logger.info(
            "HTTP %d on %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
            extra={"request_id": id(request)},
        )

    # For backward compatibility, include detail in the response
    detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": error_code,
            "message": detail_msg,
            "detail": detail_msg,  # Keep for backward compatibility
            "request_id": str(id(request)),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle validation errors from Pydantic models and query parameters.

    Returns a clean JSON response without exposing internal implementation details.
    Logs the full error for debugging.
    """
    # Log the full validation error with traceback
    logger.warning(
        "Validation error on %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
        extra={"request_id": id(request)},
    )

    # Extract first error for user-friendly message
    first_error = exc.errors()[0] if exc.errors() else {}
    field = " -> ".join(str(loc) for loc in first_error.get("loc", []))
    error_msg = first_error.get("msg", "Invalid input")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": ErrorCode.VALIDATION_ERROR,
            "message": "Request validation failed",
            "detail": f"{field}: {error_msg}" if field else error_msg,
            "request_id": str(id(request)),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all uncaught exceptions.

    Logs the full exception with traceback for debugging, but returns
    a clean error response to the client without exposing internal details.
    """
    # Log the full exception with traceback
    logger.error(
        "Unhandled exception on %s %s: %s\n%s",
        request.method,
        request.url.path,
        str(exc),
        traceback.format_exc(),
        extra={"request_id": id(request)},
    )

    # Determine error code and status based on exception type
    error_code = ErrorCode.INTERNAL_ERROR
    error_message = "An internal server error occurred"
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

    # Check for common exception patterns
    exc_str = str(exc).lower()
    if "database" in exc_str or "sqlite" in exc_str:
        error_code = ErrorCode.DATABASE_ERROR
        error_message = "Database operation failed"
    elif "file" in exc_str or "path" in exc_str:
        error_code = ErrorCode.FILE_READ_ERROR
        error_message = "File operation failed"

    return JSONResponse(
        status_code=http_status,
        content={
            "error_code": error_code,
            "message": error_message,
            "detail": str(exc),
            "request_id": str(id(request)),
        },
    )
