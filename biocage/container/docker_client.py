"""
Low-level Docker client wrapper for BioCage.

This module provides a clean interface for Docker operations with proper error
handling and logging. It abstracts subprocess calls and Docker command construction,
providing a consistent API for all Docker interactions.

The DockerClient class handles:
- Docker command execution with proper error handling
- Command construction and validation
- Output parsing and result processing
- Docker availability checking

Example:
    >>> client = DockerClient()
    >>> if client.is_docker_available():
    ...     result = client.run_command(["docker", "images"])
    ...     print("Docker is working!")
"""

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class DockerCommandError(Exception):
    """
    Exception raised when Docker command execution fails.

    This exception provides detailed information about Docker command
    failures including the command that failed, exit code, and error output.

    Attributes:
        command: The Docker command that failed
        exit_code: The exit code returned by the command
        stderr: Standard error output from the command
        stdout: Standard output from the command
    """

    def __init__(
        self,
        message: str,
        command: list[str],
        exit_code: int,
        stderr: str = "",
        stdout: str = "",
    ) -> None:
        """
        Initialize a Docker command error.

        Args:
            message: Human-readable error message
            command: The command that failed
            exit_code: Exit code from the failed command
            stderr: Standard error output
            stdout: Standard output
        """
        super().__init__(message)
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        self.stdout = stdout


class DockerClient:
    """
    Low-level Docker client for executing Docker commands.

    This class provides a clean, consistent interface for interacting with
    Docker through subprocess calls. It handles command construction,
    execution, error handling, and result parsing.

    The client automatically handles common Docker patterns and provides
    detailed error information when commands fail.

    Example:
        >>> client = DockerClient()
        >>> result = client.run_command(["docker", "--version"])
        >>> print(f"Docker version: {result.stdout}")

        >>> # Check if an image exists
        >>> images = client.list_images("biocage:latest")
        >>> if images:
        ...     print("Image exists")
    """

    def __init__(self) -> None:
        """Initialize the Docker client."""
        self._docker_available: Optional[bool] = None

    def is_docker_available(self) -> bool:
        """
        Check if Docker is available and running.

        This method caches the result to avoid repeated expensive checks.
        Docker availability is determined by running 'docker info' command.

        Returns:
            True if Docker is available and responding, False otherwise

        Example:
            >>> client = DockerClient()
            >>> if client.is_docker_available():
            ...     print("Docker is ready")
            ... else:
            ...     print("Docker is not available")
        """
        if self._docker_available is None:
            try:
                result = self.run_command(["docker", "info"], timeout=10)
                self._docker_available = result.returncode == 0
                logger.debug("Docker availability check: %s", self._docker_available)
            except (subprocess.TimeoutExpired, FileNotFoundError, DockerCommandError):
                self._docker_available = False
                logger.warning("Docker is not available")

        return self._docker_available

    def run_command(
        self,
        command: list[str],
        input_data: Optional[str] = None,
        timeout: Optional[int] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """
        Execute a Docker command with proper error handling.

        Args:
            command: List of command components (e.g., ["docker", "run", "image"])
            input_data: Optional stdin input for the command
            timeout: Optional timeout in seconds
            check: Whether to raise exception on non-zero exit codes

        Returns:
            CompletedProcess instance with stdout, stderr, and returncode

        Raises:
            DockerCommandError: If command fails and check=True
            subprocess.TimeoutExpired: If command times out

        Example:
            >>> client = DockerClient()
            >>> result = client.run_command(["docker", "images", "-q"])
            >>> image_ids = result.stdout.strip().split('\\n')
        """
        logger.debug("Executing Docker command: %s", " ".join(command))

        try:
            result = subprocess.run(
                command,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,  # We handle checking manually
            )

            logger.debug(
                "Command completed: exit_code=%d, stdout_len=%d, stderr_len=%d",
                result.returncode,
                len(result.stdout),
                len(result.stderr),
            )

            if check and result.returncode != 0:
                error_msg = f"Docker command failed: {' '.join(command)}"
                raise DockerCommandError(
                    message=error_msg,
                    command=command,
                    exit_code=result.returncode,
                    stderr=result.stderr,
                    stdout=result.stdout,
                )

            return result

        except subprocess.TimeoutExpired as e:
            logger.exception("Docker command timed out: %s", " ".join(command))
            # Create a DockerCommandError with timeout exit code and partial output
            # Convert bytes to string if needed
            stdout = e.stdout.decode('utf-8') if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = e.stderr.decode('utf-8') if isinstance(e.stderr, bytes) else (e.stderr or "")

            raise DockerCommandError(
                message=f"Docker command timed out: {' '.join(command)}",
                command=command,
                exit_code=124,  # Standard timeout exit code
                stderr=stderr,
                stdout=stdout,
            ) from e

    def build_run_command(
        self,
        image: str,
        command: Optional[list[str]] = None,
        detached: bool = False,
        name: Optional[str] = None,
        volumes: Optional[list[str]] = None,
        environment: Optional[dict[str, str]] = None,
        network: Optional[str] = None,
        memory_limit: Optional[str] = None,
        cpu_limit: Optional[str] = None,
        security_opts: Optional[list[str]] = None,
        tmpfs: Optional[list[str]] = None,
        read_only: bool = False,
        init: bool = False,
        remove: bool = False,
    ) -> list[str]:
        """
        Build a docker run command with specified options.

        This method constructs a complete 'docker run' command with all
        the specified options, handling proper formatting and validation.

        Args:
            image: Docker image name to run
            command: Command to run inside container
            detached: Run container in detached mode
            name: Container name
            volumes: List of volume mounts (format: "host:container:mode")
            environment: Environment variables
            network: Network mode
            memory_limit: Memory limit (e.g., "512m", "1g")
            cpu_limit: CPU limit (e.g., "1.0", "2.5")
            security_opts: Security options
            tmpfs: Temporary filesystem mounts
            read_only: Mount root filesystem as read-only
            init: Use init process
            remove: Remove container when it exits

        Returns:
            Complete docker run command as list of strings

        Example:
            >>> client = DockerClient()
            >>> cmd = client.build_run_command(
            ...     image="python:3.11",
            ...     command=["python", "-c", "print('hello')"],
            ...     memory_limit="512m",
            ...     remove=True
            ... )
            >>> print(" ".join(cmd))
            docker run --rm --memory=512m python:3.11 python -c print('hello')
        """
        docker_cmd = ["docker", "run"]

        # Add flags
        if detached:
            docker_cmd.append("-d")
        if remove:
            docker_cmd.append("--rm")
        if init:
            docker_cmd.append("--init")
        if read_only:
            docker_cmd.append("--read-only")

        # Add named options
        if name:
            docker_cmd.extend(["--name", name])
        if memory_limit:
            docker_cmd.append(f"--memory={memory_limit}")
        if cpu_limit:
            docker_cmd.append(f"--cpus={cpu_limit}")
        if network:
            docker_cmd.append(f"--network={network}")

        # Add volume mounts
        if volumes:
            for volume in volumes:
                docker_cmd.extend(["-v", volume])

        # Add environment variables
        if environment:
            for key, value in environment.items():
                docker_cmd.extend(["-e", f"{key}={value}"])

        # Add security options
        if security_opts:
            for opt in security_opts:
                docker_cmd.extend(["--security-opt", opt])

        # Add tmpfs mounts
        if tmpfs:
            for mount in tmpfs:
                docker_cmd.extend(["--tmpfs", mount])

        # Add image
        docker_cmd.append(image)

        # Add command
        if command:
            docker_cmd.extend(command)

        return docker_cmd

    def list_images(self, name_filter: Optional[str] = None) -> list[str]:
        """
        List Docker images, optionally filtered by name.

        Args:
            name_filter: Optional image name pattern to filter by

        Returns:
            List of image IDs

        Example:
            >>> client = DockerClient()
            >>> images = client.list_images("biocage")
            >>> print(f"Found {len(images)} BioCage images")
        """
        command = ["docker", "images", "-q"]
        if name_filter:
            command.append(name_filter)

        try:
            result = self.run_command(command)
            image_ids = [line.strip() for line in result.stdout.split("\n") if line.strip()]
            return image_ids
        except DockerCommandError:
            logger.warning("Failed to list Docker images")
            return []

    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """
        Remove a Docker container.

        Args:
            container_id: Container ID or name to remove
            force: Force removal of running container

        Returns:
            True if container was removed successfully, False otherwise

        Example:
            >>> client = DockerClient()
            >>> success = client.remove_container("my_container")
            >>> print(f"Container removed: {success}")
        """
        command = ["docker", "rm"]
        if force:
            command.append("-f")
        command.append(container_id)

        try:
            self.run_command(command)
            logger.info("Removed container: %s", container_id)
            return True
        except DockerCommandError as e:
            logger.warning("Failed to remove container %s: %s", container_id, e)
            return False

    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """
        Stop a running Docker container.

        Args:
            container_id: Container ID or name to stop
            timeout: Seconds to wait before killing the container

        Returns:
            True if container was stopped successfully, False otherwise

        Example:
            >>> client = DockerClient()
            >>> success = client.stop_container("my_container")
            >>> print(f"Container stopped: {success}")
        """
        command = ["docker", "stop", "-t", str(timeout), container_id]

        try:
            self.run_command(command)
            logger.info("Stopped container: %s", container_id)
            return True
        except DockerCommandError as e:
            logger.warning("Failed to stop container %s: %s", container_id, e)
            return False
