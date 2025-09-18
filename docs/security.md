# BioCage Security Guide

BioCage is designed with security as a primary concern, providing multiple layers of protection for executing untrusted Python code. This guide explains the security model, best practices, and potential limitations.

## Table of Contents

- [Security Architecture](#security-architecture)
- [Isolation Mechanisms](#isolation-mechanisms)
- [Resource Controls](#resource-controls)
- [Network Security](#network-security)
- [File System Security](#file-system-security)
- [Best Practices](#best-practices)
- [Threat Model](#threat-model)
- [Limitations](#limitations)
- [Security Configuration](#security-configuration)

## Security Architecture

BioCage employs a layered security approach based on Docker container isolation:

```
┌─────────────────────────────────────────┐
│              Host System                │
├─────────────────────────────────────────┤
│           BioCage Orchestrator          │
├─────────────────────────────────────────┤
│            Docker Engine                │
├─────────────────────────────────────────┤
│         Container Runtime               │
├─────────────────────────────────────────┤
│    Isolated Python Environment         │
│  ┌─────────────────────────────────┐    │
│  │        User Code                │    │
│  │     (Untrusted Python)          │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### Core Security Principles

1. **Defense in Depth**: Multiple security layers prevent single points of failure
2. **Principle of Least Privilege**: Minimal permissions and capabilities
3. **Isolation by Default**: Strong boundaries between environments
4. **Resource Limitation**: Prevent resource exhaustion attacks
5. **Fail-Safe Defaults**: Secure configurations out of the box

## Isolation Mechanisms

### Container Isolation

BioCage uses Docker containers to provide strong isolation:

```python
# Each execution runs in an isolated container
with BioCageOrchestrator(execution_mode="ephemeral") as sandbox:
    # This code cannot access the host system
    result = sandbox.run("""
    import os
    print("Container process list:")
    os.system("ps aux")  # Only shows container processes
    """)
```

**Isolation features:**
- **Process isolation**: Separate process namespace
- **Filesystem isolation**: Read-only root filesystem
- **Network isolation**: Disabled by default
- **User isolation**: Non-root execution
- **IPC isolation**: Separate inter-process communication

### Execution Mode Security

#### Ephemeral Mode (Maximum Security)
```python
# Fresh container for each execution
with BioCageOrchestrator(execution_mode="ephemeral") as sandbox:
    # First execution
    sandbox.run("secret = 'password123'")

    # Second execution - no access to previous data
    result = sandbox.run("print(secret)")  # NameError: secret not defined
```

**Security benefits:**
- No state persistence between executions
- Complete memory isolation
- Fresh Python interpreter each time
- Maximum protection against data leakage

#### Persistent Mode (Managed Security)
```python
# Same container across executions
with BioCageOrchestrator(execution_mode="persistent") as sandbox:
    sandbox.run("data = 'shared_state'")
    result = sandbox.run("print(data)")  # Accesses previous state
```

**Security considerations:**
- State persists within the session
- Memory may contain previous execution data
- Use for trusted code or controlled environments
- Automatic cleanup on session end

## Resource Controls

### Memory Limits

Prevent memory exhaustion attacks:

```python
# Limit container memory to 512MB
with BioCageOrchestrator(memory_limit="512m") as sandbox:
    result = sandbox.run("""
    try:
        # Attempt to allocate large memory
        large_list = [0] * (10**9)  # ~8GB attempt
    except MemoryError:
        print("Memory limit enforced")
    """)
```

**Memory protections:**
- Hard memory limits enforced by Docker
- Out-of-memory killer protection
- Prevents memory exhaustion of host
- Configurable per execution

### CPU Limits

Control CPU usage to prevent resource monopolization:

```python
# Limit to 1 CPU core
with BioCageOrchestrator(cpu_limit="1.0") as sandbox:
    result = sandbox.run("""
    import multiprocessing
    import time

    def cpu_intensive():
        while True:  # This will be limited
            pass

    # Even with multiple processes, limited to 1 CPU
    processes = []
    for _ in range(4):
        p = multiprocessing.Process(target=cpu_intensive)
        p.start()
        processes.append(p)

    time.sleep(5)  # Limited impact on host
    for p in processes:
        p.terminate()
    """)
```

### Execution Timeouts

Prevent infinite loops and hanging processes:

```python
with BioCageOrchestrator() as sandbox:
    # Automatically timeout after 30 seconds
    result = sandbox.run("""
    while True:  # Infinite loop
        pass
    """, timeout=30)

    if result.exit_code == 124:
        print("Execution timed out as expected")
```

## Network Security

### Network Isolation (Default)

By default, containers have no network access:

```python
with BioCageOrchestrator(network_access=False) as sandbox:
    result = sandbox.run("""
    import urllib.request
    try:
        urllib.request.urlopen('https://example.com')
    except Exception as e:
        print(f"Network blocked: {type(e).__name__}")
    """)
    # Output: Network blocked: URLError
```

### Controlled Network Access

When network access is needed, it can be enabled selectively:

```python
# Enable network for specific operations
with BioCageOrchestrator(network_access=True) as sandbox:
    result = sandbox.run("""
    import urllib.request
    import json

    # Limited to outbound connections only
    response = urllib.request.urlopen('https://api.github.com/zen')
    data = response.read().decode()
    print(f"API call successful: {len(data)} characters")
    """)
```

**Network security features:**
- Outbound connections only
- No inbound connection capabilities
- DNS resolution controlled
- Host network isolation

## File System Security

### Read-Only Root Filesystem

The container's root filesystem is read-only by default:

```python
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("""
    try:
        with open('/etc/hosts', 'a') as f:
            f.write("malicious entry")
    except PermissionError:
        print("Root filesystem is read-only")
    """)
```

### Controlled File Exposure

Host files are exposed with explicit permissions:

```python
with BioCageOrchestrator() as sandbox:
    # Expose file as read-only (default)
    sandbox.expose_file("/host/data.txt", "/app/data.txt")

    result = sandbox.run("""
    # Reading is allowed
    with open('/app/data.txt', 'r') as f:
        content = f.read()
        print(f"Read {len(content)} characters")

    try:
        # Writing is blocked
        with open('/app/data.txt', 'w') as f:
            f.write("malicious content")
    except PermissionError:
        print("Write access denied")
    """)
```

### Temporary File Security

Temporary files are isolated within containers:

```python
with BioCageOrchestrator() as sandbox:
    result = sandbox.run("""
    import tempfile
    import os

    # Create temporary file (isolated to container)
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"temporary data")
        temp_path = f.name

    print(f"Temporary file: {temp_path}")

    # File exists only in container
    print(f"File exists: {os.path.exists(temp_path)}")
    """)
    # File is automatically cleaned up with container
```

## Best Practices

### 1. Use Appropriate Execution Mode

```python
# For untrusted code - use ephemeral mode
def execute_untrusted_code(user_code):
    with BioCageOrchestrator(execution_mode="ephemeral") as sandbox:
        return sandbox.run(user_code)

# For trusted workflows - use persistent mode
def execute_trusted_workflow(workflow_steps):
    with BioCageOrchestrator(execution_mode="persistent") as sandbox:
        results = []
        for step in workflow_steps:
            result = sandbox.run(step)
            results.append(result)
        return results
```

### 2. Implement Proper Resource Limits

```python
# Production configuration with security limits
def create_secure_sandbox():
    return BioCageOrchestrator(
        execution_mode="ephemeral",     # Maximum isolation
        memory_limit="256m",            # Reasonable memory limit
        cpu_limit="1.0",               # Single CPU core
        network_access=False           # No network access
    )
```

### 3. Validate Input Code

```python
import ast

def validate_code_safety(code):
    """Basic validation of Python code."""
    try:
        # Parse code to check syntax
        tree = ast.parse(code)

        # Check for potentially dangerous operations
        dangerous_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ['subprocess', 'os', 'sys']:
                        dangerous_nodes.append(f"Import: {alias.name}")
            elif isinstance(node, ast.Call):
                if hasattr(node.func, 'id') and node.func.id in ['exec', 'eval']:
                    dangerous_nodes.append(f"Function: {node.func.id}")

        return len(dangerous_nodes) == 0, dangerous_nodes
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"]

# Use validation before execution
def safe_execute(code):
    is_safe, issues = validate_code_safety(code)

    if not is_safe:
        return f"Code validation failed: {issues}"

    with create_secure_sandbox() as sandbox:
        return sandbox.run(code)
```

### 4. Implement Logging and Monitoring

```python
import logging

# Configure security logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - SECURITY - %(message)s',
    handlers=[
        logging.FileHandler('biocage_security.log'),
        logging.StreamHandler()
    ]
)

def secure_execute_with_logging(code, user_id=None):
    """Execute code with comprehensive security logging."""

    logging.info(f"Code execution request - User: {user_id}, Length: {len(code)}")

    with BioCageOrchestrator(execution_mode="ephemeral") as sandbox:
        result = sandbox.run(code)

        # Log execution results
        logging.info(f"Execution result - Success: {result.success}, "
                    f"Time: {result.execution_time:.3f}s, "
                    f"Exit code: {result.exit_code}")

        if not result.success:
            logging.warning(f"Execution failed - Error: {result.stderr[:200]}")

        return result
```

### 5. Handle Timeouts Appropriately

```python
def execute_with_timeout_handling(code, max_timeout=60):
    """Execute code with progressive timeout handling."""

    timeouts = [10, 30, 60]  # Progressive timeouts

    for timeout in timeouts:
        if timeout > max_timeout:
            break

        with BioCageOrchestrator() as sandbox:
            result = sandbox.run(code, timeout=timeout)

            if result.success:
                return result
            elif result.exit_code == 124:  # Timeout
                logging.warning(f"Execution timed out after {timeout}s")
                continue
            else:
                # Other error, don't retry
                return result

    return SandboxExecutionResult(
        stdout="",
        stderr="Maximum execution time exceeded",
        exit_code=124,
        execution_time=max_timeout
    )
```

## Threat Model

### Threats BioCage Protects Against

✅ **Code injection attacks**
- Malicious Python code execution
- Arbitrary system command execution
- File system manipulation

✅ **Resource exhaustion attacks**
- Memory bombs and allocation attacks
- CPU consumption attacks
- Infinite loops and hangs

✅ **Data exfiltration**
- Access to host filesystem
- Network-based data theft
- Inter-container communication

✅ **Privilege escalation**
- Container escape attempts
- Root access exploitation
- System service manipulation

### Residual Risks

⚠️ **Container escape vulnerabilities**
- Docker/kernel vulnerabilities
- Requires keeping Docker updated

⚠️ **Side-channel attacks**
- Timing attacks
- Resource contention analysis

⚠️ **Host resource exhaustion**
- Multiple container creation
- Disk space consumption

## Limitations

### 1. Container Runtime Dependencies

BioCage security depends on Docker's isolation:

```python
# BioCage cannot protect against Docker vulnerabilities
# Keep Docker updated and monitored for security issues
```

### 2. Host System Security

The host system must be properly secured:

```python
# Host security checklist:
# - Updated operating system
# - Proper user permissions
# - Docker daemon security
# - Network firewall configuration
```

### 3. Resource Limits

Absolute resource protection requires system-level controls:

```python
# Additional system-level protections recommended:
# - Systemd resource limits
# - cgroups configuration
# - Kernel security modules (SELinux/AppArmor)
```

## Security Configuration

### Production Security Configuration

```python
class SecureBioCageConfig:
    """Production-ready secure configuration."""

    @staticmethod
    def get_secure_config():
        return {
            'execution_mode': 'ephemeral',    # Maximum isolation
            'memory_limit': '256m',           # Conservative memory limit
            'cpu_limit': '0.5',              # Half CPU core
            'network_access': False,          # No network access
        }

    @staticmethod
    def get_monitored_config():
        return {
            'execution_mode': 'persistent',   # For monitoring workflows
            'memory_limit': '512m',           # Adequate for analysis
            'cpu_limit': '1.0',              # Single CPU core
            'network_access': False,          # Still no network
        }

# Use secure configurations
with BioCageOrchestrator(**SecureBioCageConfig.get_secure_config()) as sandbox:
    result = sandbox.run(untrusted_code)
```

### Security Headers and Metadata

```python
def execute_with_security_context(code, security_level="high"):
    """Execute code with security context tracking."""

    security_configs = {
        "high": {
            "execution_mode": "ephemeral",
            "memory_limit": "128m",
            "cpu_limit": "0.25",
            "network_access": False
        },
        "medium": {
            "execution_mode": "ephemeral",
            "memory_limit": "512m",
            "cpu_limit": "1.0",
            "network_access": False
        },
        "low": {
            "execution_mode": "persistent",
            "memory_limit": "1g",
            "cpu_limit": "2.0",
            "network_access": True
        }
    }

    config = security_configs.get(security_level, security_configs["high"])

    with BioCageOrchestrator(**config) as sandbox:
        # Add security metadata to execution
        security_code = f"""
# Security context: {security_level}
# Memory limit: {config['memory_limit']}
# CPU limit: {config['cpu_limit']}
# Network: {config['network_access']}

{code}
"""
        return sandbox.run(security_code)
```

This security guide provides comprehensive coverage of BioCage's security model and best practices. Always stay updated with the latest Docker security advisories and apply security patches promptly to maintain the highest level of protection.