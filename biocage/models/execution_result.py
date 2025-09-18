"""
Execution result model for sandbox operations.

This module contains the SandboxExecutionResult class that encapsulates
the outcome of code execution in the sandbox, providing a standardized
way to represent execution results with metadata.

The execution result includes stdout/stderr output, exit codes, timing
information, and success/failure status for comprehensive result analysis.
"""

from typing import Any, Optional


class SandboxExecutionResult:
    """
    Container for sandbox execution results.

    This class encapsulates all information about a code execution,
    including output, errors, timing, and success status. It provides
    a standardized interface for accessing execution results.

    Attributes:
        stdout (str): Standard output from the executed code
        stderr (str): Standard error from the executed code
        exit_code (int): Process exit code (0 for success)
        execution_time (float): Time taken for execution in seconds
        error (Optional[str]): Error message if execution failed
        success (bool): True if execution succeeded, False otherwise

    Example:
        >>> result = SandboxExecutionResult(
        ...     stdout="Hello World\\n",
        ...     stderr="",
        ...     exit_code=0,
        ...     execution_time=0.125
        ... )
        >>> print(f"Success: {result.success}")
        Success: True
        >>> print(f"Output: {result.stdout.strip()}")
        Output: Hello World
    """

    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        execution_time: float = 0.0,
        error: Optional[str] = None,
    ) -> None:
        """
        Initialize a sandbox execution result.

        Args:
            stdout: Standard output from the executed code
            stderr: Standard error from the executed code
            exit_code: Process exit code (0 indicates success)
            execution_time: Time taken for execution in seconds
            error: Optional error message if execution failed

        Note:
            The success property is automatically determined based on
            exit_code being 0 and error being None.
        """
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.execution_time = execution_time
        self.error = error
        self.success = exit_code == 0 and error is None

    def __repr__(self) -> str:
        """
        Return a string representation of the execution result.

        Returns:
            A concise string showing exit code and success status

        Example:
            >>> result = SandboxExecutionResult(exit_code=1)
            >>> repr(result)
            'SandboxExecutionResult(exit_code=1, success=False)'
        """
        return f"SandboxExecutionResult(exit_code={self.exit_code}, success={self.success})"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert execution result to dictionary representation.

        This method is useful for serialization, logging, or API responses
        where a dictionary format is preferred over the object.

        Returns:
            Dictionary containing all execution result data

        Example:
            >>> result = SandboxExecutionResult(stdout="test", exit_code=0)
            >>> data = result.to_dict()
            >>> data['success']
            True
            >>> data['stdout']
            'test'
        """
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "error": self.error,
            "success": self.success,
        }

    def has_output(self) -> bool:
        """
        Check if the execution produced any output.

        Returns:
            True if stdout or stderr contain non-empty content

        Example:
            >>> result = SandboxExecutionResult(stdout="Hello")
            >>> result.has_output()
            True
        """
        return bool(self.stdout.strip() or self.stderr.strip())

    def has_errors(self) -> bool:
        """
        Check if the execution produced any errors.

        Returns:
            True if stderr contains content or error is set

        Example:
            >>> result = SandboxExecutionResult(stderr="Error occurred")
            >>> result.has_errors()
            True
        """
        return bool(self.stderr.strip() or self.error)

    def get_formatted_output(self) -> str:
        """
        Get formatted output combining stdout and stderr.

        Returns:
            Formatted string with labeled stdout and stderr sections

        Example:
            >>> result = SandboxExecutionResult(
            ...     stdout="Output text",
            ...     stderr="Error text"
            ... )
            >>> formatted = result.get_formatted_output()
            >>> "STDOUT:" in formatted
            True
        """
        output_parts = []

        if self.stdout.strip():
            output_parts.append(f"STDOUT:\n{self.stdout}")

        if self.stderr.strip():
            output_parts.append(f"STDERR:\n{self.stderr}")

        if self.error:
            output_parts.append(f"ERROR:\n{self.error}")

        return "\n\n".join(output_parts) if output_parts else "(No output)"
