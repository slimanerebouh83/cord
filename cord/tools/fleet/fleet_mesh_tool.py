"""
CORD Tools - Encrypted Fleet Mesh Messaging Tool
Allows agents to securely communicate across machines using authenticated end-to-end encryption.
"""

from __future__ import annotations
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.fleet.mesh_bus import encrypted_mesh


class FleetMeshTool(BaseTool):
    name = "fleet_mesh_send"
    description = (
        "Sends an authenticated, military-grade encrypted message across the inter-agent mesh to a target agent "
        "or broadcasts across the entire fleet."
    )
    parameters = {
        "type": "object",
        "properties": {
            "recipient": {
                "type": "string",
                "description": "Target agent ID (e.g. 'node-agent:web-server') or '*' to broadcast to all agents",
            },
            "message": {"type": "string", "description": "Message payload to encrypt and dispatch"},
            "sender_node": {
                "type": "string",
                "description": "Originating node name (default: 'master')",
                "default": "master",
            },
        },
        "required": ["recipient", "message"],
    }

    async def execute(self, recipient: str, message: str, sender_node: str = "master", **kwargs) -> ToolResult:
        if recipient == "*":
            msgs = encrypted_mesh.broadcast_encrypted(
                sender_agent="master-agent",
                sender_node=sender_node,
                payload=message,
            )
            return ToolResult(
                success=True,
                output=f"✔ Broadcasted encrypted message to {len(msgs)} registered peer agents across fleet mesh.",
            )
        else:
            msg = encrypted_mesh.send_encrypted(
                sender_agent="master-agent",
                sender_node=sender_node,
                recipient_agent=recipient,
                recipient_node="*",
                payload=message,
            )
            return ToolResult(
                success=True,
                output=f"✔ Dispatched authenticated encrypted message to '{recipient}' (ID: {msg.message_id}).",
            )
