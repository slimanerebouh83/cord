"""
CORD Subagents - Swarm Deliberation, Peer Voting & Consensus Engine.
Enables subagents to propose strategic architectures, deliberate alternatives,
cast reasoned votes, and mathematically reach true consensus.
"""

from __future__ import annotations
import time
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class SwarmProposal:
    proposal_id: str
    creator_id: str
    title: str
    description: str
    options: List[str]
    votes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    status: str = "open"  # "open" or "concluded"
    created_at: float = field(default_factory=time.time)
    consensus_choice: Optional[str] = None


class SwarmDeliberationEngine:
    """Manages multi-agent proposals, voting rounds, debate arguments, and consensus."""

    def __init__(self):
        self.proposals: Dict[str, SwarmProposal] = {}

    def create_proposal(
        self,
        creator_id: str,
        title: str,
        description: str,
        options: List[str],
    ) -> SwarmProposal:
        """Creates an active deliberation topic for subagents to vote on."""
        pid = f"prop_{uuid.uuid4().hex[:6]}"
        cleaned_options = [o.strip() for o in options if o.strip()]
        if not cleaned_options:
            cleaned_options = ["Approve", "Reject"]

        proposal = SwarmProposal(
            proposal_id=pid,
            creator_id=creator_id,
            title=title.strip(),
            description=description.strip(),
            options=cleaned_options,
        )
        self.proposals[pid] = proposal
        return proposal

    def cast_vote(
        self,
        proposal_id: str,
        voter_id: str,
        choice: str,
        rationale: str,
        weight: float = 1.0,
    ) -> Dict[str, Any]:
        """Casts an engineering vote with technical reasoning."""
        if proposal_id not in self.proposals:
            raise ValueError(f"Proposal '{proposal_id}' not found.")

        prop = self.proposals[proposal_id]
        if prop.status != "open":
            raise ValueError(f"Proposal '{proposal_id}' is already closed/concluded.")

        # Validate choice matches one of the options (case-insensitive substring match)
        clean_choice = choice.strip()
        matched_option = None
        for opt in prop.options:
            if clean_choice.lower() in opt.lower() or opt.lower() in clean_choice.lower():
                matched_option = opt
                break
        if not matched_option:
            matched_option = clean_choice

        vote_record = {
            "voter_id": voter_id,
            "choice": matched_option,
            "rationale": rationale.strip(),
            "weight": weight,
            "timestamp": time.time(),
        }
        prop.votes[voter_id] = vote_record

        return {
            "success": True,
            "proposal_id": proposal_id,
            "voter": voter_id,
            "recorded_choice": matched_option,
            "total_votes_so_far": len(prop.votes),
        }

    def tally_consensus(self, proposal_id: str, conclude: bool = True) -> Dict[str, Any]:
        """Tallies all cast votes, calculates consensus percentages, and resolves decision."""
        if proposal_id not in self.proposals:
            raise ValueError(f"Proposal '{proposal_id}' not found.")

        prop = self.proposals[proposal_id]
        if not prop.votes:
            return {
                "proposal_id": proposal_id,
                "title": prop.title,
                "status": prop.status,
                "total_votes": 0,
                "consensus_reached": False,
                "winning_choice": None,
                "tally": {},
                "arguments": [],
            }

        tally: Dict[str, float] = {}
        arguments: List[Dict[str, str]] = []

        for vote in prop.votes.values():
            c = vote["choice"]
            w = vote.get("weight", 1.0)
            tally[c] = tally.get(c, 0.0) + w
            arguments.append({
                "agent": vote["voter_id"],
                "voted_for": c,
                "reasoning": vote["rationale"],
            })

        total_weight = sum(tally.values())
        winning_choice = max(tally.items(), key=lambda x: x[1])[0]
        winning_weight = tally[winning_choice]
        percentage = (winning_weight / total_weight) * 100.0 if total_weight > 0 else 0.0

        consensus_reached = percentage >= 50.0

        if conclude:
            prop.status = "concluded"
            prop.consensus_choice = winning_choice

        return {
            "proposal_id": proposal_id,
            "title": prop.title,
            "status": prop.status,
            "total_votes": len(prop.votes),
            "consensus_reached": consensus_reached,
            "winning_choice": winning_choice,
            "majority_percentage": round(percentage, 1),
            "tally": {k: round(v, 1) for k, v in tally.items()},
            "arguments": arguments,
        }

    def list_proposals(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": p.proposal_id,
                "title": p.title,
                "creator": p.creator_id,
                "options": p.options,
                "votes_count": len(p.votes),
                "status": p.status,
                "consensus": p.consensus_choice,
            }
            for p in self.proposals.values()
        ]


swarm_deliberation = SwarmDeliberationEngine()
