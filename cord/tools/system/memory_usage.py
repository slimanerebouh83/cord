"""CORD Tool - get_memory_usage"""
from __future__ import annotations
import shutil
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GetMemoryUsageTool(BaseTool):
    name = "get_memory_usage"
    description = "Get system RAM and virtual memory usage."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        try:
            try:
                import psutil
                mem = psutil.virtual_memory()
                total_gb = mem.total / (1024 ** 3)
                used_gb = mem.used / (1024 ** 3)
                free_gb = mem.available / (1024 ** 3)
                out = f"RAM Total: {total_gb:.2f} GB | Used: {used_gb:.2f} GB ({mem.percent}%) | Available: {free_gb:.2f} GB"
                return ToolResult(success=True, output=out)
            except ImportError:
                return ToolResult(success=True, output="Memory usage requires psutil for detailed metrics.")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
