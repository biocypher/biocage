#!/usr/bin/env python3
"""
Example demonstrating BioCageOrchestrator API usage.

This script covers all major BioCageOrchestrator methods and features,
including configuration options, file operations, container management,
and information retrieval.
"""

from biocage import BioCageOrchestrator
import tempfile
import os
from pathlib import Path


def main():
    print("BioCageOrchestrator API Examples")
    print("=" * 35)

    demonstrate_basic_api()
    demonstrate_configuration_options()
    demonstrate_file_operations_api()
    demonstrate_container_management_api()
    demonstrate_information_methods()
    demonstrate_advanced_execution()


def demonstrate_basic_api():
    """Demonstrate basic BioCageOrchestrator API usage."""
    print("\n1. Basic API Usage")
    print("-" * 18)

    # Basic constructor and context manager
    print("a) Basic constructor:")
    orchestrator = BioCageOrchestrator()
    print(f"Created orchestrator: {type(orchestrator).__name__}")
    print(f"Execution mode: {orchestrator.execution_mode}")
    print(f"Memory limit: {orchestrator.memory_limit}")
    print(f"CPU limit: {orchestrator.cpu_limit}")
    orchestrator.cleanup()

    # Context manager usage
    print("\nb) Context manager usage:")
    with BioCageOrchestrator() as sandbox:
        print("Inside context manager")
        result = sandbox.run("print('Hello from API')")
        print(f"Execution success: {result.success}")
        print(f"Output: {result.stdout.strip()}")
    print("Context manager automatically cleaned up")

    # Manual lifecycle management
    print("\nc) Manual lifecycle management:")
    sandbox = BioCageOrchestrator()
    try:
        # Check if running
        print(f"Is running: {sandbox.is_running}")

        # Get container info to validate
        try:
            info = sandbox.get_container_info()
            print(f"Environment valid: {info is not None}")
        except Exception as e:
            print(f"Environment validation failed: {e}")

        # Execute code
        result = sandbox.run("x = 42; print(f'The answer is {x}')")
        print(f"Manual execution result: {result.stdout.strip()}")

    finally:
        # Always cleanup
        sandbox.cleanup()
        print("Manual cleanup completed")


def demonstrate_configuration_options():
    """Demonstrate different configuration options."""
    print("\n2. Configuration Options")
    print("-" * 24)

    configurations = [
        {
            "name": "Default Configuration",
            "config": {}
        },
        {
            "name": "Memory Limited",
            "config": {
                "memory_limit": "256m",
                "cpu_limit": "0.5"
            }
        },
        {
            "name": "Network Enabled",
            "config": {
                "network_access": True
            }
        },
        {
            "name": "Ephemeral Mode",
            "config": {
                "execution_mode": "ephemeral"
            }
        },
        {
            "name": "Persistent Mode",
            "config": {
                "execution_mode": "persistent",
                "memory_limit": "512m"
            }
        }
    ]

    for config_info in configurations:
        name = config_info["name"]
        config = config_info["config"]

        print(f"\n{name}:")
        print(f"Config: {config}")

        with BioCageOrchestrator(**config) as sandbox:
            # Test basic functionality
            result = sandbox.run("import sys; print(f'Python {sys.version.split()[0]}')")

            if result.success:
                print(f"Result: {result.stdout.strip()}")
            else:
                print(f"Error: {result.stderr.strip()}")

            # Get container info
            info = sandbox.get_container_info()
            print(f"Mode: {info['execution_mode']}")
            print(f"Memory: {info['memory_limit']}")
            print(f"Network: {info['network_access']}")


def demonstrate_file_operations_api():
    """Demonstrate file operation APIs."""
    print("\n3. File Operations API")
    print("-" * 22)

    # Create temporary test files
    temp_dir = Path(tempfile.gettempdir()) / "biocage_api_test"
    temp_dir.mkdir(exist_ok=True)

    # Create test files
    csv_file = temp_dir / "test.csv"
    csv_file.write_text("name,value\nAlice,100\nBob,200\n")

    json_file = temp_dir / "test.json"
    json_file.write_text('{"key": "value", "number": 42}')

    try:
        with BioCageOrchestrator() as sandbox:
            print("a) expose_file() method:")

            # Expose single file
            container_csv = sandbox.expose_file(
                str(csv_file),
                "/app/data.csv",
                readonly=True
            )
            print(f"Exposed CSV: {csv_file} -> {container_csv}")

            # Use exposed file
            result = sandbox.run(f"""
import pandas as pd
df = pd.read_csv('{container_csv}')
print(f'CSV shape: {{df.shape}}')
print(f'Names: {{list(df["name"])}}')
""")
            print(f"CSV processing result: {result.stdout.strip()}")

            print("\nb) expose_directory() method:")

            # Expose entire directory
            container_dir = sandbox.expose_directory(
                str(temp_dir),
                "/app/files",
                readonly=True
            )
            print(f"Exposed directory: {temp_dir} -> {container_dir}")

            # List directory contents
            result = sandbox.run(f"""
import os
files = os.listdir('{container_dir}')
print(f'Directory contains: {{files}}')

# Process JSON file
import json
with open('{container_dir}/test.json') as f:
    data = json.load(f)
print(f'JSON data: {{data}}')
""")
            print(f"Directory processing result: {result.stdout.strip()}")

            print("\nc) execute_with_files() method:")

            # Execute with temporary files
            temp_files = {
                '/tmp/config.ini': """
[settings]
debug = true
max_items = 100

[database]
host = localhost
port = 5432
""",
                '/tmp/data.txt': "Line 1\nLine 2\nLine 3\n"
            }

            result = sandbox.execute_with_files("""
import configparser
import os

# Read config file
config = configparser.ConfigParser()
config.read('/tmp/config.ini')

debug = config.getboolean('settings', 'debug')
max_items = config.getint('settings', 'max_items')

print(f'Debug mode: {debug}')
print(f'Max items: {max_items}')

# Read text file
with open('/tmp/data.txt') as f:
    lines = f.readlines()

print(f'Text file has {len(lines)} lines')
""", temp_files)

            print(f"execute_with_files result: {result.stdout.strip()}")

    finally:
        # Cleanup test files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def demonstrate_container_management_api():
    """Demonstrate container management APIs."""
    print("\n4. Container Management API")
    print("-" * 27)

    print("a) Automatic container management (context manager):")
    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        # Get initial container info
        info = sandbox.get_container_info()
        initial_container = info.get('container_id', 'None')
        print(f"Initial container: {initial_container[:12] if initial_container else 'None'}")

        # Execute some code to establish state
        sandbox.run("x = 100; y = 200")
        result = sandbox.run("print(f'Initial state: x={x}, y={y}')")
        print(f"Initial state: {result.stdout.strip()}")

        print("\nb) restart_container() method:")

        # Restart container
        new_container_id = sandbox.restart_container()
        print(f"Restarted container: {new_container_id[:12]}")

        # Verify state persistence
        result = sandbox.run("print(f'After restart: x={x}, y={y}')")
        print(f"State after restart: {result.stdout.strip()}")

        print("\nc) Container configuration override:")

        # Restart with different configuration
        new_container_id = sandbox.restart_container(
            memory_limit="256m",
            cpu_limit="1.0"
        )
        print(f"Restarted with new config: {new_container_id[:12]}")

        # Check new configuration
        info = sandbox.get_container_info()
        print(f"New memory limit: {info['memory_limit']}")
        print(f"New CPU limit: {info['cpu_limit']}")

    print("\nd) Manual container management:")
    sandbox = BioCageOrchestrator(execution_mode="persistent")
    try:
        # Manual start
        container_id = sandbox.start_container()
        print(f"Manually started container: {container_id[:12]}")

        # Execute code
        result = sandbox.run("print('Manual container management')")
        print(f"Execution result: {result.stdout.strip()}")

    finally:
        # Manual cleanup
        sandbox.cleanup()
        print("Manual cleanup completed")


def demonstrate_information_methods():
    """Demonstrate information and monitoring methods."""
    print("\n5. Information Methods")
    print("-" * 21)

    with BioCageOrchestrator(
        execution_mode="persistent",
        memory_limit="512m",
        cpu_limit="1.5",
        network_access=True
    ) as sandbox:

        print("a) get_container_info() method:")
        info = sandbox.get_container_info()

        # Display key information
        important_keys = [
            'execution_mode', 'execution_strategy', 'container_id',
            'memory_limit', 'cpu_limit', 'network_access',
            'image_name'
        ]

        for key in important_keys:
            value = info.get(key, 'N/A')
            if key == 'container_id' and value != 'N/A':
                value = f"{value[:12]}..."
            print(f"  {key}: {value}")

        print("\nb) is_running property:")
        running = sandbox.is_running
        print(f"Sandbox running: {running}")

        if running:
            result = sandbox.run("print('Sandbox is running for execution')")
            print(f"Test execution: {result.stdout.strip()}")

        print("\nc) container status check:")
        try:
            container_info = sandbox.get_container_info()
            print(f"Container healthy: {container_info.get('container_healthy', False)}")
            print(f"Container ID: {container_info.get('container_id', 'N/A')[:12]}...")
        except Exception as e:
            print(f"Container status check failed: {e}")

        print("\nd) Execution result information:")

        # Execute code and examine result details
        result = sandbox.run("""
import time
start = time.time()
total = sum(i * i for i in range(100000))
end = time.time()
print(f'Calculated sum of squares: {total}')
print(f'Computation took: {end - start:.4f} seconds')
""")

        print(f"Result success: {result.success}")
        print(f"Exit code: {result.exit_code}")
        print(f"Execution time: {result.execution_time:.4f} seconds")
        print(f"Output length: {len(result.stdout)} characters")
        print(f"Error length: {len(result.stderr)} characters")

        # Convert result to dict
        result_dict = result.to_dict()
        print(f"Result as dict keys: {list(result_dict.keys())}")


def demonstrate_advanced_execution():
    """Demonstrate advanced execution features."""
    print("\n6. Advanced Execution Features")
    print("-" * 30)

    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        print("a) Timeout handling:")

        # Quick execution
        result1 = sandbox.run("print('Quick operation')", timeout=5)
        print(f"Quick operation: {result1.success}, time: {result1.execution_time:.3f}s")

        # Timed operation (will timeout)
        result2 = sandbox.run("""
import time
print('Starting slow operation...')
time.sleep(10)
print('Slow operation completed')
""", timeout=3)

        print(f"Slow operation: {result2.success}, time: {result2.execution_time:.3f}s")
        print(f"Exit code: {result2.exit_code}")  # 124 for timeout
        print(f"Partial output: '{result2.stdout.strip()}'")

        print("\nb) Multi-line code execution:")

        complex_code = """
# Multi-line Python script
import math
import random

class Calculator:
    def __init__(self):
        self.history = []

    def calculate(self, operation, a, b):
        if operation == 'add':
            result = a + b
        elif operation == 'multiply':
            result = a * b
        elif operation == 'power':
            result = math.pow(a, b)
        else:
            result = None

        self.history.append((operation, a, b, result))
        return result

# Use the calculator
calc = Calculator()
results = []

for _ in range(3):
    a = random.randint(1, 10)
    b = random.randint(1, 5)
    op = random.choice(['add', 'multiply', 'power'])
    result = calc.calculate(op, a, b)
    results.append(f'{a} {op} {b} = {result}')

print('Calculator Results:')
for result in results:
    print(f'  {result}')

print(f'Total operations: {len(calc.history)}')
"""

        result = sandbox.run(complex_code)
        print("Complex code execution:")
        print(result.stdout)

        print("\nc) Error handling and recovery:")

        # Execute code that will fail
        error_result = sandbox.run("undefined_function()")
        print(f"Error execution success: {error_result.success}")
        print(f"Error message: {error_result.stderr.strip()}")

        # Recovery - container should still work
        recovery_result = sandbox.run("print('Recovery successful')")
        print(f"Recovery success: {recovery_result.success}")
        print(f"Recovery output: {recovery_result.stdout.strip()}")

        print("\nd) State persistence verification:")

        # Verify previous calculator is still available
        persistence_result = sandbox.run("""
try:
    print(f'Calculator history has {len(calc.history)} entries')
    print('Previous calculations still available!')
except NameError:
    print('Calculator not found - state not preserved')
""")
        print(f"Persistence check: {persistence_result.stdout.strip()}")


if __name__ == "__main__":
    main()