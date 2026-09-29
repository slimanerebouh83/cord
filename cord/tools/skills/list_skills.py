"""CORD Tool - list_skills"""
from __future__ import annotations
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class ListSkillsTool(BaseTool):
    name = "list_skills"
    description = "List all available skills discovered in the current workspace (.cord/skills) and global directory (~/.cord/skills)."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        try:
            seen_skills = set()
            skills = []
            dirs_to_check = [
                ("GLOBAL", Path.home() / ".cord" / "skills"),
                ("WORKSPACE", Path.cwd() / ".cord" / "skills"),
            ]

            for scope, d in dirs_to_check:
                if d.exists():
                    for skill_dir in d.iterdir():
                        if skill_dir.is_dir():
                            skill_file = skill_dir / "SKILL.md"
                            if skill_file.exists():
                                skill_name = skill_dir.name
                                if skill_name in seen_skills:
                                    continue
                                seen_skills.add(skill_name)
                                desc = "No description"
                                try:
                                    for line in skill_file.read_text(encoding="utf-8").splitlines():
                                        if line.startswith("description:"):
                                            desc = line.split("description:", 1)[1].strip()
                                            break
                                except Exception:
                                    pass
                                skills.append(f"- `[{scope}]` **{skill_name}**: {desc}")

            if not skills:
                return ToolResult(success=True, output="No custom skills currently defined. You can create one using 'create_skill'.")

            output = "Available Skills:\n" + "\n".join(skills)
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
