"""CORD Tool - http_request"""
from __future__ import annotations
import json
import httpx
from typing import Dict, Any, Optional
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class HttpRequestTool(BaseTool):
    name = "http_request"
    description = "Perform an HTTP request (GET, POST, PUT, DELETE) with custom headers or payload."
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target HTTP/HTTPS URL"},
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "description": "HTTP Method"},
            "headers": {"type": "object", "description": "Optional HTTP headers"},
            "data": {"type": "string", "description": "Optional request body"}
        },
        "required": ["url"]
    }

    async def execute(self, url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, data: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                res = await client.request(method.upper(), url, headers=headers, content=data)
                body = res.text[:4000]
                return ToolResult(
                    success=(200 <= res.status_code < 400),
                    output=f"HTTP {res.status_code}\n{body}",
                    metadata={"status_code": res.status_code}
                )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
