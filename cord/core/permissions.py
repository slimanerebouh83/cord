"""
CORD Core - Permission & Security Guard
Enforces human-in-the-loop validation for tool calls and dangerous commands.
"""

from __future__ import annotations
import re
from typing import Dict, Any, Tuple, Optional, Set
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.text import Text

from cord.core.config import CordConfig
from cord.ui.console import ui


# Tool category classification
READ_ONLY_TOOLS = {
    "read_file",
    "list_dir",
    "find_files",
    "grep_search",
    "fetch_web_page",
    "ask_user",
    "create_plan",
    "update_plan_step",
    "customize_ui",
}


class PermissionDecision:
    ALLOW = "allow"
    DENY = "deny"
    EDIT = "edit"


class PermissionGuard:
    """Evaluates whether a tool call should proceed, be denied, or prompt the user."""

    def __init__(self, config: CordConfig):
        self.config = config
        self.session_allowed_tools: Set[str] = set()
        self.audit_log: list[Dict[str, Any]] = []

    def is_dangerous_command(self, command: str) -> bool:
        """Checks if a shell command matches any blacklist pattern."""
        for pattern in self.config.dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    def check_permission(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Determines whether tool execution is allowed.
        Operates in 100% Automatic Approval mode by default:
        Never interrupts the user to ask 'Do you agree?'. All operations execute autonomously.
        """
        mode = getattr(self.config, "permission_mode", "yolo").lower()

        # Strict: prompt only if user explicitly configured strict mode
        if mode == "strict":
            if tool_name in self.session_allowed_tools:
                return True, None
            if tool_name == "run_shell":
                cmd = args.get("command", "")
                if self.is_dangerous_command(cmd):
                    ui.print_warning(f"🚨 Dangerous Command Detected: [bold red]{cmd}[/bold red]")
                    return self._prompt_user_permission(tool_name, args, is_dangerous=True)
            return self._prompt_user_permission(tool_name, args)

        # 100% Automatic Approval
        return True, None

    def _prompt_user_permission(
        self,
        tool_name: str,
        args: Dict[str, Any],
        is_dangerous: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """Displays interactive permission dialog in the terminal."""
        console = ui.console

        # Build card content
        card_content = Text()
        if is_dangerous:
            card_content.append("⚠️ CRITICAL SECURITY WARNING ⚠️\n", style="bold red blink")
            card_content.append("This command matches a dangerous system pattern!\n\n", style="yellow")

        card_content.append(f"Tool Request: ", style="dim")
        card_content.append(f"{tool_name}\n", style="bold cyan")

        if tool_name == "run_shell":
            card_content.append(f"Command: ", style="dim")
            card_content.append(f"{args.get('command', '')}\n", style="bold yellow")
            if args.get("cwd"):
                card_content.append(f"Directory: {args.get('cwd')}\n", style="dim")
        elif tool_name in ("write_file", "edit_file"):
            card_content.append(f"Target File: ", style="dim")
            card_content.append(f"{args.get('path', '')}\n", style="bold green")
            if "diff" in args:
                card_content.append(f"Diff Preview:\n{args.get('diff')}\n", style="dim")
        else:
            summary = ", ".join(f"{k}={repr(v)[:50]}" for k, v in args.items())
            card_content.append(f"Arguments: {summary}\n", style="dim")

        border = "red" if is_dangerous else "yellow"
        console.print(
            Panel(
                card_content,
                title="🛡️  Agent Permission Required",
                border_style=border,
                padding=(0, 1),
            )
        )

        console.print(
            "  [bold green][y][/bold green] Yes, allow once  "
            "  [bold cyan][a][/bold cyan] Always allow this tool  "
            "  [bold red][n][/bold red] No, deny  "
            "  [bold yellow][e][/bold yellow] Explain / Feedback"
        )

        choice = Prompt.ask(
            "Action",
            choices=["y", "n", "a", "e", "yes", "no", "always", "explain"],
            default="y" if not is_dangerous else "n",
        ).lower()

        if choice in ("y", "yes"):
            return True, None
        elif choice in ("a", "always"):
            self.session_allowed_tools.add(tool_name)
            ui.print_info(f"Tool '{tool_name}' will be automatically allowed for the rest of this session.")
            return True, None
        elif choice in ("n", "no"):
            ui.print_error("Execution denied by user.")
            return False, "Execution denied by user."
        elif choice in ("e", "explain"):
            reason = Prompt.ask("Enter feedback or explanation for the agent")
            return False, f"User rejected tool execution with note: {reason}"

        return False, "Execution denied by user."
