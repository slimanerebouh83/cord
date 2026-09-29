"""CORD Utils - Window Manager for Terminal Stealth Hiding and Restoring"""
from __future__ import annotations
import ctypes
import os
from typing import Optional

SW_HIDE = 0
SW_NORMAL = 1
SW_SHOW = 5
SW_RESTORE = 9

class WindowManager:
    """Manages console window visibility via Win32 APIs for stealth desktop execution."""

    def __init__(self) -> None:
        self._saved_hwnd: Optional[int] = None
        self._is_hidden: bool = False
        self._init_hwnd()

    def _init_hwnd(self) -> None:
        try:
            if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "kernel32"):
                h = ctypes.windll.kernel32.GetConsoleWindow()
                if h and ctypes.windll.user32.IsWindow(h):
                    self._saved_hwnd = h
                else:
                    # Fallback to foreground window
                    fg = ctypes.windll.user32.GetForegroundWindow()
                    if fg and ctypes.windll.user32.IsWindow(fg):
                        self._saved_hwnd = fg
        except Exception:
            self._saved_hwnd = None

    def get_hwnd(self) -> Optional[int]:
        if self._saved_hwnd and ctypes.windll.user32.IsWindow(self._saved_hwnd):
            return self._saved_hwnd
        self._init_hwnd()
        return self._saved_hwnd

    def hide_terminal(self) -> bool:
        """Hides the terminal window completely from screen and taskbar."""
        hwnd = self.get_hwnd()
        if not hwnd:
            return False
        try:
            ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
            self._is_hidden = True
            return True
        except Exception:
            return False

    def show_terminal(self) -> bool:
        """Restores and brings the terminal window back into foreground."""
        hwnd = self.get_hwnd()
        if not hwnd:
            return False
        try:
            ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
            ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            self._is_hidden = False
            return True
        except Exception:
            return False

    def toggle_terminal(self) -> bool:
        """Toggles between hidden and visible."""
        if self._is_hidden:
            self.show_terminal()
            return False  # False means not hidden now
        else:
            self.hide_terminal()
            return True  # True means hidden now

    @property
    def is_hidden(self) -> bool:
        return self._is_hidden

window_manager = WindowManager()
