#!/usr/bin/env python3
"""
Example demonstrating comprehensive error handling in BioCage.

This script shows how to handle various types of errors including
syntax errors, runtime errors, timeouts, and how to implement
robust recovery strategies.
"""

from biocage import BioCageOrchestrator
import time


def main():
    print("BioCage Error Handling Examples")
    print("=" * 40)

    demonstrate_syntax_errors()
    demonstrate_runtime_errors()
    demonstrate_timeout_handling()
    demonstrate_error_recovery()


def demonstrate_syntax_errors():
    """Demonstrate handling of Python syntax errors."""
    print("\n1. Syntax Error Handling")
    print("-" * 25)

    with BioCageOrchestrator() as sandbox:
        # Intentional syntax error - missing closing quote
        result = sandbox.run("print('Hello World)")

        print(f"Success: {result.success}")
        print(f"Exit code: {result.exit_code}")

        if not result.success:
            print("Syntax error detected:")
            print(f"Error: {result.stderr.strip()}")
            print("✓ Syntax errors are properly captured")


def demonstrate_runtime_errors():
    """Demonstrate handling of runtime exceptions."""
    print("\n2. Runtime Error Handling")
    print("-" * 26)

    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        # Division by zero error
        print("\na) Division by zero:")
        result1 = sandbox.run("""
try:
    result = 10 / 0
    print(f"Result: {result}")
except ZeroDivisionError as e:
    print(f"Caught ZeroDivisionError: {e}")
    result = float('inf')
    print(f"Using fallback result: {result}")
""")
        print(f"Output: {result1.stdout.strip()}")

        # NameError - undefined variable
        print("\nb) Undefined variable:")
        result2 = sandbox.run("""
try:
    print(undefined_variable)
except NameError as e:
    print(f"Caught NameError: {e}")
    print("Variable was not defined")
""")
        print(f"Output: {result2.stdout.strip()}")

        # Import error
        print("\nc) Import error:")
        result3 = sandbox.run("""
try:
    import nonexistent_module
    print("Import successful")
except ImportError as e:
    print(f"Caught ImportError: {e}")
    print("Using alternative approach")
""")
        print(f"Output: {result3.stdout.strip()}")

        # Index error
        print("\nd) Index error:")
        result4 = sandbox.run("""
try:
    my_list = [1, 2, 3]
    value = my_list[10]  # Index out of range
    print(f"Value: {value}")
except IndexError as e:
    print(f"Caught IndexError: {e}")
    print(f"List length: {len(my_list)}")
    print("Using safe indexing next time")
""")
        print(f"Output: {result4.stdout.strip()}")


def demonstrate_timeout_handling():
    """Demonstrate timeout handling for long-running operations."""
    print("\n3. Timeout Handling")
    print("-" * 18)

    with BioCageOrchestrator() as sandbox:
        print("Executing code that will timeout...")

        start_time = time.time()
        result = sandbox.run("""
import time
print("Starting long operation...")
time.sleep(10)  # This will timeout
print("Operation completed (this won't be reached)")
""", timeout=3)  # 3 second timeout

        execution_time = time.time() - start_time

        print(f"Success: {result.success}")
        print(f"Exit code: {result.exit_code}")  # 124 indicates timeout
        print(f"Execution time: {execution_time:.1f}s")
        print(f"Partial output: '{result.stdout.strip()}'")

        if result.exit_code == 124:
            print("✓ Timeout properly detected and handled")

        # Demonstrate successful execution with adequate timeout
        print("\nSame code with sufficient timeout:")
        result2 = sandbox.run("""
import time
print("Starting quick operation...")
time.sleep(1)  # Short sleep
print("Operation completed successfully!")
""", timeout=5)  # 5 second timeout

        print(f"Success: {result2.success}")
        print(f"Output: {result2.stdout.strip()}")


def demonstrate_error_recovery():
    """Demonstrate robust error recovery strategies."""
    print("\n4. Error Recovery Strategies")
    print("-" * 29)

    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        print("a) Graceful degradation:")

        # Setup initial state
        sandbox.run("""
data = [1, 2, 3, 4, 5]
print(f"Initial data: {data}")
""")

        # Attempt operation with fallback
        result1 = sandbox.run("""
try:
    # Try preferred method (will fail)
    import numpy as np
    result = np.mean(data)
    method = "numpy"
except ImportError:
    # Fallback to built-in method
    result = sum(data) / len(data)
    method = "built-in"

print(f"Calculated mean using {method}: {result}")
""")
        print(f"Output: {result1.stdout.strip()}")

        print("\nb) Container restart for recovery:")

        # Simulate problematic state
        result2 = sandbox.run("""
# Simulate code that puts container in bad state
import sys
print("Simulating problematic state...")
# In real scenarios, this might be memory leaks, corrupted state, etc.
problematic_state = "This could represent corrupted state"
print(f"State: {problematic_state}")
""")
        print(f"Before restart: {result2.stdout.strip()}")

        # Check container state and restart if needed
        print("Restarting container for clean slate...")
        container_info = sandbox.get_container_info()
        old_container_id = container_info['container_id']
        new_container_id = sandbox.restart_container()
        print(f"Container restarted: {old_container_id[:12]} -> {new_container_id[:12]}")

        # Verify clean state
        result3 = sandbox.run("""
try:
    print(f"Problematic state: {problematic_state}")
except NameError:
    print("✓ Clean state after restart")

# Re-establish good state
data = [10, 20, 30, 40, 50]
print(f"Fresh data: {data}")
""")
        print(f"After restart: {result3.stdout.strip()}")

        print("\nc) Multiple attempt strategy:")

        attempts = 0
        max_attempts = 3
        success = False

        while attempts < max_attempts and not success:
            attempts += 1
            print(f"Attempt {attempts}:")

            if attempts == 1:
                # First attempt - will fail
                code = "result = risky_operation_that_fails()"
            elif attempts == 2:
                # Second attempt - define the function but make it fail
                code = """
def risky_operation_that_fails():
    raise ConnectionError("Simulated network error")

try:
    result = risky_operation_that_fails()
    print(f"Success: {result}")
except ConnectionError as e:
    print(f"Attempt failed: {e}")
    raise
"""
            else:
                # Final attempt - provide working fallback
                code = """
def safe_operation():
    return "fallback_result"

try:
    # Try risky operation first
    result = risky_operation_that_fails()
except:
    # Use safe fallback
    result = safe_operation()
    print(f"Using fallback: {result}")

success = True
print("✓ Operation completed successfully")
"""

            result = sandbox.run(code)

            if result.success and "success = True" in code:
                success = True
                print(f"Success after {attempts} attempts")
                print(f"Output: {result.stdout.strip()}")
            else:
                print(f"Attempt {attempts} failed")
                if result.stderr:
                    print(f"Error: {result.stderr.strip()}")


def demonstrate_validation():
    """Demonstrate input validation before execution."""
    print("\n5. Input Validation")
    print("-" * 18)

    import ast

    def is_safe_code(code: str) -> tuple[bool, str]:
        """Basic validation of Python code."""
        try:
            ast.parse(code)
            return True, "Code is syntactically valid"
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

    test_codes = [
        "print('Hello World')",  # Valid
        "print('Hello World)",   # Invalid - missing quote
        "x = 42; print(x)",      # Valid
        "for i in range(10 print(i)",  # Invalid - missing colon
    ]

    with BioCageOrchestrator() as sandbox:
        for i, code in enumerate(test_codes, 1):
            print(f"\nValidating code {i}: {code}")

            is_valid, message = is_safe_code(code)
            print(f"Validation: {message}")

            if is_valid:
                result = sandbox.run(code)
                if result.success:
                    print(f"Execution successful: {result.stdout.strip()}")
                else:
                    print(f"Execution failed: {result.stderr.strip()}")
            else:
                print("Skipping execution due to validation failure")


if __name__ == "__main__":
    main()
    demonstrate_validation()