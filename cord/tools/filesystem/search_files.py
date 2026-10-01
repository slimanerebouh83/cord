"""CORD Tool - search_files"""
from __future__ import annotations
import os
import re
import fnmatch
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

    IGNORE_DIRS = {
        ".git", "node_modules", "appdata", ".cache", "__pycache__", ".venv",
        "venv", ".idea", ".vscode", ".android", "dist", "build", ".next",
        "target", ".cargo", ".rustup", "codex-runtimes", "cua_node",
    }

    async def execute(self, query: str, path: str = ".", file_pattern: Optional[str] = None, max_matches: int = 50, **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return ToolResult(success=True, output=f"Directory or file does not exist: {path}")

            try:
                regex = re.compile(query, re.IGNORECASE)
            except re.error as e:
                return ToolResult(success=False, output="", error=f"Invalid regex: {e}")

            matches = []

            if target.is_file():
                files = [target]
            else:
                files = []
                for root_dir, dirs, filenames in os.walk(str(target), followlinks=False, onerror=lambda _: None):
                    dirs[:] = [d for d in dirs if d.lower() not in self.IGNORE_DIRS and not d.startswith(".")]
                    for fname in filenames:
                        if file_pattern and not fnmatch.fnmatch(fname.lower(), file_pattern.lower()):
                            continue
                        files.append(Path(root_dir) / fname)
                        if len(files) >= 1500:
                            break
                    if len(files) >= 1500:
                        break

            for f in files:
                if len(matches) >= max_matches:
                    break
                try:
                    st = f.stat()
                    if st.st_size > 2 * 1024 * 1024:
                        continue
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    for idx, line in enumerate(content.splitlines(), start=1):
                        if regex.search(line):
                            try:
                                rel = f.relative_to(target)
                            except Exception:
                                rel = f.name
                            matches.append(f"{rel}:{idx}: {line.strip()[:160]}")
                            if len(matches) >= max_matches:
                                break
                except (OSError, FileNotFoundError, PermissionError):
                    continue
                except Exception:
                    continue

            if not matches:
                return ToolResult(success=True, output=f"No matches for '{query}' in {path}")
            return ToolResult(success=True, output=f"Found {len(matches)} matches for '{query}':\n" + "\n".join(matches))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
