"""
CORD UI - Animated About Screen & System Specifications
Displays high-tech ASCII cyber animation, comprehensive feature showcase,
telemetry, release highlights, and official GitHub repository link.
"""

from __future__ import annotations
import sys
import time
import platform
import asyncio
from typing import Optional

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live

from cord.ui.console import ui
from cord.core.config import CordConfig


ABOUT_ASCII_FRAMES = [
    r"""
  ██████╗  ██████╗ ██████╗  ██████╗ 
 ██╔════╝ ██╔═══██╗██╔══██╗██╔══██╗
 ██║      ██║   ██║██████╔╝██║  ██║
 ██║      ██║   ██║██╔══██╗██║  ██║
 ╚██████╗ ╚██████╔╝██║  ██║██████╔╝
  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═════╝ 
    """,
    r"""
  ██████╗  ██████╗ ██████╗  ██████╗ 
 ██╔════╝ ██╔═══██╗██╔══██╗██╔══██╗
 ██║      ██║   ██║██████╔╝██║  ██║
 ██║      ██║   ██║██╔══██╗██║  ██║
 ╚██████╗ ╚██████╔╝██║  ██║██████╔╝
  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═════╝ 
    """,
]

RELEASE_VERSION = "v1.4.0"
GITHUB_REPO_URL = "https://github.com/slimanerebouh83/cord"
AUTHOR_HANDLE = "slimanerebouh83"


async def show_about_screen(config: Optional[CordConfig] = None, animated: bool = True) -> None:
    """Displays the animated CORD system specs, features, and official GitHub link."""
    # System Telemetry Gathering
    py_ver = f"{platform.python_implementation()} {platform.python_version()}"
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    model_str = config.model if config else "Auto-Resolved"
    provider_str = config.provider.upper() if config else "Universal"
    perm_mode = (config.permission_mode.upper() if config else "YOLO")

    # If running interactively and animated is True, display a brief cyber reveal
    if animated and sys.stdout.isatty():
        gradient_styles = [
            ("bold #38bdf8", "⚡ Initializing Neural Kernel..."),
            ("bold #2563eb", "⚡ Loading AST Semantic Code Graph Engine..."),
            ("bold #818cf8", "⚡ Connecting Swarm Mesh Bus & Sentinel Council..."),
            ("bold #a855f7", "⚡ Ready. Welcome to CORD Autonomous Assistant!"),
        ]
        try:
            for style, status_msg in gradient_styles:
                ui.console.clear()
                logo_text = Text(ABOUT_ASCII_FRAMES[0], style=style)
                header_panel = Panel(
                    Text.assemble(logo_text, "\n", Text(f" {status_msg}", style="dim cyan")),
                    border_style="#38bdf8",
                    padding=(0, 2),
                )
                ui.console.print(header_panel)
                await asyncio.sleep(0.12)
        except Exception:
            pass

    ui.console.clear()

    # 1. Main Neon Logo Panel
    neon_logo = Text(ABOUT_ASCII_FRAMES[0], style="bold #38bdf8")
    title_text = Text.assemble(
        neon_logo,
        "\n",
        Text(" Autonomous Terminal Coding Agent & Computer Use System\n", style="bold bright_white"),
        Text(f" Release: {RELEASE_VERSION} (Frontier 2025/2026 Edition) │ Built with ❤️  by {AUTHOR_HANDLE}\n", style="bold #a855f7"),
        Text(f" 🌐 GitHub: {GITHUB_REPO_URL}", style="underline bold cyan"),
    )
    ui.console.print(Panel(title_text, border_style="#2563eb", padding=(0, 2)))

    # 2. System Specifications & Live Runtime Table
    spec_table = Table(
        title="🖥️  Live System & Runtime Telemetry",
        title_style="bold #38bdf8",
        border_style="#0284c7",
        show_header=True,
        header_style="bold bright_white on #0f172a",
        expand=True,
    )
    spec_table.add_column("Specification", style="bold cyan", width=26)
    spec_table.add_column("Current Runtime State", style="bright_white")

    spec_table.add_row("CORD Version", f"[bold green]{RELEASE_VERSION}[/bold green] (Next-Gen Autonomous Agent)")
    spec_table.add_row("Official Repository", f"[link={GITHUB_REPO_URL}]{GITHUB_REPO_URL}[/link]")
    spec_table.add_row("Lead Architect & Maintainer", f"[bold magenta]@{AUTHOR_HANDLE}[/bold magenta]")
    spec_table.add_row("Active LLM Model", f"[bold yellow]{model_str}[/bold yellow]")
    spec_table.add_row("Active LLM Provider", f"[bold cyan]{provider_str}[/bold cyan]")
    spec_table.add_row("Operating Permission Mode", f"[bold green]{perm_mode}[/bold green]")
    spec_table.add_row("Python Environment", py_ver)
    spec_table.add_row("Host OS / Platform", os_info)
    spec_table.add_row("Input Engine", "Dual-Engine (Docked Glowing Blue Box + Prompt-Toolkit)")
    spec_table.add_row("Tool Telemetry Mode", "Ultra-Sleek Single-Line Micro Cards")
    spec_table.add_row("Subagent Swarm Mesh", "Active (Interactive Mouse Observation Deck)")

    ui.console.print(spec_table)
    ui.console.print()

    # 3. Supercharged Features Showcase
    feat_table = Table(
        title="⚡ CORD Architectural Pillars & Frontier Capabilities",
        title_style="bold #a855f7",
        border_style="#7c3aed",
        show_header=True,
        header_style="bold bright_white on #1e1e38",
        expand=True,
    )
    feat_table.add_column("Capability Pillar", style="bold yellow", width=26)
    feat_table.add_column("Highlights & Description", style="white")

    feat_table.add_row(
        "🧠 Frontier Multi-LLM Brain",
        "Supports Claude 3.7 Sonnet (Hybrid Thinking), Gemini 2.5 Flash/Pro, DeepSeek R1/V3, OpenAI o3-mini, Ollama, Nvidia NIM, and custom proxies."
    )
    feat_table.add_row(
        "⚡ Surgical Execution & Micro Cards",
        "Ultra-compact single-line tool telemetry (Read, Edit, Run, Grep) without terminal clutter, AST diff syntax highlighting, and auto-rollback checkpoints."
    )
    feat_table.add_row(
        "🕸️ AST Code Graph & Blast Radius",
        "Real-time semantic AST cross-linking of callers, callees, classes, methods, and impacted unit tests before code changes."
    )
    feat_table.add_row(
        "🛡️ Community Sentinel Council",
        "Autonomous 4-role deliberation council (Architect, Security Auditor, UX Pragmatist, QA Lead) to triage issues, PRs, and RFC proposals."
    )
    feat_table.add_row(
        "📡 Tech Radar & MCP Marketplace",
        "1-click discovery and installation of official Model Context Protocol (MCP) servers and cutting-edge ecosystem tools."
    )
    feat_table.add_row(
        "🎨 Dynamic AI UI Customizer",
        "The AI can dynamically adapt themes, compact modes, and prompt layouts on command with immutable application identity security."
    )
    feat_table.add_row(
        "🐝 Swarm Mesh & Interactive Inspector",
        "Autonomous subagent dispatch with mouse-clickable live Observation Deck and instant Esc/Back navigation."
    )
    feat_table.add_row(
        "🖥️ NITEE Desktop Automation",
        "Complete GUI and computer use automation: mouse clicks, keyboard strokes, window management, and screen visual recognition."
    )

    ui.console.print(feat_table)
    ui.console.print(
        f"\n [bold #38bdf8]⭐ Star and contribute on GitHub:[/bold #38bdf8] [bold white underline]{GITHUB_REPO_URL}[/bold white underline]\n"
    )
