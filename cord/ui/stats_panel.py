"""CORD UI - Real-Time Workspace Statistics & Live Dashboard"""
from __future__ import annotations
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.layout import Layout
from rich.text import Text

from cord.ui.console import ui
from cord.core.modes import mode_manager

def get_workspace_file_stats(root_path: Path) -> Dict[str, Any]:
    """Scans workspace directory to calculate files count, extensions distribution, and LOC."""
    ignored = {".git", ".venv", "venv", "node_modules", "__pycache__", ".cord", "dist", "build", ".pytest_cache"}
    total_files = 0
    code_files = 0
    total_loc = 0
    ext_counts: Dict[str, int] = {}
    ext_loc: Dict[str, int] = {}

    code_exts = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss",
        ".rs", ".go", ".c", ".cpp", ".h", ".cs", ".java", ".json", ".yaml", ".yml", ".md", ".sh", ".ps1"
    }

    try:
        for p in root_path.rglob("*"):
            if any(part in ignored or part.startswith(".") for part in p.parts):
                continue
            if p.is_file():
                total_files += 1
                ext = p.suffix.lower() or "other"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

                if ext in code_exts:
                    code_files += 1
                    try:
                        # Count lines without crashing on binary or huge files
                        if p.stat().st_size < 1_000_000:
                            lines = len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
                            total_loc += lines
                            ext_loc[ext] = ext_loc.get(ext, 0) + lines
                    except Exception:
                        pass
    except Exception:
        pass

    top_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:6]

    return {
        "total_files": total_files,
        "code_files": code_files,
        "total_loc": total_loc,
        "top_exts": top_exts,
    }

def get_git_info(root_path: Path) -> Tuple[str, int]:
    branch = "no git"
    changed_count = 0
    try:
        b_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(root_path),
            capture_output=True,
            text=True,
            timeout=2.0
        )
        if b_res.returncode == 0:
            branch = b_res.stdout.strip()

        s_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root_path),
            capture_output=True,
            text=True,
            timeout=2.0
        )
        if s_res.returncode == 0:
            changed_count = len([l for l in s_res.stdout.splitlines() if l.strip()])
    except Exception:
        pass
    return branch, changed_count

def render_stats_dashboard(
    workspace_path: Path,
    session_start_time: float,
    total_input_tokens: int,
    total_output_tokens: int,
    total_turns: int = 0
) -> None:
    """Renders a comprehensive Rich statistics dashboard in the terminal."""
    w_stats = get_workspace_file_stats(workspace_path)
    branch, changed_files = get_git_info(workspace_path)
    active_profile = mode_manager.get_profile()

    elapsed_sec = int(time.time() - session_start_time)
    elapsed_str = f"{elapsed_sec // 60}m {elapsed_sec % 60}s"

    # Panel 1: Workspace & Codebase Metrics
    t1 = Table(show_header=False, box=None, padding=(0, 1))
    t1.add_column("Key", style="bold bright_cyan")
    t1.add_column("Val", style="bright_white")
    t1.add_row("📁 Workspace Root:", f"[cyan]{workspace_path.name}[/cyan] ({workspace_path})")
    t1.add_row("📄 Total Files:", f"[bold green]{w_stats['total_files']:,}[/bold green]")
    t1.add_row("💻 Code Files:", f"[bold green]{w_stats['code_files']:,}[/bold green]")
    t1.add_row("📊 Lines of Code (LOC):", f"[bold yellow]{w_stats['total_loc']:,}[/bold yellow] lines")

    ext_summary = ", ".join(f"[dim]{ext}:[/dim] {cnt}" for ext, cnt in w_stats["top_exts"][:4])
    t1.add_row("🏷️ Top File Types:", ext_summary or "None")
    t1.add_row("🌿 Git Branch:", f"[magenta]{branch}[/magenta] ([yellow]{changed_files} modified[/yellow])")

    p1 = Panel(t1, title="[bold bright_white]📊 Codebase & Workspace Analytics[/bold bright_white]", border_style="cyan")

    # Panel 2: Session & Performance Metrics
    t2 = Table(show_header=False, box=None, padding=(0, 1))
    t2.add_column("Key", style="bold bright_magenta")
    t2.add_column("Val", style="bright_white")
    t2.add_row("🎯 Active Mode:", f"[{active_profile.badge_style}]{active_profile.badge} {active_profile.name}[/{active_profile.badge_style}]")
    t2.add_row("💬 Prompt Turns:", f"{total_turns}")
    t2.add_row("⏱️ Session Time:", f"[cyan]{elapsed_str}[/cyan]")
    t2.add_row("📥 Input Tokens:", f"[bold cyan]{total_input_tokens:,}[/bold cyan]")
    t2.add_row("📤 Output Tokens:", f"[bold magenta]{total_output_tokens:,}[/bold magenta]")
    t2.add_row("🔢 Total Tokens:", f"[bold green]{total_input_tokens + total_output_tokens:,}[/bold green]")

    p2 = Panel(t2, title="[bold bright_white]⚡ Session & Runtime Status[/bold bright_white]", border_style="magenta")

    ui.console.print(Columns([p1, p2], equal=True))
