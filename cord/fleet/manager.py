"""
CORD Fleet - Node Catalog & Registry Manager
Persists known SSH nodes to ~/.cord/fleet.json and provides search, tagging, and status tracking.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

from cord.fleet.models import FleetNode


class FleetManager:
    """Manages registered SSH machines, tags, and connectivity metadata."""

    def __init__(self, fleet_file: Optional[Path] = None):
        if fleet_file is None:
            self.fleet_file = Path.home() / ".cord" / "fleet.json"
        else:
            self.fleet_file = fleet_file

        self.nodes: Dict[str, FleetNode] = {}
        self.load()

    def load(self) -> None:
        """Loads node catalog from disk."""
        if not self.fleet_file.exists():
            return
        try:
            with open(self.fleet_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        node = FleetNode.from_dict(item)
                        self.nodes[node.name] = node
                elif isinstance(data, dict):
                    for name, item in data.items():
                        node = FleetNode.from_dict(item)
                        self.nodes[name] = node
        except Exception:
            pass

    def save(self) -> None:
        """Saves current nodes to disk."""
        try:
            self.fleet_file.parent.mkdir(parents=True, exist_ok=True)
            data = [node.to_dict() for node in self.nodes.values()]
            with open(self.fleet_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def add_node(self, node: FleetNode) -> FleetNode:
        """Registers or updates a fleet node."""
        self.nodes[node.name] = node
        self.save()
        return node

    def remove_node(self, name: str) -> bool:
        """Removes a registered machine."""
        if name in self.nodes:
            del self.nodes[name]
            self.save()
            return True
        return False

    def get_node(self, name: str) -> Optional[FleetNode]:
        """Gets a node by name."""
        return self.nodes.get(name)

    def list_nodes(self, tag: Optional[str] = None) -> List[FleetNode]:
        """Lists all nodes, optionally filtered by tag."""
        nodes = list(self.nodes.values())
        if tag:
            nodes = [n for n in nodes if n.matches_tag(tag)]
        return nodes

    def update_node_status(
        self,
        name: str,
        status: str,
        system_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Updates last_seen, status, and system specs for a node."""
        node = self.nodes.get(name)
        if node:
            node.status = status
            node.last_seen = time.time()
            if system_info:
                node.system_info.update(system_info)
                if "os_type" in system_info:
                    node.os_type = system_info["os_type"]
            self.save()

    @staticmethod
    def discover_default_ssh_key() -> Optional[str]:
        """Auto-detects common SSH private keys in ~/.ssh/."""
        ssh_dir = Path.home() / ".ssh"
        if not ssh_dir.exists():
            return None
        candidate_keys = ["id_ed25519", "id_rsa", "id_ecdsa"]
        for key_name in candidate_keys:
            key_path = ssh_dir / key_name
            if key_path.exists() and key_path.is_file():
                return str(key_path)
        return None

    @classmethod
    def parse_connection_uri(cls, uri: str) -> Dict[str, Any]:
        """
        Parses connection strings into connection parameters.
        Supported formats:
        - ssh://user@host:2222
        - ssh://user:pass@host:22
        - user@host:2222
        - user@host
        - host:2222
        - host
        """
        raw = uri.strip()
        if raw.startswith("ssh://"):
            raw = raw[6:]

        user = "root"
        password = None
        port = 22
        host = raw

        # Check for user info: user[:pass]@host
        if "@" in raw:
            user_part, host_part = raw.split("@", 1)
            host = host_part
            if ":" in user_part:
                user, password = user_part.split(":", 1)
            else:
                user = user_part

        # Check for host:port
        if ":" in host:
            host, port_str = host.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                pass

        # Discovered SSH key fallback
        default_key = cls.discover_default_ssh_key()

        return {
            "user": user or "root",
            "password": password,
            "host": host,
            "port": port,
            "key_path": default_key,
        }

    def connect_quick_uri(
        self,
        uri: str,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        key_path: Optional[str] = None,
        description: str = "",
    ) -> FleetNode:
        """Quickly registers a remote machine using a connection URI."""
        parsed = self.parse_connection_uri(uri)
        node_name = name.strip() if name else f"{parsed['user']}@{parsed['host']}"
        if key_path:
            parsed["key_path"] = key_path

        node = FleetNode(
            name=node_name,
            host=parsed["host"],
            port=parsed["port"],
            user=parsed["user"],
            password=parsed.get("password"),
            key_path=parsed.get("key_path"),
            tags=tags or ["quick-connect"],
            description=description or f"Registered via quick URI: {uri}",
            status="configured",
        )
        return self.add_node(node)

    async def ping_all_nodes(self, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Concurrently pings all matching fleet nodes and updates their status."""
        import asyncio
        from cord.fleet.ssh_executor import ssh_executor

        targets = self.list_nodes(tag=tag)
        if not targets:
            return []

        async def _check(node: FleetNode) -> Dict[str, Any]:
            res = await ssh_executor.test_connection(node)
            if res.get("reachable"):
                self.update_node_status(node.name, "online", res.get("specs"))
            else:
                self.update_node_status(node.name, "unreachable")
            return {
                "name": node.name,
                "host": node.host,
                "port": node.port,
                "user": node.user,
                "reachable": res.get("reachable", False),
                "latency_ms": res.get("latency_ms", 0.0),
                "os_type": res.get("os_type", "unknown"),
                "error": res.get("error"),
            }

        tasks = [_check(node) for node in targets]
        return await asyncio.gather(*tasks)

    async def broadcast_command(
        self,
        command: str,
        tag: Optional[str] = None,
        timeout: int = 60,
    ) -> List[Any]:
        """Concurrently broadcasts a shell command across all matching fleet nodes."""
        import asyncio
        from cord.fleet.ssh_executor import ssh_executor

        targets = self.list_nodes(tag=tag)
        if not targets:
            return []

        tasks = [
            ssh_executor.execute(node, command, timeout=timeout)
            for node in targets
        ]
        return await asyncio.gather(*tasks)

    async def scan_local_subnet(
        self,
        subnet_prefix: Optional[str] = None,
        port: int = 22,
        timeout_s: float = 0.4,
        max_hosts: int = 254,
    ) -> List[Dict[str, Any]]:
        """
        Fast asynchronous scan for active SSH devices on the local network.
        If subnet_prefix is not provided, auto-detects from the local primary IP.
        """
        import asyncio
        import socket

        prefix = subnet_prefix
        if not prefix:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                parts = local_ip.split(".")
                if len(parts) == 4 and parts[0] != "127":
                    prefix = f"{parts[0]}.{parts[1]}.{parts[2]}."
            except Exception:
                pass

        if not prefix:
            prefix = "192.168.1."

        if not prefix.endswith("."):
            prefix += "."

        sem = asyncio.Semaphore(50)
        found: List[Dict[str, Any]] = []

        async def _probe(ip: str):
            async with sem:
                try:
                    conn = asyncio.open_connection(ip, port)
                    _, writer = await asyncio.wait_for(conn, timeout=timeout_s)
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    found.append({"host": ip, "port": port, "status": "open"})
                except Exception:
                    pass

        tasks = [_probe(f"{prefix}{i}") for i in range(1, min(max_hosts + 1, 255))]
        await asyncio.gather(*tasks)
        return sorted(found, key=lambda x: x["host"])


fleet_mgr = FleetManager()

