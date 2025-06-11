# BioCageManager Features & Usage

The `BioCageManager` is the core component that provides comprehensive functionality for safe code execution with state management, file system integration, and advanced container lifecycle control.

## Container Management

### Persistent vs Ephemeral Execution

The sandbox supports two execution modes:

**Ephemeral Containers** (Default with context managers):
```python
# Automatic cleanup with context manager
with BioCageManager() as sandbox:
    result = sandbox.run("print('Hello from ephemeral container!')")
    # Container automatically destroyed when exiting context
```

**Persistent Containers** (Manual lifecycle management):
```python
# Manual container management for multi-execution workflows
sandbox = BioCageManager()
sandbox.start_container(memory_limit="2g", cpu_limit="4.0")

try:
    # State persists between executions
    sandbox.run("x = 42; import pandas as pd")
    result = sandbox.run("print(f'x = {x}'); df = pd.DataFrame({'A': [1,2,3]})")
    print(result.stdout)  # "x = 42"
finally:
    sandbox.stop_container()  # Clean shutdown
```

### Container Configuration

Configure container resources and security settings:

```python
# Start container with custom resources
sandbox = BioCageManager()
sandbox.start_container(
    memory_limit="4g",        # 4GB memory limit
    cpu_limit="8.0",          # 8 CPU cores
    network_access=False      # Disabled by default for security
)

# Get container information
info = sandbox.get_container_info()
print(f"Container ID: {info['container_id'][:12]}")
print(f"Running: {info['is_running']}")
print(f"Exposed paths: {len(info['exposed_paths'])}")
```

### Context Manager Configuration

Configure containers using method chaining for cleaner code:

```python
# High-performance data science setup
with BioCageManager().configure_context_manager(
    memory_limit="8g",
    cpu_limit="4.0",
    expose_files={"/path/to/dataset.csv": "/app/data/dataset.csv"},
    expose_directories_rw={"./output": "/app/output"}
) as sandbox:
    
    sandbox.run("""
    import pandas as pd
    df = pd.read_csv('/app/data/dataset.csv')
    df.describe().to_csv('/app/output/analysis.csv')
    """)
```

## State Persistence

One of the key features of BioCageManager is state persistence between executions in the same container.

### Variable Persistence

Variables maintain their values across multiple executions:

```python
with BioCageManager() as sandbox:
    # Set variables in first execution
    sandbox.run('x = 42; y = "hello"; data = {"nums": [1,2,3]}')
    
    # Use variables in subsequent execution
    result = sandbox.run('print(f"x={x}, y={y}, sum={sum(data[\'nums\'])}")')
    print(result.stdout)  # "x=42, y=hello, sum=6"
```

### Import Persistence

Imported modules and their aliases persist between executions:

```python
sandbox = BioCageManager()
sandbox.start_container()

try:
    # Import libraries with aliases
    sandbox.run("import pandas as pd; import numpy as np")
    
    # Use imports in subsequent executions
    sandbox.run("""
    df = pd.DataFrame({'x': np.random.randn(100)})
    print(f"DataFrame shape: {df.shape}")
    """)
    
    # Imports still available
    result = sandbox.run("print(f'NumPy version: {np.__version__}')")
    print(result.stdout)
finally:
    sandbox.cleanup()
```

### Function and Class Persistence

Define functions and classes that persist across executions:

```python
with BioCageManager() as sandbox:
    # Define functions and classes
    sandbox.run("""
    def greet(name):
        return f"Hello, {name}!"
    
    class Calculator:
        def __init__(self):
            self.history = []
        
        def add(self, a, b):
            result = a + b
            self.history.append(f"{a} + {b} = {result}")
            return result
    
    calc = Calculator()
    """)
    
    # Use defined functions and objects
    result = sandbox.run("""
    message = greet("World")
    sum_result = calc.add(5, 3)
    print(f"{message} | Result: {sum_result}")
    print(f"History: {calc.history}")
    """)
    print(result.stdout)
    # Output: Hello, World! | Result: 8
    #         History: ['5 + 3 = 8']
```

### DataFrame Persistence

Pandas DataFrames and their modifications persist between executions:

```python
with BioCageManager() as sandbox:
    # Create and modify DataFrames across multiple executions
    sandbox.run("""
    import pandas as pd
    df = pd.DataFrame({
        'name': ['Alice', 'Bob', 'Charlie'],
        'age': [25, 30, 35],
        'salary': [50000, 75000, 65000]
    })
    """)
    
    # Modify DataFrame in next execution
    sandbox.run("df['bonus'] = df['salary'] * 0.1")
    
    # Access modified DataFrame
    result = sandbox.run("""
    df['total_comp'] = df['salary'] + df['bonus']
    print(df[['name', 'total_comp']].to_string())
    """)
    print(result.stdout)
```

## File System Integration

### File Exposure

Expose individual files from the host to the container:

```python
# Method 1: Manual file exposure
sandbox = BioCageManager()
container_path = sandbox.expose_file("/path/to/data.csv", "/app/shared/data.csv")

with sandbox:
    result = sandbox.run(f"""
    import pandas as pd
    df = pd.read_csv('{container_path}')
    print(f"Loaded {len(df)} rows")
    """)

# Method 2: Context manager configuration
with BioCageManager().configure_context_manager(
    expose_files={
        "/path/to/data.csv": "/app/shared/data.csv",
        "/path/to/config.json": "/app/config/settings.json"
    }
) as sandbox:
    sandbox.run("""
    import pandas as pd
    import json
    
    # Read data
    df = pd.read_csv('/app/shared/data.csv')
    
    # Read configuration
    with open('/app/config/settings.json', 'r') as f:
        config = json.load(f)
    
    print(f"Data shape: {df.shape}, Config keys: {list(config.keys())}")
    """)
```

### Directory Exposure

Expose directories with read-only or read-write access:

```python
# Read-only directory access
with BioCageManager().configure_context_manager(
    expose_directories={"/path/to/models": "/app/models"}
) as sandbox:
    result = sandbox.run("""
    import os
    model_files = os.listdir('/app/models')
    print(f"Available models: {model_files}")
    """)

# Read-write directory access
with BioCageManager().configure_context_manager(
    expose_directories_rw={"/path/to/output": "/app/output"}
) as sandbox:
    sandbox.run("""
    with open('/app/output/result.txt', 'w') as f:
        f.write('Processing completed successfully!')
    
    # Create subdirectory
    import os
    os.makedirs('/app/output/logs', exist_ok=True)
    with open('/app/output/logs/execution.log', 'w') as f:
        f.write('Execution log entry')
    """)

# Combined read-only input and read-write output
with BioCageManager().configure_context_manager(
    expose_directories={"/path/to/input": "/app/input"},      # Read-only
    expose_directories_rw={"/path/to/output": "/app/output"}  # Read-write
) as sandbox:
    sandbox.run("""
    # Read from input directory
    with open('/app/input/data.txt', 'r') as f:
        data = f.read()
    
    # Process and write to output directory
    processed_data = data.upper()
    with open('/app/output/processed.txt', 'w') as f:
        f.write(processed_data)
    
    print(f"Processed {len(data)} characters")
    """)
```

### Temporary File Creation

Create temporary files with custom content that are automatically cleaned up:

```python
with BioCageManager() as sandbox:
    # Create temporary CSV file
    csv_content = """name,age,city
Alice,25,New York
Bob,30,San Francisco
Charlie,35,Boston"""
    
    temp_csv_path = sandbox.create_temp_file(csv_content, suffix=".csv")
    
    # Create temporary JSON file
    json_content = '{"config": {"batch_size": 100, "learning_rate": 0.001}}'
    temp_json_path = sandbox.create_temp_file(json_content, suffix=".json")
    
    result = sandbox.run(f"""
    import pandas as pd
    import json
    
    # Load temporary CSV
    df = pd.read_csv('{temp_csv_path}')
    print(f"Loaded {len(df)} rows from CSV")
    
    # Load temporary JSON
    with open('{temp_json_path}', 'r') as f:
        config = json.load(f)
    print(f"Config: {{config['config']}}")
    """)
    
    print(result.stdout)
    # Temporary files are automatically cleaned up when context exits
```

## Error Handling and Reporting

### Basic Error Handling

Handle different types of errors gracefully:

```python
def safe_execute(code, description=""):
    try:
        with BioCageManager() as sandbox:
            result = sandbox.run(code, timeout=30, shutdown_on_failure=False)
            
            if result.success:
                return f"✅ {description}: {result.stdout.strip()}"
            else:
                return f"❌ {description} failed: {result.stderr.strip()}"
                
    except Exception as e:
        return f"🚨 System error in {description}: {e}"

# Test different error scenarios
print(safe_execute("print('Hello World!')", "Basic execution"))
print(safe_execute("print('Hello'  # Missing parenthesis", "Syntax error"))
print(safe_execute("print(undefined_var)", "Name error"))
print(safe_execute("x = 1 / 0", "Runtime error"))
```

### Enhanced Error Reporting

Provide detailed error categorization with debugging hints:

```python
def enhanced_error_reporting(code, description):
    with BioCageManager() as sandbox:
        result = sandbox.run(code, shutdown_on_failure=False)
        
        if result.stderr:
            stderr_lower = result.stderr.lower()
            
            if "syntaxerror" in stderr_lower:
                return f"❌ Syntax Error in {description}:\n{result.stderr}\n💡 Check for missing parentheses, quotes, or colons."
            elif "nameerror" in stderr_lower:
                return f"❌ Name Error in {description}:\n{result.stderr}\n💡 Variable not defined. Define variables before using them."
            elif "zerodivisionerror" in stderr_lower:
                return f"❌ Division by Zero in {description}:\n{result.stderr}\n💡 Add a check to ensure denominator is not zero."
            elif "importerror" in stderr_lower or "modulenotfounderror" in stderr_lower:
                return f"❌ Import Error in {description}:\n{result.stderr}\n💡 Module not available. Check spelling or install the package."
            elif "typeerror" in stderr_lower:
                return f"❌ Type Error in {description}:\n{result.stderr}\n💡 Check data types and function arguments."
            elif "indexerror" in stderr_lower:
                return f"❌ Index Error in {description}:\n{result.stderr}\n💡 Index out of range. Check list/array bounds."
            elif "keyerror" in stderr_lower:
                return f"❌ Key Error in {description}:\n{result.stderr}\n💡 Dictionary key not found. Check key spelling."
            else:
                return f"❌ Runtime Error in {description}:\n{result.stderr}\n💡 Check the error message above for details."
        
        return f"✅ {description}: {result.stdout}"

# Usage examples
print(enhanced_error_reporting("print(hello)", "Variable reference"))
print(enhanced_error_reporting("import nonexistent_module", "Module import"))
print(enhanced_error_reporting("x = [1,2,3]; print(x[10])", "List indexing"))
```

## Security and Resource Management

### Timeout and Resource Controls

Control execution timeouts and resource usage:

```python
# Timeout handling
with BioCageManager() as sandbox:
    # This will timeout after 5 seconds
    result = sandbox.run("import time; time.sleep(10)", timeout=5)
    
    if result.exit_code == 124:  # Timeout exit code
        print("⏰ Code execution timed out")
    else:
        print(f"✅ Completed in {result.execution_time:.2f}s")

# Resource monitoring
with BioCageManager().configure_context_manager(
    memory_limit="1g",
    cpu_limit="2.0"
) as sandbox:
    
    # Monitor container resources
    info = sandbox.get_container_info()
    print(f"Container: {info['container_id'][:12]}")
    print(f"Memory limit: 1GB, CPU limit: 2.0 cores")
    
    # Execute memory-intensive operation
    result = sandbox.run("""
    import numpy as np
    # Create large array (within memory limits)
    large_array = np.random.randn(1000, 1000)
    print(f"Created array shape: {large_array.shape}")
    print(f"Memory usage: ~{large_array.nbytes / 1024 / 1024:.2f} MB")
    """)
    
    print(f"Execution time: {result.execution_time:.3f}s")
```

### Failure Handling and Container Shutdown

Automatic container shutdown on critical failures:

```python
def robust_execution(code_snippets):
    """Execute multiple code snippets with failure isolation."""
    results = []
    
    for i, code in enumerate(code_snippets):
        try:
            with BioCageManager() as sandbox:
                # Enable automatic shutdown on failure
                result = sandbox.run(code, shutdown_on_failure=True)
                
                if result.success:
                    results.append(f"✅ Snippet {i+1}: Success")
                else:
                    results.append(f"❌ Snippet {i+1}: {result.stderr.strip()}")
                    
        except Exception as e:
            results.append(f"🚨 Snippet {i+1}: Critical failure - {e}")
    
    return results

# Test with various code snippets
snippets = [
    "print('Hello World!')",           # Success
    "x = 1 / 0",                      # Runtime error
    "import sys; sys.exit(1)",        # Explicit exit
    "print('After error')",           # Should still work
]

for result in robust_execution(snippets):
    print(result)
```

## Common Usage Patterns

### Multi-Step Data Analysis Workflow

```python
def data_analysis_workflow(data_path, output_dir):
    """Complete data analysis workflow with state persistence."""
    
    # Configure sandbox with input data and output directory
    with BioCageManager().configure_context_manager(
        memory_limit="4g",
        cpu_limit="2.0",
        expose_files={data_path: "/app/data/dataset.csv"},
        expose_directories_rw={output_dir: "/app/output"}
    ) as sandbox:
        
        # Step 1: Load and explore data
        result1 = sandbox.run("""
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        
        # Load dataset
        df = pd.read_csv('/app/data/dataset.csv')
        print(f"Dataset shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        
        # Basic statistics
        print("\\nDataset Info:")
        print(df.info())
        """)
        
        # Step 2: Data cleaning (state persists)
        result2 = sandbox.run("""
        # Clean data - variables from step 1 are still available
        df_clean = df.dropna()
        print(f"After cleaning: {df_clean.shape}")
        
        # Save cleaning report
        with open('/app/output/cleaning_report.txt', 'w') as f:
            f.write(f"Original shape: {df.shape}\\n")
            f.write(f"Cleaned shape: {df_clean.shape}\\n")
            f.write(f"Rows removed: {len(df) - len(df_clean)}\\n")
        """)
        
        # Step 3: Analysis and visualization
        result3 = sandbox.run("""
        # Perform analysis - all previous variables available
        summary_stats = df_clean.describe()
        
        # Save results
        summary_stats.to_csv('/app/output/summary_statistics.csv')
        
        print("Analysis completed successfully!")
        print(f"Summary statistics saved for {len(df_clean)} rows")
        """)
        
        return {
            "exploration": result1.stdout,
            "cleaning": result2.stdout, 
            "analysis": result3.stdout
        }

# Usage
# results = data_analysis_workflow('/path/to/data.csv', './analysis_output')
```

### Secure Agent Code Execution

```python
import time

class SecureCodeAgent:
    """Agent for secure execution of AI-generated code."""
    
    def __init__(self, max_execution_time=60, memory_limit="2g"):
        self.max_execution_time = max_execution_time
        self.memory_limit = memory_limit
        self.execution_history = []
    
    def execute_code(self, code, context_description=""):
        """Execute code with comprehensive error handling and logging."""
        
        execution_record = {
            "timestamp": time.time(),
            "context": context_description,
            "code_preview": code[:100] + "..." if len(code) > 100 else code,
        }
        
        try:
            with BioCageManager().configure_context_manager(
                memory_limit=self.memory_limit,
                cpu_limit="1.0"
            ) as sandbox:
                
                result = sandbox.run(
                    code, 
                    timeout=self.max_execution_time,
                    shutdown_on_failure=True
                )
                
                execution_record.update({
                    "success": result.success,
                    "execution_time": result.execution_time,
                    "output": result.stdout[:500],  # Limit output size
                    "error": result.stderr[:500] if result.stderr else None
                })
                
                # Enhanced error categorization for agents
                if not result.success:
                    error_type = self._categorize_error(result.stderr)
                    execution_record["error_category"] = error_type
                    execution_record["suggested_fix"] = self._suggest_fix(error_type)
                
                self.execution_history.append(execution_record)
                return execution_record
                
        except Exception as e:
            execution_record.update({
                "success": False,
                "error": str(e),
                "error_category": "system_error",
                "suggested_fix": "Check system resources and Docker availability"
            })
            
            self.execution_history.append(execution_record)
            return execution_record
    
    def _categorize_error(self, stderr):
        """Categorize errors for agent understanding."""
        stderr_lower = stderr.lower()
        
        if "syntaxerror" in stderr_lower:
            return "syntax_error"
        elif "nameerror" in stderr_lower:
            return "undefined_variable"
        elif "importerror" in stderr_lower or "modulenotfounderror" in stderr_lower:
            return "missing_module"
        elif "zerodivisionerror" in stderr_lower:
            return "division_by_zero"
        elif "typeerror" in stderr_lower:
            return "type_mismatch"
        elif "indexerror" in stderr_lower:
            return "index_out_of_bounds"
        elif "keyerror" in stderr_lower:
            return "key_not_found"
        else:
            return "runtime_error"
    
    def _suggest_fix(self, error_category):
        """Provide fixing suggestions based on error category."""
        suggestions = {
            "syntax_error": "Check Python syntax: parentheses, quotes, indentation",
            "undefined_variable": "Define the variable before using it",
            "missing_module": "Import the required module or check if it's available",
            "division_by_zero": "Add a check to ensure denominator is not zero",
            "type_mismatch": "Check data types and function argument compatibility",
            "index_out_of_bounds": "Verify list/array indices are within bounds",
            "key_not_found": "Check dictionary key spelling and existence",
            "runtime_error": "Review the error message and code logic"
        }
        return suggestions.get(error_category, "Review the error message and code logic")
    
    def get_execution_summary(self):
        """Get summary of all executions."""
        total = len(self.execution_history)
        successful = sum(1 for record in self.execution_history if record["success"])
        
        return {
            "total_executions": total,
            "successful_executions": successful,
            "success_rate": successful / total if total > 0 else 0,
            "average_execution_time": sum(
                record.get("execution_time", 0) 
                for record in self.execution_history
            ) / total if total > 0 else 0
        }

# Usage example
agent = SecureCodeAgent(max_execution_time=30, memory_limit="1g")

# Execute various code snippets
codes = [
    "print('Hello from secure agent!')",
    "import pandas as pd; df = pd.DataFrame({'x': [1,2,3]}); print(df)",
    "print(undefined_variable)",  # This will fail
    "x = [1,2,3]; print(sum(x))"
]

for i, code in enumerate(codes):
    result = agent.execute_code(code, f"Test execution {i+1}")
    print(f"Execution {i+1}: {'✅' if result['success'] else '❌'} "
          f"({result.get('execution_time', 0):.3f}s)")
    
    if not result['success']:
        print(f"  Error: {result['error_category']}")
        print(f"  Suggestion: {result['suggested_fix']}")

# Get execution summary
summary = agent.get_execution_summary()
print(f"\nSummary: {summary['successful_executions']}/{summary['total_executions']} "
      f"successful ({summary['success_rate']:.1%})")
```

## Migration Guide

### From Basic Usage to Advanced Features

If you're currently using basic sandbox functionality and want to leverage advanced features:

```python
# Old basic usage
from biocage import BioCageManager

with BioCageManager() as sandbox:
    result = sandbox.run("print('Hello')")

# New advanced usage with state persistence and file integration
sandbox = BioCageManager()
sandbox.start_container(memory_limit="2g")

# Expose data files
data_path = sandbox.expose_file("/path/to/data.csv", "/app/data.csv")

try:
    # Multi-step workflow with state persistence
    sandbox.run("import pandas as pd; df = pd.read_csv('/app/data.csv')")
    sandbox.run("processed_df = df.dropna(); summary = processed_df.describe()")
    result = sandbox.run("print(f'Processed {len(processed_df)} rows')")
finally:
    sandbox.stop_container()
```

## Best Practices

### Resource Management
- Use context managers for automatic cleanup
- Set appropriate memory and CPU limits
- Monitor execution times and adjust timeouts

### Security
- Keep network access disabled unless specifically needed
- Use read-only file access when possible
- Enable automatic shutdown on failures for critical applications

### Performance
- Use persistent containers for multi-step workflows
- Leverage state persistence to avoid re-importing libraries
- Pre-configure containers with required resources

### Error Handling
- Implement comprehensive error categorization
- Provide user-friendly error messages with debugging hints
- Log execution history for debugging and monitoring

---

*For more information, see the [API Reference](modules.md) and [Docker Setup Guide](docker-setup.md).* 