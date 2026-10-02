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
        "Manage remote SSH machines in the CORD fleet. Actions:\n"
        "- 'list': show all registered nodes\n"
        "- 'add': register a new machine by host/port/user\n"
        "- 'quick_connect' or 'connect': register by URI (e.g. 'ssh://user@192.168.1.50:22' or 'pi@192.168.1.100')\n"
        "- 'remove': deregister a machine by name\n"
        "- 'test': ping and detect OS specs for a specific node\n"
        "- 'ping_all': concurrently ping all machines in the fleet\n"
        "- 'scan': scan local subnet for open SSH ports to discover nearby computers\n"
        "- 'broadcast': run a command concurrently on all matching fleet machines"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "add", "connect", "quick_connect", "remove", "test", "ping_all", "scan", "broadcast"],
                "description": "Action to perform on fleet nodes",
            },
            "name": {"type": "string", "description": "Unique machine name (e.g. 'web-server', 'storage-nas')"},
            "uri": {"type": "string", "description": "Connection URI for 'quick_connect' (e.g. 'ssh://user@host:port' or 'user@host')"},
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
            "command": {"type": "string", "description": "Shell command to execute across nodes for 'broadcast'"},
            "subnet": {"type": "string", "description": "Subnet prefix for 'scan' (e.g. '192.168.1.')"},
            "tag": {"type": "string", "description": "Tag filter for 'ping_all' or 'broadcast'"},
        },
        "required": ["action"],
    }

    async def execute(
        self,
        action: str,
        name: Optional[str] = None,
        uri: Optional[str] = None,
        host: Optional[str] = None,
        port: int = 22,
        user: str = "root",
        key_path: Optional[str] = None,
        os_type: str = "linux",
        tags: Optional[List[str]] = None,
        description: str = "",
        command: Optional[str] = None,
        subnet: Optional[str] = None,
        tag: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        if action == "list":
            nodes = fleet_mgr.list_nodes(tag=tag)
            if not nodes:
                return ToolResult(
                    success=True,
                    output="No remote machines registered yet in CORD fleet. Use fleet_nodes(action='connect', uri='user@host') to register a node.",
                )
            lines = [f"Found {len(nodes)} registered fleet machine(s):"]
            for n in nodes:
                tag_str = f" [tags: {', '.join(n.tags)}]" if n.tags else ""
                lines.append(f"- 🖥️  {n.name} ({n.user}@{n.host}:{n.port}) │ OS: {n.os_type} │ Status: {n.status}{tag_str} │ {n.description}")
            return ToolResult(success=True, output="\n".join(lines))

        elif action in ("quick_connect", "connect"):
            target_uri = uri or host
            if not target_uri:
                return ToolResult(success=False, output="Parameter 'uri' (e.g. 'user@host:22') is required for quick_connect.")
            node = fleet_mgr.connect_quick_uri(
                uri=target_uri,
                name=name,
                tags=tags,
                key_path=key_path,
                description=description,
            )
            return ToolResult(
                success=True,
                output=f"✔ Quick-connected node '{node.name}' ({node.user}@{node.host}:{node.port})! Registered in ~/.cord/fleet.json.",
            )

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

        elif action == "ping_all":
            results = await fleet_mgr.ping_all_nodes(tag=tag)
            if not results:
                return ToolResult(success=True, output="No nodes found to ping.")
            lines = [f"Fleet Health Ping Report ({len(results)} nodes):"]
            for r in results:
                status_icon = "✔ [ONLINE]" if r["reachable"] else "❌ [UNREACHABLE]"
                lines.append(
                    f"{status_icon} {r['name']} ({r['user']}@{r['host']}:{r['port']}) "
                    f"│ Latency: {r['latency_ms']:.1f}ms │ OS: {r['os_type']}"
                )
            return ToolResult(success=True, output="\n".join(lines))

        elif action == "scan":
            devices = await fleet_mgr.scan_local_subnet(subnet_prefix=subnet)
            if not devices:
                return ToolResult(success=True, output="Scan complete: No open SSH devices found on the subnet.")
            lines = [f"Discovered {len(devices)} active SSH machine(s) on local network:"]
            for d in devices:
                lines.append(f"• 📡 Host: {d['host']}:{d['port']} (SSH Open)")
            lines.append("Use fleet_nodes(action='connect', uri='user@<host>') to pair with any of these machines.")
            return ToolResult(success=True, output="\n".join(lines))

        elif action == "broadcast":
            if not command:
                return ToolResult(success=False, output="Parameter 'command' is required for broadcast.")
            results = await fleet_mgr.broadcast_command(command=command, tag=tag)
            if not results:
                return ToolResult(success=True, output="No nodes available to broadcast command.")
            lines = [f"Broadcast '{command}' results across {len(results)} nodes:\n"]
            for r in results:
                lines.append(r.summary())
            return ToolResult(success=True, output="\n".join(lines))

        return ToolResult(success=False, output=f"Unknown action: '{action}'")
