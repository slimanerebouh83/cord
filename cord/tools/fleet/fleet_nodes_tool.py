"""
CORD Tools - Fleet Nodes Management Tool
Allows the agent to register, list, delete, and ping remote SSH machines.
"""

from __future__ import annotations
from typing import Optional, List
from cord.tools.base import BaseTool, ToolResult
from cord.fleet.manager import fleet_mgr
from cord.fleet.models import FleetNode
from cord.fleet.ssh_executor import ssh_executor


class FleetNodesTool(BaseTool):
    name = "fleet_nodes"
    description = (
        "Manage remote SSH machines in the CORD fleet. Supports 'list' (show all registered nodes), "
        "'add' (register a new machine), 'remove' (deregister a machine), and 'test' (ping and detect OS/specs)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "add", "remove", "test"],
                "description": "Action to perform on fleet nodes",
            },
            "name": {"type": "string", "description": "Unique machine name (e.g. 'web-server', 'storage-nas')"},
            "host": {"type": "string", "description": "Hostname or IP address of the machine"},
            "port": {"type": "integer", "description": "SSH port (default: 22)", "default": 22},
            "user": {"type": "string", "description": "SSH username (default: 'root')", "default": "root"},
            "key_path": {"type": "string", "description": "Path to SSH private key (e.g. '~/.ssh/id_rsa')"},
            "os_type": {"type": "string", "enum": ["linux", "darwin", "windows", "unknown"], "default": "linux"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of tags (e.g. ['server', 'web', 'database', 'photos'])",
            },
            "description": {"type": "string", "description": "Notes about the machine's intended role"},
        },
        "required": ["action"],
    }

    async def execute(
        self,
        action: str,
        name: Optional[str] = None,
        host: Optional[str] = None,
        port: int = 22,
        user: str = "root",
        key_path: Optional[str] = None,
        os_type: str = "linux",
        tags: Optional[List[str]] = None,
        description: str = "",
        **kwargs,
    ) -> ToolResult:
        if action == "list":
            nodes = fleet_mgr.list_nodes()
            if not nodes:
                return ToolResult(
                    success=True,
                    output="No remote machines registered yet in CORD fleet. Use fleet_nodes(action='add', name=..., host=...) to register a node.",
                )
            lines = [f"Found {len(nodes)} registered fleet machine(s):"]
            for n in nodes:
                tag_str = f" [tags: {', '.join(n.tags)}]" if n.tags else ""
                lines.append(f"- 🖥️  {n.name} ({n.user}@{n.host}:{n.port}) │ OS: {n.os_type} │ Status: {n.status}{tag_str} │ {n.description}")
            return ToolResult(success=True, output="\n".join(lines))

        elif action == "add":
            if not name or not host:
                return ToolResult(success=False, output="Both 'name' and 'host' are required to add a fleet node.")
            node = FleetNode(
                name=name.strip(),
                host=host.strip(),
                port=port,
                user=user.strip(),
                key_path=key_path.strip() if key_path else None,
                os_type=os_type,
                tags=tags or [],
                description=description,
                status="configured",
            )
            fleet_mgr.add_node(node)
            return ToolResult(
                success=True,
                output=f"Successfully registered node '{node.name}' ({node.user}@{node.host}:{node.port}) in CORD fleet.",
            )

        elif action == "remove":
            if not name:
                return ToolResult(success=False, output="Parameter 'name' is required to remove a node.")
            removed = fleet_mgr.remove_node(name)
            if removed:
                return ToolResult(success=True, output=f"Node '{name}' removed from fleet.")
            return ToolResult(success=False, output=f"Node '{name}' not found in fleet.")

        elif action == "test":
            if not name:
                return ToolResult(success=False, output="Parameter 'name' is required to test a node.")
            node = fleet_mgr.get_node(name)
            if not node:
                return ToolResult(success=False, output=f"Node '{name}' not found in fleet catalog.")
            test_res = await ssh_executor.test_connection(node)
            if test_res["reachable"]:
                fleet_mgr.update_node_status(node.name, "online", test_res["specs"])
                return ToolResult(
                    success=True,
                    output=(
                        f"✔ Node '{node.name}' is REACHABLE! Latency: {test_res['latency_ms']:.1f}ms\n"
                        f"Detected OS: {test_res['os_type']} ({test_res.get('raw_os')})\n"
                        f"Specs: {test_res.get('specs')}"
                    ),
                )
            else:
                fleet_mgr.update_node_status(node.name, "unreachable")
                return ToolResult(
                    success=False,
                    output=f"❌ Node '{node.name}' connection failed: {test_res.get('error')}",
                )

        return ToolResult(success=False, output=f"Unknown action: '{action}'")
