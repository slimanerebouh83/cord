"""CORD Tool - run_linter"""
from __future__ import annotations
import subprocess
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class RunLinterTool(BaseTool):
    name = "run_linter"
    description = "Run static analysis and linting tools (ruff, flake8, eslint, pylint, clippy) to detect code quality and syntax issues."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "linter": {
                "type": "string",
                "enum": ["auto", "ruff", "flake8", "eslint", "pylint", "clippy"],
                "description": "Linter to run ('auto' selects best tool for workspace)",
                "default": "auto"
            },
            "path": {
                "type": "string",
                "description": "Target file or directory path to lint",
                "default": "."
            },
            "fix": {
                "type": "boolean",
                "description": "If supported, automatically fix safe lint issues",
                "default": False
            }
        },
        "required": []
    }

    async def execute(self, linter: str = "auto", path: str = ".", fix: bool = False, **kwargs) -> ToolResult:
        try:
            cwd = Path.cwd()
            if linter == "auto":
                if (cwd / "package.json").exists():
                    linter = "eslint"
                elif (cwd / "Cargo.toml").exists():
                    linter = "clippy"
                else:
                    linter = "ruff"

            cmd: list[str] = []
            if linter == "ruff":
                cmd = ["ruff", "check", path]
                if fix:
                    cmd.append("--fix")
            elif linter == "flake8":
                cmd = ["flake8", path]
            elif linter == "eslint":
                cmd = ["npx", "eslint", path]
                if fix:
                    cmd.append("--fix")
            elif linter == "pylint":
                cmd = ["pylint", path]
            elif linter == "clippy":
                cmd = ["cargo", "clippy"]
                if fix:
                    cmd.extend(["--fix", "--allow-no-vcs"])
            else:
                return ToolResult(success=False, output="", error=f"Unsupported linter: {linter}")

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(cwd), shell=False)
            output = f"Linter: {linter}\nExit Code: {res.returncode}\n{res.stdout.strip()}"
            if res.stderr:
                output += f"\n{res.stderr.strip()}"

            clean = (res.returncode == 0)
            return ToolResult(
                success=clean,
                output=output if output.strip() else "No lint errors found. Code is clean!",
                error="" if clean else f"Linter identified issues (exit code {res.returncode})"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
