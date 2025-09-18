"""
Docker image management for BioCage.

This module handles checking for image existence, building images, and managing
image versioning for the BioCage sandbox environment. It provides a clean
interface for all image-related operations with proper error handling.

The ImageManager class abstracts Docker image operations and provides:
- Image existence checking with caching
- Automated image building when needed
- Image management and cleanup utilities
- Build process monitoring and logging

Example:
    >>> manager = ImageManager("biocage:latest")
    >>> manager.ensure_image_exists()  # Builds if needed
    >>> if manager.image_exists():
    ...     print("Image is ready for use")
"""

import logging
from pathlib import Path
from typing import Optional

from ..constants import DEFAULT_IMAGE_NAME, LOG_BUILDING_IMAGE, LOG_IMAGE_BUILT, LOG_IMAGE_NOT_FOUND
from .docker_client import DockerClient, DockerCommandError

logger = logging.getLogger(__name__)


class ImageBuildError(Exception):
    """
    Exception raised when image building fails.

    This exception provides detailed information about build failures
    including the build directory, image name, and error details.

    Attributes:
        image_name: The name of the image that failed to build
        build_dir: The directory where the build was attempted
        error_message: Detailed error message from the build process
    """

    def __init__(self, image_name: str, build_dir: str, error_message: str) -> None:
        """
        Initialize an image build error.

        Args:
            image_name: Name of the image that failed to build
            build_dir: Directory where build was attempted
            error_message: Detailed error message
        """
        super().__init__(f"Failed to build image '{image_name}' in '{build_dir}': {error_message}")
        self.image_name = image_name
        self.build_dir = build_dir
        self.error_message = error_message


class ImageManager:
    """
    Manages Docker images for BioCage sandbox operations.

    This class provides a high-level interface for managing Docker images
    including checking existence, building when needed, and handling
    image lifecycle operations.

    The manager caches image existence checks to avoid repeated Docker
    calls and provides detailed logging for all operations.

    Attributes:
        image_name: Name of the managed Docker image
        docker_client: Docker client for executing commands

    Example:
        >>> manager = ImageManager("biocage:latest")
        >>> manager.ensure_image_exists()
        >>>
        >>> # Check if image exists
        >>> if manager.image_exists():
        ...     print("Image is available")
        >>>
        >>> # Build image manually
        >>> manager.build_image("./docker")
    """

    def __init__(self, image_name: str = DEFAULT_IMAGE_NAME) -> None:
        """
        Initialize the image manager.

        Args:
            image_name: Name of the Docker image to manage

        Example:
            >>> manager = ImageManager("biocage:latest")
            >>> manager.image_name
            'biocage:latest'
        """
        self.image_name = image_name
        self.docker_client = DockerClient()
        self._image_exists_cache: Optional[bool] = None

    def image_exists(self, use_cache: bool = True) -> bool:
        """
        Check if the managed image exists locally.

        This method checks for image existence and optionally caches
        the result to avoid repeated Docker calls.

        Args:
            use_cache: Whether to use cached result if available

        Returns:
            True if image exists locally, False otherwise

        Example:
            >>> manager = ImageManager("python:3.11")
            >>> if manager.image_exists():
            ...     print("Python image is available")
            ... else:
            ...     print("Need to pull Python image")
        """
        if use_cache and self._image_exists_cache is not None:
            return self._image_exists_cache

        try:
            images = self.docker_client.list_images(self.image_name)
            exists = len(images) > 0
            self._image_exists_cache = exists

            logger.debug("Image %s exists: %s", self.image_name, exists)
            return exists

        except DockerCommandError as e:
            logger.exception("Failed to check image existence: %s", e)
            return False

    def ensure_image_exists(self, build_dir: str = ".") -> None:
        """
        Ensure the image exists, building it if necessary.

        This method checks if the image exists and automatically builds
        it if not found. This is the primary method for ensuring image
        availability before container operations.

        Args:
            build_dir: Directory containing Dockerfile for building

        Raises:
            ImageBuildError: If image building fails
            DockerCommandError: If Docker operations fail

        Example:
            >>> manager = ImageManager("biocage:latest")
            >>> manager.ensure_image_exists("./docker")
            >>> # Image is now guaranteed to exist (or exception raised)
        """
        if not self.docker_client.is_docker_available():
            raise DockerCommandError(
                "Docker is not available",
                ["docker"],
                1,
                "Docker daemon not running or not installed"
            )

        if self.image_exists():
            logger.debug("Image %s already exists", self.image_name)
            return

        logger.info(LOG_IMAGE_NOT_FOUND, self.image_name)
        self.build_image(build_dir)

    def build_image(self, build_dir: str = ".", force_rebuild: bool = False) -> None:
        """
        Build the Docker image from a Dockerfile.

        This method builds the image using the Dockerfile in the specified
        directory. It provides detailed logging and error handling for
        the build process.

        Args:
            build_dir: Directory containing the Dockerfile
            force_rebuild: Force rebuild even if image exists

        Raises:
            ImageBuildError: If the build process fails
            FileNotFoundError: If build directory or Dockerfile not found

        Example:
            >>> manager = ImageManager("biocage:latest")
            >>> manager.build_image("./docker", force_rebuild=True)
            >>> print("Image built successfully")
        """
        build_path = Path(build_dir).resolve()

        if not build_path.exists():
            raise FileNotFoundError(f"Build directory does not exist: {build_path}")

        dockerfile_path = build_path / "Dockerfile"
        if not dockerfile_path.exists():
            raise FileNotFoundError(f"Dockerfile not found in: {build_path}")

        if not force_rebuild and self.image_exists():
            logger.info("Image %s already exists, skipping build", self.image_name)
            return

        logger.info(LOG_BUILDING_IMAGE)

        try:
            build_command = ["docker", "build", "-t", self.image_name, str(build_path)]
            result = self.docker_client.run_command(build_command, timeout=600)  # 10 minute timeout

            # Invalidate cache since we just built the image
            self._image_exists_cache = True

            logger.info(LOG_IMAGE_BUILT)
            logger.debug("Build output: %s", result.stdout[-500:])  # Log last 500 chars

        except DockerCommandError as e:
            error_msg = f"Docker build failed: {e.stderr}"
            logger.exception("Image build failed: %s", error_msg)
            raise ImageBuildError(self.image_name, str(build_path), error_msg) from e

    def remove_image(self, force: bool = False) -> bool:
        """
        Remove the managed image from local storage.

        Args:
            force: Force removal even if containers are using the image

        Returns:
            True if image was removed successfully, False otherwise

        Example:
            >>> manager = ImageManager("old_image:latest")
            >>> if manager.remove_image():
            ...     print("Image removed successfully")
        """
        if not self.image_exists():
            logger.debug("Image %s does not exist, nothing to remove", self.image_name)
            return True

        try:
            command = ["docker", "rmi"]
            if force:
                command.append("-f")
            command.append(self.image_name)

            self.docker_client.run_command(command)

            # Invalidate cache
            self._image_exists_cache = False

            logger.info("Removed image: %s", self.image_name)
            return True

        except DockerCommandError as e:
            logger.warning("Failed to remove image %s: %s", self.image_name, e)
            return False

    def get_image_info(self) -> dict[str, str]:
        """
        Get detailed information about the managed image.

        Returns:
            Dictionary containing image metadata

        Example:
            >>> manager = ImageManager("biocage:latest")
            >>> info = manager.get_image_info()
            >>> print(f"Image ID: {info.get('id', 'N/A')}")
        """
        if not self.image_exists():
            return {"name": self.image_name, "exists": "false"}

        try:
            # Get image inspection data
            command = ["docker", "inspect", self.image_name]
            result = self.docker_client.run_command(command)

            # For now, return basic info - could parse JSON for more details
            return {
                "name": self.image_name,
                "exists": "true",
                "inspect_output_length": str(len(result.stdout))
            }

        except DockerCommandError as e:
            logger.warning("Failed to inspect image %s: %s", self.image_name, e)
            return {"name": self.image_name, "exists": "true", "error": str(e)}

    def list_related_images(self) -> list[str]:
        """
        List all images related to the managed image.

        This method finds images with similar names or tags that might
        be related to the managed image.

        Returns:
            List of related image names

        Example:
            >>> manager = ImageManager("biocage:latest")
            >>> related = manager.list_related_images()
            >>> print(f"Found {len(related)} related images")
        """
        try:
            # Extract base name without tag for searching
            base_name = self.image_name.split(":")[0]
            images = self.docker_client.list_images(base_name)
            return images

        except DockerCommandError as e:
            logger.warning("Failed to list related images: %s", e)
            return []

    def invalidate_cache(self) -> None:
        """
        Invalidate the image existence cache.

        This forces the next image_exists() call to check Docker directly
        rather than using cached results.

        Example:
            >>> manager = ImageManager("biocage:latest")
            >>> manager.invalidate_cache()
            >>> # Next call will check Docker directly
            >>> exists = manager.image_exists()
        """
        self._image_exists_cache = None
        logger.debug("Invalidated image existence cache for %s", self.image_name)
