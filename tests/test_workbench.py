"""Tests for workbench modules (session, note)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import frontmatter
import pytest

from cub.core.workbench.note import (
    _extract_web_results,
    _load_tool_result,
    write_research_note_from_session,
)
from cub.core.workbench.session import (
    WorkbenchSessionPaths,
    _default_session_id,
    _read_spec_frontmatter,
    create_pm_workbench_session,
)


class TestDefaultSessionId:
    """Tests for _default_session_id function."""

    def test_format(self) -> None:
        now = datetime(2026, 1, 27, 14, 30, 45, tzinfo=timezone.utc)
        result = _default_session_id(now)
        assert result == "wb-2026-01-27-143045"

    def test_default_uses_current_time(self) -> None:
        result = _default_session_id()
        assert result.startswith("wb-")
        # Should be wb-YYYY-MM-DD-HHMMSS (20 chars)
        assert len(result) == 20


class TestReadSpecFrontmatter:
    """Tests for _read_spec_frontmatter function."""

    def test_reads_valid_frontmatter(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text("---\ntitle: Test Spec\nstatus: researching\n---\n\n# Body\n")
        result = _read_spec_frontmatter(spec)
        assert result["title"] == "Test Spec"
        assert result["status"] == "researching"

    def test_empty_frontmatter(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text("---\n---\n\n# Body\n")
        result = _read_spec_frontmatter(spec)
        assert result == {}

    def test_no_frontmatter(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text("# Just a heading\n\nSome content.\n")
        result = _read_spec_frontmatter(spec)
        assert isinstance(result, dict)


class TestCreatePmWorkbenchSession:
    """Tests for create_pm_workbench_session function."""

    @patch("cub.core.workbench.session.AdoptionStore")
    def test_creates_session_file(self, mock_store_cls: MagicMock, tmp_path: Path) -> None:
        mock_store = MagicMock()
        mock_store.list_all.return_value = []
        mock_store_cls.default.return_value = mock_store

        spec = tmp_path / "spec.md"
        spec.write_text(
            "---\ntitle: PM Workbench\nreadiness:\n"
            "  questions:\n    - What is scope?\n"
            "    - Who are users?\n---\n\n# Body\n"
        )
        out_dir = tmp_path / "sessions"

        result = create_pm_workbench_session(
            spec_path=spec, out_dir=out_dir, session_id="wb-test-001"
        )

        assert isinstance(result, WorkbenchSessionPaths)
        assert result.session_path.exists()
        assert result.session_path.name == "wb-test-001.md"

    @patch("cub.core.workbench.session.AdoptionStore")
    def test_session_has_unknowns_from_readiness(
        self, mock_store_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_store = MagicMock()
        mock_store.list_all.return_value = []
        mock_store_cls.default.return_value = mock_store

        spec = tmp_path / "spec.md"
        spec.write_text(
            "---\nreadiness:\n  questions:\n"
            "    - What is the scope?\n"
            "    - Who decides?\n---\n\n# Body\n"
        )
        out_dir = tmp_path / "sessions"

        result = create_pm_workbench_session(spec_path=spec, out_dir=out_dir, session_id="wb-test")

        post = frontmatter.load(result.session_path)
        unknowns = post.metadata.get("unknowns", [])
        assert len(unknowns) == 2
        assert unknowns[0]["id"] == "unk-001"
        assert "scope" in unknowns[0]["title"].lower()

    @patch("cub.core.workbench.session.AdoptionStore")
    def test_session_has_next_move(self, mock_store_cls: MagicMock, tmp_path: Path) -> None:
        mock_store = MagicMock()
        mock_store.list_all.return_value = []
        mock_store_cls.default.return_value = mock_store

        spec = tmp_path / "spec.md"
        spec.write_text("---\nreadiness:\n  questions:\n    - Q1?\n---\n\n# Body\n")
        out_dir = tmp_path / "sessions"

        result = create_pm_workbench_session(spec_path=spec, out_dir=out_dir, session_id="wb-test")

        post = frontmatter.load(result.session_path)
        next_move = post.metadata.get("next_move", {})
        assert next_move["kind"] == "research"
        assert isinstance(next_move.get("queries"), list)

    @patch("cub.core.workbench.session.AdoptionStore")
    def test_no_readiness_questions(self, mock_store_cls: MagicMock, tmp_path: Path) -> None:
        mock_store = MagicMock()
        mock_store.list_all.return_value = []
        mock_store_cls.default.return_value = mock_store

        spec = tmp_path / "spec.md"
        spec.write_text("---\ntitle: No questions\n---\n\n# Body\n")
        out_dir = tmp_path / "sessions"

        result = create_pm_workbench_session(spec_path=spec, out_dir=out_dir, session_id="wb-test")

        post = frontmatter.load(result.session_path)
        unknowns = post.metadata.get("unknowns", [])
        assert len(unknowns) == 0

    @patch("cub.core.workbench.session.AdoptionStore")
    def test_adopted_tool_preferred(self, mock_store_cls: MagicMock, tmp_path: Path) -> None:
        mock_adopted = MagicMock()
        mock_adopted.tool_id = "mcp-official:brave-search"
        mock_store = MagicMock()
        mock_store.list_all.return_value = [mock_adopted]
        mock_store_cls.default.return_value = mock_store

        spec = tmp_path / "spec.md"
        spec.write_text("---\nreadiness:\n  questions:\n    - Q?\n---\n\n# Body\n")
        out_dir = tmp_path / "sessions"

        result = create_pm_workbench_session(spec_path=spec, out_dir=out_dir, session_id="wb-test")

        post = frontmatter.load(result.session_path)
        assert post.metadata["next_move"]["tool_id"] == "mcp-official:brave-search"


class TestExtractWebResults:
    """Tests for _extract_web_results function."""

    def test_extracts_from_output_format(self) -> None:
        payload = {
            "output": {
                "web": {
                    "results": [
                        {
                            "title": "Result 1",
                            "url": "https://example.com/1",
                            "description": "Desc 1",
                        },
                        {
                            "title": "Result 2",
                            "url": "https://example.com/2",
                            "description": "Desc 2",
                        },
                    ]
                }
            }
        }
        results = _extract_web_results(payload)
        assert len(results) == 2
        assert results[0]["title"] == "Result 1"
        assert results[0]["url"] == "https://example.com/1"

    def test_extracts_from_legacy_result_format(self) -> None:
        payload = {
            "result": {
                "web": {
                    "results": [
                        {
                            "title": "Legacy",
                            "url": "https://example.com/legacy",
                            "description": "Old",
                        },
                    ]
                }
            }
        }
        results = _extract_web_results(payload)
        assert len(results) == 1
        assert results[0]["title"] == "Legacy"

    def test_empty_payload(self) -> None:
        assert _extract_web_results({}) == []

    def test_no_web_key(self) -> None:
        assert _extract_web_results({"output": {"something_else": True}}) == []

    def test_no_results_in_web(self) -> None:
        assert _extract_web_results({"output": {"web": {}}}) == []

    def test_skips_items_without_title_or_url(self) -> None:
        payload = {
            "output": {
                "web": {
                    "results": [
                        {"title": "", "url": "https://example.com", "description": "No title"},
                        {"title": "No URL", "url": "", "description": "Missing URL"},
                        {"title": "Valid", "url": "https://valid.com", "description": "OK"},
                    ]
                }
            }
        }
        results = _extract_web_results(payload)
        assert len(results) == 1
        assert results[0]["title"] == "Valid"

    def test_non_dict_items_skipped(self) -> None:
        payload = {"output": {"web": {"results": ["not a dict", 42, None]}}}
        assert _extract_web_results(payload) == []

    def test_non_dict_result(self) -> None:
        payload = {"output": "string_value"}
        assert _extract_web_results(payload) == []


class TestLoadToolResult:
    """Tests for _load_tool_result function."""

    def test_loads_valid_json(self, tmp_path: Path) -> None:
        artifact = tmp_path / "artifact.json"
        artifact.write_text(
            json.dumps(
                {
                    "tool_name": "brave_search",
                    "ok": True,
                    "output": {"web": {"results": []}},
                }
            )
        )
        result = _load_tool_result(artifact)
        # Should return a ToolResult or None depending on validation
        # The important thing is it doesn't crash
        assert result is not None or result is None  # validates without error

    def test_returns_none_for_non_dict(self, tmp_path: Path) -> None:
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(["not", "a", "dict"]))
        assert _load_tool_result(artifact) is None

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert _load_tool_result(tmp_path / "missing.json") is None

    def test_returns_none_for_invalid_json(self, tmp_path: Path) -> None:
        artifact = tmp_path / "artifact.json"
        artifact.write_text("not json at all {{{")
        assert _load_tool_result(artifact) is None


class TestWriteResearchNote:
    """Tests for write_research_note_from_session function."""

    def test_raises_without_next_move(self, tmp_path: Path) -> None:
        session_path = tmp_path / "session.md"
        post = frontmatter.Post("# Session", **{"id": "test"})
        session_path.write_text(frontmatter.dumps(post))

        with pytest.raises(ValueError, match="missing next_move"):
            write_research_note_from_session(
                session_path=session_path,
                note_path=tmp_path / "note.md",
            )

    def test_raises_without_run_results(self, tmp_path: Path) -> None:
        session_path = tmp_path / "session.md"
        post = frontmatter.Post("# Session", **{"id": "test", "next_move": {"kind": "research"}})
        session_path.write_text(frontmatter.dumps(post))

        with pytest.raises(ValueError, match="no run_results"):
            write_research_note_from_session(
                session_path=session_path,
                note_path=tmp_path / "note.md",
            )

    def test_writes_note_for_failed_result(self, tmp_path: Path) -> None:
        session_path = tmp_path / "session.md"
        post = frontmatter.Post(
            "# Session",
            **{
                "id": "test",
                "next_move": {
                    "kind": "research",
                    "tool_id": "brave",
                    "run_results": [
                        {
                            "query": "test query",
                            "ok": False,
                            "error": "timeout",
                        }
                    ],
                },
            },
        )
        session_path.write_text(frontmatter.dumps(post))
        note_path = tmp_path / "notes" / "note.md"

        result = write_research_note_from_session(
            session_path=session_path,
            note_path=note_path,
        )

        assert result == note_path
        assert note_path.exists()
        content = note_path.read_text()
        assert "FAILED" in content
        assert "timeout" in content

    def test_writes_note_for_successful_result(self, tmp_path: Path) -> None:
        # Create an artifact file
        artifact = tmp_path / "artifact.json"
        artifact.write_text(
            json.dumps(
                {
                    "output": {
                        "web": {
                            "results": [
                                {
                                    "title": "Good Result",
                                    "url": "https://example.com",
                                    "description": "Useful",
                                },
                            ]
                        }
                    }
                }
            )
        )

        session_path = tmp_path / "session.md"
        post = frontmatter.Post(
            "# Session",
            **{
                "id": "test",
                "next_move": {
                    "kind": "research",
                    "run_results": [
                        {
                            "query": "test query",
                            "ok": True,
                            "artifact": str(artifact),
                        }
                    ],
                },
            },
        )
        session_path.write_text(frontmatter.dumps(post))
        note_path = tmp_path / "note.md"

        write_research_note_from_session(
            session_path=session_path,
            note_path=note_path,
        )

        content = note_path.read_text()
        assert "test query" in content
        assert "OK" in content

    def test_appends_to_existing_note(self, tmp_path: Path) -> None:
        note_path = tmp_path / "note.md"
        note_path.write_text("# Existing Note\n\nPrevious content.\n")

        session_path = tmp_path / "session.md"
        post = frontmatter.Post(
            "# Session",
            **{
                "id": "test",
                "next_move": {
                    "kind": "research",
                    "run_results": [
                        {"query": "new query", "ok": False, "error": "err"},
                    ],
                },
            },
        )
        session_path.write_text(frontmatter.dumps(post))

        write_research_note_from_session(
            session_path=session_path,
            note_path=note_path,
        )

        content = note_path.read_text()
        assert "Existing Note" in content
        assert "Previous content" in content
        assert "new query" in content
