"""
CORD UI - Interactive Onboarding Setup Wizard
Launched on first run or via /settings command.
Guides the user through Base URL, API Key, Model, Provider, and Permission configuration.
"""

from __future__ import annotations
import sys
from typing import Optional
import httpx
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.table import Table

from cord.core.config import CordConfig, ConfigManager, PROVIDER_PRESETS
from cord.ui.console import ui, CordConsole, LOGO_ASCII, SUBTITLE


def run_onboarding_wizard(config_mgr: ConfigManager) -> CordConfig:
    """Runs the interactive first-time setup wizard in the terminal."""
    console = ui.console

    console.clear()
    
    # Welcome banner
    welcome_text = Text()
    welcome_text.append(LOGO_ASCII, style="header")
    welcome_text.append(f"\n{SUBTITLE}\n\n", style="subtle")
    welcome_text.append("👋 Welcome to CORD! Let's get your coding assistant configured.\n", style="bold bright_white")
    welcome_text.append("You will configure your LLM Provider, API Key, Base URL, and Security Permissions.\n", style="dim")

    console.print(Panel(welcome_text, border_style="accent", padding=(1, 2)))

    # Step 1: Select Provider
    console.print("\n[header]Step 1 of 5: Choose your LLM Provider[/header]")
    provider_table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    provider_table.add_column("#", style="bold yellow", width=4)
    provider_table.add_column("Provider", style="bold white", width=22)
    provider_table.add_column("Default Base URL", style="dim cyan", width=36)
    provider_table.add_column("Top Model", style="dim green", width=30)

    providers_list = list(PROVIDER_PRESETS.keys())
    for idx, key in enumerate(providers_list, 1):
        p = PROVIDER_PRESETS[key]
        provider_table.add_row(str(idx), p["name"], p["base_url"], p["default_model"])

    console.print(provider_table)

    choice = Prompt.ask(
        "\nSelect provider number or name",
        choices=[str(i) for i in range(1, len(providers_list) + 1)] + providers_list,
        default="1",
    )

    if choice.isdigit():
        selected_key = providers_list[int(choice) - 1]
    else:
        selected_key = choice.lower()

    preset = PROVIDER_PRESETS.get(selected_key, PROVIDER_PRESETS["openrouter"])
    provider_name = preset["name"]
    ui.print_success(f"Selected Provider: [bold]{provider_name}[/bold]")

    # Step 2: Base URL
    console.print(f"\n[header]Step 2 of 5: API Base URL[/header]")
    console.print(f"[dim]Default for {provider_name} is [cyan]{preset['base_url']}[/cyan][/dim]")
    base_url = Prompt.ask(
        "Enter Base URL",
        default=preset["base_url"],
    ).strip()

    # Step 3: API Key
    console.print(f"\n[header]Step 3 of 5: API Key[/header]")
    if selected_key == "ollama":
        console.print("[dim]Local Ollama does not require an API key by default.[/dim]")
        api_key = Prompt.ask("API Key (leave blank for local Ollama)", default="ollama-local").strip()
    else:
        console.print(f"[dim]Get your API key at: [underline]{preset.get('api_key_url', 'Provider dashboard')}[/underline][/dim]")
        existing_key = config_mgr.config.api_key
        prompt_hint = f"API Key" if not existing_key else f"API Key [dim](leave empty to keep current: ...{existing_key[-4:]})[/dim]"
        api_key = Prompt.ask(prompt_hint, password=True, default=existing_key).strip()

    # Step 4: Model Selection
    console.print(f"\n[header]Step 4 of 5: Model Selection[/header]")
    console.print("[dim]Recommended models for this provider:[/dim]")
    for m in preset["models"]:
        console.print(f"  • [cyan]{m}[/cyan]")
    
    model = Prompt.ask(
        "Enter Model Name",
        default=preset["default_model"],
    ).strip()

    # Step 5: Permission & Security Mode
    console.print(f"\n[header]Step 5 of 5: Agent Permissions & Security Level[/header]")
    console.print("Choose how autonomous CORD should be in your terminal:")
    console.print("  [bold green][1] Yolo (Autonomous - Recommended)[/bold green]: 100% automatic pre-approval. Never pauses to ask.")
    console.print("  [bold yellow][2] Balanced[/bold yellow]: Auto-approves file reads. Prompts for shell commands and file edits.")
    console.print("  [bold red][3] Strict[/bold red]: Prompts for your approval before ANY tool or action.")

    mode_choice = Prompt.ask(
        "Select Permission Mode",
        choices=["1", "2", "3", "yolo", "balanced", "strict"],
        default="1",
    )
    mode_map = {"1": "yolo", "2": "balanced", "3": "strict"}
    perm_mode = mode_map.get(mode_choice, mode_choice)
    ui.print_success(f"Permission Mode set to: [bold]{perm_mode.upper()}[/bold]")

    # Theme selection
    theme = Prompt.ask(
        "\nSelect TUI Theme (cyberpunk, monokai, dracula, nord)",
        choices=["cyberpunk", "monokai", "dracula", "nord"],
        default="cyberpunk",
    )

    # Construct new config
    new_config = CordConfig(
        provider=selected_key,
        base_url=base_url,
        api_key=api_key,
        model=model,
        api_format=preset["api_format"],
        permission_mode=perm_mode,
        theme=theme,
    )

    # Optional Connection Test
    console.print("\n[dim]Would you like to test the API connection now?[/dim]")
    do_test = Confirm.ask("Test connection to LLM endpoint?", default=True)
    if do_test:
        test_connection(new_config)

    # Save to global config
    config_mgr.save_global_config(new_config)
    config_mgr.config = new_config
    ui.set_theme(theme)

    console.print("\n" + "=" * 60)
    ui.print_success("[bold green]Setup Complete! Settings saved to ~/.cord/config.json[/bold green]")
    console.print("[dim]You can change these anytime by typing [bold]/settings[/bold] in the chat.[/dim]")
    console.print("=" * 60 + "\n")

    return new_config


def test_connection(config: CordConfig) -> bool:
    """Performs a lightweight probe to verify API credentials and reachability."""
    console = ui.console
    with console.status("[bold cyan]Testing connection to LLM API...[/bold cyan]", spinner="dots"):
        try:
            headers = {"Authorization": f"Bearer {config.api_key}"}
            if config.extra_headers:
                headers.update(config.extra_headers)

            clean_base = config.base_url.strip().rstrip("/")
            if clean_base.endswith("/chat/completions"):
                clean_base = clean_base[:-17].rstrip("/")
            elif clean_base.endswith("/chat"):
                clean_base = clean_base[:-5].rstrip("/")

            if config.api_format == "anthropic":
                headers["x-api-key"] = config.api_key
                headers["anthropic-version"] = "2023-06-01"
                test_url = f"{clean_base}/models"
            else:
                test_url = f"{clean_base}/models"

            # Quick models check or fallback to chat completions
            response = httpx.get(test_url, headers=headers, timeout=8.0)
            if response.status_code in (200, 201):
                ui.print_success(f"Connection Successful! Endpoint responded with HTTP {response.status_code}.")
                return True
            elif response.status_code == 401:
                ui.print_error("Connection Failed: HTTP 401 Unauthorized. Check your API key!")
                return False
            elif response.status_code == 404:
                # Some custom providers don't have /models endpoint; that's fine
                ui.print_warning(f"Endpoint reached (HTTP 404 on /models, but server responded). Will proceed with configured URL.")
                return True
            else:
                ui.print_warning(f"Endpoint responded with status {response.status_code}: {response.text[:120]}")
                return True
        except Exception as e:
            ui.print_warning(f"Connection probe error ({e}). If your server is offline or local, you can still proceed.")
            return False
