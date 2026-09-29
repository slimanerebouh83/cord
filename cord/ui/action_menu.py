"""
CORD UI - Interactive Visual Action Menu (/menu)
Provides an interactive dashboard to switch operational modes, AI models,
languages, input engines, and view workspace analytics.
"""

from __future__ import annotations
from typing import Any, Optional
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt

from cord.ui.console import ui
from cord.ui.i18n import t, i18n, LANGUAGES
from cord.core.modes import mode_manager, OperationalMode


def show_interactive_action_menu(repl: Any) -> None:
    """Renders an interactive menu dashboard for quick setting toggles."""
    cfg = repl.config
    current_prof = mode_manager.get_profile()
    curr_lang = cfg.language or "en"
    lang_info = LANGUAGES.get(curr_lang, LANGUAGES["en"])
    lang_display = f"{lang_info['flag']} {lang_info['name']}"

    table = Table(
        title="🎛️ [bold bright_cyan]CORD Quick Action Dashboard[/bold bright_cyan] │ [bold yellow]/menu[/bold yellow]",
        show_header=True,
        header_style="bold bright_cyan",
        border_style="#6366f1",
        box=None,
        padding=(0, 2),
    )
    table.add_column("#", style="bold yellow", justify="center", width=4)
    table.add_column("Setting / Action", style="bold white", width=26)
    table.add_column("Current Value", style="bold cyan", width=30)
    table.add_column("Description", style="dim", width=40)

    mode_name = current_prof.name
    short_model = cfg.model.split("/")[-1]

    table.add_row(
        "1", "🎯 Operational Mode", f"{current_prof.badge} {mode_name}",
        "Switch Fast / Computer / Coder / Agent"
    )
    table.add_row(
        "2", "🤖 Model & Preset", f"[magenta]{short_model}[/magenta]",
        "Switch AI Model or Ultra-Fast Presets"
    )
    table.add_row(
        "3", "🌐 Interface Language", lang_display,
        "Change CLI language (8 supported)"
    )
    table.add_row(
        "4", "⌨️ Input Engine", f"[green]{cfg.input_engine}[/green]",
        "Input Engine (native / advanced)"
    )
    table.add_row(
        "5", "⚡ Thinking / Reasoning", f"[yellow]{cfg.thinking_mode}[/yellow]",
        "Stream / Spinner / Off"
    )
    table.add_row(
        "6", "📊 Workspace Analytics", "[cyan]/stats[/cyan]",
        "Show project files, token stats, and health"
    )
    table.add_row(
        "7", "💾 Session History", "[cyan]/sessions[/cyan]",
        "View conversation history & checkpoints"
    )
    table.add_row(
        "8", "🧹 Clear Context", "[cyan]/clear[/cyan]",
        "Clear current conversation memory"
    )
    table.add_row(
        "9", "🔭 Model Scout Subagent", "[cyan]/scout[/cyan]",
        "Discover & register latest 2025/2026 models"
    )
    table.add_row(
        "s", "🤖 Subagents & Peer Swarm", "[bold magenta]/agents[/bold magenta]",
        "Browse equal peers & dedicated isolated chats"
    )
    table.add_row(
        "0", "🚪 Close Menu", "[dim]Esc / Enter[/dim]",
        "Return to interactive chat"
    )

    ui.console.print("\n")
    ui.console.print(Panel(table, border_style="bright_blue", padding=(0, 1)))

    choice = Prompt.ask(
        "[bold cyan]Select an option (0-9, s)[/bold cyan]",
        choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "s", "q", ""],
        default="0",
    ).strip().lower()

    if choice in ("0", "q", ""):
        ui.console.print("[dim]Closed menu.[/dim]\n")
        return

    # 1. Operational Mode
    if choice == "1":
        _handle_mode_selection(repl)

    # 2. Model & Preset
    elif choice == "2":
        _handle_model_selection(repl)

    # 3. Language
    elif choice == "3":
        _handle_language_selection(repl)

    # 4. Input Engine
    elif choice == "4":
        new_engine = "advanced" if cfg.input_engine == "native" else "native"
        repl._handle_slash_command(f"/input {new_engine}")

    # 5. Thinking Mode
    elif choice == "5":
        current_tm = getattr(cfg, "thinking_mode", "stream")
        cycle = {"stream": "spinner", "spinner": "off", "off": "stream"}
        next_tm = cycle.get(current_tm, "stream")
        repl._handle_slash_command(f"/thinking {next_tm}")

    # 6. Stats
    elif choice == "6":
        repl._handle_slash_command("/stats")

    # 7. Sessions
    elif choice == "7":
        repl._handle_slash_command("/sessions")

    # 8. Clear
    elif choice == "8":
        repl._handle_slash_command("/clear")

    # 9. Model Scout
    elif choice == "9":
        repl._handle_slash_command("/scout")

    # s. Subagents & Peer Swarm
    elif choice == "s":
        import asyncio
        coro = repl._handle_slash_command("/agents")
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            asyncio.run(coro)


def _handle_mode_selection(repl: Any) -> None:
    """Prompt user to select operational mode."""
    modes = [
        ("1", "fast", "⚡ Fast (Ultra-fast chat & swift direct actions)"),
        ("2", "computer", "🖥️ Computer (Autonomous Desktop, Mouse & Window Control)"),
        ("3", "coder", "💻 Coder (Software Engineering, Testing & Auto-Debugging)"),
        ("4", "agent", "🤖 Agent (Full Autonomous Coding, Computer-Use & Planning)"),
    ]
    sub_table = Table(title="🎯 Select Operational Mode", box=None, padding=(0, 2))
    sub_table.add_column("#", style="bold yellow")
    sub_table.add_column("Mode", style="bold bright_white")
    sub_table.add_column("Name", style="cyan")
    for num, code, label in modes:
        sub_table.add_row(num, code, label)

    ui.console.print(Panel(sub_table, border_style="cyan", padding=(0, 1)))
    sel = Prompt.ask("Choose mode (1-4)", choices=["1", "2", "3", "4", "q"], default="4").strip()
    mapping = {"1": "fast", "2": "computer", "3": "coder", "4": "agent"}
    if sel in mapping:
        repl._handle_slash_command(f"/mode {mapping[sel]}")


def _handle_model_selection(repl: Any) -> None:
    """Prompt user to select a saved model preset."""
    saved = repl.config.saved_models
    if not saved:
        ui.print_warning("No saved model presets found. Use /model <name> to set model.")
        return

    sub_table = Table(title="🤖 Select Model Preset", box=None, padding=(0, 2))
    sub_table.add_column("#", style="bold yellow")
    sub_table.add_column("Preset Name", style="bold bright_white")
    sub_table.add_column("Model ID", style="cyan")
    sub_table.add_column("Description", style="dim")

    keys = list(saved.keys())
    for idx, key in enumerate(keys, 1):
        info = saved[key]
        sub_table.add_row(str(idx), key, info.get("model", ""), info.get("name", ""))

    ui.console.print(Panel(sub_table, border_style="magenta", padding=(0, 1)))
    choices = [str(i) for i in range(1, len(keys) + 1)] + ["q"]
    sel = Prompt.ask("Choose preset number", choices=choices, default="1").strip()
    if sel.isdigit() and 1 <= int(sel) <= len(keys):
        chosen_key = keys[int(sel) - 1]
        repl._handle_slash_command(f"/model {chosen_key}")


def _handle_language_selection(repl: Any) -> None:
    """Prompt user to select interface language."""
    from cord.ui.welcome import LANGUAGE_ORDER
    sub_table = Table(title="🌐 Select Language", box=None, padding=(0, 2))
    sub_table.add_column("#", style="bold yellow")
    sub_table.add_column("Flag")
    sub_table.add_column("Language", style="bold bright_white")
    sub_table.add_column("Code", style="dim cyan")

    for idx, code in enumerate(LANGUAGE_ORDER, 1):
        info = LANGUAGES[code]
        sub_table.add_row(str(idx), info["flag"], info["name"], code)

    ui.console.print(Panel(sub_table, border_style="green", padding=(0, 1)))
    choices = [str(i) for i in range(1, len(LANGUAGE_ORDER) + 1)] + ["q"]
    sel = Prompt.ask("Choose language number", choices=choices, default="1").strip()
    if sel.isdigit() and 1 <= int(sel) <= len(LANGUAGE_ORDER):
        chosen_code = LANGUAGE_ORDER[int(sel) - 1]
        repl._handle_slash_command(f"/lang {chosen_code}")
