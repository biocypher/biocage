"""Pytest configuration and shared fixtures."""

import shutil
import tempfile
from pathlib import Path

import pytest

from biocage import BioCageManager


@pytest.fixture(scope="session")
def docker_available():
    """Check if Docker is available for testing."""
    import subprocess

    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.fixture
def sandbox():
    """Provide a fresh sandbox instance for each test."""
    sandbox = BioCageManager()
    yield sandbox

    # Cleanup after test
    if sandbox.is_running:
        sandbox.cleanup()


@pytest.fixture
def persistent_sandbox():
    """Provide a sandbox with a started container for persistence tests."""
    sandbox = BioCageManager()
    sandbox.start_container()

    yield sandbox

    # Cleanup after test
    sandbox.cleanup()


@pytest.fixture
def temp_directory():
    """Provide a temporary directory for file operations."""
    temp_dir = Path(tempfile.mkdtemp(prefix="sandbox_test_"))
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_csv_file(temp_directory):
    """Create a sample CSV file for testing."""
    csv_file = temp_directory / "sample.csv"
    csv_file.write_text("""name,age,score
Alice,25,95
Bob,30,87
Charlie,35,92
""")
    return csv_file


@pytest.fixture
def sample_python_file(temp_directory):
    """Create a sample Python file for testing."""
    py_file = temp_directory / "utils.py"
    py_file.write_text("""
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

CONSTANT = 42
""")
    return py_file


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (may take several seconds)")
    config.addinivalue_line("markers", "docker: marks tests that require Docker")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests that use docker."""
    for item in items:
        # Mark tests that use sandbox fixtures as requiring docker
        if any(fixture in item.fixturenames for fixture in ["sandbox", "persistent_sandbox"]):
            item.add_marker(pytest.mark.docker)

        # Mark tests with certain names as slow
        if any(keyword in item.name for keyword in ["timeout", "performance", "large"]):
            item.add_marker(pytest.mark.slow)


@pytest.fixture(autouse=True)
def skip_if_no_docker(request, docker_available):
    """Skip tests that require Docker if Docker is not available."""
    if request.node.get_closest_marker("docker") and not docker_available:
        pytest.skip("Docker not available")


# Custom assertion helpers


def assert_successful_execution(result, expected_output=None):
    """Assert that execution was successful with optional output check."""
    assert result.success, f"Execution failed: {result.stderr}"
    assert result.exit_code == 0
    assert result.execution_time > 0

    if expected_output:
        assert expected_output in result.stdout


def assert_failed_execution(result, expected_error_type=None):
    """Assert that execution failed with optional error type check."""
    assert not result.success, f"Execution should have failed but succeeded: {result.stdout}"
    assert result.exit_code != 0
    assert result.stderr.strip(), "Expected error message in stderr"

    if expected_error_type:
        assert expected_error_type in result.stderr


def assert_container_running(sandbox):
    """Assert that the sandbox container is running."""
    assert sandbox.is_running, "Container should be running"

    info = sandbox.get_container_info()
    assert info["is_running"], "Container info should show running"
    assert info["container_id"], "Container should have an ID"


# Test data generators


def generate_test_dataframe_code():
    """Generate code for creating a test pandas DataFrame."""
    return """
import pandas as pd
import numpy as np

df = pd.DataFrame({
    'id': range(1, 6),
    'name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
    'age': [25, 30, 35, 28, 32],
    'score': [95.5, 87.0, 92.3, 88.7, 94.1]
})
"""


def generate_test_function_code():
    """Generate code for defining test functions."""
    return """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n-1)

def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True
"""


# Performance utilities


@pytest.fixture
def performance_timer():
    """Provide a simple timer for performance testing."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            self.end_time = time.time()

        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None

    return Timer()


# Error simulation utilities


def create_error_test_cases():
    """Create common error test cases."""
    return [
        ("print('hello'", "SyntaxError"),
        ("undefined_variable", "NameError"),
        ("1 / 0", "ZeroDivisionError"),
        ("import nonexistent_module", "ModuleNotFoundError"),
        ('"string" + 5', "TypeError"),
        ('{"a": 1}["b"]', "KeyError"),
        ("[1, 2, 3][10]", "IndexError"),
        ("if True:\nprint('bad indent')", "IndentationError"),
    ]
