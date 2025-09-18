"""
Dockerfile generator for dynamic image creation.

This module generates Dockerfiles with detected dependencies,
maintaining security and performance characteristics.
"""

import hashlib
import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)


class DockerfileGenerator:
    """
    Generates Dockerfiles with dynamic dependencies.

    This class creates Dockerfile content that includes the detected
    dependencies while maintaining BioCage's security model.
    """

    def __init__(self, base_image: str = "python:3.11-slim"):
        """
        Initialize the Dockerfile generator.

        Args:
            base_image: Base Docker image to use
        """
        self.base_image = base_image

    def generate_dockerfile(self, dependencies: Dict[str, str]) -> str:
        """
        Generate a Dockerfile with the specified dependencies.

        Args:
            dependencies: Dictionary of package names to versions

        Returns:
            Dockerfile content as string

        Example:
            >>> generator = DockerfileGenerator()
            >>> dockerfile = generator.generate_dockerfile({'pandas': 'latest'})
            >>> print(dockerfile)
            # Generated Dockerfile content...
        """
        # Generate dependency installation commands
        install_commands = self._generate_install_commands(dependencies)

        # Generate Dockerfile content
        dockerfile_content = f"""# Auto-generated Dockerfile for BioCage
FROM {self.base_image}

# Set environment variables for better Python behavior
ENV PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    UV_CACHE_DIR=/tmp/uv-cache \\
    UV_PYTHON_DOWNLOADS=never

# Create a non-root user for security
RUN groupadd -r sandbox && useradd -r -g sandbox -d /app -s /bin/bash sandbox

# Install UV package manager
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Install dependencies using UV (much faster than pip)
{install_commands}

# Copy the execution script
COPY execute.py ./

# Create directories for code execution
RUN mkdir -p /app/workspace /app/output && \\
    chown -R sandbox:sandbox /app

# Switch to non-root user
USER sandbox

# Set the default command
CMD ["python", "execute.py"]
"""
        return dockerfile_content

    def _generate_install_commands(self, dependencies: Dict[str, str]) -> str:
        """Generate UV install commands for dependencies."""
        if not dependencies:
            return "# No additional dependencies to install"

        # Generate requirements.txt content
        requirements_lines = []
        for package, version in dependencies.items():
            if version == "latest":
                requirements_lines.append(f"{package}")
            else:
                requirements_lines.append(f"{package}=={version}")

        requirements_content = "\\n".join(requirements_lines)

        return f"""# Create requirements.txt with detected dependencies
RUN echo '{requirements_content}' > requirements.txt

# Install dependencies using UV
RUN uv pip install --system --no-cache -r requirements.txt && \\
    rm requirements.txt"""

    def generate_image_name(self, dependencies: Dict[str, str]) -> str:
        """
        Generate a unique image name based on dependencies.

        Args:
            dependencies: Dictionary of package names to versions

        Returns:
            Unique image name
        """
        # Create a fingerprint of dependencies
        fingerprint = self._create_dependency_fingerprint(dependencies)
        return f"biocage-auto:{fingerprint}"

    def _create_dependency_fingerprint(self, dependencies: Dict[str, str]) -> str:
        """Create a unique fingerprint from dependencies."""
        # Sort dependencies for consistent fingerprinting
        sorted_deps = sorted(dependencies.items())

        # Create fingerprint string
        fingerprint_str = "|".join([f"{pkg}:{ver}" for pkg, ver in sorted_deps])

        # Generate hash
        hash_obj = hashlib.sha256(fingerprint_str.encode())
        return hash_obj.hexdigest()[:12]  # Use first 12 characters

    def generate_build_context(self, dependencies: Dict[str, str], execute_script_path: str = None) -> Dict[str, str]:
        """
        Generate build context files.

        Args:
            dependencies: Dictionary of package names to versions
            execute_script_path: Path to execute.py script

        Returns:
            Dictionary mapping filenames to content
        """
        context = {"Dockerfile": self.generate_dockerfile(dependencies)}

        # Copy execute.py if provided
        if execute_script_path and os.path.exists(execute_script_path):
            with open(execute_script_path, "r") as f:
                context["execute.py"] = f.read()

        return context

    def validate_dependencies(self, dependencies: Dict[str, str]) -> List[str]:
        """
        Validate dependencies for security and compatibility.

        Args:
            dependencies: Dictionary of package names to versions

        Returns:
            List of validation warnings/errors
        """
        warnings = []

        # Check for potentially dangerous packages
        dangerous_packages = {
            "subprocess",
            "os",
            "sys",
            "shutil",
            "glob",
            "tempfile",
            "socket",
            "urllib",
            "requests",
            "http",
            "ftplib",
            "smtplib",
        }

        for package in dependencies.keys():
            if package in dangerous_packages:
                warnings.append(f"Package '{package}' may pose security risks in sandboxed environment")

        # Check for version constraints
        for package, version in dependencies.items():
            if version != "latest" and not self._is_valid_version(version):
                warnings.append(f"Invalid version format for {package}: {version}")

        return warnings

    def _is_valid_version(self, version: str) -> bool:
        """Check if version string is valid."""
        # Simple validation - could be enhanced with proper version parsing
        import re

        version_pattern = r"^\d+(\.\d+)*([a-zA-Z0-9]+)?$"
        return bool(re.match(version_pattern, version)) or version == "latest"
