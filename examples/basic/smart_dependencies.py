#!/usr/bin/env python3
"""
Smart Dependencies Example for BioCage

This example demonstrates BioCage's automatic dependency detection and dynamic
Docker image generation feature. BioCage can automatically detect
third-party library imports and build custom Docker images on-the-fly.

Run this example to see:
- Automatic dependency detection from Python code
- Dynamic Docker image generation with UV package manager
- Intelligent caching for performance optimization
- Seamless integration with existing BioCage workflows
"""

import os
import sys

# Add the biocage module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from biocage import BioCageOrchestrator


def test_pandas_dependency() -> None:
    """Test basic dependency detection with pandas."""
    print("1. Testing pandas dependency detection...")
    print("-" * 40)

    try:
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
print(f"Columns: {list(df.columns)}")
"""
            result = sandbox.run(code)

            if result.success:
                print("✅ Pandas dependency detection successful!")
                print("Output:")
                print(result.stdout)
            else:
                print("❌ Pandas dependency detection failed:")
                print(result.stderr)
    except Exception as e:
        print(f"❌ Exception occurred: {e}")


def test_matplotlib_dependency() -> None:
    """Test matplotlib and visualization dependency detection."""
    print("2. Testing matplotlib dependency detection...")
    print("-" * 40)

    try:
        with BioCageOrchestrator(auto_detect_dependencies=True) as sandbox:
            code = """
import matplotlib.pyplot as plt
import numpy as np

# Create a simple plot
x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(8, 6))
plt.plot(x, y, label='sin(x)', color='blue', linewidth=2)
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.title('Simple Sine Plot')
plt.legend()
plt.grid(True, alpha=0.3)

# Save plot to file
plt.savefig('/app/workspace/sine_plot.png', dpi=150, bbox_inches='tight')
print("✅ Plot saved successfully to /app/workspace/sine_plot.png")
print(f"📊 Plot generated with {len(x)} data points")
print(f"📈 Y range: [{y.min():.2f}, {y.max():.2f}]")
"""
            result = sandbox.run(code)

            if result.success:
                print("✅ Matplotlib dependency detection successful!")
                print("Output:")
                print(result.stdout)
            else:
                print("❌ Matplotlib dependency detection failed:")
                print(result.stderr)
    except Exception as e:
        print(f"❌ Exception occurred: {e}")


def test_multiple_dependencies() -> None:
    """Test multiple complex dependencies."""
    print("3. Testing multiple complex dependencies...")
    print("-" * 40)

    try:
        with BioCageOrchestrator(auto_detect_dependencies=True) as sandbox:
            code = """
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json

# Generate sample data
np.random.seed(42)
n_samples = 1000

data = {
    'temperature': np.random.normal(20, 5, n_samples),
    'humidity': np.random.normal(60, 15, n_samples),
    'pressure': np.random.normal(1013, 20, n_samples)
}

# Create DataFrame
df = pd.DataFrame(data)

# Calculate statistics
stats = df.describe()
print("📊 Data Statistics:")
print(stats)

# Create correlation matrix
corr_matrix = df.corr()
print(f"\\n🔗 Correlation Matrix Shape: {corr_matrix.shape}")

# Create a simple visualization
plt.figure(figsize=(10, 6))
plt.subplot(1, 2, 1)
plt.hist(df['temperature'], bins=30, alpha=0.7, color='skyblue')
plt.title('Temperature Distribution')
plt.xlabel('Temperature (°C)')

plt.subplot(1, 2, 2)
plt.scatter(df['temperature'], df['humidity'], alpha=0.6, color='coral')
plt.xlabel('Temperature (°C)')
plt.ylabel('Humidity (%)')
plt.title('Temperature vs Humidity')

plt.tight_layout()
plt.savefig('/app/workspace/weather_analysis.png', dpi=150, bbox_inches='tight')

# Generate summary report
summary = {
    'total_samples': len(df),
    'temperature_range': [df['temperature'].min(), df['temperature'].max()],
    'humidity_range': [df['humidity'].min(), df['humidity'].max()],
    'pressure_range': [df['pressure'].min(), df['pressure'].max()],
    'plots_generated': ['weather_analysis.png']
}

print(f"\\n📋 Summary Report:")
print(json.dumps(summary, indent=2))
print("✅ Multi-dependency analysis completed successfully!")
"""
            result = sandbox.run(code)

            if result.success:
                print("✅ Multiple dependencies detection successful!")
                print("Output:")
                print(result.stdout)
            else:
                print("❌ Multiple dependencies detection failed:")
                print(result.stderr)
    except Exception as e:
        print(f"❌ Exception occurred: {e}")


def test_persistent_mode() -> None:
    """Test persistent mode with dependency detection."""
    print("4. Testing persistent mode with dependency detection...")
    print("-" * 40)

    try:
        sandbox = BioCageOrchestrator(execution_mode="persistent", auto_detect_dependencies=True)

        sandbox.start_container()

        try:
            # First execution - triggers image building
            print("🔨 First execution (building image with pandas)...")
            result1 = sandbox.run("""
import pandas as pd
import numpy as np

# Create initial data
data = {'x': np.arange(10), 'y': np.random.rand(10)}
df = pd.DataFrame(data)
print("✅ Initial data created with pandas")
""")

            if not result1.success:
                print("❌ First execution failed:")
                print(result1.stderr)
                return

            print(result1.stdout.strip())

            # Second execution - reuses same container and image
            print("🔄 Second execution (reusing container)...")
            result2 = sandbox.run("""
# Use previously created DataFrame
print(f"DataFrame shape: {df.shape}")
print(f"DataFrame columns: {list(df.columns)}")
print(f"X values: {df['x'].tolist()}")
print("✅ Successfully accessed persistent data")
""")

            if result2.success:
                print("✅ Persistent mode with dependency detection successful!")
                print("Output:")
                print(result2.stdout)
            else:
                print("❌ Second execution failed:")
                print(result2.stderr)

        finally:
            sandbox.cleanup()

    except Exception as e:
        print(f"❌ Exception occurred: {e}")


def test_error_handling() -> None:
    """Test error handling with missing dependencies."""
    print("5. Testing error handling with missing dependencies...")
    print("-" * 40)

    try:
        with BioCageOrchestrator(auto_detect_dependencies=True) as sandbox:
            # This should work fine
            result1 = sandbox.run("""
import pandas as pd
print("✅ Pandas imported successfully")
""")

            print("First execution result:")
            if result1.success:
                print(result1.stdout.strip())
            else:
                print(result1.stderr)

            # This should fail gracefully
            result2 = sandbox.run("""
import non_existent_library_12345
print("This should not print")
""")

            print("Second execution result:")
            if not result2.success:
                print("✅ Error handling worked correctly:")
                print(f"Error: {result2.stderr.strip()}")
            else:
                print("❌ Unexpected success with non-existent library")

    except Exception as e:
        print(f"❌ Exception occurred: {e}")


def print_summary() -> None:
    """Print the summary of demonstrated features."""
    print()
    print("=" * 50)
    print("Smart Dependencies Example Completed!")
    print()
    print("Key Features Demonstrated:")
    print("• 🎯 Automatic dependency detection from Python code")
    print("• 🐳 Dynamic Docker image generation")
    print("• ⚡ Fast package installation with UV")
    print("• 🔄 Intelligent image caching")
    print("• 📊 Support for data science libraries")
    print("• 🎨 Visualization library support")
    print("• 💾 Persistent mode compatibility")
    print("• 🛡️ Graceful error handling")
    print()
    print("The smart dependency detection feature eliminates the need")
    print("for manual Docker image management while maintaining security")
    print("and performance!")


def main() -> None:
    """Main function to run all smart dependency tests."""
    print("BioCage Smart Dependencies Example")
    print("=" * 50)
    print()

    test_pandas_dependency()
    print()

    test_matplotlib_dependency()
    print()

    test_multiple_dependencies()
    print()

    test_persistent_mode()
    print()

    test_error_handling()

    print_summary()


if __name__ == "__main__":
    main()
