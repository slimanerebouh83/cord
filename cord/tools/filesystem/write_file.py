"""CORD Tool - write_file"""
from __future__ import annotations
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Create or overwrite a file with specified content."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Target file path"},
            "content": {"type": "string", "description": "Exact content to write"}
        },
        "required": ["path", "content"]
    }

    async def execute(self, path: str, content: str, **kwargs) -> ToolResult:
        try:
            target = Path(path).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            old_lines = 0
            existed = target.exists()
            if existed:
                try:
                    old_lines = len(target.read_text(encoding="utf-8", errors="ignore").splitlines())
                except Exception:
                    old_lines = 0

            with open(target, "w", encoding="utf-8") as f:
                f.write(content)

            total_lines = len(content.splitlines())
            lines_added = total_lines if not existed else max(total_lines - old_lines, 0)
            lines_removed = 0 if not existed else max(old_lines - total_lines, 0)
            action = "Overwrote" if existed else "Created"

            delta_str = f"+{lines_added} lines" if not existed else f"+{lines_added} / -{lines_removed} lines"

            from cord.memory.sessions import session_manager
            session_manager.record_session_change(
                file_path=str(target),
                action="created" if not existed else "overwritten",
                diff=f"+{lines_added} lines written" if not existed else f"+{lines_added} / -{lines_removed} lines",
                lines_added=lines_added,
                lines_removed=lines_removed,
                description=f"{action} file ({total_lines} total lines)",
            )

            return ToolResult(
                success=True,
                output=f"Successfully {action.lower()} {target.name} ({delta_str}, {total_lines} total lines).",
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
