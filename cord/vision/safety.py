"""CORD Vision & Computer-Use Safety Controller"""
from __future__ import annotations
import sys
import ctypes
from enum import Enum

class ComputerSafetyLevel(str, Enum):
    OFF = "OFF"                     # No computer interaction or screenshots
    READ_ONLY = "READ_ONLY"         # Screenshots and window listings only
    INTERACTION = "INTERACTION"     # Mouse & keyboard permitted with interactive safety checks
    FULL_CONTROL = "FULL_CONTROL"   # Autonomous computer use with active kill switch

def ensure_interactive_desktop():
    """Attaches current thread to interactive user desktop (WinSta0\\default)."""
    if sys.platform != "win32":
        return
    try:
        DESKTOP_ALL = 0x01FF
        hDesk = ctypes.windll.user32.OpenDesktopW("default", 0, False, DESKTOP_ALL)
        if hDesk:
            ctypes.windll.user32.SetThreadDesktop(hDesk)
    except Exception:
        pass


class ComputerSafetyManager:
    _instance: ComputerSafetyManager | None = None

    def __init__(self):
        self.safety_level: ComputerSafetyLevel = ComputerSafetyLevel.FULL_CONTROL
        self._emergency_stopped: bool = False
        self._screen_width, self._screen_height = self._get_screen_resolution()

    @classmethod
    def get_instance(cls) -> ComputerSafetyManager:
        if cls._instance is None:
            cls._instance = ComputerSafetyManager()
        return cls._instance

    def _get_screen_resolution(self) -> tuple[int, int]:
        if sys.platform == "win32":
            try:
                ensure_interactive_desktop()
                user32 = ctypes.windll.user32
                # Enable DPI awareness to get real physical pixels
                try:
                    user32.SetProcessDPIAware()
                except Exception:
                    pass
                w = user32.GetSystemMetrics(0)
                h = user32.GetSystemMetrics(1)
                if w > 0 and h > 0:
                    return (w, h)
            except Exception:
                pass
        return (1920, 1080)

    @property
    def virtual_bounds(self) -> tuple[int, int, int, int]:
        """Returns (min_x, min_y, max_x, max_y) covering multi-monitor setups."""
        if sys.platform == "win32":
            try:
                ensure_interactive_desktop()
                user32 = ctypes.windll.user32
                vx = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
                vy = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
                vw = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
                vh = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
                if vw > 0 and vh > 0:
                    return (vx, vy, vx + vw, vy + vh)
            except Exception:
                pass
        w, h = self.screen_size
        return (0, 0, w, h)

    @property
    def screen_size(self) -> tuple[int, int]:
        # Refresh in case of resolution changes
        self._screen_width, self._screen_height = self._get_screen_resolution()
        return (self._screen_width, self._screen_height)

    def trigger_emergency_stop(self, reason: str = "User initiated kill switch"):
        self._emergency_stopped = True

    def reset_emergency_stop(self):
        self._emergency_stopped = False

    def is_stopped(self) -> bool:
        return self._emergency_stopped

    def validate_action(self, action_type: str, x: int | float | None = None, y: int | float | None = None) -> tuple[bool, str]:
        """Validate whether an action is permitted under the current safety level."""
        if self._emergency_stopped:
            return False, "Emergency kill switch is ACTIVE. All computer use actions blocked."

        if self.safety_level == ComputerSafetyLevel.OFF:
            return False, "Computer use is currently set to OFF."

        if self.safety_level == ComputerSafetyLevel.READ_ONLY:
            if action_type not in ["screenshot", "list_windows", "get_active_window"]:
                return False, f"Action '{action_type}' blocked: Safety level is READ_ONLY."

        if x is not None and y is not None:
            # Allow normalized coordinates (0.0 to 1.0 floats)
            if isinstance(x, float) and isinstance(y, float) and 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                return True, "Action permitted"

            w, h = self.screen_size
            min_x, min_y, max_x, max_y = self.virtual_bounds
            if x < min_x or x >= max_x or y < min_y or y >= max_y:
                return False, f"Coordinates ({x}, {y}) out of screen bounds ({w}x{h})."

        return True, "Action permitted"

computer_safety = ComputerSafetyManager.get_instance()
