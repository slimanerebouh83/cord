"""CORD Tool - delete_file"""
from __future__ import annotations
import shutil
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = "Delete a file or directory permanently. High-risk operation."
    required_permission = PermissionLevel.ADMIN
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Target file or directory to delete"}
        },
        "required": ["path"]
    }

    async def execute(self, path: str, **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return ToolResult(success=False, output="", error=f"Target does not exist: {path}")
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return ToolResult(success=True, output=f"Permanently deleted: {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
