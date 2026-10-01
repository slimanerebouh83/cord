"""
CORD Tool - computer_mouse
Real, high-precision Windows 10 & 11 mouse automation using modern Win32 SendInput,
Per-Monitor V2 DPI Awareness, and visible smooth cursor gliding.
"""

from __future__ import annotations
import sys
import time
import math
import ctypes
from ctypes import wintypes
from typing import Optional

from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.vision.safety import computer_safety, ensure_interactive_desktop
from cord.vision.ai_cursor import ai_cursor

# Initialize high-precision 1ms timer on Windows
if sys.platform == "win32":
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

# Modern Win32 SendInput constants & structures
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

ULONG_PTR = ctypes.c_ulonglong if sys.maxsize > 2**32 else ctypes.c_ulong

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION),
    ]

def _init_dpi_awareness():
    """Ensures accurate coordinate mapping on Windows 10 & 11 with 125%/150% DPI scaling."""
    if sys.platform == "win32":
        try:
            ensure_interactive_desktop()
            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

_init_dpi_awareness()

def _send_mouse_event(flags: int, data: int = 0, dx: int = 0, dy: int = 0):
    """Sends a mouse event using modern Win32 SendInput API with mouse_event fallback."""
    user32 = ctypes.windll.user32
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = dx
    inp.u.mi.dy = dy
    inp.u.mi.mouseData = ctypes.c_ulong(int(data)).value
    inp.u.mi.dwFlags = flags
    inp.u.mi.time = 0
    inp.u.mi.dwExtraInfo = 0
    res = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if res != 1:
        try:
            user32.mouse_event(flags, dx, dy, int(data), 0)
        except Exception:
            pass

def _get_cursor_pos() -> tuple[int, int]:
    """Returns current physical cursor position."""
    if sys.platform == "win32":
        ensure_interactive_desktop()
        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    return 0, 0

def _activate_window_at(x: int, y: int):
    """Ensures window under (x, y) is in the foreground so clicks directly trigger UI controls."""
    if sys.platform != "win32":
        return
    try:
        ensure_interactive_desktop()
        user32 = ctypes.windll.user32
        pt = wintypes.POINT(int(x), int(y))
        hwnd = user32.WindowFromPoint(pt)
        if hwnd:
            root = user32.GetAncestor(hwnd, 2)  # GA_ROOT
            target = root if root else hwnd
            cur_fore = user32.GetForegroundWindow()
            if target != cur_fore:
                try:
                    from cord.tools.computer.computer_window import _force_foreground
                    _force_foreground(target)
                except Exception:
                    user32.SetForegroundWindow(target)
                time.sleep(0.04)
    except Exception:
        pass

def _glide_cursor_to(target_x: int, target_y: int, steps: int = 2, duration: float = 0.004):
    """
    Hyper-Glide Micro-Burst Trajectory Engine.
    Executes an ultra-fast eased trajectory in sub-4ms.
    Renders the Cyberpunk AI Cursor HUD reticle and dispatches hardware coordinates instantly.
    """
    ensure_interactive_desktop()
    user32 = ctypes.windll.user32
    start_x, start_y = _get_cursor_pos()
    
    # Flash Cyberpunk AI Cursor HUD indicator
    ai_cursor.show_pointer(int(target_x), int(target_y))

    # Instant snap for short distances (< 100px)
    dist = math.hypot(target_x - start_x, target_y - start_y)
    if dist < 100:
        user32.SetCursorPos(int(target_x), int(target_y))
        _send_mouse_event(MOUSEEVENTF_MOVE)
        return

    # Micro-burst spline
    delay = duration / max(steps, 1)
    for i in range(1, steps):
        t = i / steps
        ease = 1 - (1 - t) * (1 - t)
        cx = int(start_x + (target_x - start_x) * ease)
        cy = int(start_y + (target_y - start_y) * ease)
        user32.SetCursorPos(cx, cy)
        time.sleep(delay)

    user32.SetCursorPos(int(target_x), int(target_y))
    _send_mouse_event(MOUSEEVENTF_MOVE)



class ComputerMouseTool(BaseTool):
    name = "computer_mouse"
    description = "Control the computer mouse: move cursor, click, double click, right click, drag, or scroll."
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["move", "click", "double_click", "right_click", "drag", "scroll"],
                "description": "Mouse action to execute"
            },
            "x": {
                "description": "Target X coordinate on screen (pixel int or 0.0-1.0 normalized float)"
            },
            "y": {
                "description": "Target Y coordinate on screen (pixel int or 0.0-1.0 normalized float)"
            },
            "end_x": {
                "description": "Destination X coordinate for 'drag' action"
            },
            "end_y": {
                "description": "Destination Y coordinate for 'drag' action"
            },
            "scroll_amount": {
                "type": "integer",
                "description": "Scroll notches (positive for up, negative for down; default: -120)",
                "default": -120
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        x: int | float | None = None,
        y: int | float | None = None,
        end_x: int | float | None = None,
        end_y: int | float | None = None,
        scroll_amount: int = -120,
        **kwargs
    ) -> ToolResult:
        try:
            if sys.platform != "win32":
                return ToolResult(success=False, output="", error="Native mouse control currently supports Windows.")

            ensure_interactive_desktop()

            # Resolve coordinates (handle normalized floats 0.0-1.0 or downscaled dimensions)
            from cord.vision.vision_pipeline import resolve_screen_coordinates
            ref_w = kwargs.get("reference_width")
            ref_h = kwargs.get("reference_height")

            if x is not None and y is not None:
                x, y = resolve_screen_coordinates(x, y, reference_width=ref_w, reference_height=ref_h)

            if end_x is not None and end_y is not None:
                end_x, end_y = resolve_screen_coordinates(end_x, end_y, reference_width=ref_w, reference_height=ref_h)

            # Validate against safety boundaries
            allowed, reason = computer_safety.validate_action(action, x=x, y=y)
            if not allowed:
                return ToolResult(success=False, output="", error=f"Mouse action blocked: {reason}")

            if action == "move":
                if x is None or y is None:
                    return ToolResult(success=False, output="", error="x and y coordinates are required for move")
                _glide_cursor_to(x, y)
                return ToolResult(success=True, output=f"Mouse moved smoothly to ({x}, {y})")

            elif action == "click":
                if x is not None and y is not None:
                    _activate_window_at(x, y)
                    _glide_cursor_to(x, y)
                    ai_cursor.show_click(int(x), int(y), button="left")
                    time.sleep(0.02)
                _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                time.sleep(0.04)  # 40ms human-like hold time ensures Windows & Chromium register the click
                _send_mouse_event(MOUSEEVENTF_LEFTUP)
                time.sleep(0.02)
                pos_str = f" at ({x}, {y})" if x is not None else ""
                return ToolResult(success=True, output=f"Left click performed{pos_str} via SendInput")

            elif action == "double_click":
                if x is not None and y is not None:
                    _activate_window_at(x, y)
                    _glide_cursor_to(x, y)
                    ai_cursor.show_click(int(x), int(y), button="double")
                    time.sleep(0.02)
                # First click
                _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                time.sleep(0.04)
                _send_mouse_event(MOUSEEVENTF_LEFTUP)
                time.sleep(0.06)
                # Second click
                _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                time.sleep(0.04)
                _send_mouse_event(MOUSEEVENTF_LEFTUP)
                time.sleep(0.02)
                pos_str = f" at ({x}, {y})" if x is not None else ""
                return ToolResult(success=True, output=f"Double click performed{pos_str} via SendInput")

            elif action == "right_click":
                if x is not None and y is not None:
                    _activate_window_at(x, y)
                    _glide_cursor_to(x, y)
                    ai_cursor.show_click(int(x), int(y), button="right")
                    time.sleep(0.02)
                _send_mouse_event(MOUSEEVENTF_RIGHTDOWN)
                time.sleep(0.04)
                _send_mouse_event(MOUSEEVENTF_RIGHTUP)
                time.sleep(0.02)
                pos_str = f" at ({x}, {y})" if x is not None else ""
                return ToolResult(success=True, output=f"Right click performed{pos_str} via SendInput")

            elif action == "drag":
                if x is None or y is None or end_x is None or end_y is None:
                    return ToolResult(success=False, output="", error="x, y, end_x, and end_y are all required for drag")
                # Move to start
                _glide_cursor_to(x, y)
                time.sleep(0.05)
                _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                time.sleep(0.05)
                # Drag to destination
                _glide_cursor_to(end_x, end_y, steps=20, duration=0.25)
                time.sleep(0.05)
                _send_mouse_event(MOUSEEVENTF_LEFTUP)
                return ToolResult(success=True, output=f"Dragged from ({x}, {y}) to ({end_x}, {end_y}) via SendInput")

            elif action == "scroll":
                if x is not None and y is not None:
                    _activate_window_at(x, y)
                    _glide_cursor_to(x, y)
                    time.sleep(0.02)
                else:
                    cx = computer_safety.screen_size[0] // 2
                    cy = computer_safety.screen_size[1] // 2
                    _activate_window_at(cx, cy)
                    _glide_cursor_to(cx, cy)
                    time.sleep(0.02)

                raw_amt = int(scroll_amount)
                step = -120 if raw_amt < 0 else 120
                ticks = max(abs(raw_amt) // 120, 1)
                for _ in range(ticks):
                    _send_mouse_event(MOUSEEVENTF_WHEEL, data=step)
                    time.sleep(0.005)

                return ToolResult(
                    success=True,
                    output=f"Scrolled mouse wheel ({scroll_amount} across {ticks} notches) via SendInput."
                )

            return ToolResult(success=False, output="", error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Mouse action failed: {e}")
