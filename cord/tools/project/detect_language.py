"""CORD Tool - detect_language"""
from __future__ import annotations
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

EXTENSION_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".jsx": "JavaScript (React)",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".cs": "C#",
    ".php": "PHP",
    ".rb": "Ruby",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
    ".sh": "Shell",
    ".ps1": "PowerShell"
}

class DetectLanguageTool(BaseTool):
    name = "detect_language"
    description = "Detect dominant programming languages in the current workspace or directory."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to scan (defaults to current directory)",
                "default": "."
            }
        },
        "required": []
    }

    async def execute(self, path: str = ".", **kwargs) -> ToolResult:
        try:
            target = Path(path).resolve()
            if not target.exists():
                return ToolResult(success=False, output="", error=f"Path not found: {path}")

            counts: dict[str, int] = {}
            total_files = 0

            for p in target.rglob("*"):
                if any(part.startswith(".") or part in ["node_modules", "venv", ".venv", "__pycache__", "target", "dist", "build"] for part in p.parts):
                    continue
                if p.is_file():
                    ext = p.suffix.lower()
                    if ext in EXTENSION_MAP:
                        lang = EXTENSION_MAP[ext]
                        counts[lang] = counts.get(lang, 0) + 1
                        total_files += 1

            if not counts:
                return ToolResult(success=True, output="No recognized programming languages found in this directory.")

            sorted_langs = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            output_lines = [f"Language breakdown for {target.name} ({total_files} total recognized code files):"]
            for lang, count in sorted_langs:
                pct = (count / total_files) * 100
                output_lines.append(f"  - {lang}: {count} files ({pct:.1f}%)")

            return ToolResult(success=True, output="\n".join(output_lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
