"""CORD Tool - list_directory"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class ListDirectoryTool(BaseTool):
    name = "list_directory"
    description = "List files and folders within a directory path with sizes and types."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to directory (default: '.')"},
            "max_depth": {"type": "integer", "description": "Max folder depth (default: 2)"}
        },
        "required": []
    }
    IGNORE = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea"}

    async def execute(self, path: str = ".", max_depth: int = 2, **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists() or not target.is_dir():
                return ToolResult(success=False, output="", error=f"Directory not found: {path}")
            results = []
            def scan(curr: Path, depth: int, prefix: str):
                if depth > max_depth: return
                try:
                    entries = sorted(list(curr.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
                except Exception: return
                for e in entries:
                    if e.name in self.IGNORE: continue
                    if e.is_dir():
                        results.append(f"{prefix}📁 {e.name}/")
                        scan(e, depth + 1, prefix + "  ")
                    else:
                        size_kb = e.stat().st_size / 1024
                        size_str = f"{size_kb:.1f}KB" if size_kb >= 1 else f"{e.stat().st_size}B"
                        results.append(f"{prefix}📄 {e.name} ({size_str})")
            scan(target, 1, "")
            out = f"Directory {target} (depth {max_depth}):\n" + "\n".join(results[:150])
            return ToolResult(success=True, output=out)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
