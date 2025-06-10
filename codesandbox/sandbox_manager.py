#!/usr/bin/env python3
"""
Enhanced Python Sandbox Manager with container lifecycle management,
file/path exposure, and clean execution interface.
"""

import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class SandboxExecutionResult:
    """Container for sandbox execution results."""

    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        execution_time: float = 0.0,
        error: Optional[str] = None,
    ):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.execution_time = execution_time
        self.error = error
        self.success = exit_code == 0 and error is None

    def __repr__(self):
        return f"SandboxExecutionResult(exit_code={self.exit_code}, success={self.success})"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "error": self.error,
            "success": self.success,
        }


class PythonSandboxManager:
    """
    Advanced Python sandbox manager with container lifecycle management,
    file/path exposure, and clean execution interface.
    """

    def __init__(self, image_name: str = "codesandbox:latest", container_name_prefix: str = "codesandbox"):
        self.image_name = image_name
        self.container_name_prefix = container_name_prefix
        self.container_id: Optional[str] = None
        self.container_name: Optional[str] = None
        self.is_running = False
        self.exposed_paths: Dict[str, Dict[str, str]] = {}  # host_path -> {"container_path": str, "mount_option": str}
        self.temp_files: List[str] = []  # Track temporary files for cleanup
        self._context_manager_kwargs: Dict[str, Any] = {}  # Store kwargs for context manager
        self._ensure_image_exists()

    def _ensure_image_exists(self):
        """Check if the Docker image exists, build it if not."""
        try:
            result = subprocess.run(
                ["docker", "images", "-q", self.image_name], capture_output=True, text=True, check=True
            )

            if not result.stdout.strip():
                print(f"Image {self.image_name} not found. Building...")
                self.build_image()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to check for Docker image: {e}")

    def build_image(self):
        """Build the Docker image."""
        try:
            print("Building CodeSandbox image...")
            subprocess.run(["docker", "build", "-t", self.image_name, "."], check=True)
            print("Image built successfully!")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to build Docker image: {e}")

    def start_container(self, memory_limit: str = "512m", cpu_limit: str = "1.0", network_access: bool = False) -> str:
        """
        Start a persistent container with a long-running Python process.

        Args:
            memory_limit: Memory limit (e.g., "512m", "1g")
            cpu_limit: CPU limit (e.g., "1.0", "0.5")
            network_access: Whether to allow network access

        Returns:
            Container ID
        """
        if self.is_running:
            raise RuntimeError("Container is already running. Call stop_container() first.")

        # Generate unique container name
        self.container_name = f"{self.container_name_prefix}-{uuid.uuid4().hex[:8]}"

        # Build docker run command
        docker_cmd = [
            "docker",
            "run",
            "-d",  # Detached mode
            "--name",
            self.container_name,
            "--init",  # Use init process
            f"--memory={memory_limit}",
            f"--cpus={cpu_limit}",
            "--security-opt=no-new-privileges:true",
            "--read-only",
            "--tmpfs=/app/workspace:size=100m,uid=999,gid=999",
            "--tmpfs=/tmp:noexec,nosuid,nodev,size=50m",
        ]

        # Network configuration
        if not network_access:
            docker_cmd.append("--network=none")

        # Add volume mounts for exposed paths
        for host_path, path_info in self.exposed_paths.items():
            container_path = path_info["container_path"]
            mount_option = path_info["mount_option"]
            docker_cmd.extend(["-v", f"{host_path}:{container_path}{mount_option}"])

        # Start container in sleep mode for persistent session
        docker_cmd.extend([self.image_name, "sleep", "infinity"])

        try:
            result = subprocess.run(docker_cmd, capture_output=True, text=True, check=True)
            self.container_id = result.stdout.strip()
            self.is_running = True

            # Wait a moment for the persistent executor to start
            time.sleep(0.5)

            print(f"Container started: {self.container_name} ({self.container_id[:12]})")
            return self.container_id
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to start container: {e.stderr}")

    def stop_container(self):
        """Stop and remove the container."""
        if not self.is_running or not self.container_name:
            return

        try:
            # Stop the container
            subprocess.run(["docker", "stop", self.container_name], capture_output=True, check=True)

            # Remove the container
            subprocess.run(["docker", "rm", self.container_name], capture_output=True, check=True)

            print(f"Container stopped and removed: {self.container_name}")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to clean up container {self.container_name}: {e}")
        finally:
            self.container_id = None
            self.container_name = None
            self.is_running = False

    def expose_path(
        self, host_path: Union[str, Path], container_path: Optional[str] = None, read_only: bool = True
    ) -> str:
        """
        Expose a host path to the container.

        Args:
            host_path: Path on the host system
            container_path: Path inside container (auto-generated if None)
            read_only: Whether the mount should be read-only

        Returns:
            The container path where the host path is mounted
        """
        host_path = Path(host_path).resolve()

        if not host_path.exists():
            raise FileNotFoundError(f"Host path does not exist: {host_path}")

        if container_path is None:
            # Auto-generate container path
            if host_path.is_file():
                container_path = f"/app/shared/{host_path.name}"
            else:
                container_path = f"/app/shared/{host_path.name}"

        # Store the mapping
        mount_option = ":ro" if read_only else ":rw"
        self.exposed_paths[str(host_path)] = {"container_path": container_path, "mount_option": mount_option}

        # If container is running, we need to restart it to apply new mounts
        if self.is_running:
            print("Restarting container to apply new path mapping...")
            self.stop_container()
            self.start_container()

        return container_path

    def expose_file(self, host_file_path: Union[str, Path], container_file_path: Optional[str] = None) -> str:
        """
        Expose a single file to the container.

        Args:
            host_file_path: File path on the host
            container_file_path: File path inside container

        Returns:
            The container path where the file is accessible
        """
        return self.expose_path(host_file_path, container_file_path, read_only=True)

    def expose_directory(
        self, host_dir_path: Union[str, Path], container_dir_path: Optional[str] = None, read_only: bool = True
    ) -> str:
        """
        Expose a directory to the container.

        Args:
            host_dir_path: Directory path on the host
            container_dir_path: Directory path inside container
            read_only: Whether the directory should be read-only

        Returns:
            The container path where the directory is accessible
        """
        return self.expose_path(host_dir_path, container_dir_path, read_only)

    def create_temp_file(self, content: str, suffix: str = ".py") -> str:
        """
        Create a temporary file with content and expose it to the container.

        Args:
            content: File content
            suffix: File suffix

        Returns:
            Container path to the temporary file
        """
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)

        try:
            temp_file.write(content)
            temp_file.flush()
            temp_file.close()

            # Track for cleanup
            self.temp_files.append(temp_file.name)

            # Expose to container
            container_path = self.expose_file(temp_file.name)
            return container_path

        except Exception as e:
            # Clean up on error
            try:
                os.unlink(temp_file.name)
            except:
                pass
            raise e

    def run(
        self, code: str, timeout: int = 30, stdin_input: Optional[str] = None, shutdown_on_failure: bool = True
    ) -> SandboxExecutionResult:
        """
        Execute Python code in the sandbox.

        Args:
            code: Python code to execute
            timeout: Timeout in seconds
            stdin_input: Optional stdin input for the code
            shutdown_on_failure: Whether to shutdown sandbox on execution failure

        Returns:
            SandboxExecutionResult with stdout, stderr, and metadata
        """
        start_time = time.time()

        try:
            if self.is_running:
                # Use persistent container
                result = self._run_in_persistent_container(code, timeout, stdin_input)
            else:
                # Use ephemeral container
                result = self._run_in_ephemeral_container(code, timeout, stdin_input)

            # Check if we should shutdown on failure
            if shutdown_on_failure and not result.success:
                self._handle_execution_failure(result)

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            result = SandboxExecutionResult(
                error=f"Execution failed: {e!s}", exit_code=1, execution_time=execution_time
            )

            # Shutdown on critical failure
            if shutdown_on_failure:
                self._handle_execution_failure(result)

            return result

    def _handle_execution_failure(self, result: SandboxExecutionResult):
        """
        Handle execution failure by logging and optionally shutting down the sandbox.

        Args:
            result: The failed execution result
        """
        failure_reasons = []

        # Determine the type of failure
        if result.exit_code == 124:  # Timeout
            failure_reasons.append("timeout")
        elif result.error:
            failure_reasons.append("error")
        elif result.stderr.strip():
            failure_reasons.append("stderr_output")
        elif result.exit_code != 0:
            failure_reasons.append("non_zero_exit")

        failure_type = ", ".join(failure_reasons) if failure_reasons else "unknown"

        print(f"⚠️  Sandbox execution failed ({failure_type}). Shutting down container for safety.")

        # Log failure details (you can enhance this for better logging)
        if result.error:
            print(f"   Error: {result.error}")
        if result.stderr.strip():
            print(f"   Stderr: {result.stderr.strip()}")
        if result.exit_code != 0:
            print(f"   Exit code: {result.exit_code}")

        # Shutdown the container if it's running
        if self.is_running:
            try:
                self.stop_container()
                print("✅ Container shutdown completed.")
            except Exception as e:
                print(f"❌ Failed to shutdown container: {e}")

    def _run_in_persistent_container(
        self, code: str, timeout: int, stdin_input: Optional[str]
    ) -> SandboxExecutionResult:
        """Run code in a persistent container with state persistence using stdin piping."""
        start_time = time.time()

        try:
            # Create the session execution script that reads code from stdin
            session_script = """
import sys
import json
import pickle
import os
import traceback
import time
import types
import ast
from io import StringIO

# State file for persistence
STATE_FILE = "/app/workspace/session_state.pkl"

# Load existing state if available
user_globals = {"__builtins__": __builtins__}

if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "rb") as f:
            saved_data = pickle.load(f)
            
            # Restore regular variables
            for k, v in saved_data.get("variables", {}).items():
                if not k.startswith("__"):
                    user_globals[k] = v
            
            # Restore imported modules by re-importing them
            for import_statement in saved_data.get("imports", []):
                try:
                    exec(import_statement, user_globals)
                except:
                    pass
            
            # Restore function definitions by re-executing them
            for func_code in saved_data.get("functions", []):
                try:
                    exec(func_code, user_globals)
                except:
                    pass
    except Exception as e:
        pass  # Start fresh if state loading fails

# Capture output
old_stdout = sys.stdout
old_stderr = sys.stderr
stdout_capture = StringIO()
stderr_capture = StringIO()

result = {
    "stdout": "",
    "stderr": "",
    "exit_code": 0,
    "execution_time": 0.0,
    "error": None
}

exec_start = time.time()

try:
    sys.stdout = stdout_capture
    sys.stderr = stderr_capture
    
    # Read the user code from stdin
    user_code = sys.stdin.read()
    
    exec(user_code, user_globals)
    
except Exception as e:
    result["exit_code"] = 1
    result["error"] = str(e)
    traceback.print_exc()

finally:
    sys.stdout = old_stdout
    sys.stderr = old_stderr
    
    result["execution_time"] = time.time() - exec_start
    result["stdout"] = stdout_capture.getvalue()
    result["stderr"] = stderr_capture.getvalue()
    
    # Save state for next execution
    try:
        # Load existing state
        existing_data = {"variables": {}, "imports": [], "functions": []}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "rb") as f:
                    existing_data = pickle.load(f)
            except:
                pass
        
        # Parse the user code to extract function definitions and imports
        try:
            tree = ast.parse(user_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Extract function definition from source
                    lines = user_code.split(chr(10))  # Use chr(10) for newline
                    start_line = node.lineno - 1
                    # Find the end of the function by looking for the next top-level statement
                    end_line = len(lines)
                    for i in range(start_line + 1, len(lines)):
                        line = lines[i]
                        if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                            end_line = i
                            break
                    
                    func_code = chr(10).join(lines[start_line:end_line])
                    if func_code not in existing_data["functions"]:
                        existing_data["functions"].append(func_code)
                elif isinstance(node, ast.Import):
                    # Save full import statements
                    import_line = f"import {', '.join(alias.name if alias.asname is None else f'{alias.name} as {alias.asname}' for alias in node.names)}"
                    if import_line not in existing_data["imports"]:
                        existing_data["imports"].append(import_line)
                elif isinstance(node, ast.ImportFrom):
                    # Save full from...import statements
                    module_part = f"from {node.module} " if node.module else "from . "
                    names_part = ', '.join(alias.name if alias.asname is None else f'{alias.name} as {alias.asname}' for alias in node.names)
                    import_line = f"{module_part}import {names_part}"
                    if import_line not in existing_data["imports"]:
                        existing_data["imports"].append(import_line)
        except:
            pass
        
        # Save variables (exclude modules since they're handled by import statements)
        for k, v in user_globals.items():
            if not k.startswith("__") and k != "__builtins__":
                try:
                    # Try to pickle the value (skip modules since they're handled separately)
                    if not isinstance(v, types.ModuleType):
                        pickle.dumps(v)
                        existing_data["variables"][k] = v
                except:
                    pass  # Skip non-picklable items
        
        with open(STATE_FILE, "wb") as f:
            pickle.dump(existing_data, f)
    except:
        pass  # Continue even if state saving fails

# Output result as JSON
print(json.dumps(result))
"""

            # Create a command that writes the session script and executes it with user code
            combined_input = f"{session_script}\n---ENDSCRIPT---\n{code}"

            # Execute using a shell command that splits the input
            shell_cmd = """
# Read input until separator
session_script=""
while IFS= read -r line; do
    if [ "$line" = "---ENDSCRIPT---" ]; then
        break
    fi
    session_script="$session_script$line
"
done

# Write session script to file
echo "$session_script" > /app/workspace/session_exec.py

# Read remaining input (user code) and pipe to the session script
python /app/workspace/session_exec.py
"""

            exec_cmd = ["docker", "exec", "-i", self.container_name, "sh", "-c", shell_cmd]

            # Run with timeout
            process = subprocess.run(exec_cmd, input=combined_input, capture_output=True, text=True, timeout=timeout)

            execution_time = time.time() - start_time

            # Parse JSON result from the last line
            try:
                lines = process.stdout.strip().split("\n")
                json_line = lines[-1] if lines else "{}"
                result_data = json.loads(json_line)

                return SandboxExecutionResult(
                    stdout=result_data.get("stdout", ""),
                    stderr=result_data.get("stderr", ""),
                    exit_code=result_data.get("exit_code", process.returncode),
                    execution_time=result_data.get("execution_time", execution_time),
                    error=result_data.get("error"),
                )
            except (json.JSONDecodeError, IndexError):
                # Fallback to raw output if JSON parsing fails
                return SandboxExecutionResult(
                    stdout=process.stdout,
                    stderr=process.stderr,
                    exit_code=process.returncode,
                    execution_time=execution_time,
                )

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            # Try to stop any hanging processes in the container
            try:
                subprocess.run(
                    ["docker", "exec", self.container_name, "pkill", "-f", "python"], capture_output=True, timeout=5
                )
            except:
                pass  # Best effort cleanup

            return SandboxExecutionResult(
                error=f"Code execution timed out after {timeout} seconds", exit_code=124, execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return SandboxExecutionResult(error=f"Execution error: {e!s}", exit_code=1, execution_time=execution_time)

    def _run_in_ephemeral_container(
        self, code: str, timeout: int, stdin_input: Optional[str]
    ) -> SandboxExecutionResult:
        """Run code in an ephemeral container (original approach)."""
        start_time = time.time()

        try:
            # Build docker run command
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--init",
                "--network=none",
                "--memory=512m",
                "--cpus=1.0",
                "--security-opt=no-new-privileges:true",
                "--read-only",
                "--tmpfs=/app/workspace:size=100m,uid=999,gid=999",
                "--tmpfs=/tmp:noexec,nosuid,nodev,size=50m",
            ]

            # Add volume mounts for exposed paths
            for host_path, path_info in self.exposed_paths.items():
                container_path = path_info["container_path"]
                mount_option = path_info["mount_option"]
                docker_cmd.extend(["-v", f"{host_path}:{container_path}{mount_option}"])

            # Add environment variable with code
            docker_cmd.extend(["-e", f"PYTHON_CODE={code}"])
            docker_cmd.append(self.image_name)

            # Execute with timeout
            process = subprocess.run(
                docker_cmd,
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=timeout + 5,  # Buffer for container startup
            )

            execution_time = time.time() - start_time

            # Parse JSON output from container
            try:
                result_data = json.loads(process.stdout)
                return SandboxExecutionResult(
                    stdout=result_data.get("stdout", ""),
                    stderr=result_data.get("stderr", ""),
                    exit_code=result_data.get("exit_code", process.returncode),
                    execution_time=result_data.get("execution_time", execution_time),
                    error=result_data.get("error"),
                )
            except json.JSONDecodeError:
                # Fallback to raw output
                return SandboxExecutionResult(
                    stdout=process.stdout,
                    stderr=process.stderr,
                    exit_code=process.returncode,
                    execution_time=execution_time,
                )

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return SandboxExecutionResult(
                error=f"Container execution timed out after {timeout} seconds",
                exit_code=124,
                execution_time=execution_time,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return SandboxExecutionResult(error=f"Execution error: {e!s}", exit_code=1, execution_time=execution_time)

    def cleanup(self):
        """Clean up resources (containers, temporary files, etc.)."""
        # Stop container if running
        if self.is_running:
            self.stop_container()

        # Clean up temporary files
        for temp_file in self.temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass
        self.temp_files.clear()

        # Clear exposed paths
        self.exposed_paths.clear()

    def __enter__(self):
        """Context manager entry."""
        if not self.is_running:
            self.start_container(**self._context_manager_kwargs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.cleanup()

    def configure_context_manager(
        self,
        expose_files: Optional[Dict[str, str]] = None,
        expose_directories: Optional[Dict[str, str]] = None,
        expose_directories_rw: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> "PythonSandboxManager":
        """
        Configure parameters for when using the context manager (with statement).

        Args:
            expose_files: Dict of {host_file_path: container_file_path} to expose (read-only)
            expose_directories: Dict of {host_dir_path: container_dir_path} to expose (read-only)
            expose_directories_rw: Dict of {host_dir_path: container_dir_path} to expose (read-write)
            **kwargs: Arguments to pass to start_container() when entering context

        Returns:
            Self for method chaining

        Examples:
            # With custom resources
            with PythonSandboxManager().configure_context_manager(memory_limit="4g", cpu_limit="8.0"):
                result = sandbox.run("print('Hello with custom resources!')")

            # With file exposure
            with PythonSandboxManager().configure_context_manager(
                expose_files={"/path/to/data.csv": "/app/shared/data.csv"}
            ) as sandbox:
                result = sandbox.run("import pandas as pd; data = pd.read_csv('/app/shared/data.csv')")

            # With directory exposure (read-only)
            with PythonSandboxManager().configure_context_manager(
                expose_directories={"/path/to/data_dir": "/app/shared/data"}
            ) as sandbox:
                result = sandbox.run("import os; print(os.listdir('/app/shared/data'))")

            # With writable directory exposure
            with PythonSandboxManager().configure_context_manager(
                expose_directories_rw={"./output": "/app/output"}
            ) as sandbox:
                result = sandbox.run("with open('/app/output/result.txt', 'w') as f: f.write('Hello!')")

            # Combined
            with PythonSandboxManager().configure_context_manager(
                memory_limit="2g",
                expose_files={"/path/to/data.csv": "/app/shared/data.csv"},
                expose_directories={"/path/to/models": "/app/shared/models"},
                expose_directories_rw={"./output": "/app/output"}
            ) as sandbox:
                result = sandbox.run("# Your code here")
        """
        self._context_manager_kwargs = kwargs

        # Store file/directory exposures to be applied before starting container
        if expose_files:
            for host_path, container_path in expose_files.items():
                self.expose_file(host_path, container_path)

        if expose_directories:
            for host_path, container_path in expose_directories.items():
                self.expose_directory(host_path, container_path, read_only=True)

        if expose_directories_rw:
            for host_path, container_path in expose_directories_rw.items():
                self.expose_directory(host_path, container_path, read_only=False)

        return self

    def restart_container(self, **kwargs) -> str:
        """
        Restart the container (stop if running, then start with new parameters).

        Args:
            **kwargs: Arguments to pass to start_container()

        Returns:
            Container ID of the new container
        """
        if self.is_running:
            self.stop_container()
        return self.start_container(**kwargs)

    def get_container_info(self) -> Dict[str, Any]:
        """Get information about the current container."""
        return {
            "container_id": self.container_id,
            "container_name": self.container_name,
            "is_running": self.is_running,
            "image_name": self.image_name,
            "exposed_paths": self.exposed_paths.copy(),
            "temp_files_count": len(self.temp_files),
        }
