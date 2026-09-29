"""
CORD UI - Interactive Settings Editor
Allows updating API key, base URL, model, permissions, and theme during a session.
"""

from __future__ import annotations
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from cord.core.config import ConfigManager, PROVIDER_PRESETS
from cord.ui.console import ui
from cord.ui.onboarding import test_connection, run_onboarding_wizard


def show_settings_menu(config_mgr: ConfigManager) -> None:
    """Displays an interactive in-chat settings editor."""
    console = ui.console
    cfg = config_mgr.config

    while True:
        console.print("\n")
        table = Table(title="🛠️  CORD Configuration & Settings", show_header=True, header_style="bold cyan")
        table.add_column("#", style="bold yellow", width=4)
        table.add_column("Setting", style="bold white", width=20)
        table.add_column("Current Value", style="bold green", width=42)

        masked_key = f"...{cfg.api_key[-4:]}" if cfg.api_key and len(cfg.api_key) > 4 else ("(not set)" if not cfg.api_key else "***")
        
        table.add_row("1", "Provider", cfg.provider.upper())
        table.add_row("2", "Base URL", cfg.base_url)
        table.add_row("3", "API Key", masked_key)
        table.add_row("4", "Model", cfg.model)
        table.add_row("5", "Permission Mode", f"[bold]{cfg.permission_mode.upper()}[/bold]")
        table.add_row("6", "Theme", cfg.theme)
        table.add_row("7", "Run Full Setup Wizard", "Re-run initial onboarding")
        table.add_row("8", "Test API Connection", "Verify credentials")
        table.add_row("0", "Back to Chat", "Exit settings")

        console.print(table)

        choice = Prompt.ask("\nSelect option to change", choices=[str(i) for i in range(9)], default="0")

        if choice == "0":
            ui.print_info("Returning to chat...")
            break
        elif choice == "1":
            providers = list(PROVIDER_PRESETS.keys())
            console.print(f"Available: {', '.join(providers)}")
            p = Prompt.ask("Choose Provider", choices=providers, default=cfg.provider)
            preset = PROVIDER_PRESETS[p]
            cfg.provider = p
            cfg.base_url = preset["base_url"]
            cfg.model = preset["default_model"]
            cfg.api_format = preset["api_format"]
            config_mgr.save_global_config(cfg)
            ui.print_success(f"Provider switched to {p.upper()} (Base URL: {cfg.base_url}, Model: {cfg.model})")
        elif choice == "2":
            new_url = Prompt.ask("Enter Base URL", default=cfg.base_url).strip().rstrip("/")
            if new_url.endswith("/chat/completions"):
                new_url = new_url[:-17].rstrip("/")
            elif new_url.endswith("/chat"):
                new_url = new_url[:-5].rstrip("/")
            cfg.base_url = new_url
            config_mgr.save_global_config(cfg)
            ui.print_success(f"Base URL updated to {new_url}")
        elif choice == "3":
            new_key = Prompt.ask("Enter new API Key", password=True).strip()
            if new_key:
                cfg.api_key = new_key
                config_mgr.save_global_config(cfg)
                ui.print_success("API Key updated and saved!")
        elif choice == "4":
            new_model = Prompt.ask("Enter Model Name", default=cfg.model).strip()
            cfg.model = new_model
            config_mgr.save_global_config(cfg)
            ui.print_success(f"Model updated to {new_model}")
        elif choice == "5":
            mode = Prompt.ask(
                "Select Permission Mode (balanced, strict, yolo)",
                choices=["balanced", "strict", "yolo"],
                default=cfg.permission_mode,
            )
            cfg.permission_mode = mode
            config_mgr.save_global_config(cfg)
            ui.print_success(f"Permission Mode updated to {mode.upper()}")
        elif choice == "6":
            theme = Prompt.ask(
                "Select Theme (cyberpunk, monokai, dracula, nord)",
                choices=["cyberpunk", "monokai", "dracula", "nord"],
                default=cfg.theme,
            )
            cfg.theme = theme
            config_mgr.save_global_config(cfg)
            ui.set_theme(theme)
            ui.print_success(f"Theme updated to {theme}")
        elif choice == "7":
            run_onboarding_wizard(config_mgr)
            cfg = config_mgr.config
        elif choice == "8":
            test_connection(cfg)
