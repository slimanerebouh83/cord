"""CORD Tool - create_directory"""
from __future__ import annotations
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class CreateDirectoryTool(BaseTool):
    name = "create_directory"
    description = "Create a directory (and any necessary parent directories)."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path to create"}
        },
        "required": ["path"]
    }

    async def execute(self, path: str, **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            target.mkdir(parents=True, exist_ok=True)
            return ToolResult(success=True, output=f"Created directory: {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
