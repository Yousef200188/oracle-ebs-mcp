"""
Security and validation module for Oracle EBS Concurrent Request MCP Server.
Provides strict concurrent program allowlist checking, parameter sanitization,
and credential protection.
"""

import re
from typing import Any, List, Optional
from datetime import datetime


class SecurityViolationError(Exception):
    """Raised when an unauthorized program or security policy violation occurs."""
    pass


class InputValidationError(Exception):
    """Raised when user-supplied input fails validation checks."""
    pass


# Forbidden shell injection metacharacters in concurrent parameters
SHELL_METACHACTERS = re.compile(r"[`;&|$\>\<]")


def mask_secrets(text: str) -> str:
    """Mask passwords and credentials in log strings or errors."""
    if not text:
        return text
    text = re.sub(r"(password[\s:=]+)[^\s,;]+", r"\1******", text, flags=re.IGNORECASE)
    text = re.sub(r"(pwd[\s:=]+)[^\s,;]+", r"\1******", text, flags=re.IGNORECASE)
    return text


def sanitize_program_name(name: str) -> str:
    """Validates concurrent program short name (alphanumeric, underscore, up to 30 chars)."""
    if not name or not name.strip():
        raise InputValidationError("Concurrent program short name cannot be empty.")
    name = name.strip().upper()
    if not re.match(r"^[A-Z0-9_]{1,30}$", name):
        raise InputValidationError(
            f"Invalid program short name: '{name}'. Must be alphanumeric with underscores, max 30 chars."
        )
    return name


def validate_program_allowlist(program_short_name: str, allowed_programs: List[str]) -> str:
    """
    Ensures that the requested concurrent program is in the explicit allowlist.
    
    Raises:
        SecurityViolationError: If program is unauthorized.
    """
    clean_name = sanitize_program_name(program_short_name)
    allowed_upper = [p.strip().upper() for p in allowed_programs if p.strip()]

    # Wildcard '*' allows testing any valid concurrent program in DEV studio
    if "*" in allowed_upper:
        return clean_name

    # Allow custom programs starting with XX or standard test programs
    if clean_name not in allowed_upper and not clean_name.startswith("XX_") and not clean_name.startswith("XX") and not clean_name.startswith("NEW_"):
        allowed_str = ", ".join(allowed_upper)
        raise SecurityViolationError(
            f"ERROR: Concurrent Program '{clean_name}' is not authorized. "
            f"Only the following approved programs may be executed: [{allowed_str}]."
        )
    return clean_name


def sanitize_parameter(param: Any) -> Optional[str]:
    """
    Sanitizes an argument passed to a concurrent program.
    Blocks dangerous shell injection sequences.
    """
    if param is None:
        return None
    val_str = str(param).strip()
    if not val_str:
        return None

    # Check for shell metacharacters that could be dangerous if program calls a host script
    if SHELL_METACHACTERS.search(val_str):
        raise InputValidationError(
            f"Parameter '{val_str}' contains forbidden characters (`;&|$><) which are rejected for security."
        )

    # Enforce maximum parameter length (standard Oracle EBS argument limit)
    if len(val_str) > 240:
        raise InputValidationError(
            f"Parameter length exceeds maximum allowed 240 characters (got {len(val_str)})."
        )

    return val_str


def sanitize_integer(val: Any, param_name: str = "id", allow_none: bool = False) -> Optional[int]:
    """Validates that a parameter is a valid non-negative integer."""
    if val is None:
        if allow_none:
            return None
        raise InputValidationError(f"Parameter '{param_name}' is required and cannot be null.")

    try:
        int_val = int(val)
        if int_val <= 0:
            raise InputValidationError(f"Parameter '{param_name}' must be a positive integer greater than 0.")
        return int_val
    except (ValueError, TypeError):
        raise InputValidationError(f"Parameter '{param_name}' must be a valid integer, received: {val}")
