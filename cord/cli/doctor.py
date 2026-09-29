"""CORD CLI - System Diagnostics & Environment Doctor"""
from __future__ import annotations
import sys
import shutil
import platform
from pathlib import Path
from rich.table import Table
from rich.panel import Panel

from cord.ui.console import ui
from cord.core.config import ConfigManager
from cord.providers.provider_manager import provider_manager
from cord.vision.safety import computer_safety

def run_doctor() -> None:
    """Runs a complete diagnostic check on CORD's environment, tools, and providers."""
    ui.console.print(Panel("[bold cyan]🩺 CORD System Diagnostics & Doctor[/bold cyan]", border_style="cyan"))

    table = Table(title="Environment Checks", border_style="blue", show_header=True)
    table.add_column("Component", style="bold bright_white")
    table.add_column("Detected / Status", style="white")
    table.add_column("Result", justify="center")

    # 1. OS & Architecture
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    table.add_row("Operating System", os_info, "[bold green]✓ PASS[/bold green]")

    # 2. Python Version
    py_ver = sys.version.split()[0]
    py_pass = sys.version_info >= (3, 10)
    res = "[bold green]✓ PASS[/bold green]" if py_pass else "[bold red]✗ FAIL[/bold red]"
    table.add_row("Python Runtime", f"{py_ver} ({sys.executable})", res)

    # 3. Git binary
    git_path = shutil.which("git")
    if git_path:
        table.add_row("Git CLI", git_path, "[bold green]✓ PASS[/bold green]")
    else:
        table.add_row("Git CLI", "Not found in PATH", "[bold yellow]! WARN[/bold yellow]")

    # 4. Node / npm
    node_path = shutil.which("node")
    if node_path:
        table.add_row("Node.js CLI", node_path, "[bold green]✓ PASS[/bold green]")
    else:
        table.add_row("Node.js CLI", "Not installed (JS tools unavailable)", "[dim yellow]! INFO[/dim yellow]")

    # 5. LiteLLM Abstraction Layer
    try:
        import litellm
        table.add_row("LiteLLM Engine", "Installed and ready", "[bold green]✓ PASS[/bold green]")
    except ImportError:
        table.add_row("LiteLLM Engine", "Falling back to direct HTTP engine", "[bold yellow]! WARN[/bold yellow]")

    # 6. Computer Use & Vision
    w, h = computer_safety.screen_size
    table.add_row("Computer Use (Screen)", f"{w}x{h} ({computer_safety.safety_level.value})", "[bold green]✓ PASS[/bold green]")

    # 7. Discovered Providers & API Keys
    providers = provider_manager.discover_providers()
    active = [p.name for p in providers if p.is_configured]
    if active:
        table.add_row("Configured AI Providers", ", ".join(active), "[bold green]✓ PASS[/bold green]")
    else:
        table.add_row("Configured AI Providers", "None found in environment or config", "[bold red]✗ FAIL[/bold red]")

    # 8. Workspace Directory
    config_mgr = ConfigManager()
    ws = Path(config_mgr.config.workspace_dir).resolve()
    if ws.exists():
        table.add_row("Workspace Root", str(ws), "[bold green]✓ PASS[/bold green]")
    else:
        table.add_row("Workspace Root", f"{ws} does not exist", "[bold red]✗ FAIL[/bold red]")

    ui.console.print(table)
