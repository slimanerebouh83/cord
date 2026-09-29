"""
NITEE v3 - Vision Matcher Module
Game & visual surface object detector using template matching.
Generates vision tree nodes: `v_3 Item "enemy" #conf0.91 @512,300`.
"""

from __future__ import annotations
import os
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from PIL import ImageGrab, Image
except ImportError:
    ImageGrab = None
    Image = None


@dataclass
class VisionObject:
    """Detected visual or game object from template matching."""
    id: str
    label: str
    confidence: float
    center_x: int
    center_y: int
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, w, h

    def to_tree_line(self) -> str:
        """Format node line according to NITEE v3 vision spec:
        v_3 Item "enemy" #conf0.91 @512,300
        """
        conf_str = f"{self.confidence:.2f}"
        return f'{self.id} Item "{self.label}" #conf{conf_str} @{self.center_x},{self.center_y}'


class VisionMatcher:
    """Manages template registry and runs multi-object detection on game frames."""

    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            self.templates_dir = Path.home() / ".cord" / "templates"
        else:
            self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        self._templates: Dict[str, Any] = {}  # label -> image array/data
        self._nodes: Dict[str, VisionObject] = {}
        self._load_templates()

    @property
    def templates(self) -> Dict[str, Any]:
        return self._templates

    @property
    def nodes(self) -> Dict[str, VisionObject]:
        return self._nodes

    def has_template(self, label: str) -> bool:
        """Check if a template exists in library."""
        clean = label.strip().lower()
        return clean in self._templates

    def register_template(self, label: str, image_or_path: Any) -> bool:
        """Register a new template image under a label."""
        clean = label.strip().lower()
        if isinstance(image_or_path, (str, Path)):
            p = Path(image_or_path)
            if p.exists() and cv2 is not None:
                img = cv2.imread(str(p), cv2.IMREAD_COLOR)
                if img is not None:
                    self._templates[clean] = img
                    return True
        elif cv2 is not None and isinstance(image_or_path, np.ndarray):
            self._templates[clean] = image_or_path
            return True
        elif image_or_path is not None:
            self._templates[clean] = image_or_path
            return True
        return False

    def _load_templates(self) -> None:
        """Load any image files saved in templates directory."""
        if not self.templates_dir.exists():
            return
        valid_exts = {".png", ".jpg", ".jpeg", ".bmp"}
        for f in self.templates_dir.iterdir():
            if f.is_file() and f.suffix.lower() in valid_exts:
                label = f.stem.lower()
                self.register_template(label, f)

    def detect_objects(
        self,
        frame_image: Optional[Any] = None,
        min_confidence: float = 0.70,
        max_matches_per_template: int = 5,
    ) -> Tuple[str, Dict[str, VisionObject]]:
        """Run template matching across the active screen or passed image frame.
        
        Returns:
            (formatted_tree_text, nodes_map)
        """
        self._nodes.clear()

        # If no templates registered and no external frame, return empty tree
        if not self._templates and frame_image is None:
            return "", {}

        # Capture screen frame if none provided
        screen_bgr = None
        if frame_image is not None:
            if isinstance(frame_image, np.ndarray if np else ()):
                screen_bgr = frame_image
            elif Image is not None and isinstance(frame_image, Image.Image):
                if np is not None and cv2 is not None:
                    screen_bgr = cv2.cvtColor(np.array(frame_image), cv2.COLOR_RGB2BGR)
        elif ImageGrab is not None and np is not None and cv2 is not None:
            try:
                shot = ImageGrab.grab()
                screen_bgr = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
            except Exception:
                screen_bgr = None

        if screen_bgr is not None and cv2 is not None and np is not None:
            detected_items: List[Tuple[float, str, int, int, Tuple[int, int, int, int]]] = []
            h_screen, w_screen = screen_bgr.shape[:2]
            cx_screen, cy_screen = w_screen // 2, h_screen // 2

            for label, t_img in self._templates.items():
                if not isinstance(t_img, np.ndarray):
                    continue
                th, tw = t_img.shape[:2]
                if th > h_screen or tw > w_screen:
                    continue

                res = cv2.matchTemplate(screen_bgr, t_img, cv2.TM_CCOEFF_NORMED)
                loc = np.where(res >= min_confidence)
                matches = list(zip(*loc[::-1]))  # (x, y)

                # Non-maximum suppression / grouping
                kept_matches = []
                for pt in matches:
                    x, y = int(pt[0]), int(pt[1])
                    score = float(res[y, x])
                    # Ensure not too close to previously kept match
                    if any(abs(x - kx) < tw // 2 and abs(y - ky) < th // 2 for kx, ky, _ in kept_matches):
                        continue
                    kept_matches.append((x, y, score))
                    if len(kept_matches) >= max_matches_per_template:
                        break

                for x, y, score in kept_matches:
                    cx = x + tw // 2
                    cy = y + th // 2
                    # Distance from center for prioritizing
                    dist = math.hypot(cx - cx_screen, cy - cy_screen)
                    detected_items.append((dist, label, cx, cy, (x, y, tw, th), score))

            # Sort nearest to screen center
            detected_items.sort(key=lambda item: item[0])

            for idx, (_, label, cx, cy, bbox, score) in enumerate(detected_items):
                v_id = f"v_{idx + 1}"
                node = VisionObject(
                    id=v_id,
                    label=label,
                    confidence=score,
                    center_x=cx,
                    center_y=cy,
                    bbox=bbox,
                )
                self._nodes[v_id] = node

        lines = [obj.to_tree_line() for obj in self._nodes.values()]
        return "\n".join(lines), dict(self._nodes)
