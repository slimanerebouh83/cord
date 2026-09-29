"""
CORD Tools - Grep / Codebase Search
Fast regex and text search across project files.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import List, Optional

from cord.tools.base import BaseTool, ToolResult
from cord.tools.file_tools import ListDirTool


class GrepSearchTool(BaseTool):
    name = "grep_search"
    description = "Search for regex patterns or text across files in a directory. Returns matching line numbers and snippets."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Regex pattern or exact string to search for.",
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in (default: current directory).",
            },
            "file_pattern": {
                "type": "string",
                "description": "Optional glob filter for file names (e.g. '*.py', '*.json').",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Whether search is case-sensitive (default: false).",
            },
            "max_matches": {
                "type": "integer",
                "description": "Maximum number of matching lines to return (default: 50).",
            },
        },
        "required": ["query"],
    }

    async def execute(
        self,
        query: str,
        path: str = ".",
        file_pattern: Optional[str] = None,
        case_sensitive: bool = False,
        max_matches: int = 50,
        **kwargs,
    ) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                regex = re.compile(query, flags)
            except re.error as e:
                return ToolResult(success=False, output="", error=f"Invalid regex '{query}': {e}")

            matches = []
            files_to_scan = []

            if target.is_file():
                files_to_scan = [target]
            elif target.is_dir():
                glob_pat = file_pattern or "**/*"
                for p in target.glob(glob_pat):
                    if p.is_file() and not any(ig in p.parts for ig in ListDirTool.IGNORE_DIRS):
                        files_to_scan.append(p)
            else:
                return ToolResult(success=False, output="", error=f"Target not found: {path}")

            for fpath in files_to_scan:
                if len(matches) >= max_matches:
                    break
                try:
                    # Skip binary / large files
                    if fpath.stat().st_size > 2 * 1024 * 1024:
                        continue
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for idx, line in enumerate(f, start=1):
                            if regex.search(line):
                                rel_path = fpath.relative_to(target) if target.is_dir() else fpath.name
                                matches.append(f"{rel_path}:{idx}: {line.strip()[:160]}")
                                if len(matches) >= max_matches:
                                    break
                except Exception:
                    continue

            if not matches:
                return ToolResult(success=True, output=f"No matches found for query: '{query}'")

            header = f"Found {len(matches)} match(es) for '{query}':\n"
            return ToolResult(success=True, output=header + "\n".join(matches))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
