"""
CORD Tools - Shell Execution Subsystem
Executes commands across Windows (PowerShell/cmd) and Unix (bash/sh) with real-time output.
"""

from __future__ import annotations
import os
import sys
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from cord.tools.base import BaseTool, ToolResult
from cord.ui.console import ui


class RunShellTool(BaseTool):
    name = "run_shell"
    description = "Execute a shell command (PowerShell on Windows, bash on Unix). Returns stdout, stderr, and exit code."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The exact command to run.",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command (defaults to current workspace).",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Timeout in seconds before terminating process (default: 120).",
            },
        },
        "required": ["command"],
    }

    async def execute(self, command: str, cwd: Optional[str] = None, timeout_seconds: int = 120, **kwargs) -> ToolResult:
        work_dir = Path(cwd).expanduser().resolve() if cwd else Path.cwd()
        if not work_dir.exists():
            return ToolResult(success=False, output="", error=f"Working directory does not exist: {cwd}")

        is_win = sys.platform == "win32"
        # On Windows, use powershell -Command
        if is_win:
            shell_cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command]
        else:
            shell_cmd = ["/bin/bash", "-c", command]

        ui.console.print(f"\n[bold bright_black]─── Executing: {command} ───[/bold bright_black]")

        try:
            process = await asyncio.create_subprocess_exec(
                *shell_cmd,
                cwd=str(work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_chunks = []
            stderr_chunks = []

            async def read_stream(stream, chunks, is_err=False):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode(errors="replace")
                    chunks.append(decoded)
                    # Live print output line
                    style = "dim red" if is_err else "dim white"
                    ui.console.print(f"  [dim]│[/dim] [{style}]{decoded.rstrip()}[/{style}]")

            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        read_stream(process.stdout, stdout_chunks, False),
                        read_stream(process.stderr, stderr_chunks, True),
                        process.wait(),
                    ),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except Exception:
                    pass
                return ToolResult(
                    success=False,
                    output="".join(stdout_chunks),
                    error=f"Command timed out after {timeout_seconds} seconds.",
                )

            stdout_text = "".join(stdout_chunks)
            stderr_text = "".join(stderr_chunks)
            code = process.returncode

            ui.console.print(f"[bold bright_black]─── Exit Code: {code} ───[/bold bright_black]\n")

            full_output = stdout_text
            if stderr_text:
                full_output += f"\n[STDERR]\n{stderr_text}" if full_output else stderr_text

            if code == 0:
                return ToolResult(
                    success=True,
                    output=full_output if full_output.strip() else "(Command completed with no output)",
                    metadata={"exit_code": code},
                )
            else:
                return ToolResult(
                    success=False,
                    output=full_output,
                    error=f"Process exited with code {code}",
                    metadata={"exit_code": code},
                )

        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to execute command: {e}")
