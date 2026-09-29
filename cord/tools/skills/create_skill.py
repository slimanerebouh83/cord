"""CORD Tool - create_skill"""
from __future__ import annotations
import re
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class CreateSkillTool(BaseTool):
    name = "create_skill"
    description = "Create and persist a new reusable skill/workflow in .cord/skills/<name>/SKILL.md so CORD remembers specialized patterns."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Unique identifier for the skill (e.g. 'fastapi-auth-flow', 'docker-compose-patterns')"
            },
            "description": {
                "type": "string",
                "description": "Brief 1-line summary of what this skill does and when to use it"
            },
            "instructions": {
                "type": "string",
                "description": "Comprehensive markdown instructions, rules, best practices, and code examples for this skill"
            }
        },
        "required": ["name", "description", "instructions"]
    }

    async def execute(self, name: str, description: str, instructions: str, **kwargs) -> ToolResult:
        try:
            clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "", name.strip().lower().replace(" ", "-"))
            if not clean_name:
                return ToolResult(success=False, output="", error="Invalid skill name provided.")

            # 1. Primary Global Storage: ~/.cord/skills/<clean_name>/SKILL.md
            global_skills_dir = Path.home() / ".cord" / "skills" / clean_name
            global_skills_dir.mkdir(parents=True, exist_ok=True)
            global_skill_file = global_skills_dir / "SKILL.md"

            content = (
                f"---\n"
                f"name: {clean_name}\n"
                f"description: {description.strip()}\n"
                f"---\n\n"
                f"{instructions.strip()}\n"
            )

            global_skill_file.write_text(content, encoding="utf-8")

            # 2. Workspace Mirror (if .cord exists in current workspace)
            local_skills_dir = Path.cwd() / ".cord" / "skills" / clean_name
            try:
                local_skills_dir.mkdir(parents=True, exist_ok=True)
                (local_skills_dir / "SKILL.md").write_text(content, encoding="utf-8")
            except Exception:
                pass

            return ToolResult(
                success=True,
                output=(
                    f"✔ Skill '{clean_name}' successfully created in global persistent repository:\n"
                    f"  {global_skill_file}\n"
                    f"This skill is permanently available across ALL projects, workspaces, and future conversations."
                )
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to create skill: {e}")
