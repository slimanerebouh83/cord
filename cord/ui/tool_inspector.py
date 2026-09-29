"""
CORD UI - Interactive Keyboard-Navigable Tool Inspector
Allows users to navigate through past tool executions using Up/Down arrow keys,
inspect full JSON arguments, view complete outputs, and inspect diffs.
"""

from __future__ import annotations
import sys
import time
from typing import List, Dict, Any, Optional
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group

from cord.ui.console import ui


def _get_key() -> str:
    """Reads a single keypress or arrow key on Windows and Unix."""
    if sys.platform == "win32":
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ch2 = msvcrt.getwch()
            if ch2 == "H":
                return "up"
            elif ch2 == "P":
                return "down"
            elif ch2 == "K":
                return "left"
            elif ch2 == "M":
                return "right"
            return "special"
        elif ch == "\r":
            return "enter"
        elif ch == "\x1b":
            return "esc"
        return ch.lower()
    else:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    return "up"
                elif seq == "[B":
                    return "down"
                elif seq == "[C":
                    return "right"
                elif seq == "[D":
                    return "left"
                return "esc"
            elif ch in ("\r", "\n"):
                return "enter"
            return ch.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class ToolInspector:
    """Interactive visual tool inspector navigated by arrow keys."""

    def __init__(self, tool_history: List[Dict[str, Any]]):
        self.history = tool_history
        self.current_index = len(tool_history) - 1 if tool_history else 0
        self.expanded = False

    def run(self) -> None:
        if not self.history:
            ui.print_info("No tool executions recorded in this session yet.")
            return

        ui.console.clear()
        while True:
            self._render()
            key = _get_key()

            if key in ("q", "esc"):
                ui.console.clear()
                ui.print_info("Exited Tool Inspector. Back to chat prompt.")
                break
            elif key == "up":
                if self.current_index > 0:
                    self.current_index -= 1
                    ui.console.clear()
            elif key == "down":
                if self.current_index < len(self.history) - 1:
                    self.current_index += 1
                    ui.console.clear()
            elif key == "enter":
                self.expanded = not self.expanded
                ui.console.clear()

    def _render(self) -> None:
        item = self.history[self.current_index]
        t_name = item.get("name", "unknown")
        args = item.get("args", {})
        res = item.get("result")
        elapsed = item.get("elapsed", 0.0)
        ts = item.get("timestamp", time.time())
        time_str = time.strftime("%H:%M:%S", time.localtime(ts))
        time_elapsed = f"{elapsed * 1000:.0f}ms" if elapsed < 1 else f"{elapsed:.2f}s"

        success = getattr(res, "success", True)
        status_badge = "[bold green]✔ SUCCESS[/bold green]" if success else "[bold red]✖ FAILED[/bold red]"

        # 1. Top Navigation Bar
        nav_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        nav_table.add_column("Left", justify="left")
        nav_table.add_column("Right", justify="right")
        nav_table.add_row(
            f"[bold cyan]🔍 CORD Tool Inspector[/bold cyan] [dim](Item {self.current_index + 1} of {len(self.history)})[/dim]",
            "[dim]Keys: [bold]↑/↓[/bold] Navigate │ [bold]Enter[/bold] Expand/Collapse │ [bold]Esc/q[/bold] Back[/dim]"
        )
        ui.console.print(Panel(nav_table, border_style="cyan", padding=(0, 0)))

        # 2. History selector list (compact tabs)
        selector_text = Text()
        start_idx = max(0, self.current_index - 3)
        end_idx = min(len(self.history), start_idx + 7)

        for i in range(start_idx, end_idx):
            entry = self.history[i]
            e_name = entry.get("name", "tool")
            is_active = (i == self.current_index)
            e_ok = getattr(entry.get("result"), "success", True)
            icon = "✔" if e_ok else "✖"
            if is_active:
                selector_text.append(f" ► [{i+1}] {e_name} ({icon}) ", style="bold black on cyan")
            else:
                selector_text.append(f"   [{i+1}] {e_name} ({icon}) ", style="dim white")
        ui.console.print(selector_text)
        ui.console.print()

        # 3. Main Detail Card
        details = []

        header_text = (
            f"[bold white]Tool:[/bold white] [bold magenta]{t_name}[/bold magenta]  "
            f"[bold white]Status:[/bold white] {status_badge}  "
            f"[bold white]Time:[/bold white] [cyan]{time_elapsed}[/cyan]  "
            f"[bold white]Timestamp:[/bold white] [dim]{time_str}[/dim]"
        )
        details.append(Text.from_markup(header_text))
        details.append(Text(""))

        args_table = Table(title="📥 Tool Arguments", show_header=True, header_style="bold cyan", expand=True)
        args_table.add_column("Parameter", style="bold yellow", width=18)
        args_table.add_column("Value", style="bright_white")

        for k, v in args.items():
            val_str = str(v)
            if not self.expanded and len(val_str) > 120:
                val_str = val_str[:120] + "... [dim](Press Enter to expand)[/dim]"
            args_table.add_row(k, val_str)

        details.append(args_table)
        details.append(Text(""))

        meta = getattr(res, "metadata", {}) or {}
        raw_diff = meta.get("diff")
        if raw_diff:
            diff_text = Text()
            for line in raw_diff.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    diff_text.append(f"{line}\n", style="bold green")
                elif line.startswith("-") and not line.startswith("---"):
                    diff_text.append(f"{line}\n", style="bold red")
                elif line.startswith("@@"):
                    diff_text.append(f"{line}\n", style="bold cyan")
                else:
                    diff_text.append(f"{line}\n", style="dim white")
            details.append(Panel(diff_text, title=f"📝 File Diff ({meta.get('filename', 'file')})", border_style="bright_blue"))
            details.append(Text(""))

        raw_output = getattr(res, "output", "") or getattr(res, "error", "") or "(No output)"
        if not self.expanded and len(raw_output.splitlines()) > 20:
            lines = raw_output.splitlines()[:20]
            truncated_out = "\n".join(lines) + f"\n... [dim](+{len(raw_output.splitlines()) - 20} more lines. Press Enter to view full)[/dim]"
        else:
            truncated_out = raw_output

        out_title = "📤 Output" if success else "❌ Error Details"
        border_col = "green" if success else "red"
        details.append(Panel(Text(truncated_out, style="white"), title=out_title, border_style=border_col))

        ui.console.print(Panel(Group(*details), title=f"⚡ {t_name} Execution Details", border_style="bright_cyan"))


def launch_tool_inspector(tool_history: List[Dict[str, Any]]) -> None:
    """Launches the interactive keyboard-navigable tool inspector."""
    inspector = ToolInspector(tool_history)
    inspector.run()
