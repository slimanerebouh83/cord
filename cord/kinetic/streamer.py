"""
KINETIC-CORE: Ultra-Fast C-Level Win32 Input Streaming Engine.
Compiles whole macro action chains into contiguous Win32 INPUT memory packets.
Dispatches hundreds of keystrokes, clicks, and chords in a single sub-millisecond kernel transition.
"""

from __future__ import annotations
import sys
import time
import ctypes
from ctypes import wintypes
from typing import List, Tuple, Optional

# Windows SendInput Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

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


class KineticStreamer:
    """Compiles and transmits contiguous input packet streams at hardware speeds."""

    def __init__(self):
        self.is_win32 = (sys.platform == "win32")

    def compile_keystroke_packet(self, vk: int, scan: int = 0, is_extended: bool = False) -> Tuple[INPUT, INPUT]:
        """Creates down + up INPUT structures for an atomic keystroke."""
        flags_down = KEYEVENTF_EXTENDEDKEY if is_extended else 0
        flags_up = KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if is_extended else 0)

        down = INPUT()
        down.type = INPUT_KEYBOARD
        down.ii.ki = KEYBDINPUT(vk, scan, flags_down, 0, 0)

        up = INPUT()
        up.type = INPUT_KEYBOARD
        up.ii.ki = KEYBDINPUT(vk, scan, flags_up, 0, 0)

        return down, up

    def compile_unicode_packet(self, char: str) -> Tuple[INPUT, INPUT]:
        """Creates down + up INPUT structures for an atomic Unicode character."""
        code = ord(char)
        down = INPUT()
        down.type = INPUT_KEYBOARD
        down.ii.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0)

        up = INPUT()
        up.type = INPUT_KEYBOARD
        up.ii.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)

        return down, up

    def compile_text_packet(self, text: str) -> List[INPUT]:
        """Compiles entire text string into a contiguous array of INPUT structures."""
        packets: List[INPUT] = []
        user32 = ctypes.windll.user32 if self.is_win32 else None

        for ch in text:
            if ch == "\n":
                vk = 0x0D  # VK_RETURN
                scan = user32.MapVirtualKeyW(vk, 0) if user32 else 0
                d, u = self.compile_keystroke_packet(vk, scan)
                packets.extend([d, u])
            elif ch == "\t":
                vk = 0x09  # VK_TAB
                scan = user32.MapVirtualKeyW(vk, 0) if user32 else 0
                d, u = self.compile_keystroke_packet(vk, scan)
                packets.extend([d, u])
            elif ch == "\r":
                continue
            else:
                d, u = self.compile_unicode_packet(ch)
                packets.extend([d, u])

        return packets

    def compile_click_packet(self, button: str = "left") -> Tuple[INPUT, INPUT]:
        """Compiles mouse down + up packet."""
        down = INPUT()
        down.type = INPUT_MOUSE
        up = INPUT()
        up.type = INPUT_MOUSE

        if button == "right":
            down.ii.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_RIGHTDOWN, 0, 0)
            up.ii.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_RIGHTUP, 0, 0)
        else:
            down.ii.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, 0)
            up.ii.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, 0)

        return down, up

    def dispatch_packet_batch(self, packets: List[INPUT], chunk_size: int = 128) -> int:
        """Dispatches an entire packet array in a single or chunked kernel call."""
        if not self.is_win32 or not packets:
            return 0

        user32 = ctypes.windll.user32
        total_sent = 0
        n = len(packets)

        for i in range(0, n, chunk_size):
            chunk = packets[i:i + chunk_size]
            arr = (INPUT * len(chunk))(*chunk)
            res = user32.SendInput(len(chunk), ctypes.byref(arr), ctypes.sizeof(INPUT))
            if res > 0:
                total_sent += res
            else:
                # Secondary fallback if SendInput is blocked by UIPI
                for p in chunk:
                    if p.type == INPUT_KEYBOARD:
                        ki = p.ii.ki
                        user32.keybd_event(ki.wVk, ki.wScan, ki.dwFlags, 0)
                    elif p.type == INPUT_MOUSE:
                        mi = p.ii.mi
                        user32.mouse_event(mi.dwFlags, mi.dx, mi.dy, mi.mouseData, 0)
                total_sent += len(chunk)

        return total_sent


kinetic_streamer = KineticStreamer()


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


def press_virtual_key(vk: int) -> None:
    """Presses down a virtual key using hardware scan code mapping."""
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    scan = user32.MapVirtualKeyW(vk, 0)
    flags = KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_KEYS else 0

    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ii.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    res = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if res != 1:
        user32.keybd_event(vk, scan, flags, 0)


def release_virtual_key(vk: int) -> None:
    """Releases a virtual key using hardware scan code mapping."""
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    scan = user32.MapVirtualKeyW(vk, 0)
    flags = KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_KEYS else 0)

    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ii.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    res = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if res != 1:
        user32.keybd_event(vk, scan, flags, 0)


def _get_cursor_pos() -> Tuple[int, int]:
    """Returns current physical cursor position."""
    if sys.platform == "win32":
        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    return 0, 0


def _activate_window_at(x: int, y: int) -> None:
    """Ensures window under (x, y) is in the foreground."""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        pt = wintypes.POINT(int(x), int(y))
        hwnd = user32.WindowFromPoint(pt)
        if hwnd:
            root = user32.GetAncestor(hwnd, 2)
            target = root if root else hwnd
            cur_fore = user32.GetForegroundWindow()
            if target != cur_fore:
                user32.SetForegroundWindow(target)
                time.sleep(0.008)
    except Exception:
        pass


def _send_mouse_event(flags: int, data: int = 0, dx: int = 0, dy: int = 0) -> None:
    """Dispatches a mouse event with Win32 SendInput or fallback."""
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.ii.mi = MOUSEINPUT(dx, dy, ctypes.c_ulong(int(data)).value, flags, 0, 0)
    res = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if res != 1:
        user32.mouse_event(flags, dx, dy, int(data), 0)


def activate_target_window(title_query: str) -> bool:
    """Brings matching target window to foreground."""
    if sys.platform != "win32" or not title_query:
        return False
    try:
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
            user32.ShowWindow(matched_hwnd, 9)
            user32.SetForegroundWindow(matched_hwnd)
            time.sleep(0.02)
            return True
    except Exception:
        pass
    return False
