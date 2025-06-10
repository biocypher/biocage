# CodeSandbox Test Suite

This directory contains comprehensive pytest tests for the CodeSandbox Python package. The tests are organized into focused modules that cover all aspects of the sandbox functionality.

## 🏗️ Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Pytest configuration and shared fixtures
├── pytest.ini                 # Pytest settings
├── run_tests.py               # Interactive test runner script
├── README.md                  # This file
├── test_basic_functionality.py    # Core execution and container management
├── test_persistence.py        # State persistence (variables, imports, functions)
├── test_file_exposure.py      # File and directory exposure
├── test_context_manager.py    # Context manager and configuration
└── test_error_reporting.py    # Error handling and debugging
```

## 🧪 Test Categories

### Basic Functionality (`test_basic_functionality.py`)
- **TestBasicExecution**: Simple code execution, return values, timeout handling
- **TestContainerManagement**: Context managers, manual lifecycle, custom resources
- **TestSecurity**: Network isolation, filesystem protection, resource limits
- **TestErrorHandling**: Syntax errors, runtime errors, partial output capture

### Persistence (`test_persistence.py`)
- **TestVariablePersistence**: Basic variables, complex data structures, modifications
- **TestImportPersistence**: Standard imports, aliases, from imports
- **TestFunctionPersistence**: Function definitions, closures, class definitions  
- **TestDataFramePersistence**: DataFrame creation, modification, multiple DataFrames
- **TestMixedPersistence**: Combined variables, imports, and functions

### File Exposure (`test_file_exposure.py`)
- **TestFileExposure**: Single files, auto-generated paths, Python modules
- **TestDirectoryExposure**: Read-only directories, multiple directories
- **TestWritableDirectories**: Write access, combined read-only/writable
- **TestTemporaryFiles**: CSV, Python, and multiple temp file creation

### Context Manager (`test_context_manager.py`)
- **TestBasicContextManager**: Simple usage, cleanup, exception handling
- **TestConfigureContextManager**: Resource configuration, method chaining
- **TestContextManagerWithFileExposure**: File exposure within contexts
- **TestContextManagerEdgeCases**: Nested contexts, invalid configurations
- **TestPreConfiguredMethod**: Pre-started containers with context managers

### Error Reporting (`test_error_reporting.py`)
- **TestBasicErrorReporting**: All error types (syntax, runtime, import, etc.)
- **TestPartialOutputOnError**: Output capture before errors occur
- **TestErrorHandlingWithShutdown**: Shutdown policies and recovery
- **TestTimeoutHandling**: Timeout errors and partial output
- **TestEnhancedErrorReporting**: Error categorization with debugging hints
- **TestAgentErrorIntegration**: Agent-friendly error formatting
- **TestErrorRecovery**: Try-catch patterns and graceful handling

## 🚀 Running Tests

### Quick Start

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_basic_functionality.py

# Run with coverage
pytest --cov=codesandbox --cov-report=html

# Interactive test runner
python tests/run_tests.py
```

### Using the Interactive Test Runner

The `run_tests.py` script provides an easy way to run common test scenarios:

```bash
python tests/run_tests.py
```

This will show an interactive menu:
```
Available test presets:
1. Quick tests (no slow, no Docker requirements)
2. Basic functionality tests
3. Persistence tests
4. File exposure tests
5. Context manager tests
6. Error reporting tests

Enter preset number (or 'all' for all tests):
```

### Command Line Options

```bash
# Skip slow tests
pytest -m "not slow"

# Skip Docker-dependent tests
pytest -m "not docker"

# Run only Docker tests
pytest -m "docker"

# Verbose output
pytest -v -s

# Stop on first failure
pytest -x

# Run specific test method
pytest tests/test_basic_functionality.py::TestBasicExecution::test_simple_execution

# Run tests in parallel (requires pytest-xdist)
pytest -n auto
```

### Advanced Test Runner Options

```bash
# Fast tests only
python tests/run_tests.py --fast

# Skip Docker tests
python tests/run_tests.py --no-docker

# Run with coverage
python tests/run_tests.py --coverage

# Run specific file
python tests/run_tests.py --file basic_functionality

# Verbose output
python tests/run_tests.py --verbose

# Parallel execution
python tests/run_tests.py --parallel
```

## 🔧 Test Configuration

### Markers

Tests are marked with the following markers:

- `@pytest.mark.docker`: Tests that require Docker
- `@pytest.mark.slow`: Tests that may take several seconds
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.unit`: Unit tests

### Fixtures

#### Core Fixtures
- `sandbox`: Fresh sandbox instance for each test
- `persistent_sandbox`: Sandbox with started container
- `temp_directory`: Temporary directory for file operations
- `sample_csv_file`: Pre-created CSV file for testing
- `sample_python_file`: Pre-created Python module for testing

#### Utility Fixtures
- `docker_available`: Checks if Docker is available
- `performance_timer`: Simple timer for performance tests

#### Auto-skip
- Tests marked with `@pytest.mark.docker` are automatically skipped if Docker is not available

### Helper Functions

```python
from tests.conftest import (
    assert_successful_execution,
    assert_failed_execution,
    assert_container_running,
    generate_test_dataframe_code,
    generate_test_function_code,
    create_error_test_cases
)

# Example usage
def test_my_functionality(sandbox):
    result = sandbox.run("print('Hello')")
    assert_successful_execution(result, "Hello")
```

## 📋 Test Coverage

The test suite aims for comprehensive coverage of:

✅ **Core Functionality**
- Basic code execution and result handling
- Container lifecycle management (start, stop, restart, cleanup)
- Resource configuration (memory, CPU limits)
- Security isolation and access controls

✅ **State Persistence**
- Variable persistence across executions
- Import statement persistence (standard, aliases, from imports)
- Function and class definition persistence
- Pandas DataFrame persistence and modifications

✅ **File System Integration**
- Individual file exposure with custom and auto-generated paths
- Directory exposure (read-only and read-write)
- Temporary file creation and management
- Combined file and directory operations

✅ **Context Management**
- Basic context manager usage and cleanup
- Configuration through `configure_context_manager()`
- Method chaining and pre-configuration
- Exception handling and resource cleanup

✅ **Error Handling**
- All Python error types (syntax, runtime, import, type, etc.)
- Partial output capture before errors
- Timeout handling and reporting
- Enhanced error categorization for debugging
- Agent-friendly error formatting

✅ **Edge Cases**
- Nested context managers
- Invalid configurations
- Network isolation testing
- Performance under resource constraints

## 🐳 Docker Requirements

Most tests require Docker to be available and running. The test suite will:

1. **Auto-detect Docker**: Check if Docker is available at test startup
2. **Auto-skip**: Skip Docker-dependent tests if Docker is unavailable
3. **Clean up**: Automatically clean up containers after each test

### Docker-free Testing

Some tests can run without Docker by mocking the sandbox behavior. To run only non-Docker tests:

```bash
pytest -m "not docker"
```

## 🔍 Debugging Tests

### Verbose Output

```bash
# See detailed test output
pytest -v -s

# See stdout from sandbox executions
pytest -s --capture=no
```

### Running Single Tests

```bash
# Run specific test method
pytest tests/test_basic_functionality.py::TestBasicExecution::test_simple_execution -v -s

# Run specific test class
pytest tests/test_persistence.py::TestVariablePersistence -v
```

### Test Failures

When tests fail, pytest provides detailed information:

```
FAILED tests/test_basic_functionality.py::TestBasicExecution::test_simple_execution

=========================== FAILURES ===========================
def test_simple_execution(self):
    with PythonSandboxManager() as sandbox:
        result = sandbox.run("print('Hello from sandbox!')")
>       assert result.success
E       AssertionError: assert False
E        +  where False = <SandboxExecutionResult success=False>.success

>       assert "Hello from sandbox!" in result.stdout  
E       AssertionError: assert 'Hello from sandbox!' in ''
```

## 🚧 Contributing to Tests

### Adding New Tests

1. **Choose the appropriate test file** based on functionality
2. **Follow the existing test class structure**
3. **Use descriptive test names** that explain what is being tested
4. **Add appropriate markers** (`@pytest.mark.slow`, `@pytest.mark.docker`)
5. **Use fixtures** for common setup (sandbox, temp files, etc.)
6. **Add docstrings** explaining the test purpose

Example:
```python
class TestNewFeature:
    """Test new sandbox feature."""
    
    @pytest.mark.docker
    def test_new_functionality(self, sandbox):
        """Test that new functionality works correctly."""
        result = sandbox.run("# test code here")
        assert_successful_execution(result, "expected output")
```

### Test Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Cleanup**: Use fixtures for automatic cleanup of resources
3. **Clear assertions**: Use helper functions like `assert_successful_execution()`
4. **Error testing**: Test both success and failure cases
5. **Documentation**: Add clear docstrings explaining test purpose

### Running Tests During Development

```bash
# Run tests related to your changes
pytest tests/test_basic_functionality.py -v

# Run with immediate feedback
pytest tests/test_basic_functionality.py -v -x --tb=short

# Watch for changes (requires pytest-watch)
ptw tests/test_basic_functionality.py
```

## 📊 Performance Testing

Some tests include performance considerations:

```bash
# Skip slow tests during development
pytest -m "not slow"

# Run only performance tests
pytest -m "slow"

# Time test execution
pytest --durations=10
```

## 🎯 Test Goals

The test suite ensures:

1. **Reliability**: All functionality works as expected
2. **Robustness**: Graceful handling of errors and edge cases  
3. **Security**: Proper isolation and access controls
4. **Performance**: Efficient resource usage
5. **Usability**: Clear error messages and debugging information
6. **Compatibility**: Works across different environments

---

For questions about the test suite, please refer to the main project documentation or create an issue in the project repository. 