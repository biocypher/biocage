"""
Intelligence module for BioCage - Smart dependency detection and analysis.

This module provides intelligent code analysis capabilities including:
- Automatic dependency detection from Python code
- Dynamic Docker image generation
- Smart caching and optimization

Example:
    >>> from biocage.intelligence import DependencyAnalyzer
    >>> analyzer = DependencyAnalyzer()
    >>> deps = analyzer.analyze_code_dependencies("import pandas as pd")
    >>> print(deps)
    {'pandas': 'latest'}
"""

from .dependency_analyzer import DependencyAnalyzer
from .dockerfile_generator import DockerfileGenerator
from .smart_image_manager import SmartImageManager

__all__ = ["DependencyAnalyzer", "DockerfileGenerator", "SmartImageManager"]
