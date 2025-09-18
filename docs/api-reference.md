# BioCage API Reference

Complete reference documentation for BioCage's Python API, covering all classes, methods, and configuration options.

## Table of Contents

- [BioCageOrchestrator](#biocageorchestrator)
- [SandboxExecutionResult](#sandboxexecutionresult)
- [Executor Classes](#executor-classes)
- [Container Management](#container-management)
- [Filesystem Operations](#filesystem-operations)
- [Configuration Options](#configuration-options)
- [Error Classes](#error-classes)

## BioCageOrchestrator

The main interface for BioCage sandbox operations.

### Class Definition

```python
class BioCageOrchestrator:
    """
    High-level orchestrator for secure Python code execution in Docker containers.

    Provides a unified interface for managing container lifecycle, executing code,
    and handling file system operations with configurable security policies.
    """
```

### Constructor

```python
def __init__(
    self,
    image_name: str = "biocage:latest",
    memory_limit: str = "1g",
    cpu_limit: str = "2.0",
    network_access: bool = False,
    execution_mode: str = "auto",
    auto_detect_dependencies: bool = False,
    auto_cleanup_dynamic_images: bool = True
) -> None
```

**Parameters:**

- `image_name` (str): Default Docker image name for containers
- `memory_limit` (str): Container memory limit (e.g., "512m", "1g", "2g")
- `cpu_limit` (str): Container CPU limit (e.g., "1.0", "2.0", "0.5")
- `network_access` (bool): Whether to allow network access in containers
- `execution_mode` (str): Execution strategy - "persistent", "ephemeral", or "auto"
- `auto_detect_dependencies` (bool): Whether to automatically detect dependencies and build images
- `auto_cleanup_dynamic_images` (bool): Whether to automatically remove dynamically created images on cleanup (default: True)
- `network_access` (bool): Whether to allow network access in containers
- `default_timeout` (int): Default timeout for code execution in seconds
- `image_name` (str): Docker image name to use for containers
- `remove_containers` (bool): Whether to remove containers after use

**Example:**

```python
# Basic usage
orchestrator = BioCageOrchestrator()

# Custom configuration
orchestrator = BioCageOrchestrator(
    execution_mode="persistent",
    memory_limit="512m",
    cpu_limit="1.0",
    network_access=True,
    default_timeout=60
)
```

### Context Manager Support

```python
def __enter__(self) -> "BioCageOrchestrator"
def __exit__(self, exc_type, exc_val, exc_tb) -> None
```

**Example:**

```python
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("print('Hello, BioCage!')")
    print(result.stdout)
# Automatic cleanup when exiting context
```

### Core Methods

#### run()

Execute Python code in the sandbox.

```python
def run(
    self,
    code: str,
    timeout: Optional[int] = None
) -> SandboxExecutionResult
```

**Parameters:**

- `code` (str): Python code to execute
- `timeout` (Optional[int]): Execution timeout in seconds (overrides default)

**Returns:**

- `SandboxExecutionResult`: Execution result with output and metadata

**Example:**

```python
with BioCageOrchestrator() as sandbox:
    # Basic execution
    result = sandbox.run("print('Hello')")

    # With custom timeout
    result = sandbox.run("import time; time.sleep(5)", timeout=10)

    # Multi-line code
    result = sandbox.run("""
    import math
    x = 42
    y = math.sqrt(x)
    print(f"sqrt({x}) = {y}")
    """)
```

#### expose_file()

Make a host file accessible to the sandbox.

```python
def expose_file(
    self,
    host_path: str,
    container_path: Optional[str] = None,
    readonly: bool = True
) -> str
```

**Parameters:**

- `host_path` (str): Path to file on host system
- `container_path` (Optional[str]): Target path in container (auto-generated if None)
- `readonly` (bool): Mount as read-only for security

**Returns:**

- `str`: Path where file will be accessible in container

**Example:**

```python
with BioCageOrchestrator() as sandbox:
    # Expose single file
    container_path = sandbox.expose_file("/tmp/data.csv", "/app/data.csv")

    # Use the exposed file
    result = sandbox.run(f"import pandas as pd; df = pd.read_csv('{container_path}')")
```

#### expose_directory()

Make a host directory accessible to the sandbox.

```python
def expose_directory(
    self,
    host_dir: str,
    container_dir: Optional[str] = None,
    readonly: bool = True
) -> str
```

**Parameters:**

- `host_dir` (str): Path to directory on host system
- `container_dir` (Optional[str]): Target directory in container
- `readonly` (bool): Mount as read-only for security

**Returns:**

- `str`: Path where directory will be accessible in container

**Example:**

```python
with BioCageOrchestrator() as sandbox:
    # Expose entire directory
    data_dir = sandbox.expose_directory("/path/to/data", "/app/data")

    # Access files in directory
    result = sandbox.run(f"""
    import os
    files = os.listdir('{data_dir}')
    print(f'Files: {files}')
    """)
```

#### execute_with_files()

Execute code with temporary files created in the container.

```python
def execute_with_files(
    self,
    code: str,
    files: dict[str, str],
    timeout: Optional[int] = None
) -> SandboxExecutionResult
```

**Parameters:**

- `code` (str): Python code to execute
- `files` (dict[str, str]): Mapping of file paths to content
- `timeout` (Optional[int]): Execution timeout in seconds

**Returns:**

- `SandboxExecutionResult`: Execution result

**Example:**

```python
with BioCageOrchestrator() as sandbox:
    files = {
        "/tmp/config.json": '{"debug": true}',
        "/tmp/data.txt": "Hello, World!"
    }

    result = sandbox.execute_with_files("""
    import json
    with open('/tmp/config.json') as f:
        config = json.load(f)

    with open('/tmp/data.txt') as f:
        data = f.read()

    print(f"Config: {config}")
    print(f"Data: {data}")
    """, files)
```

### Container Management

#### start_container()

Manually start a container (not needed when using context manager).

```python
def start_container(self, **kwargs) -> str
```

**Parameters:**

- `**kwargs`: Container configuration overrides

**Returns:**

- `str`: Container ID

#### restart_container()

Restart the current container while preserving state (persistent mode only).

```python
def restart_container(self, **kwargs) -> str
```

**Parameters:**

- `**kwargs`: Container configuration overrides

**Returns:**

- `str`: New container ID

**Example:**

```python
with BioCageOrchestrator(execution_mode="persistent") as sandbox:
    # Set up state
    sandbox.run("x = 42")

    # Restart container
    new_id = sandbox.restart_container()

    # State is preserved
    result = sandbox.run("print(x)")  # Outputs: 42
```

#### cleanup()

Clean up all resources (containers, temporary files, etc.).

```python
def cleanup(self) -> None
```

**Example:**

```python
sandbox = BioCageOrchestrator()
try:
    sandbox.run("print('Hello')")
finally:
    sandbox.cleanup()  # Always clean up
```

### Information Methods

#### get_container_info()

Get detailed information about the orchestrator state.

```python
def get_container_info(self) -> dict[str, Any]
```

**Returns:**

- `dict[str, Any]`: Dictionary with configuration and state information

**Example:**

```python
with BioCageOrchestrator() as sandbox:
    info = sandbox.get_container_info()
    print(f"Execution mode: {info['execution_mode']}")
    print(f"Container ID: {info.get('container_id', 'None')}")
    print(f"Memory limit: {info['memory_limit']}")
```

#### is_running

Check if the orchestrator has a running container.

```python
@property
def is_running(self) -> bool
```

**Returns:**

- `bool`: True if container is running

**Example:**

```python
with BioCageOrchestrator() as sandbox:
    if sandbox.is_running:
        print("Container is active")
        result = sandbox.run("print('Hello')")
```

## SandboxExecutionResult

Result object returned by code execution operations.

### Class Definition

```python
@dataclass
class SandboxExecutionResult:
    """
    Comprehensive result of sandbox code execution.

    Contains output streams, execution metadata, timing information,
    and error details for debugging and monitoring.
    """
```

### Attributes

```python
stdout: str              # Standard output from execution
stderr: str              # Standard error from execution
exit_code: int           # Process exit code (0 = success)
execution_time: float    # Execution time in seconds
error: Optional[str]     # Additional error information
```

### Properties

#### success

```python
@property
def success(self) -> bool
```

**Returns:**

- `bool`: True if execution completed successfully (exit_code == 0)

### Methods

#### to_dict()

Convert result to dictionary representation.

```python
def to_dict(self) -> dict[str, Any]
```

**Returns:**

- `dict[str, Any]`: Dictionary representation of the result

**Example:**

```python
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("print('Hello')")

    # Check success
    if result.success:
        print(f"Output: {result.stdout}")
    else:
        print(f"Error: {result.stderr}")
        print(f"Exit code: {result.exit_code}")

    # Get execution time
    print(f"Took {result.execution_time:.3f} seconds")

    # Convert to dict
    result_dict = result.to_dict()
```

## Executor Classes

BioCage uses different executor classes for different execution strategies.

### BaseExecutor

Abstract base class for all executors.

```python
class BaseExecutor(ABC):
    """Abstract base class for code execution strategies."""
```

#### Common Methods

```python
def execute(self, code: str, timeout: Optional[int] = None) -> SandboxExecutionResult
def is_ready(self) -> bool
def validate_environment(self) -> bool
def cleanup(self) -> None
def get_execution_info(self) -> dict[str, Any]
```

### PersistentExecutor

Executor that maintains state between executions.

```python
class PersistentExecutor(BaseExecutor):
    """
    Executor that maintains container state between executions.

    Provides state persistence, better performance for multiple executions,
    and automatic session recovery through code history replay.
    """
```

#### Key Features

- State persistence between executions
- Automatic session recovery
- Code history tracking
- Container restart capability

#### Additional Methods

```python
def restart_container(self, **kwargs) -> str
def get_session_history(self) -> list[str]
def clear_session_history(self) -> None
```

### EphemeralExecutor

Executor that creates fresh containers for each execution.

```python
class EphemeralExecutor(BaseExecutor):
    """
    Executor that creates fresh containers for each execution.

    Provides maximum isolation and security by ensuring no state
    persists between executions.
    """
```

#### Key Features

- Fresh container per execution
- Maximum isolation
- No state persistence
- Automatic cleanup

#### Additional Methods

```python
def get_execution_stats(self) -> dict[str, Any]
def reset_stats(self) -> None
```

## Container Management

### ContainerLifecycle

Manages Docker container lifecycle operations.

```python
class ContainerLifecycle:
    """Manages the complete lifecycle of Docker containers."""
```

#### Methods

```python
def start_container(
    self,
    memory_limit: str = "1g",
    cpu_limit: str = "2.0",
    network_access: bool = False,
    volumes: Optional[list] = None,
    read_only: bool = True
) -> str

def stop_container(self) -> None
def restart_container(self, **kwargs) -> str
def execute_command(
    self,
    command: list[str],
    timeout: int = 30,
    input_data: Optional[str] = None
) -> Any
```

### ImageManager

Manages Docker images for container execution.

```python
class ImageManager:
    """Manages Docker images for sandbox execution."""
```

#### Methods

```python
def ensure_image_exists(self) -> None
def image_exists(self) -> bool
def pull_image(self) -> None
```

## Filesystem Operations

### PathManager

Manages path exposure and volume mounting.

```python
class PathManager:
    """Manages host path exposure to containers."""
```

#### Methods

```python
def expose_path(
    self,
    host_path: str,
    container_path: Optional[str] = None,
    readonly: bool = True
) -> str

def expose_directory(
    self,
    host_dir: str,
    container_dir: Optional[str] = None,
    readonly: bool = True
) -> str

def get_volume_mounts(self) -> list[str]
def clear_exposed_paths(self) -> int
def get_exposed_paths_info(self) -> dict[str, dict[str, str]]
```

### TempFileManager

Manages temporary files within containers.

```python
class TempFileManager:
    """Manages temporary files and cleanup."""
```

#### Methods

```python
def create_temp_file(self, content: str, suffix: str = ".tmp") -> str
def create_temp_dir(self) -> str
def cleanup_all(self) -> None
def get_managed_paths(self) -> dict[str, list[str]]
```

## Configuration Options

### Execution Modes

- **"persistent"**: Maintains state between executions using the same container
- **"ephemeral"**: Creates fresh containers for each execution
- **"auto"**: Intelligent mode selection based on usage patterns

### Resource Limits

#### Memory Limits

- Format: `"<amount><unit>"` (e.g., "512m", "1g", "2g")
- Units: `b` (bytes), `k` (KB), `m` (MB), `g` (GB)
- Default: `"1g"`

#### CPU Limits

- Format: `"<cores>"` (e.g., "0.5", "1.0", "2.0")
- Represents number of CPU cores
- Default: `"2.0"`

### Network Access

- `True`: Enable network access within containers
- `False`: Disable network access (default for security)

### Timeout Settings

- Default timeout: 30 seconds
- Per-execution timeout: Override default for specific operations
- Minimum: 1 second
- Maximum: No enforced limit (use responsibly)

## Error Classes

### ExecutionError

Base exception for execution-related errors.

```python
class ExecutionError(Exception):
    """Base exception for sandbox execution errors."""

    def __init__(
        self,
        executor_type: str,
        error_message: str,
        code: Optional[str] = None
    ) -> None
```

### PersistentExecutionError

Exception specific to persistent execution failures.

```python
class PersistentExecutionError(ExecutionError):
    """Exception raised when persistent execution operations fail."""
```

### EphemeralExecutionError

Exception specific to ephemeral execution failures.

```python
class EphemeralExecutionError(ExecutionError):
    """Exception raised when ephemeral execution operations fail."""
```

### ContainerLifecycleError

Exception for container management failures.

```python
class ContainerLifecycleError(Exception):
    """Exception raised when container lifecycle operations fail."""
```

### DockerCommandError

Exception for Docker command failures.

```python
class DockerCommandError(Exception):
    """Exception raised when Docker commands fail."""

    def __init__(
        self,
        command: list[str],
        returncode: int,
        stdout: str = "",
        stderr: str = ""
    ) -> None
```

## Usage Examples

### Basic Usage

```python
from biocage import BioCageOrchestrator

# Simple execution
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("print('Hello, BioCage!')")
    print(result.stdout)
```

### Advanced Configuration

```python
# Production configuration
with BioCageOrchestrator(
    execution_mode="persistent",
    memory_limit="512m",
    cpu_limit="1.0",
    network_access=False,
    default_timeout=60
) as sandbox:

    # Execute code with file access
    sandbox.expose_file("/path/to/data.csv", "/app/data.csv")

    result = sandbox.run("""
    import pandas as pd
    df = pd.read_csv('/app/data.csv')
    print(f'Loaded {len(df)} rows')
    """)

    if result.success:
        print(result.stdout)
    else:
        print(f"Error: {result.stderr}")
```

### Error Handling

```python
from biocage import BioCageOrchestrator, ExecutionError

try:
    with BioCageOrchestrator() as sandbox:
        result = sandbox.run("invalid_python_code()")

        if not result.success:
            print(f"Execution failed with exit code: {result.exit_code}")
            print(f"Error output: {result.stderr}")

except ExecutionError as e:
    print(f"Execution error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

This completes the comprehensive API reference for BioCage. For practical examples and usage patterns, see the [User Guide](user-guide.md) and [Examples](examples.md).