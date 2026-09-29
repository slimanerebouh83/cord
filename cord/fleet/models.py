"""
CORD Fleet - Multi-Machine SSH Node Models
Defines data structures for remote machines, OS profiles, credentials, and telemetry.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class FleetNode:
    """Represents a remote machine registered in the CORD fleet."""
    name: str
    host: str
    port: int = 22
    user: str = "root"
    key_path: Optional[str] = None
    password: Optional[str] = None
    os_type: str = "linux"  # "linux", "darwin", "windows", "unknown"
    tags: List[str] = field(default_factory=list)
    description: str = ""
    status: str = "offline"  # "online", "offline", "unreachable", "configured"
    last_seen: float = 0.0
    system_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FleetNode":
        return cls(
            name=data.get("name", "unnamed"),
            host=data.get("host", "127.0.0.1"),
            port=int(data.get("port", 22)),
            user=data.get("user", "root"),
            key_path=data.get("key_path"),
            password=data.get("password"),
            os_type=data.get("os_type", "linux"),
            tags=list(data.get("tags", [])),
            description=data.get("description", ""),
            status=data.get("status", "offline"),
            last_seen=float(data.get("last_seen", 0.0)),
            system_info=dict(data.get("system_info", {})),
        )

    def matches_tag(self, tag: str) -> bool:
        """Checks if the node has a specific tag or name alias."""
        clean = tag.lower().strip()
        if clean == self.name.lower():
            return True
        return clean in [t.lower() for t in self.tags]
