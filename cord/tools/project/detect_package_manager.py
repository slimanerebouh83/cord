"""CORD Tool - detect_package_manager"""
from __future__ import annotations
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class DetectPackageManagerTool(BaseTool):
    name = "detect_package_manager"
    description = "Detect package managers configured in the current workspace (npm, pnpm, yarn, bun, pip, poetry, uv, cargo, etc.)."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to inspect (default: '.')",
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

            managers = []

            # JavaScript / TypeScript ecosystem
            if (target / "pnpm-lock.yaml").exists():
                managers.append({"ecosystem": "Node.js", "manager": "pnpm", "indicator": "pnpm-lock.yaml"})
            elif (target / "yarn.lock").exists():
                managers.append({"ecosystem": "Node.js", "manager": "yarn", "indicator": "yarn.lock"})
            elif (target / "bun.lockb").exists() or (target / "bun.lock").exists():
                managers.append({"ecosystem": "Node.js", "manager": "bun", "indicator": "bun lockfile"})
            elif (target / "package-lock.json").exists():
                managers.append({"ecosystem": "Node.js", "manager": "npm", "indicator": "package-lock.json"})
            elif (target / "package.json").exists():
                managers.append({"ecosystem": "Node.js", "manager": "npm (fallback)", "indicator": "package.json"})

            # Python ecosystem
            if (target / "poetry.lock").exists():
                managers.append({"ecosystem": "Python", "manager": "poetry", "indicator": "poetry.lock"})
            elif (target / "Pipfile.lock").exists():
                managers.append({"ecosystem": "Python", "manager": "pipenv", "indicator": "Pipfile.lock"})
            elif (target / "uv.lock").exists():
                managers.append({"ecosystem": "Python", "manager": "uv", "indicator": "uv.lock"})
            elif (target / "requirements.txt").exists() or (target / "pyproject.toml").exists() or (target / "setup.py").exists():
                managers.append({"ecosystem": "Python", "manager": "pip", "indicator": "requirements.txt / pyproject.toml"})

            # Rust ecosystem
            if (target / "Cargo.toml").exists():
                managers.append({"ecosystem": "Rust", "manager": "cargo", "indicator": "Cargo.toml"})

            # Go ecosystem
            if (target / "go.mod").exists():
                managers.append({"ecosystem": "Go", "manager": "go modules", "indicator": "go.mod"})

            if not managers:
                return ToolResult(success=True, output="No standard package managers detected in workspace.")

            lines = ["Detected Package Managers:"]
            for m in managers:
                lines.append(f"  - [{m['ecosystem']}] {m['manager']} (detected via {m['indicator']})")

            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
