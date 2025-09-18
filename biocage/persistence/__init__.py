"""
Persistence module for BioCage.

This module handles state persistence between executions in persistent containers,
including session script generation and state management.
"""

from .session_script import SessionScriptGenerator

__all__ = ["SessionScriptGenerator"]
