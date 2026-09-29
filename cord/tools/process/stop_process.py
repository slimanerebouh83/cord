"""CORD Tool - stop_process"""
from __future__ import annotations
import os
import signal
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.execution.process_tracker import process_tracker

class StopProcessTool(BaseTool):
    name = "stop_process"
    description = "Stop a running background process by process ID or PID."
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "process_id": {"type": "string", "description": "Tracker process ID (e.g. proc_1234_abcd)"},
            "pid": {"type": "integer", "description": "Optional OS PID"}
        },
        "required": []
    }

    async def execute(self, process_id: str = "", pid: int = 0, **kwargs) -> ToolResult:
        try:
            if process_id:
                stopped = process_tracker.stop(process_id)
                if stopped:
                    return ToolResult(success=True, output=f"Stopped process {process_id}")
            if pid > 0:
                os.kill(pid, signal.SIGTERM)
                return ToolResult(success=True, output=f"Terminated PID {pid}")
            return ToolResult(success=False, output="", error="Must provide process_id or pid.")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
