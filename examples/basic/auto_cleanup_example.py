#!/usr/bin/env python3
"""
Auto-Cleanup Example for BioCage

This example demonstrates BioCage's automatic cleanup feature for dynamically
created Docker images. By default, BioCage automatically removes dynamically
created images when the sandbox is closed to save disk space.

Run this example to see:
- Default auto-cleanup behavior
- How to disable auto-cleanup for image caching
- Manual cleanup options
- Dynamic image tracking and management
"""

import os
import sys
import subprocess

# Add the biocage module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from biocage import BioCageOrchestrator


def check_docker_images() -> None:
    """Check current Docker images to show cleanup effect."""
    try:
        result = subprocess.run(
            ["docker", "images", "--filter", "reference=biocage-auto:*", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        images = result.stdout.strip().split("\n") if result.stdout.strip() else []
        biocage_auto_images = [img for img in images if img.startswith("biocage-auto:")]
        print(f"🐳 Current biocage-auto images: {len(biocage_auto_images)}")
        for img in biocage_auto_images:
            print(f"   - {img}")
        return biocage_auto_images
    except subprocess.CalledProcessError:
        print("🐳 No biocage-auto images found or Docker not available")
        return []


def test_default_auto_cleanup() -> None:
    """Test default auto-cleanup behavior."""
    print("1. Testing default auto-cleanup behavior...")
    print("-" * 50)

    print("Before execution:")
    initial_images = check_docker_images()

    try:
        with BioCageOrchestrator(auto_detect_dependencies=True) as sandbox:
            # This will create a dynamic image with pandas
            code = """
import pandas as pd
import numpy as np

print("✅ Successfully imported pandas and numpy")
print(f"Pandas version: {pd.__version__}")
print(f"NumPy version: {np.__version__}")
"""
            result = sandbox.run(code)

            if result.success:
                print("✅ Code execution successful!")
                print("Output:", result.stdout.strip())

                # Check created images during execution
                print(f"\nDynamic images created in this session: {len(sandbox._dynamic_images_created)}")
                for image in sandbox._dynamic_images_created:
                    print(f"   - {image}")
            else:
                print("❌ Code execution failed:")
                print(result.stderr)

    except Exception as e:
        print(f"❌ Exception occurred: {e}")

    print("\nAfter context exit (auto-cleanup should have run):")
    final_images = check_docker_images()

    if len(final_images) <= len(initial_images):
        print("✅ Auto-cleanup worked correctly - dynamic images were removed")
    else:
        print("⚠️  Some dynamic images may remain (this could be normal if images were cached)")


def test_disabled_auto_cleanup() -> None:
    """Test with auto-cleanup disabled."""
    print("\n2. Testing with auto-cleanup disabled...")
    print("-" * 50)

    print("Before execution:")
    initial_images = check_docker_images()

    try:
        with BioCageOrchestrator(auto_detect_dependencies=True, auto_cleanup_dynamic_images=False) as sandbox:
            # This will create a dynamic image with matplotlib
            code = """
import matplotlib.pyplot as plt
import numpy as np

print("✅ Successfully imported matplotlib and numpy")
print(f"Matplotlib version: {plt.__version__}")

# Create a simple plot
x = np.linspace(0, 10, 50)
y = np.sin(x)
print(f"Generated {len(x)} data points for plotting")
"""
            result = sandbox.run(code)

            if result.success:
                print("✅ Code execution successful!")
                print("Output:", result.stdout.strip())

                # Check created images during execution
                print(f"\nDynamic images created in this session: {len(sandbox._dynamic_images_created)}")
                for image in sandbox._dynamic_images_created:
                    print(f"   - {image}")
            else:
                print("❌ Code execution failed:")
                print(result.stderr)

    except Exception as e:
        print(f"❌ Exception occurred: {e}")

    print("\nAfter context exit (auto-cleanup was disabled):")
    final_images = check_docker_images()

    if len(final_images) > len(initial_images):
        print("✅ Images preserved as expected - auto-cleanup was disabled")
    else:
        print("ℹ️  No new images found (could be normal if image already existed)")


def test_manual_cleanup() -> None:
    """Test manual cleanup of dynamic images."""
    print("\n3. Testing manual cleanup...")
    print("-" * 50)

    print("Before execution:")
    initial_images = check_docker_images()

    # Create orchestrator without auto-cleanup
    sandbox = BioCageOrchestrator(auto_detect_dependencies=True, auto_cleanup_dynamic_images=False)

    try:
        with sandbox:
            # Create dynamic image with scipy
            code = """
import scipy.stats as stats
import numpy as np

print("✅ Successfully imported scipy and numpy")
print(f"SciPy version: {stats.__version__}")

# Generate some random data
data = np.random.normal(0, 1, 1000)
mean, std = stats.norm.fit(data)
print(f"Fitted normal distribution: mean={mean:.3f}, std={std:.3f}")
"""
            result = sandbox.run(code)

            if result.success:
                print("✅ Code execution successful!")
                print("Output:", result.stdout.strip())

                print(f"\nDynamic images created: {len(sandbox._dynamic_images_created)}")
                for image in sandbox._dynamic_images_created:
                    print(f"   - {image}")
            else:
                print("❌ Code execution failed:")
                print(result.stderr)

    except Exception as e:
        print(f"❌ Exception occurred: {e}")

    print("\nAfter context exit (auto-cleanup disabled, images should remain):")
    intermediate_images = check_docker_images()

    # Now manually cleanup
    print("\nRunning manual cleanup...")
    sandbox.cleanup()

    print("After manual cleanup:")
    final_images = check_docker_images()

    if len(final_images) <= len(initial_images):
        print("✅ Manual cleanup worked correctly")
    else:
        print("ℹ️  Some images may remain (could be from other tests or cached)")


def test_multiple_dynamic_images() -> None:
    """Test multiple dynamic images in one session."""
    print("\n4. Testing multiple dynamic images in one session...")
    print("-" * 50)

    print("Before execution:")
    initial_images = check_docker_images()

    try:
        with BioCageOrchestrator(auto_detect_dependencies=True) as sandbox:
            # First execution - pandas
            print("📊 Executing pandas code...")
            result1 = sandbox.run("""
import pandas as pd
print("✅ Pandas imported successfully")
""")

            if result1.success:
                print(result1.stdout.strip())

            # Second execution - different dependencies
            print("\n🎨 Executing matplotlib code...")
            result2 = sandbox.run("""
import matplotlib.pyplot as plt
print("✅ Matplotlib imported successfully")
""")

            if result2.success:
                print(result2.stdout.strip())

            # Third execution - more dependencies
            print("\n🔬 Executing scipy code...")
            result3 = sandbox.run("""
import scipy.stats as stats
print("✅ SciPy imported successfully")
""")

            if result3.success:
                print(result3.stdout.strip())

            print(f"\nTotal dynamic images created: {len(sandbox._dynamic_images_created)}")
            for image in sandbox._dynamic_images_created:
                print(f"   - {image}")

    except Exception as e:
        print(f"❌ Exception occurred: {e}")

    print("\nAfter context exit (all dynamic images should be cleaned up):")
    final_images = check_docker_images()

    if len(final_images) <= len(initial_images):
        print("✅ All dynamic images cleaned up successfully")
    else:
        print("ℹ️  Some images may remain (could be from caching or other tests)")


def print_summary() -> None:
    """Print summary of demonstrated features."""
    print("\n" + "=" * 60)
    print("Auto-Cleanup Example Completed!")
    print()
    print("Key Features Demonstrated:")
    print("• 🧹 Default auto-cleanup behavior (enabled by default)")
    print("• 💾 Disabling auto-cleanup for image caching")
    print("• 🛠️  Manual cleanup options")
    print("• 📊 Multiple dynamic image management")
    print("• 🐳 Docker image tracking and monitoring")
    print("• ⚡ Efficient disk space management")
    print()
    print("Benefits of Auto-Cleanup:")
    print("• 💾 Saves disk space by removing unused images")
    print("• 🚀 Prevents Docker image bloat")
    print("• 🔄 Automatic resource management")
    print("• 🛡️  Maintains clean development environment")
    print()
    print("When to Disable Auto-Cleanup:")
    print("• 📈 Reusing the same dependencies across multiple sessions")
    print("• ⚡ Performance optimization for repeated workflows")
    print("• 🧪 Development and testing scenarios")
    print("• 🏭 Production environments with predictable workloads")


def main() -> None:
    """Main function to run all auto-cleanup tests."""
    print("BioCage Auto-Cleanup Example")
    print("=" * 60)
    print()

    # Check if Docker is available
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
        print("✅ Docker is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Docker not available - some features may not work as expected")

    print()

    test_default_auto_cleanup()
    test_disabled_auto_cleanup()
    test_manual_cleanup()
    test_multiple_dynamic_images()

    print_summary()


if __name__ == "__main__":
    main()
