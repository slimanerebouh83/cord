"""
CORD Permissions - Workspace Sandbox Guard
Enforces filesystem boundaries, prevents path traversal, and protects sensitive files.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Tuple, Optional


class SandboxViolationError(Exception):
    """Raised when an operation attempts to breach the configured workspace."""
    pass


class WorkspaceSandbox:
    """Restricts agent file operations within the workspace root."""

    SENSITIVE_PATTERNS = {
        ".env", "id_rsa", "id_ed25519", "known_hosts",
        ".ssh", ".bash_history", "passwd", "shadow",
        "system32", "windows", "boot.ini"
    }

    def __init__(self, workspace_path: Optional[Path] = None):
        self.workspace_root = (workspace_path or Path.cwd()).resolve()

    def set_workspace(self, path: Path) -> None:
        self.workspace_root = path.resolve()

    def is_within_workspace(self, path: Path | str) -> bool:
        """Verifies that resolved path is strictly inside workspace_root."""
        try:
            resolved = Path(path).expanduser().resolve()
            return resolved == self.workspace_root or self.workspace_root in resolved.parents
        except Exception:
            return False

    def validate_path(self, path: Path | str, allow_outside: bool = False) -> Path:
        """
        Validates a path. Raises SandboxViolationError if path escapes workspace
        and allow_outside is False.
        """
        resolved = Path(path).expanduser().resolve()

        if not allow_outside and not self.is_within_workspace(resolved):
            raise SandboxViolationError(
                f"Security Sandbox Breach: Path '{resolved}' is outside workspace '{self.workspace_root}'!"
            )

        # Check for sensitive files
        path_parts = {p.lower() for p in resolved.parts}
        path_name = resolved.name.lower()
        for sens in self.SENSITIVE_PATTERNS:
            if (sens in path_parts or sens == path_name) and not allow_outside:
                raise SandboxViolationError(
                    f"Security Alert: Access to sensitive file '{resolved}' requires explicit ADMIN approval!"
                )

        return resolved
