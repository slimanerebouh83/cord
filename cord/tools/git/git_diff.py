"""CORD Tool - git_diff"""
from __future__ import annotations
import subprocess
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GitDiffTool(BaseTool):
    name = "git_diff"
    description = "View git diff of unstaged or staged changes."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "staged": {"type": "boolean", "description": "View staged changes if true"}
        },
        "required": []
    }

    async def execute(self, staged: bool = False, **kwargs) -> ToolResult:
        try:
            cmd = ["git", "diff", "--cached"] if staged else ["git", "diff"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if res.returncode == 0:
                out = res.stdout.strip() or "No diff detected."
                return ToolResult(success=True, output=f"Git Diff:\n{out[:4000]}")
            return ToolResult(success=False, output="", error=res.stderr.strip() or "Git diff failed")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
