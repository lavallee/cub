"""
Tests for harness backend protocol and registry.

Tests the backend registry, auto-detection, and backend management functions.
"""

import pytest

from cub.core.harness import backend as harness_backend
from cub.core.harness.backend import (
    detect_harness,
    get_backend,
    get_capabilities,
    is_backend_available,
    list_available_backends,
    list_backends,
    register_backend,
)
from cub.core.harness.models import HarnessCapabilities, HarnessResult


class TestBackendRegistry:
    """Test backend registration and retrieval."""

    def test_register_backend(self):
        """Test registering a backend."""

        @register_backend("test-harness")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-harness"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities(
                    supports_streaming=True,
                    reports_token_usage=True,
                )

            def is_available(self) -> bool:
                return True

            def invoke(
                self, system_prompt: str, task_prompt: str, model=None, debug=False
            ) -> HarnessResult:
                return HarnessResult(output="test output")

            def invoke_streaming(
                self,
                system_prompt: str,
                task_prompt: str,
                model=None,
                debug=False,
                callback=None,
            ) -> HarnessResult:
                return HarnessResult(output="test output")

            def get_version(self) -> str:
                return "1.0.0"

        # Verify backend is registered
        assert "test-harness" in list_backends()

        # Clean up
        harness_backend._backends.pop("test-harness", None)

    def test_get_backend_by_name(self):
        """Test getting a backend by name."""

        @register_backend("test-get")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-get"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="test")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="test")

            def get_version(self) -> str:
                return "1.0.0"

        backend = get_backend("test-get")
        assert backend.name == "test-get"

        # Clean up
        harness_backend._backends.pop("test-get", None)

    def test_get_backend_invalid_name(self):
        """Test getting an invalid backend raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            get_backend("nonexistent-backend")

    def test_list_backends(self):
        """Test listing all registered backends."""
        # Clear any existing test backends
        test_backends = [k for k in list_backends() if k.startswith("test-")]
        for name in test_backends:
            harness_backend._backends.pop(name, None)

        @register_backend("test-list-1")
        class TestBackend1:
            @property
            def name(self) -> str:
                return "test-list-1"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        @register_backend("test-list-2")
        class TestBackend2:
            @property
            def name(self) -> str:
                return "test-list-2"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return False

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        backends = list_backends()
        assert "test-list-1" in backends
        assert "test-list-2" in backends

        # Clean up
        harness_backend._backends.pop("test-list-1", None)
        harness_backend._backends.pop("test-list-2", None)


class TestBackendAvailability:
    """Test backend availability detection."""

    def test_is_backend_available_true(self):
        """Test is_backend_available returns True for available backend."""

        @register_backend("test-available")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-available"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        assert is_backend_available("test-available") is True

        # Clean up
        harness_backend._backends.pop("test-available", None)

    def test_is_backend_available_false(self):
        """Test is_backend_available returns False for unavailable backend."""

        @register_backend("test-unavailable")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-unavailable"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return False

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        assert is_backend_available("test-unavailable") is False

        # Clean up
        harness_backend._backends.pop("test-unavailable", None)

    def test_is_backend_available_nonexistent(self):
        """Test is_backend_available returns False for nonexistent backend."""
        assert is_backend_available("does-not-exist") is False

    def test_is_backend_available_error_handling(self):
        """Test is_backend_available handles instantiation errors."""

        @register_backend("test-error")
        class TestBackend:
            def __init__(self):
                raise RuntimeError("Initialization failed")

            @property
            def name(self) -> str:
                return "test-error"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        # Should return False instead of raising
        assert is_backend_available("test-error") is False

        # Clean up
        harness_backend._backends.pop("test-error", None)

    def test_list_available_backends(self):
        """Test listing available backends."""

        @register_backend("test-avail-1")
        class TestBackend1:
            @property
            def name(self) -> str:
                return "test-avail-1"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        @register_backend("test-avail-2")
        class TestBackend2:
            @property
            def name(self) -> str:
                return "test-avail-2"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return False

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        available = list_available_backends()
        assert "test-avail-1" in available
        assert "test-avail-2" not in available

        # Clean up
        harness_backend._backends.pop("test-avail-1", None)
        harness_backend._backends.pop("test-avail-2", None)

    def test_list_available_backends_handles_errors(self):
        """Test list_available_backends handles errors gracefully."""

        @register_backend("test-error-list")
        class TestBackend:
            def __init__(self):
                raise RuntimeError("Failed to initialize")

            @property
            def name(self) -> str:
                return "test-error-list"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        # Should not include error backend
        available = list_available_backends()
        assert "test-error-list" not in available

        # Clean up
        harness_backend._backends.pop("test-error-list", None)


class TestGetCapabilities:
    """Test get_capabilities function."""

    def test_get_capabilities_success(self):
        """Test getting capabilities for a backend."""

        @register_backend("test-caps")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-caps"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities(
                    streaming=True,
                    token_reporting=True,
                )

            def is_available(self) -> bool:
                return True

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        caps = get_capabilities("test-caps")
        assert caps is not None
        assert caps.streaming is True
        assert caps.token_reporting is True

        # Clean up
        harness_backend._backends.pop("test-caps", None)

    def test_get_capabilities_nonexistent(self):
        """Test getting capabilities for nonexistent backend."""
        caps = get_capabilities("does-not-exist")
        assert caps is None

    def test_get_capabilities_error_handling(self):
        """Test get_capabilities handles errors."""

        @register_backend("test-caps-error")
        class TestBackend:
            def __init__(self):
                raise RuntimeError("Failed")

            @property
            def name(self) -> str:
                return "test-caps-error"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        # Should return None instead of raising
        caps = get_capabilities("test-caps-error")
        assert caps is None

        # Clean up
        harness_backend._backends.pop("test-caps-error", None)


class TestDetectHarness:
    """Test harness auto-detection."""

    def test_detect_harness_env_variable(self, monkeypatch):
        """Test detection from HARNESS environment variable."""
        # Mock shutil.which to pretend claude is available
        import shutil

        original_which = shutil.which
        monkeypatch.setattr(
            shutil, "which", lambda cmd: "/usr/bin/" + cmd if cmd == "myharness" else None
        )
        monkeypatch.setenv("HARNESS", "myharness")

        result = detect_harness()
        assert result == "myharness"

        # Restore
        monkeypatch.setattr(shutil, "which", original_which)

    def test_detect_harness_priority_list(self, monkeypatch):
        """Test detection with priority list."""
        import shutil

        def mock_which(cmd):
            if cmd in ("codex", "claude"):
                return f"/usr/bin/{cmd}"
            return None

        monkeypatch.setattr(shutil, "which", mock_which)

        # Should pick first available from priority list
        result = detect_harness(priority_list=["codex", "claude"])
        assert result == "codex"

    def test_detect_harness_default_order(self, monkeypatch):
        """Test detection with default order."""
        import shutil

        def mock_which(cmd):
            if cmd == "codex":
                return "/usr/bin/codex"
            return None

        monkeypatch.setattr(shutil, "which", mock_which)

        # Should find codex in default order
        result = detect_harness()
        assert result == "codex"

    def test_detect_harness_none_available(self, monkeypatch):
        """Test detection when no harness is available."""
        import shutil

        monkeypatch.setattr(shutil, "which", lambda cmd: None)

        result = detect_harness()
        assert result is None

    def test_detect_harness_env_auto(self, monkeypatch):
        """Test detection with HARNESS=auto."""
        import shutil

        def mock_which(cmd):
            if cmd == "claude":
                return "/usr/bin/claude"
            return None

        monkeypatch.setattr(shutil, "which", mock_which)
        monkeypatch.setenv("HARNESS", "auto")

        # Should ignore 'auto' and use default detection
        result = detect_harness()
        assert result == "claude"


class TestGetBackendAutoDetect:
    """Test get_backend with auto-detection."""

    def test_get_backend_auto_detects(self, monkeypatch):
        """Test get_backend auto-detects when name is None."""
        import shutil

        @register_backend("claude")  # Use a backend name in the default list
        class TestBackend:
            @property
            def name(self) -> str:
                return "claude"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        # Mock shutil.which to return claude
        monkeypatch.setattr(
            shutil, "which", lambda cmd: "/usr/bin/claude" if cmd == "claude" else None
        )

        backend = get_backend(None)
        assert backend.name == "claude"

        # Clean up (but don't remove claude if it was already registered)
        # harness_backend._backends.pop("claude", None)

    def test_get_backend_auto_detects_with_auto_string(self, monkeypatch):
        """Test get_backend auto-detects when name is 'auto'."""
        import shutil

        @register_backend("codex")  # Use codex which is in the default list
        class TestBackend:
            @property
            def name(self) -> str:
                return "codex"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def invoke(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def invoke_streaming(self, *args, **kwargs) -> HarnessResult:
                return HarnessResult(output="")

            def get_version(self) -> str:
                return "1.0.0"

        # Mock detection to find codex
        monkeypatch.setattr(
            shutil, "which", lambda cmd: "/usr/bin/codex" if cmd == "codex" else None
        )

        backend = get_backend("auto")
        assert backend.name == "codex"

        # Clean up (but don't remove if already registered)
        # harness_backend._backends.pop("codex", None)

    def test_get_backend_no_harness_available(self, monkeypatch):
        """Test get_backend raises when no harness is available."""
        import shutil

        monkeypatch.setattr(shutil, "which", lambda cmd: None)

        with pytest.raises(ValueError, match="No harness available"):
            get_backend(None)
