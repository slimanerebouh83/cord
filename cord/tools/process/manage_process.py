"""CORD Tool - manage_process"""
from __future__ import annotations
import json
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.execution.process_tracker import process_tracker


class ManageProcessTool(BaseTool):
    name = "manage_process"
    description = (
        "Manage background commands and long-running processes: check status, inspect live output/logs, "
        "list running background tasks, or terminate processes."
    )
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "logs", "status", "stop"],
                "description": "Action to perform: 'list' (all background processes), 'logs' (get stdout/stderr), 'status' (check if running), 'stop' (kill process)",
            },
            "proc_id": {
                "type": "string",
                "description": "Process ID (e.g. 'proc_1234_abcd') for 'logs', 'status', or 'stop'",
            },
            "tail": {
                "type": "integer",
                "description": "Number of recent lines to retrieve for 'logs' (default 50)",
                "default": 50,
            },
        },
        "required": ["action"],
    }

    async def execute(self, action: str, proc_id: Optional[str] = None, tail: int = 50, **kwargs) -> ToolResult:
        if action == "list":
            procs = process_tracker.list_all()
            if not procs:
                return ToolResult(success=True, output="No background processes currently tracked.")
            lines = [f"Active Background Processes ({len(procs)}):"]
            for pid_k, info in procs.items():
                lines.append(
                    f"- **{pid_k}** (PID {info['pid']}) [{info['status']} | Uptime: {info['uptime_seconds']}s]: `{info['command'][:60]}`"
                )
            return ToolResult(success=True, output="\n".join(lines), metadata={"processes": procs})

        if not proc_id:
            return ToolResult(success=False, output="", error="Parameter 'proc_id' is required for action: " + action)

        if action in ("logs", "status"):
            info = process_tracker.get_logs(proc_id=proc_id, tail=tail)
            if not info.get("success"):
                return ToolResult(success=False, output="", error=info.get("error", "Process not found"))
            output_msg = (
                f"Process [{proc_id}] Status: {info['status']} (PID: {info['pid']}, Uptime: {info['uptime_seconds']}s)\n"
                f"Command: {info['command']}\n"
                f"{info['output']}"
            )
            return ToolResult(success=True, output=output_msg, metadata=info)

        if action == "stop":
            success = process_tracker.stop(proc_id)
            if success:
                return ToolResult(success=True, output=f"Process '{proc_id}' successfully terminated.")
            return ToolResult(success=False, output="", error=f"Could not stop process '{proc_id}'.")

        return ToolResult(success=False, output="", error=f"Unknown action: '{action}'")
