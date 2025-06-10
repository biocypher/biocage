"""Test error reporting and handling functionality."""

from codesandbox import PythonSandboxManager


class TestBasicErrorReporting:
    """Test basic error reporting functionality."""

    def test_syntax_error_reporting(self):
        """Test that syntax errors are properly reported."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("print('Hello'  # Missing closing parenthesis")

            assert not result.success
            assert result.exit_code != 0
            assert "SyntaxError" in result.stderr
            assert result.stdout == ""  # No stdout for syntax errors

    def test_runtime_error_reporting(self):
        """Test that runtime errors are properly reported."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("x = 1 / 0")

            assert not result.success
            assert "ZeroDivisionError" in result.stderr
            assert "division by zero" in result.stderr

    def test_name_error_reporting(self):
        """Test that name errors are properly reported."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("print(undefined_variable)")

            assert not result.success
            assert "NameError" in result.stderr
            assert "undefined_variable" in result.stderr

    def test_import_error_reporting(self):
        """Test that import errors are properly reported."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("import nonexistent_module")

            assert not result.success
            assert "ModuleNotFoundError" in result.stderr
            assert "nonexistent_module" in result.stderr

    def test_indentation_error_reporting(self):
        """Test that indentation errors are properly reported."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("""
if True:
print("Bad indent")
""")

            assert not result.success
            assert "IndentationError" in result.stderr

    def test_type_error_reporting(self):
        """Test that type errors are properly reported."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run('"hello" + 5')

            assert not result.success
            assert "TypeError" in result.stderr

    def test_key_error_reporting(self):
        """Test that key errors are properly reported."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run('my_dict = {"a": 1}; print(my_dict["b"])')

            assert not result.success
            assert "KeyError" in result.stderr

    def test_index_error_reporting(self):
        """Test that index errors are properly reported."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("my_list = [1, 2, 3]; print(my_list[10])")

            assert not result.success
            assert "IndexError" in result.stderr
            assert "out of range" in result.stderr


class TestPartialOutputOnError:
    """Test that partial output is captured before errors occur."""

    def test_partial_stdout_before_error(self):
        """Test that stdout before error is captured."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("""
print("Line 1")
print("Line 2")
x = 1 / 0
print("This won't print")
""")

            assert not result.success
            assert "Line 1" in result.stdout
            assert "Line 2" in result.stdout
            assert "This won't print" not in result.stdout
            assert "ZeroDivisionError" in result.stderr

    def test_partial_output_with_variables(self):
        """Test partial execution with variable assignments."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("""
x = 10
y = 20
print(f"x + y = {x + y}")
z = x / 0  # This will cause an error
print("Won't reach here")
""")

            assert not result.success
            assert "x + y = 30" in result.stdout
            assert "Won't reach here" not in result.stdout
            assert "ZeroDivisionError" in result.stderr

    def test_multiple_print_statements_before_error(self):
        """Test multiple print statements before error."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("""
for i in range(3):
    print(f"Iteration {i}")
undefined_variable  # Error here
print("Final line")
""")

            assert not result.success
            assert "Iteration 0" in result.stdout
            assert "Iteration 1" in result.stdout
            assert "Iteration 2" in result.stdout
            assert "Final line" not in result.stdout
            assert "NameError" in result.stderr


class TestErrorHandlingWithShutdown:
    """Test error handling with different shutdown policies."""

    def test_error_with_shutdown_disabled(self):
        """Test that errors don't shutdown container when disabled."""
        with PythonSandboxManager() as sandbox:
            # First, run code that fails
            result1 = sandbox.run("x = 1 / 0", shutdown_on_failure=False)
            assert not result1.success
            assert "ZeroDivisionError" in result1.stderr

            # Container should still be running
            assert sandbox.is_running

            # Should be able to run more code
            result2 = sandbox.run("print('Still working after error')")
            assert result2.success
            assert "Still working after error" in result2.stdout

    def test_multiple_errors_with_shutdown_disabled(self):
        """Test multiple errors with shutdown disabled."""
        with PythonSandboxManager() as sandbox:
            # First error
            result1 = sandbox.run("undefined_var", shutdown_on_failure=False)
            assert not result1.success
            assert "NameError" in result1.stderr

            # Second error
            result2 = sandbox.run("1 / 0", shutdown_on_failure=False)
            assert not result2.success
            assert "ZeroDivisionError" in result2.stderr

            # Should still work
            result3 = sandbox.run("print('Survived multiple errors')")
            assert result3.success
            assert "Survived multiple errors" in result3.stdout

    def test_error_with_persistence_after_failure(self):
        """Test that state persists after error when shutdown is disabled."""
        with PythonSandboxManager() as sandbox:
            # Set up some state
            result1 = sandbox.run("counter = 5")
            assert result1.success

            # Run code that fails
            result2 = sandbox.run("counter += 3; x = 1 / 0", shutdown_on_failure=False)
            assert not result2.success
            assert "ZeroDivisionError" in result2.stderr

            # Check that successful part of the code executed
            result3 = sandbox.run("print(f'Counter: {counter}')")
            assert result3.success
            assert "Counter: 8" in result3.stdout  # Should be 5 + 3


class TestTimeoutHandling:
    """Test timeout error handling."""

    def test_timeout_error_reporting(self):
        """Test that timeouts are properly reported."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("import time; time.sleep(10)", timeout=2)

            assert not result.success
            assert result.exit_code == 124  # Standard timeout exit code

    def test_timeout_with_partial_output(self):
        """Test timeout with partial output capture."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run(
                """
import time
print("Starting long operation")
time.sleep(10)  # This will timeout
print("This won't print")
""",
                timeout=2,
            )

            assert not result.success
            assert result.exit_code == 124
            assert "Starting long operation" in result.stdout
            assert "This won't print" not in result.stdout

    def test_timeout_with_computation(self):
        """Test timeout during intensive computation."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run(
                """
print("Starting computation")
total = 0
for i in range(10000000):  # Large loop that should timeout
    total += i * i
    if i % 1000000 == 0:
        print(f"Progress: {i}")
print(f"Final total: {total}")
""",
                timeout=3,
            )

            assert not result.success
            assert result.exit_code == 124
            assert "Starting computation" in result.stdout


class TestEnhancedErrorReporting:
    """Test enhanced error reporting with debugging hints."""

    def test_syntax_error_with_hint(self):
        """Test syntax error with debugging hint."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("print('Hello'  # Missing closing parenthesis")

            assert not result.success
            assert "SyntaxError" in result.stderr

            # Check that we can categorize the error
            error_type = get_error_type(result.stderr)
            assert error_type == "Syntax Error"

    def test_name_error_with_hint(self):
        """Test name error with debugging hint."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("print(undefined_variable)")

            assert not result.success
            assert "NameError" in result.stderr

            error_type = get_error_type(result.stderr)
            assert error_type == "Name Error"

    def test_zero_division_error_with_hint(self):
        """Test division by zero with debugging hint."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("result = 10 / 0")

            assert not result.success
            assert "ZeroDivisionError" in result.stderr

            error_type = get_error_type(result.stderr)
            assert error_type == "Division by Zero Error"

    def test_import_error_with_hint(self):
        """Test import error with debugging hint."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("import fake_module")

            assert not result.success
            assert "ModuleNotFoundError" in result.stderr

            error_type = get_error_type(result.stderr)
            assert error_type == "Import Error"

    def test_type_error_with_hint(self):
        """Test type error with debugging hint."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run('"hello" + 5')

            assert not result.success
            assert "TypeError" in result.stderr

            error_type = get_error_type(result.stderr)
            assert error_type == "Type Error"

    def test_key_error_with_hint(self):
        """Test key error with debugging hint."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run('my_dict = {"a": 1}; print(my_dict["b"])')

            assert not result.success
            assert "KeyError" in result.stderr

            error_type = get_error_type(result.stderr)
            assert error_type == "Key Error"

    def test_index_error_with_hint(self):
        """Test index error with debugging hint."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("my_list = [1, 2, 3]; print(my_list[10])")

            assert not result.success
            assert "IndexError" in result.stderr

            error_type = get_error_type(result.stderr)
            assert error_type == "Index Error"


class TestAgentErrorIntegration:
    """Test error reporting suitable for agent integration."""

    def test_structured_error_message(self):
        """Test that error messages are structured for agent consumption."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("undefined_variable")

            # Simulate agent processing
            agent_message = format_agent_message(result)

            assert "NameError" in agent_message
            assert "undefined_variable" in agent_message
            assert not result.success

    def test_error_categorization_for_agents(self):
        """Test error categorization useful for agent debugging."""
        test_cases = [
            ("print('hello'", "Syntax Error"),
            ("undefined_var", "Name Error"),
            ("1 / 0", "Division by Zero Error"),
            ("import fake_module", "Import Error"),
            ('"str" + 5', "Type Error"),
        ]

        with PythonSandboxManager() as sandbox:
            for code, expected_category in test_cases:
                result = sandbox.run(code, shutdown_on_failure=False)
                assert not result.success

                category = get_error_type(result.stderr)
                assert category == expected_category

    def test_agent_friendly_error_format(self):
        """Test that errors are formatted in an agent-friendly way."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("""
print("Starting calculation")
x = 10 / 0
print("Won't reach here")
""")

            agent_message = format_agent_message(result)

            # Should contain both stdout and stderr
            assert "Starting calculation" in agent_message
            assert "ZeroDivisionError" in agent_message
            assert "Won't reach here" not in agent_message


def get_error_type(stderr):
    """Helper function to categorize errors based on stderr content."""
    stderr_lower = stderr.lower()

    if "syntaxerror" in stderr_lower:
        return "Syntax Error"
    elif "nameerror" in stderr_lower:
        return "Name Error"
    elif "zerodivisionerror" in stderr_lower:
        return "Division by Zero Error"
    elif "importerror" in stderr_lower or "modulenotfounderror" in stderr_lower:
        return "Import Error"
    elif "indentationerror" in stderr_lower:
        return "Indentation Error"
    elif "typeerror" in stderr_lower:
        return "Type Error"
    elif "keyerror" in stderr_lower:
        return "Key Error"
    elif "indexerror" in stderr_lower:
        return "Index Error"
    else:
        return "Unknown Error"


def format_agent_message(result):
    """Helper function to format execution result for agent consumption."""
    if result.exit_code == 124:  # Timeout
        return "⚠️ Code execution timed out.\n\nError: Execution timeout"
    elif result.stderr.strip():
        return f"Execution completed with errors:\n\nStdout:\n{result.stdout}\n\nStderr:\n{result.stderr}"
    else:
        return f"Execution completed successfully:\n\n{result.stdout}"


def get_debugging_hint(error_type):
    """Helper function to get debugging hints for different error types."""
    hints = {
        "Syntax Error": "Check for missing parentheses, quotes, or colons. Review Python syntax rules.",
        "Name Error": "A variable or function is not defined. Make sure to define variables before using them.",
        "Division by Zero Error": "Add a check to ensure the denominator is not zero before division.",
        "Import Error": "The module doesn't exist or isn't installed. Check the module name or install it if needed.",
        "Indentation Error": "Check your code indentation. Python uses consistent indentation to define code blocks.",
        "Type Error": "There's a mismatch between expected and actual data types. Check your variable types.",
        "Key Error": "Trying to access a dictionary key that doesn't exist. Check if the key exists first.",
        "Index Error": "List index is out of range. Check the list length before accessing indices.",
    }
    return hints.get(error_type, "Review the error message and check your code logic.")


class TestErrorRecovery:
    """Test error recovery and continuation."""

    def test_error_recovery_with_try_except(self):
        """Test that proper error handling works within the sandbox."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("""
try:
    x = 1 / 0
except ZeroDivisionError:
    print("Caught division by zero")
    x = 0

print(f"x = {x}")
print("Program continued successfully")
""")

            assert result.success
            assert "Caught division by zero" in result.stdout
            assert "x = 0" in result.stdout
            assert "Program continued successfully" in result.stdout

    def test_graceful_error_handling_pattern(self):
        """Test graceful error handling pattern for robust code."""
        with PythonSandboxManager() as sandbox:
            result = sandbox.run("""
def safe_divide(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        print(f"Warning: Cannot divide {a} by zero, returning None")
        return None

results = []
test_cases = [(10, 2), (5, 0), (8, 4)]

for a, b in test_cases:
    result = safe_divide(a, b)
    results.append(result)
    print(f"{a} / {b} = {result}")

print(f"Results: {results}")
""")

            assert result.success
            assert "5.0" in result.stdout  # 10/2
            assert "Warning: Cannot divide 5 by zero" in result.stdout
            assert "2.0" in result.stdout  # 8/4
            assert "None" in result.stdout
