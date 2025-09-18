"""
Base execution logic for BioCage sandbox operations.

This module provides the abstract base class and common functionality for
code execution in sandboxed environments. It defines the interface that
all execution strategies must implement and provides shared utilities.

The BaseExecutor class provides:
- Abstract interface for execution strategies
- Common validation and preparation logic
- Shared error handling patterns
- Timing and result processing utilities
- Template methods for execution workflow

Example:
    >>> # This is an abstract base class, use concrete implementations
    >>> from .persistent_executor import PersistentExecutor
    >>> executor = PersistentExecutor("python:3.11")
    >>> result = executor.execute("print('hello')")
    >>> print(f"Output: {result.stdout}")
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..models.execution_result import SandboxExecutionResult
from ..validation import validate_code_string, validate_timeout

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """
    Exception raised when code execution fails.

    This exception provides detailed information about execution failures
    including the execution strategy, code that failed, and error details.

    Attributes:
        executor_type: Type of executor that failed
        code: The code that failed to execute (truncated for safety)
        error_message: Detailed error message
        exit_code: Process exit code (if applicable)
    """

    def __init__(
        self,
        executor_type: str,
        error_message: str,
        code: Optional[str] = None,
        exit_code: Optional[int] = None
    ) -> None:
        """
        Initialize an execution error.

        Args:
            executor_type: Type of executor (persistent, ephemeral, etc.)
            error_message: Detailed error message
            code: Code that failed (will be truncated for safety)
            exit_code: Process exit code if available
        """
        code_snippet = code[:100] + "..." if code and len(code) > 100 else code or "N/A"
        super().__init__(f"{executor_type} execution failed: {error_message} (code: {code_snippet})")
        self.executor_type = executor_type
        self.error_message = error_message
        self.code = code
        self.exit_code = exit_code


class BaseExecutor(ABC):
    """
    Abstract base class for code execution strategies.

    This class defines the interface that all execution strategies must
    implement and provides common functionality shared across different
    execution modes (persistent, ephemeral, etc.).

    The base executor handles validation, timing, error handling, and
    result processing while delegating the actual execution logic to
    concrete implementations.

    Attributes:
        image_name: Docker image name for execution
        default_timeout: Default timeout for executions
        is_initialized: Whether the executor has been initialized

    Example:
        >>> # Subclass implementation example
        >>> class MyExecutor(BaseExecutor):
        ...     def _execute_code_internal(self, code, timeout):
        ...         # Implement actual execution logic
        ...         return SandboxExecutionResult(stdout="result")
        ...
        ...     def cleanup(self):
        ...         # Implement cleanup logic
        ...         pass
    """

    def __init__(self, image_name: str, default_timeout: int = 30) -> None:
        """
        Initialize the base executor.

        Args:
            image_name: Docker image name for code execution
            default_timeout: Default timeout in seconds for code execution

        Example:
            >>> executor = ConcreteExecutor("python:3.11", default_timeout=60)
            >>> executor.image_name
            'python:3.11'
        """
        self.image_name = image_name
        self.default_timeout = default_timeout
        self.is_initialized = False
        logger.debug(
            "Initialized %s with image=%s, timeout=%d",
            self.__class__.__name__,
            image_name,
            default_timeout
        )

    @abstractmethod
    def _execute_code_internal(
        self,
        code: str,
        timeout: Optional[int] = None,
        **kwargs
    ) -> SandboxExecutionResult:
        """
        Execute code in the sandbox (internal implementation).

        This method must be implemented by concrete executor classes to
        provide the actual execution logic specific to their strategy.

        Args:
            code: Python code to execute
            timeout: Timeout in seconds (uses default if None)
            **kwargs: Additional execution parameters

        Returns:
            Execution result with output and metadata

        Raises:
            ExecutionError: If execution fails
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """
        Clean up executor resources.

        This method must be implemented by concrete executor classes to
        properly clean up any resources (containers, temp files, etc.)
        used during execution.
        """
        pass

    def execute(
        self,
        code: str,
        timeout: Optional[int] = None,
        **kwargs
    ) -> SandboxExecutionResult:
        """
        Execute Python code in the sandbox with validation and timing.

        This is the main public interface for code execution. It handles
        validation, timing, error handling, and delegates to the internal
        implementation for actual execution.

        Args:
            code: Python code to execute
            timeout: Timeout in seconds (uses default if None)
            **kwargs: Additional execution parameters

        Returns:
            Execution result with stdout, stderr, timing, and status

        Raises:
            ExecutionError: If execution fails
            ValueError: If parameters are invalid

        Example:
            >>> executor = ConcreteExecutor("python:3.11")
            >>> result = executor.execute("print('Hello World')")
            >>> print(f"Success: {result.success}")
            >>> print(f"Output: {result.stdout}")
        """
        # Validate inputs
        validate_code_string(code)
        if timeout is not None:
            validate_timeout(timeout)
        else:
            timeout = self.default_timeout

        logger.info("Executing code with %s (timeout=%d)", self.__class__.__name__, timeout)
        logger.debug("Code to execute: %s", code[:100] + "..." if len(code) > 100 else code)

        start_time = time.time()

        try:
            # Ensure executor is initialized
            if not self.is_initialized:
                self.initialize()

            # Delegate to concrete implementation
            result = self._execute_code_internal(code, timeout, **kwargs)

            # Calculate execution time
            execution_time = time.time() - start_time
            result.execution_time = execution_time

            logger.info(
                "Execution completed: success=%s, time=%.3fs, exit_code=%d",
                result.success,
                execution_time,
                result.exit_code
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.exception("Execution failed after %.3fs: %s", execution_time, str(e))

            # If it's already an ExecutionError, re-raise it
            if isinstance(e, ExecutionError):
                raise

            # Wrap other exceptions in ExecutionError
            raise ExecutionError(
                self.__class__.__name__,
                str(e),
                code,
                getattr(e, 'exit_code', None)
            ) from e

    def initialize(self) -> None:
        """
        Initialize the executor for first use.

        This method is called automatically before the first execution
        and can be overridden by concrete classes to perform setup tasks
        like container preparation, image verification, etc.

        Example:
            >>> executor = ConcreteExecutor("python:3.11")
            >>> executor.initialize()
            >>> executor.is_initialized
            True
        """
        if self.is_initialized:
            return

        logger.debug("Initializing %s", self.__class__.__name__)
        self._initialize_internal()
        self.is_initialized = True
        logger.info("Executor initialized successfully")

    def _initialize_internal(self) -> None:
        """
        Internal initialization logic (override in subclasses).

        This method can be overridden by concrete executor classes to
        perform specific initialization tasks.
        """
        # Default implementation does nothing
        pass

    def get_execution_info(self) -> dict[str, Any]:
        """
        Get information about the executor configuration.

        Returns:
            Dictionary containing executor metadata

        Example:
            >>> executor = ConcreteExecutor("python:3.11")
            >>> info = executor.get_execution_info()
            >>> info['image_name']
            'python:3.11'
        """
        return {
            "executor_type": self.__class__.__name__,
            "image_name": self.image_name,
            "default_timeout": self.default_timeout,
            "is_initialized": self.is_initialized
        }

    def is_ready(self) -> bool:
        """
        Check if the executor is ready for code execution.

        Returns:
            True if executor is ready, False otherwise

        Example:
            >>> executor = ConcreteExecutor("python:3.11")
            >>> executor.is_ready()
            False
            >>> executor.initialize()
            >>> executor.is_ready()
            True
        """
        return self.is_initialized and self._is_ready_internal()

    def _is_ready_internal(self) -> bool:
        """
        Internal readiness check (override in subclasses).

        Returns:
            True if executor-specific resources are ready
        """
        # Default implementation assumes ready if initialized
        return True

    def __enter__(self):
        """Enter context manager and initialize if needed."""
        if not self.is_initialized:
            self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and cleanup resources."""
        self.cleanup()

    def validate_execution_environment(self) -> bool:
        """
        Validate that the execution environment is properly configured.

        This method performs pre-execution validation to ensure the
        environment is ready for code execution.

        Returns:
            True if environment is valid, False otherwise

        Example:
            >>> executor = ConcreteExecutor("python:3.11")
            >>> executor.initialize()
            >>> is_valid = executor.validate_execution_environment()
        """
        try:
            # Check if executor is initialized
            if not self.is_initialized:
                logger.warning("Executor not initialized")
                return False

            # Delegate to concrete implementation
            return self._validate_environment_internal()

        except Exception as e:
            logger.exception("Environment validation failed: %s", e)
            return False

    def _validate_environment_internal(self) -> bool:
        """
        Internal environment validation (override in subclasses).

        Returns:
            True if environment is valid
        """
        # Default implementation assumes valid
        return True

    def create_error_result(
        self,
        error_message: str,
        exit_code: int = 1,
        stderr: str = "",
        execution_time: float = 0.0
    ) -> SandboxExecutionResult:
        """
        Create a standardized error result.

        This utility method creates a consistent error result format
        for use across different execution scenarios.

        Args:
            error_message: Error message to include
            exit_code: Process exit code
            stderr: Standard error output
            execution_time: Time taken before error

        Returns:
            SandboxExecutionResult representing the error

        Example:
            >>> executor = ConcreteExecutor("python:3.11")
            >>> error_result = executor.create_error_result("Test failed")
            >>> error_result.success
            False
            >>> error_result.error
            'Test failed'
        """
        return SandboxExecutionResult(
            stdout="",
            stderr=stderr,
            exit_code=exit_code,
            execution_time=execution_time,
            error=error_message
        )

    def log_execution_start(self, code: str, timeout: int) -> None:
        """
        Log the start of code execution.

        Args:
            code: Code being executed
            timeout: Execution timeout
        """
        code_preview = code[:50] + "..." if len(code) > 50 else code
        logger.info(
            "Starting execution with %s: timeout=%ds, code='%s'",
            self.__class__.__name__,
            timeout,
            code_preview
        )

    def log_execution_end(self, result: SandboxExecutionResult) -> None:
        """
        Log the completion of code execution.

        Args:
            result: Execution result
        """
        logger.info(
            "Execution completed: success=%s, time=%.3fs, exit_code=%d, has_output=%s",
            result.success,
            result.execution_time,
            result.exit_code,
            result.has_output()
        )

        if result.has_errors():
            logger.warning("Execution had errors: %s", result.stderr[:100])
