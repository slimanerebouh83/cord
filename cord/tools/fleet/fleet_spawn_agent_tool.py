"""
CORD Tools - Fleet Node Subagent Spawner Tool
Dispatches an autonomous subagent to take complete control of a remote machine with recursive subagent capability.
"""

from __future__ import annotations
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.fleet.manager import fleet_mgr
from cord.fleet.node_agent import FleetNodeAgent
from cord.core.config import CordConfig


class FleetSpawnAgentTool(BaseTool):
    name = "fleet_spawn_agent"
    description = (
        "Deploys an autonomous subagent onto a specific remote fleet machine. "
        "The node subagent can execute commands, manage files, communicate via encrypted mesh, "
        "and recursively spawn child worker subagents on that machine to accomplish complex goals."
    )
    parameters = {
        "type": "object",
        "properties": {
            "node": {"type": "string", "description": "Target remote machine name in the fleet"},
            "mission": {
                "type": "string",
                "description": "High-level mission for the node agent (e.g. 'Setup PostgreSQL database and configure daily backups', 'Organize photo directory into year/month folders')",
            },
            "role": {
                "type": "string",
                "description": "Agent role title (e.g. 'sysadmin', 'media_curator', 'db_architect')",
                "default": "sysadmin",
            },
        },
        "required": ["node", "mission"],
    }

    def __init__(self, config: Optional[CordConfig] = None):
        super().__init__()
        self.config = config or CordConfig()

    async def execute(self, node: str, mission: str, role: str = "sysadmin", model: Optional[str] = None, provider: Optional[str] = None, **kwargs) -> ToolResult:
        target = fleet_mgr.get_node(node)
        if not target:
            return ToolResult(success=False, output=f"Node '{node}' not found in fleet catalog.")

        import copy
        agent_cfg = copy.copy(self.config)
        if model:
            agent_cfg.model = model
        if provider:
            agent_cfg.provider = provider

        agent = FleetNodeAgent(
            node=target,
            mission=mission,
            config=agent_cfg,
        )

        res = await agent.run()
        summary = (
            f"Node Subagent [{res.agent_id}] completed mission on '{res.node_name}'.\n"
            f"Status: {'SUCCESS' if res.success else 'FAILED'}\n"
            f"Child Subagents Spawned: {res.child_subagents_spawned}\n"
            f"Summary:\n{res.summary}"
        )
        return ToolResult(
            success=res.success,
            output=summary,
        )
