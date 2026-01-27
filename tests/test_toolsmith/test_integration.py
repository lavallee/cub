"""
Integration tests for toolsmith full workflow.

Tests complete workflows including:
- Sync from all mocked sources
- Search catalog (local and live fallback)
- CLI commands
- Error handling with partial source failures
"""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest
from typer.testing import CliRunner

from cub.cli.toolsmith import app
from cub.core.toolsmith.models import ToolType
from cub.core.toolsmith.service import ToolsmithService
from cub.core.toolsmith.sources import get_all_sources
from cub.core.toolsmith.store import ToolsmithStore


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


class TestFullSyncWorkflow:
    """Test complete sync workflow from all sources."""

    @patch("httpx.get")
    def test_sync_all_sources_success(
        self,
        mock_get: Mock,
        temp_store: ToolsmithStore,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test successful sync from all mocked sources."""
        mock_get.side_effect = mock_http_response_factory

        # Create service and sync
        sources = get_all_sources()
        service = ToolsmithService(temp_store, sources)
        result = service.sync()

        # Verify sync succeeded
        assert result.tools_added > 0, "Should have added tools from sources"
        assert result.tools_updated == 0, "First sync should only add, not update"
        assert result.errors == [], f"Should have no errors, got: {result.errors}"

        # Verify catalog was saved
        catalog = temp_store.load_catalog()
        assert len(catalog.tools) > 0, "Catalog should contain tools"
        assert catalog.last_sync is not None, "Should have sync timestamp"
        assert len(catalog.sources_synced) > 0, "Should track synced sources"

    @patch("httpx.get")
    def test_sync_populates_catalog_with_tools(
        self,
        mock_get: Mock,
        temp_store: ToolsmithStore,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test that synced tools appear in catalog with correct fields."""
        mock_get.side_effect = mock_http_response_factory

        # Create service with all sources and sync
        sources = get_all_sources()
        service = ToolsmithService(temp_store, sources)
        service.sync()

        # Verify tools in catalog
        catalog = temp_store.load_catalog()
        smithery_tools = [t for t in catalog.tools if t.source == "smithery"]

        assert len(smithery_tools) > 0, "Should have Smithery tools"

        # Verify tool fields
        for tool in smithery_tools:
            assert tool.id.startswith("smithery:"), (
                f"Tool ID should start with 'smithery:', got: {tool.id}"
            )
            assert tool.name, "Tool should have name"
            assert tool.source == "smithery", "Tool should have correct source"
            assert tool.source_url, "Tool should have source URL"
            assert tool.tool_type == ToolType.MCP_SERVER, "Smithery tools should be MCP servers"
            assert tool.description, "Tool should have description"
            assert tool.last_seen is not None, "Tool should have last_seen timestamp"

    @patch("httpx.get")
    def test_sync_updates_existing_tools_on_second_run(
        self,
        mock_get: Mock,
        temp_store: ToolsmithStore,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test that running sync again updates existing tools."""
        mock_get.side_effect = mock_http_response_factory

        # Create service
        sources = get_all_sources()
        service = ToolsmithService(temp_store, sources)

        # First sync
        result1 = service.sync()
        tools_added_first = result1.tools_added

        # Second sync (same data)
        result2 = service.sync()

        # Should update existing tools, not add new ones
        assert result2.tools_added == 0, "Second sync should not add new tools"
        assert result2.tools_updated == tools_added_first, (
            "Should update all previously added tools"
        )


class TestSearchWorkflow:
    """Test search workflow including local and live fallback."""

    @patch("httpx.get")
    def test_search_finds_synced_tools_locally(
        self,
        mock_get: Mock,
        temp_store: ToolsmithStore,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test that search finds tools after sync."""
        mock_get.side_effect = mock_http_response_factory

        # Sync tools
        sources = get_all_sources()
        service = ToolsmithService(temp_store, sources)
        service.sync()

        # Search for a tool (Smithery response has "fetch" tool)
        results = service.search("fetch")

        # Should find the tool locally
        assert len(results) > 0, "Should find tools matching 'fetch'"
        assert any("fetch" in tool.name.lower() for tool in results), (
            "Results should include fetch tool"
        )

    @patch("httpx.get")
    def test_search_live_fallback_when_no_local_results(
        self,
        mock_get: Mock,
        temp_store: ToolsmithStore,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test that search falls back to live sources when local search is empty."""
        mock_get.side_effect = mock_http_response_factory

        # Create service with empty catalog
        sources = get_all_sources()
        service = ToolsmithService(temp_store, sources)

        # Search for something that won't be in empty catalog
        results = service.search("weather")

        # Should perform live search and return results
        assert mock_get.called, "Should make HTTP request for live search"
        assert isinstance(results, list), "Should return list of results"

    @patch("httpx.get")
    def test_search_no_fallback_when_disabled(
        self,
        mock_get: Mock,
        temp_store: ToolsmithStore,
    ) -> None:
        """Test that search with live_fallback=False only searches local catalog."""
        # Create service with empty catalog
        sources = get_all_sources()
        service = ToolsmithService(temp_store, sources)

        # Search with live_fallback disabled
        results = service.search("test", live_fallback=False)

        # Should not make HTTP requests
        assert not mock_get.called, "Should not make HTTP request when live_fallback=False"
        assert results == [], "Should return empty results for empty catalog"


class TestErrorHandling:
    """Test error handling and partial sync on source failures."""

    @patch("httpx.get")
    def test_sync_continues_on_source_failure(
        self,
        mock_get: Mock,
        temp_store: ToolsmithStore,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test that sync continues with other sources when one raises an exception."""
        # Mock httpx.get to work normally
        mock_get.side_effect = mock_http_response_factory

        # Get all sources
        sources = get_all_sources()

        # Patch the first source's fetch_tools to raise an exception
        original_fetch = sources[0].fetch_tools

        def failing_fetch() -> list:
            raise Exception("Simulated source failure")

        sources[0].fetch_tools = failing_fetch

        # Create service and sync
        service = ToolsmithService(temp_store, sources)
        result = service.sync()

        # Should have error from the failing source
        assert len(result.errors) > 0, "Should report errors from failed sources"
        assert "Simulated source failure" in result.errors[0]

        # Should still have synced from other sources
        assert result.tools_added > 0, "Should sync tools from working sources"

        # Verify partial sync succeeded
        catalog = temp_store.load_catalog()
        assert isinstance(catalog.tools, list), "Catalog should be valid"
        assert len(catalog.tools) > 0, "Should have tools from working sources"

        # Restore original method
        sources[0].fetch_tools = original_fetch

    @patch("httpx.get")
    def test_sync_partial_success_adds_available_tools(
        self,
        mock_get: Mock,
        temp_store: ToolsmithStore,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test that partial sync adds tools from working sources."""
        # Mock httpx.get to work normally
        mock_get.side_effect = mock_http_response_factory

        # Get all sources
        sources = get_all_sources()

        # Make all sources except the first one fail
        original_methods = []
        for i, source in enumerate(sources):
            if i > 0:  # Skip first source
                original_methods.append((i, source.fetch_tools))

                def failing_fetch() -> list:
                    raise Exception("Simulated source failure")

                source.fetch_tools = failing_fetch

        # Sync
        service = ToolsmithService(temp_store, sources)
        result = service.sync()

        # Should have added tools from working source (first one)
        assert result.tools_added > 0, "Should add tools from working sources"
        assert len(result.errors) > 0, "Should report errors from failed sources"

        # Verify catalog has tools
        catalog = temp_store.load_catalog()
        assert len(catalog.tools) > 0, "Should have tools from successful source"

        # Restore original methods
        for idx, original_method in original_methods:
            sources[idx].fetch_tools = original_method

    @patch("cub.core.toolsmith.http.time.sleep")
    @patch("httpx.get")
    def test_search_handles_source_errors_gracefully(
        self,
        mock_get: Mock,
        mock_sleep: Mock,
        temp_store: ToolsmithStore,
    ) -> None:
        """Test that search continues when a source fails."""
        # Make all sources fail
        mock_get.side_effect = httpx.HTTPError("Network error")

        # Create service
        sources = get_all_sources()
        service = ToolsmithService(temp_store, sources)

        # Search should not raise exception
        results = service.search("test")

        # Should return empty results gracefully
        assert results == [], "Should return empty results when all sources fail"


class TestCLICommands:
    """Test CLI commands with mocked service."""

    @patch("httpx.get")
    def test_sync_command_success(
        self,
        mock_get: Mock,
        cli_runner: CliRunner,
        tmp_path: Path,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test 'cub toolsmith sync' command."""
        mock_get.side_effect = mock_http_response_factory

        # Mock store location
        with patch("cub.cli.toolsmith.ToolsmithStore.default") as mock_default:
            mock_default.return_value = ToolsmithStore(tmp_path / "toolsmith")

            # Run sync command
            result = cli_runner.invoke(app, ["sync"])

            # Verify success
            assert result.exit_code == 0, f"Command failed: {result.stdout}"
            assert "Sync complete" in result.stdout
            assert "Sync Statistics" in result.stdout or "Tools added" in result.stdout

    @patch("httpx.get")
    def test_sync_command_with_source_filter(
        self,
        mock_get: Mock,
        cli_runner: CliRunner,
        tmp_path: Path,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test 'cub toolsmith sync --source smithery' command."""
        mock_get.side_effect = mock_http_response_factory

        # Mock store location
        with patch("cub.cli.toolsmith.ToolsmithStore.default") as mock_default:
            mock_default.return_value = ToolsmithStore(tmp_path / "toolsmith")

            # Run sync with source filter
            result = cli_runner.invoke(app, ["sync", "--source", "smithery"])

            # Verify success
            assert result.exit_code == 0, f"Command failed: {result.stdout}"
            assert "Sync complete" in result.stdout

    @patch("cub.core.toolsmith.service.ToolsmithService.sync")
    def test_sync_command_reports_errors(
        self,
        mock_sync: Mock,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync command reports errors properly."""
        # Mock sync to return errors
        from cub.core.toolsmith.models import SyncResult

        mock_sync.return_value = SyncResult(
            tools_added=0,
            tools_updated=0,
            errors=["Source 'smithery' failed: Network error", "Source 'glama' failed: Timeout"],
        )

        # Mock store location
        with patch("cub.cli.toolsmith.ToolsmithStore.default") as mock_default:
            mock_default.return_value = ToolsmithStore(tmp_path / "toolsmith")

            # Run sync command
            result = cli_runner.invoke(app, ["sync"])

            # Should report errors and exit with error code
            assert result.exit_code == 1, "Should exit with error code on failure"
            assert "Warnings" in result.stdout  # CLI displays errors as "Warnings"

    @patch("httpx.get")
    def test_search_command_success(
        self,
        mock_get: Mock,
        cli_runner: CliRunner,
        tmp_path: Path,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test 'cub toolsmith search' command."""
        mock_get.side_effect = mock_http_response_factory

        # Mock store location
        with patch("cub.cli.toolsmith.ToolsmithStore.default") as mock_default:
            store = ToolsmithStore(tmp_path / "toolsmith")
            mock_default.return_value = store

            # First sync to populate catalog
            result = cli_runner.invoke(app, ["sync"])
            assert result.exit_code == 0

            # Then search
            result = cli_runner.invoke(app, ["search", "fetch"])

            # Verify output
            assert result.exit_code == 0, f"Command failed: {result.stdout}"
            # Should show search results table or "no tools found"
            assert "Search Results" in result.stdout or "No tools found" in result.stdout

    @patch("httpx.get")
    def test_search_command_with_source_filter(
        self,
        mock_get: Mock,
        cli_runner: CliRunner,
        tmp_path: Path,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test 'cub toolsmith search --source smithery' command."""
        mock_get.side_effect = mock_http_response_factory

        # Mock store location
        with patch("cub.cli.toolsmith.ToolsmithStore.default") as mock_default:
            store = ToolsmithStore(tmp_path / "toolsmith")
            mock_default.return_value = store

            # Sync first
            result = cli_runner.invoke(app, ["sync"])
            assert result.exit_code == 0

            # Search with source filter
            result = cli_runner.invoke(app, ["search", "test", "--source", "smithery"])

            # Should succeed
            assert result.exit_code == 0, f"Command failed: {result.stdout}"

    @patch("httpx.get")
    def test_stats_command_success(
        self,
        mock_get: Mock,
        cli_runner: CliRunner,
        tmp_path: Path,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test 'cub toolsmith stats' command."""
        mock_get.side_effect = mock_http_response_factory

        # Mock store location
        with patch("cub.cli.toolsmith.ToolsmithStore.default") as mock_default:
            store = ToolsmithStore(tmp_path / "toolsmith")
            mock_default.return_value = store

            # Sync first to populate catalog
            result = cli_runner.invoke(app, ["sync"])
            assert result.exit_code == 0

            # Run stats command
            result = cli_runner.invoke(app, ["stats"])

            # Verify output
            assert result.exit_code == 0, f"Command failed: {result.stdout}"
            assert "Tool Catalog Overview" in result.stdout or "Total tools" in result.stdout
            assert "Total tools" in result.stdout

    def test_stats_command_empty_catalog(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test 'cub toolsmith stats' with empty catalog."""
        # Mock store location
        with patch("cub.cli.toolsmith.ToolsmithStore.default") as mock_default:
            store = ToolsmithStore(tmp_path / "toolsmith")
            mock_default.return_value = store

            # Run stats on empty catalog
            result = cli_runner.invoke(app, ["stats"])

            # Should succeed and show empty state
            assert result.exit_code == 0, f"Command failed: {result.stdout}"
            assert (
                "Total tools: 0" in result.stdout or "No sources have been synced" in result.stdout
            )


class TestEndToEndWorkflow:
    """Test complete end-to-end workflow."""

    @patch("httpx.get")
    def test_complete_workflow_sync_search_stats(
        self,
        mock_get: Mock,
        temp_store: ToolsmithStore,
        mock_http_response_factory: Callable[[str], Mock],
    ) -> None:
        """Test complete workflow: sync → search → stats."""
        mock_get.side_effect = mock_http_response_factory

        # Create service
        sources = get_all_sources()
        service = ToolsmithService(temp_store, sources)

        # 1. Sync tools
        sync_result = service.sync()
        assert sync_result.tools_added > 0, "Should add tools during sync"
        assert sync_result.errors == [], "Should have no errors"

        # 2. Search for tools
        search_results = service.search("fetch")
        assert len(search_results) > 0, "Should find tools after sync"

        # 3. Get stats
        stats = service.stats()
        assert stats.total_tools > 0, "Stats should show tools"
        assert len(stats.by_source) > 0, "Stats should show sources"
        assert stats.last_sync is not None, "Stats should show last sync time"

        # Verify consistency
        assert stats.total_tools == sync_result.tools_added, "Stats should match sync result"
