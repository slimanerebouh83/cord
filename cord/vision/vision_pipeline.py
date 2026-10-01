"""CORD Vision Pipeline - Capture, Compression, and Resolution Normalization"""
from __future__ import annotations
import base64
import io
import time
import sys
import ctypes
from pathlib import Path
from PIL import Image, ImageGrab
from cord.vision.safety import computer_safety, ensure_interactive_desktop


def win32_capture_screen() -> Image.Image | None:
    """Captures screen using native Win32 GDI with interactive desktop binding."""
    if sys.platform != "win32":
        return None
    try:
        ensure_interactive_desktop()
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        if w <= 0 or h <= 0:
            return None

        hdcScreen = user32.GetDC(0)
        if not hdcScreen:
            return None

        hdcMem = gdi32.CreateCompatibleDC(hdcScreen)
        hbm = gdi32.CreateCompatibleBitmap(hdcScreen, w, h)
        hbm_old = gdi32.SelectObject(hdcMem, hbm)

        gdi32.BitBlt(hdcMem, 0, 0, w, h, hdcScreen, 0, 0, 0x00CC0020)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32),
                ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # top-down DIB
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf = (ctypes.c_char * (w * h * 4))()
        gdi32.GetDIBits(hdcMem, hbm, 0, h, ctypes.byref(buf), ctypes.byref(bmi), 0)

        gdi32.SelectObject(hdcMem, hbm_old)
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdcMem)
        user32.ReleaseDC(0, hdcScreen)

        im = Image.frombuffer("RGBA", (w, h), bytes(buf), "raw", "BGRA", 0, 1).convert("RGB")
        return im
    except Exception:
        return None


class VisionPipeline:
    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path.home() / ".cord" / "screenshots"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.last_capture: dict | None = None

    def capture_screenshot(
        self,
        crop_box: tuple[int, int, int, int] | None = None,
        max_dimension: int = 1920,
        jpeg_quality: int = 75,
        save_to_disk: bool = True
    ) -> dict:
        """
        Capture the screen, optionally crop, downscale for efficient token usage,
        and encode to base64.
        Returns a dict with physical dimensions, scaled dimensions, file path, and base64.
        """
        ensure_interactive_desktop()

        # 1. Grab screen using native Win32 GDI or PIL ImageGrab fallback
        img: Image.Image | None = win32_capture_screen()
        if img is None:
            try:
                img = ImageGrab.grab(all_screens=True)
            except Exception:
                try:
                    img = ImageGrab.grab()
                except Exception as ex:
                    raise OSError(f"Screen grab failed via all capture engines: {ex}") from ex

        original_w, original_h = img.size

        if crop_box:
            img = img.crop(crop_box)

        curr_w, curr_h = img.size

        # 2. Scale down if exceeding max dimension while preserving aspect ratio
        scale_factor = 1.0
        if max(curr_w, curr_h) > max_dimension:
            if curr_w >= curr_h:
                new_w = max_dimension
                new_h = int(curr_h * (max_dimension / curr_w))
            else:
                new_h = max_dimension
                new_w = int(curr_w * (max_dimension / curr_h))
            scale_factor = new_w / curr_w
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            new_w, new_h = curr_w, curr_h

        # 3. Compress to JPEG base64
        buffered = io.BytesIO()
        rgb_img = img.convert("RGB")
        rgb_img.save(buffered, format="JPEG", quality=jpeg_quality, optimize=True)
        img_bytes = buffered.getvalue()
        b64_str = base64.b64encode(img_bytes).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{b64_str}"

        # 4. Save to disk if requested
        saved_path = None
        if save_to_disk:
            timestamp = int(time.time() * 1000)
            file_path = self.cache_dir / f"screen_{timestamp}.jpg"
            file_path.write_bytes(img_bytes)
            saved_path = str(file_path)

        res = {
            "original_width": original_w,
            "original_height": original_h,
            "width": new_w,
            "height": new_h,
            "scale_factor": scale_factor,
            "saved_path": saved_path,
            "base64": b64_str,
            "data_uri": data_uri,
            "size_bytes": len(img_bytes)
        }
        self.last_capture = res
        return res

    def scale_point_to_screen(self, x: int | float, y: int | float, scaled_width: int, scaled_height: int) -> tuple[int, int]:
        """Convert coordinates from downscaled vision model output back to physical screen pixels."""
        return resolve_screen_coordinates(x, y, reference_width=scaled_width, reference_height=scaled_height)


def resolve_screen_coordinates(
    x: int | float | None,
    y: int | float | None,
    reference_width: int | None = None,
    reference_height: int | None = None,
) -> tuple[int, int]:
    """
    Universally resolves any coordinate representation to physical screen pixels:
    - Floats in range [0.0, 1.0] -> scaled by screen dimensions
    - Explicit reference width/height -> scaled proportionally
    - Standard physical coordinates -> returned as integers
    """
    if x is None or y is None:
        return 0, 0

    screen_w, screen_h = computer_safety.screen_size

    # 1. Handle normalized float coordinates in [0.0, 1.0]
    rx = float(x)
    ry = float(y)
    if isinstance(x, float) and 0.0 <= x <= 1.0:
        rx = x * screen_w
    if isinstance(y, float) and 0.0 <= y <= 1.0:
        ry = y * screen_h

    # 2. Handle reference width/height scaling if provided
    if reference_width and reference_height and reference_width > 0 and reference_height > 0:
        if reference_width != screen_w or reference_height != screen_h:
            rx = rx * (screen_w / reference_width)
            ry = ry * (screen_h / reference_height)

    return int(round(rx)), int(round(ry))


vision_pipeline = VisionPipeline()
