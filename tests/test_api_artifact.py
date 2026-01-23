"""
Tests for the dashboard API artifact endpoint.

Tests validate:
- GET /api/artifact endpoint
- Path validation and security against directory traversal
- File content retrieval
- Error handling (400, 404, 500)

SECURITY FOCUS: This test suite specifically validates defenses against:
- Directory traversal attacks (../)
- Null byte injection
- Symlink attacks
- Path manipulation
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cub.core.dashboard.api.app import app

# Create test client
client = TestClient(app)


@pytest.fixture
def temp_project():
    """Create a temporary project directory structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create a typical project structure
        specs_dir = project_root / "specs"
        specs_dir.mkdir()

        cub_dir = project_root / ".cub"
        cub_dir.mkdir()

        sessions_dir = cub_dir / "sessions"
        sessions_dir.mkdir()

        # Create test files
        spec_file = specs_dir / "test-feature.md"
        spec_file.write_text("# Test Feature\n\nThis is a test spec.")

        readme = project_root / "README.md"
        readme.write_text("# Project README\n")

        # Create a nested file
        nested_dir = specs_dir / "nested"
        nested_dir.mkdir()
        nested_file = nested_dir / "deep-spec.md"
        nested_file.write_text("# Deep Spec\n\nNested spec file.")

        yield project_root


class TestArtifactEndpoint:
    """Tests for GET /api/artifact endpoint."""

    def test_artifact_fetch_relative_path(self, temp_project):
        """Test fetching a file using a relative path."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "specs/test-feature.md"})

        assert response.status_code == 200
        data = response.json()

        assert "path" in data
        assert "content" in data
        assert "size" in data

        assert data["path"] == "specs/test-feature.md"
        assert "# Test Feature" in data["content"]
        assert data["size"] > 0

    def test_artifact_fetch_absolute_path(self, temp_project):
        """Test fetching a file using an absolute path within project."""
        abs_path = temp_project / "specs" / "test-feature.md"

        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": str(abs_path)})

        assert response.status_code == 200
        data = response.json()

        # Should return relative path even when given absolute
        assert data["path"] == "specs/test-feature.md"

    def test_artifact_fetch_nested_file(self, temp_project):
        """Test fetching a file from nested directory."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get(
                "/api/artifact", params={"path": "specs/nested/deep-spec.md"}
            )

        assert response.status_code == 200
        data = response.json()

        assert "# Deep Spec" in data["content"]

    def test_artifact_file_not_found(self, temp_project):
        """Test 404 for non-existent files."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "does/not/exist.md"})

        assert response.status_code == 404
        data = response.json()
        assert "File not found" in data["detail"]

    def test_artifact_empty_path(self, temp_project):
        """Test 400 for empty path."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": ""})

        assert response.status_code == 400
        data = response.json()
        assert "required" in data["detail"].lower()

    def test_artifact_whitespace_path(self, temp_project):
        """Test 400 for whitespace-only path."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "   "})

        assert response.status_code == 400

    def test_artifact_missing_path_parameter(self, temp_project):
        """Test 422 when path parameter is missing."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact")

        # FastAPI returns 422 for missing required query params
        assert response.status_code == 422


class TestDirectoryTraversalPrevention:
    """Security tests for directory traversal attack prevention."""

    def test_traversal_simple_dotdot(self, temp_project):
        """Test blocking simple ../ traversal."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "../etc/passwd"})

        assert response.status_code == 400
        assert "must be within project" in response.json()["detail"]

    def test_traversal_encoded_dotdot(self, temp_project):
        """Test blocking URL-encoded traversal attempts."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            # Note: FastAPI/Starlette handles URL decoding before we see the path
            response = client.get("/api/artifact", params={"path": "..%2F..%2Fetc/passwd"})

        # Either 400 (path outside project) or 404 (decoded path not found within project)
        assert response.status_code in (400, 404)

    def test_traversal_multiple_levels(self, temp_project):
        """Test blocking multiple directory traversal levels."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get(
                "/api/artifact",
                params={"path": "specs/../../../../../../../etc/passwd"},
            )

        assert response.status_code == 400
        assert "must be within project" in response.json()["detail"]

    def test_traversal_absolute_path_outside(self, temp_project):
        """Test blocking absolute paths outside project."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "/etc/passwd"})

        assert response.status_code == 400
        assert "must be within project" in response.json()["detail"]

    def test_traversal_with_valid_prefix(self, temp_project):
        """Test blocking traversal that starts with valid directory."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get(
                "/api/artifact", params={"path": "specs/../../etc/passwd"}
            )

        assert response.status_code == 400
        assert "must be within project" in response.json()["detail"]

    def test_traversal_backslash(self, temp_project):
        """Test blocking Windows-style backslash traversal."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get(
                "/api/artifact", params={"path": "..\\..\\etc\\passwd"}
            )

        # Path.resolve() handles this; should be blocked or not found
        assert response.status_code in (400, 404)

    def test_traversal_mixed_slashes(self, temp_project):
        """Test blocking mixed forward/back slash traversal."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get(
                "/api/artifact", params={"path": "specs\\..\\..\\etc/passwd"}
            )

        assert response.status_code in (400, 404)


class TestNullByteInjection:
    """Security tests for null byte injection prevention."""

    def test_null_byte_in_path(self, temp_project):
        """Test blocking null byte in path."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get(
                "/api/artifact", params={"path": "specs/test-feature.md\x00.jpg"}
            )

        assert response.status_code == 400
        assert "null bytes" in response.json()["detail"]

    def test_null_byte_prefix(self, temp_project):
        """Test blocking null byte at start of path."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "\x00specs/test.md"})

        assert response.status_code == 400
        assert "null bytes" in response.json()["detail"]


class TestSymlinkHandling:
    """Tests for symlink handling."""

    def test_symlink_within_project(self, temp_project):
        """Test that symlinks within project are allowed."""
        # Create a symlink within the project
        link_path = temp_project / "link-to-spec.md"
        target_path = temp_project / "specs" / "test-feature.md"

        try:
            link_path.symlink_to(target_path)
        except OSError:
            pytest.skip("Symlinks not supported on this filesystem")

        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "link-to-spec.md"})

        # Should succeed since target is within project
        assert response.status_code == 200
        assert "# Test Feature" in response.json()["content"]

    def test_symlink_outside_project(self, temp_project):
        """Test that symlinks pointing outside project are blocked."""
        # Create an external file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("External secret content")
            external_file = Path(f.name)

        try:
            # Create a symlink in project pointing to external file
            link_path = temp_project / "external-link.md"
            link_path.symlink_to(external_file)

            with patch(
                "cub.core.dashboard.api.routes.artifact.get_project_root"
            ) as mock_root:
                mock_root.return_value = temp_project
                response = client.get(
                    "/api/artifact", params={"path": "external-link.md"}
                )

            # Should be blocked because resolved path is outside project
            assert response.status_code == 400
            assert "must be within project" in response.json()["detail"]
        except OSError:
            pytest.skip("Symlinks not supported on this filesystem")
        finally:
            external_file.unlink()


class TestFileTypeHandling:
    """Tests for different file types."""

    def test_directory_rejected(self, temp_project):
        """Test that directories are rejected."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "specs"})

        assert response.status_code == 400
        assert "regular file" in response.json()["detail"]

    def test_binary_file_rejected(self, temp_project):
        """Test that binary files are rejected."""
        # Create a binary file
        binary_file = temp_project / "test.bin"
        binary_file.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")

        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "test.bin"})

        assert response.status_code == 400
        assert "binary" in response.json()["detail"].lower()


class TestResponseSchema:
    """Tests for response format."""

    def test_response_has_required_fields(self, temp_project):
        """Test that response contains all required fields."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "README.md"})

        assert response.status_code == 200
        data = response.json()

        assert "path" in data
        assert "content" in data
        assert "size" in data

        assert isinstance(data["path"], str)
        assert isinstance(data["content"], str)
        assert isinstance(data["size"], int)

    def test_size_matches_content_length(self, temp_project):
        """Test that size field matches actual content length."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "README.md"})

        assert response.status_code == 200
        data = response.json()

        assert data["size"] == len(data["content"])


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_path_with_spaces(self, temp_project):
        """Test handling paths with spaces."""
        # Create a file with spaces in name
        space_file = temp_project / "file with spaces.md"
        space_file.write_text("Content with spaces in filename")

        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get(
                "/api/artifact", params={"path": "file with spaces.md"}
            )

        assert response.status_code == 200
        assert "spaces in filename" in response.json()["content"]

    def test_path_with_unicode(self, temp_project):
        """Test handling paths with unicode characters."""
        # Create a file with unicode name
        unicode_file = temp_project / "spec-\u4e2d\u6587.md"
        unicode_file.write_text("Unicode filename content")

        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get(
                "/api/artifact", params={"path": "spec-\u4e2d\u6587.md"}
            )

        assert response.status_code == 200
        assert "Unicode filename" in response.json()["content"]

    def test_hidden_file(self, temp_project):
        """Test that hidden files (dotfiles) can be accessed."""
        hidden_file = temp_project / ".hidden-config"
        hidden_file.write_text("hidden content")

        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": ".hidden-config"})

        # Hidden files within project are allowed
        assert response.status_code == 200
        assert "hidden content" in response.json()["content"]

    def test_dot_in_path(self, temp_project):
        """Test that single dot in path is handled."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "./README.md"})

        assert response.status_code == 200

    def test_double_slash_in_path(self, temp_project):
        """Test handling of double slashes in path."""
        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": "specs//test-feature.md"})

        # Path.resolve() normalizes this
        assert response.status_code == 200

    def test_very_long_path(self, temp_project):
        """Test handling of very long paths."""
        long_path = "a" * 1000 + "/test.md"

        with patch(
            "cub.core.dashboard.api.routes.artifact.get_project_root"
        ) as mock_root:
            mock_root.return_value = temp_project
            response = client.get("/api/artifact", params={"path": long_path})

        # Should fail gracefully with 400 or 404, not crash
        assert response.status_code in (400, 404)
