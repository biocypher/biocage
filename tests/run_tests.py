#!/usr/bin/env python3
"""
Test runner script for CodeSandbox tests.

This script provides an easy way to run the test suite with common configurations.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle the result."""
    print(f"\n🚀 {description}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        print(f"✅ {description} - PASSED")
    else:
        print(f"❌ {description} - FAILED")

    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Run CodeSandbox tests")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")
    parser.add_argument("--no-docker", action="store_true", help="Skip tests that require Docker")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage reporting")
    parser.add_argument("--file", type=str, help="Run specific test file")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel (requires pytest-xdist)")

    args = parser.parse_args()

    # Base pytest command
    cmd = ["python", "-m", "pytest"]

    # Add verbosity
    if args.verbose:
        cmd.extend(["-v", "-s"])

    # Add coverage
    if args.coverage:
        cmd.extend(["--cov=codesandbox", "--cov-report=html", "--cov-report=term-missing"])

    # Add parallel execution
    if args.parallel:
        cmd.extend(["-n", "auto"])

    # Filter markers
    markers = []
    if args.fast:
        markers.append("not slow")
    if args.no_docker:
        markers.append("not docker")

    if markers:
        cmd.extend(["-m", " and ".join(markers)])

    # Specific file
    if args.file:
        test_file = Path(args.file)
        if not test_file.exists():
            test_file = Path("tests") / args.file
            if not test_file.exists():
                test_file = Path("tests") / f"test_{args.file}.py"

        if test_file.exists():
            cmd.append(str(test_file))
        else:
            print(f"❌ Test file not found: {args.file}")
            return False

    # Run the tests
    success = run_command(cmd, "Running CodeSandbox tests")

    if success:
        print("\n🎉 All tests passed!")
        if args.coverage:
            print("\n📊 Coverage report generated in htmlcov/index.html")
    else:
        print("\n💥 Some tests failed!")

    return success


def run_preset_commands():
    """Run preset test commands for common scenarios."""
    presets = [
        {
            "name": "Quick tests (no slow, no Docker requirements)",
            "cmd": ["python", "-m", "pytest", "-m", "not slow and not docker", "-v"],
            "description": "Fast tests that don't require Docker",
        },
        {
            "name": "Basic functionality tests",
            "cmd": ["python", "-m", "pytest", "tests/test_basic_functionality.py", "-v"],
            "description": "Core functionality tests",
        },
        {
            "name": "Persistence tests",
            "cmd": ["python", "-m", "pytest", "tests/test_persistence.py", "-v"],
            "description": "State persistence tests",
        },
        {
            "name": "File exposure tests",
            "cmd": ["python", "-m", "pytest", "tests/test_file_exposure.py", "-v"],
            "description": "File and directory exposure tests",
        },
        {
            "name": "Context manager tests",
            "cmd": ["python", "-m", "pytest", "tests/test_context_manager.py", "-v"],
            "description": "Context manager functionality tests",
        },
        {
            "name": "Error reporting tests",
            "cmd": ["python", "-m", "pytest", "tests/test_error_reporting.py", "-v"],
            "description": "Error handling and reporting tests",
        },
    ]

    print("Available test presets:")
    for i, preset in enumerate(presets, 1):
        print(f"{i}. {preset['name']}")

    choice = input("\nEnter preset number (or 'all' for all tests): ").strip()

    if choice.lower() == "all":
        cmd = ["python", "-m", "pytest", "-v"]
        return run_command(cmd, "Running all tests")

    try:
        preset_idx = int(choice) - 1
        if 0 <= preset_idx < len(presets):
            preset = presets[preset_idx]
            return run_command(preset["cmd"], preset["description"])
        else:
            print("Invalid choice!")
            return False
    except ValueError:
        print("Invalid choice!")
        return False


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments, show interactive menu
        success = run_preset_commands()
    else:
        # Parse command line arguments
        success = main()

    sys.exit(0 if success else 1)
