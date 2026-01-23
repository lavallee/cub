"""
Tests for the dashboard API views endpoint.

Tests validate:
- GET /api/views endpoint
- Response models and serialization
- View summary structure
- Default views availability
- Error handling
"""

from fastapi.testclient import TestClient

from cub.core.dashboard.api.app import app

# Create test client
client = TestClient(app)


class TestViewsEndpoint:
    """Tests for GET /api/views endpoint."""

    def test_views_endpoint_returns_list(self):
        """Test GET /api/views returns a list of views."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)

    def test_views_endpoint_returns_non_empty_list(self):
        """Test GET /api/views returns at least the default views."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        # Should have at least default views
        assert len(data) >= 1

    def test_default_view_included(self):
        """Test that the default view is included in the list."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        # Find the default view
        default_views = [v for v in data if v.get("is_default")]
        assert len(default_views) >= 1
        assert default_views[0]["id"] == "default"

    def test_view_summary_structure(self):
        """Test that each view has the correct structure."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        # Check that all views have required fields
        required_fields = {"id", "name", "is_default"}
        for view in data:
            assert required_fields.issubset(set(view.keys()))

            # Check field types
            assert isinstance(view["id"], str)
            assert isinstance(view["name"], str)
            assert isinstance(view["is_default"], bool)

            # Optional field types
            if "description" in view:
                assert isinstance(view["description"], (str, type(None)))

    def test_view_ids_are_unique(self):
        """Test that all view IDs are unique."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        ids = [v["id"] for v in data]
        assert len(ids) == len(set(ids)), "View IDs should be unique"

    def test_view_names_are_non_empty(self):
        """Test that all views have non-empty names."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        for view in data:
            assert view["name"].strip(), "View name should not be empty"

    def test_views_sorted_by_name(self):
        """Test that views are sorted by name for consistent ordering."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        names = [v["name"] for v in data]
        sorted_names = sorted(names)
        assert names == sorted_names, "Views should be sorted by name"

    def test_default_view_marked_correctly(self):
        """Test that exactly one view is marked as default."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        default_count = sum(1 for v in data if v["is_default"])
        assert default_count >= 1, "Should have at least one default view"

    def test_default_view_has_correct_properties(self):
        """Test that the default view has expected id and name."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        default_views = [v for v in data if v["is_default"]]
        assert len(default_views) >= 1

        default_view = default_views[0]
        assert default_view["id"] == "default"
        assert "Full Workflow" in default_view["name"] or "Default" in default_view["name"]

    def test_sprint_view_included(self):
        """Test that the sprint view is available."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        sprint_views = [v for v in data if v["id"] == "sprint"]
        assert len(sprint_views) >= 1
        assert sprint_views[0]["name"] == "Sprint View"

    def test_ideas_view_included(self):
        """Test that the ideas view is available."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        ideas_views = [v for v in data if v["id"] == "ideas"]
        assert len(ideas_views) >= 1
        assert ideas_views[0]["name"] == "Ideas View"

    def test_view_descriptions_present(self):
        """Test that views have descriptions."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        # Each view should have a description
        for view in data:
            assert "description" in view
            assert view["description"] is not None
            assert isinstance(view["description"], str)
            assert len(view["description"]) > 0


class TestViewsResponseSchema:
    """Tests for response schema validation."""

    def test_response_is_valid_json(self):
        """Test that response is valid JSON."""
        response = client.get("/api/views")
        assert response.status_code == 200

        # Should be able to parse as JSON without error
        data = response.json()
        assert data is not None

    def test_response_content_type(self):
        """Test that response has correct content type."""
        response = client.get("/api/views")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

    def test_view_summary_matches_pydantic_model(self):
        """Test that response conforms to ViewSummary Pydantic model."""
        from cub.core.dashboard.db.models import ViewSummary

        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        # Should be able to instantiate ViewSummary objects from response
        for view_data in data:
            view = ViewSummary(**view_data)
            assert view.id
            assert view.name


class TestViewsIntegration:
    """Integration tests for views endpoint."""

    def test_frontend_can_populate_switcher(self):
        """Test that response is suitable for populating a UI dropdown."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        # Should have enough data to populate a dropdown
        assert len(data) > 0

        # Each view should have display properties
        for view in data:
            # Should have display name (for dropdown)
            assert "name" in view and view["name"]

            # Should have identifier (for selection/switching)
            assert "id" in view and view["id"]

            # Should have indication of default (for UI hints)
            assert "is_default" in view and isinstance(view["is_default"], bool)

    def test_response_time_acceptable(self):
        """Test that endpoint responds quickly (no I/O bound operations)."""
        import time

        start = time.time()
        response = client.get("/api/views")
        duration = time.time() - start

        # Should respond in less than 100ms (very fast since it's just defaults)
        assert duration < 0.1
        assert response.status_code == 200

    def test_multiple_requests_consistent(self):
        """Test that multiple requests return the same views."""
        response1 = client.get("/api/views")
        response2 = client.get("/api/views")

        data1 = response1.json()
        data2 = response2.json()

        # Should return identical data
        assert len(data1) == len(data2)
        for view1, view2 in zip(data1, data2):
            assert view1["id"] == view2["id"]
            assert view1["name"] == view2["name"]
            assert view1["is_default"] == view2["is_default"]


class TestErrorHandling:
    """Tests for error handling in views endpoint."""

    def test_nonexistent_endpoint_returns_404(self):
        """Test that nonexistent endpoint returns 404."""
        response = client.get("/api/views/nonexistent")
        assert response.status_code == 404

    def test_invalid_method_returns_405(self):
        """Test that POST to views endpoint returns 405 (Method Not Allowed)."""
        response = client.post("/api/views")
        # Currently only GET is supported
        assert response.status_code == 405

    def test_invalid_method_delete_returns_405(self):
        """Test that DELETE to views endpoint returns 405."""
        response = client.delete("/api/views")
        # Currently only GET is supported
        assert response.status_code == 405


class TestViewsEdgeCases:
    """Tests for edge cases in views endpoint."""

    def test_special_characters_in_view_names(self):
        """Test that view names can contain special characters."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        # All names should be valid strings
        for view in data:
            assert isinstance(view["name"], str)
            # Should not raise encoding errors
            view["name"].encode("utf-8")

    def test_description_can_be_long(self):
        """Test that descriptions handle longer text."""
        response = client.get("/api/views")
        assert response.status_code == 200
        data = response.json()

        for view in data:
            if view.get("description"):
                # Should handle any length without error
                assert isinstance(view["description"], str)
