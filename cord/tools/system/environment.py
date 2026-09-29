"""CORD Tool - get_environment"""
from __future__ import annotations
import os
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class GetEnvironmentTool(BaseTool):
    name = "get_environment"
    description = "Get system environment variables with secrets and API keys safely masked."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {}, "required": []}

    SECRET_KEYWORDS = {"key", "token", "secret", "password", "auth", "credential", "private", "cert"}

    async def execute(self, **kwargs) -> ToolResult:
        try:
            lines = []
            for k, v in sorted(os.environ.items()):
                k_lower = k.lower()
                is_secret = any(kw in k_lower for kw in self.SECRET_KEYWORDS)
                val_repr = "***MASKED***" if is_secret else v[:80]
                lines.append(f"{k}={val_repr}")
            return ToolResult(success=True, output="Environment Variables (Sanitized):\n" + "\n".join(lines[:100]))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
