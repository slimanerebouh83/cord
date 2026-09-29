"""CORD Tool - execute_command"""
from __future__ import annotations
import sys
import uuid
import asyncio
import subprocess
from pathlib import Path
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.execution.process_tracker import process_tracker


class ExecuteCommandTool(BaseTool):
    name = "execute_command"
    description = (
        "Execute a shell command with timeout, output capture, and exit code. "
        "Supports synchronous execution or non-blocking background execution (is_background=True) "
        "allowing the agent to run long-running commands without blocking other operations."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Command to run"},
            "cwd": {"type": "string", "description": "Working directory (default: workspace)"},
            "timeout": {"type": "integer", "description": "Timeout in seconds for synchronous commands (default: 120)"},
            "is_background": {
                "type": "boolean",
                "description": "If true, starts the command in the background immediately without waiting, returning a process ID.",
                "default": False,
            },
        },
        "required": ["command"],
    }

    async def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 120,
        is_background: bool = False,
        **kwargs,
    ) -> ToolResult:
        try:
            work_dir = Path(cwd).expanduser().resolve() if cwd else Path.cwd()
            if not work_dir.exists():
                return ToolResult(success=False, output="", error=f"Directory not found: {cwd}")

            clean_cmd = command.strip()
            # Auto-detect background intent from shell syntax (e.g. ends with &)
            if clean_cmd.endswith("&") and not clean_cmd.endswith("&&"):
                is_background = True
                clean_cmd = clean_cmd[:-1].strip()

            is_win = sys.platform == "win32"
            if is_win:
                cmd_parts = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", clean_cmd]
            else:
                cmd_parts = ["/bin/bash", "-c", clean_cmd]

            # Background execution branch
            if is_background:
                proc = subprocess.Popen(
                    cmd_parts,
                    cwd=str(work_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                proc_id = f"proc_{proc.pid}_{uuid.uuid4().hex[:4]}"
                process_tracker.register(proc_id=proc_id, command=clean_cmd, pid=proc.pid, process_obj=proc)
                return ToolResult(
                    success=True,
                    output=(
                        f"⚡ Background command started successfully.\n"
                        f"Process ID: {proc_id}\n"
                        f"PID: {proc.pid}\n"
                        f"Command: {clean_cmd}\n"
                        f"You can continue other operations concurrently. Use 'manage_process' to view logs or status."
                    ),
                    metadata={"proc_id": proc_id, "pid": proc.pid, "is_background": True},
                )

            # Synchronous execution branch
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=str(work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                return ToolResult(success=False, output="", error=f"Command timed out after {timeout}s.")

            stdout = stdout_bytes.decode(errors="replace")
            stderr = stderr_bytes.decode(errors="replace")
            combined = stdout + (f"\n[STDERR]\n{stderr}" if stderr else "")

            return ToolResult(
                success=(proc.returncode == 0),
                output=combined if combined.strip() else "(No output)",
                metadata={"exit_code": proc.returncode},
                error=f"Exited with code {proc.returncode}" if proc.returncode != 0 else None,
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
