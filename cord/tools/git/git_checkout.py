"""CORD Tool - git_checkout"""
from __future__ import annotations
import subprocess
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GitCheckoutTool(BaseTool):
    name = "git_checkout"
    description = "Switch branches or restore working tree files."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Branch name, commit SHA, or file path to checkout"
            },
            "create_new": {
                "type": "boolean",
                "description": "If true, checkout with -b to create and switch to a new branch"
            }
        },
        "required": ["target"]
    }

    async def execute(self, target: str, create_new: bool = False, **kwargs) -> ToolResult:
        try:
            cmd = ["git", "checkout"]
            if create_new:
                cmd.append("-b")
            cmd.append(target)
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if res.returncode == 0:
                msg = res.stdout.strip() or res.stderr.strip() or f"Switched to {target}"
                return ToolResult(success=True, output=msg)
            return ToolResult(success=False, output="", error=res.stderr.strip() or f"Failed to checkout {target}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
