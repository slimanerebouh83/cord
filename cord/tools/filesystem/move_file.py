"""CORD Tool - move_file"""
from __future__ import annotations
import shutil
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class MoveFileTool(BaseTool):
    name = "move_file"
    description = "Move or rename a file or directory from source to destination."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Source path"},
            "destination": {"type": "string", "description": "Destination path"}
        },
        "required": ["source", "destination"]
    }

    async def execute(self, source: str, destination: str, **kwargs) -> ToolResult:
        try:
            src = Path(source).expanduser().resolve()
            dst = Path(destination).expanduser().resolve()
            if not src.exists():
                return ToolResult(success=False, output="", error=f"Source not found: {source}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            return ToolResult(success=True, output=f"Moved {source} to {destination}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
