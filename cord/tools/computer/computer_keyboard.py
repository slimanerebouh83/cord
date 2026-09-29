"""
CORD Tool - computer_keyboard
High-precision Windows 10 & 11 keyboard automation with modern Win32 SendInput (64-bit aligned),
hardware scan-code mapping, dual-pipeline keybd_event fallback, and window auto-focusing.
"""

from __future__ import annotations
import sys
import time
import ctypes
from ctypes import wintypes
from typing import Optional, List

from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.vision.safety import computer_safety

# Windows SendInput Constants
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# Accurate 64-bit and 32-bit Win32 ULONG_PTR sizing
ULONG_PTR = ctypes.c_ulonglong if sys.maxsize > 2**32 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT_I(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("ii", INPUT_I),
    ]


LPINPUT = ctypes.POINTER(INPUT)

if sys.platform == "win32":
    try:
        ctypes.windll.user32.SendInput.argtypes = (wintypes.UINT, ctypes.c_void_p, ctypes.c_int)
        ctypes.windll.user32.SendInput.restype = wintypes.UINT
    except Exception:
        pass


VK_CODES = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "space": 0x20,
    "spacebar": 0x20,
    "backspace": 0x08,
    "bs": 0x08,
    "esc": 0x1B,
    "escape": 0x1B,
    "ctrl": 0x11,
    "control": 0x11,
    "lctrl": 0xA2,
    "rctrl": 0xA3,
    "alt": 0x12,
    "lalt": 0xA4,
    "ralt": 0xA5,
    "shift": 0x10,
    "lshift": 0xA0,
    "rshift": 0xA1,
    "win": 0x5B,
    "windows": 0x5B,
    "cmd": 0x5B,
    "super": 0x5B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "ins": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "pgup": 0x21,
    "pgdn": 0x22,
    "capslock": 0x14,
    "caps_lock": 0x14,
    "printscreen": 0x2C,
    "prtscn": 0x2C,
    "scrolllock": 0x91,
    "numlock": 0x90,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}

EXTENDED_KEYS = {
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
    0x2D, 0x2E, 0x5B, 0x5C, 0x5D, 0x90, 0xA3, 0xA5,
}


def send_unicode_character(char: str) -> None:
    """Dispatches a single Unicode character using SendInput with keybd_event fallback."""
    if sys.platform != "win32":
        return

    user32 = ctypes.windll.user32
    code = ord(char)

    # 1. Primary pipeline: SendInput with 40-byte 64-bit aligned structure
    inp_down = INPUT()
    inp_down.type = INPUT_KEYBOARD
    inp_down.ii.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0)

    inp_up = INPUT()
    inp_up.type = INPUT_KEYBOARD
    inp_up.ii.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)

    inputs = (INPUT * 2)(inp_down, inp_up)
    res = user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
    if res == 2:
        return

    # 2. Secondary resilient pipeline: Win32 keybd_event
    user32.keybd_event(0, code, KEYEVENTF_UNICODE, 0)
    time.sleep(0.001)
    user32.keybd_event(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)


def press_virtual_key(vk: int) -> None:
    """Presses down a virtual key using hardware scan code mapping."""
    if sys.platform != "win32":
        return

    user32 = ctypes.windll.user32
    scan = user32.MapVirtualKeyW(vk, 0)
    flags = KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_KEYS else 0

    # 1. Primary pipeline: SendInput
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ii.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    res = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if res == 1:
        return

    # 2. Secondary resilient pipeline: keybd_event
    user32.keybd_event(vk, scan, flags, 0)


def release_virtual_key(vk: int) -> None:
    """Releases a virtual key using hardware scan code mapping."""
    if sys.platform != "win32":
        return

    user32 = ctypes.windll.user32
    scan = user32.MapVirtualKeyW(vk, 0)
    flags = KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_KEYS else 0)

    # 1. Primary pipeline: SendInput
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ii.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    res = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if res == 1:
        return

    # 2. Secondary resilient pipeline: keybd_event
    user32.keybd_event(vk, scan, flags, 0)


def activate_target_window(title_query: str) -> bool:
    """Brings matching target window to foreground to receive keyboard input."""
    if sys.platform != "win32" or not title_query:
        return False
    try:
        from cord.tools.computer.computer_window import _force_foreground
        user32 = ctypes.windll.user32
        matched_hwnd = None

        def enum_cb(hwnd, _):
            nonlocal matched_hwnd
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if title_query.lower() in buf.value.lower():
                    matched_hwnd = hwnd
                    return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

        if matched_hwnd:
            _force_foreground(matched_hwnd)
            time.sleep(0.05)
            return True
    except Exception:
        pass
    return False


class ComputerKeyboardTool(BaseTool):
    name = "computer_keyboard"
    description = (
        "Simulate hardware and Unicode keyboard operations: type text (supports all languages, code, symbols), "
        "press individual keys (e.g. 'enter', 'tab', 'esc', 'space'), or execute hotkey combos (e.g. 'ctrl+c', 'win+r', 'alt+tab')."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["type", "key", "hotkey"],
                "description": "Keyboard action: 'type' for strings, 'key' for single key tap, 'hotkey' for multi-key combos",
            },
            "text": {
                "type": "string",
                "description": "Text string to type (used when action is 'type')",
            },
            "key": {
                "type": "string",
                "description": "Key name (e.g. 'enter', 'tab', 'esc', 'backspace', 'space') when action is 'key'",
            },
            "hotkey": {
                "type": "string",
                "description": "Combination formatted like 'ctrl+c', 'alt+f4', 'ctrl+shift+p', 'win+r'",
            },
            "window_title": {
                "type": "string",
                "description": "Optional window title to bring to front and focus before typing (e.g. 'Notepad', 'Chrome')",
            },
        },
        "required": ["action"],
    }

    def _resolve_vk(self, key_name: str) -> int | None:
        name = key_name.strip().lower()
        if name in VK_CODES:
            return VK_CODES[name]
        if len(name) == 1:
            code = ord(name.upper())
            if 0x30 <= code <= 0x5A:  # 0-9, A-Z
                return code
        return None

    async def execute(
        self,
        action: str,
        text: str | None = None,
        key: str | None = None,
        hotkey: str | None = None,
        window_title: str | None = None,
        **kwargs,
    ) -> ToolResult:
        try:
            if sys.platform != "win32":
                return ToolResult(success=False, output="", error="Native keyboard control currently supports Windows.")

            allowed, reason = computer_safety.validate_action(action)
            if not allowed:
                return ToolResult(success=False, output="", error=f"Keyboard action blocked: {reason}")

            # Optional window focus before typing
            if window_title:
                activate_target_window(window_title)

            if action == "type":
                if not text:
                    return ToolResult(success=False, output="", error="text is required for action 'type'")

                for ch in text:
                    if computer_safety.is_stopped():
                        return ToolResult(success=False, output="", error="Execution aborted by Kill Switch.")
                    if ch == "\n":
                        vk = VK_CODES["enter"]
                        press_virtual_key(vk)
                        time.sleep(0.005)
                        release_virtual_key(vk)
                    elif ch == "\t":
                        vk = VK_CODES["tab"]
                        press_virtual_key(vk)
                        time.sleep(0.005)
                        release_virtual_key(vk)
                    elif ch == "\r":
                        continue
                    else:
                        send_unicode_character(ch)
                    time.sleep(0.002)

                return ToolResult(success=True, output=f"Successfully typed {len(text)} characters.")

            elif action == "key":
                if not key:
                    return ToolResult(success=False, output="", error="key is required for action 'key'")
                vk = self._resolve_vk(key)
                if vk is None:
                    return ToolResult(success=False, output="", error=f"Unrecognized key: '{key}'")

                press_virtual_key(vk)
                time.sleep(0.03)
                release_virtual_key(vk)
                return ToolResult(success=True, output=f"Successfully pressed key: '{key}'.")

            elif action == "hotkey":
                if not hotkey:
                    return ToolResult(success=False, output="", error="hotkey string is required (e.g. 'ctrl+c')")

                parts = [p.strip() for p in hotkey.split("+")]
                vks = []
                for p in parts:
                    vk = self._resolve_vk(p)
                    if vk is None:
                        return ToolResult(success=False, output="", error=f"Unrecognized hotkey component: '{p}'")
                    vks.append(vk)

                # Press down in order
                for vk in vks:
                    press_virtual_key(vk)
                    time.sleep(0.015)

                time.sleep(0.04)

                # Release in reverse order
                for vk in reversed(vks):
                    release_virtual_key(vk)
                    time.sleep(0.015)

                return ToolResult(success=True, output=f"Successfully executed hotkey combo: '{hotkey}'.")

            return ToolResult(success=False, output="", error=f"Unknown action: '{action}'")

        except Exception as e:
            return ToolResult(success=False, output="", error=f"Keyboard action failed: {e}")
