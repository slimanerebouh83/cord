"""
CORD Subagents - Swarm Computer Control Arbiter & Negotiation Protocol
Provides distributed mutual exclusion (Mutex), cooperative lease handovers,
and multi-agent plan deliberation for physical desktop automation (mouse, screen, keyboard).
"""

from __future__ import annotations
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from cord.subagents.message_bus import swarm_bus
from cord.subagents.deliberation import swarm_deliberation


@dataclass
class ComputerControlLease:
    lease_id: str
    holder_id: str
    purpose: str
    target_app: str = "Desktop"
    planned_steps: List[Dict[str, Any]] = field(default_factory=list)
    granted_at: float = field(default_factory=time.time)
    duration_sec: float = 30.0
    expires_at: float = field(default_factory=time.time)
    status: str = "active"  # "active", "released", "expired", "preempted"
    approvals: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.status == "active" and time.time() < self.expires_at

    @property
    def remaining_sec(self) -> float:
        return max(0.0, self.expires_at - time.time())


class ComputerControlArbiter:
    """
    Coordinates multi-agent desktop use through cooperative locks,
    deliberative plan proposals, and peer negotiation.
    """

    def __init__(self):
        self.active_lease: Optional[ComputerControlLease] = None
        self.wait_queue: List[Dict[str, Any]] = []
        self.history: List[Dict[str, Any]] = []

    @property
    def waiting_queue(self) -> List[Dict[str, Any]]:
        return self.wait_queue

    def request_lease(
        self,
        agent_id: str,
        purpose: str,
        planned_steps: Optional[List[Dict[str, Any]]] = None,
        target_app: str = "Desktop",
        duration_sec: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Requests exclusive control over mouse and keyboard.
        If free, grants lease immediately. If busy, enqueues request and dispatches a negotiation event.
        """
        now = time.time()
        steps = planned_steps or []
        dur = max(5.0, min(float(duration_sec), 120.0))  # Between 5s and 120s max

        # Check if current lease expired
        if self.active_lease and not self.active_lease.is_valid:
            self.active_lease.status = "expired"
            self.history.append({
                "lease_id": self.active_lease.lease_id,
                "holder": self.active_lease.holder_id,
                "purpose": self.active_lease.purpose,
                "status": "expired",
                "ended_at": now,
            })
            self.active_lease = None

        # 1. No active lease: Grant immediately
        if self.active_lease is None:
            lease_id = f"lease_{uuid.uuid4().hex[:6]}"
            lease = ComputerControlLease(
                lease_id=lease_id,
                holder_id=agent_id,
                purpose=purpose.strip(),
                target_app=target_app.strip(),
                planned_steps=steps,
                granted_at=now,
                duration_sec=dur,
                expires_at=now + dur,
                status="active",
            )
            self.active_lease = lease

            # Broadcast on swarm bus
            swarm_bus.broadcast(
                sender_id=agent_id,
                content=f"🎮 [Computer Control Granted] Agent @{agent_id} acquired lease '{lease_id}' for {dur:.0f}s. Purpose: {purpose}",
                metadata={"event": "computer_lease_acquired", "lease_id": lease_id, "agent": agent_id},
            )

            return {
                "success": True,
                "granted": True,
                "lease_id": lease_id,
                "holder": agent_id,
                "purpose": purpose,
                "duration_sec": dur,
                "expires_at": lease.expires_at,
                "message": f"Computer control lease granted to @{agent_id} for {dur:.0f} seconds.",
            }

        # 2. Same agent re-requesting: Extend lease
        if self.active_lease.holder_id == agent_id:
            self.active_lease.expires_at = now + dur
            self.active_lease.purpose = purpose
            if steps:
                self.active_lease.planned_steps = steps
            return {
                "success": True,
                "granted": True,
                "lease_id": self.active_lease.lease_id,
                "holder": agent_id,
                "extended_for_sec": dur,
                "expires_at": self.active_lease.expires_at,
                "message": f"Computer control lease extended for @{agent_id} by {dur:.0f}s.",
            }

        # 3. Another agent currently holds control: Add to negotiation queue
        queue_entry = {
            "agent_id": agent_id,
            "purpose": purpose,
            "target_app": target_app,
            "duration_sec": dur,
            "planned_steps": steps,
            "requested_at": now,
        }
        # Avoid duplicate requests from same agent
        self.wait_queue = [q for q in self.wait_queue if q["agent_id"] != agent_id]
        self.wait_queue.append(queue_entry)
        pos = len(self.wait_queue)

        # Send negotiation ping to current holder
        current_holder = self.active_lease.holder_id
        swarm_bus.send(
            sender_id=agent_id,
            recipient_id=current_holder,
            content=f"🤝 Negotiation Request: Agent @{agent_id} requests computer control for: '{purpose}' (queue position #{pos}). Please complete your current batch and call 'release_computer_control'.",
            metadata={"event": "computer_control_negotiate", "requester": agent_id},
        )

        return {
            "success": True,
            "granted": False,
            "status": "busy",
            "current_holder": current_holder,
            "current_purpose": self.active_lease.purpose,
            "remaining_sec": round(self.active_lease.remaining_sec, 1),
            "queue_position": pos,
            "message": (
                f"Computer control is currently locked by @{current_holder} for '{self.active_lease.purpose}' "
                f"({self.active_lease.remaining_sec:.1f}s remaining). You are queued at position #{pos}. "
                "A negotiation request was sent to the active holder."
            ),
        }

    def propose_plan_for_consensus(
        self,
        agent_id: str,
        title: str,
        planned_steps: List[Any],
        explanation: str,
    ) -> Dict[str, Any]:
        """
        Creates a peer deliberation proposal on the swarm bus for a multi-step desktop automation plan.
        Peers vote on whether to approve the plan and hand over control.
        """
        proposal_title = f"Desktop Control Plan: {title} (by @{agent_id})"
        description = (
            f"Agent @{agent_id} proposes the following desktop automation strategy:\n\n"
            f"**Objective & Rationale:**\n{explanation}\n\n"
            f"**Planned Action Steps ({len(planned_steps)} steps):**\n"
        )
        for i, s in enumerate(planned_steps, 1):
            if isinstance(s, dict):
                act_name = s.get("action", "unknown")
                desc = ", ".join(f"{k}={v}" for k, v in s.items() if k != "action")
                description += f"  {i}. {act_name} ({desc})\n"
            else:
                description += f"  {i}. {s}\n"

        options = [
            "Approve Plan & Grant Control",
            "Request Modification / Safer Sequence",
            "Decline Plan",
        ]

        prop = swarm_deliberation.create_proposal(
            creator_id=agent_id,
            title=proposal_title,
            description=description,
            options=options,
        )

        # Notify peers
        swarm_bus.broadcast(
            sender_id=agent_id,
            content=f"🗳️ [Desktop Plan Deliberation] @{agent_id} opened proposal '{prop.proposal_id}' for desktop automation: {title}. Cast your vote via subagent_vote.",
            metadata={"event": "desktop_plan_proposal", "proposal_id": prop.proposal_id},
        )

        return {
            "success": True,
            "status": "deliberation_opened",
            "topic_id": prop.proposal_id,
            "proposal_id": prop.proposal_id,
            "title": proposal_title,
            "options": options,
            "message": f"Desktop automation plan submitted for peer deliberation. Proposal ID: {prop.proposal_id}.",
        }

    def release_lease(self, agent_id: str) -> Dict[str, Any]:
        """
        Releases the active lease. Automatically promotes the next agent in the negotiation queue.
        """
        # Super-user override: "main", "user", or current holder can release
        if not self.active_lease:
            return {"success": True, "message": "No active computer lease to release."}

        is_authorized = (
            agent_id in ("main", "user", "root")
            or self.active_lease.holder_id == agent_id
            or not self.active_lease.is_valid
        )

        if not is_authorized:
            return {
                "success": False,
                "error": f"Cannot release lease owned by @{self.active_lease.holder_id}. Only the holder or main supervisor can release it.",
            }

        prev_holder = self.active_lease.holder_id
        self.active_lease.status = "released"
        self.history.append({
            "lease_id": self.active_lease.lease_id,
            "holder": prev_holder,
            "purpose": self.active_lease.purpose,
            "status": "released",
            "released_by": agent_id,
            "ended_at": time.time(),
        })
        self.active_lease = None

        # Failsafe hardware reset: release all modifier keys
        try:
            from cord.tools.computer.computer_keyboard import release_all_modifiers
            release_all_modifiers()
        except Exception:
            pass

        promoted_msg = ""
        # 4. Check if there are queued agents waiting: Promote next in line!
        if self.wait_queue:
            next_req = self.wait_queue.pop(0)
            next_agent = next_req["agent_id"]
            res = self.request_lease(
                agent_id=next_agent,
                purpose=next_req["purpose"],
                planned_steps=next_req.get("planned_steps"),
                target_app=next_req.get("target_app", "Desktop"),
                duration_sec=next_req.get("duration_sec", 30.0),
            )
            promoted_msg = f" Control immediately handed over to next queued agent @{next_agent}."

        swarm_bus.broadcast(
            sender_id=agent_id,
            content=f"🔓 [Computer Control Released] Control released by @{agent_id}.{promoted_msg}",
            metadata={"event": "computer_lease_released", "prev_holder": prev_holder},
        )

        handed_to = self.active_lease.holder_id if self.active_lease else None
        return {
            "success": True,
            "released_by": agent_id,
            "previous_holder": prev_holder,
            "promoted_next": bool(promoted_msg),
            "handed_over_to": handed_to,
            "message": f"Successfully released computer control lease.{promoted_msg}",
        }

    def can_execute(self, agent_id: Optional[str]) -> Tuple[bool, str]:
        """
        Validates whether the specified agent is authorized to execute physical desktop actions.
        """
        # Main supervisory agent / direct CLI user always has master control
        if not agent_id or agent_id in ("main", "user", "root", "supervisor"):
            return True, "Supervisor master access granted."

        # Check if active lease exists and is valid
        if not self.active_lease or not self.active_lease.is_valid:
            # Auto-grant temporary 30s lease if queue is empty
            self.request_lease(agent_id=agent_id, purpose="Ad-hoc desktop automation action", duration_sec=30.0)
            return True, f"Auto-granted control lease to @{agent_id}."

        if self.active_lease.holder_id == agent_id:
            return True, "Active lease holder."

        # Locked by another subagent!
        return False, (
            f"Computer control is currently locked by @{self.active_lease.holder_id} "
            f"for '{self.active_lease.purpose}' ({self.active_lease.remaining_sec:.1f}s remaining). "
            "Please call 'request_computer_control' or 'propose_computer_plan' to negotiate with peers."
        )

    def get_status(self) -> Dict[str, Any]:
        """Returns full telemetry on computer control state, active lease, and negotiation queue."""
        active_info = None
        if self.active_lease and self.active_lease.is_valid:
            active_info = {
                "lease_id": self.active_lease.lease_id,
                "holder": self.active_lease.holder_id,
                "purpose": self.active_lease.purpose,
                "target_app": self.active_lease.target_app,
                "remaining_seconds": round(self.active_lease.remaining_sec, 1),
                "planned_steps_count": len(self.active_lease.planned_steps),
            }

        return {
            "locked": active_info is not None,
            "active_lease": active_info,
            "queue_length": len(self.wait_queue),
            "queued_agents": [
                {"agent_id": q["agent_id"], "purpose": q["purpose"], "duration_sec": q["duration_sec"]}
                for q in self.wait_queue
            ],
            "recent_leases": self.history[-5:],
        }


# Global Singleton Arbiter
computer_arbiter = ComputerControlArbiter()
