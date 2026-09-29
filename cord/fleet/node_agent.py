"""
CORD Fleet - Dedicated Remote Node Subagent & Recursive Subagent Hierarchy
Enables autonomous per-machine agents that can orchestrate tasks remotely and spawn child subagents.
"""

from __future__ import annotations
import asyncio
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from cord.fleet.models import FleetNode
from cord.fleet.ssh_executor import ssh_executor, SSHCommandResult
from cord.fleet.mesh_bus import encrypted_mesh
from cord.core.config import CordConfig
from cord.tools.base import BaseTool, ToolResult


@dataclass
class NodeAgentResult:
    node_name: str
    agent_id: str
    mission: str
    success: bool
    summary: str
    actions_taken: List[str]
    child_subagents_spawned: int


class RemoteNodeExecTool(BaseTool):
    """Tool allowing a NodeSubagent to execute commands on its assigned remote machine."""
    name = "node_exec"
    description = "Executes a shell command on this assigned remote machine."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute on the remote machine",
            },
            "timeout": {
                "type": "number",
                "description": "Timeout in seconds (default: 60)",
                "default": 60,
            },
        },
        "required": ["command"],
    }

    def __init__(self, node: FleetNode):
        super().__init__()
        self.node = node

    async def execute(self, command: str, timeout: float = 60.0, **kwargs) -> ToolResult:
        res = await ssh_executor.execute(self.node, command, timeout=timeout)
        return ToolResult(
            success=res.success,
            output=res.summary(),
        )


class RemoteNodeUploadTool(BaseTool):
    """Tool allowing a NodeSubagent to upload files to its assigned remote machine."""
    name = "node_upload"
    description = "Uploads a local file or directory to this assigned remote machine."
    parameters = {
        "type": "object",
        "properties": {
            "local_path": {"type": "string", "description": "Path on the local machine"},
            "remote_path": {"type": "string", "description": "Target destination path on the remote machine"},
        },
        "required": ["local_path", "remote_path"],
    }

    def __init__(self, node: FleetNode):
        super().__init__()
        self.node = node

    async def execute(self, local_path: str, remote_path: str, **kwargs) -> ToolResult:
        res = await ssh_executor.upload(self.node, local_path, remote_path)
        return ToolResult(
            success=res["success"],
            output=f"Upload to {self.node.name}:{remote_path} -> {'SUCCESS' if res['success'] else 'FAILED'}: {res.get('error') or 'Uploaded cleanly'}",
        )


class RemoteNodeDownloadTool(BaseTool):
    """Tool allowing a NodeSubagent to download files from its assigned remote machine."""
    name = "node_download"
    description = "Downloads a file or directory from this assigned remote machine to the local system."
    parameters = {
        "type": "object",
        "properties": {
            "remote_path": {"type": "string", "description": "Source path on the remote machine"},
            "local_path": {"type": "string", "description": "Destination path on the local machine"},
        },
        "required": ["remote_path", "local_path"],
    }

    def __init__(self, node: FleetNode):
        super().__init__()
        self.node = node

    async def execute(self, remote_path: str, local_path: str, **kwargs) -> ToolResult:
        res = await ssh_executor.download(self.node, remote_path, local_path)
        return ToolResult(
            success=res["success"],
            output=f"Download from {self.node.name}:{remote_path} -> {'SUCCESS' if res['success'] else 'FAILED'}: {res.get('error') or 'Downloaded cleanly'}",
        )


class NodeMeshSendTool(BaseTool):
    """Tool allowing a NodeSubagent to send encrypted messages over the mesh bus."""
    name = "mesh_send"
    description = "Sends an authenticated, encrypted message to another agent or broadcasts across the fleet."
    parameters = {
        "type": "object",
        "properties": {
            "recipient_agent": {"type": "string", "description": "Target agent ID or '*' for broadcast"},
            "message": {"type": "string", "description": "Message content to securely send"},
        },
        "required": ["recipient_agent", "message"],
    }

    def __init__(self, agent_id: str, node: FleetNode):
        super().__init__()
        self.agent_id = agent_id
        self.node = node

    async def execute(self, recipient_agent: str, message: str, **kwargs) -> ToolResult:
        if recipient_agent == "*":
            msgs = encrypted_mesh.broadcast_encrypted(
                sender_agent=self.agent_id,
                sender_node=self.node.name,
                payload=message,
            )
            return ToolResult(
                success=True,
                output=f"Broadcasted encrypted message to {len(msgs)} registered peer agents.",
            )
        else:
            msg = encrypted_mesh.send_encrypted(
                sender_agent=self.agent_id,
                sender_node=self.node.name,
                recipient_agent=recipient_agent,
                recipient_node="*",
                payload=message,
            )
            return ToolResult(
                success=True,
                output=f"Sent encrypted message to {recipient_agent} (ID: {msg.message_id}).",
            )


class NodeMeshReadTool(BaseTool):
    """Tool allowing a NodeSubagent to read and decrypt incoming mesh messages."""
    name = "mesh_read"
    description = "Reads and decrypts all unread messages received from other agents in the encrypted mesh."
    parameters = {"type": "object", "properties": {}}

    def __init__(self, agent_id: str):
        super().__init__()
        self.agent_id = agent_id

    async def execute(self, **kwargs) -> ToolResult:
        inbox = encrypted_mesh.read_inbox(self.agent_id)
        if not inbox:
            return ToolResult(success=True, output="No new encrypted messages in inbox.")
        lines = [f"- From: {m['from_agent']}@{m.get('from_node', '?')}: {m['content']}" for m in inbox]
        return ToolResult(success=True, output=f"Received {len(inbox)} messages:\n" + "\n".join(lines))


class FleetNodeAgent:
    """
    Autonomous subagent deployed to oversee and operate on a specific remote machine.
    Capable of spawning child subagents to execute sub-missions in parallel.
    """

    def __init__(
        self,
        node: FleetNode,
        mission: str,
        config: CordConfig,
        agent_id: Optional[str] = None,
        parent_agent_id: Optional[str] = None,
    ):
        self.node = node
        self.mission = mission
        self.config = config
        self.agent_id = agent_id or f"node-agent:{node.name}-{uuid.uuid4().hex[:4]}"
        self.parent_agent_id = parent_agent_id
        self.child_agents: List[FleetNodeAgent] = []
        self.actions_log: List[str] = []

        # Register on encrypted mesh
        encrypted_mesh.register_agent(self.agent_id)

    def _build_tools(self) -> List[BaseTool]:
        """Builds tools available to this node subagent."""
        tools: List[BaseTool] = [
            RemoteNodeExecTool(self.node),
            RemoteNodeUploadTool(self.node),
            RemoteNodeDownloadTool(self.node),
            NodeMeshSendTool(self.agent_id, self.node),
            NodeMeshReadTool(self.agent_id),
        ]
        return tools

    async def spawn_child_subagent(self, child_mission: str, child_role: str = "worker") -> NodeAgentResult:
        """Spawns a child subagent tied to this node to execute a sub-task."""
        child_id = f"{self.agent_id}.child-{child_role}-{uuid.uuid4().hex[:4]}"
        child = FleetNodeAgent(
            node=self.node,
            mission=child_mission,
            config=self.config,
            agent_id=child_id,
            parent_agent_id=self.agent_id,
        )
        self.child_agents.append(child)
        return await child.run()

    async def run(self, max_steps: int = 8) -> NodeAgentResult:
        """
        Executes the autonomous mission loop on the remote node.
        """
        from cord.subagents.base_subagent import Subagent

        tools = self._build_tools()
        system_prompt = (
            f"You are dedicated Fleet Node Subagent '{self.agent_id}' controlling machine '{self.node.name}' "
            f"({self.node.os_type} at {self.node.host}:{self.node.port}).\n"
            f"Your mission: {self.mission}\n"
            f"You have direct remote execution tools (node_exec, node_upload, node_download) and encrypted mesh tools.\n"
            f"Coordinate, inspect system state, execute needed changes, and verify success thoroughly."
        )

        subagent_instance = Subagent(
            name=self.agent_id,
            role=f"node-controller:{self.node.name}",
            system_prompt=system_prompt,
            config=self.config,
            tools=tools,
            max_iterations=max_steps,
        )

        try:
            res = await subagent_instance.run(self.mission)
            self.actions_log.append(f"Mission: {self.mission} -> Success={res.success}")
            return NodeAgentResult(
                node_name=self.node.name,
                agent_id=self.agent_id,
                mission=self.mission,
                success=res.success,
                summary=res.summary,
                actions_taken=self.actions_log,
                child_subagents_spawned=len(self.child_agents),
            )
        finally:
            encrypted_mesh.unregister_agent(self.agent_id)
