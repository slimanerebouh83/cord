"""CORD Tool - git_log"""
from __future__ import annotations
import subprocess
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GitLogTool(BaseTool):
    name = "git_log"
    description = "View recent git commit logs."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "max_count": {"type": "integer", "description": "Number of commits (default: 10)"}
        },
        "required": []
    }

    async def execute(self, max_count: int = 10, **kwargs) -> ToolResult:
        try:
            cmd = ["git", "log", f"-n{max_count}", "--oneline", "--decorate"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return ToolResult(success=True, output=f"Git Log:\n{res.stdout.strip() or 'No commits'}")
            return ToolResult(success=False, output="", error=res.stderr.strip() or "Git log failed")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
