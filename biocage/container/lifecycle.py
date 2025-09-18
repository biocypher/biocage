"""
Container lifecycle management for BioCage.

This module manages the complete lifecycle of Docker containers including creation,
starting, stopping, resource management, and monitoring. It provides a high-level
interface for container operations with proper error handling and state tracking.

The ContainerLifecycle class handles:
- Container creation with proper configuration
- Starting and stopping containers safely
- Resource management (memory, CPU, network)
- Container health monitoring and status tracking
- Cleanup and resource management

Example:
    >>> lifecycle = ContainerLifecycle("biocage:latest")
    >>> container_id = lifecycle.start_container(memory_limit="1g")
    >>> # ... use container ...
    >>> lifecycle.stop_container()
"""

import logging
import subprocess
import time
import uuid
from typing import Optional

from ..constants import (
    DEFAULT_CONTAINER_PREFIX,
    DEFAULT_CPU_LIMIT,
    DEFAULT_MEMORY_LIMIT,
    ERROR_CONTAINER_RUNNING,
    LOG_CONTAINER_STARTED,
    LOG_CONTAINER_STOPPED,
)
from ..validation import validate_cpu_limit, validate_memory_limit
from .docker_client import DockerClient, DockerCommandError

logger = logging.getLogger(__name__)


class ContainerLifecycleError(Exception):
    """
    Exception raised when container lifecycle operations fail.

    This exception provides detailed information about container operation
    failures including the container name, operation attempted, and error details.

    Attributes:
        container_name: Name of the container that failed
        operation: The operation that failed (start, stop, restart, etc.)
        error_message: Detailed error message
    """

    def __init__(self, container_name: str, operation: str, error_message: str) -> None:
        """
        Initialize a container lifecycle error.

        Args:
            container_name: Name of the container
            operation: Operation that failed
            error_message: Detailed error message
        """
        super().__init__(f"Container '{container_name}' {operation} failed: {error_message}")
        self.container_name = container_name
        self.operation = operation
        self.error_message = error_message


class ContainerLifecycle:
    """
    Manages the complete lifecycle of Docker containers.

    This class provides a high-level interface for managing Docker containers
    throughout their lifecycle from creation to cleanup. It handles resource
    configuration, state tracking, and provides detailed error handling.

    The lifecycle manager maintains container state and provides methods for
    all common container operations with proper validation and logging.

    Attributes:
        image_name: Docker image name for containers
        container_name_prefix: Prefix for generated container names
        docker_client: Docker client for executing commands
        container_id: Current container ID (if any)
        container_name: Current container name (if any)
        is_running: Whether a container is currently running

    Example:
        >>> lifecycle = ContainerLifecycle("python:3.11")
        >>> container_id = lifecycle.start_container(
        ...     memory_limit="512m",
        ...     cpu_limit="1.0"
        ... )
        >>> print(f"Started container: {container_id}")
        >>>
        >>> # Container operations...
        >>>
        >>> lifecycle.stop_container()
        >>> print("Container stopped and cleaned up")
    """

    def __init__(self, image_name: str, container_name_prefix: str = DEFAULT_CONTAINER_PREFIX) -> None:
        """
        Initialize the container lifecycle manager.

        Args:
            image_name: Docker image name to use for containers
            container_name_prefix: Prefix for generated container names

        Example:
            >>> lifecycle = ContainerLifecycle("biocage:latest", "my-sandbox")
            >>> lifecycle.image_name
            'biocage:latest'
        """
        self.image_name = image_name
        self.container_name_prefix = container_name_prefix
        self.docker_client = DockerClient()

        # Container state
        self.container_id: Optional[str] = None
        self.container_name: Optional[str] = None
        self.is_running = False

    def start_container(
        self,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: str = DEFAULT_CPU_LIMIT,
        network_access: bool = False,
        volumes: Optional[list[str]] = None,
        environment: Optional[dict[str, str]] = None,
        read_only: bool = True,
        tmpfs_mounts: Optional[list[str]] = None,
        image_name: Optional[str] = None,
    ) -> str:
        """
        Start a new container with specified configuration.

        This method creates and starts a new Docker container with the
        specified resource limits and configuration. It handles validation,
        unique naming, and proper error handling.

        Args:
            memory_limit: Memory limit (e.g., "512m", "1g")
            cpu_limit: CPU limit (e.g., "1.0", "2.0")
            network_access: Whether to allow network access
            volumes: List of volume mounts in format "host:container:mode"
            environment: Environment variables to set
            read_only: Mount root filesystem as read-only
            tmpfs_mounts: Temporary filesystem mounts

        Returns:
            Container ID of the started container

        Raises:
            ContainerLifecycleError: If container start fails
            ValueError: If parameters are invalid
            RuntimeError: If container is already running

        Example:
            >>> lifecycle = ContainerLifecycle("python:3.11")
            >>> container_id = lifecycle.start_container(
            ...     memory_limit="1g",
            ...     cpu_limit="2.0",
            ...     volumes=["./data:/app/data:ro"],
            ...     environment={"PYTHONPATH": "/app"}
            ... )
            >>> print(f"Container started: {container_id[:12]}")
        """
        if self.is_running:
            raise RuntimeError(ERROR_CONTAINER_RUNNING)

        # Validate inputs
        validate_memory_limit(memory_limit)
        validate_cpu_limit(cpu_limit)

        # Use provided image_name or fall back to instance default
        target_image = image_name or self.image_name

        # Generate unique container name
        self.container_name = f"{self.container_name_prefix}-{uuid.uuid4().hex[:8]}"

        # Default tmpfs mounts for security
        default_tmpfs = ["/app/workspace:size=100m,uid=999,gid=999", "/tmp:noexec,nosuid,nodev,size=50m"]

        if tmpfs_mounts:
            default_tmpfs.extend(tmpfs_mounts)

        # Default security options
        security_opts = ["no-new-privileges:true"]

        try:
            # Build the docker run command
            docker_cmd = self.docker_client.build_run_command(
                image=target_image,
                command=["sleep", "infinity"],  # Keep container running
                detached=True,
                name=self.container_name,
                volumes=volumes or [],
                environment=environment,
                network=None if network_access else "none",
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
                security_opts=security_opts,
                tmpfs=default_tmpfs,
                read_only=read_only,
                init=True,
                remove=False,
            )

            # Start the container
            result = self.docker_client.run_command(docker_cmd, timeout=30)
            self.container_id = result.stdout.strip()
            self.is_running = True

            # Wait a moment for container to fully start
            time.sleep(0.5)

            logger.info(LOG_CONTAINER_STARTED, self.container_name, self.container_id[:12])
            return self.container_id

        except DockerCommandError as e:
            error_msg = f"Failed to start container: {e.stderr}"
            logger.exception("Container start failed: %s", error_msg)
            raise ContainerLifecycleError(self.container_name or "unknown", "start", error_msg) from e

    def stop_container(self, timeout: int = 10) -> None:
        """
        Stop and remove the current container.

        This method gracefully stops the container with a timeout and then
        removes it to clean up resources. It handles cases where the container
        may have already stopped or been removed.

        Args:
            timeout: Seconds to wait before forcing container stop

        Raises:
            ContainerLifecycleError: If stop operation fails critically

        Example:
            >>> lifecycle = ContainerLifecycle("python:3.11")
            >>> lifecycle.start_container()
            >>> # ... use container ...
            >>> lifecycle.stop_container(timeout=5)
            >>> print("Container stopped and cleaned up")
        """
        if not self.is_running or not self.container_name:
            logger.debug("No container to stop")
            return

        try:
            # Stop the container gracefully
            stop_success = self.docker_client.stop_container(self.container_name, timeout=timeout)

            # Remove the container
            remove_success = self.docker_client.remove_container(
                self.container_name,
                force=not stop_success,  # Force if stop failed
            )

            if stop_success or remove_success:
                logger.info(LOG_CONTAINER_STOPPED, self.container_name)
            else:
                logger.warning("Container cleanup may be incomplete: %s", self.container_name)

        except DockerCommandError as e:
            logger.warning("Failed to clean up container %s: %s", self.container_name, e)
            # Don't raise exception for cleanup failures

        finally:
            # Always reset state
            self.container_id = None
            self.container_name = None
            self.is_running = False

    def restart_container(self, **kwargs) -> str:
        """
        Restart the container with optionally updated configuration.

        This method stops the current container and starts a new one with
        the same or updated configuration. It's useful for applying
        configuration changes or recovering from container issues.

        Args:
            **kwargs: Configuration parameters for start_container()

        Returns:
            Container ID of the new container

        Raises:
            ContainerLifecycleError: If restart operation fails

        Example:
            >>> lifecycle = ContainerLifecycle("python:3.11")
            >>> lifecycle.start_container(memory_limit="512m")
            >>> # Need more memory...
            >>> new_id = lifecycle.restart_container(memory_limit="1g")
            >>> print(f"Restarted with new config: {new_id[:12]}")
        """
        logger.info("Restarting container...")

        if self.is_running:
            self.stop_container()

        return self.start_container(**kwargs)

    def is_container_healthy(self) -> bool:
        """
        Check if the current container is running and healthy.

        This method verifies that the container exists, is running, and
        is responsive to basic operations.

        Returns:
            True if container is healthy, False otherwise

        Example:
            >>> lifecycle = ContainerLifecycle("python:3.11")
            >>> lifecycle.start_container()
            >>> if lifecycle.is_container_healthy():
            ...     print("Container is ready for use")
            ... else:
            ...     print("Container needs attention")
        """
        if not self.is_running or not self.container_name:
            return False

        try:
            # Check if container is still running
            command = ["docker", "ps", "-q", "-f", f"name={self.container_name}"]
            result = self.docker_client.run_command(command)

            # If we get output, container is running
            is_healthy = bool(result.stdout.strip())

            # Update our state if container stopped
            if not is_healthy:
                self.is_running = False

            return is_healthy

        except DockerCommandError:
            self.is_running = False
            return False

    def get_container_info(self) -> dict[str, str]:
        """
        Get detailed information about the current container.

        Returns:
            Dictionary containing container information

        Example:
            >>> lifecycle = ContainerLifecycle("python:3.11")
            >>> lifecycle.start_container()
            >>> info = lifecycle.get_container_info()
            >>> print(f"Container status: {info['status']}")
        """
        base_info = {
            "container_id": self.container_id or "",
            "container_name": self.container_name or "",
            "image_name": self.image_name,
            "is_running": str(self.is_running),
        }

        if not self.is_running or not self.container_name:
            base_info["status"] = "stopped"
            return base_info

        try:
            # Get container inspection data
            command = ["docker", "inspect", self.container_name]
            result = self.docker_client.run_command(command, check=False)

            if result.returncode == 0:
                base_info["status"] = "running"
                base_info["inspect_available"] = "true"
            else:
                base_info["status"] = "unknown"
                base_info["inspect_error"] = result.stderr

        except DockerCommandError as e:
            base_info["status"] = "error"
            base_info["error"] = str(e)

        return base_info

    def execute_command(
        self, command: list[str], input_data: Optional[str] = None, timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess[str]:
        """
        Execute a command inside the running container.

        Args:
            command: Command to execute as list of strings
            input_data: Optional stdin input
            timeout: Optional timeout in seconds

        Returns:
            CompletedProcess with command results

        Raises:
            ContainerLifecycleError: If container is not running
            DockerCommandError: If command execution fails

        Example:
            >>> lifecycle = ContainerLifecycle("python:3.11")
            >>> lifecycle.start_container()
            >>> result = lifecycle.execute_command(["python", "--version"])
            >>> print(f"Python version: {result.stdout}")
        """
        if not self.is_running or not self.container_name:
            raise ContainerLifecycleError(self.container_name or "unknown", "execute", "Container is not running")

        exec_cmd = ["docker", "exec", "-i", self.container_name, *command]

        try:
            return self.docker_client.run_command(exec_cmd, input_data=input_data, timeout=timeout)
        except DockerCommandError as e:
            raise ContainerLifecycleError(self.container_name, "execute", f"Command execution failed: {e}") from e
