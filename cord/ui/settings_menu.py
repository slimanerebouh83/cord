"""
CORD UI - Interactive Settings Editor & Configuration Dashboard
Supports full mouse-clicking on rows and buttons, numeric keypad shortcuts,
theme customizer (including cord_blue), language switching (Arabic, English, etc.),
and real-time credentials testing without exceptions.
"""

from __future__ import annotations
import sys
from typing import Optional, List, Any

from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel

from cord.core.config import ConfigManager, PROVIDER_PRESETS, normalize_base_url
from cord.ui.console import ui, THEMES
from cord.ui.i18n import i18n, LANGUAGES
from cord.ui.onboarding import test_connection, run_onboarding_wizard


def _is_interactive_console() -> bool:
    """Checks whether the console is connected to an interactive TTY."""
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def _run_mouse_settings_menu(config_mgr: ConfigManager) -> str:
    """Interactive mouse-clickable application for the settings menu using prompt_toolkit."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.layout import Layout
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
    from prompt_toolkit.styles import Style

    cfg = config_mgr.config
    masked_key = f"...{cfg.api_key[-4:]}" if cfg.api_key and len(cfg.api_key) > 4 else ("(not set)" if not cfg.api_key else "***")
    current_lang = getattr(cfg, "language", "en")
    lang_info = LANGUAGES.get(current_lang, {"name": current_lang, "flag": "🌐"})
    lang_display = f"{lang_info.get('flag', '')} {lang_info.get('name', current_lang)}"

    kb = KeyBindings()

    def make_click_handler(choice_val: str):
        def _on_click(mouse_event: MouseEvent):
            if mouse_event.event_type in (MouseEventType.MOUSE_UP, MouseEventType.MOUSE_DOWN):
                from prompt_toolkit.application.current import get_app
                app = get_app()
                app.exit(result=choice_val)
        return _on_click

    # Keypad and numeric key shortcuts
    @kb.add("0")
    @kb.add("q")
    @kb.add("escape")
    def _(event):
        event.app.exit(result="0")

    for i in range(1, 10):
        def _bind_key(num_str: str):
            def _handler(event):
                event.app.exit(result=num_str)
            return _handler
        kb.add(str(i))(_bind_key(str(i)))

    fragments: List[Any] = []
    fragments.append(("class:header", "╔═════════════════════════════════════════════════════════════════════════════════════════════════════╗\n"))
    fragments.append(("class:header", "║ 🛠️  CORD Configuration & Settings Dashboard                                                        ║\n"))
    fragments.append(("class:header", "║ 🖱️  MOUSE & KEYPAD: Click on any setting row below or press [0-9] on your keyboard to edit!          ║\n"))
    fragments.append(("class:header", "╠═════╦═════════════════════════╦════════════════════════════════════════════════════════════════════╣\n"))
    fragments.append(("class:tbl_head", "║  #  ║ Setting                 ║ Current Value / Action                                             ║\n"))
    fragments.append(("class:header", "╠═════╬═════════════════════════╬════════════════════════════════════════════════════════════════════╣\n"))

    rows = [
        ("1", "Provider", cfg.provider.upper(), "class:row_odd"),
        ("2", "Base URL", (cfg.base_url or "(default)")[:56], "class:row_even"),
        ("3", "API Key", masked_key, "class:row_odd"),
        ("4", "Model", cfg.model[:56], "class:row_even"),
        ("5", "Permission Mode", cfg.permission_mode.upper(), "class:row_odd"),
        ("6", "UI Theme", cfg.theme, "class:row_even"),
        ("7", "Interface Language", lang_display, "class:row_odd"),
        ("8", "Test API Connection", "Verify active provider credentials & endpoint", "class:row_even"),
        ("9", "Full Setup Wizard", "Re-run interactive onboarding wizard", "class:row_odd"),
    ]

    for num, label, val, row_style in rows:
        line_str = f"║  {num}  ║ {label:<23} ║ {val:<66} ║\n"
        fragments.append((row_style, line_str, make_click_handler(num)))

    fragments.append(("class:header", "╠═════╩═════════════════════════╩════════════════════════════════════════════════════════════════════╣\n"))
    fragments.append(("class:btn_exit", "║  [ 0. ⬅️  Back to Chat ]  (Click here or press Esc / 0 to return)                                   ║\n", make_click_handler("0")))
    fragments.append(("class:header", "╚═════════════════════════════════════════════════════════════════════════════════════════════════════╝\n\n"))

    style = Style.from_dict({
        "header": "fg:#38bdf8 bold",
        "tbl_head": "fg:#60a5fa bold",
        "row_odd": "fg:#ffffff bg:#0f172a",
        "row_even": "fg:#f1f5f9 bg:#1e293b",
        "btn_exit": "fg:#ffffff bg:#2563eb bold",
    })

    output = None
    try:
        from prompt_toolkit.output import create_output
        output = create_output()
    except Exception:
        from prompt_toolkit.output import DummyOutput
        output = DummyOutput()

    control = FormattedTextControl(fragments)
    app = Application(
        layout=Layout(HSplit([Window(content=control)])),
        key_bindings=kb,
        style=style,
        mouse_support=True,
        full_screen=False,
        output=output,
    )

    try:
        import asyncio
        if asyncio.get_event_loop().is_running():
            # In running event loop, this is called synchronously or via future
            pass
    except Exception:
        pass

    return app.run() or "0"


def show_settings_menu(config_mgr: ConfigManager) -> None:
    """Displays an interactive in-chat settings editor with mouse and keypad support."""
    console = ui.console
    cfg = config_mgr.config

    while True:
        choice = "0"
        if _is_interactive_console():
            try:
                choice = _run_mouse_settings_menu(config_mgr)
            except Exception:
                choice = None

        if not choice:
            console.print("\n")
            table = Table(
                title="🛠️  CORD Configuration & Settings",
                show_header=True,
                header_style="bold cyan",
                border_style="#2563eb",
            )
            table.add_column("#", style="bold yellow", width=4)
            table.add_column("Setting", style="bold white", width=22)
            table.add_column("Current Value", style="bold green")

            masked_key = f"...{cfg.api_key[-4:]}" if cfg.api_key and len(cfg.api_key) > 4 else ("(not set)" if not cfg.api_key else "***")
            current_lang = getattr(cfg, "language", "en")
            lang_info = LANGUAGES.get(current_lang, {"name": current_lang, "flag": "🌐"})
            lang_display = f"{lang_info.get('flag', '')} {lang_info.get('name', current_lang)}"

            table.add_row("1", "Provider", cfg.provider.upper())
            table.add_row("2", "Base URL", cfg.base_url or "(default)")
            table.add_row("3", "API Key", masked_key)
            table.add_row("4", "Model", cfg.model)
            table.add_row("5", "Permission Mode", f"[bold]{cfg.permission_mode.upper()}[/bold]")
            table.add_row("6", "UI Theme", cfg.theme)
            table.add_row("7", "Interface Language", lang_display)
            table.add_row("8", "Test API Connection", "Verify active credentials")
            table.add_row("9", "Full Setup Wizard", "Re-run initial onboarding")
            table.add_row("0", "Back to Chat", "Exit settings")

            console.print(table)
            choice = Prompt.ask("\nSelect option [0-9]", choices=[str(i) for i in range(10)], default="0")

        if choice == "0":
            ui.print_info("Returning to chat...")
            break

        elif choice == "1":
            providers = list(PROVIDER_PRESETS.keys())
            console.print(f"Available Providers: {', '.join(providers)}")
            p = Prompt.ask("Choose Provider", choices=providers, default=cfg.provider)
            preset = PROVIDER_PRESETS[p]
            cfg.provider = p
            cfg.base_url = preset["base_url"]
            cfg.model = preset["default_model"]
            cfg.api_format = preset["api_format"]
            config_mgr.save_global_config(cfg)
            ui.print_success(f"Provider switched to {p.upper()} (Base URL: {cfg.base_url}, Model: {cfg.model})")

        elif choice == "2":
            entered_url = Prompt.ask("Enter Base URL", default=cfg.base_url)
            new_url, notice = normalize_base_url(entered_url)
            if notice:
                ui.print_info(f"[yellow]{notice}[/yellow]")
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
            if new_model:
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
            available_themes = list(THEMES.keys())
            theme = Prompt.ask(
                f"Select Theme ({', '.join(available_themes)})",
                choices=available_themes,
                default=cfg.theme if cfg.theme in available_themes else "cord_blue",
            )
            cfg.theme = theme
            config_mgr.save_global_config(cfg)
            ui.set_theme(theme)
            ui.print_success(f"Theme updated to {theme}")

        elif choice == "7":
            lang_codes = list(LANGUAGES.keys())
            lang_list_str = ", ".join([f"{c} ({LANGUAGES[c]['name']})" for c in lang_codes])
            console.print(f"Available Languages: {lang_list_str}")
            chosen_lang = Prompt.ask("Choose Language code", choices=lang_codes, default=getattr(cfg, "language", "ar")).strip().lower()
            if i18n.set_language(chosen_lang):
                cfg.language = chosen_lang
                config_mgr.save_global_config(cfg)
                ui.print_success(f"Interface language updated to {LANGUAGES[chosen_lang]['name']} ({chosen_lang})")

        elif choice == "8":
            test_connection(cfg)

        elif choice == "9":
            run_onboarding_wizard(config_mgr)
            cfg = config_mgr.config
