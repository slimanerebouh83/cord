"""
CORD Tools - Base Tool Specification
Provides typed interfaces, permission mappings, and standardized execution results.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from cord.permissions.levels import PermissionLevel, RiskLevel


@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    truncated: bool = False
    cached_output_id: Optional[str] = None

    def to_string(self) -> str:
        if self.success:
            return self.output
        return f"ERROR: {self.error or self.output}"


class BaseTool:
    """Base class for all modular agent tools."""

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}
    required_permission: PermissionLevel = PermissionLevel.SAFE
    risk_level: RiskLevel = RiskLevel.LOW

    async def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError

    def to_schema(self) -> Dict[str, Any]:
        """Converts tool definition to standard JSON schema for function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
