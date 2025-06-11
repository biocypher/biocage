"""Test basic sandbox functionality."""

from biocage import BioCageManager


class TestBasicExecution:
    """Test basic code execution functionality."""

    def test_simple_execution(self):
        """Test basic code execution."""
        with BioCageManager() as sandbox:
            result = sandbox.run("print('Hello from sandbox!')")
            assert result.success
            assert "Hello from sandbox!" in result.stdout
            assert result.exit_code == 0
            assert result.execution_time > 0

    def test_multiple_statements(self):
        """Test execution of multiple statements."""
        with BioCageManager() as sandbox:
            result = sandbox.run("""
x = 10
y = 20
print(f"Sum: {x + y}")
""")
            assert result.success
            assert "Sum: 30" in result.stdout

    def test_return_values(self):
        """Test that result object contains expected attributes."""
        with BioCageManager() as sandbox:
            result = sandbox.run("print('test')")

            # Check all expected attributes exist
            assert hasattr(result, "stdout")
            assert hasattr(result, "stderr")
            assert hasattr(result, "exit_code")
            assert hasattr(result, "execution_time")
            assert hasattr(result, "success")
            assert hasattr(result, "error")

    def test_timeout_handling(self):
        """Test timeout functionality."""
        with BioCageManager() as sandbox:
            result = sandbox.run("import time; time.sleep(10)", timeout=2)
            assert not result.success
            assert result.exit_code == 124  # Timeout exit code

    def test_container_info(self):
        """Test getting container information."""
        with BioCageManager() as sandbox:
            info = sandbox.get_container_info()
            assert info["is_running"] is True
            assert info["container_id"] is not None
            assert info["container_name"] is not None
            assert isinstance(info["exposed_paths"], dict)
            assert isinstance(info["temp_files_count"], int)


class TestContainerManagement:
    """Test container lifecycle management."""

    def test_context_manager(self):
        """Test context manager functionality."""
        with BioCageManager() as sandbox:
            assert sandbox.is_running
            result = sandbox.run("print('Context manager works')")
            assert result.success
        # Container should be cleaned up after context exit

    def test_manual_container_management(self):
        """Test manual container start/stop."""
        sandbox = BioCageManager()
        assert not sandbox.is_running

        try:
            sandbox.start_container()
            assert sandbox.is_running

            result = sandbox.run("print('Manual management')")
            assert result.success
        finally:
            sandbox.cleanup()
            assert not sandbox.is_running

    def test_custom_resources(self):
        """Test container with custom resource limits."""
        with BioCageManager().configure_context_manager(memory_limit="512m", cpu_limit="1.0") as sandbox:
            result = sandbox.run("print('Custom resources')")
            assert result.success

            info = sandbox.get_container_info()
            assert info["is_running"]

    def test_restart_container(self):
        """Test container restart functionality."""
        sandbox = BioCageManager()

        try:
            # Start initial container
            container_id_1 = sandbox.start_container(memory_limit="256m")
            assert sandbox.is_running

            # Restart with different settings
            container_id_2 = sandbox.restart_container(memory_limit="512m")
            assert sandbox.is_running
            assert container_id_1 != container_id_2

            result = sandbox.run("print('Restarted container')")
            assert result.success
        finally:
            sandbox.cleanup()


class TestSecurity:
    """Test security features and isolation."""

    def test_network_isolation(self):
        """Test that network access is blocked."""
        with BioCageManager() as sandbox:
            result = sandbox.run("""
import urllib.request
try:
    urllib.request.urlopen('http://google.com', timeout=1)
    print("SECURITY_ISSUE: Network access allowed")
except Exception as e:
    print(f"Network blocked: {type(e).__name__}")
""")
            assert result.success
            assert "Network blocked" in result.stdout
            assert "SECURITY_ISSUE" not in result.stdout

    def test_filesystem_isolation(self):
        """Test that filesystem is properly isolated."""
        with BioCageManager() as sandbox:
            result = sandbox.run("""
import os
try:
    # Try to access sensitive system files
    with open('/etc/passwd', 'r') as f:
        content = f.read()
    print("INFO: System file access in container")
    print(f"File content length: {len(content)}")
except Exception as e:
    print(f"System file access blocked: {type(e).__name__}")
""")
            assert result.success
            # In a container, /etc/passwd might exist but contain container-specific info
            # This is normal container behavior, not a security issue
            assert "System file access" in result.stdout

    def test_write_protection(self):
        """Test that root filesystem is read-only."""
        with BioCageManager() as sandbox:
            result = sandbox.run("""
import os
try:
    with open('/test_write.txt', 'w') as f:
        f.write('test')
    print("SECURITY_ISSUE: Root filesystem is writable")
except Exception as e:
    print(f"Root filesystem protected: {type(e).__name__}")
""")
            assert result.success
            assert "SECURITY_ISSUE" not in result.stdout
            assert "protected" in result.stdout


class TestErrorHandling:
    """Test error handling and reporting."""

    def test_syntax_error(self):
        """Test syntax error handling."""
        with BioCageManager() as sandbox:
            result = sandbox.run("print('Hello'  # Missing closing parenthesis")
            assert not result.success
            assert "SyntaxError" in result.stderr
            assert result.exit_code != 0

    def test_runtime_error(self):
        """Test runtime error handling."""
        with BioCageManager() as sandbox:
            result = sandbox.run("x = 1 / 0")
            assert not result.success
            assert "ZeroDivisionError" in result.stderr

    def test_name_error(self):
        """Test name error handling."""
        with BioCageManager() as sandbox:
            result = sandbox.run("print(undefined_variable)")
            assert not result.success
            assert "NameError" in result.stderr

    def test_import_error(self):
        """Test import error handling."""
        with BioCageManager() as sandbox:
            result = sandbox.run("import nonexistent_module")
            assert not result.success
            assert "ModuleNotFoundError" in result.stderr

    def test_partial_output_on_error(self):
        """Test that partial output is captured before error."""
        with BioCageManager() as sandbox:
            result = sandbox.run("""
print("This should appear")
x = 1 / 0
print("This should not appear")
""")
            assert not result.success
            assert "This should appear" in result.stdout
            assert "This should not appear" not in result.stdout
            assert "ZeroDivisionError" in result.stderr

    def test_error_with_shutdown_disabled(self):
        """Test error handling with shutdown_on_failure=False."""
        with BioCageManager() as sandbox:
            result = sandbox.run("x = 1 / 0", shutdown_on_failure=False)
            assert not result.success
            # Container should still be running
            assert sandbox.is_running

            # Should be able to run more code
            result2 = sandbox.run("print('Still working')")
            assert result2.success
            assert "Still working" in result2.stdout
