"""
Path management for BioCage container filesystem operations.

This module handles the exposure of host filesystem paths to containers,
managing path validation, mount operations, and ensuring secure access
to directories and files within the sandboxed environment.

The PathManager class provides:
- Safe path validation and normalization
- Host path to container path mapping
- Volume mount string generation for Docker
- Path existence and accessibility checks
- Security validation for exposed paths

Example:
    >>> manager = PathManager()
    >>> mount_path = manager.expose_path("/home/user/data", "/app/data")
    >>> mounts = manager.get_volume_mounts()
    >>> print(f"Mounts: {mounts}")
"""

import logging
from pathlib import Path
from typing import Optional

from ..constants import DEFAULT_CONTAINER_WORKSPACE
from ..validation import validate_path

logger = logging.getLogger(__name__)


class PathExposureError(Exception):
    """
    Exception raised when path exposure operations fail.

    This exception is raised when there are issues with exposing host
    paths to the container, such as invalid paths, permission issues,
    or security violations.

    Attributes:
        host_path: The host path that failed to be exposed
        container_path: The intended container path
        error_message: Detailed error message
    """

    def __init__(self, host_path: str, container_path: str, error_message: str) -> None:
        """
        Initialize a path exposure error.

        Args:
            host_path: Host filesystem path that failed
            container_path: Container path that was attempted
            error_message: Detailed error message
        """
        super().__init__(f"Failed to expose '{host_path}' to '{container_path}': {error_message}")
        self.host_path = host_path
        self.container_path = container_path
        self.error_message = error_message


class PathManager:
    """
    Manages filesystem path exposure to Docker containers.

    This class handles the secure exposure of host filesystem paths to
    containers, ensuring proper validation, mapping, and mount generation
    for Docker volume operations.

    The manager tracks exposed paths and generates the necessary Docker
    volume mount strings for container creation, while enforcing security
    constraints on which paths can be exposed.

    Attributes:
        exposed_paths: Dictionary mapping container paths to host paths
        workspace_path: Default workspace path in the container

    Example:
        >>> manager = PathManager()
        >>> manager.expose_path("/home/user/project", "/app/project", readonly=True)
        >>> manager.expose_directory("/tmp/data", "/app/data")
        >>>
        >>> # Get volume mounts for Docker
        >>> mounts = manager.get_volume_mounts()
        >>> print(f"Volume mounts: {mounts}")
        >>>
        >>> # Check if path is exposed
        >>> if manager.is_path_exposed("/app/project"):
        ...     print("Project directory is available in container")
    """

    def __init__(self, workspace_path: str = DEFAULT_CONTAINER_WORKSPACE) -> None:
        """
        Initialize the path manager.

        Args:
            workspace_path: Default workspace path inside the container

        Example:
            >>> manager = PathManager("/app/workspace")
            >>> manager.workspace_path
            '/app/workspace'
        """
        self.workspace_path = workspace_path
        self.exposed_paths: dict[str, dict[str, str]] = {}
        logger.debug("Initialized PathManager with workspace: %s", workspace_path)

    def expose_path(
        self,
        host_path: str,
        container_path: Optional[str] = None,
        readonly: bool = False,
        create_if_missing: bool = False
    ) -> str:
        """
        Expose a host path to the container at the specified location.

        This method validates the host path, ensures it's safe to expose,
        and maps it to a container path. It handles both files and directories
        with appropriate security checks.

        Args:
            host_path: Path on the host filesystem to expose
            container_path: Target path inside the container (auto-generated if None)
            readonly: Whether to mount the path as read-only
            create_if_missing: Create the host path if it doesn't exist

        Returns:
            The container path where the host path is exposed

        Raises:
            PathExposureError: If path exposure fails
            ValueError: If paths are invalid
            FileNotFoundError: If host path doesn't exist and create_if_missing is False

        Example:
            >>> manager = PathManager()
            >>> container_path = manager.expose_path(
            ...     "/home/user/data",
            ...     "/app/input",
            ...     readonly=True
            ... )
            >>> print(f"Data available at: {container_path}")
            Data available at: /app/input
        """
        # Validate and normalize host path
        host_path_obj = Path(host_path).resolve()
        host_path_str = str(host_path_obj)

        validate_path(host_path_str)

        # Generate container path if not provided
        if container_path is None:
            container_path = f"{self.workspace_path}/{host_path_obj.name}"

        # Validate container path
        if not container_path.startswith('/'):
            raise ValueError(f"Container path must be absolute: {container_path}")

        # Check if host path exists
        if not host_path_obj.exists():
            if create_if_missing:
                try:
                    if self._looks_like_file(host_path_str):
                        host_path_obj.parent.mkdir(parents=True, exist_ok=True)
                        host_path_obj.touch()
                    else:
                        host_path_obj.mkdir(parents=True, exist_ok=True)
                    logger.info("Created missing path: %s", host_path_str)
                except OSError as e:
                    raise PathExposureError(
                        host_path_str,
                        container_path,
                        f"Failed to create path: {e}"
                    ) from e
            else:
                raise FileNotFoundError(f"Host path does not exist: {host_path_str}")

        # Security checks
        if not self._is_safe_to_expose(host_path_str):
            raise PathExposureError(
                host_path_str,
                container_path,
                "Path failed security validation"
            )

        # Check if container path is already exposed
        if container_path in self.exposed_paths:
            existing_host = self.exposed_paths[container_path]["host_path"]
            if existing_host != host_path_str:
                logger.warning(
                    "Container path %s already exposed to %s, replacing with %s",
                    container_path,
                    existing_host,
                    host_path_str
                )

        # Store the mapping
        self.exposed_paths[container_path] = {
            "host_path": host_path_str,
            "readonly": readonly,
            "type": "file" if host_path_obj.is_file() else "directory"
        }

        logger.info(
            "Exposed %s '%s' to container path '%s' (readonly=%s)",
            "file" if host_path_obj.is_file() else "directory",
            host_path_str,
            container_path,
            readonly
        )

        return container_path

    def expose_directory(
        self,
        host_dir: str,
        container_dir: Optional[str] = None,
        readonly: bool = False,
        create_if_missing: bool = True
    ) -> str:
        """
        Expose a host directory to the container.

        This is a convenience method specifically for directories that
        ensures the path is treated as a directory and provides directory-
        specific defaults.

        Args:
            host_dir: Directory on the host filesystem
            container_dir: Target directory inside the container
            readonly: Whether to mount as read-only
            create_if_missing: Create directory if it doesn't exist

        Returns:
            The container directory path

        Raises:
            PathExposureError: If directory exposure fails
            ValueError: If the host path exists but is not a directory

        Example:
            >>> manager = PathManager()
            >>> container_dir = manager.expose_directory(
            ...     "/home/user/workspace",
            ...     "/app/workspace"
            ... )
            >>> print(f"Workspace: {container_dir}")
        """
        host_path = Path(host_dir).resolve()

        # Ensure it's a directory if it exists
        if host_path.exists() and not host_path.is_dir():
            raise ValueError(f"Host path exists but is not a directory: {host_dir}")

        return self.expose_path(
            str(host_path),
            container_dir,
            readonly=readonly,
            create_if_missing=create_if_missing
        )

    def expose_file(
        self,
        host_file: str,
        container_file: Optional[str] = None,
        readonly: bool = True,
        create_if_missing: bool = False
    ) -> str:
        """
        Expose a host file to the container.

        This is a convenience method specifically for files that provides
        file-appropriate defaults (readonly=True, create_if_missing=False).

        Args:
            host_file: File on the host filesystem
            container_file: Target file path inside the container
            readonly: Whether to mount as read-only (default True for files)
            create_if_missing: Create file if it doesn't exist

        Returns:
            The container file path

        Raises:
            PathExposureError: If file exposure fails
            ValueError: If the host path exists but is not a file

        Example:
            >>> manager = PathManager()
            >>> container_file = manager.expose_file(
            ...     "/home/user/config.json",
            ...     "/app/config.json"
            ... )
            >>> print(f"Config file: {container_file}")
        """
        host_path = Path(host_file).resolve()

        # Ensure it's a file if it exists
        if host_path.exists() and not host_path.is_file():
            raise ValueError(f"Host path exists but is not a file: {host_file}")

        return self.expose_path(
            str(host_path),
            container_file,
            readonly=readonly,
            create_if_missing=create_if_missing
        )

    def remove_exposed_path(self, container_path: str) -> bool:
        """
        Remove a previously exposed path mapping.

        Args:
            container_path: Container path to remove

        Returns:
            True if path was removed, False if it wasn't exposed

        Example:
            >>> manager = PathManager()
            >>> manager.expose_path("/tmp/data", "/app/data")
            >>> removed = manager.remove_exposed_path("/app/data")
            >>> print(f"Removed: {removed}")
        """
        if container_path in self.exposed_paths:
            removed = self.exposed_paths.pop(container_path)
            logger.info("Removed exposed path: %s -> %s", container_path, removed["host_path"])
            return True
        return False

    def get_volume_mounts(self) -> list[str]:
        """
        Generate Docker volume mount strings for all exposed paths.

        Returns:
            List of volume mount strings in Docker format (host:container:mode)

        Example:
            >>> manager = PathManager()
            >>> manager.expose_path("/tmp/data", "/app/data", readonly=True)
            >>> mounts = manager.get_volume_mounts()
            >>> print(mounts)
            ['/tmp/data:/app/data:ro']
        """
        mounts = []
        for container_path, info in self.exposed_paths.items():
            host_path = info["host_path"]
            mode = "ro" if info["readonly"] else "rw"
            mount_str = f"{host_path}:{container_path}:{mode}"
            mounts.append(mount_str)

        logger.debug("Generated %d volume mounts", len(mounts))
        return mounts

    def is_path_exposed(self, container_path: str) -> bool:
        """
        Check if a container path is currently exposed.

        Args:
            container_path: Path to check inside the container

        Returns:
            True if the path is exposed, False otherwise

        Example:
            >>> manager = PathManager()
            >>> manager.expose_path("/tmp/data", "/app/data")
            >>> manager.is_path_exposed("/app/data")
            True
        """
        return container_path in self.exposed_paths

    def get_host_path(self, container_path: str) -> Optional[str]:
        """
        Get the host path for a given container path.

        Args:
            container_path: Container path to lookup

        Returns:
            Host path if exposed, None otherwise

        Example:
            >>> manager = PathManager()
            >>> manager.expose_path("/tmp/data", "/app/data")
            >>> host_path = manager.get_host_path("/app/data")
            >>> print(host_path)
            /tmp/data
        """
        if container_path in self.exposed_paths:
            return self.exposed_paths[container_path]["host_path"]
        return None

    def get_exposed_paths_info(self) -> dict[str, dict[str, str]]:
        """
        Get detailed information about all exposed paths.

        Returns:
            Dictionary with container paths as keys and path info as values

        Example:
            >>> manager = PathManager()
            >>> manager.expose_path("/tmp/data", "/app/data", readonly=True)
            >>> info = manager.get_exposed_paths_info()
            >>> print(info["/app/data"]["readonly"])
            True
        """
        return self.exposed_paths.copy()

    def clear_exposed_paths(self) -> int:
        """
        Remove all exposed path mappings.

        Returns:
            Number of paths that were cleared

        Example:
            >>> manager = PathManager()
            >>> manager.expose_path("/tmp/data", "/app/data")
            >>> count = manager.clear_exposed_paths()
            >>> print(f"Cleared {count} exposed paths")
        """
        count = len(self.exposed_paths)
        self.exposed_paths.clear()
        logger.info("Cleared %d exposed paths", count)
        return count

    def _is_safe_to_expose(self, host_path: str) -> bool:
        """
        Validate that a host path is safe to expose to the container.

        Args:
            host_path: Host path to validate

        Returns:
            True if safe to expose, False otherwise
        """
        path_obj = Path(host_path).resolve()

        # Disallow system critical directories
        forbidden_paths = [
            "/etc",
            "/usr/bin",
            "/usr/sbin",
            "/bin",
            "/sbin",
            "/boot",
            "/dev",
            "/proc",
            "/sys",
            "/var/lib/docker",
        ]

        path_str = str(path_obj)
        for forbidden in forbidden_paths:
            if path_str.startswith(forbidden):
                logger.warning("Blocked attempt to expose system path: %s", path_str)
                return False

        # Check if path is readable
        try:
            if path_obj.exists():
                # Test read access
                if path_obj.is_file():
                    with open(path_obj, 'rb') as f:
                        f.read(1)  # Try to read one byte
                elif path_obj.is_dir():
                    list(path_obj.iterdir())  # Try to list directory
        except (PermissionError, OSError) as e:
            logger.warning("Path not accessible: %s (%s)", path_str, e)
            return False

        return True

    def _looks_like_file(self, path: str) -> bool:
        """
        Heuristic to determine if a path looks like a file.

        Args:
            path: Path to analyze

        Returns:
            True if it looks like a file, False if it looks like a directory
        """
        path_obj = Path(path)
        # If it has a suffix, likely a file
        if path_obj.suffix:
            return True
        # If the name contains a dot but no slash after it, likely a file
        if '.' in path_obj.name and not path.endswith('/'):
            return True
        return False
