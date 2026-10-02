"""
CORD Tools - Computer Control Negotiation & Mutual Exclusion Tools
Equips autonomous subagents with tools to request exclusive desktop leases,
propose automation plans for peer voting, and release control cleanly.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional

from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.subagents.computer_arbiter import computer_arbiter


class RequestComputerControlTool(BaseTool):
    name = "request_computer_control"
    description = (
        "Request exclusive access/lease to control the physical computer (mouse, screen, keyboard). "
        "If another subagent is currently operating the desktop, this adds you to the negotiation queue "
        "and notifies the active holder to prepare for a handover."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "purpose": {
                "type": "string",
                "description": "Clear reason why you need desktop control (e.g. 'Fill web form in Chrome', 'Launch Notepad and verify text output').",
            },
            "planned_steps": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Optional list of action steps you intend to perform.",
            },
            "target_app": {
                "type": "string",
                "description": "Target application name or window title (e.g. 'Chrome', 'Notepad', 'Explorer').",
                "default": "Desktop",
            },
            "duration_sec": {
                "type": "integer",
                "description": "Estimated duration in seconds required (5 to 120, default: 30).",
                "default": 30,
            },
            "agent_id": {
                "type": "string",
                "description": "Your agent identifier (e.g. 'operator', 'tester_1'). If omitted, defaults to caller identity.",
            },
        },
        "required": ["purpose"],
    }

    async def execute(
        self,
        purpose: str,
        planned_steps: Optional[List[Dict[str, Any]]] = None,
        target_app: str = "Desktop",
        duration_sec: int = 30,
        agent_id: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        caller = agent_id or kwargs.get("_agent_name") or "subagent_operator"
        res = computer_arbiter.request_lease(
            agent_id=caller,
            purpose=purpose,
            planned_steps=planned_steps,
            target_app=target_app,
            duration_sec=float(duration_sec),
        )

        if res.get("granted"):
            return ToolResult(
                success=True,
                output=(
                    f"✓ Computer control lease GRANTED to @{caller} for {duration_sec}s.\n"
                    f"Lease ID: {res['lease_id']}\n"
                    f"Target App: {target_app}\n"
                    f"You now have exclusive access to 'computer_act', 'computer_mouse', and 'computer_keyboard'. "
                    "Remember to call 'release_computer_control' when finished!"
                ),
            )
        else:
            return ToolResult(
                success=True,
                output=(
                    f"⏳ Computer control is currently locked by @{res['current_holder']} "
                    f"for: '{res['current_purpose']}' ({res['remaining_sec']}s remaining).\n"
                    f"Queue position: #{res['queue_position']}.\n"
                    "A negotiation request was sent. Please wait or collaborate with peer subagents."
                ),
            )


class ReleaseComputerControlTool(BaseTool):
    name = "release_computer_control"
    description = (
        "Release your active computer control lease and reset hardware modifiers, "
        "allowing peer subagents in the negotiation queue to take control of the desktop."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "Your agent identifier. If omitted, uses current caller identity.",
            },
        },
    }

    async def execute(self, agent_id: Optional[str] = None, **kwargs) -> ToolResult:
        caller = agent_id or kwargs.get("_agent_name") or "subagent_operator"
        res = computer_arbiter.release_lease(agent_id=caller)
        if res.get("success"):
            return ToolResult(success=True, output=f"✓ {res['message']}")
        return ToolResult(success=False, output="", error=res.get("error", "Failed to release lease."))


class ProposeComputerPlanTool(BaseTool):
    name = "propose_computer_plan"
    description = (
        "Submit a detailed desktop automation plan for peer deliberation and voting. "
        "Other subagents inspect your proposed steps, provide feedback, and cast consensus votes "
        "before physical actions are performed on the screen."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title of the proposed plan (e.g. 'End-to-End Search in Chrome').",
            },
            "planned_steps": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Ordered list of action dictionaries (e.g. [{'action': 'scroll_down'}, {'action': 'click', 'x': 500, 'y': 300}, ...]).",
            },
            "explanation": {
                "type": "string",
                "description": "Rationale and expected outcome of the automation sequence.",
            },
            "agent_id": {
                "type": "string",
                "description": "Your agent identifier.",
            },
        },
        "required": ["title", "planned_steps", "explanation"],
    }

    async def execute(
        self,
        title: str,
        planned_steps: Optional[List[Any]] = None,
        explanation: str = "",
        agent_id: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        caller = agent_id or kwargs.get("_agent_name") or "subagent_operator"
        res = computer_arbiter.propose_plan_for_consensus(
            agent_id=caller,
            title=title,
            planned_steps=planned_steps or [],
            explanation=explanation or f"Execution of planned desktop action: {title}",
        )
        return ToolResult(
            success=True,
            output=(
                f"🗳️ {res['message']}\n"
                f"Proposal: {res['title']}\n"
                f"Voting Options: {', '.join(res['options'])}\n"
                "Peer subagents can now review your strategy and cast their votes via 'subagent_vote'."
            ),
        )


class GetComputerArbiterStatusTool(BaseTool):
    name = "get_computer_arbiter_status"
    description = "Inspect the current computer control state: active lease holder, remaining time, and queued subagents."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> ToolResult:
        status = computer_arbiter.get_status()
        active = status.get("active_lease")
        if active:
            lines = [
                f"🔒 Status: LOCKED by @{active['holder']}",
                f"  • Purpose: {active['purpose']}",
                f"  • Target: {active['target_app']}",
                f"  • Remaining: {active['remaining_seconds']}s",
                f"  • Planned steps: {active['planned_steps_count']}",
            ]
        else:
            lines = ["🔓 Status: UNLOCKED (Desktop is currently free for any agent to request)."]

        q_len = status.get("queue_length", 0)
        lines.append(f"📋 Negotiation Queue ({q_len} waiting):")
        if q_len > 0:
            for idx, q in enumerate(status.get("queued_agents", []), 1):
                lines.append(f"  #{idx}. @{q['agent_id']} — '{q['purpose']}' ({q['duration_sec']}s)")
        else:
            lines.append("  (Queue is empty)")

        return ToolResult(success=True, output="\n".join(lines))
