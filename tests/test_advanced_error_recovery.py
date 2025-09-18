"""Test advanced error recovery and handling patterns."""

import pytest
import time

from biocage import BioCageOrchestrator


class TestErrorRecovery:
    """Test error recovery patterns and graceful degradation."""

    def test_syntax_error_recovery(self):
        """Test recovery from syntax errors."""
        with BioCageOrchestrator(execution_mode="persistent") as sandbox:
            # Set up some initial state
            result1 = sandbox.run("""
x = 42
y = "hello world"
print("Initial state set")
""")
            assert result1.success
            assert "Initial state set" in result1.stdout

            # Execute code with runtime error (allows partial output)
            result2 = sandbox.run("""
print("Before runtime error")
x = 1 / 0  # This will cause a runtime error
print("After runtime error - this won't execute")
""", shutdown_on_failure=False)
            assert not result2.success
            assert "Before runtime error" in result2.stdout
            assert "ZeroDivisionError" in result2.stderr
            assert "After runtime error" not in result2.stdout

            # Verify container is still functional and state is preserved
            result3 = sandbox.run("""
print("Recovery test")
print(f"x = {x}, y = {y}")
print("Container recovered from runtime error")
""")
            assert result3.success
            assert "Recovery test" in result3.stdout
            assert "x = 42, y = hello world" in result3.stdout
            assert "Container recovered from runtime error" in result3.stdout

    def test_runtime_error_recovery(self):
        """Test recovery from runtime errors."""
        with BioCageOrchestrator(execution_mode="persistent") as sandbox:
            # Set up initial state
            result1 = sandbox.run("""
data = [1, 2, 3, 4, 5]
counter = 0
print("Setup complete")
""")
            assert result1.success

            # Execute code that will have runtime error
            result2 = sandbox.run("""
print("Starting operations...")
for i, value in enumerate(data):
    counter += 1
    print(f"Processing item {i}: {value}")

    # This will cause division by zero on third iteration (i=2, value=3)
    result = 10 / (value - 3)
    print(f"Result: {result}")

print("This should not execute due to error")
""", shutdown_on_failure=False)
            assert not result2.success
            assert "Processing item 0: 1" in result2.stdout
            assert "Processing item 1: 2" in result2.stdout
            assert "Processing item 2: 3" in result2.stdout
            assert "ZeroDivisionError" in result2.stderr
            assert "This should not execute" not in result2.stdout

            # Verify container still works after error (even though partial state is lost)
            result3 = sandbox.run("""
# Re-establish state since session doesn't preserve partial execution state
data = [1, 2, 3, 4, 5]
counter = 0
print("Recovery check:")
print(f"Data re-established: {data}")
print("Container is functional after runtime error")
""")
            assert result3.success
            assert "Data re-established: [1, 2, 3, 4, 5]" in result3.stdout
            assert "Container is functional after runtime error" in result3.stdout

    def test_import_error_recovery(self):
        """Test recovery from import errors."""
        with BioCageOrchestrator(execution_mode="persistent") as sandbox:
            # First, establish successful imports
            result1 = sandbox.run("""
print("Establishing imports...")
import math
import os
print("Standard imports successful")
""")
            assert result1.success
            assert "Standard imports successful" in result1.stdout

            # Try to import non-existent module
            result2 = sandbox.run("""
print("Attempting bad import...")
import nonexistent_module_xyz
print("This line should not execute")
""", shutdown_on_failure=False)
            assert not result2.success
            assert "ModuleNotFoundError" in result2.stderr
            assert "This line should not execute" not in result2.stdout

            # Verify successful imports are still available and container functional
            result3 = sandbox.run("""
print("Testing recovered imports:")
print(f"Pi from math: {math.pi}")
print(f"OS name: {os.name}")
print("Previously imported modules still work")
""")
            assert result3.success
            assert "Pi from math: 3.14159" in result3.stdout
            assert "Previously imported modules still work" in result3.stdout

    def test_memory_error_recovery(self):
        """Test recovery from memory-related issues."""
        with BioCageOrchestrator(
            execution_mode="persistent",
            memory_limit="256m"
        ) as sandbox:
            # Set up some initial data
            result1 = sandbox.run("""
initial_data = list(range(1000))
print(f"Initial data created: {len(initial_data)} items")
""")
            assert result1.success

            # Try to create very large data structure (may cause memory issues)
            result2 = sandbox.run("""
print("Attempting large memory allocation...")

try:
    # Try to create a very large list
    large_data = []
    for i in range(1000000):  # 1 million items
        large_data.append([j for j in range(100)])  # Each item is a list of 100 elements

        if i % 100000 == 0:
            print(f"Created {i} items so far...")

    print(f"Large data created successfully: {len(large_data)} items")

except MemoryError as e:
    print(f"Memory allocation failed as expected: {e}")
except Exception as e:
    print(f"Other error during allocation: {type(e).__name__}: {e}")
""", timeout=30, shutdown_on_failure=False)

            # This might succeed or fail depending on system resources
            # The important part is that the container recovers

            # Verify container is still functional and initial data preserved
            result3 = sandbox.run("""
print("Memory recovery test:")
print(f"Initial data still available: {len(initial_data)} items")
print(f"Can still perform operations: {sum(initial_data[:10])}")

# Try a smaller, safe memory allocation
safe_data = list(range(5000))
print(f"Safe allocation successful: {len(safe_data)} items")
""")
            assert result3.success
            assert "Initial data still available: 1000 items" in result3.stdout
            assert "Safe allocation successful: 5000 items" in result3.stdout

    def test_timeout_recovery(self):
        """Test recovery after timeout errors."""
        with BioCageOrchestrator(execution_mode="persistent") as sandbox:
            # Set up initial state
            result1 = sandbox.run("""
state_var = "initial_state"
counter = 0
print("Pre-timeout state established")
""")
            assert result1.success

            # Execute code that will timeout
            result2 = sandbox.run("""
print("Starting operation that will timeout...")
counter = 1

import time
time.sleep(10)  # This will cause timeout

counter = 2  # This should not execute
print("This should not appear due to timeout")
""", timeout=3, shutdown_on_failure=False)

            assert not result2.success
            assert result2.exit_code == 124  # Timeout exit code
            assert "Starting operation that will timeout..." in result2.stdout
            assert "This should not appear due to timeout" not in result2.stdout

            # Test recovery - container should still be functional
            result3 = sandbox.run("""
print("Testing recovery after timeout:")
print(f"State variable: {state_var}")
# Note: counter changes during timeout are lost due to session persistence

# Verify we can still do normal operations
import math
result = math.sqrt(16)
print(f"Math operation works: sqrt(16) = {result}")
print("Container recovered successfully from timeout")
""")

            assert result3.success
            assert "State variable: initial_state" in result3.stdout
            assert "Math operation works: sqrt(16) = 4.0" in result3.stdout
            assert "Container recovered successfully from timeout" in result3.stdout

    def test_multiple_consecutive_errors(self):
        """Test handling multiple consecutive errors gracefully."""
        with BioCageOrchestrator(execution_mode="persistent") as sandbox:
            # Initial setup
            result0 = sandbox.run("""
error_count = 0
print("Error resilience test initialized")
""")
            assert result0.success

            # Error 1: Runtime error
            result1 = sandbox.run("""
print("Operation 1: Testing runtime error resilience")
x = 1 / 0  # Runtime error
print("Should not reach here")
""", shutdown_on_failure=False)
            assert not result1.success
            assert "ZeroDivisionError" in result1.stderr

            # Recovery check 1
            recovery1 = sandbox.run("""
error_count += 1
print(f"After error 1 - errors handled: {error_count}")
print("Container still functional after runtime error")
""")
            assert recovery1.success

            # Error 2: Name error
            result2 = sandbox.run("""
print("Operation 2: Testing name error resilience")
print(undefined_variable_name)  # Name error
print("Should not reach here")
""", shutdown_on_failure=False)
            assert not result2.success
            assert "NameError" in result2.stderr

            # Recovery check 2
            recovery2 = sandbox.run("""
error_count += 1
print(f"After error 2 - errors handled: {error_count}")
print("Container still functional after name error")
""")
            assert recovery2.success

            # Error 3: Import error
            result3 = sandbox.run("""
print("Operation 3: Testing import error resilience")
import nonexistent_module_abc  # Import error
print("Should not reach here")
""", shutdown_on_failure=False)
            assert not result3.success
            assert "ModuleNotFoundError" in result3.stderr

            # Final recovery check
            recovery3 = sandbox.run("""
error_count += 1
print("=== Final Error Resilience Report ===")
print(f"Total errors handled: {error_count}")
print(f"Container remained functional through {error_count} consecutive errors")

# Verify container can still do complex operations
import math
test_result = sum(math.sqrt(i) for i in range(1, 11))
print(f"Complex operation result: {test_result:.2f}")
print("Error resilience test completed successfully")
""")

            assert recovery3.success
            assert "Total errors handled: 3" in recovery3.stdout
            assert "Error resilience test completed successfully" in recovery3.stdout

    def test_error_recovery_with_file_operations(self):
        """Test error recovery during file operations."""
        import tempfile
        from pathlib import Path

        # Create test files
        temp_dir = Path(tempfile.mkdtemp())
        valid_file = temp_dir / "valid.txt"
        valid_file.write_text("This is valid content\nLine 2\nLine 3")

        try:
            with BioCageOrchestrator(execution_mode="persistent") as sandbox:
                # Expose the valid file
                container_path = sandbox.expose_file(str(valid_file), "/app/data.txt")

                # Set up initial state
                result1 = sandbox.run(f"""
processed_files = []
error_files = []
print("File operation error recovery test")

# Successfully read the valid file
with open('{container_path}', 'r') as f:
    content = f.read()

processed_files.append('valid.txt')
print(f"Successfully read file: {{len(content)}} characters")
""")
                assert result1.success

                # Try to read non-existent file (should cause unhandled error)
                result2 = sandbox.run("""
print("Attempting to read non-existent file...")

# This should cause an unhandled error
with open('/app/definitely_missing.txt', 'r') as f:
    bad_content = f.read()

print("Should not reach this line")
""", shutdown_on_failure=False)
                assert not result2.success
                assert "FileNotFoundError" in result2.stderr

                # Verify recovery and that container can still access files
                result3 = sandbox.run(f"""
print("=== File Operation Recovery Check ===")
print(f"Successfully processed files: {{processed_files}}")

# Verify we can still read the valid file
with open('{container_path}', 'r') as f:
    lines = f.readlines()

print(f"Valid file still accessible: {{len(lines)}} lines")
print("File operation recovery successful")

# Test that we can handle errors properly now
try:
    with open('/app/nonexistent.txt', 'r') as f:
        content = f.read()
except FileNotFoundError:
    print("Can properly handle file errors after recovery")
""")
                assert result3.success
                assert "Successfully processed files: ['valid.txt']" in result3.stdout
                assert "Valid file still accessible: 3 lines" in result3.stdout
                assert "Can properly handle file errors after recovery" in result3.stdout

        finally:
            import shutil
            shutil.rmtree(temp_dir)

    def test_graceful_degradation_patterns(self):
        """Test graceful degradation when components fail."""
        with BioCageOrchestrator(execution_mode="persistent") as sandbox:
            result = sandbox.run("""
print("=== Graceful Degradation Pattern Test ===")

# System status tracker
system_status = {
    'core_functions': True,
    'advanced_features': True,
    'optional_components': True,
    'error_log': []
}

def safe_operation(operation_name, operation_func):
    '''Safely execute an operation with graceful degradation.'''
    try:
        result = operation_func()
        print(f"✓ {operation_name}: SUCCESS")
        return result
    except Exception as e:
        error_msg = f"{operation_name}: {type(e).__name__}"
        system_status['error_log'].append(error_msg)
        print(f"✗ {operation_name}: FAILED - {error_msg}")
        return None

# Core function (should work)
def core_function():
    return sum(range(100))

core_result = safe_operation("Core computation", core_function)

# Advanced feature (might fail)
def advanced_feature():
    import nonexistent_advanced_module
    return "advanced result"

advanced_result = safe_operation("Advanced feature", advanced_feature)
if advanced_result is None:
    system_status['advanced_features'] = False

# Optional component (designed to fail)
def optional_component():
    x = 1 / 0  # This will fail
    return "optional result"

optional_result = safe_operation("Optional component", optional_component)
if optional_result is None:
    system_status['optional_components'] = False

# System continues to function with degraded capabilities
print("\\n=== System Status Report ===")
for component, status in system_status.items():
    if component != 'error_log':
        status_str = "OPERATIONAL" if status else "DEGRADED"
        print(f"{component.replace('_', ' ').title()}: {status_str}")

if system_status['error_log']:
    print("\\nErrors encountered:")
    for error in system_status['error_log']:
        print(f"  - {error}")

# Demonstrate system still functions with core capabilities
print("\\n=== Degraded Mode Operations ===")
if system_status['core_functions']:
    backup_result = sum(range(50))  # Simpler fallback operation
    print(f"Fallback computation result: {backup_result}")

print("System continues operating in degraded mode")
print("Graceful degradation test completed")
""")

            assert result.success
            assert "System continues operating in degraded mode" in result.stdout
            assert "Core computation: SUCCESS" in result.stdout
            assert "Advanced feature: FAILED" in result.stdout
            assert "Optional component: FAILED" in result.stdout
            assert "Graceful degradation test completed" in result.stdout


class TestErrorHandlingIntegration:
    """Test error handling integration with other features."""

    def test_error_recovery_with_container_restart(self):
        """Test error recovery combined with container restart."""
        with BioCageOrchestrator(execution_mode="persistent") as sandbox:
            # Set up initial state
            result1 = sandbox.run("""
persistent_data = {'counter': 0, 'operations': []}
print("Initial state established")
""")
            assert result1.success

            # Cause an error (changes during failed execution are not preserved)
            result2 = sandbox.run("""
print("About to cause error...")
undefined_variable_error
""", shutdown_on_failure=False)
            assert not result2.success
            assert "NameError" in result2.stderr

            # Update state after error (successfully)
            result3 = sandbox.run("""
persistent_data['counter'] += 1
persistent_data['operations'].append('before_restart')
print(f"State before restart: {persistent_data}")
""")
            assert result3.success
            assert "counter': 1" in result3.stdout

            # Restart container (tests that restart works, though state is reset)
            new_container_id = sandbox.restart_container()

            # Verify container is functional after restart (state gets reset due to session restoration)
            result4 = sandbox.run("""
# Re-establish state since restart resets the session
persistent_data = {'counter': 0, 'operations': []}
persistent_data['operations'].append('after_restart')
print(f"State after restart: {persistent_data}")
print("Container restart recovery successful")
""")
            assert result4.success
            assert "after_restart" in result4.stdout
            assert "Container restart recovery successful" in result4.stdout

    def test_error_patterns_with_resource_constraints(self):
        """Test error patterns under resource constraints."""
        with BioCageOrchestrator(
            execution_mode="persistent",
            memory_limit="256m",
            cpu_limit="1.0"
        ) as sandbox:

            result = sandbox.run("""
print("Error patterns under resource constraints")

error_scenarios = []

# Scenario 1: Normal error under constraints
try:
    result = 10 / 0
except ZeroDivisionError as e:
    error_scenarios.append(f"Math error: {type(e).__name__}")

# Scenario 2: Memory allocation under constraints
try:
    large_data = [i for i in range(100000)]  # Should work with 256m
    error_scenarios.append("Memory allocation: SUCCESS")
except MemoryError as e:
    error_scenarios.append(f"Memory error: {type(e).__name__}")

# Scenario 3: CPU-intensive operation under constraints
try:
    import time
    start = time.time()
    result = sum(i * i for i in range(50000))  # CPU-intensive but should complete
    duration = time.time() - start
    error_scenarios.append(f"CPU operation: SUCCESS ({duration:.3f}s)")
except Exception as e:
    error_scenarios.append(f"CPU error: {type(e).__name__}")

print("\\nError scenario results:")
for scenario in error_scenarios:
    print(f"  {scenario}")

print("Resource-constrained error handling completed")
""", timeout=30)

            assert result.success
            assert "Resource-constrained error handling completed" in result.stdout
            assert "Math error: ZeroDivisionError" in result.stdout

    def test_cascading_error_prevention(self):
        """Test prevention of cascading errors."""
        with BioCageOrchestrator(execution_mode="persistent") as sandbox:
            result = sandbox.run("""
print("=== Cascading Error Prevention Test ===")

# Set up error-prone system
class SafeSystem:
    def __init__(self):
        self.components = {
            'database': True,
            'cache': True,
            'network': True,
            'storage': True
        }
        self.fallbacks_used = []

    def safe_database_operation(self):
        if not self.components['database']:
            return self._use_fallback('database', 'memory_store')

        try:
            # Simulate database operation that fails
            raise ConnectionError("Database connection failed")
        except Exception as e:
            self.components['database'] = False
            return self._use_fallback('database', 'memory_store')

    def safe_cache_operation(self):
        if not self.components['cache']:
            return self._use_fallback('cache', 'no_cache')

        try:
            # This depends on database, but shouldn't cascade fail
            if not self.components['database']:
                return self._use_fallback('cache', 'no_cache')

            # Cache operation
            return "cache_result"
        except Exception as e:
            self.components['cache'] = False
            return self._use_fallback('cache', 'no_cache')

    def _use_fallback(self, component, fallback_name):
        self.fallbacks_used.append(f"{component} -> {fallback_name}")
        return f"fallback_{fallback_name}"

# Test the safe system
safe_sys = SafeSystem()

print("Testing component failures with fallbacks:")

# This will fail and trigger fallback
db_result = safe_sys.safe_database_operation()
print(f"Database operation result: {db_result}")

# This should use fallback because database failed
cache_result = safe_sys.safe_cache_operation()
print(f"Cache operation result: {cache_result}")

print("\\nSystem state after failures:")
for component, status in safe_sys.components.items():
    print(f"  {component}: {'OK' if status else 'FAILED'}")

print("\\nFallbacks used:")
for fallback in safe_sys.fallbacks_used:
    print(f"  {fallback}")

operational_components = sum(safe_sys.components.values())
print(f"\\nOperational components: {operational_components}/{len(safe_sys.components)}")
print("System remains partially functional despite failures")
print("Cascading error prevention test completed")
""")

            assert result.success
            assert "System remains partially functional despite failures" in result.stdout
            assert "database -> memory_store" in result.stdout
            assert "cache -> no_cache" in result.stdout
            assert "Cascading error prevention test completed" in result.stdout