"""CORD Tool - start_process"""
from __future__ import annotations
import subprocess
import uuid
from pathlib import Path
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.execution.process_tracker import process_tracker

class StartProcessTool(BaseTool):
    name = "start_process"
    description = "Start a long-running background process (e.g. dev server, background service)."
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Command to run in background"},
            "cwd": {"type": "string", "description": "Working directory (default: workspace)"}
        },
        "required": ["command"]
    }

    async def execute(self, command: str, cwd: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            work_dir = Path(cwd).expanduser().resolve() if cwd else Path.cwd()
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=str(work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            proc_id = f"proc_{proc.pid}_{uuid.uuid4().hex[:4]}"
            process_tracker.register(proc_id=proc_id, command=command, pid=proc.pid, process_obj=proc)
            return ToolResult(
                success=True,
                output=f"Background process started.\nID: {proc_id}\nPID: {proc.pid}\nCommand: {command}",
                metadata={"proc_id": proc_id, "pid": proc.pid}
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
