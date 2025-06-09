#!/usr/bin/env python3
"""
Safe code execution script for the Docker container.
Executes Python code with timeout and output capture.
"""

import sys
import os
import json
import subprocess
import tempfile
import signal
from pathlib import Path
from contextlib import contextmanager

# Timeout for code execution (in seconds)
EXECUTION_TIMEOUT = 30

@contextmanager
def timeout_handler(seconds):
    """Context manager for handling execution timeout."""
    def timeout_signal_handler(signum, frame):
        raise TimeoutError(f"Code execution timed out after {seconds} seconds")
    
    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_signal_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Reset the alarm and restore the old handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

def execute_python_code(code: str) -> dict:
    """
    Execute Python code safely and return results.
    
    Args:
        code: Python code string to execute
        
    Returns:
        dict: Execution results with stdout, stderr, and exit_code
    """
    result = {
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "execution_time": 0,
        "error": None
    }
    
    try:
        # Create a temporary file for the code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/app/workspace') as temp_file:
            temp_file.write(code)
            temp_file_path = temp_file.name
        
        # Execute the code with timeout
        with timeout_handler(EXECUTION_TIMEOUT):
            import time
            start_time = time.time()
            
            process = subprocess.run(
                [sys.executable, temp_file_path],
                capture_output=True,
                text=True,
                cwd='/app/workspace',
                timeout=EXECUTION_TIMEOUT
            )
            
            end_time = time.time()
            result["execution_time"] = end_time - start_time
            result["stdout"] = process.stdout
            result["stderr"] = process.stderr
            result["exit_code"] = process.returncode
            
    except TimeoutError as e:
        result["error"] = str(e)
        result["exit_code"] = 124  # Standard timeout exit code
    except subprocess.TimeoutExpired:
        result["error"] = f"Process timed out after {EXECUTION_TIMEOUT} seconds"
        result["exit_code"] = 124
    except Exception as e:
        result["error"] = f"Execution error: {str(e)}"
        result["exit_code"] = 1
    finally:
        # Clean up temporary file
        try:
            if 'temp_file_path' in locals():
                os.unlink(temp_file_path)
        except OSError:
            pass
    
    return result

def main():
    """Main execution function."""
    # Check for different input methods
    
    # Method 1: Code from environment variable
    if 'PYTHON_CODE' in os.environ:
        code = os.environ['PYTHON_CODE']
    
    # Method 2: Code from stdin
    elif not sys.stdin.isatty():
        code = sys.stdin.read()
    
    # Method 3: Code from file
    elif len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r') as f:
                code = f.read()
        except FileNotFoundError:
            print(json.dumps({
                "error": f"File not found: {sys.argv[1]}",
                "exit_code": 2
            }))
            sys.exit(2)
    
    # Method 4: Interactive mode (for testing)
    else:
        print("Python Code Executor - Enter your code (Ctrl+D to execute):")
        try:
            code = sys.stdin.read()
        except KeyboardInterrupt:
            print("\nExecution cancelled.")
            sys.exit(130)
    
    if not code.strip():
        print(json.dumps({
            "error": "No code provided",
            "exit_code": 1
        }))
        sys.exit(1)
    
    # Execute the code
    result = execute_python_code(code)
    
    # Output results as JSON
    print(json.dumps(result, indent=2))
    
    # Exit with the same code as the executed script
    sys.exit(result["exit_code"])

if __name__ == "__main__":
    main() 