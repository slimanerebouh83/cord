"""CORD Tool - install_dependencies"""
from __future__ import annotations
import subprocess
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class InstallDependenciesTool(BaseTool):
    name = "install_dependencies"
    description = "Install project dependencies or a specific package using pip, npm, pnpm, yarn, or poetry."
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "manager": {
                "type": "string",
                "enum": ["auto", "pip", "npm", "pnpm", "yarn", "poetry", "cargo"],
                "description": "Package manager to use ('auto' detects by lockfile or project files)",
                "default": "auto"
            },
            "package": {
                "type": "string",
                "description": "Optional specific package to install (e.g. 'pytest', 'axios'). If omitted, installs all project dependencies."
            }
        },
        "required": []
    }

    async def execute(self, manager: str = "auto", package: str | None = None, **kwargs) -> ToolResult:
        try:
            cwd = Path.cwd()
            if manager == "auto":
                if (cwd / "poetry.lock").exists() or (cwd / "pyproject.toml").exists():
                    manager = "poetry" if (cwd / "poetry.lock").exists() else "pip"
                elif (cwd / "pnpm-lock.yaml").exists():
                    manager = "pnpm"
                elif (cwd / "yarn.lock").exists():
                    manager = "yarn"
                elif (cwd / "package.json").exists():
                    manager = "npm"
                elif (cwd / "Cargo.toml").exists():
                    manager = "cargo"
                else:
                    manager = "pip"

            cmd: list[str] = []
            if manager == "pip":
                if package:
                    cmd = ["python", "-m", "pip", "install", package]
                elif (cwd / "requirements.txt").exists():
                    cmd = ["python", "-m", "pip", "install", "-r", "requirements.txt"]
                elif (cwd / "pyproject.toml").exists():
                    cmd = ["python", "-m", "pip", "install", "-e", "."]
                else:
                    return ToolResult(success=False, output="", error="No requirements.txt or pyproject.toml found for pip")
            elif manager == "npm":
                cmd = ["npm", "install"]
                if package:
                    cmd.append(package)
            elif manager == "pnpm":
                cmd = ["pnpm", "add" if package else "install"]
                if package:
                    cmd.append(package)
            elif manager == "yarn":
                cmd = ["yarn", "add" if package else "install"]
                if package:
                    cmd.append(package)
            elif manager == "poetry":
                cmd = ["poetry", "add" if package else "install"]
                if package:
                    cmd.append(package)
            elif manager == "cargo":
                if package:
                    cmd = ["cargo", "add", package]
                else:
                    cmd = ["cargo", "build"]
            else:
                return ToolResult(success=False, output="", error=f"Unsupported package manager: {manager}")

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(cwd), shell=False)
            output = f"Command: {' '.join(cmd)}\nExit Code: {res.returncode}\n{res.stdout.strip()}"
            if res.stderr:
                output += f"\n{res.stderr.strip()}"

            success = (res.returncode == 0)
            return ToolResult(
                success=success,
                output=output,
                error="" if success else f"Package installation failed with exit code {res.returncode}"
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Dependency installation timed out after 180 seconds")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
