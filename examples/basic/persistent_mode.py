#!/usr/bin/env python3
"""
Example demonstrating BioCage persistent execution mode.

This script shows how variables and imports persist between executions
in persistent mode, making it ideal for interactive workflows and
multi-step computations.
"""

from biocage import BioCageOrchestrator


def main():
    print("BioCage Persistent Mode Example")
    print("=" * 40)

    # Persistent mode maintains state between executions
    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        print("\n1. Setting up initial state...")

        # First execution - define variables and imports
        result1 = sandbox.run("""
x = 42
y = 10
print(f"Defined: x={x}, y={y}")
""")
        print(f"Result: {result1.stdout.strip()}")

        print("\n2. Using persistent variables...")

        # Second execution - variables persist
        result2 = sandbox.run("""
z = x * y
print(f"Calculated: z = x * y = {z}")
""")
        print(f"Result: {result2.stdout.strip()}")

        print("\n3. Adding imports that persist...")

        # Third execution - import libraries
        result3 = sandbox.run("""
import math
import datetime

sqrt_z = math.sqrt(z)
current_time = datetime.datetime.now().strftime("%H:%M:%S")
print(f"sqrt({z}) = {sqrt_z:.2f}")
print(f"Time: {current_time}")
""")
        print(f"Result: {result3.stdout.strip()}")

        print("\n4. Building on persistent state...")

        # Fourth execution - everything is still available
        result4 = sandbox.run("""
# All previous variables and imports are available
data = {
    'original_x': x,
    'original_y': y,
    'calculated_z': z,
    'sqrt_z': sqrt_z,
    'pi': math.pi,
    'timestamp': current_time
}

for key, value in data.items():
    print(f"{key}: {value}")
""")
        print(f"Result: {result4.stdout.strip()}")

        print("\n5. Demonstrating container restart with state recovery...")

        # Force container restart (state will be automatically restored)
        container_info = sandbox.get_container_info()
        old_container_id = container_info['container_id']
        new_container_id = sandbox.restart_container()

        print(f"Container restarted: {old_container_id[:12]} -> {new_container_id[:12]}")

        # State is automatically restored after restart
        result5 = sandbox.run("""
print("After container restart:")
print(f"x = {x}")
print(f"y = {y}")
print(f"z = {z}")
print(f"sqrt_z = {sqrt_z:.2f}")
print(f"math.pi = {math.pi:.6f}")
""")
        print(f"Result: {result5.stdout.strip()}")

    print("\n" + "=" * 40)
    print("Persistent mode allows:")
    print("✓ Variables persist between executions")
    print("✓ Imports remain loaded")
    print("✓ State survives container restarts")
    print("✓ Better performance for workflows")


if __name__ == "__main__":
    main()