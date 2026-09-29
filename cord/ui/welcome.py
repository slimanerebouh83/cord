"""
CORD UI - First-Run Welcome & Language Selection Wizard
Guides new users to choose their language on first startup and configures CORD preferences.
"""

from __future__ import annotations
from typing import Optional
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt

from cord.ui.console import ui
from cord.ui.i18n import LANGUAGES, i18n, t
from cord.core.config import ConfigManager

LANGUAGE_ORDER = ["en", "fr", "es", "de", "zh", "ja", "ru", "tr", "ar"]

def show_first_run_language_wizard(config_mgr: ConfigManager) -> str:
    """
    Renders an interactive onboarding screen to choose the interface language.
    Saves the choice to ~/.cord/config.json and updates the active runtime.
    """
    console = ui.console

    # Welcome Header
    header_text = Text()
    header_text.append("✨ Welcome to CORD CLI ✨\n", style="bold bright_cyan")
    header_text.append("Autonomous Software Engineering & Computer-Use Agent\n\n", style="bold #a855f7")
    header_text.append("Please select your interface language:", style="bright_white")

    console.print(
        Panel(
            header_text,
            border_style="bright_cyan",
            padding=(1, 2),
            title="[bold yellow]🚀 CORD Onboarding[/bold yellow]",
        )
    )

    # Languages Table
    table = Table(show_header=True, header_style="bold bright_cyan", box=None, padding=(0, 2))
    table.add_column("#", style="bold yellow", justify="center", width=4)
    table.add_column("Flag", justify="center", width=6)
    table.add_column("Language", style="bold bright_white")
    table.add_column("Code", style="dim cyan", width=8)

    for idx, code in enumerate(LANGUAGE_ORDER, 1):
        info = LANGUAGES[code]
        table.add_row(str(idx), info["flag"], info["name"], f"({code})")

    console.print(Panel(table, border_style="dim cyan", padding=(0, 1)))

    choices = [str(i) for i in range(1, len(LANGUAGE_ORDER) + 1)] + LANGUAGE_ORDER

    selected_idx_or_code = Prompt.ask(
        "[bold cyan]Select language[/bold cyan]",
        choices=choices,
        default="1",
    ).strip().lower()

    if selected_idx_or_code.isdigit():
        idx = int(selected_idx_or_code) - 1
        chosen_code = LANGUAGE_ORDER[idx]
    else:
        chosen_code = selected_idx_or_code if selected_idx_or_code in LANGUAGES else "en"

    # Set and persist config globally
    i18n.set_language(chosen_code)
    cfg = config_mgr.config
    cfg.language = chosen_code
    config_mgr.save_global_config(cfg)

    lang_name = f"{LANGUAGES[chosen_code]['flag']} {LANGUAGES[chosen_code]['name']}"
    msg = t('language_set', lang=lang_name)
    ui.print_success(f"\n{msg}\n")

    return chosen_code

