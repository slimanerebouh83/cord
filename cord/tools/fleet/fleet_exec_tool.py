"""
CORD Tools - Fleet Remote Command Execution Tool
Runs shell commands across one or multiple remote machines via OpenSSH.
"""

from __future__ import annotations
import asyncio
from typing import Optional, List
from cord.tools.base import BaseTool, ToolResult
from cord.fleet.manager import fleet_mgr
from cord.fleet.ssh_executor import ssh_executor


class FleetExecTool(BaseTool):
    name = "fleet_exec"
    description = (
        "Executes a shell command on a remote fleet machine via SSH. "
        "Can target a specific machine by 'node', or broadcast across all machines matching a 'tag'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute on remote system (e.g. 'docker ps', 'df -h', 'systemctl status nginx')",
            },
            "node": {
                "type": "string",
                "description": "Target machine name (e.g. 'web-server'). If omitted, 'tag' must be provided.",
            },
            "tag": {
                "type": "string",
                "description": "Target all machines matching this tag (e.g. 'server', 'database', 'all')",
            },
            "timeout": {
                "type": "number",
                "description": "Execution timeout in seconds (default: 60)",
                "default": 60,
            },
        },
        "required": ["command"],
    }

    async def execute(
        self,
        command: str,
        node: Optional[str] = None,
        tag: Optional[str] = None,
        timeout: float = 60.0,
        **kwargs,
    ) -> ToolResult:
        if not node and not tag:
            return ToolResult(success=False, output="Must specify either 'node' or 'tag' to target machines.")

        # Single target node
        if node:
            target = fleet_mgr.get_node(node)
            if not target:
                return ToolResult(success=False, output=f"Node '{node}' not found in fleet catalog.")
            res = await ssh_executor.execute(target, command, timeout=timeout)
            return ToolResult(
                success=res.success,
                output=res.summary(),
            )

        # Broadcast across matching tags
        targets = fleet_mgr.list_nodes(tag=None if tag == "all" else tag)
        if not targets:
            return ToolResult(success=False, output=f"No machines found matching tag '{tag}'.")

        tasks = [ssh_executor.execute(t, command, timeout=timeout) for t in targets]
        results = await asyncio.gather(*tasks)

        lines = [f"Executed across {len(results)} machine(s) for tag '{tag}':"]
        all_success = True
        for r in results:
            lines.append(f"\n--- [Node: {r.node_name}] ---")
            lines.append(r.summary())
            if not r.success:
                all_success = False

        return ToolResult(success=all_success, output="\n".join(lines))
