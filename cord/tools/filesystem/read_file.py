"""CORD Tool - read_file"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read file contents with line numbering and optional line ranges."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to file"},
            "start_line": {"type": "integer", "description": "1-indexed start line"},
            "end_line": {"type": "integer", "description": "1-indexed end line"}
        },
        "required": ["path"]
    }

    async def execute(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists() or not target.is_file():
                return ToolResult(success=False, output="", error=f"File not found: {path}")
            if target.stat().st_size > 5 * 1024 * 1024:
                return ToolResult(success=False, output="", error=f"File too large (>5MB): {path}")
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            s_idx = max(0, (start_line - 1) if start_line else 0)
            e_idx = min(len(lines), end_line if end_line else len(lines))
            out_lines = [f"{i:4d} | {lines[i-1].rstrip()}" for i in range(s_idx + 1, e_idx + 1)]
            header = f"--- {path} (Lines {s_idx + 1}-{e_idx} of {len(lines)}) ---\n"
            return ToolResult(success=True, output=header + "\n".join(out_lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
