"""CORD Tool - improve_skill"""
from __future__ import annotations
import re
from pathlib import Path
from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel

class ImproveSkillTool(BaseTool):
    name = "improve_skill"
    description = "Update, append new findings, or refine instructions in an existing skill."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name of the skill to update"
            },
            "new_instructions": {
                "type": "string",
                "description": "Additional rules, edge case notes, or improved workflow instructions to integrate"
            },
            "mode": {
                "type": "string",
                "enum": ["append", "replace"],
                "description": "'append' adds new notes at the end of the skill; 'replace' overwrites the skill body",
                "default": "append"
            }
        },
        "required": ["name", "new_instructions"]
    }

    async def execute(self, name: str, new_instructions: str, mode: str = "append", **kwargs) -> ToolResult:
        try:
            clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "", name.strip().lower().replace(" ", "-"))
            global_skill_file = Path.home() / ".cord" / "skills" / clean_name / "SKILL.md"
            local_skill_file = Path.cwd() / ".cord" / "skills" / clean_name / "SKILL.md"

            target_files = []
            if global_skill_file.exists():
                target_files.append(global_skill_file)
            if local_skill_file.exists():
                target_files.append(local_skill_file)

            if not target_files:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Skill '{clean_name}' not found in global or workspace skills. Use 'create_skill' to create it first.",
                )

            # Read from the primary existing file
            primary_file = target_files[0]
            existing_content = primary_file.read_text(encoding="utf-8")

            if mode == "append":
                updated = (
                    f"{existing_content.rstrip()}\n\n"
                    f"### Updated Notes & Improvements:\n"
                    f"{new_instructions.strip()}\n"
                )
            else:
                # Keep frontmatter if present
                if existing_content.startswith("---"):
                    parts = existing_content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1]
                        updated = f"---{frontmatter}---\n\n{new_instructions.strip()}\n"
                    else:
                        updated = new_instructions.strip()
                else:
                    updated = new_instructions.strip()

            for tf in target_files:
                tf.write_text(updated, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"✔ Skill '{clean_name}' has been successfully improved and saved globally at:\n  {target_files[0]}"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to improve skill: {e}")
