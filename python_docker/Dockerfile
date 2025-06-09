# Use Python 3.11 slim image for minimal size
FROM python:3.11-slim

# Set environment variables for better Python behavior
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_PYTHON_DOWNLOADS=never

# Create a non-root user for security
RUN groupadd -r sandbox && useradd -r -g sandbox -d /app -s /bin/bash sandbox

# Install UV package manager
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml requirements.txt ./

# Install dependencies using UV (much faster than pip)
RUN uv pip install --system --no-cache -r requirements.txt

# Copy the execution script
COPY execute.py ./

# Create directories for code execution
RUN mkdir -p /app/workspace /app/output && \
    chown -R sandbox:sandbox /app

# Switch to non-root user
USER sandbox

# Set the default command
CMD ["python", "execute.py"] 