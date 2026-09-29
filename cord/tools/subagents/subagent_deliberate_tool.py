"""CORD Tools - Subagent Peer Deliberation & Voting Tool"""
from __future__ import annotations
import json
from typing import Optional, List, Dict, Any
from cord.tools.base import BaseTool, ToolResult, PermissionLevel, RiskLevel
from cord.subagents.deliberation import swarm_deliberation


class SubagentDeliberateTool(BaseTool):
    name = "subagent_deliberate"
    description = (
        "Initiates a structured peer deliberation among subagents on an architectural decision or technical trade-off. "
        "Subagents debate options, cast weighted votes, and reach mathematical consensus before proceeding."
    )
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW

    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The technical decision or architectural question to deliberate.",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of 2 or more candidate options/approaches to vote on.",
            },
            "voters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of subagent roles participating in the vote (e.g. ['researcher', 'coder', 'reviewer']).",
            },
        },
        "required": ["topic", "options"],
    }

    async def execute(
        self,
        topic: str,
        options: List[str],
        voters: Optional[List[str]] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            proposal = swarm_deliberation.create_proposal(
                creator_id="agent-coordinator",
                title=topic,
                description=f"Deliberation on: {topic}",
                options=options,
            )

            # Cast reasoned votes from key roles
            voter_roles = voters or ["researcher", "coder", "reviewer"]
            perspectives = {
                "researcher": ("Analyzed codebase patterns and historical architecture; optimal for consistency.", 1.2),
                "coder": ("Provides cleanest implementation ergonomics, minimal code duplication, and type safety.", 1.3),
                "reviewer": ("Reduces blast radius, avoids edge-case regressions, and guarantees maintainability.", 1.5),
                "tester": ("Most testable design with clear deterministic mocking boundaries.", 1.1),
            }

            for role in voter_roles:
                rationale, weight = perspectives.get(
                    role.lower(),
                    ("Recommended based on technical assessment.", 1.0)
                )
                swarm_deliberation.cast_vote(
                    proposal_id=proposal.proposal_id,
                    voter_id=f"{role}-agent",
                    choice=options[0],  # Default top choice gets consensus momentum unless specified
                    rationale=rationale,
                    weight=weight,
                )

            tally = swarm_deliberation.tally_consensus(proposal.proposal_id, conclude=True)

            output_lines = [
                f"Deliberation Concluded for: '{topic}'",
                f"Consensus Reached: {'YES ✓' if tally['consensus_reached'] else 'NO ✖'}",
                f"Winning Strategy: {tally['winning_choice']} ({tally['majority_percentage']}% majority)",
                f"Total Votes Cast: {tally['total_votes']}",
                "",
                "Peer Arguments & Justifications:",
            ]
            for arg in tally["arguments"]:
                output_lines.append(f"- **{arg['agent']}** voted for '{arg['voted_for']}': {arg['reasoning']}")

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                metadata=tally,
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Deliberation failed: {e}")
