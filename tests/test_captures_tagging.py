"""
Tests for capture auto-tagging functionality.

Tests the suggest_tags function for keyword extraction and tag suggestion.
"""


from cub.core.captures.tagging import suggest_tags


class TestSuggestTags:
    """Test the suggest_tags function."""

    def test_suggest_tags_git(self) -> None:
        """Test detection of git-related keywords."""
        assert "git" in suggest_tags("Fix git merge conflict")
        assert "git" in suggest_tags("Create new branch and push")
        assert "git" in suggest_tags("Need to rebase this pull request")

    def test_suggest_tags_ui(self) -> None:
        """Test detection of UI-related keywords."""
        assert "ui" in suggest_tags("Add dark mode to UI")
        assert "ui" in suggest_tags("Fix button styling issue")
        assert "ui" in suggest_tags("Create new dashboard component")

    def test_suggest_tags_api(self) -> None:
        """Test detection of API-related keywords."""
        assert "api" in suggest_tags("Implement new API endpoint")
        assert "api" in suggest_tags("Fix REST API response handling")
        assert "api" in suggest_tags("GraphQL query optimization")

    def test_suggest_tags_database(self) -> None:
        """Test detection of database-related keywords."""
        assert "database" in suggest_tags("Add database migration")
        assert "database" in suggest_tags("Optimize SQL queries")
        assert "database" in suggest_tags("Schema design for new feature")

    def test_suggest_tags_auth(self) -> None:
        """Test detection of authentication-related keywords."""
        assert "auth" in suggest_tags("Implement OAuth login flow")
        assert "auth" in suggest_tags("Fix JWT token validation")
        assert "auth" in suggest_tags("Session management issue")

    def test_suggest_tags_performance(self) -> None:
        """Test detection of performance-related keywords."""
        assert "performance" in suggest_tags("Optimize slow database queries")
        assert "performance" in suggest_tags("Fix slow performance issues")
        assert "performance" in suggest_tags("Memory leak investigation")

    def test_suggest_tags_security(self) -> None:
        """Test detection of security-related keywords."""
        assert "security" in suggest_tags("Fix XSS vulnerability")
        assert "security" in suggest_tags("Encrypt sensitive data")
        assert "security" in suggest_tags("CSRF protection needed")

    def test_suggest_tags_test(self) -> None:
        """Test detection of test-related keywords."""
        assert "test" in suggest_tags("Write unit tests for auth")
        assert "test" in suggest_tags("Add pytest coverage")
        assert "test" in suggest_tags("Mock API responses")

    def test_suggest_tags_docs(self) -> None:
        """Test detection of documentation-related keywords."""
        assert "docs" in suggest_tags("Update README")
        assert "docs" in suggest_tags("Write API documentation")
        assert "docs" in suggest_tags("Create setup guide")

    def test_suggest_tags_bug(self) -> None:
        """Test detection of bug-related keywords."""
        assert "bug" in suggest_tags("Fix broken login flow")
        assert "bug" in suggest_tags("Crash on invalid input")
        assert "bug" in suggest_tags("Error handling issue")

    def test_suggest_tags_feature(self) -> None:
        """Test detection of feature-related keywords."""
        assert "feature" in suggest_tags("Add dark mode support")
        assert "feature" in suggest_tags("Implement new export format")
        assert "feature" in suggest_tags("Enhance search functionality")

    def test_suggest_tags_refactor(self) -> None:
        """Test detection of refactoring-related keywords."""
        assert "refactor" in suggest_tags("Clean up legacy code")
        assert "refactor" in suggest_tags("Improve code organization")
        assert "refactor" in suggest_tags("Simplify API client")

    def test_suggest_tags_docker(self) -> None:
        """Test detection of Docker-related keywords."""
        assert "docker" in suggest_tags("Create Docker image")
        assert "docker" in suggest_tags("Update docker-compose configuration")
        assert "docker" in suggest_tags("Kubernetes deployment config")

    def test_suggest_tags_python(self) -> None:
        """Test detection of Python-related keywords."""
        assert "python" in suggest_tags("Update Python dependencies")
        assert "python" in suggest_tags("Create py module for tool")
        assert "python" in suggest_tags("pip requirements update")

    def test_suggest_tags_multiple(self) -> None:
        """Test multiple tags suggested from single content."""
        tags = suggest_tags("Fix git merge conflict in API endpoint")
        assert "git" in tags
        assert "api" in tags

    def test_suggest_tags_multiple_comprehensive(self) -> None:
        """Test comprehensive multi-tag suggestion."""
        tags = suggest_tags("Add auth UI component with API integration and test coverage")
        assert "auth" in tags
        assert "ui" in tags
        assert "api" in tags
        assert "test" in tags

    def test_suggest_tags_case_insensitive(self) -> None:
        """Test that keyword matching is case-insensitive."""
        assert "git" in suggest_tags("GIT merge conflict")
        assert "git" in suggest_tags("Git Merge Conflict")
        assert "git" in suggest_tags("gIt MeRgE cOnFlIcT")

    def test_suggest_tags_no_false_positives(self) -> None:
        """Test that non-matching content returns empty list."""
        tags = suggest_tags("This is a generic note about something random")
        assert len(tags) == 0

    def test_suggest_tags_empty_content(self) -> None:
        """Test with empty content."""
        tags = suggest_tags("")
        assert len(tags) == 0

    def test_suggest_tags_no_duplicate_tags(self) -> None:
        """Test that same tag is not suggested multiple times."""
        # Use a keyword that appears multiple times
        tags = suggest_tags("git pull git push git commit")
        # Should only have 'git' once
        assert tags.count("git") == 1

    def test_suggest_tags_order_preserved(self) -> None:
        """Test that tag order is consistent."""
        content = "Fix git merge conflict in API"
        tags1 = suggest_tags(content)
        tags2 = suggest_tags(content)
        assert tags1 == tags2

    def test_suggest_tags_partial_keywords(self) -> None:
        """Test that partial matches work (e.g., 'dark mode' as a keyword)."""
        assert "ui" in suggest_tags("Implement dark mode feature")
        assert "ui" in suggest_tags("Add light mode theme")

    def test_suggest_tags_long_content(self) -> None:
        """Test with longer, multi-line content."""
        content = """
        This capture describes implementing a new authentication system.
        We need to:
        1. Add OAuth login with JWT tokens
        2. Implement session management
        3. Add security checks
        4. Write unit tests
        5. Update documentation
        """
        tags = suggest_tags(content)
        assert "auth" in tags
        assert "security" in tags
        assert "test" in tags
        assert "docs" in tags

    def test_suggest_tags_mixed_keywords(self) -> None:
        """Test content with multiple tech stack keywords."""
        tags = suggest_tags("Refactor Python API with Docker container and database migration")
        assert "python" in tags
        assert "api" in tags
        assert "docker" in tags
        assert "database" in tags
        assert "refactor" in tags
