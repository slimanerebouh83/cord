"""CORD Tool - inspect_project"""
from __future__ import annotations
import os
import json
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class InspectProjectTool(BaseTool):
    name = "inspect_project"
    description = "Perform a comprehensive architecture and stack inspection of the current project workspace."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "root_path": {
                "type": "string",
                "description": "Root directory of the project (defaults to current workspace)",
                "default": "."
            }
        },
        "required": []
    }

    async def execute(self, root_path: str = ".", **kwargs) -> ToolResult:
        try:
            root = Path(root_path).resolve()
            if not root.exists() or not root.is_dir():
                return ToolResult(success=False, output="", error=f"Directory does not exist: {root_path}")

            summary: dict = {
                "project_name": root.name,
                "project_root": str(root),
                "configs_detected": [],
                "languages": {},
                "entry_points": [],
                "top_level_items": [],
            }

            # Top level items
            for item in sorted(root.iterdir()):
                if item.name.startswith(".") and item.name not in [".git", ".env", ".github", ".cord"]:
                    continue
                summary["top_level_items"].append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file"
                })

            # Check config files
            known_configs = [
                "pyproject.toml", "requirements.txt", "setup.py", "Pipfile", "poetry.lock",
                "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "tsconfig.json",
                "Cargo.toml", "Cargo.lock", "go.mod", "go.sum", "pom.xml", "build.gradle",
                "Dockerfile", "docker-compose.yml", "Makefile", ".env", "README.md"
            ]
            for cfg in known_configs:
                if (root / cfg).exists():
                    summary["configs_detected"].append(cfg)

            # Detect entry points
            candidates = ["main.py", "app.py", "index.py", "cli.py", "index.ts", "index.js", "src/main.rs", "main.go"]
            for cand in candidates:
                if (root / cand).exists():
                    summary["entry_points"].append(cand)

            # Sample languages by counting file extensions
            ext_counts: dict[str, int] = {}
            for path in root.rglob("*"):
                if any(p.startswith(".") or p in ["node_modules", "venv", ".venv", "__pycache__", "target", "dist", "build"] for p in path.parts):
                    continue
                if path.is_file():
                    ext = path.suffix.lower()
                    if ext:
                        ext_counts[ext] = ext_counts.get(ext, 0) + 1

            summary["file_extensions_distribution"] = dict(sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:10])

            report = json.dumps(summary, indent=2)
            return ToolResult(success=True, output=f"Project Inspection Report:\n{report}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
