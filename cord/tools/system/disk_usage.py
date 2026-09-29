"""CORD Tool - get_disk_usage"""
from __future__ import annotations
import shutil
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GetDiskUsageTool(BaseTool):
    name = "get_disk_usage"
    description = "Get disk space usage for a given path or current drive."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Target folder or drive root (default: '.')"}
        },
        "required": []
    }

    async def execute(self, path: str = ".", **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            total, used, free = shutil.disk_usage(target)
            total_gb = total / (1024 ** 3)
            used_gb = used / (1024 ** 3)
            free_gb = free / (1024 ** 3)
            used_pct = (used / total) * 100
            out = f"Disk at {target}:\nTotal: {total_gb:.1f} GB | Used: {used_gb:.1f} GB ({used_pct:.1f}%) | Free: {free_gb:.1f} GB"
            return ToolResult(success=True, output=out)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
