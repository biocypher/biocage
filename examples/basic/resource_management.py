#!/usr/bin/env python3
"""
Example demonstrating resource management in BioCage.

This script shows how to configure and monitor memory limits, CPU limits,
network access, and execution timeouts for secure and controlled
code execution.
"""

from biocage import BioCageOrchestrator
import time


def main():
    print("BioCage Resource Management Example")
    print("=" * 39)

    demonstrate_memory_limits()
    demonstrate_cpu_limits()
    demonstrate_network_control()
    demonstrate_timeout_management()
    demonstrate_comprehensive_configuration()


def demonstrate_memory_limits():
    """Demonstrate memory limit enforcement."""
    print("\n1. Memory Limit Management")
    print("-" * 26)

    # Test with reasonable memory limit
    print("a) Working within memory limits:")
    with BioCageOrchestrator(memory_limit="256m") as sandbox:
        result = sandbox.run("""
import sys
import numpy as np

# Check available memory info
print("Memory limit test:")

# Create a small array (should work)
try:
    small_array = np.zeros((1000, 1000))  # ~8MB
    print(f"✓ Small array created: {small_array.shape}")
    print(f"Memory usage: ~{small_array.nbytes / 1024 / 1024:.1f} MB")

    # Basic memory info
    print(f"Python object count: {len(sys.modules)}")

except Exception as e:
    print(f"✗ Small array creation failed: {e}")
""")

        print("Result:")
        print(result.stdout)

    # Test memory limit enforcement
    print("\nb) Testing memory limit enforcement:")
    with BioCageOrchestrator(memory_limit="128m") as sandbox:
        result = sandbox.run("""
import numpy as np

print("Attempting large memory allocation...")
try:
    # Try to allocate more memory than limit allows
    # 128MB limit, trying to allocate ~800MB
    large_array = np.zeros((10000, 10000))  # ~800MB
    print(f"✗ Large allocation succeeded unexpectedly: {large_array.shape}")
except MemoryError:
    print("✓ MemoryError caught - memory limit enforced")
except Exception as e:
    print(f"✓ Memory limit enforced via: {type(e).__name__}: {e}")

print("Memory limit is working properly")
""")

        print("Result:")
        print(result.stdout)


def demonstrate_cpu_limits():
    """Demonstrate CPU limit enforcement."""
    print("\n2. CPU Limit Management")
    print("-" * 23)

    print("Testing CPU limit enforcement...")

    # Test with CPU limit
    with BioCageOrchestrator(
        cpu_limit="0.5",  # Limit to 0.5 CPU cores
        execution_mode="persistent"
    ) as sandbox:

        # First, establish baseline timing
        result1 = sandbox.run("""
import time
import multiprocessing

def cpu_intensive_task(duration=1):
    \"\"\"CPU-intensive task for testing.\"\"\"
    start = time.time()
    while time.time() - start < duration:
        # Busy wait to consume CPU
        _ = sum(i * i for i in range(1000))

# Test single-threaded performance
print("Testing single-threaded CPU performance...")
start_time = time.time()
cpu_intensive_task(2)  # 2 seconds of work
single_thread_time = time.time() - start_time

print(f"Single-thread time: {single_thread_time:.2f}s")
""")

        print("Single-threaded test:")
        print(result1.stdout)

        # Test multi-threaded performance (should be limited)
        result2 = sandbox.run("""
import multiprocessing
import time

def worker_task():
    \"\"\"Worker task for multiprocessing test.\"\"\"
    # CPU-intensive work
    total = 0
    for i in range(1000000):
        total += i * i
    return total

print("Testing multi-threaded CPU performance...")
start_time = time.time()

# Try to use multiple processes (should be limited by CPU quota)
with multiprocessing.Pool(processes=4) as pool:
    results = pool.map(worker_task, range(4))

multi_thread_time = time.time() - start_time

print(f"Multi-thread time: {multi_thread_time:.2f}s")
print(f"Results count: {len(results)}")
print("Note: With CPU limits, multi-threading may not provide speedup")
""")

        print("Multi-threaded test:")
        print(result2.stdout)


def demonstrate_network_control():
    """Demonstrate network access control."""
    print("\n3. Network Access Control")
    print("-" * 25)

    # Test with network disabled (default)
    print("a) Network disabled (default):")
    with BioCageOrchestrator(network_access=False) as sandbox:
        result = sandbox.run("""
import urllib.request
import socket

print("Testing network access (should be blocked)...")

# Test HTTP request
try:
    response = urllib.request.urlopen('https://httpbin.org/get', timeout=5)
    print(f"✗ HTTP request succeeded: {response.code}")
except Exception as e:
    print(f"✓ HTTP request blocked: {type(e).__name__}")

# Test DNS resolution
try:
    ip = socket.gethostbyname('google.com')
    print(f"✗ DNS resolution succeeded: {ip}")
except Exception as e:
    print(f"✓ DNS resolution blocked: {type(e).__name__}")

print("Network access is properly disabled")
""")

        print("Result:")
        print(result.stdout)

    # Test with network enabled
    print("\nb) Network enabled:")
    with BioCageOrchestrator(network_access=True) as sandbox:
        result = sandbox.run("""
import urllib.request
import socket
import json

print("Testing network access (should work)...")

# Test DNS resolution
try:
    ip = socket.gethostbyname('httpbin.org')
    print(f"✓ DNS resolution works: httpbin.org -> {ip}")
except Exception as e:
    print(f"✗ DNS resolution failed: {e}")

# Test HTTP request
try:
    response = urllib.request.urlopen('https://httpbin.org/get', timeout=10)
    data = json.loads(response.read().decode())
    print(f"✓ HTTP request successful: {response.code}")
    print(f"Response origin: {data.get('origin', 'unknown')}")
except Exception as e:
    print(f"✗ HTTP request failed: {e}")
""")

        print("Result:")
        print(result.stdout)


def demonstrate_timeout_management():
    """Demonstrate timeout management for different scenarios."""
    print("\n4. Timeout Management")
    print("-" * 19)

    with BioCageOrchestrator() as sandbox:
        # Quick operation with appropriate timeout
        print("a) Quick operation with adequate timeout:")
        start_time = time.time()
        result1 = sandbox.run("""
import time
print("Starting quick operation...")
time.sleep(1)
print("Quick operation completed!")
""", timeout=5)

        elapsed = time.time() - start_time
        print(f"Success: {result1.success}")
        print(f"Time taken: {elapsed:.2f}s")
        print(f"Output: {result1.stdout.strip()}")

        # Slow operation that times out
        print("\nb) Slow operation with insufficient timeout:")
        start_time = time.time()
        result2 = sandbox.run("""
import time
print("Starting slow operation...")
for i in range(10):
    print(f"Step {i+1}/10")
    time.sleep(1)
print("Slow operation completed!")
""", timeout=3)  # Will timeout after 3 seconds

        elapsed = time.time() - start_time
        print(f"Success: {result2.success}")
        print(f"Exit code: {result2.exit_code}")  # 124 for timeout
        print(f"Time taken: {elapsed:.2f}s")
        print(f"Partial output: {result2.stdout.strip()}")

        # Infinite loop with timeout protection
        print("\nc) Infinite loop with timeout protection:")
        start_time = time.time()
        result3 = sandbox.run("""
import time
print("Starting infinite loop...")
counter = 0
while True:  # Infinite loop
    counter += 1
    if counter % 1000000 == 0:
        print(f"Loop iteration: {counter}")
    if counter > 10000000:  # This won't be reached
        break
print("This line won't be reached")
""", timeout=2)

        elapsed = time.time() - start_time
        print(f"Success: {result3.success}")
        print(f"Exit code: {result3.exit_code}")
        print(f"Time taken: {elapsed:.2f}s")
        print(f"Output before timeout: {result3.stdout.strip()}")

        # Dynamic timeout based on operation complexity
        print("\nd) Dynamic timeout assignment:")

        operations = [
            ("Simple calculation", "result = sum(range(1000)); print(f'Result: {result}')", 5),
            ("Medium calculation", "result = sum(i*i for i in range(100000)); print(f'Result: {result}')", 10),
            ("File operation", """
import tempfile
with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
    for i in range(1000):
        f.write(f'Line {i}\\n')
    temp_name = f.name
print(f'Created file: {temp_name}')
""", 15)
        ]

        for name, code, timeout in operations:
            print(f"\n{name} (timeout: {timeout}s):")
            start_time = time.time()
            result = sandbox.run(code, timeout=timeout)
            elapsed = time.time() - start_time

            print(f"  Success: {result.success}")
            print(f"  Time: {elapsed:.2f}s")
            if result.success:
                print(f"  Output: {result.stdout.strip()}")


def demonstrate_comprehensive_configuration():
    """Demonstrate a comprehensive resource configuration."""
    print("\n5. Comprehensive Resource Configuration")
    print("-" * 42)

    # Production-like configuration
    config = {
        "memory_limit": "512m",      # 512MB memory
        "cpu_limit": "1.0",          # 1 CPU core
        "network_access": False,     # No network access
        "execution_mode": "persistent"  # Persistent mode for efficiency
    }

    print(f"Configuration: {config}")

    with BioCageOrchestrator(**config) as sandbox:
        # Test the comprehensive setup
        result = sandbox.run("""
import psutil
import os
import sys
import time

print("Resource Configuration Test")
print("=" * 30)

# Memory information
try:
    process = psutil.Process()
    memory_info = process.memory_info()
    print(f"Memory RSS: {memory_info.rss / 1024 / 1024:.1f} MB")
    print(f"Memory VMS: {memory_info.vms / 1024 / 1024:.1f} MB")
except ImportError:
    print("psutil not available, using basic memory info")
    print("Memory tracking requires additional packages")

# CPU information
cpu_count = os.cpu_count()
print(f"Available CPUs: {cpu_count}")

# Process information
print(f"Process ID: {os.getpid()}")
print(f"Python version: {sys.version.split()[0]}")

# Test computational capability
print("\\nRunning computational test...")
start_time = time.time()
result = sum(i * i for i in range(1000000))
compute_time = time.time() - start_time

print(f"Computation result: {result}")
print(f"Computation time: {compute_time:.4f}s")

# Test memory allocation within limits
print("\\nTesting memory allocation...")
try:
    import numpy as np
    # Allocate ~50MB (should be fine with 512MB limit)
    test_array = np.zeros((6000, 1000))
    print(f"✓ Memory allocation successful: {test_array.shape}")
    print(f"Array memory: ~{test_array.nbytes / 1024 / 1024:.1f} MB")
    del test_array  # Clean up
except Exception as e:
    print(f"Memory allocation issue: {e}")

print("\\n✓ Configuration test completed successfully")
""")

        print("Comprehensive test result:")
        print(result.stdout)

        # Show execution info
        execution_info = sandbox.get_container_info()
        print(f"\nExecution Info:")
        print(f"  Strategy: {execution_info['execution_strategy']}")
        print(f"  Container ID: {execution_info['container_id'][:12]}...")
        print(f"  Memory limit: {execution_info['memory_limit']}")
        print(f"  CPU limit: {execution_info['cpu_limit']}")
        print(f"  Network access: {execution_info['network_access']}")


def demonstrate_monitoring():
    """Demonstrate resource monitoring during execution."""
    print("\n6. Resource Monitoring")
    print("-" * 21)

    with BioCageOrchestrator(
        memory_limit="256m",
        execution_mode="persistent"
    ) as sandbox:

        # Install monitoring tools
        sandbox.run("import sys")

        # Monitor resource usage over time
        result = sandbox.run("""
import time
import gc

def monitor_memory():
    \"\"\"Simple memory monitoring.\"\"\"
    import sys
    objects = len(gc.get_objects())
    return objects

print("Resource Monitoring Demo")
print("-" * 24)

# Baseline measurement
initial_objects = monitor_memory()
print(f"Initial objects: {initial_objects}")

# Create some data and monitor
data_sets = []
for i in range(5):
    # Create data
    data = list(range(i * 10000, (i + 1) * 10000))
    data_sets.append(data)

    # Monitor
    current_objects = monitor_memory()
    print(f"Step {i+1}: {current_objects} objects (+{current_objects - initial_objects})")

    time.sleep(0.1)  # Brief pause

# Clean up and monitor
print("\\nCleaning up...")
del data_sets
gc.collect()

final_objects = monitor_memory()
print(f"After cleanup: {final_objects} objects")
print(f"Net change: {final_objects - initial_objects} objects")
""")

        print("Monitoring result:")
        print(result.stdout)


if __name__ == "__main__":
    main()
    demonstrate_monitoring()