"""
CORD UI - Complete Changes Dashboard & Session Changelog Inspector
Renders a comprehensive, high-contrast dashboard showing all file modifications,
line additions (+X), line removals (-Y), and syntax-highlighted diffs per conversation.
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group

from cord.ui.console import ui
from cord.memory.sessions import session_manager


def render_changes_dashboard(session_id: Optional[str] = None) -> None:
    """Displays a complete visual changes dashboard for the current or specified session."""
    changes = session_manager.get_session_changes(session_id)
    sid = session_id or session_manager.current_session_id
    tfile = session_manager.current_target_file

    if not changes:
        ui.console.print()
        ui.print_info(f"No file modifications or changes recorded yet in session [{sid}].")
        if tfile:
            ui.console.print(f"  [dim]Target File Scoped:[/dim] [bold cyan]{tfile}[/bold cyan]")
        ui.console.print()
        return

    tot_added = sum(c.get("lines_added", 0) for c in changes)
    tot_removed = sum(c.get("lines_removed", 0) for c in changes)
    unique_files = list(dict.fromkeys(c.get("file") for c in changes if c.get("file")))

    # 1. Dashboard Header Banner
    header_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    header_table.add_column("Left", justify="left")
    header_table.add_column("Right", justify="right")

    target_badge = f" [bold magenta][📁 {Path(tfile).name}][/bold magenta]" if tfile else " [dim][🌐 Global Scope][/dim]"
    header_table.add_row(
        f"[bold bright_white]📊 CORD Changes Dashboard[/bold bright_white]{target_badge}",
        f"[bold cyan]Session:[/bold cyan] [dim]{sid}[/dim]"
    )
    ui.console.print()
    ui.console.print(Panel(header_table, border_style="cyan", padding=(0, 1)))

    # 2. Summary Statistics Metric Bar
    stats_table = Table(title="📈 Session Modification Metrics", show_header=True, header_style="bold cyan", expand=True)
    stats_table.add_column("Metric", style="bold white", width=24)
    stats_table.add_column("Count / Delta", style="bright_white")
    stats_table.add_column("Notes", style="dim")

    stats_table.add_row("Total Files Modified", str(len(unique_files)), f"{len(unique_files)} unique files")
    stats_table.add_row("Lines Added", f"[bold green]+{tot_added}[/bold green]", "New or replaced code lines")
    stats_table.add_row("Lines Removed", f"[bold red]-{tot_removed}[/bold red]", "Deleted or replaced lines")
    stats_table.add_row("Net Code Change", f"[bold yellow]{tot_added - tot_removed:+d}[/bold yellow]", "Net line impact")
    stats_table.add_row("Total Edit Actions", str(len(changes)), "Checkpoints logged")

    ui.console.print(stats_table)
    ui.console.print()

    # 3. File Breakdown & Unified Diffs
    ui.console.print("[bold bright_white]📝 Detailed File Changelog & Diffs:[/bold bright_white]\n")

    for idx, ch in enumerate(changes, start=1):
        fpath = ch.get("file", "unknown")
        fname = ch.get("filename") or Path(fpath).name
        action = ch.get("action", "edited").upper()
        added = ch.get("lines_added", 0)
        removed = ch.get("lines_removed", 0)
        desc = ch.get("description", "")
        ts = ch.get("timestamp", time.time())
        t_str = time.strftime("%H:%M:%S", time.localtime(ts))

        action_color = "green" if action == "CREATED" else ("yellow" if action == "EDITED" else "red")
        badge = f"[bold {action_color}][{action}][/bold {action_color}]"
        diff_stats = f"[bold green]+{added}[/bold green] [bold red]-{removed}[/bold red]"

        card_title = f"#{idx} {badge} [bold cyan]{fname}[/bold cyan] │ {diff_stats} │ [dim]{t_str}[/dim]"

        diff_body = ch.get("diff", "")
        card_content = Text()
        if desc:
            card_content.append(f"{desc}\n\n", style="dim")

        if diff_body:
            for d_line in diff_body.splitlines():
                if d_line.startswith("+") and not d_line.startswith("+++"):
                    card_content.append(f"{d_line}\n", style="bold green")
                elif d_line.startswith("-") and not d_line.startswith("---"):
                    card_content.append(f"{d_line}\n", style="bold red")
                elif d_line.startswith("@@"):
                    card_content.append(f"{d_line}\n", style="bold cyan")
                else:
                    card_content.append(f"{d_line}\n", style="dim white")
        else:
            card_content.append("(No diff text available)", style="dim")

        ui.console.print(Panel(
            card_content,
            title=card_title,
            title_align="left",
            border_style="bright_blue",
            padding=(0, 1)
        ))

    ui.console.print(f"[dim]Tip: Use [/dim][bold cyan]/undo[/bold cyan][dim] to revert the most recent file change.[/dim]\n")
