"""
CORD Tools - Swarm Deliberation, Voting, and Consensus Tools.
Allows agents and subagents to propose strategic approaches, debate alternatives,
cast technical votes, and reach collective consensus.
"""

from __future__ import annotations
import json
from typing import Dict, Any, List, Optional

from cord.tools.base import BaseTool, ToolResult, PermissionLevel, RiskLevel
from cord.subagents.deliberation import swarm_deliberation
from cord.subagents.message_bus import swarm_bus


class SubagentProposeTool(BaseTool):
    name = "subagent_propose"
    description = (
        "Post an architectural proposal or strategic decision to the subagent swarm for peer deliberation and voting."
    )
    required_permission = PermissionLevel.SAFE
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Clear title of the proposal (e.g. 'Use FastAPI vs LiteStar for Backend API')",
            },
            "description": {
                "type": "string",
                "description": "Technical background, problem statement, and tradeoffs for peer consideration",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of choices for subagents to vote on (e.g. ['FastAPI', 'LiteStar', 'Django-Ninja'])",
            },
            "creator_id": {
                "type": "string",
                "description": "Your agent/subagent ID (default: 'agent')",
            },
        },
        "required": ["title", "description", "options"],
    }

    async def execute(
        self,
        title: str,
        description: str,
        options: List[str],
        creator_id: str = "agent",
        **kwargs,
    ) -> ToolResult:
        try:
            prop = swarm_deliberation.create_proposal(
                creator_id=creator_id,
                title=title,
                description=description,
                options=options,
            )
            # Announce proposal across swarm bus
            swarm_bus.broadcast(
                sender_id=creator_id,
                content=f"📢 NEW PROPOSAL [{prop.proposal_id}]: '{title}' by {creator_id}. Options: {options}. Call 'subagent_vote' to cast your vote!",
                metadata={"type": "proposal", "proposal_id": prop.proposal_id},
            )

            return ToolResult(
                success=True,
                output=(
                    f"✔ Swarm Proposal Created: [{prop.proposal_id}] '{title}'\n"
                    f"Options: {', '.join(prop.options)}\n"
                    f"Announced across the swarm. Peer subagents can now deliberate and vote."
                ),
                metadata={"proposal_id": prop.proposal_id},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to create proposal: {e}")


class SubagentVoteTool(BaseTool):
    name = "subagent_vote"
    description = "Cast a reasoned engineering vote on an active proposal in the subagent swarm."
    required_permission = PermissionLevel.SAFE
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "proposal_id": {
                "type": "string",
                "description": "ID of the proposal (e.g. 'prop_abc123')",
            },
            "choice": {
                "type": "string",
                "description": "Your chosen option from the proposal's options",
            },
            "rationale": {
                "type": "string",
                "description": "Detailed engineering rationale and arguments supporting your vote",
            },
            "voter_id": {
                "type": "string",
                "description": "Your agent/subagent ID",
            },
        },
        "required": ["proposal_id", "choice", "rationale", "voter_id"],
    }

    async def execute(
        self,
        proposal_id: str,
        choice: str,
        rationale: str,
        voter_id: str,
        **kwargs,
    ) -> ToolResult:
        try:
            res = swarm_deliberation.cast_vote(
                proposal_id=proposal_id,
                voter_id=voter_id,
                choice=choice,
                rationale=rationale,
            )
            return ToolResult(
                success=True,
                output=(
                    f"✔ Vote recorded from '{voter_id}' on proposal [{proposal_id}].\n"
                    f"Choice: {res['recorded_choice']}\n"
                    f"Total votes recorded so far: {res['total_votes_so_far']}"
                ),
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to cast vote: {e}")


class SubagentConsensusTool(BaseTool):
    name = "subagent_consensus"
    description = "Tally votes, compute mathematical consensus, and resolve the winning decision for a proposal."
    required_permission = PermissionLevel.SAFE
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "proposal_id": {
                "type": "string",
                "description": "ID of the proposal to evaluate",
            },
            "conclude": {
                "type": "boolean",
                "description": "Whether to conclude and finalize the voting round (default: true)",
                "default": True,
            },
        },
        "required": ["proposal_id"],
    }

    async def execute(self, proposal_id: str, conclude: bool = True, **kwargs) -> ToolResult:
        try:
            report = swarm_deliberation.tally_consensus(proposal_id=proposal_id, conclude=conclude)
            output = (
                f"📊 SWARM CONSENSUS REPORT: [{report['proposal_id']}] '{report['title']}'\n"
                f"Status: {report['status'].upper()}\n"
                f"Total Votes Cast: {report['total_votes']}\n"
                f"Winning Option: {report['winning_choice']} ({report['majority_percentage']}% majority)\n"
                f"Vote Breakdown: {json.dumps(report['tally'], indent=2)}\n\n"
                f"Subagent Deliberations & Arguments:\n"
            )
            for arg in report["arguments"]:
                output += f"- **{arg['agent']}** voted '{arg['voted_for']}': {arg['reasoning']}\n"

            return ToolResult(success=True, output=output, metadata=report)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to compute consensus: {e}")
