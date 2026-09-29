"""
CORD Tools - Fleet File Transfer & Sync Tool
Uploads, downloads, or synchronizes files and directories between local machine and remote nodes.
"""

from __future__ import annotations
import os
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.fleet.manager import fleet_mgr
from cord.fleet.ssh_executor import ssh_executor


class FleetTransferTool(BaseTool):
    name = "fleet_transfer"
    description = (
        "Transfer files or directories between the local machine and remote fleet nodes via SCP. "
        "Supports 'upload' (local to remote) and 'download' (remote to local)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["upload", "download"],
                "description": "'upload' sends local files to remote node; 'download' fetches remote files locally",
            },
            "node": {"type": "string", "description": "Target machine name in fleet"},
            "local_path": {"type": "string", "description": "Path on the local machine"},
            "remote_path": {"type": "string", "description": "Path on the remote machine"},
            "timeout": {
                "type": "number",
                "description": "Transfer timeout in seconds (default: 120)",
                "default": 120,
            },
        },
        "required": ["direction", "node", "local_path", "remote_path"],
    }

    async def execute(
        self,
        direction: str,
        node: str,
        local_path: str,
        remote_path: str,
        timeout: float = 120.0,
        **kwargs,
    ) -> ToolResult:
        target = fleet_mgr.get_node(node)
        if not target:
            return ToolResult(success=False, output=f"Node '{node}' not found in fleet catalog.")

        if direction == "upload":
            res = await ssh_executor.upload(target, local_path, remote_path, timeout=timeout)
            if res["success"]:
                return ToolResult(
                    success=True,
                    output=f"✔ Uploaded '{local_path}' to {node}:{remote_path} in {res.get('duration_ms', 0):.1f}ms.",
                )
            else:
                return ToolResult(
                    success=False,
                    output=f"❌ Upload failed: {res.get('error')}",
                )

        elif direction == "download":
            res = await ssh_executor.download(target, remote_path, local_path, timeout=timeout)
            if res["success"]:
                return ToolResult(
                    success=True,
                    output=f"✔ Downloaded {node}:{remote_path} to '{local_path}' in {res.get('duration_ms', 0):.1f}ms.",
                )
            else:
                return ToolResult(
                    success=False,
                    output=f"❌ Download failed: {res.get('error')}",
                )

        return ToolResult(success=False, output=f"Invalid direction: '{direction}'")
