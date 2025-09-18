"""
Input validation helpers for BioCage.
"""

import re
from pathlib import Path
from typing import Union

from .constants import ERROR_PATH_NOT_EXISTS


def validate_timeout(timeout: int) -> None:
    """Validate timeout value.

    Args:
        timeout: Timeout in seconds

    Raises:
        ValueError: If timeout is invalid
    """
    if timeout <= 0:
        raise ValueError("Timeout must be positive")
    if timeout > 3600:  # 1 hour max
        raise ValueError("Timeout cannot exceed 3600 seconds (1 hour)")


def validate_memory_limit(memory_limit: str) -> None:
    """Validate memory limit format.

    Args:
        memory_limit: Memory limit string (e.g., "512m", "1g")

    Raises:
        ValueError: If memory limit format is invalid
    """
    if not re.match(r'^\d+[kmg]?$', memory_limit.lower()):
        raise ValueError(f"Invalid memory limit '{memory_limit}': must be in format like '512m', '1g', or '1024'")


def validate_cpu_limit(cpu_limit: str) -> None:
    """Validate CPU limit format.

    Args:
        cpu_limit: CPU limit string (e.g., "1.0", "2.5")

    Raises:
        ValueError: If CPU limit format is invalid
    """
    try:
        cpu_value = float(cpu_limit)
        if cpu_value <= 0:
            raise ValueError("CPU limit must be positive")
        if cpu_value > 32:  # Reasonable upper limit
            raise ValueError("CPU limit cannot exceed 32")
    except ValueError as e:
        if "could not convert" in str(e):
            raise ValueError(f"Invalid CPU limit '{cpu_limit}': must be a valid number") from e
        raise


def validate_path_exists(path: Union[str, Path]) -> Path:
    """Validate that a path exists.

    Args:
        path: Path to validate

    Returns:
        Resolved Path object

    Raises:
        FileNotFoundError: If path does not exist
    """
    path_obj = Path(path).resolve()
    if not path_obj.exists():
        raise FileNotFoundError(ERROR_PATH_NOT_EXISTS)
    return path_obj


def validate_path(path: str) -> None:
    """
    Validate a general file system path.

    Args:
        path: Path to validate

    Raises:
        ValueError: If path is invalid
    """
    if not path or not path.strip():
        raise ValueError("Path cannot be empty")
    if len(path) > 4096:  # Maximum path length
        raise ValueError("Path is too long")


def validate_container_path(container_path: str) -> None:
    """Validate container path format.

    Args:
        container_path: Path inside container

    Raises:
        ValueError: If container path is invalid
    """
    if not container_path.startswith('/'):
        raise ValueError("Container path must be absolute (start with '/')")
    if '..' in container_path:
        raise ValueError("Container path cannot contain '..' for security")
    if not container_path.strip():
        raise ValueError("Container path cannot be empty")


def validate_code_string(code: str) -> None:
    """
    Validate Python code string for execution.

    Args:
        code: Python code to validate

    Raises:
        ValueError: If code is invalid
    """
    if not code.strip():
        raise ValueError("Code cannot be empty")
    if len(code) > 1_000_000:  # 1MB limit
        raise ValueError("Code size cannot exceed 1MB")


def validate_code_input(code: str) -> None:
    """Basic validation of code input.

    Args:
        code: Python code to validate

    Raises:
        ValueError: If code is invalid
    """
    if not code.strip():
        raise ValueError("Code cannot be empty")
    if len(code) > 1_000_000:  # 1MB limit
        raise ValueError("Code size cannot exceed 1MB")


def validate_file_suffix(suffix: str) -> None:
    """Validate file suffix format.

    Args:
        suffix: File suffix (e.g., ".py", ".csv")

    Raises:
        ValueError: If suffix is invalid
    """
    if not suffix.startswith('.'):
        raise ValueError("File suffix must start with '.'")
    if len(suffix) < 2:
        raise ValueError("File suffix must have at least one character after '.'")
    if not re.match(r'^\.[a-zA-Z0-9]+$', suffix):
        raise ValueError("File suffix can only contain alphanumeric characters")
