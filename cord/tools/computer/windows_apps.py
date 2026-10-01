"""
CORD Tool - windows_app
Native Windows 10 & 11 application launcher and system utilities automation.
"""

from __future__ import annotations
import os
import sys
import subprocess
import ctypes
from typing import Optional

from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.vision.safety import computer_safety, ensure_interactive_desktop

WINDOWS_APP_SHORTCUTS = {
    "notepad": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "settings": "ms-settings:",
    "explorer": "explorer.exe",
    "taskmgr": "taskmgr.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "paint": "mspaint.exe",
    "control": "control.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "browser": "msedge.exe",
}

class WindowsAppTool(BaseTool):
    name = "windows_app"
    description = "Launch, open, or control native Windows 10 & 11 applications and utilities (notepad, calc, settings, explorer, terminal, browser, minimize_all)."
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open", "open_url", "minimize_all", "open_settings"],
                "description": "Action to perform on Windows desktop"
            },
            "app_name": {
                "type": "string",
                "description": "Name or executable of the application (e.g. 'notepad', 'calc', 'settings', 'terminal', 'explorer')"
            },
            "target": {
                "type": "string",
                "description": "File path, URL, or settings page URI (e.g. 'https://github.com', 'ms-settings:windowsupdate')"
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        app_name: Optional[str] = None,
        target: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        if sys.platform != "win32":
            return ToolResult(success=False, output="", error="windows_app is designed specifically for Windows 10 and 11.")

        ensure_interactive_desktop()

        allowed, reason = computer_safety.validate_action(action)
        if not allowed:
            return ToolResult(success=False, output="", error=f"Windows action blocked: {reason}")

        try:
            if action == "open":
                app_key = (app_name or "").strip().lower()
                cmd = WINDOWS_APP_SHORTCUTS.get(app_key, app_key)
                if not cmd:
                    return ToolResult(success=False, output="", error="app_name is required for 'open' action.")

                try:
                    os.startfile(cmd)
                except Exception:
                    subprocess.Popen(cmd, shell=True)

                return ToolResult(success=True, output=f"Windows 10/11 application '{app_name}' launched successfully.")

            elif action == "open_url":
                url = (target or "").strip()
                if not url:
                    return ToolResult(success=False, output="", error="target URL is required for 'open_url'.")
                os.startfile(url)
                return ToolResult(success=True, output=f"Opened URL in default Windows browser: {url}")

            elif action == "open_settings":
                sub_uri = target or "ms-settings:"
                if not sub_uri.startswith("ms-settings:"):
                    sub_uri = f"ms-settings:{sub_uri}"
                os.startfile(sub_uri)
                return ToolResult(success=True, output=f"Opened Windows 10/11 Settings ({sub_uri}).")

            elif action == "minimize_all":
                # Toggle desktop via Win+D shell hook
                ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0) # Left Win key down
                ctypes.windll.user32.keybd_event(0x44, 0, 0, 0) # 'D' key down
                ctypes.windll.user32.keybd_event(0x44, 0, 2, 0) # 'D' key up
                ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0) # Left Win key up
                return ToolResult(success=True, output="Minimized all desktop windows (Win+D).")

            return ToolResult(success=False, output="", error=f"Unknown windows_app action: {action}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to execute Windows action: {e}")
