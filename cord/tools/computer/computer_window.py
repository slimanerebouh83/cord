"""
CORD Tool - computer_window
Window manipulation and app launching for Windows 10 & 11 with Foreground Lock Bypass
and native os.startfile integration.
"""

from __future__ import annotations
import os
import sys
import subprocess
import ctypes
from ctypes import wintypes
from typing import Optional, List, Dict

from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.vision.safety import computer_safety

SW_RESTORE = 9
WM_CLOSE = 0x0010

def _force_foreground(hwnd: int) -> bool:
    """Forces window to foreground bypassing Windows 10 & 11 foreground lock."""
    if sys.platform != "win32":
        return False
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, SW_RESTORE)

    cur_thread = ctypes.windll.kernel32.GetCurrentThreadId()
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    if cur_thread != target_thread:
        user32.AttachThreadInput(cur_thread, target_thread, True)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        user32.AttachThreadInput(cur_thread, target_thread, False)
    else:
        user32.SetForegroundWindow(hwnd)
    return True


class ComputerWindowTool(BaseTool):
    name = "computer_window"
    description = "Inspect and manipulate OS desktop windows: list open windows, bring a window to focus, launch an application, or close a window."
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "focus", "launch", "close"],
                "description": "Window action to perform"
            },
            "title_query": {
                "type": "string",
                "description": "Substring to search window title (used for focus or close)"
            },
            "hwnd": {
                "type": "integer",
                "description": "Specific Window Handle ID (optional alternative to title_query)"
            },
            "app_command": {
                "type": "string",
                "description": "Command or application path to launch (e.g. 'notepad', 'calc', 'ms-settings:', 'https://google.com')"
            }
        },
        "required": ["action"]
    }

    def _enum_windows(self) -> List[Dict[str, Any]]:
        user32 = ctypes.windll.user32
        windows = []

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def enum_windows_callback(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()
                    if title:
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        windows.append({
                            "hwnd": hwnd,
                            "title": title,
                            "pid": pid.value
                        })
            return True

        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return windows

    async def execute(
        self,
        action: str,
        title_query: str | None = None,
        hwnd: int | None = None,
        app_command: str | None = None,
        **kwargs
    ) -> ToolResult:
        try:
            if sys.platform != "win32":
                return ToolResult(success=False, output="", error="Native window management currently supports Windows.")

            allowed, reason = computer_safety.validate_action(action)
            if not allowed:
                return ToolResult(success=False, output="", error=f"Window action blocked: {reason}")

            user32 = ctypes.windll.user32

            if action == "list":
                windows = self._enum_windows()
                if not windows:
                    return ToolResult(success=True, output="No visible windows found.")
                lines = [f"Found {len(windows)} visible windows on desktop:"]
                for w in windows:
                    lines.append(f"  - [HWND: {w['hwnd']}, PID: {w['pid']}] \"{w['title']}\"")
                return ToolResult(success=True, output="\n".join(lines))

            elif action == "focus":
                target_hwnd = hwnd
                if not target_hwnd and title_query:
                    q = title_query.lower()
                    for w in self._enum_windows():
                        if q in w["title"].lower():
                            target_hwnd = w["hwnd"]
                            break

                if not target_hwnd:
                    return ToolResult(success=False, output="", error=f"Could not find window matching '{title_query}'")

                _force_foreground(target_hwnd)
                return ToolResult(success=True, output=f"Brought window (HWND: {target_hwnd}) to front using Windows foreground bypass.")

            elif action == "launch":
                if not app_command:
                    return ToolResult(success=False, output="", error="app_command is required for launch")

                launched_via = "subprocess"
                # On Windows, try native os.startfile first for instant app launch
                try:
                    os.startfile(app_command)
                    launched_via = "os.startfile"
                except Exception:
                    subprocess.Popen(app_command, shell=True)

                return ToolResult(success=True, output=f"Successfully launched application: '{app_command}' via {launched_via}")

            elif action == "close":
                target_hwnd = hwnd
                if not target_hwnd and title_query:
                    q = title_query.lower()
                    for w in self._enum_windows():
                        if q in w["title"].lower():
                            target_hwnd = w["hwnd"]
                            break

                if not target_hwnd:
                    return ToolResult(success=False, output="", error=f"Could not find window matching '{title_query}'")

                user32.PostMessageW(target_hwnd, WM_CLOSE, 0, 0)
                return ToolResult(success=True, output=f"Sent close request to window (HWND: {target_hwnd}).")

            return ToolResult(success=False, output="", error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Window operation failed: {e}")
