"""CORD Tool - edit_file"""
from __future__ import annotations
import difflib
from pathlib import Path
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.memory.sessions import session_manager


class EditFileTool(BaseTool):
    name = "edit_file"
    description = (
        "Surgically edit a file by replacing old_content, replacing/deleting a line range "
        "(start_line to end_line), or inserting lines. Set new_content='' to delete lines."
    )
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to file to edit"},
            "old_content": {"type": "string", "description": "Exact or approximate text to replace (optional if start_line is provided)"},
            "new_content": {"type": "string", "description": "Replacement text, or empty string '' to delete target lines"},
            "start_line": {"type": "integer", "description": "1-indexed starting line number for line-based replacement or deletion"},
            "end_line": {"type": "integer", "description": "1-indexed ending line number (defaults to start_line if omitted)"},
            "insert_after_line": {"type": "integer", "description": "1-indexed line number after which to insert new_content without deleting lines"}
        },
        "required": ["path"]
    }

    async def execute(
        self,
        path: str,
        old_content: Optional[str] = None,
        new_content: str = "",
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        insert_after_line: Optional[int] = None,
        **kwargs
    ) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return ToolResult(success=False, output="", error=f"File not found: {path}")

            orig = target.read_text(encoding="utf-8", errors="replace")
            orig_lines = orig.replace("\r\n", "\n").splitlines()
            norm_new = (new_content or "").replace("\r\n", "\n")
            updated_lines = list(orig_lines)
            matched_mode = "search_replace"

            # 1. Line range insertion mode
            if insert_after_line is not None:
                matched_mode = f"insert_after_line_{insert_after_line}"
                idx = max(0, min(insert_after_line, len(orig_lines)))
                insertion = norm_new.splitlines()
                updated_lines = orig_lines[:idx] + insertion + orig_lines[idx:]

            # 2. Line range replacement / deletion mode
            elif start_line is not None:
                matched_mode = f"lines_{start_line}"
                s_idx = max(1, start_line) - 1
                e_idx = max(s_idx + 1, end_line if end_line is not None else start_line)
                s_idx = min(s_idx, len(orig_lines))
                e_idx = min(e_idx, len(orig_lines))

                replacement = norm_new.splitlines() if norm_new else []
                updated_lines = orig_lines[:s_idx] + replacement + orig_lines[e_idx:]

            # 3. Text search and replace mode
            elif old_content is not None:
                norm_orig = "\n".join(orig_lines)
                norm_old = old_content.replace("\r\n", "\n")

                if norm_old in norm_orig:
                    if norm_orig.count(norm_old) > 1:
                        return ToolResult(
                            success=False,
                            output="",
                            error=f"Multiple occurrences of old_content in {path}. Provide more surrounding lines or use start_line/end_line."
                        )
                    updated_text = norm_orig.replace(norm_old, norm_new, 1)
                    updated_lines = updated_text.splitlines()
                else:
                    # Fuzzy whitespace-tolerant fallback
                    old_sub_lines = [l.strip() for l in norm_old.splitlines() if l.strip()]
                    found_start = -1
                    if old_sub_lines:
                        for i in range(len(orig_lines) - len(old_sub_lines) + 1):
                            match = True
                            for j, target_l in enumerate(old_sub_lines):
                                if orig_lines[i + j].strip() != target_l:
                                    match = False
                                    break
                            if match:
                                found_start = i
                                break

                    if found_start != -1:
                        found_end = found_start + len(old_sub_lines)
                        replacement = norm_new.splitlines() if norm_new else []
                        updated_lines = orig_lines[:found_start] + replacement + orig_lines[found_end:]
                        matched_mode = "fuzzy_whitespace"
                    else:
                        return ToolResult(
                            success=False,
                            output="",
                            error=f"old_content not found in {path}. Verify the exact lines with read_file or use start_line/end_line."
                        )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error="Either old_content, start_line, or insert_after_line must be specified."
                )

            updated = "\n".join(updated_lines)
            if orig and orig.endswith("\n") and not updated.endswith("\n"):
                updated += "\n"

            # Compute unified diff
            diff_lines = list(difflib.unified_diff(
                orig_lines,
                updated_lines,
                fromfile=f"a/{target.name}",
                tofile=f"b/{target.name}",
                lineterm=""
            ))
            diff = "\n".join(diff_lines)
            lines_added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
            lines_removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

            # Write changes to disk
            target.write_text(updated, encoding="utf-8")

            # Record in session changelog
            session_manager.record_session_change(
                file_path=str(target),
                action="deleted" if not updated.strip() else "edited",
                diff=diff,
                lines_added=lines_added,
                lines_removed=lines_removed,
                description=f"Surgical edit ({matched_mode})",
            )

            action_desc = "Deleted" if (not norm_new and (start_line or old_content)) else "Updated"
            return ToolResult(
                success=True,
                output=f"{action_desc} {target.name} (+{lines_added} / -{lines_removed} lines via {matched_mode}).\nDiff:\n{diff}",
                metadata={
                    "file": str(target),
                    "filename": target.name,
                    "lines_added": lines_added,
                    "lines_removed": lines_removed,
                    "diff": diff,
                    "new_content": norm_new,
                    "mode": matched_mode,
                }
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
