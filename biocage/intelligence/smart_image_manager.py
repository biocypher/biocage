"""
Smart image manager for dynamic Docker image creation and caching.

This module manages the lifecycle of dynamically generated Docker images,
including building, caching, and cleanup operations.
"""

import hashlib
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional, Set

from ..container.docker_client import DockerClient, DockerCommandError
from .dependency_analyzer import DependencyAnalyzer
from .dockerfile_generator import DockerfileGenerator

logger = logging.getLogger(__name__)


class SmartImageManager:
    """
    Manages dynamic Docker image creation and caching.

    This class coordinates dependency analysis, Dockerfile generation,
    and image building with intelligent caching.
    """

    def __init__(self, cache_ttl: int = 86400):  # 24 hours default
        """
        Initialize the smart image manager.

        Args:
            cache_ttl: Time to live for cached images in seconds
        """
        self.dependency_analyzer = DependencyAnalyzer()
        self.dockerfile_generator = DockerfileGenerator()
        self.docker_client = DockerClient()
        self.cache_ttl = cache_ttl
        self.image_cache: Dict[str, Dict] = {}  # fingerprint -> image_info
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None

    def get_or_create_image(self, code: str) -> str:
        """
        Get or create an image for the given code.

        Args:
            code: Python code to analyze for dependencies

        Returns:
            Docker image name

        Example:
            >>> manager = SmartImageManager()
            >>> image_name = manager.get_or_create_image("import pandas as pd")
            >>> print(image_name)
            biocage-auto:abc123def456
        """
        # Analyze dependencies
        dependencies = self.dependency_analyzer.analyze_code_dependencies(code)

        if not dependencies:
            # No third-party dependencies, use default image
            logger.info("No third-party dependencies detected, using default image")
            return "biocage:latest"

        # Generate dependency fingerprint
        fingerprint = self._create_dependency_fingerprint(dependencies)

        # Check cache
        cached_image = self._get_cached_image(fingerprint)
        if cached_image:
            logger.info("Using cached image: %s", cached_image)
            return cached_image

        # Build new image
        image_name = self._build_image(dependencies, fingerprint)

        # Cache the image
        self._cache_image(fingerprint, image_name, dependencies)

        return image_name

    def _create_dependency_fingerprint(self, dependencies: Dict[str, str]) -> str:
        """Create a unique fingerprint from dependencies."""
        sorted_deps = sorted(dependencies.items())
        fingerprint_str = "|".join([f"{pkg}:{ver}" for pkg, ver in sorted_deps])
        hash_obj = hashlib.sha256(fingerprint_str.encode())
        return hash_obj.hexdigest()[:12]

    def _get_cached_image(self, fingerprint: str) -> Optional[str]:
        """Get cached image if it exists and is not expired."""
        if fingerprint not in self.image_cache:
            return None

        cache_entry = self.image_cache[fingerprint]
        current_time = time.time()

        # Check if cache entry is expired
        if current_time - cache_entry["timestamp"] > self.cache_ttl:
            logger.info("Cache entry expired for fingerprint: %s", fingerprint)
            del self.image_cache[fingerprint]
            return None

        # Check if image still exists
        image_name = cache_entry["image_name"]
        if self._image_exists(image_name):
            return image_name
        else:
            # Remove from cache if image doesn't exist
            del self.image_cache[fingerprint]
            return None

    def _cache_image(self, fingerprint: str, image_name: str, dependencies: Dict[str, str]) -> None:
        """Cache an image with its metadata."""
        self.image_cache[fingerprint] = {
            "image_name": image_name,
            "dependencies": dependencies,
            "timestamp": time.time(),
        }
        logger.info("Cached image: %s with fingerprint: %s", image_name, fingerprint)

    def _build_image(self, dependencies: Dict[str, str], fingerprint: str) -> str:
        """Build a new Docker image with the specified dependencies."""
        # Generate image name
        image_name = self.dockerfile_generator.generate_image_name(dependencies)

        # Validate dependencies
        warnings = self.dockerfile_generator.validate_dependencies(dependencies)
        if warnings:
            logger.warning("Dependency validation warnings: %s", warnings)

        # Create temporary build directory
        build_dir = self._get_temp_dir()

        try:
            # Generate build context
            build_context = self.dockerfile_generator.generate_build_context(
                dependencies, execute_script_path="python_docker/execute.py"
            )

            # Write build files
            for filename, content in build_context.items():
                file_path = Path(build_dir) / filename
                with open(file_path, "w") as f:
                    f.write(content)

            # Build the image
            logger.info("Building image: %s", image_name)
            self._build_docker_image(build_dir, image_name)

            logger.info("Successfully built image: %s", image_name)
            return image_name

        except Exception as e:
            logger.error("Failed to build image %s: %s", image_name, e)
            raise
        finally:
            # Clean up temporary files
            self._cleanup_temp_files(build_dir)

    def _get_temp_dir(self) -> str:
        """Get or create temporary directory for builds."""
        if self._temp_dir is None:
            self._temp_dir = tempfile.TemporaryDirectory()
        return self._temp_dir.name

    def _build_docker_image(self, build_dir: str, image_name: str) -> None:
        """Build Docker image using docker client."""
        build_command = ["docker", "build", "-t", image_name, build_dir]

        try:
            result = self.docker_client.run_command(build_command, timeout=600)  # 10 minutes
            logger.debug("Build output: %s", result.stdout[-500:])  # Log last 500 chars
        except DockerCommandError as e:
            error_msg = f"Docker build failed: {e.stderr}"
            logger.error("Image build failed: %s", error_msg)
            raise RuntimeError(error_msg) from e

    def _cleanup_temp_files(self, build_dir: str) -> None:
        """Clean up temporary build files."""
        try:
            build_path = Path(build_dir)
            if build_path.exists():
                for file in build_path.iterdir():
                    try:
                        file.unlink()
                    except OSError:
                        pass
        except Exception as e:
            logger.warning("Failed to cleanup temp files: %s", e)

    def _image_exists(self, image_name: str) -> bool:
        """Check if a Docker image exists."""
        try:
            images = self.docker_client.list_images(image_name)
            return len(images) > 0
        except DockerCommandError:
            return False

    def cleanup_old_images(self, max_age: int = 604800) -> int:  # 7 days default
        """
        Clean up old cached images.

        Args:
            max_age: Maximum age in seconds for images to keep

        Returns:
            Number of images removed
        """
        current_time = time.time()
        removed_count = 0

        # Find expired cache entries
        expired_fingerprints = []
        for fingerprint, cache_entry in self.image_cache.items():
            if current_time - cache_entry["timestamp"] > max_age:
                expired_fingerprints.append(fingerprint)

        # Remove expired images
        for fingerprint in expired_fingerprints:
            cache_entry = self.image_cache[fingerprint]
            image_name = cache_entry["image_name"]

            try:
                if self._remove_image(image_name):
                    removed_count += 1
                    del self.image_cache[fingerprint]
                    logger.info("Removed expired image: %s", image_name)
            except Exception as e:
                logger.warning("Failed to remove image %s: %s", image_name, e)

        return removed_count

    def _remove_image(self, image_name: str) -> bool:
        """Remove a Docker image."""
        try:
            command = ["docker", "rmi", "-f", image_name]
            self.docker_client.run_command(command)
            return True
        except DockerCommandError:
            return False

    def get_cache_info(self) -> Dict:
        """Get information about the current cache state."""
        current_time = time.time()
        cache_stats = {"total_cached_images": len(self.image_cache), "cache_entries": []}

        for fingerprint, cache_entry in self.image_cache.items():
            age = current_time - cache_entry["timestamp"]
            cache_stats["cache_entries"].append({
                "fingerprint": fingerprint,
                "image_name": cache_entry["image_name"],
                "dependencies": cache_entry["dependencies"],
                "age_seconds": age,
                "age_formatted": self._format_age(age),
            })

        return cache_stats

    def _format_age(self, age_seconds: int) -> str:
        """Format age in human-readable format."""
        if age_seconds < 3600:
            return f"{age_seconds / 60:.1f} minutes"
        elif age_seconds < 86400:
            return f"{age_seconds / 3600:.1f} hours"
        else:
            return f"{age_seconds / 86400:.1f} days"

    def clear_cache(self) -> int:
        """
        Clear all cached images.

        Returns:
            Number of images removed
        """
        removed_count = 0

        for fingerprint in list(self.image_cache.keys()):
            cache_entry = self.image_cache[fingerprint]
            image_name = cache_entry["image_name"]

            try:
                if self._remove_image(image_name):
                    removed_count += 1
            except Exception as e:
                logger.warning("Failed to remove image %s: %s", image_name, e)

        self.image_cache.clear()

        # Clean up temp directory
        if self._temp_dir:
            try:
                self._temp_dir.cleanup()
                self._temp_dir = None
            except Exception as e:
                logger.warning("Failed to cleanup temp directory: %s", e)

        logger.info("Cleared cache, removed %d images", removed_count)
        return removed_count

    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            # Only clean up temp directory, not the cache
            if self._temp_dir:
                try:
                    self._temp_dir.cleanup()
                    self._temp_dir = None
                except Exception:
                    pass  # Ignore errors during cleanup
        except Exception:
            pass  # Ignore errors during cleanup
