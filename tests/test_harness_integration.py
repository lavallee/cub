"""
Integration tests for async harness backends.

Tests harness detection, feature support, and basic execution for all
registered async harnesses.
"""

import pytest

from cub.core.harness import async_backend as harness_async
from cub.core.harness.async_backend import (
    detect_async_harness,
    get_async_backend,
    get_async_capabilities,
    is_async_backend_available,
    list_async_backends,
    list_available_async_backends,
    register_async_backend,
)
from cub.core.harness.models import HarnessCapabilities, HarnessFeature, TaskInput, TaskResult


class MockAsyncBackend:
    """Mock async backend for testing."""

    @property
    def name(self) -> str:
        return "mock-async"

    @property
    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(
            streaming=True,
            token_reporting=True,
        )

    def is_available(self) -> bool:
        return True

    def supports_feature(self, feature: HarnessFeature) -> bool:
        """Check feature support."""
        if feature == HarnessFeature.STREAMING:
            return True
        elif feature == HarnessFeature.HOOKS:
            return False
        elif feature == HarnessFeature.CUSTOM_TOOLS:
            return False
        return False

    async def run_task(
        self,
        task_input: TaskInput,
        debug: bool = False,
    ) -> TaskResult:
        """Execute task (mock implementation)."""
        return TaskResult(
            output="mock output",
            exit_code=0,
        )

    async def stream_task(
        self,
        task_input: TaskInput,
        debug: bool = False,
    ):
        """Stream task output (mock implementation)."""
        yield "mock"
        yield " "
        yield "streaming"

    def get_version(self) -> str:
        return "1.0.0-mock"


class TestAsyncBackendRegistry:
    """Test async backend registration and retrieval."""

    def test_register_async_backend(self):
        """Test registering an async backend."""

        @register_async_backend("test-async-harness")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-async-harness"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities(streaming=True, token_reporting=True)

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="test", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield "test"

            def get_version(self) -> str:
                return "1.0.0"

        # Verify backend is registered
        assert "test-async-harness" in list_async_backends()

        # Clean up
        harness_async._async_backends.pop("test-async-harness", None)

    def test_get_async_backend_by_name(self):
        """Test getting an async backend by name."""

        @register_async_backend("test-get-async")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-get-async"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="test", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield "test"

            def get_version(self) -> str:
                return "1.0.0"

        backend = get_async_backend("test-get-async")
        assert backend.name == "test-get-async"

        # Clean up
        harness_async._async_backends.pop("test-get-async", None)

    def test_get_async_backend_invalid_name(self):
        """Test getting an invalid async backend raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            get_async_backend("nonexistent-async-backend")

    def test_list_async_backends(self):
        """Test listing all registered async backends."""
        # Clear any existing test backends
        test_backends = [k for k in list_async_backends() if k.startswith("test-")]
        for name in test_backends:
            harness_async._async_backends.pop(name, None)

        @register_async_backend("test-list-async-1")
        class TestBackend1:
            @property
            def name(self) -> str:
                return "test-list-async-1"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield ""

            def get_version(self) -> str:
                return "1.0.0"

        @register_async_backend("test-list-async-2")
        class TestBackend2:
            @property
            def name(self) -> str:
                return "test-list-async-2"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return False

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield ""

            def get_version(self) -> str:
                return "1.0.0"

        backends = list_async_backends()
        assert "test-list-async-1" in backends
        assert "test-list-async-2" in backends

        # Clean up
        harness_async._async_backends.pop("test-list-async-1", None)
        harness_async._async_backends.pop("test-list-async-2", None)


class TestAsyncBackendAvailability:
    """Test async backend availability detection."""

    def test_is_async_backend_available_true(self):
        """Test is_async_backend_available returns True for available backend."""

        @register_async_backend("test-avail-async")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-avail-async"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield ""

            def get_version(self) -> str:
                return "1.0.0"

        assert is_async_backend_available("test-avail-async") is True

        # Clean up
        harness_async._async_backends.pop("test-avail-async", None)

    def test_is_async_backend_available_false(self):
        """Test is_async_backend_available returns False for unavailable backend."""

        @register_async_backend("test-unavail-async")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-unavail-async"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return False

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield ""

            def get_version(self) -> str:
                return "1.0.0"

        assert is_async_backend_available("test-unavail-async") is False

        # Clean up
        harness_async._async_backends.pop("test-unavail-async", None)

    def test_is_async_backend_available_nonexistent(self):
        """Test is_async_backend_available returns False for nonexistent backend."""
        assert is_async_backend_available("does-not-exist-async") is False

    def test_list_available_async_backends(self):
        """Test listing available async backends."""

        @register_async_backend("test-avail-async-1")
        class TestBackend1:
            @property
            def name(self) -> str:
                return "test-avail-async-1"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield ""

            def get_version(self) -> str:
                return "1.0.0"

        @register_async_backend("test-avail-async-2")
        class TestBackend2:
            @property
            def name(self) -> str:
                return "test-avail-async-2"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return False

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield ""

            def get_version(self) -> str:
                return "1.0.0"

        available = list_available_async_backends()
        assert "test-avail-async-1" in available
        assert "test-avail-async-2" not in available

        # Clean up
        harness_async._async_backends.pop("test-avail-async-1", None)
        harness_async._async_backends.pop("test-avail-async-2", None)


class TestGetAsyncCapabilities:
    """Test get_async_capabilities function."""

    def test_get_async_capabilities_success(self):
        """Test getting capabilities for an async backend."""

        @register_async_backend("test-caps-async")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-caps-async"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities(streaming=True, token_reporting=True)

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield ""

            def get_version(self) -> str:
                return "1.0.0"

        caps = get_async_capabilities("test-caps-async")
        assert caps is not None
        assert caps.streaming is True
        assert caps.token_reporting is True

        # Clean up
        harness_async._async_backends.pop("test-caps-async", None)

    def test_get_async_capabilities_nonexistent(self):
        """Test getting capabilities for nonexistent async backend."""
        caps = get_async_capabilities("does-not-exist-async")
        assert caps is None


class TestDetectAsyncHarness:
    """Test async harness auto-detection."""

    def test_detect_async_harness_env_variable(self, monkeypatch):
        """Test detection from HARNESS environment variable."""
        # Register a mock backend
        harness_async._async_backends["myharness-async"] = MockAsyncBackend

        monkeypatch.setenv("HARNESS", "myharness-async")

        result = detect_async_harness()
        assert result == "myharness-async"

        # Clean up
        harness_async._async_backends.pop("myharness-async", None)

    def test_detect_async_harness_priority_list(self):
        """Test detection with priority list."""

        @register_async_backend("first-async")
        class FirstBackend:
            @property
            def name(self) -> str:
                return "first-async"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield ""

            def get_version(self) -> str:
                return "1.0.0"

        @register_async_backend("second-async")
        class SecondBackend:
            @property
            def name(self) -> str:
                return "second-async"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield ""

            def get_version(self) -> str:
                return "1.0.0"

        # Should pick first available from priority list
        result = detect_async_harness(priority_list=["first-async", "second-async"])
        assert result == "first-async"

        # Clean up
        harness_async._async_backends.pop("first-async", None)
        harness_async._async_backends.pop("second-async", None)

    def test_detect_async_harness_none_available(self, monkeypatch):
        """Test detection when no async harness is available."""
        # Save original backends
        original = harness_async._async_backends.copy()

        try:
            # Clear all backends
            harness_async._async_backends.clear()

            result = detect_async_harness()
            assert result is None
        finally:
            # Restore
            harness_async._async_backends.update(original)


class TestAsyncHarnessExecution:
    """Test async harness execution with mock backend."""

    @pytest.mark.asyncio
    async def test_run_task_basic(self):
        """Test basic run_task execution."""

        @register_async_backend("test-exec")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-exec"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return False

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(
                    output=f"Executed: {task_input.prompt}",
                    exit_code=0,
                )

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield "test"

            def get_version(self) -> str:
                return "1.0.0"

        backend = get_async_backend("test-exec")
        task_input = TaskInput(
            prompt="Test task",
            system_prompt="System instructions",
            model="test-model",
        )

        result = await backend.run_task(task_input)
        assert result.success is True
        assert "Executed: Test task" in result.output
        assert result.exit_code == 0

        # Clean up
        harness_async._async_backends.pop("test-exec", None)

    @pytest.mark.asyncio
    async def test_stream_task_basic(self):
        """Test basic stream_task execution."""

        @register_async_backend("test-stream")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-stream"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities(streaming=True)

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return feature == HarnessFeature.STREAMING

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield "chunk1"
                yield "chunk2"
                yield "chunk3"

            def get_version(self) -> str:
                return "1.0.0"

        backend = get_async_backend("test-stream")
        task_input = TaskInput(prompt="Test streaming task")

        chunks = []
        async for chunk in backend.stream_task(task_input):
            chunks.append(chunk)

        assert chunks == ["chunk1", "chunk2", "chunk3"]

        # Clean up
        harness_async._async_backends.pop("test-stream", None)


class TestFeatureDetection:
    """Test feature detection across different harnesses."""

    def test_supports_feature_streaming(self):
        """Test streaming feature detection."""

        @register_async_backend("test-feature-stream")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-feature-stream"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities(streaming=True)

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return feature == HarnessFeature.STREAMING

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield ""

            def get_version(self) -> str:
                return "1.0.0"

        backend = get_async_backend("test-feature-stream")
        assert backend.supports_feature(HarnessFeature.STREAMING) is True
        assert backend.supports_feature(HarnessFeature.HOOKS) is False
        assert backend.supports_feature(HarnessFeature.CUSTOM_TOOLS) is False

        # Clean up
        harness_async._async_backends.pop("test-feature-stream", None)

    def test_supports_feature_hooks(self):
        """Test hooks feature detection."""

        @register_async_backend("test-feature-hooks")
        class TestBackend:
            @property
            def name(self) -> str:
                return "test-feature-hooks"

            @property
            def capabilities(self) -> HarnessCapabilities:
                return HarnessCapabilities()

            def is_available(self) -> bool:
                return True

            def supports_feature(self, feature: HarnessFeature) -> bool:
                return feature == HarnessFeature.HOOKS

            async def run_task(self, task_input: TaskInput, debug: bool = False) -> TaskResult:
                return TaskResult(output="", exit_code=0)

            async def stream_task(self, task_input: TaskInput, debug: bool = False):
                yield ""

            def get_version(self) -> str:
                return "1.0.0"

        backend = get_async_backend("test-feature-hooks")
        assert backend.supports_feature(HarnessFeature.HOOKS) is True
        assert backend.supports_feature(HarnessFeature.STREAMING) is False

        # Clean up
        harness_async._async_backends.pop("test-feature-hooks", None)
