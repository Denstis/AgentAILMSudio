"""
Sandbox module for LM Agent.

Provides code validation and safe execution environment.
"""

from .validator import (
    ValidationResult,
    safe_path
)

from .modules import (
    get_allowed_modules,
    is_module_allowed,
    contains_forbidden_pattern
)

__all__ = [
    # Validator
    "ValidationResult",
    "safe_path",
    
    # Modules
    "get_allowed_modules",
    "is_module_allowed",
    "contains_forbidden_pattern",
]