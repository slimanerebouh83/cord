"""CORD Tools - Collaborative Subagent Planning & Distribution Tool"""
from __future__ import annotations
import json
from typing import Optional, List, Dict, Any
from cord.tools.base import BaseTool, ToolResult, PermissionLevel, RiskLevel
from cord.subagents.collaborative_planner import CollaborativePlanner


class CollaborativePlanTool(BaseTool):
    name = "collaborative_plan"
    description = (
        "Decomposes a complex objective into an autonomous multi-phase plan, distributes the phases "
        "across specialized subagents (researcher, coder, reviewer, tester), conducts peer deliberation "
        "and consensus voting, and executes the tasks concurrently in parallel."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM

    parameters = {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "High-level goal or complex engineering objective to plan and execute.",
            },
            "phases": {
                "type": "array",
                "description": "Optional custom phases list. If omitted, an optimal 5-phase plan (Research, Deliberate, Implement, Review, Test) is automatically synthesized.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Unique phase identifier"},
                        "title": {"type": "string", "description": "Descriptive title for this phase"},
                        "role": {"type": "string", "description": "Subagent role (researcher, coder, reviewer, tester)"},
                        "task": {"type": "string", "description": "Explicit instructions for this phase"},
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Prerequisite phase IDs that must complete first",
                        },
                        "deliberation_topic": {"type": "string", "description": "Optional architectural decision topic"},
                        "deliberation_options": {"type": "array", "items": {"type": "string"}, "description": "Candidate options for peer voting"},
                    },
                    "required": ["role", "task"],
                },
            },
            "enable_deliberation": {
                "type": "boolean",
                "description": "Whether subagents should conduct peer debate and consensus voting before implementation (default true).",
                "default": True,
            },
            "max_concurrency": {
                "type": "integer",
                "description": "Maximum number of parallel subagents running simultaneously (default 4).",
                "default": 4,
            },
        },
        "required": ["goal"],
    }

    def __init__(self, subagent_manager: Any):
        super().__init__()
        self.subagent_manager = subagent_manager
        self.planner = CollaborativePlanner(subagent_manager)

    async def execute(
        self,
        goal: str,
        phases: Optional[Any] = None,
        enable_deliberation: bool = True,
        max_concurrency: int = 4,
        **kwargs,
    ) -> ToolResult:
        try:
            report = await self.planner.execute_plan(
                goal=goal,
                phases=phases,
                enable_deliberation=enable_deliberation,
                max_concurrency=max_concurrency,
            )

            output_lines = [
                f"Collaborative Plan Execution: {'SUCCESS ✓' if report['success'] else 'PARTIAL / FAILED ✖'}",
                f"Goal: {goal}",
                f"Phases Completed: {report['completed_phases']}/{report['total_phases']}",
                "",
                "Phase Breakdown:",
            ]
            for p in report["phases"]:
                st_icon = "✓" if p["status"] == "completed" else "✖"
                cons = f" [Consensus: {p['consensus']}]" if p.get("consensus") else ""
                output_lines.append(f"- [{st_icon}] {p['title']} ({p['role'].upper()}){cons}")
                if p.get("summary"):
                    output_lines.append(f"   Summary: {p['summary'][:160]}...")

            return ToolResult(
                success=report["success"],
                output="\n".join(output_lines),
                metadata=report,
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Collaborative plan failed: {e}")
