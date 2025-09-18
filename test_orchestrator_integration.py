#!/usr/bin/env python3
"""
Integration test for BioCage orchestrator with smart dependency detection.
"""

import sys
import os

# Add the biocage module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from biocage import BioCageOrchestrator


def test_basic_code():
    """Test with basic Python code (no dependencies)."""
    print("Testing basic code execution...")

    with BioCageOrchestrator(auto_detect_dependencies=True) as sandbox:
        result = sandbox.run("print('Hello, World!')")

        assert result.success and "Hello, World!" in result.stdout, f"Basic code test failed: {result.stderr}"
        print("✓ Basic code test passed")


def test_pandas_code():
    """Test with pandas dependency."""
    print("\nTesting pandas code execution...")

    with BioCageOrchestrator(auto_detect_dependencies=True) as sandbox:
        code = """
import pandas as pd
import numpy as np

# Create a simple DataFrame
data = {'Name': ['Alice', 'Bob', 'Charlie'],
        'Age': [25, 30, 35],
        'City': ['New York', 'London', 'Paris']}
df = pd.DataFrame(data)
print("DataFrame created successfully:")
print(df)
print(f"Shape: {df.shape}")
"""
        result = sandbox.run(code)

        assert result.success and "DataFrame created successfully" in result.stdout, (
            f"Pandas code test failed: {result.stderr}"
        )
        print("✓ Pandas code test passed")


def test_matplotlib_code():
    """Test with matplotlib dependency."""
    print("\nTesting matplotlib code execution...")

    with BioCageOrchestrator(auto_detect_dependencies=True) as sandbox:
        code = """
import matplotlib.pyplot as plt
import numpy as np

# Create a simple plot
x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(8, 6))
plt.plot(x, y, label='sin(x)')
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.title('Simple Sine Plot')
plt.legend()
plt.grid(True)

# Save plot to file
plt.savefig('/app/workspace/sine_plot.png')
print("Plot saved successfully to /app/workspace/sine_plot.png")
print(f"Plot size: {len(x)} points")
"""
        result = sandbox.run(code)

        assert result.success and "Plot saved successfully" in result.stdout, (
            f"Matplotlib code test failed: {result.stderr}"
        )
        print("✓ Matplotlib code test passed")


def test_mixed_dependencies():
    """Test with multiple dependencies."""
    print("\nTesting mixed dependencies...")

    with BioCageOrchestrator(auto_detect_dependencies=True) as sandbox:
        code = """
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Create sample data
np.random.seed(42)
data = np.random.randn(100, 3)
df = pd.DataFrame(data, columns=['A', 'B', 'C'])

# Calculate statistics
stats = df.describe()
print("Data statistics:")
print(stats)

# Create correlation matrix
corr_matrix = df.corr()
print(f"Correlation matrix shape: {corr_matrix.shape}")
print("Test completed successfully!")
"""
        result = sandbox.run(code)

        assert result.success and "Test completed successfully" in result.stdout, (
            f"Mixed dependencies test failed: {result.stderr}"
        )
        print("✓ Mixed dependencies test passed")


def test_persistent_mode():
    """Test persistent mode with dependency detection."""
    print("\nTesting persistent mode...")

    sandbox = BioCageOrchestrator(execution_mode="persistent", auto_detect_dependencies=True)

    # Start container
    sandbox.start_container()

    try:
        # First execution - should trigger image building
        result1 = sandbox.run("import pandas as pd\ndf = pd.DataFrame({'x': [1, 2, 3]})\nprint('First execution')")

        assert result1.success, f"First execution failed: {result1.stderr}"

        # Second execution - should reuse same container
        result2 = sandbox.run("print('DataFrame shape:', df.shape)")

        assert result2.success and "DataFrame shape:" in result2.stdout, f"Second execution failed: {result2.stderr}"
        print("✓ Persistent mode test passed")

    finally:
        sandbox.cleanup()


def main():
    """Run all integration tests."""
    print("Running BioCage Orchestrator Integration Tests")
    print("=" * 60)

    # Check if Docker is available
    try:
        import subprocess

        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("❌ Docker is not available. Skipping integration tests.")
            return 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ Docker is not available. Skipping integration tests.")
        return 0

    print("✓ Docker is available. Running tests...")

    tests = [test_basic_code, test_pandas_code, test_matplotlib_code, test_mixed_dependencies, test_persistent_mode]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")

    print("\n" + "=" * 60)
    print(f"Integration tests passed: {passed}/{total}")

    if passed == total:
        print("🎉 All integration tests passed!")
        return 0
    else:
        print("❌ Some integration tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
