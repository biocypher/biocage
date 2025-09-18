"""
Persistent execution strategy for BioCage sandbox operations.

This module implements a persistent execution strategy that maintains a
long-running container and preserves state between executions. It's ideal
for interactive sessions and scenarios requiring state continuity.

The PersistentExecutor class provides:
- Long-running container management
- State persistence between executions
- Session script generation and restoration
- Efficient execution with minimal overhead
- Path exposure and file system management

Example:
    >>> executor = PersistentExecutor("python:3.11")
    >>> result1 = executor.execute("x = 42")
    >>> result2 = executor.execute("print(x)")  # x is still available
    >>> print(result2.stdout)  # Output: 42
    >>> executor.cleanup()
"""

import logging
import time
from typing import Any, Optional

from ..constants import DEFAULT_CPU_LIMIT, DEFAULT_MEMORY_LIMIT
from ..container.image_manager import ImageManager
from ..container.lifecycle import ContainerLifecycle, ContainerLifecycleError
from ..filesystem.path_manager import PathManager
from ..filesystem.temp_file_manager import TempFileManager
from ..models.execution_result import SandboxExecutionResult
from ..persistence.session_script import SessionScriptGenerator
from .executor import BaseExecutor, ExecutionError

logger = logging.getLogger(__name__)


class PersistentExecutionError(ExecutionError):
    """
    Exception raised when persistent execution operations fail.

    This extends ExecutionError with persistent-specific context
    like container state and session information.
    """

    def __init__(
        self,
        error_message: str,
        code: Optional[str] = None,
        container_id: Optional[str] = None,
        session_state: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Initialize a persistent execution error.

        Args:
            error_message: Detailed error message
            code: Code that failed to execute
            container_id: Container ID if available
            session_state: Session state information
        """
        super().__init__("PersistentExecutor", error_message, code)
        self.container_id = container_id
        self.session_state = session_state


class PersistentExecutor(BaseExecutor):
    """
    Executor that maintains a persistent container for state continuity.

    This executor creates a long-running container that persists between
    executions, allowing variables, imports, and other state to be maintained
    across multiple code execution requests. It's ideal for interactive
    sessions and scenarios requiring state preservation.

    The persistent executor manages container lifecycle, session state,
    and provides efficient execution with minimal per-execution overhead.

    Attributes:
        container_lifecycle: Container management instance
        image_manager: Image management instance
        path_manager: Path exposure management
        temp_file_manager: Temporary file management
        session_script_generator: Session state tracking
        memory_limit: Container memory limit
        cpu_limit: Container CPU limit
        container_id: Current container ID (if running)

    Example:
        >>> # Create and use persistent executor
        >>> with PersistentExecutor("python:3.11") as executor:
        ...     # First execution - create variable
        ...     result1 = executor.execute("data = [1, 2, 3, 4, 5]")
        ...
        ...     # Second execution - use variable from first execution
        ...     result2 = executor.execute("print(sum(data))")
        ...     print(f"Sum: {result2.stdout.strip()}")  # Output: Sum: 15
        ...
        ...     # Expose a directory for file operations
        ...     executor.expose_directory("/tmp/data", "/app/data")
        ...
        ...     # File operations persist in the container
        ...     result3 = executor.execute("with open('/app/data/test.txt', 'w') as f: f.write('hello')")
        ...     result4 = executor.execute("print(open('/app/data/test.txt').read())")
        ...     print(f"File content: {result4.stdout.strip()}")  # Output: File content: hello
    """

    def __init__(
        self,
        image_name: str,
        default_timeout: int = 30,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: str = DEFAULT_CPU_LIMIT,
        network_access: bool = False
    ) -> None:
        """
        Initialize the persistent executor.

        Args:
            image_name: Docker image name for the container
            default_timeout: Default timeout for code execution
            memory_limit: Container memory limit (e.g., "512m", "1g")
            cpu_limit: Container CPU limit (e.g., "1.0", "2.0")
            network_access: Whether to allow network access in container

        Example:
            >>> executor = PersistentExecutor(
            ...     "python:3.11",
            ...     memory_limit="1g",
            ...     cpu_limit="2.0",
            ...     network_access=True
            ... )
        """
        super().__init__(image_name, default_timeout)

        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.network_access = network_access

        # Initialize components
        self.container_lifecycle = ContainerLifecycle(image_name)
        self.image_manager = ImageManager(image_name)
        self.path_manager = PathManager()
        self.temp_file_manager = TempFileManager()
        self.session_script_generator = SessionScriptGenerator()

        # Container state
        self.container_id: Optional[str] = None

        logger.info(
            "Initialized PersistentExecutor: image=%s, memory=%s, cpu=%s, network=%s",
            image_name, memory_limit, cpu_limit, network_access
        )

    def _initialize_internal(self) -> None:
        """
        Initialize the persistent executor and start the container.

        This method ensures the Docker image exists and starts a persistent
        container that will be used for all subsequent executions.
        """
        logger.info("Initializing persistent container...")

        try:
            # Ensure image exists
            self.image_manager.ensure_image_exists()

            # Start persistent container
            self.container_id = self.container_lifecycle.start_container(
                memory_limit=self.memory_limit,
                cpu_limit=self.cpu_limit,
                network_access=self.network_access,
                volumes=self.path_manager.get_volume_mounts(),
                read_only=False,  # Allow writing for persistence
            )

            logger.info("Persistent container started: %s", self.container_id[:12])

        except (ContainerLifecycleError, Exception) as e:
            raise PersistentExecutionError(f"Failed to initialize persistent container: {e}") from e

    def _execute_code_internal(
        self,
        code: str,
        timeout: Optional[int] = None,
        **kwargs
    ) -> SandboxExecutionResult:
        """
        Execute code in the persistent container.

        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            **kwargs: Additional execution parameters

        Returns:
            Execution result with output and metadata

        Raises:
            PersistentExecutionError: If execution fails
        """
        if not self.container_lifecycle.is_container_healthy():
            raise PersistentExecutionError(
                "Container is not healthy",
                code,
                self.container_id
            )

        self.log_execution_start(code, timeout or self.default_timeout)
        start_time = time.time()

        try:
            # For persistent execution, we try to preserve partial state on failure
            # if shutdown_on_failure is False in kwargs
            shutdown_on_failure = kwargs.get('shutdown_on_failure', True)

            if not shutdown_on_failure and ';' in code:
                # Try to execute statements individually to preserve partial state
                return self._execute_statements_individually(code, timeout)
            else:
                # Normal execution - prepare script with session state restoration
                execution_script = self._prepare_execution_script(code)

                # Execute the complete script with session restoration via stdin for Unicode support
                exec_command = ["python"]
                result = self.container_lifecycle.execute_command(
                    exec_command,
                    timeout=timeout or self.default_timeout,
                    input_data=execution_script
                )

            # Create execution result
            execution_time = time.time() - start_time
            sandbox_result = SandboxExecutionResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                execution_time=execution_time
            )

            # Track code in session for persistence
            if sandbox_result.success:
                self.session_script_generator.add_code(code)

            self.log_execution_end(sandbox_result)
            return sandbox_result

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Execution failed in persistent container: {e}"
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

    def _prepare_execution_script(self, code: str) -> str:
        """
        Prepare the execution script with session state restoration.

        Args:
            code: User code to execute

        Returns:
            Complete script with session restoration and user code
        """
        script_parts = []

        # Add session restoration if we have state
        if self.session_script_generator.has_state():
            # Re-execute all successful code from history for state restoration
            script_parts.append("# Session restoration - re-executing previous code")
            for code_block in self.session_script_generator.code_history:
                script_parts.append(code_block)
            script_parts.append("")

        # Add user code
        script_parts.append("# User code")
        script_parts.append(code)

        return "\n".join(script_parts)

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

    def _execute_statements_individually(self, code: str, timeout: Optional[int]) -> SandboxExecutionResult:
        """
        Execute statements individually to preserve partial state on failure.

        Args:
            code: Code to execute (expected to contain semicolon-separated statements)
            timeout: Execution timeout

        Returns:
            Execution result with combined output and success status
        """
        # Split code by semicolons and execute each statement separately
        statements = [stmt.strip() for stmt in code.split(';') if stmt.strip()]

        combined_stdout = ""
        combined_stderr = ""
        execution_time = 0.0

        for i, statement in enumerate(statements):
            try:
                # Prepare script with session restoration for this statement
                execution_script = self._prepare_execution_script(statement)

                # Execute this statement via stdin for Unicode support
                exec_command = ["python"]
                start_time = time.time()
                result = self.container_lifecycle.execute_command(
                    exec_command,
                    timeout=timeout or self.default_timeout,
                    input_data=execution_script
                )

                execution_time += time.time() - start_time

                # This statement succeeded
                combined_stdout += result.stdout
                combined_stderr += result.stderr

                # Add successful statement to session history
                self.session_script_generator.add_code(statement)

            except Exception as e:
                # This statement failed
                execution_time += time.time() - start_time

                # Extract error details
                python_stderr = self._extract_python_stderr(e)
                python_stdout = self._extract_python_stdout(e)

                combined_stdout += python_stdout
                combined_stderr += python_stderr

                # Return result showing partial success
                return SandboxExecutionResult(
                    stdout=combined_stdout,
                    stderr=combined_stderr,
                    exit_code=1,  # Failed overall
                    execution_time=execution_time,
                    error=f"Statement {i+1} failed: {e}"
                )

        # All statements succeeded
        return SandboxExecutionResult(
            stdout=combined_stdout,
            stderr=combined_stderr,
            exit_code=0,
            execution_time=execution_time
        )

    def expose_path(
        self,
        host_path: str,
        container_path: Optional[str] = None,
        readonly: bool = False
    ) -> str:
        """
        Expose a host path to the persistent container.

        Note: Path exposure requires container restart to take effect.

        Args:
            host_path: Path on host filesystem
            container_path: Target path in container
            readonly: Mount as read-only

        Returns:
            Container path where host path is accessible

        Example:
            >>> executor = PersistentExecutor("python:3.11")
            >>> container_path = executor.expose_path("/tmp/data", "/app/data")
            >>> print(f"Host data available at: {container_path}")
        """
        container_path = self.path_manager.expose_path(host_path, container_path, readonly)

        # Restart container to apply new mounts if it's running
        # or if the container was just initialized but the volumes weren't included
        if self.container_lifecycle.is_running:
            logger.info("Restarting container to apply new path exposure")
            self.container_id = self.container_lifecycle.restart_container(
                memory_limit=self.memory_limit,
                cpu_limit=self.cpu_limit,
                network_access=self.network_access,
                volumes=self.path_manager.get_volume_mounts(),
                read_only=False,
            )
        elif self.is_initialized:
            # Container was initialized but volumes might not be applied yet
            # This can happen when expose_path is called right after initialization
            logger.info("Restarting recently initialized container to include new volumes")
            self.container_id = self.container_lifecycle.restart_container(
                memory_limit=self.memory_limit,
                cpu_limit=self.cpu_limit,
                network_access=self.network_access,
                volumes=self.path_manager.get_volume_mounts(),
                read_only=False,
            )

        return container_path

    def restart_container(self, **kwargs: Any) -> str:
        """
        Restart the persistent container with optional new parameters.

        Args:
            **kwargs: Optional new container parameters (memory_limit, cpu_limit, etc.)

        Returns:
            New container ID

        Raises:
            PersistentExecutionError: If restart fails

        Example:
            >>> executor = PersistentExecutor("python:3.11")
            >>> new_container_id = executor.restart_container(memory_limit="1g")
        """
        logger.info("Restarting persistent container with new parameters")

        try:
            # Extract parameters with defaults
            memory_limit = kwargs.get('memory_limit', self.memory_limit)
            cpu_limit = kwargs.get('cpu_limit', self.cpu_limit)
            network_access = kwargs.get('network_access', self.network_access)

            # Update instance variables if new values provided
            if 'memory_limit' in kwargs:
                self.memory_limit = memory_limit
            if 'cpu_limit' in kwargs:
                self.cpu_limit = cpu_limit
            if 'network_access' in kwargs:
                self.network_access = network_access

            # Get current session script to restore after restart
            session_script = self.session_script_generator.generate_session_script(include_history=True)

            # Restart the container
            self.container_id = self.container_lifecycle.restart_container(
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
                network_access=network_access,
                volumes=self.path_manager.get_volume_mounts(),
                read_only=False,
            )

            # Restore session state if we have any
            if session_script.strip():
                logger.debug("Restoring session state after restart")
                try:
                    self._execute_code_internal(session_script, timeout=60)
                except Exception as e:
                    logger.warning("Failed to restore session state after restart: %s", e)

            logger.info("Container restarted successfully: %s", self.container_id[:12])
            return self.container_id

        except Exception as e:
            error_msg = f"Failed to restart persistent container: {e}"
            logger.exception(error_msg)
            raise PersistentExecutionError(error_msg) from e

    def expose_directory(
        self,
        host_dir: str,
        container_dir: Optional[str] = None,
        readonly: bool = False
    ) -> str:
        """
        Expose a host directory to the persistent container.

        Args:
            host_dir: Directory on host filesystem
            container_dir: Target directory in container
            readonly: Mount as read-only

        Returns:
            Container directory path

        Example:
            >>> executor = PersistentExecutor("python:3.11")
            >>> work_dir = executor.expose_directory("/home/user/work", "/app/work")
        """
        return self.expose_path(host_dir, container_dir, readonly)

    def get_session_summary(self) -> dict[str, Any]:
        """
        Get summary of current session state.

        Returns:
            Dictionary with session information

        Example:
            >>> executor = PersistentExecutor("python:3.11")
            >>> executor.execute("import os; x = 42")
            >>> summary = executor.get_session_summary()
            >>> print(f"Imports: {summary['imports']}")
        """
        base_summary = self.session_script_generator.get_session_summary()
        base_summary.update({
            "container_id": self.container_id,
            "container_healthy": self.container_lifecycle.is_container_healthy(),
            "exposed_paths": len(self.path_manager.get_exposed_paths_info()),
            "temp_files": len(self.temp_file_manager.get_managed_paths()["files"])
        })
        return base_summary

    def generate_session_script(self, include_history: bool = False) -> str:
        """
        Generate a script that recreates the current session state.

        Args:
            include_history: Include full execution history

        Returns:
            Python script for session restoration

        Example:
            >>> executor = PersistentExecutor("python:3.11")
            >>> executor.execute("import json; data = {'key': 'value'}")
            >>> script = executor.generate_session_script()
            >>> print("Session script generated")
        """
        return self.session_script_generator.generate_session_script(include_history)

    def restart_session(self) -> None:
        """
        Restart the persistent container, preserving session state.

        This method restarts the container and restores the session state
        using the session script generator.

        Example:
            >>> executor = PersistentExecutor("python:3.11")
            >>> executor.execute("x = 42")
            >>> executor.restart_session()
            >>> result = executor.execute("print(x)")  # x is still available
        """
        logger.info("Restarting persistent session")

        # Generate session restoration script
        session_script = self.session_script_generator.generate_session_script()

        # Restart container
        self.container_id = self.container_lifecycle.restart_container(
            memory_limit=self.memory_limit,
            cpu_limit=self.cpu_limit,
            network_access=self.network_access,
            volumes=self.path_manager.get_volume_mounts(),
            read_only=False,
        )

        # Restore session state if we have any
        if session_script.strip():
            logger.debug("Restoring session state after restart")
            restoration_result = self._execute_code_internal(session_script)
            if not restoration_result.success:
                logger.warning("Session state restoration had errors: %s", restoration_result.stderr)

    def clear_session(self) -> None:
        """
        Clear session state and restart with a clean container.

        Example:
            >>> executor = PersistentExecutor("python:3.11")
            >>> executor.execute("x = 42")
            >>> executor.clear_session()
            >>> result = executor.execute("print(x)")  # NameError: x not defined
        """
        logger.info("Clearing persistent session")

        # Clear session state
        self.session_script_generator.clear_session()

        # Restart container with clean state
        self.container_id = self.container_lifecycle.restart_container(
            memory_limit=self.memory_limit,
            cpu_limit=self.cpu_limit,
            network_access=self.network_access,
            volumes=self.path_manager.get_volume_mounts(),
            read_only=False,
        )

    def _is_ready_internal(self) -> bool:
        """
        Check if the persistent executor is ready for execution.

        Returns:
            True if container is healthy and ready
        """
        return (
            self.container_id is not None and
            self.container_lifecycle.is_container_healthy()
        )

    def _validate_environment_internal(self) -> bool:
        """
        Validate the persistent execution environment.

        Returns:
            True if environment is valid
        """
        if not self.container_id:
            logger.warning("No container ID available")
            return False

        if not self.container_lifecycle.is_container_healthy():
            logger.warning("Container is not healthy")
            return False

        return True

    def cleanup(self) -> None:
        """
        Clean up all resources used by the persistent executor.

        This method stops the container, cleans up temporary files,
        and resets all state.

        Example:
            >>> executor = PersistentExecutor("python:3.11")
            >>> # ... use executor ...
            >>> executor.cleanup()
        """
        logger.info("Cleaning up persistent executor")

        try:
            # Stop container
            if self.container_lifecycle.is_running:
                self.container_lifecycle.stop_container()

            # Clean up temporary files
            self.temp_file_manager.cleanup_all()

            # Clear session state
            self.session_script_generator.clear_session()

            # Clear path mappings
            self.path_manager.clear_exposed_paths()

            # Reset state
            self.container_id = None
            self.is_initialized = False

            logger.info("Persistent executor cleanup completed")

        except Exception as e:
            logger.exception("Error during persistent executor cleanup: %s", e)

    def get_execution_info(self) -> dict[str, Any]:
        """
        Get detailed information about the persistent executor.

        Returns:
            Dictionary with executor and container information
        """
        base_info = super().get_execution_info()
        base_info.update({
            "execution_strategy": "persistent",
            "container_id": self.container_id,
            "container_name": self.container_lifecycle.container_name,
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "network_access": self.network_access,
            "container_healthy": self._is_ready_internal(),
            "session_state": self.session_script_generator.get_session_summary(),
            "exposed_paths": self.path_manager.get_exposed_paths_info(),
            "temp_files_count": len(self.temp_file_manager.get_managed_paths()["files"]),
        })
        return base_info
