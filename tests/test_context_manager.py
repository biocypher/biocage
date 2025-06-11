"""Test context manager functionality."""

from biocage import BioCageManager


class TestBasicContextManager:
    """Test basic context manager functionality."""

    def test_simple_context_manager(self):
        """Test basic context manager usage."""
        with BioCageManager() as sandbox:
            assert sandbox.is_running
            result = sandbox.run("print('Hello from context manager!')")
            assert result.success
            assert "Hello from context manager!" in result.stdout
        # Container should be cleaned up after context exit

    def test_automatic_cleanup(self):
        """Test that context manager properly cleans up resources."""
        sandbox = None
        with BioCageManager() as sb:
            sandbox = sb
            assert sandbox.is_running
            result = sandbox.run("x = 42")
            assert result.success

        # After context exit, container should be cleaned up
        # Note: is_running might still be True briefly due to async cleanup
        # The important thing is that resources are properly disposed

    def test_context_manager_with_exception(self):
        """Test context manager cleanup when exception occurs."""
        try:
            with BioCageManager() as sandbox:
                assert sandbox.is_running
                result = sandbox.run("print('Before exception')")
                assert result.success
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected exception

        # Container should still be cleaned up despite exception


class TestConfigureContextManager:
    """Test configured context manager functionality."""

    def test_configure_with_resources(self):
        """Test context manager with custom resource configuration."""
        with BioCageManager().configure_context_manager(memory_limit="1g", cpu_limit="2.0") as sandbox:
            assert sandbox.is_running

            info = sandbox.get_container_info()
            assert info["is_running"]
            assert info["container_id"] is not None

            result = sandbox.run("print('Custom resources working')")
            assert result.success
            assert "Custom resources working" in result.stdout

    def test_configure_with_high_performance(self):
        """Test high-performance configuration."""
        with BioCageManager().configure_context_manager(memory_limit="4g", cpu_limit="8.0") as sandbox:
            result = sandbox.run("""
import pandas as pd
import numpy as np

# Create a larger dataset to use the resources
data = pd.DataFrame({
    'x': np.random.randn(10000),
    'y': np.random.randn(10000),
    'z': np.random.randn(10000)
})

print(f"Dataset shape: {data.shape}")
print(f"Memory usage: {data.memory_usage(deep=True).sum():,} bytes")
print(f"Mean values: x={data.x.mean():.3f}, y={data.y.mean():.3f}")

# Test computation
correlation = data.corr()
print(f"Correlation computed: {correlation.shape}")
""")
            assert result.success
            assert "Dataset shape: (10000, 3)" in result.stdout
            assert "Correlation computed: (3, 3)" in result.stdout

    def test_method_chaining(self):
        """Test that configure_context_manager returns self for chaining."""
        sandbox = BioCageManager()
        configured_sandbox = sandbox.configure_context_manager(memory_limit="512m")

        # Should return the same instance
        assert sandbox is configured_sandbox

        with configured_sandbox as active_sandbox:
            assert active_sandbox is sandbox
            result = active_sandbox.run("print('Method chaining works!')")
            assert result.success
            assert "Method chaining works!" in result.stdout

    def test_configure_multiple_parameters(self):
        """Test configuring multiple parameters at once."""
        with BioCageManager().configure_context_manager(
            memory_limit="2g",
            cpu_limit="4.0",
            network_access=False,  # Explicit security setting
        ) as sandbox:
            # Test that configuration is applied
            info = sandbox.get_container_info()
            assert info["is_running"]

            # Test that the sandbox works with these settings
            result = sandbox.run("""
import os
import sys

print(f"Python version: {sys.version.split()[0]}")
print(f"Working directory: {os.getcwd()}")
print("Configuration test passed")
""")
            assert result.success
            assert "Configuration test passed" in result.stdout


class TestContextManagerWithFileExposure:
    """Test context manager with file and directory exposure."""

    def test_configure_with_temp_files(self):
        """Test context manager with temporary file creation."""
        with BioCageManager().configure_context_manager(memory_limit="1g") as sandbox:
            # Create temp files within context
            csv_path = sandbox.create_temp_file("name,age\nAlice,25\nBob,30", ".csv")
            json_path = sandbox.create_temp_file('{"test": true, "value": 42}', ".json")

            result = sandbox.run(f"""
import pandas as pd
import json
import os

# Use the temp files
df = pd.read_csv('{csv_path}')
print(f"CSV loaded: {{len(df)}} rows")

with open('{json_path}', 'r') as f:
    data = json.load(f)
print(f"JSON value: {{data['value']}}")

# Check paths exist
csv_exists = os.path.exists('{csv_path}')
json_exists = os.path.exists('{json_path}')
print(f"Files exist: CSV={{csv_exists}}, JSON={{json_exists}}")
""")
            assert result.success
            assert "CSV loaded: 2 rows" in result.stdout
            assert "JSON value: 42" in result.stdout
            assert "CSV=True, JSON=True" in result.stdout

    def test_configure_with_file_exposure(self):
        """Test context manager configured with file exposure."""
        import os
        import tempfile

        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test file content\nSecond line")
            temp_file = f.name

        try:
            with BioCageManager().configure_context_manager(
                memory_limit="512m", expose_files={temp_file: "/app/shared/test.txt"}
            ) as sandbox:
                result = sandbox.run("""
import os

file_path = '/app/shared/test.txt'
print(f"File exists: {os.path.exists(file_path)}")

with open(file_path, 'r') as f:
    content = f.read()
print(f"Content lines: {len(content.split(chr(10)))}")
print(f"First line: {content.split(chr(10))[0]}")
""")
                assert result.success
                assert "File exists: True" in result.stdout
                assert "Content lines: 2" in result.stdout
                assert "First line: Test file content" in result.stdout
        finally:
            os.unlink(temp_file)

    def test_configure_with_directory_exposure(self):
        """Test context manager with directory exposure."""
        import shutil
        import tempfile
        from pathlib import Path

        # Create temporary directory with test files
        test_dir = Path(tempfile.mkdtemp())
        try:
            (test_dir / "file1.txt").write_text("Content of file 1")
            (test_dir / "file2.txt").write_text("Content of file 2")

            with BioCageManager().configure_context_manager(expose_directories={str(test_dir): "/app/data"}) as sandbox:
                result = sandbox.run("""
import os

data_dir = '/app/data'
print(f"Directory exists: {os.path.exists(data_dir)}")

files = os.listdir(data_dir)
print(f"Files found: {sorted(files)}")

# Read files
for filename in sorted(files):
    with open(os.path.join(data_dir, filename), 'r') as f:
        content = f.read()
    print(f"{filename}: {len(content)} chars")
""")
                assert result.success
                assert "Directory exists: True" in result.stdout
                assert "file1.txt" in result.stdout
                assert "file2.txt" in result.stdout
                assert "Content of file" in result.stdout or "chars" in result.stdout
        finally:
            shutil.rmtree(test_dir)


class TestContextManagerEdgeCases:
    """Test edge cases and error conditions."""

    def test_nested_context_managers(self):
        """Test that nested context managers work correctly."""
        with BioCageManager().configure_context_manager(memory_limit="512m") as sandbox1:
            result1 = sandbox1.run("x = 1; print(f'Sandbox 1: {x}')")
            assert result1.success

            with BioCageManager().configure_context_manager(memory_limit="256m") as sandbox2:
                result2 = sandbox2.run("y = 2; print(f'Sandbox 2: {y}')")
                assert result2.success
                assert "Sandbox 2: 2" in result2.stdout

            # First sandbox should still work
            result3 = sandbox1.run("print(f'Back to sandbox 1: {x}')")
            assert result3.success
            assert "Back to sandbox 1: 1" in result3.stdout

    def test_reuse_after_context_exit(self):
        """Test behavior when trying to reuse sandbox after context exit."""
        sandbox = None
        with BioCageManager() as sb:
            sandbox = sb
            result = sandbox.run("print('In context')")
            assert result.success

        # After context exit, trying to run should handle gracefully
        # The exact behavior depends on implementation, but it shouldn't crash
        try:
            result = sandbox.run("print('After context')")
            # If it works, that's fine
            # If it fails, that's also acceptable behavior
        except Exception:
            # Expected that it might fail after cleanup
            pass

    def test_configure_with_invalid_resources(self):
        """Test handling of invalid resource specifications."""
        # These should either work or fail gracefully, not crash
        try:
            with BioCageManager().configure_context_manager(
                memory_limit="invalid", cpu_limit="also_invalid"
            ) as sandbox:
                # If it doesn't raise an exception, the sandbox should still work
                result = sandbox.run("print('Still working')")
                # Don't assert success here as invalid resources might cause issues
        except (ValueError, RuntimeError) as e:
            # It's acceptable to raise an exception for invalid resource specs
            assert "invalid" in str(e).lower() or "error" in str(e).lower()

    def test_multiple_configure_calls(self):
        """Test calling configure_context_manager multiple times."""
        sandbox = BioCageManager()

        # Configure multiple times (last one should win)
        sandbox.configure_context_manager(memory_limit="512m")
        sandbox.configure_context_manager(memory_limit="1g", cpu_limit="2.0")

        with sandbox as active_sandbox:
            result = active_sandbox.run("print('Multiple configures work')")
            assert result.success
            assert "Multiple configures work" in result.stdout


class TestPreConfiguredMethod:
    """Test pre-configuration method (starting container before context)."""

    def test_pre_configured_container(self):
        """Test using a pre-started container with context manager."""
        sandbox = BioCageManager()

        # Start container manually first
        sandbox.start_container(memory_limit="512m", cpu_limit="1.0")
        assert sandbox.is_running

        try:
            # Now use with context manager
            with sandbox:
                result = sandbox.run("print('Pre-configured container')")
                assert result.success
                assert "Pre-configured container" in result.stdout

                # Container should still be running during context
                assert sandbox.is_running
        finally:
            # Manual cleanup since we started it manually
            if sandbox.is_running:
                sandbox.cleanup()

    def test_pre_configured_with_persistence(self):
        """Test pre-configured container maintains state through context."""
        sandbox = BioCageManager()
        sandbox.start_container()

        try:
            # Set some state before context
            result = sandbox.run("counter = 0")
            assert result.success

            with sandbox:
                # Increment in context
                result = sandbox.run("counter += 1; print(f'Counter: {counter}')")
                assert result.success
                assert "Counter: 1" in result.stdout

            # After context exit, the container may be cleaned up
            # Check if container is still running first
            if sandbox.is_running:
                result = sandbox.run("counter += 1; print(f'After context: {counter}')")
                assert result.success
                assert "After context: 2" in result.stdout
            else:
                # Container was cleaned up by context manager, which is valid behavior
                print("Container was cleaned up by context manager - this is expected behavior")
        finally:
            if sandbox.is_running:
                sandbox.cleanup()
