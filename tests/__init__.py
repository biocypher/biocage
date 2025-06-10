"""
CodeSandbox Test Suite

This package contains comprehensive tests for the CodeSandbox Python package.

Test Categories:
- Basic functionality: Core execution and container management
- Persistence: Variable, import, function, and DataFrame persistence
- File exposure: File and directory exposure functionality
- Context manager: Context manager and configuration features
- Error reporting: Error handling and debugging capabilities

Usage:
    # Run all tests
    pytest

    # Run specific test file
    pytest tests/test_basic_functionality.py

    # Run tests with specific marker
    pytest -m "not slow"

    # Run with coverage
    pytest --cov=codesandbox
"""

__version__ = "1.0.0"
__author__ = "CodeSandbox Team"
