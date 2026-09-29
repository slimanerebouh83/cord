"""
CORD Tools - Clipboard Management Tool
Provides read/write access to the system clipboard for the autonomous agent.
"""
from __future__ import annotations
import json
import subprocess
from typing import Any, Dict

from cord.tools.base import BaseTool, ToolResult


class ClipboardTool(BaseTool):
    """Reads from and writes to the system clipboard."""
    name = "clipboard"
    description = "Read or write text from/to the system clipboard. Actions: 'read' to get clipboard content, 'write' to set clipboard content."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write"],
                "description": "Action to perform: 'read' clipboard content or 'write' to clipboard."
            },
            "text": {
                "type": "string",
                "description": "Text to write to clipboard (required for 'write' action)."
            }
        },
        "required": ["action"]
    }

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "read")

        if action == "read":
            try:
                result = subprocess.run(
                    ["powershell", "-Command", "Get-Clipboard"],
                    capture_output=True, text=True, timeout=5
                )
                content = result.stdout.strip()
                return ToolResult(
                    success=True,
                    output=content if content else "(clipboard is empty)",
                    metadata={"chars": len(content)}
                )
            except Exception as e:
                return ToolResult(success=False, output="", error=f"Failed to read clipboard: {e}")

        elif action == "write":
            text = kwargs.get("text", "")
            if not text:
                return ToolResult(success=False, output="", error="No text provided to write to clipboard.")
            try:
                safe_text = text.replace('"', '`"')
                subprocess.run(
                    ["powershell", "-Command", f'Set-Clipboard -Value "{safe_text}"'],
                    capture_output=True, text=True, timeout=5
                )
                return ToolResult(
                    success=True,
                    output=f"Copied {len(text)} chars to clipboard.",
                    metadata={"chars": len(text)}
                )
            except Exception as e:
                return ToolResult(success=False, output="", error=f"Failed to write to clipboard: {e}")

        return ToolResult(success=False, output="", error=f"Unknown action: {action}")
