"""
Constants and configuration values for BioCage.
"""

# Container configuration
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_CPU_LIMIT = "1.0"
DEFAULT_TIMEOUT = 30
DEFAULT_IMAGE_NAME = "biocage:latest"
DEFAULT_CONTAINER_PREFIX = "biocage"

# Docker security options
DOCKER_SECURITY_OPTS = [
    "--security-opt=no-new-privileges:true",
    "--read-only",
    "--tmpfs=/app/workspace:size=100m,uid=999,gid=999",
    "--tmpfs=/tmp:noexec,nosuid,nodev,size=50m",
]

# Network configuration
NETWORK_DISABLED = "--network=none"

# Container paths
DEFAULT_CONTAINER_WORKSPACE = "/app/workspace"
WORKSPACE_PATH = "/app/workspace"
SHARED_PATH = "/app/shared"
STATE_FILE_PATH = "/app/workspace/session_state.pkl"
SESSION_SCRIPT_PATH = "/app/workspace/session_exec.py"

# Execution constants
SCRIPT_SEPARATOR = "---ENDSCRIPT---"
TIMEOUT_EXIT_CODE = 124

# Error messages
ERROR_CONTAINER_RUNNING = "Container is already running. Call stop_container() first."
ERROR_IMAGE_BUILD_FAILED = "Failed to build Docker image"
ERROR_CONTAINER_START_FAILED = "Failed to start container"
ERROR_PATH_NOT_EXISTS = "Host path does not exist"
ERROR_EXECUTION_FAILED = "Execution failed"
ERROR_TIMEOUT = "Code execution timed out after {} seconds"

# Log messages
LOG_IMAGE_NOT_FOUND = "Image {} not found. Building..."
LOG_BUILDING_IMAGE = "Building BioCage image..."
LOG_IMAGE_BUILT = "Image built successfully!"
LOG_CONTAINER_STARTED = "Container started: {} ({})"
LOG_CONTAINER_STOPPED = "Container stopped and removed: {}"
LOG_CONTAINER_RESTART = "Restarting container to apply new path mapping..."
LOG_EXECUTION_FAILED = "Sandbox execution failed ({}). Shutting down container for safety."
LOG_SHUTDOWN_COMPLETED = "Container shutdown completed."
