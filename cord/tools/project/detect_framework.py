"""CORD Tool - detect_framework"""
from __future__ import annotations
import json
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class DetectFrameworkTool(BaseTool):
    name = "detect_framework"
    description = "Identify backend and frontend web frameworks, CLI libraries, or AI SDKs used in the project."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to inspect",
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

            frameworks = set()

            # Check Python dependencies
            py_reqs = ""
            for req_file in ["requirements.txt", "pyproject.toml", "setup.py"]:
                f = target / req_file
                if f.exists():
                    try:
                        py_reqs += f.read_text(encoding="utf-8", errors="ignore").lower() + "\n"
                    except Exception:
                        pass

            py_framework_signatures = {
                "fastapi": "FastAPI",
                "flask": "Flask",
                "django": "Django",
                "tornado": "Tornado",
                "aiohttp": "aiohttp",
                "rich": "Rich CLI",
                "typer": "Typer CLI",
                "click": "Click CLI",
                "litellm": "LiteLLM",
                "langchain": "LangChain",
                "openai": "OpenAI SDK",
                "pydantic": "Pydantic",
                "sqlalchemy": "SQLAlchemy",
                "pytest": "PyTest"
            }
            for sig, label in py_framework_signatures.items():
                if sig in py_reqs:
                    frameworks.add(label)

            # Check JS/TS dependencies
            pkg_file = target / "package.json"
            if pkg_file.exists():
                try:
                    data = json.loads(pkg_file.read_text(encoding="utf-8", errors="ignore"))
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    js_framework_signatures = {
                        "react": "React",
                        "next": "Next.js",
                        "vue": "Vue",
                        "nuxt": "Nuxt.js",
                        "svelte": "Svelte",
                        "express": "Express",
                        "nest": "NestJS",
                        "tailwindcss": "TailwindCSS",
                        "electron": "Electron",
                        "vite": "Vite",
                        "webpack": "Webpack",
                        "jest": "Jest"
                    }
                    for sig, label in js_framework_signatures.items():
                        if sig in deps:
                            frameworks.add(label)
                except Exception:
                    pass

            if not frameworks:
                return ToolResult(success=True, output="No major frameworks explicitly recognized in dependencies.")

            output = "Detected Frameworks & Libraries:\n" + "\n".join(f"  - {f}" for f in sorted(frameworks))
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
