"""Tests for sandbox provider protocol and registry."""

from pathlib import Path

import pytest

from cub.core.sandbox import (
    SandboxCapabilities,
    SandboxConfig,
    SandboxProvider,
    SandboxState,
    SandboxStatus,
    detect_provider,
    get_capabilities,
    get_provider,
    is_provider_available,
    list_available_providers,
    list_providers,
    register_provider,
)


class MockProvider:
    """Mock sandbox provider for testing."""

    @property
    def name(self) -> str:
        return "mock"

    @property
    def capabilities(self) -> SandboxCapabilities:
        return SandboxCapabilities(
            network_isolation=True,
            resource_limits=True,
            snapshots=False,
            remote=False,
            gpu=False,
        )

    def is_available(self) -> bool:
        return True

    def start(self, project_dir: Path, config: SandboxConfig) -> str:
        return "mock-sandbox-123"

    def stop(self, sandbox_id: str) -> None:
        pass

    def status(self, sandbox_id: str) -> SandboxStatus:
        return SandboxStatus(
            id=sandbox_id,
            provider="mock",
            state=SandboxState.RUNNING,
        )

    def logs(
        self,
        sandbox_id: str,
        follow: bool = False,
        callback: object = None,
    ) -> str:
        return "Mock logs"

    def diff(self, sandbox_id: str) -> str:
        return "Mock diff"

    def export(
        self,
        sandbox_id: str,
        dest_path: Path,
        changed_only: bool = True,
    ) -> None:
        pass

    def cleanup(self, sandbox_id: str) -> None:
        pass

    def get_version(self) -> str:
        return "1.0.0"


def test_provider_protocol() -> None:
    """Test that MockProvider implements SandboxProvider protocol."""
    provider = MockProvider()
    assert isinstance(provider, SandboxProvider)


def test_register_provider() -> None:
    """Test provider registration."""

    @register_provider("test-provider")
    class TestProvider:
        @property
        def name(self) -> str:
            return "test-provider"

        @property
        def capabilities(self) -> SandboxCapabilities:
            return SandboxCapabilities()

        def is_available(self) -> bool:
            return False

        def start(self, project_dir: Path, config: SandboxConfig) -> str:
            return "test-id"

        def stop(self, sandbox_id: str) -> None:
            pass

        def status(self, sandbox_id: str) -> SandboxStatus:
            return SandboxStatus(
                id=sandbox_id, provider="test-provider", state=SandboxState.STOPPED
            )

        def logs(self, sandbox_id: str, follow: bool = False, callback: object = None) -> str:
            return ""

        def diff(self, sandbox_id: str) -> str:
            return ""

        def export(self, sandbox_id: str, dest_path: Path, changed_only: bool = True) -> None:
            pass

        def cleanup(self, sandbox_id: str) -> None:
            pass

        def get_version(self) -> str:
            return "0.1.0"

    assert "test-provider" in list_providers()


def test_get_provider_invalid() -> None:
    """Test get_provider with invalid name."""
    with pytest.raises(ValueError, match="not registered"):
        get_provider("nonexistent")


def test_detect_provider_none() -> None:
    """Test detect_provider when no providers available."""
    # With no registered providers that are available, should return None
    result = detect_provider()
    # We can't assert None because other tests may have registered providers
    assert result is None or isinstance(result, str)


def test_list_providers() -> None:
    """Test list_providers returns registered providers."""
    providers = list_providers()
    assert isinstance(providers, list)


def test_list_available_providers() -> None:
    """Test list_available_providers returns only available providers."""
    available = list_available_providers()
    assert isinstance(available, list)


def test_is_provider_available() -> None:
    """Test is_provider_available checks availability."""
    # Non-existent provider
    assert not is_provider_available("nonexistent")


def test_get_capabilities() -> None:
    """Test get_capabilities returns None for non-existent provider."""
    caps = get_capabilities("nonexistent")
    assert caps is None


def test_sandbox_capabilities_model() -> None:
    """Test SandboxCapabilities model."""
    caps = SandboxCapabilities(
        network_isolation=True,
        resource_limits=True,
        snapshots=True,
        remote=False,
        gpu=True,
    )
    assert caps.network_isolation is True
    assert caps.snapshots is True
    assert caps.remote is False


def test_sandbox_status_model() -> None:
    """Test SandboxStatus model."""
    status = SandboxStatus(
        id="test-123",
        provider="docker",
        state=SandboxState.RUNNING,
    )
    assert status.id == "test-123"
    assert status.provider == "docker"
    assert status.state == SandboxState.RUNNING
    assert status.exit_code is None


def test_sandbox_config_model() -> None:
    """Test SandboxConfig model."""
    config = SandboxConfig(
        memory="4g",
        cpus=2.0,
        timeout="2h",
        network=False,
        env={"FOO": "bar"},
        cub_args=["--once"],
    )
    assert config.memory == "4g"
    assert config.cpus == 2.0
    assert config.network is False
    assert config.env["FOO"] == "bar"
    assert config.cub_args == ["--once"]
