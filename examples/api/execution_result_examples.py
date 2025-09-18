#!/usr/bin/env python3
"""
Example demonstrating SandboxExecutionResult API usage.

This script shows how to work with execution results, including
success checking, error handling, timing analysis, and result
serialization.
"""

from biocage import BioCageOrchestrator
import json
import time


def main():
    print("SandboxExecutionResult API Examples")
    print("=" * 39)

    demonstrate_basic_result_properties()
    demonstrate_success_handling()
    demonstrate_error_analysis()
    demonstrate_timing_analysis()
    demonstrate_result_serialization()
    demonstrate_result_comparison()


def demonstrate_basic_result_properties():
    """Demonstrate basic SandboxExecutionResult properties."""
    print("\n1. Basic Result Properties")
    print("-" * 26)

    with BioCageOrchestrator() as sandbox:
        # Successful execution
        result = sandbox.run("print('Hello, World!')")

        print("Successful execution result:")
        print(f"  stdout: '{result.stdout.strip()}'")
        print(f"  stderr: '{result.stderr}'")
        print(f"  exit_code: {result.exit_code}")
        print(f"  execution_time: {result.execution_time:.4f} seconds")
        print(f"  error: {result.error}")
        print(f"  success: {result.success}")

        # Result with both stdout and calculation
        result2 = sandbox.run("""
import math
x = 42
result = math.sqrt(x)
print(f'The square root of {x} is {result:.2f}')
print(f'Verification: {result:.2f}^2 = {result**2:.1f}')
""")

        print("\nCalculation result:")
        print(f"  stdout: '{result2.stdout.strip()}'")
        print(f"  success: {result2.success}")
        print(f"  lines of output: {len(result2.stdout.strip().split('\\n'))}")

        # Result with no output
        result3 = sandbox.run("x = 100; y = 200; z = x + y")

        print("\nSilent execution result:")
        print(f"  stdout: '{result3.stdout}'")
        print(f"  stderr: '{result3.stderr}'")
        print(f"  success: {result3.success}")
        print(f"  execution_time: {result3.execution_time:.4f} seconds")


def demonstrate_success_handling():
    """Demonstrate different ways to handle execution success."""
    print("\n2. Success Handling Patterns")
    print("-" * 28)

    test_cases = [
        ("Successful execution", "print('Success!')"),
        ("Syntax error", "print('Missing quote)"),
        ("Runtime error", "undefined_variable"),
        ("Import error", "import nonexistent_module"),
        ("Zero division", "result = 1 / 0")
    ]

    with BioCageOrchestrator() as sandbox:
        for description, code in test_cases:
            print(f"\n{description}:")
            result = sandbox.run(code)

            # Pattern 1: Simple success check
            if result.success:
                print(f"  ✓ Success: {result.stdout.strip()}")
            else:
                print(f"  ✗ Failed: {result.stderr.strip()}")

            # Pattern 2: Exit code checking
            if result.exit_code == 0:
                print(f"  Exit code indicates success")
            else:
                print(f"  Exit code {result.exit_code} indicates failure")

            # Pattern 3: Comprehensive checking
            status = "SUCCESS" if result.success else "FAILURE"
            timing = f"({result.execution_time:.3f}s)"
            print(f"  Status: {status} {timing}")


def demonstrate_error_analysis():
    """Demonstrate error analysis and debugging."""
    print("\n3. Error Analysis and Debugging")
    print("-" * 32)

    error_scenarios = [
        {
            "name": "Syntax Error",
            "code": "if True print('missing colon')",
            "expected_type": "SyntaxError"
        },
        {
            "name": "Name Error",
            "code": "print(undefined_variable)",
            "expected_type": "NameError"
        },
        {
            "name": "Type Error",
            "code": "'string' + 42",
            "expected_type": "TypeError"
        },
        {
            "name": "Index Error",
            "code": "my_list = [1, 2, 3]; print(my_list[10])",
            "expected_type": "IndexError"
        },
        {
            "name": "Key Error",
            "code": "my_dict = {'a': 1}; print(my_dict['b'])",
            "expected_type": "KeyError"
        }
    ]

    with BioCageOrchestrator() as sandbox:
        for scenario in error_scenarios:
            name = scenario["name"]
            code = scenario["code"]
            expected = scenario["expected_type"]

            print(f"\n{name}:")
            print(f"  Code: {code}")

            result = sandbox.run(code)

            if not result.success:
                print(f"  Success: {result.success}")
                print(f"  Exit code: {result.exit_code}")

                # Analyze error message
                error_lines = result.stderr.strip().split('\n')
                print(f"  Error lines: {len(error_lines)}")

                # Look for expected error type
                full_error = result.stderr
                if expected in full_error:
                    print(f"  ✓ Found expected {expected}")
                else:
                    print(f"  ? Expected {expected}, got different error")

                # Extract key error information
                if error_lines:
                    last_line = error_lines[-1]
                    print(f"  Key error: {last_line}")

            else:
                print(f"  Unexpected success: {result.stdout.strip()}")

        # Demonstrate error recovery
        print(f"\nError Recovery:")
        sandbox.run("good_variable = 'This works'")
        result = sandbox.run("print(good_variable)")
        print(f"  Recovery successful: {result.success}")
        print(f"  Output: {result.stdout.strip()}")


def demonstrate_timing_analysis():
    """Demonstrate execution timing analysis."""
    print("\n4. Timing Analysis")
    print("-" * 17)

    timing_tests = [
        ("Quick operation", "print('hello')"),
        ("Simple calculation", "sum(range(1000))"),
        ("Medium calculation", "sum(i*i for i in range(10000))"),
        ("String operations", "''.join(str(i) for i in range(1000))"),
        ("Import operation", "import json, math, random"),
        ("File operation", "open('/tmp/test.txt', 'w').write('test'); print('file written')")
    ]

    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        timing_results = []

        for description, code in timing_tests:
            print(f"\n{description}:")

            # Run multiple times for better timing
            times = []
            for i in range(3):
                result = sandbox.run(code)
                times.append(result.execution_time)

                if result.success:
                    output_preview = result.stdout.strip()[:50]
                    if len(result.stdout.strip()) > 50:
                        output_preview += "..."
                    print(f"  Run {i+1}: {result.execution_time:.4f}s - {output_preview}")
                else:
                    print(f"  Run {i+1}: {result.execution_time:.4f}s - ERROR")

            # Calculate statistics
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            timing_results.append({
                'operation': description,
                'avg_time': avg_time,
                'min_time': min_time,
                'max_time': max_time,
                'runs': len(times)
            })

            print(f"  Average: {avg_time:.4f}s, Min: {min_time:.4f}s, Max: {max_time:.4f}s")

        # Summary of timing analysis
        print(f"\nTiming Summary:")
        timing_results.sort(key=lambda x: x['avg_time'])

        for result in timing_results:
            print(f"  {result['operation']:<20}: {result['avg_time']:.4f}s avg")

        # Identify patterns
        fastest = timing_results[0]
        slowest = timing_results[-1]
        print(f"\nFastest: {fastest['operation']} ({fastest['avg_time']:.4f}s)")
        print(f"Slowest: {slowest['operation']} ({slowest['avg_time']:.4f}s)")
        print(f"Speed difference: {slowest['avg_time'] / fastest['avg_time']:.1f}x")


def demonstrate_result_serialization():
    """Demonstrate result serialization and deserialization."""
    print("\n5. Result Serialization")
    print("-" * 21)

    with BioCageOrchestrator() as sandbox:
        # Create various types of results
        results = []

        # Successful result
        result1 = sandbox.run("print('Success result'); print('Line 2')")
        results.append(("Success", result1))

        # Error result
        result2 = sandbox.run("undefined_function()")
        results.append(("Error", result2))

        # Long output result
        result3 = sandbox.run("for i in range(5): print(f'Line {i+1}')")
        results.append(("Multi-line", result3))

        # Result with timing
        result4 = sandbox.run("import time; time.sleep(0.1); print('Timed operation')")
        results.append(("Timed", result4))

        print("Serializing results to dictionaries:")
        serialized_results = []

        for name, result in results:
            print(f"\n{name} result:")

            # Convert to dictionary
            result_dict = result.to_dict()
            serialized_results.append((name, result_dict))

            # Display dictionary contents
            for key, value in result_dict.items():
                if key in ['stdout', 'stderr']:
                    # Truncate long strings for display
                    display_value = repr(value[:50] + "..." if len(value) > 50 else value)
                else:
                    display_value = repr(value)
                print(f"  {key}: {display_value}")

        print(f"\nJSON serialization:")

        # Serialize to JSON
        json_data = []
        for name, result_dict in serialized_results:
            json_entry = {
                'name': name,
                'result': result_dict
            }
            json_data.append(json_entry)

        # Convert to JSON string
        json_string = json.dumps(json_data, indent=2)
        print(f"JSON length: {len(json_string)} characters")
        print(f"JSON preview: {json_string[:200]}...")

        # Demonstrate JSON round-trip
        parsed_data = json.loads(json_string)
        print(f"\nJSON round-trip successful:")
        print(f"Parsed {len(parsed_data)} result entries")

        for entry in parsed_data:
            name = entry['name']
            result_data = entry['result']
            success = result_data['success']
            exec_time = result_data['execution_time']
            print(f"  {name}: success={success}, time={exec_time:.4f}s")


def demonstrate_result_comparison():
    """Demonstrate comparing and analyzing multiple results."""
    print("\n6. Result Comparison and Analysis")
    print("-" * 34)

    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        # Execute the same operation multiple times
        operation = "import random; result = sum(random.randint(1, 100) for _ in range(1000)); print(f'Sum: {result}')"

        print("Running same operation multiple times:")
        results = []

        for i in range(5):
            result = sandbox.run(operation)
            results.append(result)
            print(f"  Run {i+1}: success={result.success}, time={result.execution_time:.4f}s")

        # Analyze results
        print(f"\nResult Analysis:")

        # Success rate
        successful_runs = sum(1 for r in results if r.success)
        success_rate = (successful_runs / len(results)) * 100
        print(f"  Success rate: {successful_runs}/{len(results)} ({success_rate:.1f}%)")

        # Timing statistics
        times = [r.execution_time for r in results if r.success]
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            variance = sum((t - avg_time) ** 2 for t in times) / len(times)
            std_dev = variance ** 0.5

            print(f"  Timing statistics:")
            print(f"    Average: {avg_time:.4f}s")
            print(f"    Min: {min_time:.4f}s")
            print(f"    Max: {max_time:.4f}s")
            print(f"    Std dev: {std_dev:.4f}s")
            print(f"    Coefficient of variation: {(std_dev/avg_time)*100:.1f}%")

        # Output analysis
        outputs = [r.stdout.strip() for r in results if r.success]
        unique_outputs = set(outputs)
        print(f"  Output analysis:")
        print(f"    Total outputs: {len(outputs)}")
        print(f"    Unique outputs: {len(unique_outputs)}")

        if len(unique_outputs) > 1:
            print(f"    Output samples:")
            for i, output in enumerate(list(unique_outputs)[:3]):
                print(f"      {i+1}: {output}")

        # Compare different operations
        print(f"\nComparing different operations:")

        operations = [
            ("Math operation", "import math; print(f'Result: {math.sqrt(12345):.2f}')"),
            ("String operation", "text = 'hello world'; print(f'Upper: {text.upper()}')"),
            ("List operation", "numbers = list(range(100)); print(f'Sum: {sum(numbers)}')"),
        ]

        comparison_results = []
        for name, code in operations:
            result = sandbox.run(code)
            comparison_results.append((name, result))
            print(f"  {name}: {result.success}, {result.execution_time:.4f}s")

        # Find fastest and slowest
        successful_comparisons = [(name, result) for name, result in comparison_results if result.success]
        if successful_comparisons:
            fastest = min(successful_comparisons, key=lambda x: x[1].execution_time)
            slowest = max(successful_comparisons, key=lambda x: x[1].execution_time)

            print(f"\n  Fastest: {fastest[0]} ({fastest[1].execution_time:.4f}s)")
            print(f"  Slowest: {slowest[0]} ({slowest[1].execution_time:.4f}s)")

            if fastest[1].execution_time > 0:
                speedup = slowest[1].execution_time / fastest[1].execution_time
                print(f"  Speed difference: {speedup:.1f}x")


if __name__ == "__main__":
    main()