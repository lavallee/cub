"""
Docker-based sandbox provider.

This module implements the SandboxProvider protocol for Docker,
providing isolated execution environments using Docker containers.
"""

import json
import shutil
import subprocess
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .models import (
    ResourceUsage,
    SandboxCapabilities,
    SandboxConfig,
    SandboxState,
    SandboxStatus,
)
from .provider import register_provider


@register_provider("docker")
class DockerProvider:
    """
    Docker-based sandbox provider.

    Provides isolated execution using Docker containers with:
    - Full filesystem isolation via volumes
    - Network isolation option
    - Resource limits (memory, CPU)
    - Security hardening (no-new-privileges)
    - Fast startup (~2-5s)
    """

    # Default Docker image for sandbox execution
    DEFAULT_IMAGE = "cub:latest"

    # Default resource limits
    DEFAULT_MEMORY = "4g"
    DEFAULT_CPUS = 2.0

    @property
    def name(self) -> str:
        """Provider name."""
        return "docker"

    @property
    def capabilities(self) -> SandboxCapabilities:
        """Get Docker provider capabilities."""
        return SandboxCapabilities(
            network_isolation=True,
            resource_limits=True,
            snapshots=False,  # Docker can commit containers, but it's slow
            remote=False,
            gpu=False,  # Could be enabled with nvidia-docker
            streaming_logs=True,
            file_sync=True,
        )

    def is_available(self) -> bool:
        """
        Check if Docker is available and daemon is running.

        Returns:
            True if Docker CLI exists and daemon is responsive
        """
        # Check if docker command exists
        if not shutil.which("docker"):
            return False

        # Check if daemon is running
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def start(
        self,
        project_dir: Path,
        config: SandboxConfig,
    ) -> str:
        """
        Start a new Docker sandbox with the project.

        Creates a Docker volume, copies the project to it, and starts
        a container running cub.

        Args:
            project_dir: Local project directory to sandbox
            config: Sandbox configuration

        Returns:
            Sandbox ID (container name)

        Raises:
            RuntimeError: If sandbox creation fails
        """
        # Generate unique sandbox ID
        sandbox_id = f"cub-sandbox-{int(time.time())}"
        volume_name = f"{sandbox_id}_work"

        # Get configuration values with defaults
        image = str(config.provider_opts.get("image", self.DEFAULT_IMAGE))
        memory = config.memory or self.DEFAULT_MEMORY
        cpus = config.cpus or self.DEFAULT_CPUS

        try:
            # Create Docker volume
            self._run_docker(["volume", "create", volume_name])

            # Copy project to volume using alpine container
            project_path = str(project_dir.resolve())
            self._run_docker(
                [
                    "run",
                    "--rm",
                    "-v",
                    f"{project_path}:/source:ro",
                    "-v",
                    f"{volume_name}:/dest",
                    "alpine",
                    "sh",
                    "-c",
                    "cp -a /source/. /dest/",
                ]
            )

            # Build container run command
            docker_cmd = [
                "run",
                "--name",
                sandbox_id,
                "--detach",
                "-v",
                f"{volume_name}:/project",
                "-w",
                "/project",
                "--memory",
                memory,
                f"--cpus={cpus}",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "256",
            ]

            # Network isolation
            if not config.network:
                docker_cmd.extend(["--network", "none"])

            # Environment variables
            for key, value in config.env.items():
                docker_cmd.extend(["-e", f"{key}={value}"])

            # Add image
            docker_cmd.append(image)

            # Add cub run command with any cub_args
            docker_cmd.extend(["cub", "run"])
            docker_cmd.extend(config.cub_args)

            # Launch container
            self._run_docker(docker_cmd)

            return sandbox_id

        except subprocess.CalledProcessError as e:
            # Cleanup on failure
            self._cleanup_resources(sandbox_id, volume_name, ignore_errors=True)
            raise RuntimeError(f"Failed to start sandbox: {e.stderr}") from e

    def stop(self, sandbox_id: str) -> None:
        """
        Stop a running sandbox.

        Args:
            sandbox_id: Sandbox to stop

        Raises:
            ValueError: If sandbox not found
            RuntimeError: If stop operation fails
        """
        if not self._container_exists(sandbox_id):
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        try:
            self._run_docker(["stop", sandbox_id])
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to stop sandbox: {e.stderr}") from e

    def status(self, sandbox_id: str) -> SandboxStatus:
        """
        Get current sandbox status.

        Args:
            sandbox_id: Sandbox to query

        Returns:
            SandboxStatus object with current state

        Raises:
            ValueError: If sandbox not found
        """
        if not self._container_exists(sandbox_id):
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        # Get container inspect data
        try:
            result = self._run_docker(
                [
                    "inspect",
                    sandbox_id,
                    "--format",
                    "{{json .State}}",
                ]
            )
            state_data = json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to get sandbox status: {e}") from e

        # Map Docker state to SandboxState
        docker_status = state_data.get("Status", "unknown")
        state_map = {
            "created": SandboxState.STARTING,
            "running": SandboxState.RUNNING,
            "paused": SandboxState.RUNNING,
            "restarting": SandboxState.STARTING,
            "removing": SandboxState.CLEANING_UP,
            "exited": SandboxState.STOPPED,
            "dead": SandboxState.FAILED,
        }
        state = state_map.get(docker_status, SandboxState.FAILED)

        # Parse timestamps
        started_at = None
        stopped_at = None
        if state_data.get("StartedAt"):
            started_at = self._parse_docker_timestamp(state_data["StartedAt"])
        if state_data.get("FinishedAt"):
            finished = state_data["FinishedAt"]
            # Docker returns "0001-01-01T00:00:00Z" for not-yet-finished
            if not finished.startswith("0001-"):
                stopped_at = self._parse_docker_timestamp(finished)

        # Get resource usage for running containers
        resources = None
        if state == SandboxState.RUNNING:
            resources = self._get_resource_usage(sandbox_id)

        # Get exit code
        exit_code = state_data.get("ExitCode")
        if exit_code == 0 and state == SandboxState.RUNNING:
            exit_code = None

        # Get error message
        error = None
        if state_data.get("Error"):
            error = state_data["Error"]
        elif state == SandboxState.FAILED and state_data.get("OOMKilled"):
            error = "Container killed: out of memory"

        return SandboxStatus(
            id=sandbox_id,
            provider=self.name,
            state=state,
            started_at=started_at,
            stopped_at=stopped_at,
            resources=resources,
            exit_code=exit_code,
            error=error,
        )

    def logs(
        self,
        sandbox_id: str,
        follow: bool = False,
        callback: Callable[[str], None] | None = None,
    ) -> str:
        """
        Get sandbox logs.

        Args:
            sandbox_id: Sandbox to get logs from
            follow: Stream logs until sandbox stops
            callback: Optional callback for each log chunk

        Returns:
            Complete log output

        Raises:
            ValueError: If sandbox not found
        """
        if not self._container_exists(sandbox_id):
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        cmd = ["logs"]
        if follow:
            cmd.append("-f")
        cmd.append(sandbox_id)

        if follow and callback:
            # Stream logs with callback
            return self._stream_logs(cmd, callback)
        else:
            # Get all logs at once
            result = self._run_docker(cmd, check=False)
            output = result.stdout + result.stderr
            return output

    def diff(self, sandbox_id: str) -> str:
        """
        Get changes made in sandbox.

        Runs git diff inside the container to get all file changes.

        Args:
            sandbox_id: Sandbox to diff

        Returns:
            Git-style unified diff

        Raises:
            ValueError: If sandbox not found
        """
        if not self._container_exists(sandbox_id):
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        # Check if container is running
        status = self.status(sandbox_id)
        if status.state == SandboxState.RUNNING:
            # Execute git diff in running container
            try:
                result = self._run_docker(
                    [
                        "exec",
                        sandbox_id,
                        "git",
                        "diff",
                        "HEAD",
                    ],
                    check=False,
                )
                return result.stdout
            except subprocess.CalledProcessError:
                pass

        # For stopped containers, we need to start a temporary container
        # with the same volume to get the diff
        volume_name = f"{sandbox_id}_work"
        try:
            result = self._run_docker(
                [
                    "run",
                    "--rm",
                    "-v",
                    f"{volume_name}:/project",
                    "-w",
                    "/project",
                    "alpine/git",
                    "diff",
                    "HEAD",
                ],
                check=False,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return ""

    def export(
        self,
        sandbox_id: str,
        dest_path: Path,
        changed_only: bool = True,
    ) -> None:
        """
        Export files from sandbox to local path.

        Args:
            sandbox_id: Sandbox to export from
            dest_path: Local destination directory
            changed_only: Only export changed files (default: True)

        Raises:
            ValueError: If sandbox not found
            RuntimeError: If export fails
        """
        if not self._container_exists(sandbox_id):
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        dest_path = dest_path.resolve()
        dest_path.mkdir(parents=True, exist_ok=True)
        volume_name = f"{sandbox_id}_work"

        if changed_only:
            # Get list of changed files
            try:
                result = self._run_docker(
                    [
                        "run",
                        "--rm",
                        "-v",
                        f"{volume_name}:/project",
                        "-w",
                        "/project",
                        "alpine/git",
                        "diff",
                        "--name-only",
                        "HEAD",
                    ],
                    check=False,
                )
                changed_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
            except subprocess.CalledProcessError:
                changed_files = []

            if not changed_files:
                return  # No changes to export

            # Copy each changed file
            for filepath in changed_files:
                # Create destination directory
                dest_file = dest_path / filepath
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                # Copy file from volume
                try:
                    cp_cmd = f"cp '/project/{filepath}' '/dest/{filepath}' 2>/dev/null || true"
                    self._run_docker(
                        [
                            "run",
                            "--rm",
                            "-v",
                            f"{volume_name}:/project:ro",
                            "-v",
                            f"{dest_path}:/dest",
                            "alpine",
                            "sh",
                            "-c",
                            cp_cmd,
                        ]
                    )
                except subprocess.CalledProcessError:
                    pass  # File may have been deleted

        else:
            # Copy entire project
            try:
                self._run_docker(
                    [
                        "run",
                        "--rm",
                        "-v",
                        f"{volume_name}:/project:ro",
                        "-v",
                        f"{dest_path}:/dest",
                        "alpine",
                        "sh",
                        "-c",
                        "cp -a /project/. /dest/",
                    ]
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to export sandbox: {e.stderr}") from e

    def cleanup(self, sandbox_id: str) -> None:
        """
        Full cleanup of sandbox resources.

        Stops the container (if running) and removes container and volume.

        Args:
            sandbox_id: Sandbox to clean up

        Raises:
            ValueError: If sandbox not found
        """
        volume_name = f"{sandbox_id}_work"

        # Check if container or volume exists
        container_exists = self._container_exists(sandbox_id)
        volume_exists = self._volume_exists(volume_name)

        if not container_exists and not volume_exists:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        self._cleanup_resources(sandbox_id, volume_name, ignore_errors=False)

    def get_version(self) -> str:
        """
        Get Docker version.

        Returns:
            Docker version string or 'unknown'
        """
        try:
            result = self._run_docker(["version", "--format", "{{.Server.Version}}"])
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "unknown"

    # =========================================================================
    # Private helpers
    # =========================================================================

    def _run_docker(
        self,
        args: list[str],
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """
        Run a docker command.

        Args:
            args: Docker command arguments
            check: Raise on non-zero exit code

        Returns:
            CompletedProcess result
        """
        cmd = ["docker"] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                cmd,
                result.stdout,
                result.stderr,
            )
        return result

    def _stream_logs(
        self,
        cmd: list[str],
        callback: Callable[[str], None],
    ) -> str:
        """
        Stream Docker logs with callback.

        Args:
            cmd: Docker logs command
            callback: Function to call for each chunk

        Returns:
            Complete log output
        """
        full_cmd = ["docker"] + cmd
        output_chunks: list[str] = []

        process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            if process.stdout:
                for line in process.stdout:
                    output_chunks.append(line)
                    callback(line)
        finally:
            process.wait()

        return "".join(output_chunks)

    def _container_exists(self, container_name: str) -> bool:
        """Check if a container exists."""
        result = self._run_docker(
            ["ps", "-a", "--filter", f"name=^{container_name}$", "--format", "{{.Names}}"],
            check=False,
        )
        return container_name in result.stdout

    def _volume_exists(self, volume_name: str) -> bool:
        """Check if a volume exists."""
        result = self._run_docker(
            ["volume", "ls", "--filter", f"name=^{volume_name}$", "--format", "{{.Name}}"],
            check=False,
        )
        return volume_name in result.stdout

    def _get_resource_usage(self, sandbox_id: str) -> ResourceUsage | None:
        """
        Get resource usage for a running container.

        Args:
            sandbox_id: Container to query

        Returns:
            ResourceUsage object or None if unavailable
        """
        try:
            result = self._run_docker(
                [
                    "stats",
                    sandbox_id,
                    "--no-stream",
                    "--format",
                    "{{json .}}",
                ],
                check=False,
            )

            if not result.stdout.strip():
                return None

            stats = json.loads(result.stdout)

            # Parse memory (e.g., "1.2GiB / 4GiB")
            mem_usage = stats.get("MemUsage", "")
            mem_used = None
            mem_limit = None
            if " / " in mem_usage:
                parts = mem_usage.split(" / ")
                mem_used = parts[0].strip()
                mem_limit = parts[1].strip()

            # Parse CPU (e.g., "45.23%")
            cpu_str = stats.get("CPUPerc", "").rstrip("%")
            cpu_percent = None
            if cpu_str:
                try:
                    cpu_percent = float(cpu_str)
                except ValueError:
                    pass

            return ResourceUsage(
                memory_used=mem_used,
                memory_limit=mem_limit,
                cpu_percent=cpu_percent,
            )

        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None

    def _parse_docker_timestamp(self, timestamp: str) -> datetime | None:
        """
        Parse Docker timestamp to datetime.

        Docker uses RFC3339Nano format with variable precision.

        Args:
            timestamp: Docker timestamp string

        Returns:
            datetime object or None if parsing fails
        """
        if not timestamp:
            return None

        # Docker timestamps can have nanoseconds, truncate to microseconds
        # Format: 2024-01-15T10:30:00.123456789Z
        try:
            # Remove trailing Z and handle nanoseconds
            ts = timestamp.rstrip("Z")
            if "." in ts:
                date_part, frac = ts.split(".")
                # Truncate to 6 digits for microseconds
                frac = frac[:6].ljust(6, "0")
                ts = f"{date_part}.{frac}"
            return datetime.fromisoformat(ts)
        except ValueError:
            return None

    def _cleanup_resources(
        self,
        sandbox_id: str,
        volume_name: str,
        ignore_errors: bool = True,
    ) -> None:
        """
        Clean up container and volume.

        Args:
            sandbox_id: Container name
            volume_name: Volume name
            ignore_errors: Suppress errors during cleanup
        """
        # Stop and remove container
        try:
            self._run_docker(["rm", "-f", sandbox_id], check=False)
        except subprocess.CalledProcessError:
            if not ignore_errors:
                raise

        # Remove volume
        try:
            self._run_docker(["volume", "rm", volume_name], check=False)
        except subprocess.CalledProcessError:
            if not ignore_errors:
                raise
