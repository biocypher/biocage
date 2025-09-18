#!/usr/bin/env python3
"""
Test script for smart dependency detection feature.
"""

import sys
import os

# Add the biocage module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from biocage.intelligence import DependencyAnalyzer, DockerfileGenerator, SmartImageManager


def test_dependency_analyzer():
    """Test the dependency analyzer."""
    print("Testing DependencyAnalyzer...")

    analyzer = DependencyAnalyzer()

    # Test basic imports
    code = """
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import matplotlib.pyplot as plt
"""

    deps = analyzer.analyze_code_dependencies(code)
    print(f"Detected dependencies: {deps}")

    expected = {"pandas", "numpy", "scikit-learn", "matplotlib"}
    detected = set(deps.keys())

    assert expected.issubset(detected), f"Expected: {expected}, Got: {detected}"
    print("✓ Dependency analyzer test passed")


def test_dockerfile_generator():
    """Test the Dockerfile generator."""
    print("\nTesting DockerfileGenerator...")

    generator = DockerfileGenerator()

    dependencies = {"pandas": "latest", "numpy": "latest", "matplotlib": "latest"}

    dockerfile = generator.generate_dockerfile(dependencies)
    print(f"Generated Dockerfile length: {len(dockerfile)} characters")

    # Check if key components are present
    checks = [
        "FROM python:3.11-slim" in dockerfile,
        "pandas" in dockerfile,
        "numpy" in dockerfile,
        "matplotlib" in dockerfile,
        "uv pip install" in dockerfile,
        "USER sandbox" in dockerfile,
    ]

    assert all(checks), f"Missing components in Dockerfile: {checks}"
    print("✓ Dockerfile generator test passed")


def test_image_name_generation():
    """Test image name generation."""
    print("\nTesting image name generation...")

    generator = DockerfileGenerator()

    dependencies1 = {"pandas": "latest", "numpy": "latest"}
    dependencies2 = {"pandas": "latest", "numpy": "latest"}  # Same as above
    dependencies3 = {"pandas": "latest", "matplotlib": "latest"}  # Different

    name1 = generator.generate_image_name(dependencies1)
    name2 = generator.generate_image_name(dependencies2)
    name3 = generator.generate_image_name(dependencies3)

    print(f"Dependencies 1: {dependencies1} -> {name1}")
    print(f"Dependencies 2: {dependencies2} -> {name2}")
    print(f"Dependencies 3: {dependencies3} -> {name3}")

    # Same dependencies should generate same name
    assert name1 == name2, "Same dependencies should generate same name"
    assert name1 != name3, "Different dependencies should generate different names"
    print("✓ Image name generation test passed")


def test_smart_image_manager():
    """Test the smart image manager (without actually building images)."""
    print("\nTesting SmartImageManager...")

    manager = SmartImageManager()

    # Test with no dependencies (should return default image)
    code1 = "print('Hello World')"
    image1 = manager.get_or_create_image(code1)
    print(f"Code: {code1} -> Image: {image1}")

    # Test with dependencies (should generate image name)
    code2 = "import pandas as pd\nimport numpy as np"
    image2 = manager.get_or_create_image(code2)
    print(f"Code: {code2} -> Image: {image2}")

    # Test cache info
    cache_info = manager.get_cache_info()
    print(f"Cache info: {cache_info}")

    # Clean up
    manager.clear_cache()

    assert image1 == "biocage:latest", f"Expected default image, got: {image1}"
    assert image2.startswith("biocage-auto:"), f"Expected auto-generated image, got: {image2}"
    print("✓ Smart image manager test passed")


def main():
    """Run all tests."""
    print("Running Smart Dependency Detection Tests")
    print("=" * 50)

    tests = [test_dependency_analyzer, test_dockerfile_generator, test_image_name_generation, test_smart_image_manager]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")

    print("\n" + "=" * 50)
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
