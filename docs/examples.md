# BioCage Examples

This guide provides comprehensive examples demonstrating BioCage's capabilities. All examples include working code that you can run directly.

## Table of Contents

- [Basic Examples](#basic-examples)
- [API Examples](#api-examples)
- [Advanced Examples](#advanced-examples)
- [Data Files](#data-files)
- [Running Examples](#running-examples)

## Basic Examples

### Simple Demo (`examples/basic/simple_demo.py`)

A comprehensive demonstration of BioCage's core features:

```bash
python examples/basic/simple_demo.py
```

**Features demonstrated:**
- Basic code execution
- Persistent vs ephemeral modes
- File operations
- Error handling and recovery
- Resource configuration

**Key code snippet:**
```python
from biocage import BioCageOrchestrator

# Basic execution
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("print('Hello from BioCage!')")
    print(f"Output: {result.stdout.strip()}")

# Persistent mode
with BioCageOrchestrator(execution_mode="persistent") as sandbox:
    sandbox.run("x = 42")
    result = sandbox.run("print(f'x = {x}')")
    print(result.stdout.strip())  # Output: x = 42
```

### Persistent Mode (`examples/basic/persistent_mode.py`)

Demonstrates state persistence between executions:

```bash
python examples/basic/persistent_mode.py
```

**What you'll learn:**
- Variables persist between executions
- Imports remain loaded
- State survives container restarts
- Better performance for workflows

**Key features:**
- Session state management
- Container restart with recovery
- Code history replay
- Import persistence

### Ephemeral Mode (`examples/basic/ephemeral_mode.py`)

Shows maximum isolation with fresh containers:

```bash
python examples/basic/ephemeral_mode.py
```

**What you'll learn:**
- Maximum isolation between executions
- No state leakage or persistence
- Fresh Python environment each time
- Ideal for untrusted code execution

**Security demonstration:**
- Shows how malicious state is cleaned between executions
- Demonstrates complete environment isolation

### Error Handling (`examples/basic/error_handling.py`)

Comprehensive error handling patterns:

```bash
python examples/basic/error_handling.py
```

**Error types covered:**
- Syntax errors
- Runtime exceptions (NameError, ImportError, etc.)
- Timeout handling
- Container recovery strategies
- Multiple attempt patterns

**Key patterns:**
```python
# Graceful error handling
result = sandbox.run("risky_code()")
if not result.success:
    print(f"Error: {result.stderr}")
    # Implement recovery strategy

# Timeout handling
result = sandbox.run("long_operation()", timeout=5)
if result.exit_code == 124:  # Timeout
    print("Operation timed out")
```

### File Operations (`examples/basic/file_operations.py`)

File system integration and security:

```bash
python examples/basic/file_operations.py
```

**Operations demonstrated:**
- Exposing individual files
- Exposing entire directories
- Working with temporary files
- File permissions and security
- Complete data processing workflows

**Key patterns:**
```python
# Expose files to sandbox
with BioCageOrchestrator() as sandbox:
    container_path = sandbox.expose_file("/host/data.csv", "/app/data.csv")

    result = sandbox.run(f"""
    import pandas as pd
    df = pd.read_csv('{container_path}')
    print(f'Loaded {len(df)} rows')
    """)
```

### Resource Management (`examples/basic/resource_management.py`)

Resource configuration and monitoring:

```bash
python examples/basic/resource_management.py
```

**Resources covered:**
- Memory limits and enforcement
- CPU limits and monitoring
- Network access control
- Execution timeouts
- Comprehensive configuration

**Configuration examples:**
```python
# Production configuration
with BioCageOrchestrator(
    memory_limit="512m",
    cpu_limit="1.0",
    network_access=False,
    execution_mode="persistent"
) as sandbox:
    result = sandbox.run("resource_intensive_operation()")
```

## API Examples

### Orchestrator API (`examples/api/orchestrator_examples.py`)

Complete BioCageOrchestrator API demonstration:

```bash
python examples/api/orchestrator_examples.py
```

**API methods covered:**
- Constructor options and configuration
- Context manager usage
- File exposure methods
- Container management
- Information retrieval methods
- Advanced execution features

**Patterns demonstrated:**
- Configuration validation
- Container lifecycle management
- Resource monitoring
- Error recovery strategies

### Execution Results (`examples/api/execution_result_examples.py`)

Working with SandboxExecutionResult objects:

```bash
python examples/api/execution_result_examples.py
```

**Result analysis:**
- Success checking patterns
- Error analysis and debugging
- Timing analysis and performance
- Result serialization
- Result comparison and statistics

**Analysis patterns:**
```python
# Comprehensive result analysis
result = sandbox.run("complex_operation()")

print(f"Success: {result.success}")
print(f"Exit code: {result.exit_code}")
print(f"Execution time: {result.execution_time:.3f}s")
print(f"Output length: {len(result.stdout)} characters")

# Convert to dictionary for storage
result_dict = result.to_dict()
```

## Advanced Examples

### Container Pool (`examples/advanced/container_pool.py`)

High-throughput concurrent execution:

```bash
python examples/advanced/container_pool.py
```

**Advanced features:**
- Container pool management
- Concurrent task execution
- Performance optimization
- Resource utilization monitoring
- Health checking

**Pool usage:**
```python
# Create container pool
pool = ContainerPool(pool_size=4, memory_limit="512m")

try:
    # Execute tasks concurrently
    tasks = ["task1_code", "task2_code", "task3_code"]
    results = pool.execute_concurrent(tasks, max_workers=4)

    for i, result_info in enumerate(results):
        print(f"Task {i}: {result_info['result'].success}")
finally:
    pool.cleanup()
```

**Performance benefits:**
- Faster execution through parallelization
- Reduced container startup overhead
- Efficient resource utilization
- Scalable architecture

## Data Files

The `examples/data/` directory contains synthetic datasets for testing:

### Sample Employee Data (`sample_data.csv`)
```csv
name,age,city,salary,department
Alice Johnson,25,New York,75000,Engineering
Bob Smith,30,London,68000,Marketing
...
```

### Sales Transactions (`sales_data.csv`)
```csv
transaction_id,date,product_id,product_name,category,quantity,unit_price,total_amount
T001,2024-01-15,P101,Wireless Headphones,Electronics,2,89.99,179.98
...
```

### Configuration (`config.json`)
```json
{
  "database": {
    "host": "localhost",
    "port": 5432,
    "name": "example_db"
  },
  "features": {
    "enable_caching": true,
    "debug_mode": false
  }
}
```

### Product Catalog (`products.json`)
```json
{
  "products": [
    {
      "id": "P101",
      "name": "Wireless Headphones",
      "category": "Electronics",
      "price": 89.99,
      "rating": 4.5
    }
  ]
}
```

## Running Examples

### Prerequisites

1. **Docker**: Ensure Docker is installed and running
2. **BioCage**: Install the BioCage package
3. **Dependencies**: Install required Python packages

```bash
# Check Docker installation
docker --version

# Install BioCage
pip install -e .

# Install example dependencies
pip install pandas numpy matplotlib
```

### Running Individual Examples

```bash
# Run from project root directory
cd /path/to/biocage

# Basic examples
python examples/basic/simple_demo.py
python examples/basic/persistent_mode.py
python examples/basic/ephemeral_mode.py

# API examples
python examples/api/orchestrator_examples.py
python examples/api/execution_result_examples.py

# Advanced examples
python examples/advanced/container_pool.py
```

### Running All Examples

```bash
# Run all basic examples
for script in examples/basic/*.py; do
    echo "Running $script..."
    python "$script"
    echo "---"
done

# Run all API examples
for script in examples/api/*.py; do
    echo "Running $script..."
    python "$script"
    echo "---"
done
```

### Expected Output

Each example produces detailed output showing:

- **Operation status**: Success/failure indicators
- **Execution details**: Timing, resource usage
- **Results**: Actual output from code execution
- **Demonstrations**: Feature-specific behaviors
- **Statistics**: Performance and utilization metrics

### Troubleshooting

If examples fail to run:

1. **Check Docker**: Ensure Docker daemon is running
2. **Check images**: Run `docker images` to verify BioCage image exists
3. **Check permissions**: Ensure user can access Docker
4. **Check dependencies**: Install missing Python packages
5. **Check paths**: Verify examples are run from correct directory

### Custom Examples

To create your own examples:

1. **Use the simple demo as a template**
2. **Import BioCageOrchestrator**
3. **Follow the context manager pattern**
4. **Include error handling**
5. **Add meaningful output and demonstrations**

Example template:
```python
#!/usr/bin/env python3
from biocage import BioCageOrchestrator

def main():
    print("My Custom BioCage Example")
    print("=" * 30)

    with BioCageOrchestrator() as sandbox:
        result = sandbox.run("print('Hello from my example!')")
        print(f"Result: {result.stdout.strip()}")

if __name__ == "__main__":
    main()
```

This completes the comprehensive examples documentation. Each example is designed to be educational, practical, and demonstrate real-world usage patterns of BioCage.