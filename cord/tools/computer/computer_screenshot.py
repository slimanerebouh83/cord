"""CORD Tool - computer_screenshot"""
from __future__ import annotations
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.vision.safety import computer_safety
from cord.vision.vision_pipeline import vision_pipeline

class ComputerScreenshotTool(BaseTool):
    name = "computer_screenshot"
    description = "Capture an image of the computer screen or a specific region to inspect the GUI state."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "crop_box": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional bounding box to crop [left, top, right, bottom]"
            },
            "include_base64": {
                "type": "boolean",
                "description": "If true, include base64 data uri directly in output for vision models",
                "default": False
            }
        },
        "required": []
    }

    async def execute(self, crop_box: list[int] | None = None, include_base64: bool = False, **kwargs) -> ToolResult:
        try:
            allowed, reason = computer_safety.validate_action("screenshot")
            if not allowed:
                return ToolResult(success=False, output="", error=f"Action blocked by safety policy: {reason}")

            box = tuple(crop_box) if crop_box and len(crop_box) == 4 else None
            res = vision_pipeline.capture_screenshot(crop_box=box, save_to_disk=True)

            msg = (
                f"Screenshot captured successfully:\n"
                f"  - Saved to: {res['saved_path']}\n"
                f"  - Resolution: {res['width']}x{res['height']} (Original: {res['original_width']}x{res['original_height']})\n"
                f"  - File size: {res['size_bytes'] / 1024:.1f} KB"
            )
            if include_base64:
                msg += f"\n  - Data URI: {res['data_uri'][:100]}... [truncated]"

            return ToolResult(success=True, output=msg)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to capture screenshot: {e}")
