"""
BioCage Orchestrator - High-level API for sandbox operations.

This module provides the main orchestration interface for BioCage, managing
execution strategies, resource allocation, and providing backward compatibility
with the original BioCageManager API while leveraging the new modular architecture.

The BioCageOrchestrator class provides:
- Automatic execution strategy selection (persistent vs ephemeral)
- High-level API for common sandbox operations
- Backward compatibility with existing code
- Resource management and cleanup
- Path and file exposure utilities

Example:
    >>> with BioCageOrchestrator() as sandbox:
    ...     result = sandbox.run("print('Hello World')")
    ...     print(result.stdout)
    Hello World
"""

import logging
from pathlib import Path
from typing import Any, Optional, Union

from .constants import DEFAULT_CPU_LIMIT, DEFAULT_IMAGE_NAME, DEFAULT_MEMORY_LIMIT
from .execution import EphemeralExecutor, PersistentExecutor
from .models import SandboxExecutionResult
from .validation import validate_timeout

logger = logging.getLogger(__name__)


class BioCageOrchestrator:
    """
    High-level orchestrator for BioCage sandbox operations.

    This class provides the main interface for code execution in secure
    containers, managing execution strategies, resource allocation, and
    providing a clean API for all sandbox operations.

    The orchestrator automatically selects between persistent and ephemeral
    execution modes based on usage patterns and provides backward compatibility
    with the original BioCageManager interface.

    Attributes:
        image_name: Docker image name for containers
        memory_limit: Default memory limit for containers
        cpu_limit: Default CPU limit for containers
        network_access: Whether to allow network access
        execution_mode: Current execution mode ('auto', 'persistent', 'ephemeral')
        current_executor: Currently active executor instance

    Example:
        >>> # Basic usage with context manager
        >>> with BioCageOrchestrator() as sandbox:
        ...     result = sandbox.run("print('Hello World')")
        ...     print(f"Output: {result.stdout}")
        >>>
        >>> # Manual execution mode selection
        >>> sandbox = BioCageOrchestrator(execution_mode='persistent')
        >>> sandbox.start_container()
        >>> try:
        ...     result1 = sandbox.run("x = 42")
        ...     result2 = sandbox.run("print(x)")  # x persists
        ... finally:
        ...     sandbox.cleanup()
        >>>
        >>> # File exposure
        >>> with BioCageOrchestrator() as sandbox:
        ...     sandbox.expose_file("/tmp/data.csv", "/app/data.csv")
        ...     result = sandbox.run("import pandas as pd; df = pd.read_csv('/app/data.csv')")
    """

    def __init__(
        self,
        image_name: str = DEFAULT_IMAGE_NAME,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: str = DEFAULT_CPU_LIMIT,
        network_access: bool = False,
        execution_mode: str = "auto",
    ) -> None:
        """
        Initialize the BioCage orchestrator.

        Args:
            image_name: Docker image name for containers
            memory_limit: Memory limit for containers (e.g., "512m", "1g")
            cpu_limit: CPU limit for containers (e.g., "1.0", "2.0")
            network_access: Whether to allow network access in containers
            execution_mode: Execution mode ('auto', 'persistent', 'ephemeral')

        Example:
            >>> orchestrator = BioCageOrchestrator(
            ...     image_name="python:3.11",
            ...     memory_limit="1g",
            ...     cpu_limit="2.0",
            ...     execution_mode="persistent"
            ... )
        """
        self.image_name = image_name
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.network_access = network_access
        self.execution_mode = execution_mode

        # Execution state
        self.current_executor: Optional[Union[PersistentExecutor, EphemeralExecutor]] = None
        self.is_running = False
        self._context_manager_active = False

        logger.info(
            "Initialized BioCageOrchestrator: image=%s, mode=%s, memory=%s, cpu=%s",
            image_name, execution_mode, memory_limit, cpu_limit
        )

    def start_container(
        self,
        memory_limit: Optional[str] = None,
        cpu_limit: Optional[str] = None,
        network_access: Optional[bool] = None
    ) -> str:
        """
        Start a persistent container for stateful execution.

        This method forces the use of persistent execution mode and starts
        a long-running container that maintains state between executions.

        Args:
            memory_limit: Memory limit override
            cpu_limit: CPU limit override
            network_access: Network access override

        Returns:
            Container ID of the started container

        Raises:
            RuntimeError: If container is already running

        Example:
            >>> orchestrator = BioCageOrchestrator()
            >>> container_id = orchestrator.start_container(memory_limit="1g")
            >>> # Now all executions will use the persistent container
            >>> result = orchestrator.run("x = 42")
            >>> orchestrator.stop_container()
        """
        if self.is_running:
            raise RuntimeError("Container is already running")

        # Use provided overrides or defaults
        memory = memory_limit or self.memory_limit
        cpu = cpu_limit or self.cpu_limit
        network = network_access if network_access is not None else self.network_access

        # Create persistent executor
        self.current_executor = PersistentExecutor(
            image_name=self.image_name,
            memory_limit=memory,
            cpu_limit=cpu,
            network_access=network
        )

        # Initialize and get container ID
        self.current_executor.initialize()
        self.is_running = True

        container_info = self.current_executor.get_execution_info()
        container_id: str = container_info.get("container_id", "") or ""

        logger.info("Started persistent container: %s", container_id[:12] if container_id else "unknown")
        return container_id

    def stop_container(self) -> None:
        """
        Stop the persistent container if running.

        This method stops and cleans up the persistent container,
        switching back to ephemeral execution mode.

        Example:
            >>> orchestrator = BioCageOrchestrator()
            >>> orchestrator.start_container()
            >>> # ... use container ...
            >>> orchestrator.stop_container()
        """
        if not self.is_running or not self.current_executor:
            logger.debug("No container to stop")
            return

        try:
            self.current_executor.cleanup()
            logger.info("Stopped persistent container")
        except Exception as e:
            logger.exception("Failed to stop container: %s", e)
        finally:
            self.current_executor = None
            self.is_running = False

    def run(
        self,
        code: str,
        timeout: int = 30,
        stdin_input: Optional[str] = None,
        shutdown_on_failure: bool = True
    ) -> SandboxExecutionResult:
        """
        Execute Python code in the sandbox.

        This method automatically selects the appropriate execution strategy
        based on the current mode and container state, providing a seamless
        execution experience.

        Args:
            code: Python code to execute
            timeout: Timeout in seconds
            stdin_input: Optional stdin input (not used in modular executors)
            shutdown_on_failure: Whether to shutdown on execution failure

        Returns:
            SandboxExecutionResult with execution details

        Example:
            >>> orchestrator = BioCageOrchestrator()
            >>> result = orchestrator.run("print('Hello World')")
            >>> print(f"Success: {result.success}")
            >>> print(f"Output: {result.stdout}")
        """
        # Validate inputs
        validate_timeout(timeout)

        # Handle empty code gracefully
        if not code.strip():
            return SandboxExecutionResult(
                stdout="",
                stderr="",
                exit_code=0,
                execution_time=0.0,
            )

        try:
            # Determine execution strategy
            executor = self._get_executor()

            # Execute code, passing shutdown_on_failure for persistence handling
            result = executor.execute(code, timeout=timeout, shutdown_on_failure=shutdown_on_failure)

            # Handle failure if requested
            if shutdown_on_failure and not result.success and self.is_running:
                logger.warning("Execution failed, shutting down persistent container")
                self.stop_container()

            return result

        except Exception as e:
            logger.exception("Code execution failed: %s", e)
            error_result = SandboxExecutionResult(
                error=f"Execution failed: {e}",
                exit_code=1,
                execution_time=0.0
            )

            # Shutdown on critical failure
            if shutdown_on_failure and self.is_running:
                self.stop_container()

            return error_result

    def expose_path(
        self,
        host_path: Union[str, Path],
        container_path: Optional[str] = None,
        readonly: bool = True
    ) -> str:
        """
        Expose a host path to containers.

        This method configures path exposure for both current and future
        container executions.

        Args:
            host_path: Path on the host filesystem
            container_path: Target path in containers
            readonly: Whether to mount as read-only

        Returns:
            Container path where the host path will be accessible

        Example:
            >>> orchestrator = BioCageOrchestrator()
            >>> container_path = orchestrator.expose_path("/tmp/data", "/app/data")
            >>> result = orchestrator.run("import os; print(os.listdir('/app/data'))")
        """
        # Force persistent mode for path exposures - ephemeral containers can't mount volumes
        if self.execution_mode == "auto" and not self.current_executor:
            # Temporarily override mode detection to force persistent
            old_mode = self.execution_mode
            self.execution_mode = "persistent"
            try:
                executor = self._get_executor()
            finally:
                self.execution_mode = old_mode
        else:
            executor = self._get_executor()

        if isinstance(executor, PersistentExecutor):
            return executor.expose_path(str(host_path), container_path, readonly)
        else:
            return executor.expose_path(str(host_path), container_path, readonly)

    def expose_file(
        self,
        host_file_path: Union[str, Path],
        container_file_path: Optional[str] = None
    ) -> str:
        """
        Expose a single file to containers.

        Args:
            host_file_path: File path on the host
            container_file_path: File path inside containers

        Returns:
            The container path where the file is accessible

        Example:
            >>> orchestrator = BioCageOrchestrator()
            >>> file_path = orchestrator.expose_file("/tmp/config.json", "/app/config.json")
            >>> result = orchestrator.run("import json; print(json.load(open('/app/config.json')))")
        """
        return self.expose_path(host_file_path, container_file_path, readonly=True)

    def expose_directory(
        self,
        host_dir_path: Union[str, Path],
        container_dir_path: Optional[str] = None,
        readonly: bool = True
    ) -> str:
        """
        Expose a directory to containers.

        Args:
            host_dir_path: Directory path on the host
            container_dir_path: Directory path inside containers
            readonly: Whether the directory should be read-only

        Returns:
            The container path where the directory is accessible

        Example:
            >>> orchestrator = BioCageOrchestrator()
            >>> dir_path = orchestrator.expose_directory("/home/data", "/app/data", readonly=False)
            >>> result = orchestrator.run("with open('/app/data/output.txt', 'w') as f: f.write('Hello')")
        """
        return self.expose_path(host_dir_path, container_dir_path, readonly)

    def restart_container(self, **kwargs: Any) -> str:
        """
        Restart the persistent container with optional new parameters.

        Args:
            **kwargs: New parameters for container startup

        Returns:
            Container ID of the restarted container

        Example:
            >>> orchestrator = BioCageOrchestrator()
            >>> orchestrator.start_container(memory_limit="512m")
            >>> # Need more memory
            >>> container_id = orchestrator.restart_container(memory_limit="1g")
        """
        if not self.is_running or not isinstance(self.current_executor, PersistentExecutor):
            raise RuntimeError("No persistent container to restart")

        # Update configuration with provided kwargs
        memory = kwargs.get('memory_limit', self.memory_limit)
        cpu = kwargs.get('cpu_limit', self.cpu_limit)
        network = kwargs.get('network_access', self.network_access)

        # Restart the persistent executor
        container_id = self.current_executor.restart_container(
            memory_limit=memory,
            cpu_limit=cpu,
            network_access=network
        )

        logger.info("Restarted persistent container: %s", container_id[:12])
        return container_id

    def get_container_info(self) -> dict[str, Any]:
        """
        Get information about the current execution environment.

        Returns:
            Dictionary with execution environment details

        Example:
            >>> orchestrator = BioCageOrchestrator()
            >>> info = orchestrator.get_container_info()
            >>> print(f"Execution mode: {info['execution_mode']}")
        """
        base_info = {
            "execution_mode": self._get_current_mode(),
            "is_running": self.is_running,
            "image_name": self.image_name,
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "network_access": self.network_access,
        }

        if self.current_executor:
            executor_info = self.current_executor.get_execution_info()
            base_info.update(executor_info)

        return base_info

    def create_temp_file(self, content: str, suffix: str = ".txt") -> str:
        """
        Create a temporary file with the given content in the execution environment.

        This method creates a temporary file inside the container that is accessible
        from code execution. The file is automatically tracked for cleanup.

        Args:
            content: Content to write to the temporary file
            suffix: File extension (e.g., ".csv", ".py", ".json")

        Returns:
            Path to the temporary file that can be used in executed code

        Raises:
            ValueError: If content is empty or suffix is invalid
            RuntimeError: If no executor is available or file creation fails

        Example:
            >>> orchestrator = BioCageOrchestrator()
            >>> csv_path = orchestrator.create_temp_file("name,age\\nAlice,25", ".csv")
            >>> result = orchestrator.run(f"import pandas as pd; df = pd.read_csv('{csv_path}')")
        """
        import uuid

        from .validation import validate_file_suffix

        # Validate inputs
        if not content.strip():
            raise ValueError("Content cannot be empty")

        validate_file_suffix(suffix)

        # Ensure we have an executor
        if not self.current_executor:
            self._get_executor()

        # Generate a unique filename in the container workspace
        unique_id = uuid.uuid4().hex[:8]
        container_path = f"/app/workspace/temp_{unique_id}{suffix}"

        # Create the file inside the container using Python code execution
        escaped_content = repr(content)  # Safely escape the content
        create_file_code = f"""
import os
os.makedirs('/app/workspace', exist_ok=True)
with open('{container_path}', 'w') as f:
    f.write({escaped_content})
print(f"Created temp file: {container_path}")
"""

        # Type guard to ensure we have an executor
        if self.current_executor is None:
            raise RuntimeError("No executor available")

        # Execute the file creation code
        result = self.current_executor.execute(create_file_code)
        if not result.success:
            raise RuntimeError(f"Failed to create temp file: {result.stderr}")

        # Track the file in the executor's temp file manager for cleanup
        if hasattr(self.current_executor, 'temp_file_manager'):
            # Add to the files list for tracking (as container path)
            self.current_executor.temp_file_manager.temp_files.append(container_path)

        return container_path

    def cleanup(self) -> None:
        """
        Clean up all resources used by the orchestrator.

        This method stops any running containers, cleans up temporary files,
        and resets the orchestrator state.

        Example:
            >>> orchestrator = BioCageOrchestrator()
            >>> orchestrator.start_container()
            >>> # ... use orchestrator ...
            >>> orchestrator.cleanup()
        """
        logger.info("Cleaning up BioCage orchestrator")

        try:
            if self.current_executor:
                self.current_executor.cleanup()

            # Reset state
            self.current_executor = None
            self.is_running = False

            logger.info("BioCage orchestrator cleanup completed")

        except Exception as e:
            logger.exception("Error during orchestrator cleanup: %s", e)

    def configure_context_manager(
        self,
        expose_files: Optional[dict[str, str]] = None,
        expose_directories: Optional[dict[str, str]] = None,
        expose_directories_rw: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> "BioCageOrchestrator":
        """
        Configure parameters for when using the context manager (with statement).

        This method provides backward compatibility with the original BioCageManager
        API while leveraging the new modular architecture.

        Args:
            expose_files: Dict of {host_file_path: container_file_path} to expose (read-only)
            expose_directories: Dict of {host_dir_path: container_dir_path} to expose (read-only)
            expose_directories_rw: Dict of {host_dir_path: container_dir_path} to expose (read-write)
            **kwargs: Additional parameters for container startup

        Returns:
            Self for method chaining

        Example:
            >>> with BioCageOrchestrator().configure_context_manager(
            ...     expose_files={"/path/data.csv": "/app/data.csv"},
            ...     expose_directories_rw={"./output": "/app/output"}
            ... ) as sandbox:
            ...     result = sandbox.run("print('Hello World')")
        """
        # Store configuration for context manager
        self._expose_files = expose_files or {}
        self._expose_directories = expose_directories or {}
        self._expose_directories_rw = expose_directories_rw or {}
        self._context_kwargs = kwargs

        return self

    def __enter__(self) -> "BioCageOrchestrator":
        """Context manager entry - prepare for execution."""
        self._context_manager_active = True

        # Apply path exposures if configured
        if hasattr(self, '_expose_files'):
            for host_path, container_path in self._expose_files.items():
                self.expose_file(host_path, container_path)

        if hasattr(self, '_expose_directories'):
            for host_path, container_path in self._expose_directories.items():
                self.expose_directory(host_path, container_path, readonly=True)

        if hasattr(self, '_expose_directories_rw'):
            for host_path, container_path in self._expose_directories_rw.items():
                self.expose_directory(host_path, container_path, readonly=False)

        # If execution mode is persistent or auto, start a persistent container
        if self.execution_mode in ("persistent", "auto") and not self.is_running:
            kwargs = getattr(self, '_context_kwargs', {})
            try:
                self.start_container(**kwargs)
            except Exception as e:
                # Re-raise validation errors as ValueError for better error handling
                if "invalid" in str(e).lower() or "must be" in str(e).lower():
                    raise ValueError(str(e)) from e
                raise

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup resources."""
        self._context_manager_active = False
        self.cleanup()

    def _get_executor(self) -> Union[PersistentExecutor, EphemeralExecutor]:
        """
        Get the appropriate executor for the current execution context.

        Returns:
            Executor instance based on current mode and state
        """
        # If we have a persistent executor running, use it
        if self.is_running and isinstance(self.current_executor, PersistentExecutor):
            return self.current_executor

        # Determine execution mode
        mode = self._get_current_mode()

        if mode == "persistent":
            # Create or return persistent executor
            if not self.current_executor or not isinstance(self.current_executor, PersistentExecutor):
                self.current_executor = PersistentExecutor(
                    image_name=self.image_name,
                    memory_limit=self.memory_limit,
                    cpu_limit=self.cpu_limit,
                    network_access=self.network_access
                )
                if not self.current_executor.is_initialized:
                    self.current_executor.initialize()
                self.is_running = True

            return self.current_executor

        else:  # ephemeral mode
            # Create or return ephemeral executor
            if not self.current_executor or not isinstance(self.current_executor, EphemeralExecutor):
                self.current_executor = EphemeralExecutor(
                    image_name=self.image_name,
                    memory_limit=self.memory_limit,
                    cpu_limit=self.cpu_limit,
                    network_access=self.network_access
                )
                if not self.current_executor.is_initialized:
                    self.current_executor.initialize()

            return self.current_executor

    def _has_path_exposures(self) -> bool:
        """
        Check if any path exposures have been configured.

        Returns:
            True if any paths have been exposed, False otherwise
        """
        # Check if we have any existing executor with path exposures
        if self.current_executor:
            if hasattr(self.current_executor, 'path_manager'):
                exposed_paths = self.current_executor.path_manager.get_exposed_paths_info()
                if exposed_paths:
                    return True

        # Check if we have pending exposures from context manager configuration
        if (hasattr(self, '_expose_files') or
            hasattr(self, '_expose_directories') or
            hasattr(self, '_expose_directories_rw')):
            return True

        return False

    def _get_current_mode(self) -> str:
        """
        Determine the current execution mode.

        Returns:
            Current execution mode ('persistent' or 'ephemeral')
        """
        if self.execution_mode == "persistent":
            return "persistent"
        elif self.execution_mode == "ephemeral":
            return "ephemeral"
        else:  # auto mode
            # In auto mode, use persistent if we're in a context manager, already running,
            # or if we have path exposures (which require persistent containers)
            if (self._context_manager_active or
                self.is_running or
                self._has_path_exposures()):
                return "persistent"
            else:
                return "ephemeral"


# Backward compatibility alias
BioCageManager = BioCageOrchestrator
