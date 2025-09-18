"""
Ephemeral execution strategy for BioCage sandbox operations.

This module implements an ephemeral execution strategy that creates fresh
containers for each execution. It provides maximum isolation and security
by ensuring no state persists between executions.

The EphemeralExecutor class provides:
- Fresh container for each execution
- Maximum isolation and security
- No state persistence between executions
- Automatic cleanup after each execution
- Optimal for untrusted code execution

Example:
    >>> executor = EphemeralExecutor("python:3.11")
    >>> result1 = executor.execute("x = 42")
    >>> result2 = executor.execute("print(x)")  # NameError: x not defined
    >>> # Each execution is completely isolated
"""

import logging
import time
from typing import Any, Optional

from ..constants import DEFAULT_CPU_LIMIT, DEFAULT_MEMORY_LIMIT
from ..container.image_manager import ImageManager
from ..container.lifecycle import ContainerLifecycle
from ..filesystem.path_manager import PathManager
from ..filesystem.temp_file_manager import TempFileManager
from ..models.execution_result import SandboxExecutionResult
from .executor import BaseExecutor, ExecutionError

logger = logging.getLogger(__name__)


class EphemeralExecutionError(ExecutionError):
    """
    Exception raised when ephemeral execution operations fail.

    This extends ExecutionError with ephemeral-specific context
    like container creation and cleanup issues.
    """

    def __init__(
        self,
        error_message: str,
        code: Optional[str] = None,
        cleanup_failed: bool = False
    ) -> None:
        """
        Initialize an ephemeral execution error.

        Args:
            error_message: Detailed error message
            code: Code that failed to execute
            cleanup_failed: Whether cleanup also failed
        """
        super().__init__("EphemeralExecutor", error_message, code)
        self.cleanup_failed = cleanup_failed


class EphemeralExecutor(BaseExecutor):
    """
    Executor that creates fresh containers for each execution.

    This executor provides maximum isolation by creating a new container
    for each code execution request. No state persists between executions,
    making it ideal for running untrusted code or when complete isolation
    is required.

    The ephemeral executor emphasizes security and isolation over performance,
    as each execution incurs the overhead of container creation and cleanup.

    Attributes:
        image_manager: Image management instance
        path_manager: Path exposure management (per-execution)
        memory_limit: Container memory limit
        cpu_limit: Container CPU limit
        network_access: Whether to allow network access
        execution_count: Number of executions performed

    Example:
        >>> # Create ephemeral executor
        >>> executor = EphemeralExecutor("python:3.11")
        >>>
        >>> # Each execution is completely isolated
        >>> result1 = executor.execute("global_var = 'hello'")
        >>> print(f"First execution: {result1.success}")
        >>>
        >>> # Previous execution state is not available
        >>> result2 = executor.execute("print(global_var)")  # This will fail
        >>> print(f"Second execution success: {result2.success}")  # False
        >>>
        >>> # For file operations, paths must be exposed for each execution
        >>> executor.expose_path("/tmp/data", "/app/data")
        >>> result3 = executor.execute("import os; print(os.listdir('/app/data'))")
    """

    def __init__(
        self,
        image_name: str,
        default_timeout: int = 30,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: str = DEFAULT_CPU_LIMIT,
        network_access: bool = False,
        remove_containers: bool = True
    ) -> None:
        """
        Initialize the ephemeral executor.

        Args:
            image_name: Docker image name for containers
            default_timeout: Default timeout for code execution
            memory_limit: Container memory limit (e.g., "512m", "1g")
            cpu_limit: Container CPU limit (e.g., "1.0", "2.0")
            network_access: Whether to allow network access in containers
            remove_containers: Whether to remove containers after execution

        Example:
            >>> executor = EphemeralExecutor(
            ...     "python:3.11",
            ...     memory_limit="512m",
            ...     cpu_limit="1.0",
            ...     network_access=False,
            ...     remove_containers=True
            ... )
        """
        super().__init__(image_name, default_timeout)

        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.network_access = network_access
        self.remove_containers = remove_containers

        # Initialize components (path manager per-execution)
        self.image_manager = ImageManager(image_name)
        self.path_manager = PathManager()  # Shared configuration
        self.temp_file_manager = TempFileManager()  # Shared for ephemeral usage
        self.execution_count = 0

        logger.info(
            "Initialized EphemeralExecutor: image=%s, memory=%s, cpu=%s, network=%s",
            image_name, memory_limit, cpu_limit, network_access
        )

    def _initialize_internal(self) -> None:
        """
        Initialize the ephemeral executor by ensuring the image exists.

        Unlike persistent executors, ephemeral executors don't start
        containers during initialization - they create them per execution.
        """
        logger.info("Initializing ephemeral executor...")

        try:
            # Ensure image exists
            self.image_manager.ensure_image_exists()
            logger.info("Ephemeral executor ready - image available")

        except Exception as e:
            raise EphemeralExecutionError(f"Failed to initialize ephemeral executor: {e}") from e

    def _execute_code_internal(
        self,
        code: str,
        timeout: Optional[int] = None,
        **kwargs
    ) -> SandboxExecutionResult:
        """
        Execute code in a fresh ephemeral container.

        This method creates a new container, executes the code, captures
        the results, and cleans up the container.

        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            **kwargs: Additional execution parameters

        Returns:
            Execution result with output and metadata

        Raises:
            EphemeralExecutionError: If execution fails
        """
        self.execution_count += 1
        container_lifecycle = None
        temp_file_manager = TempFileManager()

        self.log_execution_start(code, timeout or self.default_timeout)
        start_time = time.time()

        try:
            # Create container lifecycle for this execution
            container_lifecycle = ContainerLifecycle(self.image_name)

            # Start container with current path mappings
            container_id = container_lifecycle.start_container(
                memory_limit=self.memory_limit,
                cpu_limit=self.cpu_limit,
                network_access=self.network_access,
                volumes=self.path_manager.get_volume_mounts(),
                read_only=True,  # Ephemeral containers are read-only
            )

            logger.debug("Created ephemeral container: %s", container_id[:12])

            # Execute code via stdin to avoid file system writes and handle Unicode properly
            exec_command = ["python"]
            result = container_lifecycle.execute_command(
                exec_command,
                timeout=timeout or self.default_timeout,
                input_data=code
            )

            # Create execution result
            execution_time = time.time() - start_time
            sandbox_result = SandboxExecutionResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                execution_time=execution_time
            )

            self.log_execution_end(sandbox_result)
            return sandbox_result

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Execution failed in ephemeral container: {e}"
            logger.exception(error_msg)

            # Extract actual Python stderr and stdout from nested exceptions
            python_stderr = self._extract_python_stderr(e)
            python_stdout = self._extract_python_stdout(e)

            # Set proper exit code for timeout
            exit_code = 124 if "timed out" in str(e).lower() else getattr(e, 'exit_code', 1)

            return SandboxExecutionResult(
                stdout=python_stdout,
                stderr=python_stderr,
                exit_code=exit_code,
                execution_time=execution_time,
                error=error_msg
            )

        finally:
            # Always cleanup resources
            cleanup_success = True

            try:
                # Cleanup temporary files
                temp_file_manager.cleanup_all()

                # Stop and remove container
                if container_lifecycle and container_lifecycle.is_running:
                    container_lifecycle.stop_container()

            except Exception as cleanup_error:
                cleanup_success = False
                logger.warning("Cleanup failed for ephemeral execution: %s", cleanup_error)

            logger.debug(
                "Ephemeral execution %d completed (cleanup_success=%s)",
                self.execution_count,
                cleanup_success
            )

    def _extract_python_stderr(self, exception: Exception) -> str:
        """
        Extract actual Python stderr from nested container/docker exceptions.

        Args:
            exception: The exception caught during execution

        Returns:
            The actual Python stderr if available, otherwise the exception string
        """
        # Import here to avoid circular imports
        from ..container.docker_client import DockerCommandError
        from ..container.lifecycle import ContainerLifecycleError

        # Check if it's a ContainerLifecycleError with a DockerCommandError cause
        if isinstance(exception, ContainerLifecycleError) and exception.__cause__:
            if isinstance(exception.__cause__, DockerCommandError):
                # Return the actual Docker command stderr which contains Python errors
                return exception.__cause__.stderr or str(exception)

        # Check if it's directly a DockerCommandError
        elif isinstance(exception, DockerCommandError):
            return exception.stderr or str(exception)

        # For other exceptions, return the string representation
        return str(exception)

    def _extract_python_stdout(self, exception: Exception) -> str:
        """
        Extract actual Python stdout from nested container/docker exceptions.

        Args:
            exception: The exception caught during execution

        Returns:
            The actual Python stdout if available, otherwise empty string
        """
        # Import here to avoid circular imports
        from ..container.docker_client import DockerCommandError
        from ..container.lifecycle import ContainerLifecycleError

        # Check if it's a ContainerLifecycleError with a DockerCommandError cause
        if isinstance(exception, ContainerLifecycleError) and exception.__cause__:
            if isinstance(exception.__cause__, DockerCommandError):
                # Return the actual Docker command stdout which contains Python output
                return exception.__cause__.stdout or ""

        # Check if it's directly a DockerCommandError
        elif isinstance(exception, DockerCommandError):
            return exception.stdout or ""

        # For other exceptions, return empty string
        return ""

    def expose_path(
        self,
        host_path: str,
        container_path: Optional[str] = None,
        readonly: bool = True
    ) -> str:
        """
        Configure path exposure for future ephemeral executions.

        This method configures path mappings that will be applied to
        all subsequent ephemeral container executions.

        Args:
            host_path: Path on host filesystem
            container_path: Target path in container
            readonly: Mount as read-only (default True for security)

        Returns:
            Container path where host path will be accessible

        Example:
            >>> executor = EphemeralExecutor("python:3.11")
            >>> container_path = executor.expose_path("/tmp/data", "/app/data")
            >>> result = executor.execute("import os; print(os.listdir('/app/data'))")
        """
        return self.path_manager.expose_path(host_path, container_path, readonly)

    def expose_directory(
        self,
        host_dir: str,
        container_dir: Optional[str] = None,
        readonly: bool = True
    ) -> str:
        """
        Configure directory exposure for future ephemeral executions.

        Args:
            host_dir: Directory on host filesystem
            container_dir: Target directory in container
            readonly: Mount as read-only (default True for security)

        Returns:
            Container directory path

        Example:
            >>> executor = EphemeralExecutor("python:3.11")
            >>> work_dir = executor.expose_directory("/home/user/work", "/app/work")
        """
        return self.path_manager.expose_directory(host_dir, container_dir, readonly)

    def clear_exposed_paths(self) -> int:
        """
        Clear all configured path exposures.

        Returns:
            Number of paths that were cleared

        Example:
            >>> executor = EphemeralExecutor("python:3.11")
            >>> executor.expose_path("/tmp/data", "/app/data")
            >>> count = executor.clear_exposed_paths()
            >>> print(f"Cleared {count} exposed paths")
        """
        return self.path_manager.clear_exposed_paths()

    def get_exposed_paths(self) -> dict[str, dict[str, str]]:
        """
        Get information about currently configured path exposures.

        Returns:
            Dictionary with exposed path configurations

        Example:
            >>> executor = EphemeralExecutor("python:3.11")
            >>> executor.expose_path("/tmp/data", "/app/data")
            >>> paths = executor.get_exposed_paths()
            >>> print(f"Exposed paths: {list(paths.keys())}")
        """
        return self.path_manager.get_exposed_paths_info()

    def execute_with_files(
        self,
        code: str,
        files: dict[str, str],
        timeout: Optional[int] = None
    ) -> SandboxExecutionResult:
        """
        Execute code with temporary files created in the container.

        This convenience method creates temporary files in the container
        and makes them available during code execution.

        Args:
            code: Python code to execute
            files: Dictionary mapping file paths to content
            timeout: Execution timeout in seconds

        Returns:
            Execution result

        Example:
            >>> executor = EphemeralExecutor("python:3.11")
            >>> files = {
            ...     "/tmp/data.txt": "Hello, World!",
            ...     "/tmp/config.json": '{"setting": "value"}'
            ... }
            >>> result = executor.execute_with_files(
            ...     "print(open('/tmp/data.txt').read())",
            ...     files
            ... )
            >>> print(result.stdout.strip())  # Output: Hello, World!
        """
        # Prepare code that creates the files first
        file_creation_code = []
        for file_path, content in files.items():
            # Escape the content for safe inclusion in Python string
            escaped_content = repr(content)
            file_creation_code.append(f"with open({file_path!r}, 'w') as f: f.write({escaped_content})")

        # Combine file creation with user code
        full_code = "\n".join(file_creation_code + ["", "# User code", code])

        return self.execute(full_code, timeout=timeout)

    def _is_ready_internal(self) -> bool:
        """
        Check if the ephemeral executor is ready for execution.

        For ephemeral executors, this just checks if the image is available.

        Returns:
            True if ready for execution
        """
        return self.image_manager.image_exists()

    def _validate_environment_internal(self) -> bool:
        """
        Validate the ephemeral execution environment.

        Returns:
            True if environment is valid
        """
        # Check if image exists
        if not self.image_manager.image_exists():
            logger.warning("Docker image not available: %s", self.image_name)
            return False

        # Check Docker availability
        if not self.image_manager.docker_client.is_docker_available():
            logger.warning("Docker is not available")
            return False

        return True

    def cleanup(self) -> None:
        """
        Clean up ephemeral executor resources.

        For ephemeral executors, this mainly involves clearing path
        configurations since containers are cleaned up per-execution.

        Example:
            >>> executor = EphemeralExecutor("python:3.11")
            >>> executor.cleanup()
        """
        logger.info("Cleaning up ephemeral executor")

        try:
            # Clear path configurations
            cleared_paths = self.path_manager.clear_exposed_paths()

            # Clean up temporary files
            self.temp_file_manager.cleanup_all()

            # Reset state
            self.execution_count = 0
            self.is_initialized = False

            logger.info(
                "Ephemeral executor cleanup completed: cleared %d exposed paths",
                cleared_paths
            )

        except Exception as e:
            logger.exception("Error during ephemeral executor cleanup: %s", e)

    def get_execution_info(self) -> dict[str, Any]:
        """
        Get detailed information about the ephemeral executor.

        Returns:
            Dictionary with executor configuration and statistics
        """
        base_info = super().get_execution_info()
        base_info.update({
            "execution_strategy": "ephemeral",
            "execution_count": self.execution_count,
            "container_id": None,  # Ephemeral containers don't persist
            "container_name": None,  # Ephemeral containers don't persist
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "network_access": self.network_access,
            "remove_containers": self.remove_containers,
            "image_available": self._is_ready_internal(),
            "exposed_paths": self.path_manager.get_exposed_paths_info(),
            "temp_files_count": len(self.temp_file_manager.get_managed_paths()["files"]),
        })
        return base_info

    def get_execution_stats(self) -> dict[str, Any]:
        """
        Get execution statistics for this ephemeral executor.

        Returns:
            Dictionary with execution statistics

        Example:
            >>> executor = EphemeralExecutor("python:3.11")
            >>> executor.execute("print('hello')")
            >>> stats = executor.get_execution_stats()
            >>> print(f"Executions: {stats['execution_count']}")
        """
        return {
            "execution_count": self.execution_count,
            "image_name": self.image_name,
            "configuration": {
                "memory_limit": self.memory_limit,
                "cpu_limit": self.cpu_limit,
                "network_access": self.network_access,
                "remove_containers": self.remove_containers
            }
        }

    def reset_stats(self) -> None:
        """
        Reset execution statistics.

        Example:
            >>> executor = EphemeralExecutor("python:3.11")
            >>> executor.execute("print('test')")
            >>> executor.reset_stats()
            >>> executor.execution_count
            0
        """
        self.execution_count = 0
        logger.debug("Reset execution statistics")
