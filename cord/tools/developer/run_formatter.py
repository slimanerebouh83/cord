"""CORD Tool - run_formatter"""
from __future__ import annotations
import subprocess
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class RunFormatterTool(BaseTool):
    name = "run_formatter"
    description = "Automatically format code using black, ruff, prettier, autopep8, or rustfmt."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "formatter": {
                "type": "string",
                "enum": ["auto", "black", "ruff", "prettier", "rustfmt"],
                "description": "Code formatting tool to run ('auto' detects by file types in workspace)",
                "default": "auto"
            },
            "path": {
                "type": "string",
                "description": "Target file or directory path to format (default: current directory)",
                "default": "."
            },
            "check_only": {
                "type": "boolean",
                "description": "If true, only check formatting without modifying files (dry-run)",
                "default": False
            }
        },
        "required": []
    }

    async def execute(self, formatter: str = "auto", path: str = ".", check_only: bool = False, **kwargs) -> ToolResult:
        try:
            cwd = Path.cwd()
            if formatter == "auto":
                if (cwd / "package.json").exists():
                    formatter = "prettier"
                elif (cwd / "Cargo.toml").exists():
                    formatter = "rustfmt"
                else:
                    # Check if ruff or black exists
                    formatter = "black"

            cmd: list[str] = []
            if formatter == "black":
                cmd = ["black", path]
                if check_only:
                    cmd.append("--check")
            elif formatter == "ruff":
                cmd = ["ruff", "format", path]
                if check_only:
                    cmd.append("--check")
            elif formatter == "prettier":
                cmd = ["npx", "prettier", "--write" if not check_only else "--check", path]
            elif formatter == "rustfmt":
                cmd = ["cargo", "fmt"]
                if check_only:
                    cmd.extend(["--", "--check"])
            else:
                return ToolResult(success=False, output="", error=f"Unsupported formatter: {formatter}")

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(cwd), shell=False)
            output = f"Formatter: {formatter}\nExit Code: {res.returncode}\n{res.stdout.strip()}"
            if res.stderr:
                output += f"\n{res.stderr.strip()}"

            return ToolResult(
                success=(res.returncode == 0),
                output=output,
                error="" if res.returncode == 0 else f"Formatter exited with code {res.returncode}"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
