"""
Temporary file management for BioCage sandbox operations.

This module handles the creation, management, and cleanup of temporary files
and directories used during sandbox execution. It provides secure temporary
file operations with automatic cleanup and proper lifecycle management.

The TempFileManager class provides:
- Secure temporary file and directory creation
- Automatic cleanup on completion or error
- Context manager support for guaranteed cleanup
- Temporary file tracking and management
- Safe file writing and reading operations

Example:
    >>> with TempFileManager() as temp_mgr:
    ...     temp_file = temp_mgr.create_temp_file("print('hello')", suffix=".py")
    ...     temp_dir = temp_mgr.create_temp_directory()
    ...     # Files are automatically cleaned up when exiting context
"""

import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class TempFileError(Exception):
    """
    Exception raised when temporary file operations fail.

    This exception provides detailed information about temporary file
    operation failures including the operation attempted and error details.

    Attributes:
        operation: The operation that failed (create, write, read, cleanup)
        path: The path that failed (if applicable)
        error_message: Detailed error message
    """

    def __init__(self, operation: str, error_message: str, path: Optional[str] = None) -> None:
        """
        Initialize a temporary file error.

        Args:
            operation: Operation that failed
            error_message: Detailed error message
            path: Path that failed (if applicable)
        """
        if path:
            super().__init__(f"Temporary file {operation} failed for '{path}': {error_message}")
        else:
            super().__init__(f"Temporary file {operation} failed: {error_message}")
        self.operation = operation
        self.error_message = error_message
        self.path = path


class TempFileManager:
    """
    Manages temporary files and directories for sandbox operations.

    This class provides secure creation and management of temporary files
    and directories with automatic cleanup capabilities. It tracks all
    created temporary items and ensures proper cleanup even in error cases.

    The manager can be used as a context manager for guaranteed cleanup
    or managed manually with explicit cleanup calls.

    Attributes:
        temp_files: List of created temporary file paths
        temp_directories: List of created temporary directory paths
        base_dir: Base directory for temporary file creation

    Example:
        >>> # Using as context manager (recommended)
        >>> with TempFileManager() as temp_mgr:
        ...     script_file = temp_mgr.create_temp_file("print('hello')")
        ...     output_dir = temp_mgr.create_temp_directory()
        ...     # Automatic cleanup when exiting
        >>>
        >>> # Manual management
        >>> temp_mgr = TempFileManager()
        >>> try:
        ...     temp_file = temp_mgr.create_temp_file("data")
        ...     # ... use temp file ...
        ... finally:
        ...     temp_mgr.cleanup_all()
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        """
        Initialize the temporary file manager.

        Args:
            base_dir: Base directory for temporary files (uses system default if None)

        Example:
            >>> temp_mgr = TempFileManager("/tmp/biocage")
            >>> temp_mgr.base_dir
            '/tmp/biocage'
        """
        self.base_dir = base_dir
        self.temp_files: list[str] = []
        self.temp_directories: list[str] = []
        logger.debug("Initialized TempFileManager with base_dir: %s", base_dir)

    def __enter__(self) -> "TempFileManager":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and cleanup all temporary files."""
        self.cleanup_all()

    def create_temp_file(
        self,
        content: str = "",
        suffix: str = "",
        prefix: str = "biocage_",
        encoding: str = "utf-8"
    ) -> str:
        """
        Create a temporary file with optional content.

        This method creates a secure temporary file, optionally writes content
        to it, and tracks it for later cleanup. The file is created with
        appropriate permissions and in a secure location.

        Args:
            content: Content to write to the file
            suffix: File suffix (e.g., ".py", ".txt")
            prefix: File prefix for identification
            encoding: Text encoding for file content

        Returns:
            Path to the created temporary file

        Raises:
            TempFileError: If file creation or writing fails

        Example:
            >>> temp_mgr = TempFileManager()
            >>> script_path = temp_mgr.create_temp_file(
            ...     "print('Hello World')",
            ...     suffix=".py"
            ... )
            >>> print(f"Script created at: {script_path}")
        """
        try:
            # Create temporary file
            fd, file_path = tempfile.mkstemp(
                suffix=suffix,
                prefix=prefix,
                dir=self.base_dir,
                text=True
            )

            # Close the file descriptor initially
            os.close(fd)

            # Write content if provided
            if content:
                with open(file_path, 'w', encoding=encoding) as f:
                    f.write(content)

            # Track the file
            self.temp_files.append(file_path)
            logger.debug("Created temporary file: %s", file_path)

            return file_path

        except OSError as e:
            raise TempFileError("create", str(e)) from e

    def create_temp_directory(self, prefix: str = "biocage_") -> str:
        """
        Create a temporary directory.

        This method creates a secure temporary directory and tracks it
        for later cleanup.

        Args:
            prefix: Directory prefix for identification

        Returns:
            Path to the created temporary directory

        Raises:
            TempFileError: If directory creation fails

        Example:
            >>> temp_mgr = TempFileManager()
            >>> temp_dir = temp_mgr.create_temp_directory()
            >>> print(f"Temp directory: {temp_dir}")
        """
        try:
            dir_path = tempfile.mkdtemp(
                prefix=prefix,
                dir=self.base_dir
            )

            # Track the directory
            self.temp_directories.append(dir_path)
            logger.debug("Created temporary directory: %s", dir_path)

            return dir_path

        except OSError as e:
            raise TempFileError("create", str(e)) from e

    def write_temp_file(self, file_path: str, content: str, encoding: str = "utf-8") -> None:
        """
        Write content to an existing temporary file.

        Args:
            file_path: Path to the temporary file
            content: Content to write
            encoding: Text encoding

        Raises:
            TempFileError: If writing fails
            ValueError: If file is not managed by this manager

        Example:
            >>> temp_mgr = TempFileManager()
            >>> temp_file = temp_mgr.create_temp_file()
            >>> temp_mgr.write_temp_file(temp_file, "new content")
        """
        if file_path not in self.temp_files:
            raise ValueError(f"File not managed by this TempFileManager: {file_path}")

        try:
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
            logger.debug("Wrote content to temporary file: %s", file_path)

        except OSError as e:
            raise TempFileError("write", str(e), file_path) from e

    def read_temp_file(self, file_path: str, encoding: str = "utf-8") -> str:
        """
        Read content from a temporary file.

        Args:
            file_path: Path to the temporary file
            encoding: Text encoding

        Returns:
            Content of the file

        Raises:
            TempFileError: If reading fails
            ValueError: If file is not managed by this manager

        Example:
            >>> temp_mgr = TempFileManager()
            >>> temp_file = temp_mgr.create_temp_file("test content")
            >>> content = temp_mgr.read_temp_file(temp_file)
            >>> print(content)
            test content
        """
        if file_path not in self.temp_files:
            raise ValueError(f"File not managed by this TempFileManager: {file_path}")

        try:
            with open(file_path, encoding=encoding) as f:
                content = f.read()
            logger.debug("Read content from temporary file: %s", file_path)
            return content

        except OSError as e:
            raise TempFileError("read", str(e), file_path) from e

    def get_temp_file_in_directory(self, temp_dir: str, filename: str) -> str:
        """
        Get the path for a file within a temporary directory.

        Args:
            temp_dir: Temporary directory path
            filename: Name of the file

        Returns:
            Full path to the file within the directory

        Raises:
            ValueError: If directory is not managed by this manager

        Example:
            >>> temp_mgr = TempFileManager()
            >>> temp_dir = temp_mgr.create_temp_directory()
            >>> file_path = temp_mgr.get_temp_file_in_directory(temp_dir, "data.txt")
        """
        if temp_dir not in self.temp_directories:
            raise ValueError(f"Directory not managed by this TempFileManager: {temp_dir}")

        return os.path.join(temp_dir, filename)

    def cleanup_file(self, file_path: str) -> bool:
        """
        Remove a specific temporary file.

        Args:
            file_path: Path to the file to remove

        Returns:
            True if file was removed successfully, False otherwise

        Example:
            >>> temp_mgr = TempFileManager()
            >>> temp_file = temp_mgr.create_temp_file()
            >>> removed = temp_mgr.cleanup_file(temp_file)
            >>> print(f"File removed: {removed}")
        """
        if file_path not in self.temp_files:
            logger.warning("File not managed by this manager: %s", file_path)
            return False

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug("Removed temporary file: %s", file_path)

            self.temp_files.remove(file_path)
            return True

        except OSError as e:
            logger.warning("Failed to remove temporary file %s: %s", file_path, e)
            return False

    def cleanup_directory(self, dir_path: str) -> bool:
        """
        Remove a specific temporary directory and all its contents.

        Args:
            dir_path: Path to the directory to remove

        Returns:
            True if directory was removed successfully, False otherwise

        Example:
            >>> temp_mgr = TempFileManager()
            >>> temp_dir = temp_mgr.create_temp_directory()
            >>> removed = temp_mgr.cleanup_directory(temp_dir)
            >>> print(f"Directory removed: {removed}")
        """
        if dir_path not in self.temp_directories:
            logger.warning("Directory not managed by this manager: %s", dir_path)
            return False

        try:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
                logger.debug("Removed temporary directory: %s", dir_path)

            self.temp_directories.remove(dir_path)
            return True

        except OSError as e:
            logger.warning("Failed to remove temporary directory %s: %s", dir_path, e)
            return False

    def cleanup_all(self) -> dict[str, int]:
        """
        Remove all temporary files and directories managed by this instance.

        Returns:
            Dictionary with cleanup statistics

        Example:
            >>> temp_mgr = TempFileManager()
            >>> temp_mgr.create_temp_file()
            >>> temp_mgr.create_temp_directory()
            >>> stats = temp_mgr.cleanup_all()
            >>> print(f"Cleaned up {stats['files_cleaned']} files")
        """
        files_cleaned = 0
        files_failed = 0
        dirs_cleaned = 0
        dirs_failed = 0

        # Clean up files
        for file_path in self.temp_files.copy():  # Copy to avoid modification during iteration
            if self.cleanup_file(file_path):
                files_cleaned += 1
            else:
                files_failed += 1

        # Clean up directories
        for dir_path in self.temp_directories.copy():  # Copy to avoid modification during iteration
            if self.cleanup_directory(dir_path):
                dirs_cleaned += 1
            else:
                dirs_failed += 1

        stats = {
            "files_cleaned": files_cleaned,
            "files_failed": files_failed,
            "directories_cleaned": dirs_cleaned,
            "directories_failed": dirs_failed
        }

        logger.info(
            "Cleanup completed: %d files, %d directories cleaned; %d files, %d directories failed",
            files_cleaned, dirs_cleaned, files_failed, dirs_failed
        )

        return stats

    def get_managed_paths(self) -> dict[str, list[str]]:
        """
        Get all paths currently managed by this instance.

        Returns:
            Dictionary with lists of managed files and directories

        Example:
            >>> temp_mgr = TempFileManager()
            >>> temp_mgr.create_temp_file()
            >>> paths = temp_mgr.get_managed_paths()
            >>> print(f"Managing {len(paths['files'])} files")
        """
        return {
            "files": self.temp_files.copy(),
            "directories": self.temp_directories.copy()
        }

    def has_managed_paths(self) -> bool:
        """
        Check if this manager has any temporary paths.

        Returns:
            True if managing any files or directories, False otherwise

        Example:
            >>> temp_mgr = TempFileManager()
            >>> temp_mgr.has_managed_paths()
            False
            >>> temp_mgr.create_temp_file()
            >>> temp_mgr.has_managed_paths()
            True
        """
        return len(self.temp_files) > 0 or len(self.temp_directories) > 0


@contextmanager
def temp_file(content: str = "", suffix: str = "", encoding: str = "utf-8"):
    """
    Context manager for creating a single temporary file.

    This is a convenience function for creating a single temporary file
    with automatic cleanup.

    Args:
        content: Content to write to the file
        suffix: File suffix
        encoding: Text encoding

    Yields:
        Path to the temporary file

    Example:
        >>> with temp_file("print('hello')", suffix=".py") as script_path:
        ...     print(f"Script at: {script_path}")
        ...     # File is automatically cleaned up when exiting
    """
    with TempFileManager() as temp_mgr:
        file_path = temp_mgr.create_temp_file(content, suffix=suffix, encoding=encoding)
        yield file_path


@contextmanager
def temp_directory(prefix: str = "biocage_"):
    """
    Context manager for creating a single temporary directory.

    This is a convenience function for creating a single temporary directory
    with automatic cleanup.

    Args:
        prefix: Directory prefix

    Yields:
        Path to the temporary directory

    Example:
        >>> with temp_directory() as temp_dir:
        ...     print(f"Temp dir: {temp_dir}")
        ...     # Directory is automatically cleaned up when exiting
    """
    with TempFileManager() as temp_mgr:
        dir_path = temp_mgr.create_temp_directory(prefix=prefix)
        yield dir_path
