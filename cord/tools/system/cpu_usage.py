"""CORD Tool - get_cpu_usage"""
from __future__ import annotations
import os
import time
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GetCpuUsageTool(BaseTool):
    name = "get_cpu_usage"
    description = "Get current CPU count and utilization percentage."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        try:
            cores = os.cpu_count() or 1
            # Check if psutil is available
            try:
                import psutil
                usage = psutil.cpu_percent(interval=0.2)
                return ToolResult(success=True, output=f"CPU Utilization: {usage}%\nLogical Cores: {cores}")
            except ImportError:
                return ToolResult(success=True, output=f"CPU Cores: {cores} (psutil not installed for live %)")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
