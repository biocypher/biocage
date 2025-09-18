"""
Session script generation for persistent BioCage containers.

This module handles the generation of session scripts that maintain state
between executions in persistent containers. It manages variable tracking,
import statements, and code history to provide seamless execution continuity.

The SessionScriptGenerator class provides:
- Automatic tracking of imports and variables
- Session state persistence between executions
- Smart code merging and deduplication
- History management and cleanup
- Script generation for container initialization

Example:
    >>> generator = SessionScriptGenerator()
    >>> generator.add_code("import numpy as np")
    >>> generator.add_code("x = 5")
    >>> script = generator.generate_session_script()
    >>> print("Session script ready for container")
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class SessionScriptError(Exception):
    """
    Exception raised when session script operations fail.

    This exception provides detailed information about session script
    generation failures including the operation attempted and error details.

    Attributes:
        operation: The operation that failed
        error_message: Detailed error message
        code_snippet: The code that caused the error (if applicable)
    """

    def __init__(self, operation: str, error_message: str, code_snippet: Optional[str] = None) -> None:
        """
        Initialize a session script error.

        Args:
            operation: Operation that failed
            error_message: Detailed error message
            code_snippet: Code that caused the error
        """
        if code_snippet:
            super().__init__(f"Session script {operation} failed: {error_message} (code: {code_snippet[:50]}...)")
        else:
            super().__init__(f"Session script {operation} failed: {error_message}")
        self.operation = operation
        self.error_message = error_message
        self.code_snippet = code_snippet


class SessionScriptGenerator:
    """
    Generates session scripts for persistent container state management.

    This class tracks code execution history, imports, and variable assignments
    to generate session scripts that restore container state between executions.
    It provides intelligent code analysis and merging capabilities.

    The generator maintains a history of executed code and can produce
    consolidated scripts that recreate the current session state in a
    fresh container instance.

    Attributes:
        imports: Set of import statements from the session
        assignments: Dictionary of variable assignments
        code_history: List of executed code blocks
        max_history_size: Maximum number of code blocks to retain

    Example:
        >>> generator = SessionScriptGenerator()
        >>>
        >>> # Add code from execution history
        >>> generator.add_code("import os")
        >>> generator.add_code("data_dir = '/app/data'")
        >>> generator.add_code("files = os.listdir(data_dir)")
        >>>
        >>> # Generate session script
        >>> script = generator.generate_session_script()
        >>> print("Session script contains imports and variables")
        >>>
        >>> # Reset and start fresh
        >>> generator.clear_session()
    """

    def __init__(self, max_history_size: int = 1000) -> None:
        """
        Initialize the session script generator.

        Args:
            max_history_size: Maximum number of code blocks to retain in history

        Example:
            >>> generator = SessionScriptGenerator(max_history_size=500)
            >>> generator.max_history_size
            500
        """
        self.imports: set[str] = set()
        self.assignments: dict[str, str] = {}
        self.code_history: list[str] = []
        self.max_history_size = max_history_size
        logger.debug("Initialized SessionScriptGenerator with max_history_size=%d", max_history_size)

    def add_code(self, code: str) -> None:
        """
        Add executed code to the session for state tracking.

        This method analyzes the provided code to extract imports, variable
        assignments, and other stateful operations. It updates the session
        state accordingly for later script generation.

        Args:
            code: Code that was executed in the session

        Raises:
            SessionScriptError: If code analysis fails

        Example:
            >>> generator = SessionScriptGenerator()
            >>> generator.add_code("import json")
            >>> generator.add_code("data = {'key': 'value'}")
            >>> len(generator.imports)
            1
            >>> 'data' in generator.assignments
            True
        """
        if not code or not code.strip():
            return

        code = code.strip()

        try:
            # Add to history
            self.code_history.append(code)

            # Maintain history size limit
            if len(self.code_history) > self.max_history_size:
                self.code_history = self.code_history[-self.max_history_size:]

            # Extract imports
            self._extract_imports(code)

            # Extract variable assignments
            self._extract_assignments(code)

            logger.debug("Added code to session: %s", code[:50] + "..." if len(code) > 50 else code)

        except Exception as e:
            raise SessionScriptError("add_code", str(e), code) from e

    def generate_session_script(self, include_history: bool = False) -> str:
        """
        Generate a session script that recreates the current state.

        This method creates a Python script that, when executed, will
        recreate the current session state including imports and variable
        assignments. Optionally includes full execution history.

        Args:
            include_history: Whether to include full code execution history

        Returns:
            Python script as string

        Raises:
            SessionScriptError: If script generation fails

        Example:
            >>> generator = SessionScriptGenerator()
            >>> generator.add_code("import os")
            >>> generator.add_code("x = 42")
            >>> script = generator.generate_session_script()
            >>> "import os" in script
            True
            >>> "x = 42" in script
            True
        """
        try:
            script_parts = []

            # Add header comment
            script_parts.append("# BioCage Session Restoration Script")
            script_parts.append("# This script recreates the session state")
            script_parts.append("")

            # Add imports section
            if self.imports:
                script_parts.append("# Imports")
                for import_stmt in sorted(self.imports):
                    script_parts.append(import_stmt)
                script_parts.append("")

            # Add variable assignments section
            if self.assignments:
                script_parts.append("# Variable assignments")
                for var_name, assignment in self.assignments.items():
                    script_parts.append(assignment)
                script_parts.append("")

            # Optionally add full history
            if include_history and self.code_history:
                script_parts.append("# Execution history")
                script_parts.append("# (This section contains all executed code)")
                for i, code_block in enumerate(self.code_history, 1):
                    script_parts.append(f"# Block {i}:")
                    for line in code_block.split('\n'):
                        script_parts.append(f"# {line}")
                script_parts.append("")

            script = '\n'.join(script_parts)
            logger.debug("Generated session script with %d lines", len(script_parts))
            return script

        except Exception as e:
            raise SessionScriptError("generate_session_script", str(e)) from e

    def get_session_summary(self) -> dict[str, int]:
        """
        Get a summary of the current session state.

        Returns:
            Dictionary with session statistics

        Example:
            >>> generator = SessionScriptGenerator()
            >>> generator.add_code("import os")
            >>> generator.add_code("x = 5")
            >>> summary = generator.get_session_summary()
            >>> summary['imports']
            1
            >>> summary['variables']
            1
        """
        return {
            "imports": len(self.imports),
            "variables": len(self.assignments),
            "code_blocks": len(self.code_history),
            "total_code_length": sum(len(code) for code in self.code_history)
        }

    def clear_session(self) -> None:
        """
        Clear all session state and start fresh.

        This method resets all tracked imports, assignments, and history
        to start a new session from a clean state.

        Example:
            >>> generator = SessionScriptGenerator()
            >>> generator.add_code("import os")
            >>> generator.clear_session()
            >>> len(generator.imports)
            0
        """
        self.imports.clear()
        self.assignments.clear()
        self.code_history.clear()
        logger.info("Cleared session state")

    def has_state(self) -> bool:
        """
        Check if the session has any tracked state.

        Returns:
            True if session has imports, assignments, or history

        Example:
            >>> generator = SessionScriptGenerator()
            >>> generator.has_state()
            False
            >>> generator.add_code("x = 1")
            >>> generator.has_state()
            True
        """
        return len(self.imports) > 0 or len(self.assignments) > 0 or len(self.code_history) > 0

    def get_imports(self) -> set[str]:
        """
        Get all tracked import statements.

        Returns:
            Set of import statements

        Example:
            >>> generator = SessionScriptGenerator()
            >>> generator.add_code("import os")
            >>> generator.add_code("from pathlib import Path")
            >>> imports = generator.get_imports()
            >>> len(imports)
            2
        """
        return self.imports.copy()

    def get_assignments(self) -> dict[str, str]:
        """
        Get all tracked variable assignments.

        Returns:
            Dictionary mapping variable names to assignment statements

        Example:
            >>> generator = SessionScriptGenerator()
            >>> generator.add_code("x = 42")
            >>> assignments = generator.get_assignments()
            >>> assignments['x']
            'x = 42'
        """
        return self.assignments.copy()

    def _extract_imports(self, code: str) -> None:
        """
        Extract import statements from code.

        Args:
            code: Code to analyze for imports
        """
        lines = code.split('\n')
        for line in lines:
            line = line.strip()
            if self._is_import_statement(line):
                self.imports.add(line)

    def _extract_assignments(self, code: str) -> None:
        """
        Extract variable assignments from code.

        Args:
            code: Code to analyze for assignments
        """
        lines = code.split('\n')
        for line in lines:
            line = line.strip()
            if self._is_assignment_statement(line):
                var_name = self._extract_variable_name(line)
                if var_name:
                    self.assignments[var_name] = line

    def _is_import_statement(self, line: str) -> bool:
        """
        Check if a line is an import statement.

        Args:
            line: Line to check

        Returns:
            True if line is an import statement
        """
        line = line.strip()
        return (
            line.startswith('import ') or
            (line.startswith('from ') and ' import ' in line)
        ) and not line.startswith('#')

    def _is_assignment_statement(self, line: str) -> bool:
        """
        Check if a line is a variable assignment.

        Args:
            line: Line to check

        Returns:
            True if line is a variable assignment
        """
        line = line.strip()
        if not line or line.startswith('#'):
            return False

        # Simple heuristic for assignment: contains '=' but not in comparison operators
        if '=' not in line:
            return False

        # Exclude comparison operators
        if any(op in line for op in ['==', '!=', '<=', '>=', '+=', '-=', '*=', '/=']):
            return False

        # Check for simple assignment pattern
        assignment_pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*.+'
        return bool(re.match(assignment_pattern, line))

    def _extract_variable_name(self, assignment_line: str) -> Optional[str]:
        """
        Extract variable name from assignment statement.

        Args:
            assignment_line: Assignment statement

        Returns:
            Variable name if found, None otherwise
        """
        match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=', assignment_line.strip())
        return match.group(1) if match else None

    def remove_variable(self, var_name: str) -> bool:
        """
        Remove a variable from tracked assignments.

        Args:
            var_name: Name of variable to remove

        Returns:
            True if variable was removed, False if not found

        Example:
            >>> generator = SessionScriptGenerator()
            >>> generator.add_code("x = 42")
            >>> generator.remove_variable("x")
            True
            >>> "x" in generator.assignments
            False
        """
        if var_name in self.assignments:
            del self.assignments[var_name]
            logger.debug("Removed variable from session: %s", var_name)
            return True
        return False

    def update_variable(self, var_name: str, assignment: str) -> None:
        """
        Update or add a variable assignment.

        Args:
            var_name: Name of the variable
            assignment: Assignment statement

        Example:
            >>> generator = SessionScriptGenerator()
            >>> generator.update_variable("x", "x = 100")
            >>> generator.assignments["x"]
            'x = 100'
        """
        self.assignments[var_name] = assignment
        logger.debug("Updated variable in session: %s", var_name)

    def get_code_history(self, limit: Optional[int] = None) -> list[str]:
        """
        Get the code execution history.

        Args:
            limit: Maximum number of recent code blocks to return

        Returns:
            List of code blocks in execution order

        Example:
            >>> generator = SessionScriptGenerator()
            >>> generator.add_code("print('hello')")
            >>> generator.add_code("print('world')")
            >>> history = generator.get_code_history(limit=1)
            >>> len(history)
            1
        """
        if limit is None:
            return self.code_history.copy()
        return self.code_history[-limit:] if limit > 0 else []
