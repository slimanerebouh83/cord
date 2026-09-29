"""
CORD Vision - Native AI Cursor & Click Visual Feedback (Win32 GDI HUD)
Provides instant visual feedback (AI pointer crosshair and expanding click ripple)
directly onto the display using Win32 GDI without creating ANY overlay windows,
preventing window focus theft, terminal freezes, or taskbar interception.
"""

from __future__ import annotations
import sys
import time
import ctypes
import threading
from typing import Optional


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class AICursorHUD:
    """
    Ultra-lightweight, zero-window visual HUD for CORD AI mouse actions.
    Uses native Win32 GDI to render pointer highlights and click ripples directly to
    the desktop device context, ensuring:
      1. Zero full-screen windows or invisible barriers.
      2. Zero window focus theft from PowerShell or terminal.
      3. Zero mouse click or taskbar interception.
      4. 100% thread safety and instantaneous cleanup.
    """
    _instance: Optional[AICursorHUD] = None
    _lock = threading.Lock()

    def __init__(self):
        self.enabled = (sys.platform == "win32")
        self.current_x = 0
        self.current_y = 0
        self._user32 = ctypes.windll.user32 if self.enabled else None
        self._gdi32 = ctypes.windll.gdi32 if self.enabled else None

    @classmethod
    def get_instance(cls) -> AICursorHUD:
        with cls._lock:
            if cls._instance is None:
                cls._instance = AICursorHUD()
            return cls._instance

    def show_pointer(self, x: int, y: int, label: str = "[🤖 CORD AI]"):
        """Displays a sleek cyberpunk AI pointer reticle and badge at (x, y)."""
        self.current_x = int(x)
        self.current_y = int(y)
        if not self.enabled or not self._user32 or not self._gdi32:
            return

        threading.Thread(target=self._draw_pointer_gdi, args=(int(x), int(y), label), daemon=True).start()

    def _draw_pointer_gdi(self, x: int, y: int, label: str):
        try:
            hdc = self._user32.GetDC(0)
            if not hdc:
                return

            PS_SOLID = 0
            # 1. Outer Cyan Reticle & Precision Crosshair Ticks (BGR: 0xFFFF00)
            pen_cyan = self._gdi32.CreatePen(PS_SOLID, 2, 0xFFFF00)
            old_pen = self._gdi32.SelectObject(hdc, pen_cyan)
            old_brush = self._gdi32.SelectObject(hdc, self._gdi32.GetStockObject(5))  # NULL_BRUSH

            # Dual Target Rings
            self._gdi32.Ellipse(hdc, x - 18, y - 18, x + 18, y + 18)
            self._gdi32.Ellipse(hdc, x - 6, y - 6, x + 6, y + 6)

            # 4 Crosshair Ticks
            self._gdi32.MoveToEx(hdc, x - 26, y, None); self._gdi32.LineTo(hdc, x - 18, y)
            self._gdi32.MoveToEx(hdc, x + 18, y, None); self._gdi32.LineTo(hdc, x + 26, y)
            self._gdi32.MoveToEx(hdc, x, y - 26, None); self._gdi32.LineTo(hdc, x, y - 18)
            self._gdi32.MoveToEx(hdc, x, y + 18, None); self._gdi32.LineTo(hdc, x, y + 26)

            # 2. Cyber Magenta/Cyan Arrow Pointer at (x, y)
            pen_magenta = self._gdi32.CreatePen(PS_SOLID, 2, 0xFF00FF)
            self._gdi32.SelectObject(hdc, pen_magenta)
            pts = (POINT * 7)(
                POINT(x, y),
                POINT(x + 16, y + 12),
                POINT(x + 8, y + 13),
                POINT(x + 13, y + 23),
                POINT(x + 9, y + 25),
                POINT(x + 5, y + 15),
                POINT(x, y + 18)
            )
            self._gdi32.Polygon(hdc, pts, 7)

            # 3. Glowing Badge Text
            self._gdi32.SetBkMode(hdc, 1)  # TRANSPARENT
            self._gdi32.SetTextColor(hdc, 0xFFFF00)  # Cyan
            self._gdi32.TextOutW(hdc, x + 22, y + 12, label, len(label))

            time.sleep(0.08)

            # Cleanup GDI
            self._gdi32.SelectObject(hdc, old_pen)
            self._gdi32.SelectObject(hdc, old_brush)
            self._gdi32.DeleteObject(pen_cyan)
            self._gdi32.DeleteObject(pen_magenta)
            self._user32.ReleaseDC(0, hdc)

            # Invalidate to restore screen region cleanly
            rc = RECT(x - 30, y - 30, x + 140, y + 35)
            self._user32.InvalidateRect(0, ctypes.byref(rc), True)
        except Exception:
            pass

    def show_click(self, x: int, y: int, button: str = "left"):
        """Displays an expanding click ripple shockwave at (x, y)."""
        self.current_x = int(x)
        self.current_y = int(y)
        if not self.enabled or not self._user32 or not self._gdi32:
            return

        threading.Thread(target=self._draw_ripple_gdi, args=(int(x), int(y)), daemon=True).start()

    def _draw_ripple_gdi(self, x: int, y: int):
        try:
            hdc = self._user32.GetDC(0)
            if not hdc:
                return

            PS_SOLID = 0
            # Multi-hue expanding rings: Yellow -> Cyan -> Magenta
            colors = [0x00FFFF, 0xFFFF00, 0xFF00FF]
            for idx, r in enumerate([12, 24, 38]):
                pen = self._gdi32.CreatePen(PS_SOLID, 2, colors[idx % len(colors)])
                old_pen = self._gdi32.SelectObject(hdc, pen)
                old_brush = self._gdi32.SelectObject(hdc, self._gdi32.GetStockObject(5))  # NULL_BRUSH

                self._gdi32.Ellipse(hdc, x - r, y - r, x + r, y + r)
                time.sleep(0.015)

                self._gdi32.SelectObject(hdc, old_pen)
                self._gdi32.SelectObject(hdc, old_brush)
                self._gdi32.DeleteObject(pen)

            self._user32.ReleaseDC(0, hdc)

            # Invalidate to restore screen region cleanly
            rc = RECT(x - 45, y - 45, x + 45, y + 45)
            self._user32.InvalidateRect(0, ctypes.byref(rc), True)
        except Exception:
            pass

    def hide(self):
        """Zero-op for GDI HUD since elements auto-restore immediately."""
        pass


ai_cursor = AICursorHUD.get_instance()
