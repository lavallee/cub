"""Tests for Docker sandbox provider."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.sandbox import (
    SandboxCapabilities,
    SandboxConfig,
    SandboxState,
    get_provider,
    is_provider_available,
    list_providers,
)
from cub.core.sandbox.docker import DockerProvider


class TestDockerProviderProperties:
    """Test DockerProvider basic properties."""

    def test_name(self) -> None:
        """Test provider name."""
        provider = DockerProvider()
        assert provider.name == "docker"

    def test_capabilities(self) -> None:
        """Test provider capabilities."""
        provider = DockerProvider()
        caps = provider.capabilities
        assert isinstance(caps, SandboxCapabilities)
        assert caps.network_isolation is True
        assert caps.resource_limits is True
        assert caps.snapshots is False
        assert caps.remote is False
        assert caps.gpu is False
        assert caps.streaming_logs is True
        assert caps.file_sync is True


class TestDockerProviderRegistration:
    """Test provider registration."""

    def test_docker_registered(self) -> None:
        """Test that docker provider is registered."""
        assert "docker" in list_providers()

    @patch("cub.core.sandbox.docker.shutil.which")
    @patch("cub.core.sandbox.docker.subprocess.run")
    def test_get_provider_docker(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
    ) -> None:
        """Test getting docker provider."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = MagicMock(returncode=0)

        provider = get_provider("docker")
        assert provider.name == "docker"


class TestDockerProviderAvailability:
    """Test Docker availability detection."""

    @patch("cub.core.sandbox.docker.shutil.which")
    def test_is_available_no_docker(self, mock_which: MagicMock) -> None:
        """Test is_available when docker not installed."""
        mock_which.return_value = None
        provider = DockerProvider()
        assert provider.is_available() is False

    @patch("cub.core.sandbox.docker.shutil.which")
    @patch("cub.core.sandbox.docker.subprocess.run")
    def test_is_available_daemon_not_running(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
    ) -> None:
        """Test is_available when daemon not running."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = MagicMock(returncode=1)

        provider = DockerProvider()
        assert provider.is_available() is False

    @patch("cub.core.sandbox.docker.shutil.which")
    @patch("cub.core.sandbox.docker.subprocess.run")
    def test_is_available_daemon_running(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
    ) -> None:
        """Test is_available when docker is working."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = MagicMock(returncode=0)

        provider = DockerProvider()
        assert provider.is_available() is True

    @patch("cub.core.sandbox.docker.shutil.which")
    @patch("cub.core.sandbox.docker.subprocess.run")
    def test_is_available_timeout(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
    ) -> None:
        """Test is_available when docker info times out."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.side_effect = subprocess.TimeoutExpired("docker", 10)

        provider = DockerProvider()
        assert provider.is_available() is False


class TestDockerProviderStart:
    """Test sandbox start functionality."""

    @patch.object(DockerProvider, "_run_docker")
    def test_start_creates_volume_and_container(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that start creates volume and launches container."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        provider = DockerProvider()
        config = SandboxConfig()

        sandbox_id = provider.start(tmp_path, config)

        assert sandbox_id.startswith("cub-sandbox-")

        # Verify volume creation
        calls = mock_run.call_args_list
        assert any("volume" in str(call) and "create" in str(call) for call in calls)

        # Verify container run
        assert any("run" in str(call) and "--detach" in str(call) for call in calls)

    @patch.object(DockerProvider, "_run_docker")
    def test_start_with_custom_config(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test start with custom configuration."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        provider = DockerProvider()
        config = SandboxConfig(
            memory="8g",
            cpus=4.0,
            network=False,
            env={"FOO": "bar"},
            cub_args=["--once", "--epic", "test"],
        )

        sandbox_id = provider.start(tmp_path, config)
        assert sandbox_id.startswith("cub-sandbox-")

        # Check container run command includes config
        run_calls = [c for c in mock_run.call_args_list if "run" in str(c)]
        last_run = str(run_calls[-1])
        assert "--memory" in last_run
        assert "8g" in last_run
        assert "--network" in last_run
        assert "none" in last_run
        assert "FOO=bar" in last_run

    @patch.object(DockerProvider, "_run_docker")
    @patch.object(DockerProvider, "_cleanup_resources")
    def test_start_cleans_up_on_failure(
        self,
        mock_cleanup: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that start cleans up on failure."""
        # First call (volume create) succeeds, second fails
        mock_run.side_effect = [
            MagicMock(returncode=0),  # volume create
            subprocess.CalledProcessError(1, "docker", "", "copy failed"),  # cp
        ]

        provider = DockerProvider()
        config = SandboxConfig()

        with pytest.raises(RuntimeError, match="Failed to start sandbox"):
            provider.start(tmp_path, config)

        # Verify cleanup was called
        mock_cleanup.assert_called_once()


class TestDockerProviderStop:
    """Test sandbox stop functionality."""

    @patch.object(DockerProvider, "_container_exists")
    @patch.object(DockerProvider, "_run_docker")
    def test_stop_running_container(
        self,
        mock_run: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """Test stopping a running container."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        provider = DockerProvider()
        provider.stop("cub-sandbox-123")

        mock_run.assert_called_with(["stop", "cub-sandbox-123"])

    @patch.object(DockerProvider, "_container_exists")
    def test_stop_nonexistent_container(
        self,
        mock_exists: MagicMock,
    ) -> None:
        """Test stopping nonexistent container raises ValueError."""
        mock_exists.return_value = False

        provider = DockerProvider()
        with pytest.raises(ValueError, match="Sandbox not found"):
            provider.stop("nonexistent")


class TestDockerProviderStatus:
    """Test sandbox status functionality."""

    @patch.object(DockerProvider, "_container_exists")
    @patch.object(DockerProvider, "_run_docker")
    @patch.object(DockerProvider, "_get_resource_usage")
    def test_status_running_container(
        self,
        mock_resources: MagicMock,
        mock_run: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """Test getting status of running container."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "Status": "running",
                    "StartedAt": "2024-01-15T10:30:00.000000000Z",
                    "FinishedAt": "0001-01-01T00:00:00Z",
                }
            ),
        )
        mock_resources.return_value = None

        provider = DockerProvider()
        status = provider.status("cub-sandbox-123")

        assert status.id == "cub-sandbox-123"
        assert status.provider == "docker"
        assert status.state == SandboxState.RUNNING
        assert status.started_at is not None

    @patch.object(DockerProvider, "_container_exists")
    @patch.object(DockerProvider, "_run_docker")
    def test_status_stopped_container(
        self,
        mock_run: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """Test getting status of stopped container."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "Status": "exited",
                    "StartedAt": "2024-01-15T10:30:00.000000000Z",
                    "FinishedAt": "2024-01-15T11:30:00.000000000Z",
                    "ExitCode": 0,
                }
            ),
        )

        provider = DockerProvider()
        status = provider.status("cub-sandbox-123")

        assert status.state == SandboxState.STOPPED
        assert status.stopped_at is not None

    @patch.object(DockerProvider, "_container_exists")
    @patch.object(DockerProvider, "_run_docker")
    def test_status_oom_killed(
        self,
        mock_run: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """Test status shows OOM killed error."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "Status": "dead",
                    "OOMKilled": True,
                    "ExitCode": 137,
                }
            ),
        )

        provider = DockerProvider()
        status = provider.status("cub-sandbox-123")

        assert status.state == SandboxState.FAILED
        assert status.error == "Container killed: out of memory"

    @patch.object(DockerProvider, "_container_exists")
    def test_status_nonexistent_container(
        self,
        mock_exists: MagicMock,
    ) -> None:
        """Test status of nonexistent container raises ValueError."""
        mock_exists.return_value = False

        provider = DockerProvider()
        with pytest.raises(ValueError, match="Sandbox not found"):
            provider.status("nonexistent")


class TestDockerProviderLogs:
    """Test sandbox logs functionality."""

    @patch.object(DockerProvider, "_container_exists")
    @patch.object(DockerProvider, "_run_docker")
    def test_logs_returns_output(
        self,
        mock_run: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """Test getting logs from container."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Hello from container\n",
            stderr="",
        )

        provider = DockerProvider()
        logs = provider.logs("cub-sandbox-123")

        assert "Hello from container" in logs

    @patch.object(DockerProvider, "_container_exists")
    def test_logs_nonexistent_container(
        self,
        mock_exists: MagicMock,
    ) -> None:
        """Test logs of nonexistent container raises ValueError."""
        mock_exists.return_value = False

        provider = DockerProvider()
        with pytest.raises(ValueError, match="Sandbox not found"):
            provider.logs("nonexistent")


class TestDockerProviderDiff:
    """Test sandbox diff functionality."""

    @patch.object(DockerProvider, "_container_exists")
    @patch.object(DockerProvider, "status")
    @patch.object(DockerProvider, "_run_docker")
    def test_diff_running_container(
        self,
        mock_run: MagicMock,
        mock_status: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """Test getting diff from running container."""
        mock_exists.return_value = True
        mock_status.return_value = MagicMock(state=SandboxState.RUNNING)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n",
        )

        provider = DockerProvider()
        diff = provider.diff("cub-sandbox-123")

        assert "--- a/file.txt" in diff
        assert "+new" in diff

    @patch.object(DockerProvider, "_container_exists")
    @patch.object(DockerProvider, "status")
    @patch.object(DockerProvider, "_run_docker")
    def test_diff_stopped_container(
        self,
        mock_run: MagicMock,
        mock_status: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """Test getting diff from stopped container uses temporary container."""
        mock_exists.return_value = True
        mock_status.return_value = MagicMock(state=SandboxState.STOPPED)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="diff output\n",
        )

        provider = DockerProvider()
        diff = provider.diff("cub-sandbox-123")

        assert diff == "diff output\n"
        # Verify it used alpine/git for diff
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("alpine/git" in c for c in calls)


class TestDockerProviderExport:
    """Test sandbox export functionality."""

    @patch.object(DockerProvider, "_container_exists")
    @patch.object(DockerProvider, "_run_docker")
    def test_export_changed_files(
        self,
        mock_run: MagicMock,
        mock_exists: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test exporting changed files only."""
        mock_exists.return_value = True
        # First call: get changed files, second: copy file
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="src/main.py\nREADME.md\n"),
            MagicMock(returncode=0),  # copy src/main.py
            MagicMock(returncode=0),  # copy README.md
        ]

        provider = DockerProvider()
        dest = tmp_path / "export"
        provider.export("cub-sandbox-123", dest, changed_only=True)

        # Verify dest directory created
        assert dest.exists()

    @patch.object(DockerProvider, "_container_exists")
    @patch.object(DockerProvider, "_run_docker")
    def test_export_all_files(
        self,
        mock_run: MagicMock,
        mock_exists: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test exporting all files."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        provider = DockerProvider()
        dest = tmp_path / "export"
        provider.export("cub-sandbox-123", dest, changed_only=False)

        # Verify copy command was called
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("cp -a" in c for c in calls)

    @patch.object(DockerProvider, "_container_exists")
    def test_export_nonexistent_container(
        self,
        mock_exists: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test export of nonexistent container raises ValueError."""
        mock_exists.return_value = False

        provider = DockerProvider()
        with pytest.raises(ValueError, match="Sandbox not found"):
            provider.export("nonexistent", tmp_path / "export")


class TestDockerProviderCleanup:
    """Test sandbox cleanup functionality."""

    @patch.object(DockerProvider, "_container_exists")
    @patch.object(DockerProvider, "_volume_exists")
    @patch.object(DockerProvider, "_cleanup_resources")
    def test_cleanup_removes_resources(
        self,
        mock_cleanup: MagicMock,
        mock_vol_exists: MagicMock,
        mock_container_exists: MagicMock,
    ) -> None:
        """Test cleanup removes container and volume."""
        mock_container_exists.return_value = True
        mock_vol_exists.return_value = True

        provider = DockerProvider()
        provider.cleanup("cub-sandbox-123")

        mock_cleanup.assert_called_once_with(
            "cub-sandbox-123",
            "cub-sandbox-123_work",
            ignore_errors=False,
        )

    @patch.object(DockerProvider, "_container_exists")
    @patch.object(DockerProvider, "_volume_exists")
    def test_cleanup_nonexistent_sandbox(
        self,
        mock_vol_exists: MagicMock,
        mock_container_exists: MagicMock,
    ) -> None:
        """Test cleanup of nonexistent sandbox raises ValueError."""
        mock_container_exists.return_value = False
        mock_vol_exists.return_value = False

        provider = DockerProvider()
        with pytest.raises(ValueError, match="Sandbox not found"):
            provider.cleanup("nonexistent")


class TestDockerProviderVersion:
    """Test version retrieval."""

    @patch.object(DockerProvider, "_run_docker")
    def test_get_version(self, mock_run: MagicMock) -> None:
        """Test getting Docker version."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="24.0.7\n",
        )

        provider = DockerProvider()
        version = provider.get_version()

        assert version == "24.0.7"

    @patch.object(DockerProvider, "_run_docker")
    def test_get_version_failure(self, mock_run: MagicMock) -> None:
        """Test get_version returns unknown on failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "docker")

        provider = DockerProvider()
        version = provider.get_version()

        assert version == "unknown"


class TestDockerProviderHelpers:
    """Test private helper methods."""

    def test_parse_docker_timestamp(self) -> None:
        """Test parsing Docker timestamps."""
        provider = DockerProvider()

        # Standard format
        ts = provider._parse_docker_timestamp("2024-01-15T10:30:00.123456789Z")
        assert ts is not None
        assert ts.year == 2024
        assert ts.month == 1
        assert ts.day == 15

        # Without nanoseconds
        ts = provider._parse_docker_timestamp("2024-01-15T10:30:00Z")
        assert ts is not None

        # Empty string
        ts = provider._parse_docker_timestamp("")
        assert ts is None

    @patch.object(DockerProvider, "_run_docker")
    def test_container_exists(self, mock_run: MagicMock) -> None:
        """Test container existence check."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="cub-sandbox-123\n",
        )

        provider = DockerProvider()
        assert provider._container_exists("cub-sandbox-123") is True

    @patch.object(DockerProvider, "_run_docker")
    def test_container_not_exists(self, mock_run: MagicMock) -> None:
        """Test container non-existence check."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
        )

        provider = DockerProvider()
        assert provider._container_exists("nonexistent") is False

    @patch.object(DockerProvider, "_run_docker")
    def test_get_resource_usage(self, mock_run: MagicMock) -> None:
        """Test getting resource usage."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "MemUsage": "1.2GiB / 4GiB",
                    "CPUPerc": "45.23%",
                }
            ),
        )

        provider = DockerProvider()
        usage = provider._get_resource_usage("cub-sandbox-123")

        assert usage is not None
        assert usage.memory_used == "1.2GiB"
        assert usage.memory_limit == "4GiB"
        assert usage.cpu_percent == 45.23


class TestDockerProviderIntegration:
    """Integration tests that verify provider implements protocol correctly."""

    def test_implements_sandbox_provider_protocol(self) -> None:
        """Test that DockerProvider implements SandboxProvider protocol."""
        from cub.core.sandbox import SandboxProvider

        provider = DockerProvider()
        assert isinstance(provider, SandboxProvider)

    @patch("cub.core.sandbox.docker.shutil.which")
    @patch("cub.core.sandbox.docker.subprocess.run")
    def test_is_provider_available_integration(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
    ) -> None:
        """Test is_provider_available integration."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = MagicMock(returncode=0)

        assert is_provider_available("docker") is True
