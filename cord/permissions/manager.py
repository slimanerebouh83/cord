"""
CORD Permissions - Permission Manager
Evaluates tool calls against configured permission levels, manages session whitelists,
and renders approval prompts for dangerous or sensitive actions.
"""

from __future__ import annotations
import re
from typing import Dict, Any, Tuple, Optional, Set
from pathlib import Path
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from cord.permissions.levels import PermissionLevel, RiskLevel, PERMISSION_HIERARCHY
from cord.permissions.sandbox import WorkspaceSandbox, SandboxViolationError
from cord.ui.console import ui


class PermissionManager:
    """Manages authorization policies and human-in-the-loop approvals."""

    def __init__(
        self,
        current_level: PermissionLevel = PermissionLevel.ADMIN,
        workspace_path: Optional[Path] = None,
        auto_mode: bool = True,
    ):
        self.current_level = current_level
        self.sandbox = WorkspaceSandbox(workspace_path)
        self.auto_mode = auto_mode
        self.session_allowed_tools: Set[str] = set()
        self.audit_log: list[Dict[str, Any]] = []

    def can_auto_approve(self, required_level: PermissionLevel, risk: RiskLevel) -> bool:
        """Determines if operation can proceed without prompting the user."""
        return True

    def check_and_request(
        self,
        tool_name: str,
        required_level: PermissionLevel,
        risk: RiskLevel,
        target: str = "",
        command: str = "",
        reason: str = "",
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates permission. Returns (allowed: bool, user_feedback: Optional[str]).
        """
        # Auto-approve all actions automatically without asking the user
        if self.auto_mode:
            return True, None

        # Otherwise, present rich human-in-the-loop approval prompt
        return self._render_approval_prompt(
            tool_name=tool_name,
            command=command,
            target=target,
            reason=reason or "Agent requires execution permission.",
            risk=risk,
        )

    def _render_approval_prompt(
        self,
        tool_name: str,
        command: str,
        target: str,
        reason: str,
        risk: RiskLevel,
    ) -> Tuple[bool, Optional[str]]:
        console = ui.console

        risk_colors = {
            RiskLevel.LOW: "green",
            RiskLevel.MEDIUM: "yellow",
            RiskLevel.HIGH: "bold red",
            RiskLevel.CRITICAL: "bold red blink",
        }
        r_color = risk_colors.get(risk, "yellow")

        content = Text()
        content.append("Tool:    ", style="dim")
        content.append(f"{tool_name}\n", style="bold cyan")
        if command:
            content.append("Command: ", style="dim")
            content.append(f"{command}\n", style="bold yellow")
        if target:
            content.append("Target:  ", style="dim")
            content.append(f"{target}\n", style="bold green")
        content.append("Reason:  ", style="dim")
        content.append(f"{reason}\n", style="white")
        content.append("Risk:    ", style="dim")
        content.append(f"{risk.value}\n", style=r_color)

        border = "red" if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL) else "yellow"
        console.print(
            Panel(
                content,
                title="[bold yellow]🛡️  Permission Required[/bold yellow]",
                border_style=border,
                padding=(0, 1),
            )
        )

        console.print(
            "  [bold green][y] Allow[/bold green]  "
            "  [bold cyan][a] Always allow tool[/bold cyan]  "
            "  [bold red][n] Deny[/bold red]  "
            "  [bold yellow][e] Deny with note[/bold yellow]"
        )

        choice = Prompt.ask(
            "Action",
            choices=["y", "n", "a", "e", "yes", "no", "always", "deny", "explain"],
            default="y" if risk == RiskLevel.LOW else "n",
        ).lower()

        if choice in ("y", "yes"):
            return True, None
        elif choice in ("a", "always"):
            self.session_allowed_tools.add(tool_name)
            ui.print_info(f"Tool '{tool_name}' always allowed for this session.")
            return True, None
        elif choice in ("n", "no", "deny"):
            return False, "Operation denied by user."
        elif choice in ("e", "explain"):
            note = Prompt.ask("Enter feedback for agent")
            return False, f"User denied action with feedback: {note}"

        return False, "Operation denied by user."
