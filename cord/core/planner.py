"""
CORD Core - Dynamic Step Planner & Task Tracker
Allows the agent to self-organize complex multi-step tasks into actionable checklists.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from cord.ui.console import ui


@dataclass
class PlanStep:
    id: int
    title: str
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"
    notes: str = ""


@dataclass
class Plan:
    goal: str
    steps: List[PlanStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PlanManager:
    """Manages active task plan and renders progress."""

    def __init__(self):
        self.current_plan: Optional[Plan] = None

    def create_plan(self, goal: str, step_titles: List[str]) -> Plan:
        steps = [PlanStep(id=i + 1, title=t, status="pending") for i, t in enumerate(step_titles)]
        self.current_plan = Plan(goal=goal, steps=steps)
        self.render()
        return self.current_plan

    def update_step(self, step_id: int, status: str, notes: str = "") -> Optional[PlanStep]:
        if not self.current_plan:
            return None
        for step in self.current_plan.steps:
            if step.id == step_id:
                step.status = status
                if notes:
                    step.notes = notes
                self.render()
                return step
        return None

    def render(self) -> None:
        if not self.current_plan:
            return

        table = Table(title=f"📋 Plan: {self.current_plan.goal}", show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Status", width=14)
        table.add_column("Task Description", style="bold white")
        table.add_column("Notes", style="dim cyan")

        status_icons = {
            "pending": "[dim]⏳ Pending[/dim]",
            "in_progress": "[bold yellow]🔄 In Progress[/bold yellow]",
            "completed": "[bold green]✅ Done[/bold green]",
            "failed": "[bold red]❌ Failed[/bold red]",
        }

        for s in self.current_plan.steps:
            icon = status_icons.get(s.status, s.status)
            table.add_row(str(s.id), icon, s.title, s.notes or "")

        ui.console.print(table)


# Global plan manager instance
plan_mgr = PlanManager()
