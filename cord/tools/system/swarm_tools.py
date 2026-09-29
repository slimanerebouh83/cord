"""CORD Tools - Swarm Mesh Communication & Autonomous Dispatch Tools"""
from __future__ import annotations
import json
from typing import Dict, Any, List, Optional

from cord.tools.base import BaseTool, ToolResult, PermissionLevel, RiskLevel
from cord.subagents.message_bus import swarm_bus


class SubagentSendMessageTool(BaseTool):
    """Sends a direct message to a peer subagent in the swarm."""

    name = "subagent_send_message"
    description = "Send a direct peer-to-peer message to another subagent in the active swarm."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sender_id": {"type": "string", "description": "Your own subagent name/ID"},
                "recipient_id": {"type": "string", "description": "Target subagent name/ID"},
                "message": {"type": "string", "description": "Content of the message"},
            },
            "required": ["recipient_id", "message"],
        }

    async def execute(self, recipient_id: str, message: str, sender_id: str = "agent", **kwargs: Any) -> ToolResult:
        try:
            swarm_bus.send(sender_id=sender_id, recipient_id=recipient_id, content=message)
            return ToolResult(
                output=f"✔ Message delivered to subagent '{recipient_id}' from '{sender_id}'.",
                success=True,
            )
        except Exception as e:
            return ToolResult(output=f"Failed to deliver message: {e}", success=False)


class SubagentBroadcastTool(BaseTool):
    """Broadcasts a message to all subagents in the swarm."""

    name = "subagent_broadcast"
    description = "Broadcast a message to all other active subagents in the swarm."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sender_id": {"type": "string", "description": "Your own subagent name/ID"},
                "message": {"type": "string", "description": "Message to broadcast"},
            },
            "required": ["message"],
        }

    async def execute(self, message: str, sender_id: str = "agent", **kwargs: Any) -> ToolResult:
        try:
            swarm_bus.broadcast(sender_id=sender_id, content=message)
            return ToolResult(
                output=f"✔ Broadcast message published across swarm by '{sender_id}'.",
                success=True,
            )
        except Exception as e:
            return ToolResult(output=f"Failed to broadcast message: {e}", success=False)


class SubagentReadInboxTool(BaseTool):
    """Reads incoming messages for a subagent."""

    name = "subagent_read_inbox"
    description = "Check unread messages received from other subagents or the swarm coordinator."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Your subagent ID to read messages for"},
            },
            "required": ["agent_id"],
        }

    async def execute(self, agent_id: str, **kwargs: Any) -> ToolResult:
        try:
            messages = swarm_bus.get_inbox(agent_id=agent_id, unread_only=True)
            if not messages:
                return ToolResult(output=f"Inbox empty. No new messages for '{agent_id}'.", success=True)
            return ToolResult(
                output=f"Retrieved {len(messages)} message(s):\n" + json.dumps(messages, indent=2, ensure_ascii=False),
                success=True,
            )
        except Exception as e:
            return ToolResult(output=f"Failed to read inbox: {e}", success=False)


class SwarmDispatchTool(BaseTool):
    """Dispatches a swarm of subagents to execute decomposed tasks in parallel."""

    name = "swarm_dispatch"
    description = (
        "Decompose a high-level goal into concurrent subagent tasks. "
        "Each task gets dedicated instructions, roles, and tool permissions, "
        "running concurrently with support for up to 1000 subagent workers."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM

    def __init__(self, subagent_manager: Optional[Any] = None):
        super().__init__()
        self.subagent_manager = subagent_manager

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Overall objective or problem statement"},
                "tasks": {
                    "type": "array",
                    "description": "List of distinct tasks with custom prompts and roles",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Unique name for the subagent worker"},
                            "role": {"type": "string", "description": "Role (e.g. researcher, coder, tester, reviewer, or custom)"},
                            "prompt": {"type": "string", "description": "Detailed, self-contained prompt and instructions for this subagent"},
                            "tools": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of specific tool names allowed for this subagent",
                            },
                        },
                        "required": ["role", "prompt"],
                    },
                },
                "max_concurrency": {
                    "type": "integer",
                    "description": "Maximum concurrent subagents to run simultaneously (default 50)",
                },
            },
            "required": ["goal", "tasks"],
        }

    async def execute(self, goal: str, tasks: List[Dict[str, Any]], max_concurrency: int = 50, **kwargs: Any) -> ToolResult:
        if not self.subagent_manager:
            return ToolResult(output="Error: Subagent manager not initialized on SwarmDispatchTool.", success=False)

        try:
            res = await self.subagent_manager.run_swarm(
                goal=goal,
                tasks=tasks,
                max_concurrency=max_concurrency,
            )
            return ToolResult(
                output=json.dumps(res, indent=2, ensure_ascii=False),
                success=True,
            )
        except Exception as e:
            return ToolResult(output=f"Swarm execution failed: {e}", success=False)


class SubagentShareSkillTool(BaseTool):
    """Shares/teaches a skill directly to peer subagents and registers it into global persistent skills."""

    name = "subagent_share_skill"
    description = "Share/teach a skill directly to other subagents in the swarm, and permanently register it in ~/.cord/skills/."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM

    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Unique identifier for the skill"},
            "description": {"type": "string", "description": "1-line summary of what the skill does"},
            "instructions": {"type": "string", "description": "Comprehensive instructions and best practices"},
            "recipient_id": {
                "type": "string",
                "description": "Target subagent ID or '*' to share with the entire swarm",
                "default": "*",
            },
            "sender_id": {
                "type": "string",
                "description": "Your own subagent name/ID",
                "default": "agent",
            },
        },
        "required": ["name", "description", "instructions"],
    }

    async def execute(
        self,
        name: str,
        description: str,
        instructions: str,
        recipient_id: str = "*",
        sender_id: str = "agent",
        **kwargs: Any,
    ) -> ToolResult:
        import re
        from pathlib import Path
        try:
            clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "", name.strip().lower().replace(" ", "-"))
            if not clean_name:
                return ToolResult(output="Invalid skill name.", success=False)

            # 1. Save to global persistent store ~/.cord/skills/<clean_name>/SKILL.md
            global_dir = Path.home() / ".cord" / "skills" / clean_name
            global_dir.mkdir(parents=True, exist_ok=True)
            content = f"---\nname: {clean_name}\ndescription: {description.strip()}\n---\n\n{instructions.strip()}\n"
            (global_dir / "SKILL.md").write_text(content, encoding="utf-8")

            # 2. Transmit to peer(s) over swarm message bus
            msg_payload = f"📚 SKILL SHARED by '{sender_id}': `{clean_name}`\nDescription: {description}\n\nInstructions:\n{instructions}"
            if recipient_id == "*":
                swarm_bus.broadcast(sender_id=sender_id, content=msg_payload, metadata={"type": "skill_share", "skill": clean_name})
            else:
                swarm_bus.send(sender_id=sender_id, recipient_id=recipient_id, content=msg_payload, metadata={"type": "skill_share", "skill": clean_name})

            return ToolResult(
                output=(
                    f"✔ Skill '{clean_name}' successfully shared with '{recipient_id}' by '{sender_id}'\n"
                    f"Permanently registered in global skills: {global_dir / 'SKILL.md'}"
                ),
                success=True,
            )
        except Exception as e:
            return ToolResult(output=f"Failed to share skill: {e}", success=False)


class SubagentListPeersTool(BaseTool):
    """Discovers peer subagents in the swarm, their active roles, domain knowledge, and status."""

    name = "subagent_list_peers"
    description = "Discover all active and provisioned subagents in the swarm, inspect their roles, capabilities, and knowledge."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW

    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            active_peers = list(swarm_bus._inboxes.keys())
            channels = {ch: list(agents) for ch, agents in swarm_bus._channels.items()}
            total_capacity = swarm_bus.agent_count

            lines = [
                f"Swarm Peer Roster (Capacity: {total_capacity:,} agents):",
                f"Active Interconnected Agents: {len(active_peers)}",
            ]
            for peer in active_peers[:50]:
                lines.append(f"- **{peer}** [Status: ACTIVE | Inbox: {len(swarm_bus._inboxes[peer])} messages]")
            if len(active_peers) > 50:
                lines.append(f"... and {len(active_peers) - 50} more active agents.")

            if channels:
                lines.append("\nActive Squad Channels:")
                for ch, members in channels.items():
                    lines.append(f"- `#{ch}`: {len(members)} agents ({', '.join(list(members)[:5])})")

            return ToolResult(output="\n".join(lines), success=True)
        except Exception as e:
            return ToolResult(output=f"Failed to list peers: {e}", success=False)
