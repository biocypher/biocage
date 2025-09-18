#!/usr/bin/env python3
"""
Debug script for smart dependency detection.
"""

import sys
import os

# Add the biocage module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from biocage.intelligence import SmartImageManager


def debug_smart_image_manager():
    """Debug the smart image manager."""
    print("Debugging SmartImageManager...")

    # Test with matplotlib code
    code = """
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)
plt.plot(x, y)
plt.savefig('/app/workspace/test.png')
print('Plot created')
"""

    manager = SmartImageManager()

    # Step 1: Analyze dependencies
    from biocage.intelligence import DependencyAnalyzer

    analyzer = DependencyAnalyzer()
    deps = analyzer.analyze_code_dependencies(code)
    print(f"Detected dependencies: {deps}")

    # Step 2: Generate image name
    from biocage.intelligence import DockerfileGenerator

    generator = DockerfileGenerator()
    image_name = generator.generate_image_name(deps)
    print(f"Generated image name: {image_name}")

    # Step 3: Generate Dockerfile
    dockerfile = generator.generate_dockerfile(deps)
    print(f"Generated Dockerfile:\n{dockerfile}")

    # Step 4: Check if we would use this image
    final_image = manager.get_or_create_image(code)
    print(f"Final image name: {final_image}")

    # Check cache
    cache_info = manager.get_cache_info()
    print(f"Cache info: {cache_info}")

    # Clean up
    manager.clear_cache()


if __name__ == "__main__":
    debug_smart_image_manager()
