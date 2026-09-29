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


fleet_mgr = FleetManager()
