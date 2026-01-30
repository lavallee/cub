"""Tests for cub.core.invoke module."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from cub.core.invoke import cub_command, cub_python_command, is_dev_mode


class TestIsDevMode:
    """Test is_dev_mode() detection."""

    def test_env_var_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUB_DEV_MODE", "true")
        assert is_dev_mode() is True

    def test_env_var_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUB_DEV_MODE", "1")
        assert is_dev_mode() is True

    def test_env_var_yes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUB_DEV_MODE", "yes")
        assert is_dev_mode() is True

    def test_env_var_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUB_DEV_MODE", "false")
        assert is_dev_mode() is False

    def test_env_var_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUB_DEV_MODE", "0")
        assert is_dev_mode() is False

    def test_env_var_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUB_DEV_MODE", "")
        assert is_dev_mode() is False

    def test_fallback_to_config_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CUB_DEV_MODE", raising=False)
        mock_config = MagicMock()
        mock_config.dev_mode = True
        with patch("cub.core.config.load_config", return_value=mock_config):
            assert is_dev_mode() is True

    def test_fallback_to_config_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CUB_DEV_MODE", raising=False)
        mock_config = MagicMock()
        mock_config.dev_mode = False
        with patch("cub.core.config.load_config", return_value=mock_config):
            assert is_dev_mode() is False

    def test_fallback_config_error_returns_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CUB_DEV_MODE", raising=False)
        with patch(
            "cub.core.config.load_config", side_effect=RuntimeError("no config")
        ):
            assert is_dev_mode() is False


class TestCubCommand:
    """Test cub_command() output."""

    def test_dev_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUB_DEV_MODE", "true")
        assert cub_command() == ["uv", "run", "cub"]

    def test_production_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUB_DEV_MODE", "false")
        assert cub_command() == ["cub"]


class TestCubPythonCommand:
    """Test cub_python_command() output."""

    def test_dev_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUB_DEV_MODE", "true")
        assert cub_python_command() == ["uv", "run", "python", "-m", "cub"]

    def test_production_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUB_DEV_MODE", "false")
        assert cub_python_command() == [sys.executable, "-m", "cub"]
