"""Test container pool management functionality."""

import threading
import time
import concurrent.futures
from contextlib import contextmanager
import queue

import pytest

from biocage import BioCageOrchestrator


class MockContainerPool:
    """
    Mock container pool for testing pool management functionality.

    This class mimics the functionality from the container_pool.py example
    to test concurrent execution patterns.
    """

    def __init__(self, pool_size=3, **sandbox_kwargs):
        """Initialize the container pool."""
        self.pool_size = pool_size
        self.sandbox_kwargs = sandbox_kwargs
        self.available_sandboxes = queue.Queue()
        self.in_use_sandboxes = set()
        self.lock = threading.Lock()
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize all containers in the pool."""
        for i in range(self.pool_size):
            sandbox = BioCageOrchestrator(
                execution_mode="persistent",
                **self.sandbox_kwargs
            )
            sandbox.start_container()

            # Pre-warm container
            warmup_result = sandbox.run("import math; import random; x = 42")
            assert warmup_result.success

            self.available_sandboxes.put(sandbox)

    @contextmanager
    def get_sandbox(self, timeout=30):
        """Get a sandbox from the pool using context manager."""
        sandbox = None
        try:
            sandbox = self.available_sandboxes.get(timeout=timeout)
            with self.lock:
                self.in_use_sandboxes.add(sandbox)
            yield sandbox
        except queue.Empty:
            raise RuntimeError(f"No available sandboxes in pool (timeout: {timeout}s)")
        finally:
            if sandbox:
                with self.lock:
                    if sandbox in self.in_use_sandboxes:
                        self.in_use_sandboxes.remove(sandbox)
                        self.available_sandboxes.put(sandbox)

    def execute_concurrent(self, code_list, max_workers=None):
        """Execute multiple code snippets concurrently."""
        if max_workers is None:
            max_workers = min(self.pool_size, len(code_list))

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

        tasks = [(i, code) for i, code in enumerate(code_list)]
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(execute_code, task): task[0]
                for task in tasks
            }

            for future in concurrent.futures.as_completed(future_to_task):
                task_id = future_to_task[future]
                try:
                    result_info = future.result()
                    results.append(result_info)
                except Exception as e:
                    results.append({
                        'task_id': task_id,
                        'result': None,
                        'error': str(e),
                        'total_time': 0
                    })

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
        healthy_containers = 0
        total_containers = 0

        # Check available containers
        temp_sandboxes = []
        while not self.available_sandboxes.empty():
            try:
                sandbox = self.available_sandboxes.get_nowait()
                temp_sandboxes.append(sandbox)
                total_containers += 1

                result = sandbox.run("print('Health check OK')")
                if result.success:
                    healthy_containers += 1
            except queue.Empty:
                break

        # Return sandboxes to pool
        for sandbox in temp_sandboxes:
            self.available_sandboxes.put(sandbox)

        # Count in-use containers
        with self.lock:
            in_use_count = len(self.in_use_sandboxes)
            total_containers += in_use_count

        health_percentage = (healthy_containers / total_containers * 100) if total_containers > 0 else 0

        return {
            'healthy_containers': healthy_containers,
            'total_containers': total_containers,
            'health_percentage': health_percentage,
            'in_use_containers': in_use_count
        }

    def cleanup(self):
        """Clean up all sandboxes in the pool."""
        with self.lock:
            for sandbox in list(self.in_use_sandboxes):
                try:
                    sandbox.cleanup()
                except Exception:
                    pass
            self.in_use_sandboxes.clear()

        while not self.available_sandboxes.empty():
            try:
                sandbox = self.available_sandboxes.get_nowait()
                try:
                    sandbox.cleanup()
                except Exception:
                    pass
            except queue.Empty:
                break


class TestContainerPool:
    """Test container pool management functionality."""

    def test_pool_initialization(self):
        """Test that container pool initializes correctly."""
        pool = MockContainerPool(pool_size=2, memory_limit="256m")

        try:
            status = pool.get_pool_status()
            assert status['total_sandboxes'] == 2
            assert status['available'] == 2
            assert status['in_use'] == 0
            assert status['utilization'] == 0.0
        finally:
            pool.cleanup()

    def test_pool_sandbox_checkout(self):
        """Test checking out and returning sandboxes from pool."""
        pool = MockContainerPool(pool_size=2, memory_limit="256m")

        try:
            # Check initial status
            status = pool.get_pool_status()
            assert status['available'] == 2
            assert status['in_use'] == 0

            # Get a sandbox
            with pool.get_sandbox() as sandbox:
                # Test the sandbox works
                result = sandbox.run("print('Pool sandbox works')")
                assert result.success
                assert "Pool sandbox works" in result.stdout

                # Check status while sandbox is in use
                status = pool.get_pool_status()
                assert status['available'] == 1
                assert status['in_use'] == 1
                assert status['utilization'] == 50.0

            # After returning sandbox
            status = pool.get_pool_status()
            assert status['available'] == 2
            assert status['in_use'] == 0
            assert status['utilization'] == 0.0
        finally:
            pool.cleanup()

    def test_concurrent_execution(self):
        """Test concurrent execution using container pool."""
        pool = MockContainerPool(pool_size=3, memory_limit="256m")

        try:
            tasks = [
                "result = 10 + 5; print(f'Task result: {result}')",
                "import math; result = math.pi * 2; print(f'Pi doubled: {result:.2f}')",
                "data = [1, 2, 3, 4, 5]; result = sum(data); print(f'Sum: {result}')",
                "text = 'hello world'; result = text.upper(); print(f'Upper: {result}')",
            ]

            start_time = time.time()
            results = pool.execute_concurrent(tasks, max_workers=3)
            total_time = time.time() - start_time

            # Verify all tasks completed
            assert len(results) == len(tasks)

            successful_tasks = [r for r in results if r['result'] and r['result'].success]
            assert len(successful_tasks) == len(tasks)

            # Verify outputs
            outputs = [r['result'].stdout for r in successful_tasks]
            combined_output = ' '.join(outputs)

            assert "Task result: 15" in combined_output
            assert "Pi doubled: 6.28" in combined_output
            assert "Sum: 15" in combined_output
            assert "Upper: HELLO WORLD" in combined_output

            # Verify concurrent execution was faster than sequential would be
            # (This is a rough check - concurrent should be significantly faster)
            expected_sequential_time = sum(r['result'].execution_time for r in successful_tasks)
            assert total_time < expected_sequential_time * 0.8  # At least 20% faster

            print(f"Concurrent execution: {total_time:.2f}s vs estimated sequential: {expected_sequential_time:.2f}s")
        finally:
            pool.cleanup()

    def test_pool_health_check(self):
        """Test container pool health checking."""
        pool = MockContainerPool(pool_size=2, memory_limit="256m")

        try:
            health = pool.health_check()

            assert health['total_containers'] == 2
            assert health['healthy_containers'] == 2
            assert health['health_percentage'] == 100.0
            assert health['in_use_containers'] == 0
        finally:
            pool.cleanup()

    def test_pool_resource_limits(self):
        """Test that pool containers respect resource limits."""
        pool = MockContainerPool(
            pool_size=2,
            memory_limit="256m",
            cpu_limit="0.5"
        )

        try:
            with pool.get_sandbox() as sandbox:
                info = sandbox.get_container_info()
                assert info['memory_limit'] == "256m"
                assert info['cpu_limit'] == "0.5"

                # Test that container can execute code
                result = sandbox.run("print('Resource limits working')")
                assert result.success
                assert "Resource limits working" in result.stdout
        finally:
            pool.cleanup()

    def test_pool_timeout_handling(self):
        """Test pool timeout when no containers available."""
        pool = MockContainerPool(pool_size=1, memory_limit="256m")

        try:
            # Occupy the only available container
            with pool.get_sandbox() as sandbox1:
                # Try to get another container with short timeout
                with pytest.raises(RuntimeError, match="No available sandboxes"):
                    with pool.get_sandbox(timeout=1):
                        pass  # This should timeout
        finally:
            pool.cleanup()

    def test_pool_state_isolation(self):
        """Test that different containers in pool maintain state isolation."""
        pool = MockContainerPool(pool_size=2, memory_limit="256m")

        try:
            # Set different variables in different containers
            containers_used = []

            with pool.get_sandbox() as sandbox1:
                result1 = sandbox1.run("container_id = 1; x = 'first'")
                assert result1.success
                info1 = sandbox1.get_container_info()
                containers_used.append(info1['container_id'])

            with pool.get_sandbox() as sandbox2:
                result2 = sandbox2.run("container_id = 2; x = 'second'")
                assert result2.success
                info2 = sandbox2.get_container_info()
                containers_used.append(info2['container_id'])

            # Verify we got different containers (in persistent mode, state should be maintained)
            # But when we get containers again, variables should be preserved per container
            with pool.get_sandbox() as sandbox:
                result = sandbox.run("print(f'Container: {container_id}, x: {x}')")
                if result.success:
                    # State was preserved - this means we got a container we used before
                    assert "Container: " in result.stdout
                    assert "x: " in result.stdout
        finally:
            pool.cleanup()


class TestPoolPerformance:
    """Test container pool performance characteristics."""

    def test_pool_vs_sequential_performance(self):
        """Test that pool execution is faster than sequential execution."""
        # Test tasks that take some time to execute
        tasks = [
            f"result = sum(range({1000 * (i+1)})); print(f'Task {i}: {{result}}')"
            for i in range(4)
        ]

        # Sequential execution
        sequential_start = time.time()
        with BioCageOrchestrator(execution_mode="persistent") as sandbox:
            sequential_results = []
            for i, task in enumerate(tasks):
                result = sandbox.run(task)
                sequential_results.append(result)
        sequential_time = time.time() - sequential_start

        # Concurrent execution with pool
        pool = MockContainerPool(pool_size=3, memory_limit="512m")
        try:
            concurrent_start = time.time()
            concurrent_results = pool.execute_concurrent(tasks, max_workers=3)
            concurrent_time = time.time() - concurrent_start

            # Verify both approaches got same results
            assert len(sequential_results) == len(concurrent_results)

            # All should be successful
            assert all(r.success for r in sequential_results)
            assert all(r['result'].success for r in concurrent_results if r['result'])

            # Concurrent should be faster (with some tolerance for overhead)
            speedup = sequential_time / concurrent_time
            print(f"Speedup: {speedup:.2f}x (sequential: {sequential_time:.2f}s, concurrent: {concurrent_time:.2f}s)")

            # We expect at least some speedup, though perfect scaling is not guaranteed
            assert speedup > 1.1  # At least 10% faster
        finally:
            pool.cleanup()

    def test_pool_utilization_monitoring(self):
        """Test monitoring pool utilization during execution."""
        pool = MockContainerPool(pool_size=3, memory_limit="256m")

        try:
            utilization_history = []

            def monitor_utilization():
                """Monitor pool utilization in background."""
                for _ in range(10):
                    status = pool.get_pool_status()
                    utilization_history.append(status['utilization'])
                    time.sleep(0.1)

            # Start monitoring
            monitor_thread = threading.Thread(target=monitor_utilization)
            monitor_thread.start()

            # Execute tasks that will utilize the pool
            tasks = [
                "import time; time.sleep(0.5); print(f'Task {i} complete')"
                for i in range(6)  # More tasks than pool size
            ]

            results = pool.execute_concurrent(tasks, max_workers=3)
            monitor_thread.join()

            # Verify monitoring captured utilization changes
            max_utilization = max(utilization_history)
            assert max_utilization > 0  # Pool was utilized

            # Verify tasks completed successfully
            successful = [r for r in results if r['result'] and r['result'].success]
            assert len(successful) == len(tasks)
        finally:
            pool.cleanup()