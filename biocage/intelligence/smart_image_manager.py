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
            execute_script_path = os.path.join(os.path.dirname(__file__), "..", "..", "python_docker", "execute.py")
            build_context = self.dockerfile_generator.generate_build_context(
                dependencies, execute_script_path=execute_script_path
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

    def cleanup_old_images(self, max_age: int = 604800, policy: str = "age", max_count: Optional[int] = None, 
                          max_size_mb: Optional[int] = None, exclude_patterns: Optional[list[str]] = None) -> dict:
        """
        Clean up cached images based on specified policy.

        Args:
            max_age: Maximum age in seconds for images to keep (age-based policy)
            policy: Cleanup policy - "age", "count", "size", or "combined"
            max_count: Maximum number of images to keep (count-based policy)
            max_size_mb: Maximum total size in MB (size-based policy)
            exclude_patterns: List of image name patterns to exclude from cleanup

        Returns:
            Dictionary with cleanup statistics
        """
        current_time = time.time()
        exclude_patterns = exclude_patterns or []
        
        cleanup_stats = {
            "removed_count": 0,
            "failed_count": 0,
            "space_saved_bytes": 0,
            "total_images_before": len(self.image_cache),
            "total_images_after": 0,
            "policy_used": policy,
            "cleanup_details": []
        }

        try:
            if policy == "age":
                cleanup_stats.update(self._cleanup_by_age(max_age, exclude_patterns))
            elif policy == "count":
                if max_count is None:
                    raise ValueError("max_count must be specified for count-based cleanup")
                cleanup_stats.update(self._cleanup_by_count(max_count, exclude_patterns))
            elif policy == "size":
                if max_size_mb is None:
                    raise ValueError("max_size_mb must be specified for size-based cleanup")
                cleanup_stats.update(self._cleanup_by_size(max_size_mb, exclude_patterns))
            elif policy == "combined":
                cleanup_stats.update(self._cleanup_combined(max_age, max_count, max_size_mb, exclude_patterns))
            else:
                raise ValueError(f"Unknown cleanup policy: {policy}")

            cleanup_stats["total_images_after"] = len(self.image_cache)
            logger.info("Cleanup completed: %s", cleanup_stats)

        except Exception as e:
            logger.exception("Cleanup failed: %s", e)
            cleanup_stats["error"] = str(e)

        return cleanup_stats

    def _cleanup_by_age(self, max_age: int, exclude_patterns: list[str]) -> dict:
        """Clean up images based on age."""
        current_time = time.time()
        removed_count = 0
        failed_count = 0
        space_saved = 0
        cleanup_details = []

        # Find expired cache entries
        expired_fingerprints = []
        for fingerprint, cache_entry in self.image_cache.items():
            if current_time - cache_entry["timestamp"] > max_age:
                image_name = cache_entry["image_name"]
                if not self._should_exclude_image(image_name, exclude_patterns):
                    expired_fingerprints.append((fingerprint, cache_entry))

        # Remove expired images
        for fingerprint, cache_entry in expired_fingerprints:
            image_name = cache_entry["image_name"]
            image_size = self._get_image_size(image_name)
            
            try:
                if self._remove_image_with_cleanup(image_name):
                    removed_count += 1
                    space_saved += image_size
                    del self.image_cache[fingerprint]
                    logger.info("Removed expired image: %s (age: %s)", 
                              image_name, self._format_age(current_time - cache_entry["timestamp"]))
                    cleanup_details.append({
                        "image": image_name,
                        "reason": "age",
                        "age_seconds": current_time - cache_entry["timestamp"],
                        "size_bytes": image_size
                    })
                else:
                    failed_count += 1
                    cleanup_details.append({
                        "image": image_name,
                        "reason": "age",
                        "failed": True,
                        "error": "Removal failed"
                    })
            except Exception as e:
                failed_count += 1
                logger.warning("Failed to remove image %s: %s", image_name, e)
                cleanup_details.append({
                    "image": image_name,
                    "reason": "age",
                    "failed": True,
                    "error": str(e)
                })

        return {
            "removed_count": removed_count,
            "failed_count": failed_count,
            "space_saved_bytes": space_saved,
            "cleanup_details": cleanup_details
        }

    def _cleanup_by_count(self, max_count: int, exclude_patterns: list[str]) -> dict:
        """Clean up images based on count, keeping the most recently used."""
        if len(self.image_cache) <= max_count:
            return {
                "removed_count": 0,
                "failed_count": 0,
                "space_saved_bytes": 0,
                "cleanup_details": []
            }

        # Sort by timestamp (oldest first)
        sorted_images = sorted(
            self.image_cache.items(),
            key=lambda x: x[1]["timestamp"]
        )

        # Calculate how many to remove
        to_remove = len(self.image_cache) - max_count
        removed_count = 0
        failed_count = 0
        space_saved = 0
        cleanup_details = []

        for fingerprint, cache_entry in sorted_images[:to_remove]:
            image_name = cache_entry["image_name"]
            if self._should_exclude_image(image_name, exclude_patterns):
                continue

            image_size = self._get_image_size(image_name)
            
            try:
                if self._remove_image_with_cleanup(image_name):
                    removed_count += 1
                    space_saved += image_size
                    del self.image_cache[fingerprint]
                    logger.info("Removed image by count policy: %s", image_name)
                    cleanup_details.append({
                        "image": image_name,
                        "reason": "count",
                        "size_bytes": image_size
                    })
                else:
                    failed_count += 1
                    cleanup_details.append({
                        "image": image_name,
                        "reason": "count",
                        "failed": True,
                        "error": "Removal failed"
                    })
            except Exception as e:
                failed_count += 1
                logger.warning("Failed to remove image %s: %s", image_name, e)
                cleanup_details.append({
                    "image": image_name,
                    "reason": "count",
                    "failed": True,
                    "error": str(e)
                })

        return {
            "removed_count": removed_count,
            "failed_count": failed_count,
            "space_saved_bytes": space_saved,
            "cleanup_details": cleanup_details
        }

    def _cleanup_by_size(self, max_size_mb: int, exclude_patterns: list[str]) -> dict:
        """Clean up images based on total size, removing oldest first."""
        max_size_bytes = max_size_mb * 1024 * 1024
        
        # Calculate current total size
        current_size = 0
        image_sizes = []
        
        for fingerprint, cache_entry in self.image_cache.items():
            image_name = cache_entry["image_name"]
            image_size = self._get_image_size(image_name)
            current_size += image_size
            image_sizes.append((fingerprint, cache_entry, image_size))

        if current_size <= max_size_bytes:
            return {
                "removed_count": 0,
                "failed_count": 0,
                "space_saved_bytes": 0,
                "cleanup_details": []
            }

        # Sort by timestamp (oldest first) to remove least recently used
        image_sizes.sort(key=lambda x: x[1]["timestamp"])
        
        removed_count = 0
        failed_count = 0
        space_saved = 0
        cleanup_details = []

        for fingerprint, cache_entry, image_size in image_sizes:
            if current_size <= max_size_bytes:
                break

            image_name = cache_entry["image_name"]
            if self._should_exclude_image(image_name, exclude_patterns):
                continue

            try:
                if self._remove_image_with_cleanup(image_name):
                    removed_count += 1
                    space_saved += image_size
                    current_size -= image_size
                    del self.image_cache[fingerprint]
                    logger.info("Removed image by size policy: %s", image_name)
                    cleanup_details.append({
                        "image": image_name,
                        "reason": "size",
                        "size_bytes": image_size
                    })
                else:
                    failed_count += 1
                    cleanup_details.append({
                        "image": image_name,
                        "reason": "size",
                        "failed": True,
                        "error": "Removal failed"
                    })
            except Exception as e:
                failed_count += 1
                logger.warning("Failed to remove image %s: %s", image_name, e)
                cleanup_details.append({
                    "image": image_name,
                    "reason": "size",
                    "failed": True,
                    "error": str(e)
                })

        return {
            "removed_count": removed_count,
            "failed_count": failed_count,
            "space_saved_bytes": space_saved,
            "cleanup_details": cleanup_details
        }

    def _cleanup_combined(self, max_age: int, max_count: Optional[int], max_size_mb: Optional[int], 
                         exclude_patterns: list[str]) -> dict:
        """Clean up images using combined policies."""
        total_removed = 0
        total_failed = 0
        total_space_saved = 0
        all_cleanup_details = []

        # Apply age-based cleanup first
        if max_age > 0:
            age_result = self._cleanup_by_age(max_age, exclude_patterns)
            total_removed += age_result["removed_count"]
            total_failed += age_result["failed_count"]
            total_space_saved += age_result["space_saved_bytes"]
            all_cleanup_details.extend(age_result["cleanup_details"])

        # Apply count-based cleanup if specified
        if max_count is not None:
            count_result = self._cleanup_by_count(max_count, exclude_patterns)
            total_removed += count_result["removed_count"]
            total_failed += count_result["failed_count"]
            total_space_saved += count_result["space_saved_bytes"]
            all_cleanup_details.extend(count_result["cleanup_details"])

        # Apply size-based cleanup if specified
        if max_size_mb is not None:
            size_result = self._cleanup_by_size(max_size_mb, exclude_patterns)
            total_removed += size_result["removed_count"]
            total_failed += size_result["failed_count"]
            total_space_saved += size_result["space_saved_bytes"]
            all_cleanup_details.extend(size_result["cleanup_details"])

        return {
            "removed_count": total_removed,
            "failed_count": total_failed,
            "space_saved_bytes": total_space_saved,
            "cleanup_details": all_cleanup_details
        }

    def _should_exclude_image(self, image_name: str, exclude_patterns: list[str]) -> bool:
        """Check if an image should be excluded from cleanup."""
        for pattern in exclude_patterns:
            if pattern in image_name:
                return True
        return False

    def _get_image_size(self, image_name: str) -> int:
        """Get the size of a Docker image in bytes."""
        try:
            command = ["docker", "images", image_name, "--format", "{{.Size}}"]
            result = self.docker_client.run_command(command)
            
            if result.stdout.strip():
                # Parse size string (e.g., "1.2GB", "500MB", "100KB")
                size_str = result.stdout.strip().upper()
                if "GB" in size_str:
                    return int(float(size_str.replace("GB", "")) * 1024 * 1024 * 1024)
                elif "MB" in size_str:
                    return int(float(size_str.replace("MB", "")) * 1024 * 1024)
                elif "KB" in size_str:
                    return int(float(size_str.replace("KB", "")) * 1024)
                else:
                    return int(size_str)  # Assume bytes
            return 0
        except Exception:
            return 0

    def _remove_image_with_cleanup(self, image_name: str) -> bool:
        """Remove a Docker image with proper cleanup of dependent resources."""
        import time
        
        # First, stop and remove containers using this image
        self._cleanup_containers_using_image(image_name)
        
        # Retry removal logic
        for attempt in range(3):
            try:
                command = ["docker", "rmi", "-f", image_name]
                self.docker_client.run_command(command)
                return True
            except Exception as e:
                if attempt == 2:  # Final attempt
                    logger.warning("Final attempt failed to remove image %s: %s", image_name, e)
                    return False
                
                logger.debug("Attempt %d failed to remove image %s, retrying...: %s", 
                           attempt + 1, image_name, e)
                time.sleep(1)
        
        return False

    def _cleanup_containers_using_image(self, image_name: str) -> None:
        """Stop and remove containers that are using the specified image."""
        try:
            # Find containers using this image
            command = ["docker", "ps", "-a", "--filter", f"ancestor={image_name}", "--format", "{{.ID}}"]
            result = self.docker_client.run_command(command)
            
            container_ids = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            for container_id in container_ids:
                if container_id.strip():
                    try:
                        # Stop container if running
                        stop_command = ["docker", "stop", container_id.strip()]
                        self.docker_client.run_command(stop_command)
                        
                        # Remove container
                        remove_command = ["docker", "rm", "-f", container_id.strip()]
                        self.docker_client.run_command(remove_command)
                        
                        logger.debug("Stopped and removed container %s using image %s", 
                                   container_id.strip()[:12], image_name)
                    except Exception as e:
                        logger.warning("Failed to cleanup container %s: %s", 
                                     container_id.strip()[:12], e)
        except Exception as e:
            logger.warning("Failed to find containers using image %s: %s", image_name, e)

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
