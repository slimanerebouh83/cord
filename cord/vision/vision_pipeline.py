"""CORD Vision Pipeline - Capture, Compression, and Resolution Normalization"""
from __future__ import annotations
import base64
import io
import time
from pathlib import Path
from PIL import Image, ImageGrab
from cord.vision.safety import computer_safety

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
        # 1. Grab screen using PIL ImageGrab
        img: Image.Image = ImageGrab.grab()
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

    def scale_point_to_screen(self, x: int, y: int, scaled_width: int, scaled_height: int) -> tuple[int, int]:
        """Convert coordinates from downscaled vision model output back to physical screen pixels."""
        screen_w, screen_h = computer_safety.screen_size
        actual_x = int(x * (screen_w / scaled_width))
        actual_y = int(y * (screen_h / scaled_height))
        return (actual_x, actual_y)

vision_pipeline = VisionPipeline()
