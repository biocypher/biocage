# BioCage Troubleshooting Guide

This guide helps you diagnose and resolve common issues when using BioCage. It covers installation problems, runtime errors, performance issues, and debugging techniques.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Installation Issues](#installation-issues)
- [Container Problems](#container-problems)
- [Execution Failures](#execution-failures)
- [Performance Issues](#performance-issues)
- [File System Problems](#file-system-problems)
- [Network Issues](#network-issues)
- [Debugging Techniques](#debugging-techniques)
- [Common Error Messages](#common-error-messages)

## Quick Diagnostics

Run this diagnostic script to check your BioCage setup:

```python
#!/usr/bin/env python3
"""BioCage diagnostic script."""

import subprocess
import sys
import os
from pathlib import Path

def run_diagnostics():
    print("BioCage Diagnostic Report")
    print("=" * 30)

    # Check Python version
    print(f"Python version: {sys.version}")

    # Check Docker installation
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        print(f"Docker version: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ Docker not found - install Docker first")
        return

    # Check Docker daemon
    try:
        result = subprocess.run(['docker', 'info'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Docker daemon is running")
        else:
            print("❌ Docker daemon not running")
            return
    except Exception as e:
        print(f"❌ Docker daemon check failed: {e}")
        return

    # Check BioCage installation
    try:
        from biocage import BioCageOrchestrator
        print("✅ BioCage import successful")
    except ImportError as e:
        print(f"❌ BioCage import failed: {e}")
        return

    # Check basic functionality
    try:
        with BioCageOrchestrator() as sandbox:
            result = sandbox.run("print('Diagnostic test')")
            if result.success:
                print("✅ Basic execution test passed")
            else:
                print(f"❌ Basic execution failed: {result.stderr}")
    except Exception as e:
        print(f"❌ Basic execution test failed: {e}")
        return

    print("\n✅ All diagnostics passed!")

if __name__ == "__main__":
    run_diagnostics()
```

Save this as `diagnose.py` and run:
```bash
python diagnose.py
```

## Installation Issues

### Docker Not Found

**Error**: `FileNotFoundError: [Errno 2] No such file or directory: 'docker'`

**Solution**:
```bash
# macOS
brew install docker
# or download Docker Desktop from docker.com

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install docker.io

# CentOS/RHEL
sudo yum install docker
```

### Docker Daemon Not Running

**Error**: `docker: Cannot connect to the Docker daemon`

**Solution**:
```bash
# Start Docker daemon (Linux)
sudo systemctl start docker
sudo systemctl enable docker

# macOS/Windows
# Start Docker Desktop application

# Check Docker status
docker info
```

### Permission Denied

**Error**: `docker: permission denied while trying to connect`

**Solution**:
```bash
# Add user to docker group (Linux)
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker

# Test without sudo
docker ps
```

### BioCage Import Error

**Error**: `ModuleNotFoundError: No module named 'biocage'`

**Solution**:
```bash
# Install in development mode
pip install -e .

# Or install from PyPI (when available)
pip install biocage

# Check installation
python -c "import biocage; print(biocage.__version__)"
```

## Container Problems

### Image Not Found

**Error**: `docker: Error response from daemon: pull access denied`

**Solution**:
```python
# Check available images
import subprocess
result = subprocess.run(['docker', 'images'], capture_output=True, text=True)
print(result.stdout)

# Build BioCage image if needed
subprocess.run(['docker', 'build', '-t', 'biocage:latest', '.'])
```

### Container Creation Failed

**Error**: `ContainerLifecycleError: Failed to create container`

**Diagnosis**:
```python
from biocage import BioCageOrchestrator

# Check with minimal configuration
try:
    with BioCageOrchestrator(memory_limit="128m", cpu_limit="0.1") as sandbox:
        result = sandbox.run("print('test')")
        print("Container creation successful")
except Exception as e:
    print(f"Container creation failed: {e}")
    print("Try reducing resource limits")
```

### Container Stuck in Starting State

**Symptoms**: Long delays before execution begins

**Solution**:
```bash
# Check running containers
docker ps

# Check container logs
docker logs <container_id>

# Clean up stuck containers
docker container prune

# Restart Docker daemon if needed
sudo systemctl restart docker  # Linux
# or restart Docker Desktop
```

### Out of Disk Space

**Error**: `no space left on device`

**Solution**:
```bash
# Check disk usage
df -h

# Clean up Docker resources
docker system prune -a

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune
```

## Execution Failures

### Code Execution Timeout

**Error**: `exit_code: 124` (timeout)

**Diagnosis**:
```python
from biocage import BioCageOrchestrator

# Test with longer timeout
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("""
import time
print("Starting operation...")
time.sleep(5)
print("Operation complete")
""", timeout=10)  # Increase timeout

    if result.exit_code == 124:
        print("Still timing out - check for infinite loops")
    else:
        print(f"Success: {result.stdout}")
```

### Python Syntax Errors

**Error**: `SyntaxError` in stderr

**Solution**:
```python
import ast

def validate_syntax(code):
    """Validate Python syntax before execution."""
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)

# Example usage
code = "print('hello world')"  # Missing closing quote
is_valid, error = validate_syntax(code)

if is_valid:
    with BioCageOrchestrator() as sandbox:
        result = sandbox.run(code)
else:
    print(f"Syntax error: {error}")
```

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'some_package'`

**Solution**:
```python
# Check available packages in container
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("""
import sys
import pkg_resources

print("Python version:", sys.version)
print("Installed packages:")
for pkg in sorted(pkg_resources.working_set, key=lambda x: x.project_name.lower()):
    print(f"  {pkg.project_name} {pkg.version}")
""")
    print(result.stdout)
```

**Custom Docker image with additional packages**:
```dockerfile
FROM python:3.11-slim

# Install additional packages
RUN pip install pandas numpy matplotlib scikit-learn

# Set working directory
WORKDIR /app

# Default command
CMD ["python"]
```

### Memory Allocation Errors

**Error**: `MemoryError` or container killed

**Solution**:
```python
# Increase memory limit
with BioCageOrchestrator(memory_limit="2g") as sandbox:
    result = sandbox.run("""
import numpy as np
import psutil

# Check available memory
memory = psutil.virtual_memory()
print(f"Available memory: {memory.available / 1024**3:.1f} GB")

# Create array with reasonable size
arr = np.zeros((1000, 1000))  # ~8MB
print(f"Array created: {arr.shape}")
""")
```

## Performance Issues

### Slow Container Startup

**Symptoms**: Long delays before first execution

**Solutions**:
```python
# Use persistent mode for multiple executions
with BioCageOrchestrator(execution_mode="persistent") as sandbox:
    # Startup cost paid once
    for i in range(10):
        result = sandbox.run(f"print('Execution {i}')")

# Pre-warm containers
def create_warmed_sandbox():
    sandbox = BioCageOrchestrator(execution_mode="persistent")
    sandbox.start_container()
    # Pre-load common imports
    sandbox.run("import pandas as pd, numpy as np")
    return sandbox
```

### Slow Code Execution

**Diagnosis**:
```python
import time

def benchmark_execution():
    test_codes = [
        "print('simple')",
        "sum(range(10000))",
        "import pandas as pd; pd.DataFrame({'a': range(100)})",
    ]

    for code in test_codes:
        with BioCageOrchestrator() as sandbox:
            start = time.time()
            result = sandbox.run(code)
            end = time.time()

            print(f"Code: {code[:30]}...")
            print(f"Time: {end - start:.3f}s")
            print(f"Success: {result.success}")
            print("---")

benchmark_execution()
```

### High Resource Usage

**Monitoring**:
```python
def monitor_resource_usage():
    with BioCageOrchestrator() as sandbox:
        result = sandbox.run("""
import psutil
import os

# CPU usage
cpu_percent = psutil.cpu_percent(interval=1)
print(f"CPU usage: {cpu_percent}%")

# Memory usage
memory = psutil.virtual_memory()
process = psutil.Process()
process_memory = process.memory_info().rss / 1024**2

print(f"System memory: {memory.percent}% used")
print(f"Process memory: {process_memory:.1f} MB")

# Disk usage
disk = psutil.disk_usage('/')
print(f"Disk usage: {disk.percent}%")
""")
        print(result.stdout)

monitor_resource_usage()
```

## File System Problems

### File Not Found

**Error**: `FileNotFoundError: [Errno 2] No such file or directory`

**Solution**:
```python
import os
from pathlib import Path

# Check if file exists before exposing
host_file = "/path/to/data.csv"

if Path(host_file).exists():
    with BioCageOrchestrator() as sandbox:
        container_path = sandbox.expose_file(host_file, "/app/data.csv")
        result = sandbox.run(f"""
import os
print(f"File exists: {os.path.exists('{container_path}')}")
print(f"File size: {os.path.getsize('{container_path}')} bytes")
""")
else:
    print(f"Host file not found: {host_file}")
```

### Permission Denied

**Error**: `PermissionError: [Errno 13] Permission denied`

**Solutions**:
```python
# Check file permissions on host
import stat
import os

def check_file_permissions(file_path):
    try:
        stat_info = os.stat(file_path)
        mode = stat_info.st_mode
        print(f"File: {file_path}")
        print(f"Owner can read: {bool(mode & stat.S_IRUSR)}")
        print(f"Owner can write: {bool(mode & stat.S_IWUSR)}")
        print(f"Others can read: {bool(mode & stat.S_IROTH)}")
    except Exception as e:
        print(f"Cannot check permissions: {e}")

# Fix permissions if needed
# chmod 644 /path/to/file  # Make readable
```

### Mount Point Issues

**Error**: Mount-related errors when exposing files

**Diagnosis**:
```python
def diagnose_mount_issues():
    test_file = "/tmp/biocage_test.txt"

    # Create test file
    with open(test_file, 'w') as f:
        f.write("test content")

    try:
        with BioCageOrchestrator() as sandbox:
            container_path = sandbox.expose_file(test_file, "/app/test.txt")

            result = sandbox.run(f"""
import os
print(f"Mount successful: {os.path.exists('{container_path}')}")
if os.path.exists('{container_path}'):
    with open('{container_path}', 'r') as f:
        content = f.read()
    print(f"Content: {content}")
""")
            print(result.stdout)

    except Exception as e:
        print(f"Mount failed: {e}")
    finally:
        # Cleanup
        os.unlink(test_file)

diagnose_mount_issues()
```

## Network Issues

### DNS Resolution Failed

**Error**: Network-related errors even with `network_access=True`

**Diagnosis**:
```python
with BioCageOrchestrator(network_access=True) as sandbox:
    result = sandbox.run("""
import socket
import urllib.request

# Test DNS resolution
try:
    ip = socket.gethostbyname('google.com')
    print(f"DNS resolution successful: google.com -> {ip}")
except Exception as e:
    print(f"DNS resolution failed: {e}")

# Test HTTP connection
try:
    response = urllib.request.urlopen('http://httpbin.org/get', timeout=5)
    print(f"HTTP connection successful: {response.code}")
except Exception as e:
    print(f"HTTP connection failed: {e}")
""")
    print(result.stdout)
```

### Proxy Configuration

**Issue**: Network access fails due to corporate proxy

**Solution**:
```python
# Set proxy environment variables
import os

proxy_settings = {
    'HTTP_PROXY': 'http://proxy.company.com:8080',
    'HTTPS_PROXY': 'http://proxy.company.com:8080',
    'NO_PROXY': 'localhost,127.0.0.1'
}

# Apply to container environment
with BioCageOrchestrator(network_access=True) as sandbox:
    proxy_code = f"""
import os
import urllib.request

# Set proxy environment variables
{proxy_settings}
for key, value in {proxy_settings}.items():
    os.environ[key] = value

# Test connection
try:
    response = urllib.request.urlopen('https://httpbin.org/get', timeout=10)
    print(f"Proxy connection successful: {response.code}")
except Exception as e:
    print(f"Proxy connection failed: {e}")
"""
    result = sandbox.run(proxy_code)
    print(result.stdout)
```

## Debugging Techniques

### Enable Debug Logging

```python
import logging

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# BioCage will now output detailed logs
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("print('debug test')")
```

### Container Inspection

```python
def inspect_container():
    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        # Get container info
        info = sandbox.get_container_info()

        print("Container Information:")
        for key, value in info.items():
            if key == 'container_id':
                print(f"  {key}: {value[:12]}...")
            else:
                print(f"  {key}: {value}")

        # Inspect container environment
        result = sandbox.run("""
import os
import sys
import platform

print("Environment Information:")
print(f"Python version: {sys.version}")
print(f"Platform: {platform.platform()}")
print(f"Working directory: {os.getcwd()}")
print(f"User: {os.getenv('USER', 'unknown')}")
print(f"Home: {os.getenv('HOME', 'unknown')}")

print("\\nEnvironment variables:")
for key, value in sorted(os.environ.items()):
    if not key.startswith('_'):  # Skip internal variables
        print(f"  {key}: {value}")
""")
        print(result.stdout)

inspect_container()
```

### Step-by-Step Execution

```python
def debug_step_by_step():
    """Debug code execution step by step."""

    code_steps = [
        "import sys",
        "print('Python version:', sys.version)",
        "x = 42",
        "print('x =', x)",
        "y = x * 2",
        "print('y =', y)"
    ]

    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        for i, step in enumerate(code_steps):
            print(f"\nStep {i+1}: {step}")

            result = sandbox.run(step)

            print(f"Success: {result.success}")
            print(f"Time: {result.execution_time:.3f}s")

            if result.stdout:
                print(f"Output: {result.stdout.strip()}")
            if result.stderr:
                print(f"Error: {result.stderr.strip()}")

            if not result.success:
                print("Stopping due to error")
                break

debug_step_by_step()
```

## Common Error Messages

### `ContainerLifecycleError`

**Meaning**: Container management operation failed

**Solutions**:
1. Check Docker daemon status
2. Verify sufficient system resources
3. Clean up unused containers
4. Check Docker image availability

### `DockerCommandError`

**Meaning**: Docker command execution failed

**Solutions**:
1. Verify Docker installation
2. Check user permissions
3. Ensure Docker daemon is running
4. Review Docker logs

### `ExecutionError`

**Meaning**: Code execution failed within container

**Solutions**:
1. Check code syntax
2. Verify required imports are available
3. Increase timeout if needed
4. Check resource limits

### `TimeoutExpired`

**Meaning**: Operation exceeded time limit

**Solutions**:
1. Increase timeout parameter
2. Optimize code for better performance
3. Check for infinite loops
4. Use persistent mode for multiple operations

### `AttributeError: 'BioCageOrchestrator' object has no attribute...`

**Meaning**: Using incorrect method names

**Solutions**:
1. Check method name spelling
2. Verify BioCage version compatibility
3. Use `dir(sandbox)` to see available methods
4. Check documentation for correct API

## Getting Help

If you're still experiencing issues:

1. **Check the logs**: Enable debug logging for detailed information
2. **Run diagnostics**: Use the diagnostic script at the top of this guide
3. **Check documentation**: Review the user guide and API reference
4. **Search issues**: Look for similar problems in the project issues
5. **Create an issue**: Report new bugs with detailed reproduction steps

### Issue Report Template

```
**BioCage Version**: [version]
**Docker Version**: [version]
**Operating System**: [OS and version]
**Python Version**: [version]

**Problem Description**:
[Clear description of the issue]

**Code to Reproduce**:
```python
[Minimal code that reproduces the issue]
```

**Expected Behavior**:
[What you expected to happen]

**Actual Behavior**:
[What actually happened]

**Error Messages**:
[Full error messages and stack traces]

**Additional Context**:
[Any other relevant information]
```

This troubleshooting guide should help you resolve most common BioCage issues. Remember to keep your Docker installation updated and follow security best practices.