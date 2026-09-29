"""CORD Tool - git_commit"""
from __future__ import annotations
import subprocess
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GitCommitTool(BaseTool):
    name = "git_commit"
    description = "Stage changes and record changes to the repository with a commit message."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Commit message describing the changes"
            },
            "add_all": {
                "type": "boolean",
                "description": "If true, stage all modified and untracked files (git add -A) before committing",
                "default": True
            }
        },
        "required": ["message"]
    }

    async def execute(self, message: str, add_all: bool = True, **kwargs) -> ToolResult:
        try:
            if add_all:
                add_res = subprocess.run(["git", "add", "-A"], capture_output=True, text=True, timeout=10)
                if add_res.returncode != 0:
                    return ToolResult(success=False, output="", error=f"Git add failed: {add_res.stderr.strip()}")

            res = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                return ToolResult(success=True, output=f"Commit created successfully:\n{res.stdout.strip()}")
            out = res.stdout.strip()
            err = res.stderr.strip()
            if "nothing to commit" in out or "nothing to commit" in err:
                return ToolResult(success=True, output="Nothing to commit, working tree clean.")
            return ToolResult(success=False, output=out, error=err or "Git commit failed")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
