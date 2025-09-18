# BioCage User Guide

This comprehensive guide covers BioCage's core features, advanced usage patterns, and best practices for secure Python code execution.

## Table of Contents

- [Core Concepts](#core-concepts)
- [Execution Modes](#execution-modes)
- [State Management](#state-management)
- [Dynamic Image Management](#dynamic-image-management)
- [File System Operations](#file-system-operations)
- [Error Handling](#error-handling)
- [Resource Management](#resource-management)
- [Configuration Options](#configuration-options)
- [Best Practices](#best-practices)

## Core Concepts

### The BioCageOrchestrator

The `BioCageOrchestrator` is the main interface for interacting with BioCage. It manages container lifecycle, executes code, and handles resource allocation.

```python
from biocage import BioCageOrchestrator

# Simple usage
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("print('Hello from BioCage!')")
    print(result.stdout)
```

### Execution Results

Every code execution returns a `SandboxExecutionResult` with comprehensive information:

```python
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("x = 42; print(x)")

    # Check execution status
    print(f"Successful: {result.success}")
    print(f"Exit code: {result.exit_code}")
    print(f"Execution time: {result.execution_time:.3f}s")

    # Access output
    if result.success:
        print(f"Output: {result.stdout}")
    else:
        print(f"Error: {result.stderr}")
```

### Container Lifecycle

BioCage automatically manages Docker containers, but you can also control the lifecycle manually:

```python
# Automatic lifecycle (recommended)
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("import numpy as np")
    # Container automatically cleaned up

# Manual lifecycle (advanced)
sandbox = BioCageOrchestrator()
try:
    sandbox.start_container()
    result = sandbox.run("import pandas as pd")
finally:
    sandbox.cleanup()  # Always cleanup
```

## Execution Modes

BioCage supports two distinct execution modes, each optimized for different use cases.

### Persistent Mode

Persistent mode maintains state between executions using the same container:

```python
# Persistent mode (default for context managers)
with BioCageOrchestrator(execution_mode="persistent") as sandbox:
    # First execution - define variables
    result1 = sandbox.run("x = 42")

    # Second execution - variables persist
    result2 = sandbox.run("y = x * 2")

    # Third execution - use accumulated state
    result3 = sandbox.run("print(f'x={x}, y={y}')")
    print(result3.stdout)  # Output: x=42, y=84
```

**Benefits:**
- State persistence between executions
- Better performance for multiple operations
- Ideal for interactive workflows
- Libraries stay loaded (no re-import overhead)

**Use cases:**
- Data analysis workflows
- Interactive Python sessions
- Multi-step computations
- Development and testing

### Ephemeral Mode

Ephemeral mode creates fresh containers for each execution:

```python
# Ephemeral mode - maximum isolation
with BioCageOrchestrator(execution_mode="ephemeral") as sandbox:
    # First execution
    result1 = sandbox.run("x = 42")

    # Second execution - x is not defined (fresh container)
    result2 = sandbox.run("print(x)")  # NameError: name 'x' is not defined
    print(f"Success: {result2.success}")  # False
```

**Benefits:**
- Maximum isolation and security
- No state leakage between executions
- Consistent starting environment
- Ideal for untrusted code

**Use cases:**
- Running untrusted code
- Isolated script execution
- Security-critical applications
- One-off computations

### Auto Mode

Auto mode intelligently selects the execution strategy:

```python
# Auto mode (default) - starts ephemeral, switches to persistent when needed
sandbox = BioCageOrchestrator(execution_mode="auto")

# Single execution - uses ephemeral
result1 = sandbox.run("print('Hello')")

# When files are exposed, automatically switches to persistent
sandbox.expose_file("/tmp/data.csv", "/app/data.csv")
result2 = sandbox.run("import pandas as pd; df = pd.read_csv('/app/data.csv')")

# Subsequent executions remain persistent
result3 = sandbox.run("print(len(df))")
```

## State Management

### Variable Persistence

In persistent mode, variables and imports persist across executions:

```python
with BioCageOrchestrator(execution_mode="persistent") as sandbox:
    # Import libraries
    sandbox.run("import numpy as np")
    sandbox.run("import pandas as pd")

    # Create data structures
    sandbox.run("""
    data = {
        'names': ['Alice', 'Bob', 'Charlie'],
        'ages': [25, 30, 35],
        'cities': ['New York', 'London', 'Tokyo']
    }
    df = pd.DataFrame(data)
    """)

    # Use persisted data
    result = sandbox.run("print(df.groupby('cities')['ages'].mean())")
    print(result.stdout)
```

### Session Recovery

BioCage automatically handles container restarts while preserving state:

```python
with BioCageOrchestrator(execution_mode="persistent") as sandbox:
    # Set up initial state
    sandbox.run("x = 100")
    sandbox.run("import math")

    # Force container restart (simulates failure recovery)
    container_id = sandbox.restart_container()

    # State is automatically restored
    result = sandbox.run("print(f'x = {x}, sqrt(x) = {math.sqrt(x)}')")
    print(result.stdout)  # Output: x = 100, sqrt(x) = 10.0
```

### Memory Management

Monitor and manage memory usage in persistent sessions:

```python
with BioCageOrchestrator(
    execution_mode="persistent",
    memory_limit="1g"
) as sandbox:
    # Create large datasets
    sandbox.run("import numpy as np")
    sandbox.run("large_array = np.random.rand(1000000)")

    # Check memory usage
    result = sandbox.run("""
    import psutil
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"Memory usage: {memory_mb:.1f} MB")
    """)
    print(result.stdout)

    # Clean up large objects
    sandbox.run("del large_array")
```

## Dynamic Image Management

### Automatic Dependency Detection

BioCage can automatically detect dependencies in your code and create custom Docker images:

```python
with BioCageOrchestrator(auto_detect_dependencies=True) as sandbox:
    # Code with pandas and numpy dependencies
    code = """
import pandas as pd
import numpy as np

data = {'Name': ['Alice', 'Bob'], 'Age': [25, 30]}
df = pd.DataFrame(data)
print(df)
"""
    result = sandbox.run(code)
    print(result.stdout)
```

### Auto-Cleanup of Dynamic Images

By default, BioCage automatically removes dynamically created images when the sandbox is closed to save disk space:

```python
# Default behavior - auto-cleanup enabled
with BioCageOrchestrator(
    auto_detect_dependencies=True,
    auto_cleanup_dynamic_images=True  # This is the default
) as sandbox:
    result = sandbox.run("import pandas as pd; print('pandas imported')")
    # Dynamic image will be automatically removed when context exits
```

### Disabling Auto-Cleanup

If you want to cache dynamically created images for reuse across multiple sessions:

```python
# Disable auto-cleanup to cache images
with BioCageOrchestrator(
    auto_detect_dependencies=True,
    auto_cleanup_dynamic_images=False
) as sandbox:
    result = sandbox.run("import pandas as pd; print('pandas imported')")
    # Dynamic image will be preserved for future use
```

### Manual Cleanup

You can also manually clean up dynamic images while keeping the sandbox running:

```python
sandbox = BioCageOrchestrator(
    auto_detect_dependencies=True,
    auto_cleanup_dynamic_images=False
)

with sandbox:
    # Create dynamic images
    sandbox.run("import pandas as pd")
    sandbox.run("import numpy as np")
    
    # Images are still available for reuse
    
# Manually cleanup when done
sandbox.cleanup()  # This will remove dynamic images if auto_cleanup_dynamic_images=True
```

### Monitoring Dynamic Images

Check which dynamic images were created during a session:

```python
sandbox = BioCageOrchestrator(auto_detect_dependencies=True)

with sandbox:
    sandbox.run("import pandas as pd")
    sandbox.run("import torch")
    
    # Check created images (internal attribute for debugging)
    print(f"Created {len(sandbox._dynamic_images_created)} dynamic images")
    for image in sandbox._dynamic_images_created:
        print(f"  - {image}")
```

## File System Operations

### Exposing Files

Make host files accessible to sandbox execution:

```python
with BioCageOrchestrator() as sandbox:
    # Expose a single file
    container_path = sandbox.expose_file(
        "/Users/data/dataset.csv",
        "/app/dataset.csv"
    )

    # Use the exposed file
    result = sandbox.run(f"""
    import pandas as pd
    df = pd.read_csv('{container_path}')
    print(f'Dataset shape: {df.shape}')
    """)
    print(result.stdout)
```

### Exposing Directories

Expose entire directories for complex workflows:

```python
with BioCageOrchestrator() as sandbox:
    # Expose project directory
    project_dir = sandbox.expose_directory(
        "/Users/myproject/data",
        "/app/data",
        readonly=True
    )

    # Access multiple files
    result = sandbox.run(f"""
    import os
    files = os.listdir('{project_dir}')
    print(f'Available files: {files}')

    # Process each CSV file
    import pandas as pd
    for file in files:
        if file.endswith('.csv'):
            df = pd.read_csv(f'{project_dir}/{file}')
            print(f'{file}: {len(df)} rows')
    """)
    print(result.stdout)
```

### Working with Temporary Files

Create temporary files within the sandbox:

```python
with BioCageOrchestrator() as sandbox:
    # Method 1: Create files through code execution
    sandbox.run("""
    with open('/tmp/temp_data.txt', 'w') as f:
        f.write('Hello from BioCage!')
    """)

    result = sandbox.run("print(open('/tmp/temp_data.txt').read())")
    print(result.stdout)  # Output: Hello from BioCage!

    # Method 2: Use execute_with_files for ephemeral executors
    files = {
        '/tmp/config.json': '{"debug": true, "max_items": 100}',
        '/tmp/data.txt': 'Sample data\nLine 2\nLine 3'
    }

    result = sandbox.execute_with_files("""
    import json
    with open('/tmp/config.json') as f:
        config = json.load(f)

    with open('/tmp/data.txt') as f:
        lines = f.readlines()

    print(f"Debug mode: {config['debug']}")
    print(f"Data lines: {len(lines)}")
    """, files)
    print(result.stdout)
```

### File Permissions and Security

BioCage enforces security through file system permissions:

```python
with BioCageOrchestrator() as sandbox:
    # Expose as read-only (default)
    sandbox.expose_file("/path/to/sensitive.txt", "/app/data.txt", readonly=True)

    # Attempt to modify (will fail safely)
    result = sandbox.run("""
    try:
        with open('/app/data.txt', 'w') as f:
            f.write('malicious content')
        print('File modified successfully')
    except PermissionError as e:
        print(f'Permission denied: {e}')
    """)
    print(result.stdout)  # Output: Permission denied: ...
```

## Error Handling

### Syntax Errors

Handle Python syntax errors gracefully:

```python
with BioCageOrchestrator() as sandbox:
    # Intentional syntax error
    result = sandbox.run("print('missing quote)")

    if not result.success:
        print(f"Syntax error detected:")
        print(f"Exit code: {result.exit_code}")
        print(f"Error message: {result.stderr}")
        # Stderr will contain: SyntaxError: unterminated string literal
```

### Runtime Errors

Capture and handle runtime exceptions:

```python
with BioCageOrchestrator() as sandbox:
    # Runtime error
    result = sandbox.run("""
    try:
        value = 10 / 0
    except ZeroDivisionError as e:
        print(f"Caught error: {e}")
        value = float('inf')

    print(f"Result: {value}")
    """)

    print(result.stdout)  # Output: Caught error: division by zero
                         #         Result: inf
```

### Timeout Handling

Manage execution timeouts:

```python
with BioCageOrchestrator() as sandbox:
    # Set timeout for potentially long-running code
    result = sandbox.run("""
    import time
    print("Starting long operation...")
    time.sleep(10)  # This will timeout
    print("Operation completed")
    """, timeout=5)

    if not result.success:
        print(f"Execution timed out after 5 seconds")
        print(f"Exit code: {result.exit_code}")  # 124 for timeout
        print(f"Partial output: {result.stdout}")  # "Starting long operation..."
```

### Error Recovery Strategies

Implement robust error recovery:

```python
with BioCageOrchestrator(execution_mode="persistent") as sandbox:
    # Attempt risky operation with fallback
    result = sandbox.run("""
    try:
        import some_unreliable_library
        result = some_unreliable_library.process_data()
    except ImportError:
        print("Library not available, using alternative")
        result = "fallback_result"
    except Exception as e:
        print(f"Operation failed: {e}")
        result = None

    print(f"Final result: {result}")
    """)

    if result.success:
        print("Recovery successful")
    else:
        # Container might be in bad state, restart it
        sandbox.restart_container()
        print("Container restarted for recovery")
```

## Resource Management

### Memory Limits

Control memory usage to prevent system overload:

```python
# Set memory limit
with BioCageOrchestrator(memory_limit="512m") as sandbox:
    result = sandbox.run("""
    import numpy as np
    try:
        # Try to allocate large array
        large_array = np.zeros((100000, 10000))  # ~7.5GB
        print("Large allocation successful")
    except MemoryError:
        print("Memory limit exceeded - allocation failed")
    """)
    print(result.stdout)
```

### CPU Limits

Restrict CPU usage for fair resource sharing:

```python
# Limit to 1 CPU core
with BioCageOrchestrator(cpu_limit="1.0") as sandbox:
    result = sandbox.run("""
    import multiprocessing
    import time

    def cpu_intensive_task():
        # Simulate CPU-intensive work
        for i in range(10**7):
            _ = i ** 2

    start_time = time.time()

    # This will be limited by CPU constraint
    processes = []
    for _ in range(4):  # Try to use 4 cores
        p = multiprocessing.Process(target=cpu_intensive_task)
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    elapsed = time.time() - start_time
    print(f"Execution time with CPU limit: {elapsed:.2f}s")
    """)
    print(result.stdout)
```

### Network Access Control

Control network access for security:

```python
# Disable network access (default)
with BioCageOrchestrator(network_access=False) as sandbox:
    result = sandbox.run("""
    import urllib.request
    try:
        response = urllib.request.urlopen('https://httpbin.org/get')
        print("Network access successful")
    except Exception as e:
        print(f"Network access blocked: {type(e).__name__}")
    """)
    print(result.stdout)  # Output: Network access blocked: URLError

# Enable network access when needed
with BioCageOrchestrator(network_access=True) as sandbox:
    result = sandbox.run("""
    import urllib.request
    try:
        response = urllib.request.urlopen('https://httpbin.org/get', timeout=5)
        print(f"Network access successful: {response.code}")
    except Exception as e:
        print(f"Network request failed: {e}")
    """)
    print(result.stdout)
```

## Configuration Options

### Complete Configuration Example

```python
# Comprehensive configuration
with BioCageOrchestrator(
    # Execution mode
    execution_mode="persistent",  # or "ephemeral", "auto"

    # Resource limits
    memory_limit="1g",           # 1GB memory limit
    cpu_limit="2.0",             # 2 CPU cores

    # Network and security
    network_access=False,        # Disable network

    # Timeouts
    default_timeout=30,          # 30 second default timeout

    # Container management
    image_name="python:3.11",   # Custom Python image
    remove_containers=True       # Clean up containers
) as sandbox:

    # Your code execution here
    result = sandbox.run("print('Configured sandbox ready!')")
    print(result.stdout)
```

### Environment Variables

Pass environment variables to the sandbox:

```python
with BioCageOrchestrator() as sandbox:
    # Set environment variables in container
    result = sandbox.run("""
    import os

    # Set variables
    os.environ['API_KEY'] = 'test_key_123'
    os.environ['DEBUG'] = 'true'

    # Access variables
    api_key = os.getenv('API_KEY', 'not_found')
    debug = os.getenv('DEBUG', 'false').lower() == 'true'

    print(f"API Key: {api_key}")
    print(f"Debug mode: {debug}")
    """)
    print(result.stdout)
```

## Best Practices

### 1. Use Context Managers

Always use the `with` statement for automatic cleanup:

```python
# Good
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("print('Hello')")

# Avoid (manual cleanup required)
sandbox = BioCageOrchestrator()
result = sandbox.run("print('Hello')")
sandbox.cleanup()  # Easy to forget!
```

### 2. Handle Errors Gracefully

Always check execution results:

```python
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("potentially_failing_code()")

    if result.success:
        process_success(result.stdout)
    else:
        handle_error(result.stderr, result.exit_code)
```

### 3. Set Appropriate Timeouts

Prevent hanging executions:

```python
with BioCageOrchestrator() as sandbox:
    # Short timeout for quick operations
    result = sandbox.run("print('quick')", timeout=5)

    # Longer timeout for complex operations
    result = sandbox.run("complex_data_processing()", timeout=300)
```

### 4. Limit Resources

Protect your system from resource exhaustion:

```python
with BioCageOrchestrator(
    memory_limit="512m",
    cpu_limit="1.0"
) as sandbox:
    # Limited resource usage
    result = sandbox.run("resource_intensive_operation()")
```

### 5. Use Read-Only File Access

When possible, expose files as read-only:

```python
with BioCageOrchestrator() as sandbox:
    # Read-only access (secure)
    sandbox.expose_file("/path/to/data.csv", "/app/data.csv", readonly=True)

    # Only when write access is absolutely necessary
    sandbox.expose_file("/path/to/output.txt", "/app/output.txt", readonly=False)
```

### 6. Validate Input Code

Pre-validate code before execution when possible:

```python
import ast

def is_safe_code(code: str) -> bool:
    """Basic validation of Python code safety."""
    try:
        tree = ast.parse(code)
        # Add your safety checks here
        return True
    except SyntaxError:
        return False

with BioCageOrchestrator() as sandbox:
    user_code = get_user_input()

    if is_safe_code(user_code):
        result = sandbox.run(user_code)
    else:
        print("Code validation failed")
```

### 7. Log Execution Details

Maintain execution logs for debugging:

```python
import logging

logging.basicConfig(level=logging.INFO)

with BioCageOrchestrator() as sandbox:
    result = sandbox.run("print('Hello')")

    logging.info(f"Execution successful: {result.success}")
    logging.info(f"Execution time: {result.execution_time:.3f}s")

    if not result.success:
        logging.error(f"Execution failed: {result.stderr}")
```

### 8. Use Persistent Mode for Workflows

When executing multiple related operations:

```python
# Efficient for multi-step workflows
with BioCageOrchestrator(execution_mode="persistent") as sandbox:
    # Step 1: Setup
    sandbox.run("import pandas as pd")
    sandbox.run("df = pd.read_csv('/app/data.csv')")

    # Step 2: Processing
    sandbox.run("df_cleaned = df.dropna()")

    # Step 3: Analysis
    result = sandbox.run("print(df_cleaned.describe())")
    print(result.stdout)
```

This completes the comprehensive BioCage user guide. For more advanced topics, see the [Advanced Guide](advanced-guide.md), and for complete API documentation, refer to the [API Reference](api-reference.md).