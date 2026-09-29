"""CORD Tool - git_status"""
from __future__ import annotations
import subprocess
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GitStatusTool(BaseTool):
    name = "git_status"
    description = "Check git status of the current workspace repository."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        try:
            res = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                out = res.stdout.strip() or "Working tree clean, no uncommitted changes."
                return ToolResult(success=True, output=f"Git Status:\n{out}")
            return ToolResult(success=False, output="", error=f"Git error: {res.stderr.strip() or 'Not a git repo'}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
