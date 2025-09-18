# BioCage Advanced Guide

This guide covers advanced BioCage features, performance optimization, complex workflows, and integration patterns for sophisticated use cases.

## Table of Contents

- [Performance Optimization](#performance-optimization)
- [Advanced Container Management](#advanced-container-management)
- [Complex File Operations](#complex-file-operations)
- [Integration Patterns](#integration-patterns)
- [Monitoring and Observability](#monitoring-and-observability)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

## Performance Optimization

### Execution Mode Selection

Choose the optimal execution mode based on your use case:

```python
from biocage import BioCageOrchestrator

# High-performance persistent mode for workflows
with BioCageOrchestrator(execution_mode="persistent") as sandbox:
    # Setup phase (one-time cost)
    sandbox.run("import pandas as pd, numpy as np, matplotlib.pyplot as plt")

    # Multiple fast executions (no import overhead)
    for dataset in datasets:
        result = sandbox.run(f"df = pd.read_csv('{dataset}'); print(len(df))")

# Maximum security ephemeral mode for untrusted code
with BioCageOrchestrator(execution_mode="ephemeral") as sandbox:
    for user_code in untrusted_submissions:
        result = sandbox.run(user_code)  # Fresh container each time
```

### Container Reuse Strategies

Optimize container lifecycle for different scenarios:

```python
# Long-running analysis session
class AnalysisSession:
    def __init__(self):
        self.sandbox = BioCageOrchestrator(
            execution_mode="persistent",
            memory_limit="2g",
            cpu_limit="4.0"
        )
        self.sandbox.start_container()
        self._setup_environment()

    def _setup_environment(self):
        """One-time setup for the session."""
        setup_code = """
import pandas as pd
import numpy as np
import scipy.stats as stats
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# Setup global configuration
pd.set_option('display.max_columns', None)
np.random.seed(42)

print("Analysis environment ready")
"""
        result = self.sandbox.run(setup_code)
        if not result.success:
            raise RuntimeError(f"Environment setup failed: {result.stderr}")

    def analyze_dataset(self, data_path: str):
        """Analyze a dataset using the persistent environment."""
        code = f"""
# Load and analyze dataset
df = pd.read_csv('{data_path}')

# Basic statistics
print(f"Dataset shape: {{df.shape}}")
print(f"Memory usage: {{df.memory_usage(deep=True).sum() / 1024**2:.1f}} MB")

# Data quality check
missing_data = df.isnull().sum()
if missing_data.any():
    print(f"Missing data: {{missing_data[missing_data > 0].to_dict()}}")

# Summary statistics
print("\\nSummary Statistics:")
print(df.describe())
"""
        return self.sandbox.run(code)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sandbox.cleanup()

# Usage
with AnalysisSession() as session:
    for dataset in large_dataset_list:
        result = session.analyze_dataset(dataset)
        print(f"Analysis complete: {result.execution_time:.2f}s")
```

### Memory Management

Implement intelligent memory management for large-scale operations:

```python
class MemoryOptimizedSandbox:
    def __init__(self, initial_memory="1g"):
        self.current_memory = initial_memory
        self.sandbox = BioCageOrchestrator(
            execution_mode="persistent",
            memory_limit=initial_memory
        )
        self.sandbox.start_container()

    def execute_with_memory_monitoring(self, code: str, max_memory="4g"):
        """Execute code with automatic memory scaling."""

        # Check current memory usage
        memory_check = self.sandbox.run("""
import psutil
process = psutil.Process()
memory_mb = process.memory_info().rss / 1024 / 1024
print(f"Current memory: {memory_mb:.1f} MB")
""")

        # Execute the actual code
        result = self.sandbox.run(code)

        # If execution failed due to memory, try with more memory
        if not result.success and "memory" in result.stderr.lower():
            print(f"Memory limit exceeded, scaling up from {self.current_memory} to {max_memory}")

            # Restart with more memory
            self.sandbox.restart_container(memory_limit=max_memory)
            self.current_memory = max_memory

            # Retry execution
            result = self.sandbox.run(code)

        return result

    def cleanup(self):
        self.sandbox.cleanup()

# Usage for memory-intensive operations
memory_sandbox = MemoryOptimizedSandbox("512m")
try:
    # This might need memory scaling
    result = memory_sandbox.execute_with_memory_monitoring("""
import numpy as np
# Create large array that might exceed initial memory limit
large_array = np.random.rand(10000, 10000)
print(f"Created array: {large_array.shape}")
print(f"Memory usage: {large_array.nbytes / 1024**3:.2f} GB")
""", max_memory="8g")

    print(f"Execution successful: {result.success}")
finally:
    memory_sandbox.cleanup()
```

### Batch Processing Optimization

Optimize for processing multiple items efficiently:

```python
class BatchProcessor:
    def __init__(self, batch_size=10):
        self.batch_size = batch_size
        self.sandbox = BioCageOrchestrator(
            execution_mode="persistent",
            memory_limit="2g"
        )
        self.sandbox.start_container()
        self._init_batch_environment()

    def _init_batch_environment(self):
        """Initialize environment for batch processing."""
        init_code = """
import json
import pandas as pd
from typing import List, Dict, Any

# Global batch storage
batch_results = []
batch_errors = []

def process_item(item_data):
    \"\"\"Process a single item.\"\"\"
    try:
        # Example processing logic
        if isinstance(item_data, dict):
            result = {
                'id': item_data.get('id'),
                'processed': True,
                'value': item_data.get('value', 0) * 2
            }
            return result
        else:
            return {'error': 'Invalid item format'}
    except Exception as e:
        return {'error': str(e)}

def process_batch(items: List[Dict[str, Any]]):
    \"\"\"Process a batch of items.\"\"\"
    results = []
    for item in items:
        result = process_item(item)
        results.append(result)
    return results

print("Batch processing environment initialized")
"""
        result = self.sandbox.run(init_code)
        if not result.success:
            raise RuntimeError(f"Batch environment init failed: {result.stderr}")

    def process_items(self, items):
        """Process items in optimized batches."""
        all_results = []

        # Process in batches
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]

            # Serialize batch data
            batch_json = json.dumps(batch)

            # Execute batch processing
            code = f"""
import json
batch_data = json.loads('''{batch_json}''')
batch_results = process_batch(batch_data)

# Report batch statistics
print(f"Processed batch of {{len(batch_data)}} items")
success_count = sum(1 for r in batch_results if 'error' not in r)
print(f"Success rate: {{success_count}}/{{len(batch_data)}}")

# Return results as JSON
results_json = json.dumps(batch_results)
print("RESULTS:" + results_json)
"""

            result = self.sandbox.run(code)

            if result.success:
                # Extract results from output
                output_lines = result.stdout.strip().split('\n')
                results_line = next((line for line in output_lines if line.startswith("RESULTS:")), None)

                if results_line:
                    results_json = results_line[8:]  # Remove "RESULTS:" prefix
                    batch_results = json.loads(results_json)
                    all_results.extend(batch_results)

                print(f"Batch {i//self.batch_size + 1}: {result.execution_time:.2f}s")
            else:
                print(f"Batch {i//self.batch_size + 1} failed: {result.stderr}")

        return all_results

    def cleanup(self):
        self.sandbox.cleanup()

# Usage example
processor = BatchProcessor(batch_size=20)
try:
    # Generate test data
    test_items = [{'id': i, 'value': i * 10} for i in range(100)]

    # Process efficiently
    results = processor.process_items(test_items)
    print(f"Processed {len(results)} items total")

finally:
    processor.cleanup()
```

## Advanced Container Management

### Dynamic Resource Allocation

Implement dynamic resource allocation based on workload:

```python
class DynamicResourceManager:
    def __init__(self):
        self.resource_profiles = {
            'light': {'memory': '256m', 'cpu': '0.5'},
            'medium': {'memory': '1g', 'cpu': '1.0'},
            'heavy': {'memory': '4g', 'cpu': '2.0'},
            'extreme': {'memory': '8g', 'cpu': '4.0'}
        }
        self.current_profile = 'medium'
        self.sandbox = None

    def analyze_code_complexity(self, code: str) -> str:
        """Analyze code to predict resource requirements."""
        # Simple heuristics for resource prediction
        lines = len(code.split('\n'))

        # Check for memory-intensive patterns
        memory_indicators = ['numpy', 'pandas', 'array', 'matrix', 'DataFrame']
        cpu_indicators = ['for', 'while', 'range(', 'multiprocessing']

        memory_score = sum(1 for indicator in memory_indicators if indicator in code)
        cpu_score = sum(1 for indicator in cpu_indicators if indicator in code)

        # Determine profile
        if memory_score >= 3 or cpu_score >= 3 or lines > 100:
            return 'extreme'
        elif memory_score >= 2 or cpu_score >= 2 or lines > 50:
            return 'heavy'
        elif memory_score >= 1 or cpu_score >= 1 or lines > 20:
            return 'medium'
        else:
            return 'light'

    def execute_with_optimal_resources(self, code: str):
        """Execute code with dynamically allocated resources."""

        # Predict required resources
        predicted_profile = self.analyze_code_complexity(code)
        print(f"Predicted resource profile: {predicted_profile}")

        # Check if we need to adjust resources
        if predicted_profile != self.current_profile or self.sandbox is None:
            if self.sandbox:
                self.sandbox.cleanup()

            # Create sandbox with optimal resources
            profile = self.resource_profiles[predicted_profile]
            self.sandbox = BioCageOrchestrator(
                execution_mode="persistent",
                memory_limit=profile['memory'],
                cpu_limit=profile['cpu']
            )
            self.current_profile = predicted_profile
            print(f"Allocated resources: {profile}")

        # Execute code
        result = self.sandbox.run(code)

        # Log resource usage
        print(f"Execution time: {result.execution_time:.3f}s")
        print(f"Resource profile: {self.current_profile}")

        return result

    def cleanup(self):
        if self.sandbox:
            self.sandbox.cleanup()

# Usage example
resource_manager = DynamicResourceManager()
try:
    # Light workload
    result1 = resource_manager.execute_with_optimal_resources("print('Hello')")

    # Heavy workload
    heavy_code = """
import numpy as np
import pandas as pd

# Create large dataset
data = np.random.rand(100000, 50)
df = pd.DataFrame(data)

# Perform computations
result = df.groupby(df.columns[0] > 0.5).agg({
    col: ['mean', 'std', 'min', 'max']
    for col in df.columns[:10]
})

print(f"Processed dataset: {df.shape}")
print(f"Result shape: {result.shape}")
"""
    result2 = resource_manager.execute_with_optimal_resources(heavy_code)

finally:
    resource_manager.cleanup()
```

### Container Pool Management

Implement container pooling for high-throughput scenarios:

```python
import threading
import queue
import time
from contextlib import contextmanager

class ContainerPool:
    def __init__(self, pool_size=3, **sandbox_kwargs):
        self.pool_size = pool_size
        self.sandbox_kwargs = sandbox_kwargs
        self.available_sandboxes = queue.Queue()
        self.in_use_sandboxes = set()
        self.lock = threading.Lock()

        # Initialize pool
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize the container pool."""
        for i in range(self.pool_size):
            sandbox = BioCageOrchestrator(
                execution_mode="persistent",
                **self.sandbox_kwargs
            )
            sandbox.start_container()
            self.available_sandboxes.put(sandbox)
            print(f"Initialized container {i+1}/{self.pool_size}")

    @contextmanager
    def get_sandbox(self, timeout=30):
        """Get a sandbox from the pool."""
        try:
            # Get available sandbox
            sandbox = self.available_sandboxes.get(timeout=timeout)

            with self.lock:
                self.in_use_sandboxes.add(sandbox)

            yield sandbox

        except queue.Empty:
            raise RuntimeError("No available sandboxes in pool")

        finally:
            # Return sandbox to pool
            with self.lock:
                if sandbox in self.in_use_sandboxes:
                    self.in_use_sandboxes.remove(sandbox)
                    self.available_sandboxes.put(sandbox)

    def execute_concurrent(self, code_list, max_workers=None):
        """Execute multiple code snippets concurrently."""
        import concurrent.futures

        if max_workers is None:
            max_workers = min(self.pool_size, len(code_list))

        def execute_code(code):
            with self.get_sandbox() as sandbox:
                return sandbox.run(code)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(execute_code, code) for code in code_list]
            results = []

            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    result = future.result()
                    results.append(result)
                    print(f"Completed task {i+1}/{len(code_list)}")
                except Exception as e:
                    print(f"Task {i+1} failed: {e}")
                    results.append(None)

        return results

    def get_pool_status(self):
        """Get current pool status."""
        with self.lock:
            return {
                'total_sandboxes': self.pool_size,
                'available': self.available_sandboxes.qsize(),
                'in_use': len(self.in_use_sandboxes)
            }

    def cleanup(self):
        """Clean up all sandboxes in the pool."""
        # Clean up in-use sandboxes
        with self.lock:
            for sandbox in list(self.in_use_sandboxes):
                sandbox.cleanup()
            self.in_use_sandboxes.clear()

        # Clean up available sandboxes
        while not self.available_sandboxes.empty():
            try:
                sandbox = self.available_sandboxes.get_nowait()
                sandbox.cleanup()
            except queue.Empty:
                break

        print("Container pool cleaned up")

# Usage example
pool = ContainerPool(pool_size=4, memory_limit="1g", cpu_limit="1.0")
try:
    # Concurrent execution example
    tasks = [
        "import time; time.sleep(1); print('Task 1 done')",
        "print('Task 2: ', sum(range(100000)))",
        "import math; print('Task 3: ', math.sqrt(12345))",
        "print('Task 4: ', 'hello'.upper())",
        "import random; print('Task 5: ', random.randint(1, 100))"
    ]

    start_time = time.time()
    results = pool.execute_concurrent(tasks)
    end_time = time.time()

    print(f"\nExecuted {len(tasks)} tasks in {end_time - start_time:.2f}s")
    print(f"Pool status: {pool.get_pool_status()}")

    for i, result in enumerate(results):
        if result and result.success:
            print(f"Task {i+1}: {result.stdout.strip()}")

finally:
    pool.cleanup()
```

## Complex File Operations

### Advanced File System Management

Handle complex file operations with sophisticated patterns:

```python
class AdvancedFileManager:
    def __init__(self):
        self.sandbox = BioCageOrchestrator(execution_mode="persistent")
        self.sandbox.start_container()
        self.exposed_paths = {}

    def expose_project_structure(self, project_root: str, container_root="/app/project"):
        """Expose an entire project structure with smart mapping."""
        import os

        exposed_mappings = {}

        # Map common project directories
        common_dirs = ['src', 'tests', 'data', 'config', 'docs', 'scripts']

        for dir_name in common_dirs:
            host_path = os.path.join(project_root, dir_name)
            if os.path.exists(host_path):
                container_path = f"{container_root}/{dir_name}"
                exposed_path = self.sandbox.expose_directory(
                    host_path,
                    container_path,
                    readonly=True
                )
                exposed_mappings[dir_name] = exposed_path
                print(f"Exposed {dir_name}: {host_path} -> {exposed_path}")

        # Expose individual important files
        important_files = ['requirements.txt', 'setup.py', 'pyproject.toml', 'README.md']

        for file_name in important_files:
            host_file = os.path.join(project_root, file_name)
            if os.path.exists(host_file):
                container_file = f"{container_root}/{file_name}"
                exposed_path = self.sandbox.expose_file(
                    host_file,
                    container_file,
                    readonly=True
                )
                exposed_mappings[file_name] = exposed_path
                print(f"Exposed {file_name}: {host_file} -> {exposed_path}")

        self.exposed_paths.update(exposed_mappings)
        return exposed_mappings

    def create_workspace_structure(self, workspace_path="/app/workspace"):
        """Create a structured workspace inside the container."""

        workspace_code = f"""
import os

# Create workspace structure
workspace = '{workspace_path}'
directories = [
    'input',
    'output',
    'temp',
    'logs',
    'cache',
    'results'
]

created_dirs = []
for dir_name in directories:
    dir_path = os.path.join(workspace, dir_name)
    os.makedirs(dir_path, exist_ok=True)
    created_dirs.append(dir_path)

print(f"Created workspace at: {{workspace}}")
print(f"Directories: {{created_dirs}}")

# Create useful helper functions
def get_workspace_path(subdir=''):
    return os.path.join('{workspace_path}', subdir)

def list_workspace():
    return os.listdir('{workspace_path}')

def clean_temp():
    import shutil
    temp_path = get_workspace_path('temp')
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)
        os.makedirs(temp_path)
    return temp_path

print("Workspace helper functions available: get_workspace_path, list_workspace, clean_temp")
"""

        result = self.sandbox.run(workspace_code)
        if result.success:
            print("Workspace structure created successfully")
            print(result.stdout)
        else:
            print(f"Failed to create workspace: {result.stderr}")

        return result.success

    def process_file_batch(self, file_paths, processing_function):
        """Process multiple files with a custom function."""

        # Expose all files
        exposed_files = {}
        for i, file_path in enumerate(file_paths):
            container_path = f"/app/input/file_{i:03d}_{os.path.basename(file_path)}"
            exposed_path = self.sandbox.expose_file(file_path, container_path, readonly=True)
            exposed_files[file_path] = exposed_path

        # Create processing script
        file_list = list(exposed_files.values())
        processing_code = f"""
import os
import json

# File processing function
{processing_function}

# Process all files
file_paths = {file_list}
results = []

for file_path in file_paths:
    try:
        result = process_file(file_path)
        results.append({{'file': file_path, 'result': result, 'success': True}})
        print(f"Processed: {{os.path.basename(file_path)}}")
    except Exception as e:
        results.append({{'file': file_path, 'error': str(e), 'success': False}})
        print(f"Failed: {{os.path.basename(file_path)}} - {{e}}")

# Save results
results_file = '/app/output/batch_results.json'
with open(results_file, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\\nProcessed {{len(file_paths)}} files")
print(f"Results saved to: {{results_file}}")

# Summary
success_count = sum(1 for r in results if r['success'])
print(f"Success rate: {{success_count}}/{len(results)}")
"""

        return self.sandbox.run(processing_code)

    def export_results(self, output_dir: str):
        """Export results from container to host."""

        export_code = f"""
import os
import shutil
import json

# Find all result files
result_files = []
workspace = '/app/workspace'

for root, dirs, files in os.walk(workspace):
    for file in files:
        if file.endswith(('.json', '.csv', '.txt', '.log')):
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, workspace)
            result_files.append((file_path, relative_path))

print(f"Found {{len(result_files)}} result files")

# Create export manifest
manifest = {{
    'export_time': os.popen('date').read().strip(),
    'files': [{{
        'container_path': container_path,
        'relative_path': relative_path,
        'size_bytes': os.path.getsize(container_path) if os.path.exists(container_path) else 0
    }} for container_path, relative_path in result_files]
}}

# Save manifest
with open('/app/output/export_manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)

print("Export manifest created")
for container_path, relative_path in result_files:
    print(f"  {{relative_path}} ({{os.path.getsize(container_path)}} bytes)")
"""

        return self.sandbox.run(export_code)

    def cleanup(self):
        self.sandbox.cleanup()

# Usage example
file_manager = AdvancedFileManager()
try:
    # Create workspace
    file_manager.create_workspace_structure()

    # Define a file processing function
    processing_function = """
def process_file(file_path):
    \"\"\"Process a single file and return results.\"\"\"
    import os

    # Get file info
    file_info = {
        'name': os.path.basename(file_path),
        'size': os.path.getsize(file_path),
        'extension': os.path.splitext(file_path)[1]
    }

    # Process based on file type
    if file_info['extension'].lower() == '.txt':
        with open(file_path, 'r') as f:
            content = f.read()
            file_info['lines'] = len(content.split('\\n'))
            file_info['words'] = len(content.split())
            file_info['chars'] = len(content)

    elif file_info['extension'].lower() == '.csv':
        # Simple CSV analysis
        with open(file_path, 'r') as f:
            lines = f.readlines()
            file_info['rows'] = len(lines) - 1  # Exclude header
            if lines:
                file_info['columns'] = len(lines[0].split(','))

    return file_info
"""

    # Create some test files (in real usage, these would be existing files)
    import tempfile
    test_files = []
    temp_dir = tempfile.mkdtemp()

    # Create test files
    for i in range(3):
        test_file = os.path.join(temp_dir, f"test_{i}.txt")
        with open(test_file, 'w') as f:
            f.write(f"This is test file {i}\\n" * (i + 1))
        test_files.append(test_file)

    # Process files
    result = file_manager.process_file_batch(test_files, processing_function)
    print("\nBatch processing result:")
    print(result.stdout)

    # Export results
    export_result = file_manager.export_results("/tmp/biocage_export")
    print("\nExport result:")
    print(export_result.stdout)

finally:
    file_manager.cleanup()
    # Clean up test files
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)
```

## Integration Patterns

### Web Service Integration

Integrate BioCage with web frameworks:

```python
from flask import Flask, request, jsonify
import asyncio
import concurrent.futures

app = Flask(__name__)

class BioCageWebService:
    def __init__(self, max_workers=4):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.sandbox_pool = ContainerPool(pool_size=max_workers)

    def execute_code_async(self, code, timeout=30):
        """Execute code asynchronously."""
        def execute():
            with self.sandbox_pool.get_sandbox() as sandbox:
                return sandbox.run(code, timeout=timeout)

        return self.executor.submit(execute)

    def cleanup(self):
        self.executor.shutdown(wait=True)
        self.sandbox_pool.cleanup()

# Global service instance
biocage_service = BioCageWebService()

@app.route('/execute', methods=['POST'])
def execute_code():
    """Execute Python code via REST API."""
    try:
        data = request.get_json()
        code = data.get('code', '')
        timeout = data.get('timeout', 30)

        if not code:
            return jsonify({'error': 'No code provided'}), 400

        # Execute code asynchronously
        future = biocage_service.execute_code_async(code, timeout)
        result = future.result(timeout=timeout + 5)  # Add buffer for container overhead

        return jsonify({
            'success': result.success,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'exit_code': result.exit_code,
            'execution_time': result.execution_time
        })

    except concurrent.futures.TimeoutError:
        return jsonify({'error': 'Execution timed out'}), 408
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    pool_status = biocage_service.sandbox_pool.get_pool_status()
    return jsonify({
        'status': 'healthy',
        'container_pool': pool_status
    })

# Cleanup on app shutdown
import atexit
atexit.register(biocage_service.cleanup)

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
```

### Jupyter Notebook Integration

Create BioCage magic commands for Jupyter:

```python
# biocage_magic.py
from IPython.core.magic import Magics, magics_class, cell_magic
from IPython.core.magic_arguments import (argument, magic_arguments, parse_argstring)
from biocage import BioCageOrchestrator

@magics_class
class BioCageMagics(Magics):

    def __init__(self, shell):
        super(BioCageMagics, self).__init__(shell)
        self.sandbox = None
        self.persistent_mode = False

    @magic_arguments()
    @argument('--persistent', action='store_true', help='Use persistent execution mode')
    @argument('--memory', type=str, default='1g', help='Memory limit')
    @argument('--cpu', type=str, default='2.0', help='CPU limit')
    @argument('--timeout', type=int, default=30, help='Execution timeout')
    @cell_magic
    def biocage(self, line, cell):
        """Execute cell content in BioCage sandbox."""
        args = parse_argstring(self.biocage, line)

        # Setup sandbox if needed
        if args.persistent and not self.sandbox:
            self.sandbox = BioCageOrchestrator(
                execution_mode='persistent',
                memory_limit=args.memory,
                cpu_limit=args.cpu
            )
            self.persistent_mode = True
            print(f"Started persistent BioCage session (memory: {args.memory}, cpu: {args.cpu})")

        # Execute code
        if self.persistent_mode and self.sandbox:
            result = self.sandbox.run(cell, timeout=args.timeout)
        else:
            # Use ephemeral mode
            with BioCageOrchestrator(
                execution_mode='ephemeral',
                memory_limit=args.memory,
                cpu_limit=args.cpu
            ) as sandbox:
                result = sandbox.run(cell, timeout=args.timeout)

        # Display results
        if result.success:
            if result.stdout:
                print(result.stdout)
        else:
            print(f"Error (exit code {result.exit_code}):")
            print(result.stderr)

        print(f"Execution time: {result.execution_time:.3f}s")

        return result

    @cell_magic
    def biocage_cleanup(self, line, cell):
        """Clean up persistent BioCage session."""
        if self.sandbox:
            self.sandbox.cleanup()
            self.sandbox = None
            self.persistent_mode = False
            print("BioCage session cleaned up")

# Load the magic
def load_ipython_extension(ipython):
    ipython.register_magic_function(BioCageMagics)

# Usage in Jupyter:
# %load_ext biocage_magic
#
# %%biocage --persistent --memory 2g
# import pandas as pd
# df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
# print(df.describe())
```

## Monitoring and Observability

### Comprehensive Monitoring System

Implement detailed monitoring for production use:

```python
import logging
import time
import threading
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import json

@dataclass
class ExecutionMetrics:
    timestamp: float
    execution_time: float
    memory_limit: str
    cpu_limit: str
    success: bool
    exit_code: int
    code_length: int
    stdout_length: int
    stderr_length: int
    container_id: Optional[str] = None

class BioCageMonitor:
    def __init__(self, log_file='biocage_metrics.log'):
        self.metrics: List[ExecutionMetrics] = []
        self.lock = threading.Lock()

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def record_execution(self, sandbox: BioCageOrchestrator, code: str, result):
        """Record execution metrics."""

        info = sandbox.get_container_info()

        metrics = ExecutionMetrics(
            timestamp=time.time(),
            execution_time=result.execution_time,
            memory_limit=info['memory_limit'],
            cpu_limit=info['cpu_limit'],
            success=result.success,
            exit_code=result.exit_code,
            code_length=len(code),
            stdout_length=len(result.stdout),
            stderr_length=len(result.stderr),
            container_id=info.get('container_id')
        )

        with self.lock:
            self.metrics.append(metrics)

        # Log execution
        self.logger.info(f"Execution: success={result.success}, time={result.execution_time:.3f}s, "
                        f"memory={info['memory_limit']}, exit_code={result.exit_code}")

        if not result.success:
            self.logger.warning(f"Execution failed: {result.stderr[:200]}")

    def get_performance_stats(self, window_minutes=60) -> Dict:
        """Get performance statistics for the specified time window."""

        current_time = time.time()
        window_start = current_time - (window_minutes * 60)

        with self.lock:
            recent_metrics = [m for m in self.metrics if m.timestamp >= window_start]

        if not recent_metrics:
            return {'message': 'No data in time window'}

        # Calculate statistics
        execution_times = [m.execution_time for m in recent_metrics]
        success_count = sum(1 for m in recent_metrics if m.success)

        stats = {
            'window_minutes': window_minutes,
            'total_executions': len(recent_metrics),
            'success_rate': (success_count / len(recent_metrics)) * 100,
            'avg_execution_time': sum(execution_times) / len(execution_times),
            'min_execution_time': min(execution_times),
            'max_execution_time': max(execution_times),
            'p95_execution_time': sorted(execution_times)[int(0.95 * len(execution_times))],
            'errors': [m for m in recent_metrics if not m.success]
        }

        return stats

    def export_metrics(self, filename: str):
        """Export metrics to JSON file."""

        with self.lock:
            data = [asdict(m) for m in self.metrics]

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        self.logger.info(f"Exported {len(data)} metrics to {filename}")

class MonitoredBioCageOrchestrator(BioCageOrchestrator):
    """BioCageOrchestrator with built-in monitoring."""

    def __init__(self, monitor: BioCageMonitor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitor = monitor

    def run(self, code: str, timeout: Optional[int] = None):
        """Execute code with monitoring."""

        start_time = time.time()
        result = super().run(code, timeout)

        # Record metrics
        self.monitor.record_execution(self, code, result)

        return result

# Usage example
monitor = BioCageMonitor('production_metrics.log')

# Use monitored orchestrator
with MonitoredBioCageOrchestrator(monitor, execution_mode='persistent') as sandbox:

    # Simulate various workloads
    test_codes = [
        "print('Hello World')",
        "import numpy as np; arr = np.random.rand(1000, 1000); print(f'Created array: {arr.shape}')",
        "for i in range(10000): pass; print('Loop completed')",
        "undefined_variable",  # This will fail
        "import time; time.sleep(0.5); print('Delayed operation')"
    ]

    for code in test_codes:
        result = sandbox.run(code)
        time.sleep(0.1)  # Brief pause between executions

# Get performance statistics
stats = monitor.get_performance_stats(window_minutes=5)
print("\nPerformance Statistics:")
print(json.dumps(stats, indent=2, default=str))

# Export metrics
monitor.export_metrics('biocage_metrics_export.json')
```

## Production Deployment

### Production-Ready Configuration

Configure BioCage for production environments:

```python
import os
import logging
from biocage import BioCageOrchestrator

class ProductionBioCageConfig:
    """Production configuration for BioCage."""

    @staticmethod
    def get_config():
        """Get production configuration from environment variables."""

        return {
            'execution_mode': os.getenv('BIOCAGE_EXECUTION_MODE', 'persistent'),
            'memory_limit': os.getenv('BIOCAGE_MEMORY_LIMIT', '1g'),
            'cpu_limit': os.getenv('BIOCAGE_CPU_LIMIT', '2.0'),
            'network_access': os.getenv('BIOCAGE_NETWORK_ACCESS', 'false').lower() == 'true',
            'default_timeout': int(os.getenv('BIOCAGE_DEFAULT_TIMEOUT', '30')),
            'image_name': os.getenv('BIOCAGE_IMAGE_NAME', 'python:3.11'),
            'remove_containers': os.getenv('BIOCAGE_REMOVE_CONTAINERS', 'true').lower() == 'true'
        }

    @staticmethod
    def setup_logging():
        """Setup production logging."""

        log_level = os.getenv('BIOCAGE_LOG_LEVEL', 'INFO')
        log_file = os.getenv('BIOCAGE_LOG_FILE', '/var/log/biocage.log')

        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

class ProductionBioCageOrchestrator(BioCageOrchestrator):
    """Production-ready BioCage orchestrator with enhanced error handling."""

    def __init__(self, *args, **kwargs):
        # Apply production configuration
        config = ProductionBioCageConfig.get_config()
        config.update(kwargs)  # Allow override

        super().__init__(**config)

        # Setup logging
        ProductionBioCageConfig.setup_logging()
        self.logger = logging.getLogger(__name__)

        # Production settings
        self.max_retries = int(os.getenv('BIOCAGE_MAX_RETRIES', '3'))
        self.retry_delay = float(os.getenv('BIOCAGE_RETRY_DELAY', '1.0'))

    def run_with_retry(self, code: str, timeout: Optional[int] = None):
        """Execute code with retry logic for production reliability."""

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                self.logger.debug(f"Execution attempt {attempt + 1}")
                result = self.run(code, timeout)

                if result.success:
                    if attempt > 0:
                        self.logger.info(f"Execution succeeded on attempt {attempt + 1}")
                    return result
                else:
                    self.logger.warning(f"Execution failed on attempt {attempt + 1}: {result.stderr}")
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)

            except Exception as e:
                last_exception = e
                self.logger.error(f"Exception on attempt {attempt + 1}: {e}")

                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    # Try to recover by restarting container
                    try:
                        self.restart_container()
                        self.logger.info("Container restarted for recovery")
                    except Exception as restart_error:
                        self.logger.error(f"Container restart failed: {restart_error}")

        # All retries exhausted
        if last_exception:
            raise last_exception
        else:
            return result  # Return last failed result

# Docker Compose configuration for production
docker_compose_yaml = """
version: '3.8'

services:
  biocage-app:
    build: .
    environment:
      - BIOCAGE_EXECUTION_MODE=persistent
      - BIOCAGE_MEMORY_LIMIT=2g
      - BIOCAGE_CPU_LIMIT=2.0
      - BIOCAGE_NETWORK_ACCESS=false
      - BIOCAGE_DEFAULT_TIMEOUT=60
      - BIOCAGE_LOG_LEVEL=INFO
      - BIOCAGE_LOG_FILE=/var/log/biocage.log
      - BIOCAGE_MAX_RETRIES=3
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./logs:/var/log
    ports:
      - "8000:8000"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
"""

# Save Docker Compose configuration
with open('docker-compose.prod.yml', 'w') as f:
    f.write(docker_compose_yaml)

print("Production configuration created")
print("Deploy with: docker-compose -f docker-compose.prod.yml up -d")
```

This comprehensive advanced guide covers the sophisticated patterns and production considerations needed for deploying BioCage in real-world scenarios. The examples demonstrate scalable, robust, and maintainable approaches to using BioCage in complex environments.