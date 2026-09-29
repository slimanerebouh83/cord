"""CORD Tool - get_system_info"""
from __future__ import annotations
import sys
import platform
import os
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GetSystemInfoTool(BaseTool):
    name = "get_system_info"
    description = "Get detailed operating system, architecture, CPU count, and Python environment info."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        try:
            info = [
                f"OS: {platform.system()} {platform.release()} ({platform.version()})",
                f"Architecture: {platform.machine()}",
                f"Processor: {platform.processor() or 'Standard'}",
                f"CPU Cores: {os.cpu_count() or 1}",
                f"Python: {sys.version.split()[0]} ({sys.executable})",
                f"Platform: {sys.platform}",
            ]
            return ToolResult(success=True, output="System Specifications:\n" + "\n".join(info))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
