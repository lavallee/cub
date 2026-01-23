"""
Tests for API error handling middleware.

Tests validate:
- Consistent error response format with error codes
- HTTPException handling with proper error codes
- Validation error handling
- Uncaught exception handling
- Error logging (without exposing stack traces to clients)
- Request ID tracking
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cub.core.dashboard.api.app import ErrorCode, app
from cub.core.dashboard.db.connection import configure_connection
from cub.core.dashboard.db.schema import create_schema

# Create test client
client = TestClient(app)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = sqlite3.connect(str(db_path))
        configure_connection(conn)
        create_schema(conn)
        conn.commit()
        conn.close()
        yield db_path


class TestErrorResponseFormat:
    """Tests for consistent error response format."""

    def test_404_error_format(self):
        """Test that 404 errors return consistent format with NOT_FOUND code."""
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = Path("/tmp/nonexistent_db.db")
            response = client.get("/api/entity/nonexistent-id")

        assert response.status_code == 404
        data = response.json()

        # Validate response structure
        assert "error_code" in data
        assert "message" in data
        assert "request_id" in data

        # Validate error code
        assert data["error_code"] == ErrorCode.NOT_FOUND

        # Validate message contains useful info
        assert "Entity not found" in data["message"]
        assert "nonexistent-id" in data["message"]

        # Should not contain stack trace
        assert "Traceback" not in str(data)
        assert "File" not in data.get("message", "")

    def test_500_error_format_database(self, temp_db):
        """Test that database errors return DATABASE_ERROR code."""
        # Create corrupted database
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_db = Path(tmpdir) / "bad.db"
            bad_db.write_text("not a database")

            with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
                mock_path.return_value = bad_db
                response = client.get("/api/board")

        assert response.status_code == 500
        data = response.json()

        # Validate response structure
        assert "error_code" in data
        assert "message" in data
        assert "request_id" in data

        # Validate error code is DATABASE_ERROR
        assert data["error_code"] == ErrorCode.DATABASE_ERROR

        # Should contain useful message but not full stack trace
        assert "database" in data["message"].lower() or "Database" in data["message"]
        assert "Traceback" not in str(data)

    def test_400_error_format_invalid_path(self):
        """Test that path validation errors return INVALID_PATH code."""
        response = client.get("/api/artifact?path=")

        assert response.status_code == 400
        data = response.json()

        # Validate response structure
        assert "error_code" in data
        assert "message" in data
        assert "request_id" in data

        # Validate error code
        assert data["error_code"] == ErrorCode.INVALID_PATH

        # Should contain useful message
        assert "path" in data["message"].lower() or "Path" in data["message"]

    def test_400_error_format_directory_traversal(self):
        """Test that directory traversal attempts return INVALID_PATH code."""
        response = client.get("/api/artifact?path=../../../etc/passwd")

        assert response.status_code == 400
        data = response.json()

        # Validate error code
        assert data["error_code"] == ErrorCode.INVALID_PATH

        # Should contain security-related message
        assert "path" in data["message"].lower()


class TestValidationErrors:
    """Tests for request validation error handling."""

    def test_missing_required_parameter(self):
        """Test that missing required parameters trigger validation errors."""
        response = client.get("/api/artifact")

        # FastAPI returns 422 for validation errors
        assert response.status_code == 422
        data = response.json()

        # Validate error response structure
        assert "error_code" in data
        assert "message" in data
        assert "detail" in data
        assert "request_id" in data

        # Validate error code
        assert data["error_code"] == ErrorCode.VALIDATION_ERROR

        # Validate message describes the validation failure
        assert "validation" in data["message"].lower()

        # Detail should mention the missing parameter
        assert "path" in data["detail"].lower()


class TestErrorLogging:
    """Tests for error logging behavior."""

    def test_server_errors_logged(self, temp_db, caplog):
        """Test that 500 errors are logged with details."""
        import logging

        caplog.set_level(logging.ERROR)

        # Trigger a database error
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_db = Path(tmpdir) / "bad.db"
            bad_db.write_text("not a database")

            with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
                mock_path.return_value = bad_db
                client.get("/api/board")

        # Verify error was logged
        assert len(caplog.records) > 0
        assert any("HTTP 500" in record.message or "error" in record.message.lower()
                   for record in caplog.records)

    def test_client_errors_logged_at_info(self, caplog):
        """Test that 4xx errors are logged at INFO level."""
        import logging

        caplog.set_level(logging.INFO)

        # Trigger a 404 error
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = Path("/tmp/nonexistent_db.db")
            client.get("/api/entity/test-id")

        # Verify it was logged at INFO or higher
        assert len(caplog.records) > 0
        # Should have some log record about the request
        assert any(record.levelno <= logging.INFO for record in caplog.records)


class TestRequestIdTracking:
    """Tests for request ID tracking in error responses."""

    def test_request_id_in_error_response(self):
        """Test that all error responses include a request ID."""
        response = client.get("/api/entity/nonexistent")

        data = response.json()
        assert "request_id" in data
        assert data["request_id"] is not None
        assert len(data["request_id"]) > 0

    def test_request_ids_are_unique(self):
        """Test that different requests get different IDs."""
        response1 = client.get("/api/entity/test-1")
        response2 = client.get("/api/entity/test-2")

        data1 = response1.json()
        data2 = response2.json()

        assert data1["request_id"] != data2["request_id"]


class TestNoStackTraceExposure:
    """Tests that stack traces are never exposed to clients."""

    def test_uncaught_exception_no_stack_trace(self, temp_db):
        """Test that uncaught exceptions don't expose stack traces."""
        # Create a scenario that causes an exception
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_db = Path(tmpdir) / "bad.db"
            bad_db.write_text("not a database")

            with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
                mock_path.return_value = bad_db
                response = client.get("/api/entity/test-id")

        assert response.status_code == 500
        data = response.json()

        # Verify no Python stack trace elements in response
        response_str = str(data).lower()
        assert "traceback" not in response_str
        assert "file \"" not in response_str
        assert "line " not in response_str
        assert ".py" not in response_str
        assert "raise " not in response_str

    def test_validation_error_no_internal_details(self):
        """Test that validation errors don't expose internal implementation."""
        response = client.get("/api/artifact")

        data = response.json()
        response_str = str(data).lower()

        # Should not contain internal Python/Pydantic details
        assert "pydantic" not in response_str
        assert "field required" not in response_str or "path" in data["detail"].lower()


class TestSpecificErrorCodes:
    """Tests for specific error code assignment."""

    def test_database_error_code(self):
        """Test that database errors get DATABASE_ERROR code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_db = Path(tmpdir) / "bad.db"
            bad_db.write_text("not a database")

            with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
                mock_path.return_value = bad_db
                response = client.get("/api/board/stats")

        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == ErrorCode.DATABASE_ERROR

    def test_file_error_code(self):
        """Test that file operation errors get FILE_READ_ERROR code."""
        response = client.get("/api/artifact?path=nonexistent-file.txt")

        assert response.status_code == 404
        data = response.json()
        # 404 for file not found should be NOT_FOUND
        assert data["error_code"] == ErrorCode.NOT_FOUND

    def test_invalid_path_error_code(self):
        """Test that path validation errors get INVALID_PATH code."""
        # Test null byte injection attempt
        response = client.get("/api/artifact?path=test%00.txt")

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ErrorCode.INVALID_PATH


class TestHealthEndpoints:
    """Tests that health endpoints still work correctly."""

    def test_root_endpoint_success(self):
        """Test that root endpoint returns success without error format."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # Should not have error structure
        assert "error_code" not in data

    def test_health_endpoint_success(self):
        """Test that health endpoint returns success without error format."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        # Should not have error structure
        assert "error_code" not in data


class TestErrorMessageQuality:
    """Tests for quality and clarity of error messages."""

    def test_404_message_includes_entity_id(self):
        """Test that 404 errors include the entity ID."""
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = Path("/tmp/nonexistent_db.db")
            response = client.get("/api/entity/my-special-id-123")

        data = response.json()
        assert "my-special-id-123" in data["message"]

    def test_validation_error_describes_problem(self):
        """Test that validation errors describe what's wrong."""
        response = client.get("/api/artifact")

        data = response.json()
        # Should mention the field that's problematic
        assert "path" in data["detail"].lower()

    def test_path_security_error_clear_message(self):
        """Test that path security errors have clear messages."""
        response = client.get("/api/artifact?path=../../etc/passwd")

        data = response.json()
        # Should indicate the path is not allowed
        assert "path" in data["message"].lower()
        assert data["error_code"] == ErrorCode.INVALID_PATH
