"""CORD Tool - run_project"""
from __future__ import annotations
import subprocess
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.execution.process_tracker import process_tracker

class RunProjectTool(BaseTool):
    name = "run_project"
    description = "Launch or execute the project's primary entry point (e.g. main.py, npm start, npm run dev, cargo run)."
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Optional custom command to run. If omitted, detects standard entry point (npm start, main.py, etc.)"
            },
            "background": {
                "type": "boolean",
                "description": "If true, spawn as background process and return process ID for servers; if false, wait for output (timeout 30s)",
                "default": False
            }
        },
        "required": []
    }

    async def execute(self, command: str | None = None, background: bool = False, **kwargs) -> ToolResult:
        try:
            cwd = Path.cwd()
            if not command:
                if (cwd / "package.json").exists():
                    command = "npm run dev" if "dev" in (cwd / "package.json").read_text(encoding="utf-8", errors="ignore") else "npm start"
                elif (cwd / "Cargo.toml").exists():
                    command = "cargo run"
                elif (cwd / "main.py").exists():
                    command = "python main.py"
                elif (cwd / "app.py").exists():
                    command = "python app.py"
                else:
                    return ToolResult(success=False, output="", error="Could not auto-determine project entry point. Please provide 'command'.")

            if background:
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=str(cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                proc_id = f"run_{proc.pid}"
                process_tracker.register(proc_id=proc_id, command=command, pid=proc.pid, process_obj=proc)
                pid = proc.pid
                
                # Check for common web dev server ports in project files or command
                detected_port = None
                for port in ("3000", "5173", "8000", "8080", "5000", "4200"):
                    if port in command:
                        detected_port = port
                        break

                url_hint = f"http://localhost:{detected_port}" if detected_port else "http://localhost:3000 (or check server output)"
                output_msg = (
                    f"Project started in background with PID {pid} (Tracked ID: {pid})\n"
                    f"Command: {command}\n\n"
                    f"⚡ Computer-Use Autonomous Testing Guide:\n"
                    f"  1. Open/Focus application in browser: `browser_media(action='open_url', url='{url_hint}')` or `computer_window(action='focus')`\n"
                    f"  2. Inspect UI visually: `computer_screenshot()`\n"
                    f"  3. Autonomously test buttons & UI controls: `computer_act(action='click_point', x=..., y=...)`"
                )
                return ToolResult(
                    success=True,
                    output=output_msg,
                    metadata={"pid": pid, "command": command, "url_hint": url_hint}
                )
            else:
                res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30, cwd=str(cwd))
                out = f"Command: {command}\nExit Code: {res.returncode}\n\nSTDOUT:\n{res.stdout[-2000:]}"
                if res.stderr:
                    out += f"\nSTDERR:\n{res.stderr[-1000:]}"
                return ToolResult(
                    success=(res.returncode == 0),
                    output=out,
                    error="" if res.returncode == 0 else f"Process exited with code {res.returncode}"
                )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Project run timed out after 30 seconds (consider using background=true for long-running servers).")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
