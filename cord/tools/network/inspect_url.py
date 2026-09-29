"""CORD Tool - inspect_url"""
from __future__ import annotations
import httpx
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class InspectUrlTool(BaseTool):
    name = "inspect_url"
    description = "Inspect an HTTP/HTTPS URL and get status code, headers, and content type."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to inspect"}
        },
        "required": ["url"]
    }

    async def execute(self, url: str, **kwargs) -> ToolResult:
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                res = await client.head(url)
                if res.status_code == 405: # Method Not Allowed for HEAD, fallback to GET
                    res = await client.get(url)
                headers_str = "\n".join(f"{k}: {v}" for k, v in res.headers.items())
                out = f"URL: {url}\nStatus: {res.status_code}\nHeaders:\n{headers_str}"
                return ToolResult(success=True, output=out, metadata={"status_code": res.status_code})
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
