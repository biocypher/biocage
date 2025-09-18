#!/usr/bin/env python3
"""
Advanced example demonstrating container pool management for high-throughput scenarios.

This script shows how to implement container pooling to execute multiple
code snippets concurrently while managing resource allocation efficiently.
"""

import threading
import queue
import time
from contextlib import contextmanager
import concurrent.futures
from biocage import BioCageOrchestrator


class ContainerPool:
    """
    A pool of BioCage containers for concurrent execution.

    This class manages a pool of persistent containers to enable
    high-throughput code execution with minimal container startup overhead.
    """

    def __init__(self, pool_size=3, **sandbox_kwargs):
        """
        Initialize the container pool.

        Args:
            pool_size: Number of containers to maintain in the pool
            **sandbox_kwargs: Configuration options for BioCage containers
        """
        self.pool_size = pool_size
        self.sandbox_kwargs = sandbox_kwargs
        self.available_sandboxes = queue.Queue()
        self.in_use_sandboxes = set()
        self.lock = threading.Lock()

        print(f"Initializing container pool with {pool_size} containers...")
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize all containers in the pool."""
        for i in range(self.pool_size):
            print(f"Creating container {i+1}/{self.pool_size}...")

            sandbox = BioCageOrchestrator(
                execution_mode="persistent",
                **self.sandbox_kwargs
            )
            sandbox.start_container()

            # Pre-warm container with basic imports
            warmup_result = sandbox.run("""
import math
import json
import time
import random
print(f"Container {id({})} warmed up")
""")

            if warmup_result.success:
                print(f"Container {i+1} ready: {warmup_result.stdout.strip()}")
            else:
                print(f"Container {i+1} warmup failed: {warmup_result.stderr}")

            self.available_sandboxes.put(sandbox)

        print(f"Container pool initialization complete!")

    @contextmanager
    def get_sandbox(self, timeout=30):
        """
        Get a sandbox from the pool using context manager.

        Args:
            timeout: Maximum time to wait for an available sandbox

        Yields:
            BioCageOrchestrator: A sandbox from the pool
        """
        sandbox = None
        try:
            # Get available sandbox
            sandbox = self.available_sandboxes.get(timeout=timeout)

            with self.lock:
                self.in_use_sandboxes.add(sandbox)

            yield sandbox

        except queue.Empty:
            raise RuntimeError(f"No available sandboxes in pool (timeout: {timeout}s)")

        finally:
            # Return sandbox to pool
            if sandbox:
                with self.lock:
                    if sandbox in self.in_use_sandboxes:
                        self.in_use_sandboxes.remove(sandbox)
                        self.available_sandboxes.put(sandbox)

    def execute_concurrent(self, code_list, max_workers=None):
        """
        Execute multiple code snippets concurrently.

        Args:
            code_list: List of code strings to execute
            max_workers: Maximum number of concurrent workers

        Returns:
            List of SandboxExecutionResult objects
        """
        if max_workers is None:
            max_workers = min(self.pool_size, len(code_list))

        print(f"Executing {len(code_list)} tasks with {max_workers} workers...")

        def execute_code(task_info):
            task_id, code = task_info
            with self.get_sandbox() as sandbox:
                start_time = time.time()
                result = sandbox.run(code)
                execution_time = time.time() - start_time

                container_info = sandbox.get_container_info()
                return {
                    'task_id': task_id,
                    'result': result,
                    'total_time': execution_time,
                    'container_id': container_info['container_id']
                }

        # Create task list with IDs
        tasks = [(i, code) for i, code in enumerate(code_list)]

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(execute_code, task): task[0]
                for task in tasks
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_task):
                task_id = future_to_task[future]

                try:
                    result_info = future.result()
                    results.append(result_info)

                    success = "✓" if result_info['result'].success else "✗"
                    container_short_id = result_info['container_id'][:8]
                    print(f"{success} Task {task_id}: {result_info['total_time']:.2f}s "
                          f"(container: {container_short_id})")

                except Exception as e:
                    print(f"✗ Task {task_id} failed with exception: {e}")
                    results.append({
                        'task_id': task_id,
                        'result': None,
                        'error': str(e),
                        'total_time': 0
                    })

        # Sort results by task_id to maintain order
        results.sort(key=lambda x: x['task_id'])
        return results

    def get_pool_status(self):
        """Get current pool status information."""
        with self.lock:
            return {
                'total_sandboxes': self.pool_size,
                'available': self.available_sandboxes.qsize(),
                'in_use': len(self.in_use_sandboxes),
                'utilization': len(self.in_use_sandboxes) / self.pool_size * 100
            }

    def health_check(self):
        """Perform health check on all containers in the pool."""
        print("Performing pool health check...")

        healthy_containers = 0
        total_containers = 0

        # Check available containers
        temp_sandboxes = []
        while not self.available_sandboxes.empty():
            try:
                sandbox = self.available_sandboxes.get_nowait()
                temp_sandboxes.append(sandbox)
                total_containers += 1

                # Test basic functionality
                result = sandbox.run("print('Health check OK')")
                container_info = sandbox.get_container_info()
                container_short_id = container_info['container_id'][:8]

                if result.success:
                    healthy_containers += 1
                    print(f"  Container {container_short_id}: Healthy")
                else:
                    print(f"  Container {container_short_id}: Unhealthy - {result.stderr}")

            except queue.Empty:
                break

        # Return sandboxes to pool
        for sandbox in temp_sandboxes:
            self.available_sandboxes.put(sandbox)

        # Check in-use containers (just count them)
        with self.lock:
            in_use_count = len(self.in_use_sandboxes)
            total_containers += in_use_count

        health_percentage = (healthy_containers / total_containers * 100) if total_containers > 0 else 0

        print(f"Health check complete: {healthy_containers}/{total_containers} "
              f"containers healthy ({health_percentage:.1f}%)")

        return {
            'healthy_containers': healthy_containers,
            'total_containers': total_containers,
            'health_percentage': health_percentage,
            'in_use_containers': in_use_count
        }

    def cleanup(self):
        """Clean up all sandboxes in the pool."""
        print("Cleaning up container pool...")

        # Clean up in-use sandboxes
        with self.lock:
            for sandbox in list(self.in_use_sandboxes):
                try:
                    container_info = sandbox.get_container_info()
                    container_short_id = container_info['container_id'][:8]
                    sandbox.cleanup()
                    print(f"  Cleaned up in-use container: {container_short_id}")
                except Exception as e:
                    print(f"  Failed to clean up container: {e}")
            self.in_use_sandboxes.clear()

        # Clean up available sandboxes
        cleaned_count = 0
        while not self.available_sandboxes.empty():
            try:
                sandbox = self.available_sandboxes.get_nowait()
                try:
                    container_info = sandbox.get_container_info()
                    container_short_id = container_info['container_id'][:8]
                    sandbox.cleanup()
                    cleaned_count += 1
                    print(f"  Cleaned up available container: {container_short_id}")
                except Exception as cleanup_e:
                    sandbox.cleanup()  # Still try to cleanup even if we can't get info
                    cleaned_count += 1
                    print(f"  Cleaned up available container: <unknown>")
            except queue.Empty:
                break
            except Exception as e:
                print(f"  Failed to clean up container: {e}")

        print(f"Container pool cleanup complete: {cleaned_count} containers cleaned")


def demonstrate_basic_pool_usage():
    """Demonstrate basic container pool functionality."""
    print("\n" + "=" * 50)
    print("BASIC CONTAINER POOL DEMONSTRATION")
    print("=" * 50)

    # Create a pool with 3 containers
    pool = ContainerPool(
        pool_size=3,
        memory_limit="512m",
        cpu_limit="1.0"
    )

    try:
        # Test individual sandbox access
        print("\n1. Testing individual sandbox access:")
        with pool.get_sandbox() as sandbox:
            result = sandbox.run("import math; print(f'Pi = {math.pi:.6f}')")
            print(f"Individual execution: {result.stdout.strip()}")

        # Check pool status
        status = pool.get_pool_status()
        print(f"\nPool status: {status}")

    finally:
        pool.cleanup()


def demonstrate_concurrent_execution():
    """Demonstrate concurrent execution with the container pool."""
    print("\n" + "=" * 50)
    print("CONCURRENT EXECUTION DEMONSTRATION")
    print("=" * 50)

    # Create pool optimized for concurrent work
    pool = ContainerPool(
        pool_size=4,
        memory_limit="256m",
        cpu_limit="0.5"
    )

    try:
        # Create a variety of tasks
        tasks = [
            # Quick tasks
            "print('Quick task:', 42 * 2)",
            "import random; print('Random:', random.randint(1, 100))",

            # Computational tasks
            "result = sum(i*i for i in range(10000)); print(f'Sum of squares: {result}')",
            "import math; result = [math.factorial(i) for i in range(1, 11)]; print(f'Factorials: {len(result)} calculated')",

            # String processing
            "text = 'hello world' * 1000; print(f'Text processing: {len(text)} characters, {text.count(\"world\")} occurrences')",

            # Data structure operations
            "data = {'key' + str(i): i**2 for i in range(100)}; print(f'Dictionary: {len(data)} items, sum = {sum(data.values())}')",

            # Time-based task
            "import time; time.sleep(0.5); print('Delayed task completed')",

            # JSON processing
            "import json; data = {'numbers': list(range(50))}; json_str = json.dumps(data); print(f'JSON: {len(json_str)} characters')"
        ]

        # Execute all tasks concurrently
        start_time = time.time()
        results = pool.execute_concurrent(tasks, max_workers=4)
        total_time = time.time() - start_time

        print(f"\n📊 EXECUTION SUMMARY:")
        print(f"Total tasks: {len(tasks)}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Average time per task: {total_time/len(tasks):.2f}s")

        # Analyze results
        successful_tasks = [r for r in results if r['result'] and r['result'].success]
        failed_tasks = [r for r in results if not r['result'] or not r['result'].success]

        print(f"Successful: {len(successful_tasks)}")
        print(f"Failed: {len(failed_tasks)}")

        if successful_tasks:
            execution_times = [r['result'].execution_time for r in successful_tasks]
            print(f"Fastest execution: {min(execution_times):.3f}s")
            print(f"Slowest execution: {max(execution_times):.3f}s")
            print(f"Average execution: {sum(execution_times)/len(execution_times):.3f}s")

        # Show some successful outputs
        print(f"\n📋 SAMPLE OUTPUTS:")
        for i, result_info in enumerate(successful_tasks[:3]):
            output = result_info['result'].stdout.strip()
            print(f"Task {result_info['task_id']}: {output}")

    finally:
        pool.cleanup()


def demonstrate_performance_comparison():
    """Compare pool performance vs sequential execution."""
    print("\n" + "=" * 50)
    print("PERFORMANCE COMPARISON")
    print("=" * 50)

    # Create test tasks
    test_tasks = [
        f"result = sum(range({1000 * (i+1)})); print(f'Task {i}: {{result}}')"
        for i in range(8)
    ]

    print(f"Testing with {len(test_tasks)} computational tasks...\n")

    # Test 1: Sequential execution
    print("1. Sequential execution:")
    sequential_start = time.time()

    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        for i, task in enumerate(test_tasks):
            result = sandbox.run(task)
            if result.success:
                print(f"  Task {i}: {result.execution_time:.3f}s")

    sequential_time = time.time() - sequential_start
    print(f"Sequential total time: {sequential_time:.2f}s")

    # Test 2: Pool-based concurrent execution
    print("\n2. Concurrent execution with pool:")
    pool = ContainerPool(pool_size=4, memory_limit="512m")

    try:
        concurrent_start = time.time()
        results = pool.execute_concurrent(test_tasks, max_workers=4)
        concurrent_time = time.time() - concurrent_start

        print(f"Concurrent total time: {concurrent_time:.2f}s")

        # Calculate speedup
        speedup = sequential_time / concurrent_time
        print(f"\n📈 PERFORMANCE ANALYSIS:")
        print(f"Speedup: {speedup:.2f}x")
        print(f"Efficiency: {speedup/4*100:.1f}% (with 4 workers)")

        if speedup > 1:
            print("✓ Concurrent execution is faster!")
        else:
            print("⚠️  Sequential execution was faster (overhead dominated)")

    finally:
        pool.cleanup()


def demonstrate_pool_monitoring():
    """Demonstrate pool monitoring and health checking."""
    print("\n" + "=" * 50)
    print("POOL MONITORING DEMONSTRATION")
    print("=" * 50)

    pool = ContainerPool(pool_size=3, memory_limit="256m")

    try:
        # Initial health check
        print("1. Initial health check:")
        health = pool.health_check()

        print("\n2. Pool utilization monitoring:")

        # Create some long-running tasks to show utilization
        long_tasks = [
            "import time; time.sleep(2); print(f'Long task {i} done')"
            for i in range(5)
        ]

        # Execute with monitoring
        def monitor_pool():
            for i in range(10):
                status = pool.get_pool_status()
                print(f"  T+{i}s: Available={status['available']}, "
                      f"In-use={status['in_use']}, "
                      f"Utilization={status['utilization']:.1f}%")
                time.sleep(1)

        # Start monitoring in background
        import threading
        monitor_thread = threading.Thread(target=monitor_pool)
        monitor_thread.start()

        # Execute long tasks
        results = pool.execute_concurrent(long_tasks, max_workers=3)

        # Wait for monitoring to complete
        monitor_thread.join()

        print("\n3. Final health check:")
        final_health = pool.health_check()

        print(f"\nHealth comparison:")
        print(f"Initial: {health['health_percentage']:.1f}%")
        print(f"Final: {final_health['health_percentage']:.1f}%")

    finally:
        pool.cleanup()


def main():
    """Run all container pool demonstrations."""
    print("BioCage Container Pool Advanced Example")
    print("=" * 60)

    try:
        demonstrate_basic_pool_usage()
        demonstrate_concurrent_execution()
        demonstrate_performance_comparison()
        demonstrate_pool_monitoring()

        print("\n" + "=" * 60)
        print("✓ All container pool demonstrations completed successfully!")
        print("\nKey takeaways:")
        print("- Container pools enable high-throughput concurrent execution")
        print("- Pool size should match your concurrency requirements")
        print("- Monitor pool utilization to optimize performance")
        print("- Health checks help identify problematic containers")

    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()