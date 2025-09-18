#!/usr/bin/env python3
"""
Example demonstrating BioCage ephemeral execution mode.

This script shows how ephemeral mode creates fresh containers for each
execution, providing maximum isolation and security by ensuring no
state persists between executions.
"""

from biocage import BioCageOrchestrator


def main():
    print("BioCage Ephemeral Mode Example")
    print("=" * 40)

    # Ephemeral mode creates fresh containers for each execution
    with BioCageOrchestrator(execution_mode="ephemeral") as sandbox:
        print("\n1. First execution - defining variables...")

        # First execution - define variables
        result1 = sandbox.run("""
x = 42
y = 10
z = x + y
print(f"Defined: x={x}, y={y}, z={z}")
""")
        print(f"Result: {result1.stdout.strip()}")
        print(f"Success: {result1.success}")

        print("\n2. Second execution - variables are NOT available...")

        # Second execution - previous variables are not available
        result2 = sandbox.run("""
try:
    print(f"x = {x}")  # This will fail
except NameError as e:
    print(f"NameError: {e}")
    print("Variables from previous execution are not available")
""")
        print(f"Result: {result2.stdout.strip()}")
        print(f"Success: {result2.success}")

        print("\n3. Third execution - fresh environment again...")

        # Third execution - completely fresh environment
        result3 = sandbox.run("""
# Define new variables (completely independent)
a = 100
b = 200
print(f"New variables: a={a}, b={b}")

# Try to access previous variables
try:
    print(f"Old x was: {x}")
except NameError:
    print("Previous variables (x) not accessible")

try:
    print(f"Old z was: {z}")
except NameError:
    print("Previous variables (z) not accessible")
""")
        print(f"Result: {result3.stdout.strip()}")
        print(f"Success: {result3.success}")

        print("\n4. Fourth execution - imports also don't persist...")

        # Fourth execution - imports don't persist either
        result4 = sandbox.run("""
import math
import datetime

# Check if previous variables exist
try:
    print(f"Variable 'a' from previous execution: {a}")
except NameError:
    print("Variable 'a' not found (expected in ephemeral mode)")

# Use fresh imports
pi_value = math.pi
current_time = datetime.datetime.now().strftime("%H:%M:%S")
print(f"Fresh calculation: π = {pi_value:.6f}")
print(f"Current time: {current_time}")
""")
        print(f"Result: {result4.stdout.strip()}")

        print("\n5. Fifth execution - even imports are gone...")

        result5 = sandbox.run("""
try:
    print(f"Pi is: {math.pi}")
except NameError:
    print("math module not available (imports don't persist)")

try:
    print(f"Time was: {current_time}")
except NameError:
    print("current_time variable not available")

print("Each execution is completely isolated!")
""")
        print(f"Result: {result5.stdout.strip()}")

    print("\n" + "=" * 40)
    print("Ephemeral mode characteristics:")
    print("✓ Maximum isolation between executions")
    print("✓ No state leakage or persistence")
    print("✓ Fresh Python environment each time")
    print("✓ Ideal for untrusted code execution")
    print("✓ Higher security, lower performance")


def demonstrate_security_benefit():
    """Demonstrate the security benefit of ephemeral mode."""
    print("\n" + "=" * 50)
    print("Security Demonstration")
    print("=" * 50)

    with BioCageOrchestrator(execution_mode="ephemeral") as sandbox:
        print("\n1. Simulating potentially malicious code...")

        # First execution - "malicious" code tries to set up persistence
        result1 = sandbox.run("""
# Simulate malicious code trying to persist
secret_password = "hidden_password_123"
malicious_data = {"passwords": ["user1:pass1", "user2:pass2"]}

print("Malicious code executed (simulated)")
print(f"Stored secret: {secret_password}")
print(f"Stored data: {malicious_data}")
""")
        print(f"Malicious execution result: {result1.stdout.strip()}")

        print("\n2. Next execution - malicious data is gone...")

        # Second execution - malicious data is not available
        result2 = sandbox.run("""
try:
    print(f"Retrieved secret: {secret_password}")
except NameError:
    print("✓ Secret password not accessible")

try:
    print(f"Retrieved data: {malicious_data}")
except NameError:
    print("✓ Malicious data not accessible")

print("✓ Ephemeral mode prevented data persistence")
""")
        print(f"Clean execution result: {result2.stdout.strip()}")


if __name__ == "__main__":
    main()
    demonstrate_security_benefit()