#!/usr/bin/env python3
"""
Simple BioCage demonstration showing basic functionality.

This script demonstrates the core features of BioCage in a straightforward
way without complex error handling or advanced features.
"""

from biocage import BioCageOrchestrator
from pathlib import Path
import time


def main():
    print("BioCage Simple Demonstration")
    print("=" * 30)

    # Test 1: Basic execution
    print("\n1. Basic Code Execution")
    print("-" * 22)

    with BioCageOrchestrator() as sandbox:
        result = sandbox.run("print('Hello from BioCage!')")
        print(f"✓ Success: {result.success}")
        print(f"✓ Output: {result.stdout.strip()}")
        print(f"✓ Time: {result.execution_time:.3f}s")

    # Test 2: Persistent mode
    print("\n2. Persistent Mode")
    print("-" * 16)

    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        # Set a variable
        result1 = sandbox.run("x = 42")
        print(f"Set variable: success={result1.success}")

        # Use the variable
        result2 = sandbox.run("print(f'x = {x}')")
        print(f"Read variable: {result2.stdout.strip()}")

    # Test 3: Ephemeral mode
    print("\n3. Ephemeral Mode")
    print("-" * 16)

    with BioCageOrchestrator(execution_mode="ephemeral") as sandbox:
        # First execution
        result1 = sandbox.run("y = 100; print(f'Set y = {y}')")
        print(f"First execution: {result1.stdout.strip()}")

        # Second execution (y should not exist)
        result2 = sandbox.run("try:\n    print(f'y = {y}')\nexcept NameError:\n    print('y not found (expected)')")
        print(f"Second execution: {result2.stdout.strip()}")

    # Test 4: File operations
    print("\n4. File Operations")
    print("-" * 17)

    # Use sample data
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    csv_file = data_dir / "sample_data.csv"

    if csv_file.exists():
        with BioCageOrchestrator() as sandbox:
            # Expose the CSV file
            container_path = sandbox.expose_file(str(csv_file), "/app/data.csv")
            print(f"Exposed file: {container_path}")

            # Read and analyze the file
            result = sandbox.run("""
import pandas as pd
df = pd.read_csv('/app/data.csv')
print(f'Dataset: {len(df)} rows, {len(df.columns)} columns')
print(f'Average age: {df["age"].mean():.1f}')
print(f'Departments: {df["department"].nunique()}')
""")
            print("File analysis:")
            print(result.stdout.strip())
    else:
        print("Sample data not found, skipping file operations")

    # Test 5: Error handling
    print("\n5. Error Handling")
    print("-" * 16)

    with BioCageOrchestrator() as sandbox:
        # Intentional error
        result = sandbox.run("undefined_variable")
        print(f"Error execution: success={result.success}")
        print(f"Exit code: {result.exit_code}")
        if not result.success:
            print("Error message:", result.stderr.strip().split('\n')[-1])

        # Recovery
        result2 = sandbox.run("print('Recovery successful')")
        print(f"Recovery: {result2.stdout.strip()}")

    # Test 6: Different resource configurations
    print("\n6. Resource Configurations")
    print("-" * 26)

    configs = [
        {"memory_limit": "256m", "cpu_limit": "0.5"},
        {"memory_limit": "1g", "cpu_limit": "2.0"},
        {"network_access": True}
    ]

    for i, config in enumerate(configs, 1):
        print(f"\nConfig {i}: {config}")
        try:
            with BioCageOrchestrator(**config) as sandbox:
                result = sandbox.run("import sys; print(f'Python {sys.version.split()[0]} ready')")
                print(f"  Result: {result.stdout.strip()}")

                # Get container info
                info = sandbox.get_container_info()
                print(f"  Memory: {info['memory_limit']}, CPU: {info['cpu_limit']}")
        except Exception as e:
            print(f"  Error: {e}")

    print("\n" + "=" * 30)
    print("✓ BioCage demonstration complete!")
    print("\nKey features demonstrated:")
    print("- Basic code execution")
    print("- Persistent vs ephemeral modes")
    print("- File operations")
    print("- Error handling and recovery")
    print("- Resource configuration")


if __name__ == "__main__":
    main()