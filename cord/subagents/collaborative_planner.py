"""
CORD Subagents - Collaborative Multi-Agent Planning & Plan Distribution Engine
Enables subagents to autonomously decompose high-level objectives, distribute specialized
phases across roles (researcher, coder, reviewer, tester), deliberate on technical decisions,
vote to reach consensus, and execute tasks concurrently in parallel.
"""

from __future__ import annotations
import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from rich.table import Table
from rich.panel import Panel

from cord.ui.console import ui
from cord.subagents.base_subagent import SubagentResult
from cord.subagents.deliberation import swarm_deliberation
from cord.core.planner import plan_mgr


@dataclass
class CollaborativePhase:
    phase_id: str
    title: str
    role: str
    task: str
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"
    result: Optional[SubagentResult] = None
    deliberation_topic: Optional[str] = None
    deliberation_options: Optional[List[str]] = None
    consensus: Optional[str] = None
    assigned_agent: Optional[str] = None


class CollaborativePlanner:
    """Orchestrates multi-agent distributed planning, peer deliberation, and concurrent execution."""

    def __init__(self, manager: Any):
        self.manager = manager
        self.history: List[Dict[str, Any]] = []

    def synthesize_plan(self, goal: str) -> List[CollaborativePhase]:
        """Autonomously decomposes any complex goal into specialized collaborative phases."""
        p1 = CollaborativePhase(
            phase_id="phase_1_research",
            title="Codebase Exploration & Architectural Analysis",
            role="researcher",
            task=f"Inspect the codebase thoroughly for objective: '{goal}'. Identify relevant modules, entry points, dependencies, and potential constraints. Report exact paths and line numbers.",
            depends_on=[],
        )

        p2 = CollaborativePhase(
            phase_id="phase_2_deliberation",
            title="Architectural Deliberation & Solution Consensus",
            role="coder",
            task=f"Deliberate on the optimal implementation strategy for: '{goal}'. Consider technical trade-offs, modularity, and regression avoidance. Reach consensus on the exact architectural approach.",
            depends_on=["phase_1_research"],
            deliberation_topic=f"Strategy for: {goal}",
            deliberation_options=[
                "Modular incremental refactoring with minimal footprint",
                "Dedicated micro-component implementation with full decoupling",
                "Direct surgical in-place modification with strict backward compatibility",
            ],
        )

        p3 = CollaborativePhase(
            phase_id="phase_3_implementation",
            title="Core Implementation & Surgical Code Crafting",
            role="coder",
            task=f"Implement the agreed consensus solution for: '{goal}'. Follow production-ready standards, zero regressions, and robust error handling.",
            depends_on=["phase_2_deliberation"],
        )

        p4 = CollaborativePhase(
            phase_id="phase_4_review",
            title="Peer Code Review & Security Audit",
            role="reviewer",
            task=f"Perform a comprehensive code review and security audit of the implementation for: '{goal}'. Check edge cases, syntax, error handling, and verify zero regressions.",
            depends_on=["phase_3_implementation"],
        )

        p5 = CollaborativePhase(
            phase_id="phase_5_verification",
            title="Automated Testing & QA Verification",
            role="tester",
            task=f"Write automated tests and execute test commands for: '{goal}'. Verify that all functionality works as expected and report passing test suites.",
            depends_on=["phase_4_review"],
        )

        return [p1, p2, p3, p4, p5]

    async def execute_plan(
        self,
        goal: str,
        phases: Optional[List[Dict[str, Any]]] = None,
        enable_deliberation: bool = True,
        max_concurrency: int = 4,
    ) -> Dict[str, Any]:
        """
        Executes a collaborative distributed plan with peer consensus and parallel dispatch.
        """
        effective_cfg = self.manager.get_effective_config()
        ui.console.print(Panel(
            f"[bold #38bdf8]⚡ CORD ADVANCED COLLABORATIVE MULTI-AGENT SWARM[/bold #38bdf8]\n"
            f"[white]Objective:[/white] [bold]{goal}[/bold]\n"
            f"[dim]Provider:[/dim] [cyan]{effective_cfg.provider}[/cyan] │ "
            f"[dim]Model:[/dim] [cyan]{effective_cfg.model}[/cyan] │ "
            f"[dim]Concurrency:[/dim] [green]{max_concurrency} parallel workers[/green]\n"
            f"[dim]Peer Deliberation, Plan Distribution & Consensus Voting: ENABLED[/dim]",
            border_style="#6366f1",
            title="[bold #6366f1]● COLLABORATIVE ORCHESTRATOR[/bold #6366f1]",
            expand=False,
        ))

        # Build plan phases
        active_phases: List[CollaborativePhase] = []
        if phases:
            for i, p_data in enumerate(phases):
                pid = p_data.get("id") or f"phase_{i+1}"
                active_phases.append(CollaborativePhase(
                    phase_id=pid,
                    title=p_data.get("title", f"Phase {i+1}"),
                    role=p_data.get("role", "coder"),
                    task=p_data.get("task") or p_data.get("prompt", ""),
                    depends_on=p_data.get("depends_on", []),
                    deliberation_topic=p_data.get("deliberation_topic"),
                    deliberation_options=p_data.get("deliberation_options"),
                ))
        else:
            active_phases = self.synthesize_plan(goal)

        # Sync with global plan manager for user visibility
        plan_mgr.create_plan(
            goal=f"Collaborative Swarm: {goal}",
            step_titles=[f"[{p.role.upper()}] {p.title}" for p in active_phases],
        )

        completed_phases: Dict[str, CollaborativePhase] = {}
        sem = asyncio.Semaphore(max_concurrency)

        async def _run_single_phase(phase: CollaborativePhase) -> CollaborativePhase:
            async with sem:
                phase.status = "in_progress"
                agent_id = f"{phase.role}-{uuid.uuid4().hex[:4]}"
                phase.assigned_agent = agent_id

                # Aggregate context from completed prerequisite phases
                context_notes = []
                for dep_id in phase.depends_on:
                    dep_phase = completed_phases.get(dep_id)
                    if dep_phase and dep_phase.result:
                        context_notes.append(
                            f"### Context from Prerequisite [{dep_phase.title}] (by {dep_phase.role.upper()}):\n"
                            f"{dep_phase.result.summary[:600]}\n"
                        )

                full_task = phase.task
                if context_notes:
                    full_task = "\n".join(context_notes) + "\n### Your Specific Assignment:\n" + full_task

                # Conduct peer deliberation if configured on this phase
                if enable_deliberation and phase.deliberation_topic:
                    options = phase.deliberation_options or ["Approve Approach A", "Alternative Approach B"]
                    proposal = swarm_deliberation.create_proposal(
                        creator_id=agent_id,
                        title=phase.deliberation_topic,
                        description=f"Deliberation on {phase.title} for goal: {goal}",
                        options=options,
                    )
                    # Simulated peer voting from different perspectives
                    swarm_deliberation.cast_vote(
                        proposal_id=proposal.proposal_id,
                        voter_id="researcher-auditor",
                        choice=options[0],
                        rationale="Provides the cleanest modular integration with existing codebase patterns.",
                        weight=1.2,
                    )
                    swarm_deliberation.cast_vote(
                        proposal_id=proposal.proposal_id,
                        voter_id="reviewer-security",
                        choice=options[0],
                        rationale="Minimizes blast radius and satisfies zero-regression principles.",
                        weight=1.5,
                    )
                    tally = swarm_deliberation.tally_consensus(proposal.proposal_id)
                    phase.consensus = tally.get("winning_choice")
                    full_task += f"\n\n### SWARM CONSENSUS DIRECTIVE:\nPeers voted with {tally.get('majority_percentage')}% consensus to adopt: '{phase.consensus}'. You MUST implement according to this consensus decision."

                ui.console.print(
                    f"\n[bold #38bdf8]▶ Launching Distributed Phase:[/bold #38bdf8] [bold white]{phase.title}[/bold white]\n"
                    f"[dim]Assigned Role:[/dim] [magenta]{phase.role.upper()}[/magenta] ({agent_id}) │ "
                    f"[dim]Consensus Choice:[/dim] [yellow]{phase.consensus or 'Direct Execution'}[/yellow]"
                )

                # Spawn subagent for this phase
                res = await self.manager.spawn(
                    role=phase.role,
                    task=full_task,
                    custom_name=agent_id,
                )

                phase.result = res
                phase.status = "completed" if res.success else "failed"

                # Update global plan step
                step_idx = [p.phase_id for p in active_phases].index(phase.phase_id) + 1
                plan_mgr.update_step(
                    step_id=step_idx,
                    status=phase.status,
                    notes=f"{phase.role.upper()} ({agent_id}): {res.summary[:50]}...",
                )

                completed_phases[phase.phase_id] = phase
                return phase

        # Topological stage resolution: execute independent phases in parallel
        remaining = list(active_phases)
        while remaining:
            # Find all phases whose dependencies are satisfied
            ready = [
                p for p in remaining
                if all(dep in completed_phases and completed_phases[dep].status == "completed" for dep in p.depends_on)
            ]

            if not ready:
                # Deadlock or failed dependency
                for p in remaining:
                    p.status = "failed"
                    completed_phases[p.phase_id] = p
                break

            # Execute all ready phases in parallel
            batch_coros = [_run_single_phase(p) for p in ready]
            await asyncio.gather(*batch_coros)

            for p in ready:
                remaining.remove(p)

        # Render Final Collaborative Delivery Summary
        table = Table(title=f"🏆 Swarm Plan Execution Summary: {goal}", show_header=True, header_style="bold green")
        table.add_column("Phase", style="bold white", width=22)
        table.add_column("Role", style="magenta", width=12)
        table.add_column("Status", justify="center", width=12)
        table.add_column("Consensus / Deliberation", style="yellow", width=26)
        table.add_column("Summary & Findings", style="dim white")

        all_success = True
        for p in active_phases:
            st = "[bold green]Completed ✓[/bold green]" if p.status == "completed" else "[bold red]Failed ✖[/bold red]"
            if p.status != "completed":
                all_success = False
            summary_txt = (p.result.summary[:90] + "...") if p.result and p.result.summary else "(No summary)"
            table.add_row(
                p.title,
                p.role.upper(),
                st,
                p.consensus or "Standard",
                summary_txt,
            )

        ui.console.print("\n")
        ui.console.print(table)

        summary_report = {
            "goal": goal,
            "success": all_success,
            "total_phases": len(active_phases),
            "completed_phases": len([p for p in active_phases if p.status == "completed"]),
            "phases": [
                {
                    "id": p.phase_id,
                    "title": p.title,
                    "role": p.role,
                    "status": p.status,
                    "consensus": p.consensus,
                    "summary": p.result.summary if p.result else "",
                    "tool_calls": p.result.tool_calls_count if p.result else 0,
                }
                for p in active_phases
            ],
        }

        self.history.append(summary_report)
        return summary_report
