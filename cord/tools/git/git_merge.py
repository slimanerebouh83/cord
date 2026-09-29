"""CORD Tool - git_merge"""
from __future__ import annotations
import subprocess
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GitMergeTool(BaseTool):
    name = "git_merge"
    description = "Join two or more development histories together (merge another branch into current branch)."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "branch": {
                "type": "string",
                "description": "The name of the branch to merge into the current HEAD"
            }
        },
        "required": ["branch"]
    }

    async def execute(self, branch: str, **kwargs) -> ToolResult:
        try:
            res = subprocess.run(["git", "merge", branch], capture_output=True, text=True, timeout=15)
            if res.returncode == 0:
                return ToolResult(success=True, output=f"Merge successful:\n{res.stdout.strip()}")
            out = res.stdout.strip()
            err = res.stderr.strip()
            return ToolResult(success=False, output=out, error=err or "Git merge conflict or error occurred")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
