"""CORD UI - Text Compatibility Helpers"""
from __future__ import annotations

def is_arabic(text: str) -> bool:
    """Check if string contains any Arabic characters (disabled)."""
    return False

def fix_arabic(text: str) -> str:
    """Safe pass-through for string formatting."""
    return text if text else ""

