"""CORD Tool - search_files"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class SearchFilesTool(BaseTool):
    name = "search_files"
    description = "Search for regex patterns or text across workspace files."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Regex pattern or string to search for"},
            "path": {"type": "string", "description": "Directory to search (default: '.')"},
            "file_pattern": {"type": "string", "description": "Glob filter (e.g. '*.py')"},
            "max_matches": {"type": "integer", "description": "Max matching lines (default: 50)"}
        },
        "required": ["query"]
    }

    async def execute(self, query: str, path: str = ".", file_pattern: Optional[str] = None, max_matches: int = 50, **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            regex = re.compile(query, re.IGNORECASE)
            matches = []
            files = list(target.glob(file_pattern or "**/*")) if target.is_dir() else [target]
            for f in files:
                if len(matches) >= max_matches: break
                if not f.is_file() or f.stat().st_size > 2 * 1024 * 1024: continue
                try:
                    for idx, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                        if regex.search(line):
                            rel = f.relative_to(target) if target.is_dir() else f.name
                            matches.append(f"{rel}:{idx}: {line.strip()[:160]}")
                            if len(matches) >= max_matches: break
                except Exception: continue
            if not matches:
                return ToolResult(success=True, output=f"No matches for '{query}'")
            return ToolResult(success=True, output=f"Found {len(matches)} matches for '{query}':\n" + "\n".join(matches))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
