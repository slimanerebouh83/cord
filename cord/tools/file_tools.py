"""
CORD Tools - File Operations (Read, Write, Edit, List, Find)
"""

from __future__ import annotations
import os
import difflib
from pathlib import Path
from typing import Any, Dict, List, Optional

from cord.tools.base import BaseTool, ToolResult
from cord.ui.console import ui


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the contents of a file with optional line ranges. Returns numbered lines."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read (relative to workspace or absolute).",
            },
            "start_line": {
                "type": "integer",
                "description": "Optional 1-indexed starting line number.",
            },
            "end_line": {
                "type": "integer",
                "description": "Optional 1-indexed ending line number (inclusive).",
            },
        },
        "required": ["path"],
    }

    async def execute(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return ToolResult(success=False, output="", error=f"File not found: {path}")
            if not target.is_file():
                return ToolResult(success=False, output="", error=f"Path is not a file: {path}")

            # Check file size (cap at 5MB)
            if target.stat().st_size > 5 * 1024 * 1024:
                return ToolResult(success=False, output="", error=f"File is too large (>5MB): {path}")

            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            s_idx = max(0, (start_line - 1) if start_line else 0)
            e_idx = min(total_lines, end_line if end_line is not None else total_lines)

            selected_lines = lines[s_idx:e_idx]
            output_parts = []
            for i, line in enumerate(selected_lines, start=s_idx + 1):
                output_parts.append(f"{i:4d} | {line.rstrip()}")

            header = f"--- {path} (Lines {s_idx + 1}-{e_idx} of {total_lines}) ---\n"
            return ToolResult(success=True, output=header + "\n".join(output_parts))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Create a new file or overwrite an existing file with the provided content."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to create or overwrite.",
            },
            "content": {
                "type": "string",
                "description": "The exact content to write into the file.",
            },
        },
        "required": ["path", "content"],
    }

    async def execute(self, path: str, content: str, **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            
            existed = target.exists()
            old_len = len(target.read_text(encoding="utf-8", errors="replace").splitlines()) if existed else 0

            with open(target, "w", encoding="utf-8") as f:
                f.write(content)

            total_lines = len(content.splitlines())
            lines_added = total_lines if not existed else max(total_lines - old_len, 0)
            lines_removed = 0 if not existed else max(old_len - total_lines, 0)
            action = "Overwrote" if existed else "Created"
            delta_str = f"+{lines_added} lines" if not existed else f"+{lines_added} / -{lines_removed} lines"
            msg = f"Successfully {action.lower()} {target.name} ({delta_str}, {total_lines} total lines)."
            ui.print_success(msg)
            return ToolResult(
                success=True,
                output=msg,
                metadata={
                    "file": str(target),
                    "filename": target.name,
                    "lines_added": lines_added,
                    "lines_removed": lines_removed,
                    "action": action.lower(),
                    "total_lines": total_lines,
                    "snippet": "\n".join(content.splitlines()[:15]),
                }
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class EditFileTool(BaseTool):
    name = "edit_file"
    description = "Precisely edit a file by replacing old_content with new_content. Generates unified diff."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to edit.",
            },
            "old_content": {
                "type": "string",
                "description": "The exact block of code/text to be replaced.",
            },
            "new_content": {
                "type": "string",
                "description": "The new replacement text.",
            },
        },
        "required": ["path", "old_content", "new_content"],
    }

    async def execute(self, path: str, old_content: str, new_content: str, **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return ToolResult(success=False, output="", error=f"File not found: {path}")

            with open(target, "r", encoding="utf-8", errors="replace") as f:
                original = f.read()

            # Normalize line endings for reliable matching
            norm_orig = original.replace("\r\n", "\n")
            norm_old = old_content.replace("\r\n", "\n")
            norm_new = new_content.replace("\r\n", "\n")

            if norm_old not in norm_orig:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Target old_content not found in {path}. Make sure the code snippet matches exactly.",
                )

            count = norm_orig.count(norm_old)
            if count > 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Found {count} occurrences of old_content in {path}. Please provide a larger unique context block.",
                )

            updated = norm_orig.replace(norm_old, norm_new, 1)

            # Generate diff preview
            diff_lines = list(
                difflib.unified_diff(
                    norm_orig.splitlines(),
                    updated.splitlines(),
                    fromfile=f"a/{target.name}",
                    tofile=f"b/{target.name}",
                    lineterm="",
                )
            )
            diff_text = "\n".join(diff_lines)
            lines_added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
            lines_removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

            # Write file back
            with open(target, "w", encoding="utf-8") as f:
                f.write(updated)

            ui.print_diff(path, diff_text)
            ui.print_success(f"Updated {target.name} (+{lines_added} / -{lines_removed} lines)")
            return ToolResult(
                success=True,
                output=f"Successfully updated {target.name} (+{lines_added} / -{lines_removed} lines).\nDiff:\n{diff_text}",
                metadata={
                    "file": str(target),
                    "filename": target.name,
                    "lines_added": lines_added,
                    "lines_removed": lines_removed,
                    "diff": diff_text,
                    "new_content": norm_new,
                    "old_content": norm_old,
                }
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListDirTool(BaseTool):
    name = "list_dir"
    description = "List files and subdirectories within a directory path."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path of directory to list (defaults to current workspace directory).",
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum recursive traversal depth (default 2).",
            },
        },
        "required": [],
    }

    IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode", "dist", "build"}

    async def execute(self, path: str = ".", max_depth: int = 2, **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists() or not target.is_dir():
                return ToolResult(success=False, output="", error=f"Directory does not exist: {path}")

            results: List[str] = []
            
            def scan(curr: Path, depth: int, prefix: str):
                if depth > max_depth:
                    return
                try:
                    entries = sorted(list(curr.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
                except PermissionError:
                    return

                for entry in entries:
                    if entry.name in self.IGNORE_DIRS:
                        continue
                    try:
                        if entry.is_dir():
                            results.append(f"{prefix}📁 {entry.name}/")
                            scan(entry, depth + 1, prefix + "  ")
                        else:
                            size_kb = entry.stat().st_size / 1024
                            size_str = f"{size_kb:.1f}KB" if size_kb >= 1 else f"{entry.stat().st_size}B"
                            results.append(f"{prefix}📄 {entry.name} ({size_str})")
                    except PermissionError:
                        continue

            scan(target, 1, "")
            out = f"Contents of {target} (max depth {max_depth}):\n" + "\n".join(results[:150])
            if len(results) > 150:
                out += f"\n... ({len(results) - 150} more items)"
            return ToolResult(success=True, output=out)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class FindFilesTool(BaseTool):
    name = "find_files"
    description = "Search for files by glob pattern (e.g. '*.py', '**/test_*.js')."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match files.",
            },
            "path": {
                "type": "string",
                "description": "Base directory to start searching from (default: current directory).",
            },
        },
        "required": ["pattern"],
    }

    async def execute(self, pattern: str, path: str = ".", **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            matches = list(target.glob(pattern))
            
            # Filter out ignored dirs
            filtered = [
                m for m in matches 
                if not any(ig in m.parts for ig in ListDirTool.IGNORE_DIRS)
            ]

            lines = [str(m.relative_to(target) if m.is_relative_to(target) else m) for m in filtered[:100]]
            out = f"Found {len(filtered)} file(s) matching '{pattern}':\n" + "\n".join(lines)
            return ToolResult(success=True, output=out)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
