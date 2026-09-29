"""
CORD UI - Console and Styling Subsystem
Provides rich console styling, themes, badges, and layout utilities.
Hardened with UTF-8 reconfigure and safe fallback characters for Windows terminals.
"""

from __future__ import annotations
import sys
from typing import Optional, Any
from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from cord.ui.arabic import fix_arabic, is_arabic

# Force UTF-8 stdout/stderr on Windows to prevent cp1256 / charmap UnicodeEncodeErrors
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

THEMES = {
    "cord_blue": Theme({
        "info": "bold #3b82f6",
        "warning": "bold #f59e0b",
        "error": "bold #ef4444",
        "success": "bold #10b981",
        "accent": "bold #2563eb",
        "subtle": "dim #94a3b8",
        "header": "bold #60a5fa",
        "tool": "bold #38bdf8",
        "model": "bold #818cf8",
        "path": "underline #38bdf8",
        "badge": "bold white on #2563eb",
    }),
    "cyberpunk": Theme({
        "info": "bold cyan",
        "warning": "bold yellow",
        "error": "bold red",
        "success": "bold green",
        "accent": "bold magenta",
        "subtle": "dim white",
        "header": "bold bright_cyan",
        "tool": "bold bright_yellow",
        "model": "bold bright_magenta",
        "path": "underline cyan",
        "badge": "black on cyan",
    }),
    "monokai": Theme({
        "info": "bold bright_blue",
        "warning": "bold yellow",
        "error": "bold bright_red",
        "success": "bold bright_green",
        "accent": "bold magenta",
        "subtle": "dim bright_white",
        "header": "bold yellow",
        "tool": "bold bright_green",
        "model": "bold bright_yellow",
        "path": "underline bright_cyan",
        "badge": "black on bright_green",
    }),
    "dracula": Theme({
        "info": "bold #8be9fd",
        "warning": "bold #f1fa8c",
        "error": "bold #ff5555",
        "success": "bold #50fa7b",
        "accent": "bold #bd93f9",
        "subtle": "dim #6272a4",
        "header": "bold #ff79c6",
        "tool": "bold #f1fa8c",
        "model": "bold #bd93f9",
        "path": "underline #8be9fd",
        "badge": "black on #bd93f9",
    }),
    "nord": Theme({
        "info": "bold #88c0d0",
        "warning": "bold #ebcb8b",
        "error": "bold #bf616a",
        "success": "bold #a3be8c",
        "accent": "bold #b48ead",
        "subtle": "dim #4c566a",
        "header": "bold #81a1c1",
        "tool": "bold #d08770",
        "model": "bold #b48ead",
        "path": "underline #8fbcbb",
        "badge": "black on #88c0d0",
    }),
}

# ASCII Logo for CORD
LOGO_ASCII = r"""
 ██████╗ ██████╗ ██████╗ ██████╗ 
██╔════╝██╔═══██╗██╔══██╗██╔══██╗
██║     ██║   ██║██████╔╝██║  ██║
██║     ██║   ██║██╔══██╗██║  ██║
╚██████╗╚██████╔╝██║  ██║██████╔╝
 ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝ 
"""

SUBTITLE = "Autonomous Terminal Coding Agent — Powered by LiteLLM Universal Layer"


class CordConsole:
    """Manages Rich output with customizable themes and Windows-safe symbols."""

    _instance: Optional[CordConsole] = None

    def __init__(self, theme_name: str = "cord_blue"):
        self.theme_name = theme_name if theme_name in THEMES else "cord_blue"
        # Use safe console settings
        self.console = Console(
            theme=THEMES[self.theme_name],
            highlight=True,
            safe_box=True,
        )

    @classmethod
    def get(cls, theme_name: str = "cord_blue") -> CordConsole:
        if cls._instance is None:
            cls._instance = CordConsole(theme_name)
        return cls._instance

    def set_theme(self, theme_name: str) -> None:
        if theme_name in THEMES:
            self.theme_name = theme_name
            self.console = Console(theme=THEMES[theme_name], highlight=True, safe_box=True)

    def print_banner(self, model: str = "", provider: str = "", mode: str = "") -> None:
        """Prints the CORD startup banner with metadata badges."""
        text = Text(LOGO_ASCII, style="header")
        sub = Text(f" {SUBTITLE}\n", style="subtle")
        
        badges = Text()
        if model:
            badges.append(" [Model] ", style="dim")
            badges.append(f" {model} ", style="badge")
            badges.append("  ")
        if provider:
            badges.append(" [Provider] ", style="dim")
            badges.append(f" {provider.upper()} ", style="bold magenta")
            badges.append("  ")
        if mode:
            mode_style = "bold green" if mode == "yolo" else ("bold yellow" if mode == "balanced" else "bold red")
            badges.append(" [Mode] ", style="dim")
            badges.append(f" {mode.upper()} ", style=mode_style)
            badges.append("  ")

        panel = Panel(
            Text.assemble(text, sub, "\n", badges),
            border_style="accent",
            subtitle="[dim]Type [bold]/help[/bold] for commands, [bold]Ctrl+C[/bold] to interrupt[/dim]",
            subtitle_align="center",
            padding=(0, 2),
        )
        self.console.print(panel)

    def print_info(self, msg: str) -> None:
        display = fix_arabic(msg) if is_arabic(msg) else msg
        self.console.print(f" [info][i][/info] {display}")

    def print_success(self, msg: str) -> None:
        display = fix_arabic(msg) if is_arabic(msg) else msg
        self.console.print(f" [success][v][/success] {display}")

    def print_warning(self, msg: str) -> None:
        display = fix_arabic(msg) if is_arabic(msg) else msg
        self.console.print(f" [warning][!][/warning] {display}")

    def print_error(self, msg: str) -> None:
        display = fix_arabic(msg) if is_arabic(msg) else msg
        self.console.print(f" [error][x][/error] {display}")

    def print_tool_start(self, tool_name: str, args_summary: str) -> None:
        self.console.print(f"\n[tool]>> Tool Call:[/tool] [bold white]{tool_name}[/bold white] [dim]({args_summary})[/dim]")

    def print_tool_result(self, tool_name: str, success: bool = True, snippet: str = "") -> None:
        mark = "[success][v][/success]" if success else "[error][x][/error]"
        self.console.print(f"{mark} [dim]{tool_name} returned:[/dim]")
        if snippet:
            lines = snippet.strip().split("\n")[:12]
            for line in lines:
                self.console.print(f"  [dim]|[/dim] {line}")
            if len(lines) < len(snippet.strip().split("\n")):
                self.console.print(f"  [dim]| ... ({len(snippet.strip().splitlines()) - 12} more lines)[/dim]")

    def print_diff(self, filename: str, diff_text: str) -> None:
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
        panel = Panel(syntax, title=f"[bold cyan]Diff Preview: {filename}[/bold cyan]", border_style="cyan")
        self.console.print(panel)


# Global console shortcut
ui = CordConsole.get()
