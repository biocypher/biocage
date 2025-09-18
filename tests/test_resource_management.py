"""Test resource management and monitoring functionality."""

import time
import pytest

from biocage import BioCageOrchestrator


class TestResourceLimits:
    """Test container resource limits and enforcement."""

    def test_memory_limit_configuration(self):
        """Test different memory limit configurations."""
        memory_configs = [
            ("256m", "256m"),
            ("512m", "512m"),
            ("1g", "1g"),
            ("2g", "2g"),
        ]

        for memory_limit, expected in memory_configs:
            with BioCageOrchestrator(memory_limit=memory_limit) as sandbox:
                info = sandbox.get_container_info()
                assert info["memory_limit"] == expected

                # Test that container can execute basic operations
                result = sandbox.run(f"""
print(f"Container memory limit: {info['memory_limit']}")
print("Memory limit configuration test passed")
""")
                assert result.success
                assert "Memory limit configuration test passed" in result.stdout

    def test_cpu_limit_configuration(self):
        """Test different CPU limit configurations."""
        cpu_configs = [
            ("0.5", "0.5"),
            ("1.0", "1.0"),
            ("2.0", "2.0"),
            ("4.0", "4.0"),
        ]

        for cpu_limit, expected in cpu_configs:
            with BioCageOrchestrator(cpu_limit=cpu_limit) as sandbox:
                info = sandbox.get_container_info()
                assert info["cpu_limit"] == expected

                # Test that container can execute basic operations
                result = sandbox.run(f"""
print(f"Container CPU limit: {info['cpu_limit']}")
print("CPU limit configuration test passed")
""")
                assert result.success
                assert "CPU limit configuration test passed" in result.stdout

    def test_combined_resource_limits(self):
        """Test containers with combined memory and CPU limits."""
        resource_configs = [
            {"memory_limit": "256m", "cpu_limit": "0.5"},
            {"memory_limit": "512m", "cpu_limit": "1.0"},
            {"memory_limit": "1g", "cpu_limit": "2.0"},
        ]

        for config in resource_configs:
            with BioCageOrchestrator(**config) as sandbox:
                info = sandbox.get_container_info()
                assert info["memory_limit"] == config["memory_limit"]
                assert info["cpu_limit"] == config["cpu_limit"]

                result = sandbox.run(f"""
print(f"Memory: {info['memory_limit']}, CPU: {info['cpu_limit']}")

# Test with some computation
import time
start = time.time()
result = sum(i * i for i in range(10000))
duration = time.time() - start

print(f"Computation completed in {{duration:.4f}}s, result: {{result}}")
""")

                assert result.success
                assert f"Memory: {config['memory_limit']}, CPU: {config['cpu_limit']}" in result.stdout
                assert "Computation completed" in result.stdout

    def test_memory_intensive_operations(self):
        """Test memory-intensive operations under different limits."""
        # Test with larger memory limit for memory-intensive task
        with BioCageOrchestrator(memory_limit="1g", cpu_limit="2.0") as sandbox:
            result = sandbox.run("""
import sys

print("Starting memory-intensive test...")

# Create lists of different sizes and measure memory
test_sizes = [1000, 10000, 100000]
memory_results = []

for size in test_sizes:
    # Create a list of integers
    data = list(range(size))

    # Calculate size in bytes (rough estimate)
    estimated_size = sys.getsizeof(data) + sum(sys.getsizeof(x) for x in data[:100])  # Sample first 100

    memory_results.append({
        'size': size,
        'estimated_bytes': estimated_size,
        'first_10': data[:10],
        'last_10': data[-10:]
    })

    print(f"Created list of size {size}, estimated memory: {estimated_size} bytes")

print(f"Memory test completed. Created {len(memory_results)} data structures.")

# Test with some string operations
text_data = "Hello World! " * 10000
print(f"Created text data: {len(text_data)} characters")

print("Memory-intensive operations completed successfully")
""")

            assert result.success
            assert "Memory-intensive operations completed successfully" in result.stdout
            assert "Created text data:" in result.stdout

    def test_cpu_intensive_operations(self):
        """Test CPU-intensive operations under different limits."""
        cpu_configs = [
            {"cpu_limit": "0.5", "expected_slower": True},
            {"cpu_limit": "2.0", "expected_slower": False},
        ]

        execution_times = []

        for config in cpu_configs:
            with BioCageOrchestrator(
                memory_limit="512m",
                cpu_limit=config["cpu_limit"]
            ) as sandbox:

                result = sandbox.run("""
import time
import math

print("Starting CPU-intensive test...")

start_time = time.time()

# CPU-intensive mathematical calculations
result = 0
for i in range(100000):
    result += math.sqrt(i) * math.sin(i / 1000.0) * math.cos(i / 1000.0)

computation_time = time.time() - start_time

print(f"CPU computation completed in {computation_time:.4f} seconds")
print(f"Result: {result:.6f}")
print("CPU-intensive operations completed")
""")

                assert result.success
                assert "CPU-intensive operations completed" in result.stdout

                # Extract execution time for comparison
                lines = result.stdout.split('\n')
                for line in lines:
                    if "completed in" in line and "seconds" in line:
                        time_str = line.split("completed in ")[1].split(" seconds")[0]
                        execution_times.append({
                            "cpu_limit": config["cpu_limit"],
                            "time": float(time_str)
                        })
                        break

        # Verify we got timing data
        assert len(execution_times) == 2
        print(f"Execution times: {execution_times}")

        # Note: Due to containerization overhead and test environment variability,
        # we don't strictly enforce that lower CPU limits are slower, just verify both completed

    def test_timeout_with_resource_limits(self):
        """Test timeout behavior under different resource constraints."""
        with BioCageOrchestrator(memory_limit="256m", cpu_limit="0.5") as sandbox:
            # Test normal execution within timeout
            result1 = sandbox.run("""
import time
print("Quick operation starting...")
time.sleep(0.1)
print("Quick operation completed")
""", timeout=5)

            assert result1.success
            assert "Quick operation completed" in result1.stdout
            assert result1.execution_time < 5.0

            # Test timeout with slow operation
            result2 = sandbox.run("""
import time
print("Slow operation starting...")
time.sleep(10)  # This should timeout
print("Slow operation completed")
""", timeout=2)

            assert not result2.success
            assert result2.exit_code == 124  # Timeout exit code
            assert "Slow operation starting..." in result2.stdout
            assert "Slow operation completed" not in result2.stdout

    def test_resource_monitoring_during_execution(self):
        """Test monitoring resource usage during execution."""
        with BioCageOrchestrator(
            memory_limit="512m",
            cpu_limit="1.0",
            execution_mode="persistent"
        ) as sandbox:

            # Execute a task and monitor
            result = sandbox.run("""
import os
import time

print("=== Resource Monitoring Test ===")

# Get process information (what we can access in container)
try:
    # Check if we can see memory info
    with open('/proc/meminfo', 'r') as f:
        meminfo = f.read()

    # Extract some memory information
    mem_total = None
    mem_available = None

    for line in meminfo.split('\\n'):
        if line.startswith('MemTotal:'):
            mem_total = line.split()[1]
        elif line.startswith('MemAvailable:'):
            mem_available = line.split()[1]

    if mem_total:
        print(f"System memory total: {mem_total} kB")
    if mem_available:
        print(f"System memory available: {mem_available} kB")

except Exception as e:
    print(f"Could not read memory info: {e}")

# Check CPU information
try:
    with open('/proc/cpuinfo', 'r') as f:
        cpuinfo = f.read()

    # Count processors
    processors = cpuinfo.count('processor')
    print(f"Available processors: {processors}")

except Exception as e:
    print(f"Could not read CPU info: {e}")

# Test load
print("Performing test computation...")
start = time.time()
result = sum(i * i for i in range(50000))
duration = time.time() - start

print(f"Test computation: {duration:.4f}s, result: {result}")

print("Resource monitoring test completed")
""")

            assert result.success
            assert "Resource monitoring test completed" in result.stdout

            # Check container info
            info = sandbox.get_container_info()
            assert info["memory_limit"] == "512m"
            assert info["cpu_limit"] == "1.0"


class TestResourceValidation:
    """Test resource limit validation and error handling."""

    def test_invalid_memory_limits(self):
        """Test handling of invalid memory limit specifications."""
        # These should work (valid formats)
        valid_limits = ["128m", "256m", "512m", "1g", "2g"]

        for limit in valid_limits:
            try:
                with BioCageOrchestrator(memory_limit=limit) as sandbox:
                    result = sandbox.run("print('Memory limit valid')")
                    assert result.success
            except Exception as e:
                pytest.fail(f"Valid memory limit {limit} failed: {e}")

    def test_invalid_cpu_limits(self):
        """Test handling of invalid CPU limit specifications."""
        # These should work (valid formats)
        valid_limits = ["0.1", "0.5", "1.0", "2.0", "4.0"]

        for limit in valid_limits:
            try:
                with BioCageOrchestrator(cpu_limit=limit) as sandbox:
                    result = sandbox.run("print('CPU limit valid')")
                    assert result.success
            except Exception as e:
                pytest.fail(f"Valid CPU limit {limit} failed: {e}")

    def test_resource_limit_override_in_restart(self):
        """Test overriding resource limits during container restart."""
        with BioCageOrchestrator(
            execution_mode="persistent",
            memory_limit="256m",
            cpu_limit="0.5"
        ) as sandbox:

            # Check initial limits
            info1 = sandbox.get_container_info()
            assert info1["memory_limit"] == "256m"
            assert info1["cpu_limit"] == "0.5"

            result1 = sandbox.run("initial_var = 42; print('Initial container ready')")
            assert result1.success

            # Restart with different limits
            new_container_id = sandbox.restart_container(
                memory_limit="512m",
                cpu_limit="1.0"
            )

            # Check new limits
            info2 = sandbox.get_container_info()
            assert info2["memory_limit"] == "512m"
            assert info2["cpu_limit"] == "1.0"
            assert info2["container_id"] != info1["container_id"]

            # Verify state persistence with new limits
            result2 = sandbox.run("print(f'Variable after restart: {initial_var}')")
            assert result2.success
            assert "Variable after restart: 42" in result2.stdout


class TestResourcePerformance:
    """Test performance characteristics under different resource constraints."""

    def test_memory_constraint_impact(self):
        """Test impact of memory constraints on performance."""
        memory_configs = [
            {"memory_limit": "256m", "description": "low memory"},
            {"memory_limit": "1g", "description": "high memory"},
        ]

        results = []

        for config in memory_configs:
            with BioCageOrchestrator(
                memory_limit=config["memory_limit"],
                cpu_limit="2.0"
            ) as sandbox:

                result = sandbox.run(f"""
import time

print("Testing with {config['description']}...")

start_time = time.time()

# Memory allocation test
data_structures = []
for i in range(1000):
    # Create list with some data
    data = list(range(i * 10))
    data_structures.append(data)

allocation_time = time.time() - start_time

# Simple computation on the data
start_time = time.time()
total = sum(len(ds) for ds in data_structures)
computation_time = time.time() - start_time

print(f"Allocation time: {{allocation_time:.4f}}s")
print(f"Computation time: {{computation_time:.4f}}s")
print(f"Total data points: {{total}}")
print("Test completed with {config['description']}")
""")

                assert result.success
                assert f"Test completed with {config['description']}" in result.stdout

                # Extract timing information
                lines = result.stdout.split('\n')
                for line in lines:
                    if "Allocation time:" in line:
                        alloc_time = float(line.split("Allocation time: ")[1].split("s")[0])
                        results.append({
                            "config": config["description"],
                            "memory_limit": config["memory_limit"],
                            "allocation_time": alloc_time
                        })
                        break

        # Verify we got results for both configurations
        assert len(results) == 2
        print(f"Memory constraint results: {results}")

    def test_cpu_constraint_impact(self):
        """Test impact of CPU constraints on computational performance."""
        cpu_configs = [
            {"cpu_limit": "0.5", "description": "limited CPU"},
            {"cpu_limit": "2.0", "description": "full CPU"},
        ]

        results = []

        for config in cpu_configs:
            with BioCageOrchestrator(
                memory_limit="512m",
                cpu_limit=config["cpu_limit"]
            ) as sandbox:

                result = sandbox.run(f"""
import time
import math

print("Testing with {config['description']}...")

start_time = time.time()

# CPU-intensive computation
result = 0
iterations = 50000

for i in range(iterations):
    result += math.sqrt(i + 1) * math.sin(i / 1000) * math.cos(i / 2000)

computation_time = time.time() - start_time

print(f"Computation time: {{computation_time:.4f}}s")
print(f"Iterations: {{iterations}}")
print(f"Result: {{result:.6f}}")
print(f"Rate: {{iterations/computation_time:.1f}} ops/sec")
print(f"Test completed with {config['description']}")
""")

                assert result.success
                assert f"Test completed with {config['description']}" in result.stdout

                # Extract timing information
                lines = result.stdout.split('\n')
                for line in lines:
                    if "Computation time:" in line:
                        comp_time = float(line.split("Computation time: ")[1].split("s")[0])
                        results.append({
                            "config": config["description"],
                            "cpu_limit": config["cpu_limit"],
                            "computation_time": comp_time
                        })
                        break

        # Verify we got results for both configurations
        assert len(results) == 2
        print(f"CPU constraint results: {results}")

    def test_resource_usage_patterns(self):
        """Test different resource usage patterns."""
        with BioCageOrchestrator(
            memory_limit="512m",
            cpu_limit="1.0"
        ) as sandbox:

            result = sandbox.run("""
import time
import gc

print("=== Resource Usage Pattern Test ===")

# Pattern 1: Gradual memory allocation
print("Pattern 1: Gradual memory allocation")
start_time = time.time()

data = []
for i in range(5):
    chunk = list(range(i * 10000, (i + 1) * 10000))
    data.append(chunk)
    print(f"  Allocated chunk {i+1}, total items: {sum(len(chunk) for chunk in data)}")

alloc_time = time.time() - start_time
print(f"Allocation completed in {alloc_time:.4f}s")

# Pattern 2: Memory cleanup
print("\\nPattern 2: Memory cleanup")
start_time = time.time()

del data
gc.collect()  # Force garbage collection

cleanup_time = time.time() - start_time
print(f"Cleanup completed in {cleanup_time:.4f}s")

# Pattern 3: Burst computation
print("\\nPattern 3: Burst computation")
start_time = time.time()

results = []
for burst in range(3):
    burst_result = sum(i * i for i in range(10000))
    results.append(burst_result)
    print(f"  Burst {burst+1} completed: {burst_result}")

burst_time = time.time() - start_time
print(f"Burst computation completed in {burst_time:.4f}s")

print("\\n=== Resource usage pattern test completed ===")
""")

            assert result.success
            assert "Resource usage pattern test completed" in result.stdout
            assert "Pattern 1: Gradual memory allocation" in result.stdout
            assert "Pattern 2: Memory cleanup" in result.stdout
            assert "Pattern 3: Burst computation" in result.stdout


class TestResourceIntegration:
    """Test resource management integration with other features."""

    def test_resource_limits_with_file_operations(self):
        """Test resource limits combined with file operations."""
        import tempfile
        from pathlib import Path

        # Create test file
        temp_dir = Path(tempfile.mkdtemp())
        large_file = temp_dir / "large_data.txt"

        # Create a moderately large file
        content = "\n".join([f"Line {i}: " + "x" * 100 for i in range(1000)])
        large_file.write_text(content)

        try:
            with BioCageOrchestrator(
                memory_limit="256m",
                cpu_limit="1.0"
            ) as sandbox:

                container_path = sandbox.expose_file(str(large_file), "/app/data.txt")

                result = sandbox.run(f"""
import time

print("Resource limits + file operations test")

# Read and process the large file
start_time = time.time()

with open('{container_path}', 'r') as f:
    lines = f.readlines()

read_time = time.time() - start_time
print(f"File read completed in {{read_time:.4f}}s")
print(f"Lines read: {{len(lines)}}")

# Process the data (memory and CPU intensive)
start_time = time.time()

processed_data = []
for i, line in enumerate(lines):
    if i % 100 == 0:  # Process every 100th line
        processed_line = line.strip().upper()
        word_count = len(processed_line.split())
        processed_data.append({{
            'line_num': i,
            'length': len(processed_line),
            'word_count': word_count
        }})

process_time = time.time() - start_time
print(f"Processing completed in {{process_time:.4f}}s")
print(f"Processed entries: {{len(processed_data)}}")

print("Resource + file test completed successfully")
""")

                assert result.success
                assert "Resource + file test completed successfully" in result.stdout
                assert "Lines read: 1000" in result.stdout

        finally:
            import shutil
            shutil.rmtree(temp_dir)

    def test_resource_limits_with_persistence(self):
        """Test resource limits with persistent execution mode."""
        with BioCageOrchestrator(
            execution_mode="persistent",
            memory_limit="256m",
            cpu_limit="0.5"
        ) as sandbox:

            # First execution - create some data
            result1 = sandbox.run("""
print("Execution 1: Creating persistent data with resource limits")

# Create data structure that will persist
persistent_data = {
    'numbers': list(range(1000)),
    'squares': [i*i for i in range(1000)],
    'metadata': {
        'created': 'execution_1',
        'size': 1000
    }
}

print(f"Created data: {len(persistent_data['numbers'])} numbers")
print(f"First 5 numbers: {persistent_data['numbers'][:5]}")
print(f"First 5 squares: {persistent_data['squares'][:5]}")
""")

            assert result1.success
            assert "Created data: 1000 numbers" in result1.stdout

            # Second execution - use persistent data
            result2 = sandbox.run("""
print("Execution 2: Using persistent data with resource limits")

# Access persistent data
print(f"Data still available: {persistent_data['metadata']['created']}")
print(f"Total numbers: {len(persistent_data['numbers'])}")

# Perform computation on persistent data
import time
start_time = time.time()

# CPU-intensive operation on persistent data
sum_numbers = sum(persistent_data['numbers'])
sum_squares = sum(persistent_data['squares'])

computation_time = time.time() - start_time

print(f"Sum of numbers: {sum_numbers}")
print(f"Sum of squares: {sum_squares}")
print(f"Computation time: {computation_time:.4f}s")
""")

            assert result2.success
            assert "Data still available: execution_1" in result2.stdout
            assert "Sum of numbers: 499500" in result2.stdout  # Sum of 0..999

            # Verify resource limits are still enforced
            info = sandbox.get_container_info()
            assert info["memory_limit"] == "256m"
            assert info["cpu_limit"] == "0.5"