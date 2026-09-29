"""CORD Tool - build_project"""
from __future__ import annotations
import subprocess
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class BuildProjectTool(BaseTool):
    name = "build_project"
    description = "Compile or build the project distribution (e.g. npm run build, cargo build, python -m build)."
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Custom build command. If omitted, detects standard build command."
            }
        },
        "required": []
    }

    async def execute(self, command: str | None = None, **kwargs) -> ToolResult:
        try:
            cwd = Path.cwd()
            if not command:
                if (cwd / "package.json").exists():
                    pkg_text = (cwd / "package.json").read_text(encoding="utf-8", errors="ignore")
                    if "build" in pkg_text:
                        command = "npm run build"
                    else:
                        return ToolResult(success=False, output="", error="No 'build' script found in package.json")
                elif (cwd / "Cargo.toml").exists():
                    command = "cargo build"
                elif (cwd / "pyproject.toml").exists() or (cwd / "setup.py").exists():
                    command = "python -m build"
                elif (cwd / "Makefile").exists():
                    command = "make build"
                else:
                    return ToolResult(success=False, output="", error="No standard build system detected (package.json, Cargo.toml, pyproject.toml, Makefile). Please provide 'command'.")

            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=180, cwd=str(cwd))
            out = f"Build Command: {command}\nExit Code: {res.returncode}\n\nSTDOUT:\n{res.stdout[-3000:]}"
            if res.stderr:
                out += f"\nSTDERR:\n{res.stderr[-2000:]}"

            success = (res.returncode == 0)
            return ToolResult(
                success=success,
                output=out,
                error="" if success else f"Build failed with exit code {res.returncode}"
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Build command timed out after 180 seconds")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
