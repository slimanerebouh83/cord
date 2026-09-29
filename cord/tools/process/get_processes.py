"""CORD Tool - get_processes"""
from __future__ import annotations
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.execution.process_tracker import process_tracker

class GetProcessesTool(BaseTool):
    name = "get_processes"
    description = "List all active background processes launched by CORD."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        try:
            procs = process_tracker.list_all()
            if not procs:
                return ToolResult(success=True, output="No active background processes.")
            lines = [f"- ID: {pid} | PID: {info['pid']} | Status: {info['status']} | Uptime: {info['uptime_seconds']}s | Cmd: {info['command']}" for pid, info in procs.items()]
            return ToolResult(success=True, output="Running Background Processes:\n" + "\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
