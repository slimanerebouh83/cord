"""CORD Tool - download_file"""
from __future__ import annotations
from pathlib import Path
import httpx
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class DownloadFileTool(BaseTool):
    name = "download_file"
    description = "Download a remote file from a URL to a local destination path."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to download from"},
            "destination": {"type": "string", "description": "Local destination file path"}
        },
        "required": ["url", "destination"]
    }

    async def execute(self, url: str, destination: str, **kwargs) -> ToolResult:
        try:
            dst = Path(destination).expanduser().resolve()
            dst.parent.mkdir(parents=True, exist_ok=True)
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return ToolResult(success=False, output="", error=f"Download failed: HTTP {res.status_code}")
                with open(dst, "wb") as f:
                    f.write(res.content)
            size_kb = len(res.content) / 1024
            return ToolResult(success=True, output=f"Downloaded {url} -> {destination} ({size_kb:.1f} KB)")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
