"""
CORD Cron - Job Data Models
Defines scheduled automation tasks, recurrence expressions, target nodes, and execution state.
"""

from __future__ import annotations
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class CronJob:
    """Represents a persistent recurring automation task."""
    id: str
    name: str
    schedule_expr: str
    prompt: str
    target_node: str = "local"
    action_type: str = "agent_prompt"  # "agent_prompt", "generate_report", "send_email", "sync_files"
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    last_run: float = 0.0
    next_run: float = 0.0
    run_count: int = 0
    last_status: str = "pending"  # "pending", "running", "success", "failed"
    last_output: str = ""
    recipient_email: Optional[str] = None
    output_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CronJob":
        return cls(
            id=data.get("id", "job-unnamed"),
            name=data.get("name", "Unnamed Task"),
            schedule_expr=data.get("schedule_expr", "every 24h"),
            prompt=data.get("prompt", ""),
            target_node=data.get("target_node", "local"),
            action_type=data.get("action_type", "agent_prompt"),
            enabled=bool(data.get("enabled", True)),
            created_at=float(data.get("created_at", time.time())),
            last_run=float(data.get("last_run", 0.0)),
            next_run=float(data.get("next_run", 0.0)),
            run_count=int(data.get("run_count", 0)),
            last_status=data.get("last_status", "pending"),
            last_output=data.get("last_output", ""),
            recipient_email=data.get("recipient_email"),
            output_path=data.get("output_path"),
        )
