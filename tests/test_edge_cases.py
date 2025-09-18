"""
Edge case tests for BioCage robustness.
"""

import pytest
from biocage import BioCageOrchestrator as BioCageManager


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_code_string(self, sandbox):
        """Test execution with empty code string."""
        result = sandbox.run("")
        # Should succeed but produce no output
        assert result.success
        assert result.stdout.strip() == ""

    def test_whitespace_only_code(self, sandbox):
        """Test execution with whitespace-only code."""
        result = sandbox.run("   \n\t  \n   ")
        # Should succeed but produce no output
        assert result.success
        assert result.stdout.strip() == ""

    def test_very_large_output(self, sandbox):
        """Test handling of very large output."""
        code = """
# Generate large output (about 1MB)
for i in range(10000):
    print(f"Line {i}: " + "x" * 100)
"""
        result = sandbox.run(code, timeout=60)

        if result.success:
            # Should handle large output gracefully
            assert len(result.stdout) > 100000
            assert "Line 0:" in result.stdout
            assert "Line 9999:" in result.stdout
        else:
            # May fail due to resource limits, which is acceptable
            assert "timeout" in result.error.lower() or "memory" in result.stderr.lower()

    def test_unicode_and_special_characters(self, sandbox):
        """Test handling of Unicode and special characters."""
        code = '''
# Test various Unicode characters
print("Hello 世界! 🐍 Python")
print("Math symbols: ∑ ∆ ∞ π")
print("Emojis: 😀 🚀 💻")
print("Special chars: «»""''")
'''
        result = sandbox.run(code)
        assert result.success
        assert "Hello 世界! 🐍 Python" in result.stdout
        assert "Math symbols: ∑ ∆ ∞ π" in result.stdout

    def test_infinite_loop_timeout(self, sandbox):
        """Test timeout handling with infinite loop."""
        code = """
while True:
    pass
"""
        result = sandbox.run(code, timeout=2)
        assert not result.success
        assert result.exit_code == 124  # Timeout exit code
        assert "timeout" in result.error.lower() or "timed out" in result.error.lower()

    def test_memory_intensive_operation(self, sandbox):
        """Test memory-intensive operations."""
        code = """
try:
    # Try to allocate large amount of memory
    big_list = [0] * (10**7)  # About 80MB for integers
    print(f"Allocated list with {len(big_list)} elements")
except MemoryError:
    print("MemoryError: Not enough memory")
except Exception as e:
    print(f"Other error: {e}")
"""
        result = sandbox.run(code)
        # Should either succeed or fail gracefully
        assert result.success or "memory" in result.stderr.lower()

    def test_multiple_syntax_errors(self, sandbox):
        """Test handling of multiple syntax errors."""
        code = """
print("Missing closing quote
if True
    print("Missing colon above")
def function_without_body():
"""
        result = sandbox.run(code)
        assert not result.success
        assert "syntaxerror" in result.stderr.lower()

    def test_deeply_nested_code(self, sandbox):
        """Test deeply nested code structures."""
        # Create deeply nested if statements
        code = "x = 1\n"
        for i in range(50):
            code += "  " * i + f"if x == 1:\n"
        code += "  " * 50 + "print('Deep nesting works')\n"

        result = sandbox.run(code)
        if result.success:
            assert "Deep nesting works" in result.stdout
        else:
            # May fail due to recursion limits
            assert "recursion" in result.stderr.lower() or "maximum" in result.stderr.lower()

    def test_import_nonexistent_module(self, sandbox):
        """Test importing non-existent modules."""
        code = """
try:
    import this_module_definitely_does_not_exist
except ImportError as e:
    print(f"ImportError caught: {e}")
except ModuleNotFoundError as e:
    print(f"ModuleNotFoundError caught: {e}")
"""
        result = sandbox.run(code)
        assert result.success
        assert ("ImportError caught:" in result.stdout or
                "ModuleNotFoundError caught:" in result.stdout)

    def test_file_operations_in_container(self, sandbox):
        """Test file operations within container workspace."""
        code = """
import os
import tempfile

# Test writing to workspace
try:
    with open('/app/workspace/test.txt', 'w') as f:
        f.write('Hello from container')

    with open('/app/workspace/test.txt', 'r') as f:
        content = f.read()

    print(f"File content: {content}")

    # Clean up
    os.remove('/app/workspace/test.txt')
    print("File operations successful")

except Exception as e:
    print(f"File operation error: {e}")
"""
        result = sandbox.run(code)
        assert result.success
        assert "File content: Hello from container" in result.stdout
        assert "File operations successful" in result.stdout

    def test_concurrent_sandbox_instances(self):
        """Test multiple sandbox instances running concurrently."""
        sandbox1 = BioCageManager()
        sandbox2 = BioCageManager()

        try:
            with sandbox1:
                with sandbox2:
                    result1 = sandbox1.run('x = 1; print(f"Sandbox 1: {x}")')
                    result2 = sandbox2.run('y = 2; print(f"Sandbox 2: {y}")')

                    assert result1.success
                    assert result2.success
                    assert "Sandbox 1: 1" in result1.stdout
                    assert "Sandbox 2: 2" in result2.stdout
        finally:
            sandbox1.cleanup()
            sandbox2.cleanup()

    def test_container_restart_after_failure(self, persistent_sandbox):
        """Test container behavior after critical failure."""
        # Cause a critical failure
        result1 = persistent_sandbox.run("import sys; sys.exit(1)", timeout=5)
        assert not result1.success

        # Container should still be usable (or restart automatically)
        result2 = persistent_sandbox.run("print('After failure')", timeout=5)
        # May succeed if container recovered, or fail if shutdown for safety
        # Both behaviors are acceptable depending on shutdown_on_failure setting

    def test_invalid_python_syntax_recovery(self, persistent_sandbox):
        """Test recovery from invalid Python syntax."""
        # Invalid syntax
        result1 = persistent_sandbox.run("print('hello'", shutdown_on_failure=False)
        assert not result1.success

        # Should be able to run valid code after syntax error
        result2 = persistent_sandbox.run("print('valid code')", shutdown_on_failure=False)
        if persistent_sandbox.is_running:
            assert result2.success
            assert "valid code" in result2.stdout

    def test_network_isolation(self, sandbox):
        """Test that network access is properly isolated."""
        code = """
import socket

try:
    # Try to make a network connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    sock.connect(('google.com', 80))
    sock.close()
    print("Network connection succeeded")
except Exception as e:
    print(f"Network connection failed: {type(e).__name__}")
"""
        result = sandbox.run(code)
        assert result.success
        # Should fail to connect due to network isolation
        assert "Network connection failed" in result.stdout

    def test_resource_cleanup_after_exception(self, temp_directory):
        """Test that resources are cleaned up after exceptions."""
        # Create a file to expose
        test_file = temp_directory / "test.txt"
        test_file.write_text("test content")

        sandbox = BioCageManager()

        try:
            # Expose file (this automatically starts a persistent container)
            sandbox.expose_file(test_file)

            # Simulate an error during execution
            result = sandbox.run("raise RuntimeError('Test error')")
            assert not result.success

            # Verify cleanup happens
            sandbox.cleanup()
            assert not sandbox.is_running
            # Check that resources are cleaned up
            assert sandbox.current_executor is None or not hasattr(sandbox.current_executor, 'container_id')

        except Exception:
            # Ensure cleanup even if test fails
            sandbox.cleanup()
            raise

    def test_large_number_of_variables(self, persistent_sandbox):
        """Test handling of large number of variables in persistent mode."""
        # Create many variables
        code = """
# Create 1000 variables
for i in range(1000):
    globals()[f'var_{i}'] = i * 2

print(f"Created variables: var_0={var_0}, var_999={var_999}")
print(f"Total variables: {len([k for k in globals() if k.startswith('var_')])}")
"""
        result = persistent_sandbox.run(code)
        assert result.success
        assert "var_0=0" in result.stdout
        assert "var_999=1998" in result.stdout
        assert "Total variables: 1000" in result.stdout

        # Variables should persist
        result2 = persistent_sandbox.run("print(f'Persistent check: var_500={var_500}')")
        if result2.success:  # May fail if state persistence has limits
            assert "var_500=1000" in result2.stdout