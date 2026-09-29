"""CORD Tool - git_branch"""
from __future__ import annotations
import subprocess
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GitBranchTool(BaseTool):
    name = "git_branch"
    description = "List branches, create a new branch, or delete an existing branch in the repository."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create", "delete"],
                "description": "Branch operation to perform: 'list', 'create', or 'delete'"
            },
            "branch_name": {
                "type": "string",
                "description": "Name of the branch to create or delete (required for create/delete)"
            }
        },
        "required": ["action"]
    }

    async def execute(self, action: str = "list", branch_name: str | None = None, **kwargs) -> ToolResult:
        try:
            if action == "list":
                res = subprocess.run(["git", "branch", "-a"], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return ToolResult(success=True, output=f"Git Branches:\n{res.stdout.strip()}")
                return ToolResult(success=False, output="", error=res.stderr.strip() or "Failed to list branches")

            if not branch_name:
                return ToolResult(success=False, output="", error="branch_name is required for create/delete actions")

            if action == "create":
                res = subprocess.run(["git", "branch", branch_name], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return ToolResult(success=True, output=f"Successfully created branch '{branch_name}'")
                return ToolResult(success=False, output="", error=res.stderr.strip() or f"Failed to create branch '{branch_name}'")

            elif action == "delete":
                res = subprocess.run(["git", "branch", "-D", branch_name], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return ToolResult(success=True, output=f"Successfully deleted branch '{branch_name}'")
                return ToolResult(success=False, output="", error=res.stderr.strip() or f"Failed to delete branch '{branch_name}'")

            return ToolResult(success=False, output="", error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
