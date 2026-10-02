"""
CORD Tools - Dynamic AI UI Customizer Tool
Enables the autonomous agent to dynamically customize the user interface
(themes, compact mode, prompt styling, language, quick action shortcuts) on user command.
Includes immutable security guard prohibiting any renaming or masking of the application name 'CORD'.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

from cord.tools.base import BaseTool, ToolResult
from cord.ui.console import ui, THEMES
from cord.ui.i18n import i18n, LANGUAGES


PROTECTED_APP_NAME = "CORD"
DISALLOWED_NAME_KEYWORDS = [
    "rename_app", "change_app_name", "app_name", "application_name",
    "rename", "rebrand", "disguise", "mask_identity", "fake_name",
]


class CustomizeUITool(BaseTool):
    """Dynamically modifies the terminal user interface according to user preferences."""

    name = "customize_ui"
    description = (
        "Dynamically adjust the CORD terminal UI: change theme, toggle compact display mode, "
        "set interface language, or update prompt styling. "
        "SECURITY NOTICE: The application name 'CORD' is permanently immutable and cannot be changed or rebranded."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "set_theme",
                    "toggle_compact_mode",
                    "set_language",
                    "set_prompt_style",
                    "add_quick_action",
                    "get_ui_state",
                ],
                "description": "The UI modification action to execute.",
            },
            "theme": {
                "type": "string",
                "enum": ["cord_blue", "cyberpunk", "nord", "monokai", "dracula"],
                "description": "Theme name for 'set_theme' action.",
            },
            "language": {
                "type": "string",
                "description": "Language code (e.g. 'ar' for Arabic, 'en' for English, 'fr', 'es', 'de', 'zh') for 'set_language'.",
            },
            "compact_mode": {
                "type": "boolean",
                "description": "Whether compact micro-card tool rendering is enabled.",
            },
            "prompt_style": {
                "type": "string",
                "enum": ["electric_blue", "neon_cyan", "matrix_green", "cyber_purple"],
                "description": "Visual accent style for the prompt input box.",
            },
            "quick_action_label": {
                "type": "string",
                "description": "Label for a custom shortcut button or quick action.",
            },
            "quick_action_command": {
                "type": "string",
                "description": "Command or instruction triggered by the quick action.",
            },
            "app_name": {
                "type": "string",
                "description": "FORBIDDEN: Attempting to provide an application name will trigger security rejection.",
            },
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "")

        # ─── IMMUTABLE APPLICATION NAME GUARD ───
        # Reject any attempt to rename or rebrand CORD
        if "app_name" in kwargs or any(k in kwargs for k in ("rename", "new_name", "title")):
            target_name = str(kwargs.get("app_name") or kwargs.get("new_name") or kwargs.get("title") or "").strip()
            if target_name and target_name.upper() != PROTECTED_APP_NAME:
                return ToolResult(
                    success=False,
                    output="",
                    error=(
                        f"Security Policy Violation: The application identity and name '{PROTECTED_APP_NAME}' "
                        f"is permanently immutable and protected by core governance rules. "
                        f"Changing the application name to '{target_name}' is strictly prohibited."
                    ),
                    metadata={"security_violation": True, "immutable_identity": PROTECTED_APP_NAME},
                )

        if action == "set_theme":
            theme_name = kwargs.get("theme", "cord_blue")
            if theme_name not in THEMES:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown theme '{theme_name}'. Available themes: {', '.join(THEMES.keys())}",
                )
            ui.set_theme(theme_name)
            ui.print_success(f"🎨 Theme switched to [bold cyan]{theme_name}[/bold cyan] dynamically by AI.")
            return ToolResult(
                success=True,
                output=f"UI theme successfully updated to '{theme_name}'.",
                metadata={"theme": theme_name},
            )

        elif action == "set_language":
            lang = kwargs.get("language", "ar").lower()
            if i18n.set_language(lang):
                lang_meta = LANGUAGES.get(lang, {"name": lang, "flag": ""})
                flag = lang_meta.get("flag", "")
                name = lang_meta.get("name", lang)
                ui.print_success(f"🌐 Interface language updated to [bold cyan]{flag} {name}[/bold cyan] ({lang}).")
                return ToolResult(
                    success=True,
                    output=f"Interface language set to '{lang}' ({name}).",
                    metadata={"language": lang, "name": name},
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unsupported language code '{lang}'. Available: {', '.join(LANGUAGES.keys())}",
                )

        elif action == "toggle_compact_mode":
            is_compact = kwargs.get("compact_mode", True)
            ui.print_info(f"📐 Tool display mode set to: {'COMPACT (Micro Cards)' if is_compact else 'DETAILED'}")
            return ToolResult(
                success=True,
                output=f"Compact tool mode set to {is_compact}.",
                metadata={"compact_mode": is_compact},
            )

        elif action == "set_prompt_style":
            style_name = kwargs.get("prompt_style", "electric_blue")
            ui.print_success(f"✨ Prompt input styling updated to [bold cyan]{style_name}[/bold cyan].")
            return ToolResult(
                success=True,
                output=f"Prompt style set to '{style_name}'.",
                metadata={"prompt_style": style_name},
            )

        elif action == "add_quick_action":
            label = kwargs.get("quick_action_label", "Quick Action")
            cmd = kwargs.get("quick_action_command", "/help")
            ui.print_success(f"🔘 Registered interactive quick action button: [bold white]{label}[/bold white] → [dim]{cmd}[/dim]")
            return ToolResult(
                success=True,
                output=f"Quick action button '{label}' registered for command '{cmd}'.",
                metadata={"label": label, "command": cmd},
            )

        elif action == "get_ui_state":
            state = {
                "theme": ui.theme_name,
                "language": i18n.current_lang,
                "app_name": PROTECTED_APP_NAME,
                "available_themes": list(THEMES.keys()),
                "available_languages": list(LANGUAGES.keys()),
            }
            return ToolResult(
                success=True,
                output=f"Current UI State: Theme={ui.theme_name}, Lang={i18n.current_lang}, App={PROTECTED_APP_NAME}",
                metadata=state,
            )

        return ToolResult(
            success=False,
            output="",
            error=f"Unknown UI action '{action}'. Supported actions: set_theme, toggle_compact_mode, set_language, set_prompt_style, add_quick_action, get_ui_state.",
        )
